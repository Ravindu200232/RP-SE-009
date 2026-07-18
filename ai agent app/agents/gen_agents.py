"""agents/gen_agents.py — the rule-based generation agents (v2 engine).

Each agent reads its RULE doc plus the complete product-context/v1 contract, asks local Gemma 4
to generate ONE artifact, streams the code live, extracts it, and writes the file. No templates —
the rules + Architect plan are the only structure. Generation writes whole files; the separate
bugfix_agent does surgical line-level fixes.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path

from agents import llm
from agents.analyzer import format_diagnostics
from agents.scaffold import pascal, route_name

RULES_DIR = Path(__file__).parent / "rules"

SYSTEM = (
    "You are Gemma 4 acting as a senior Next.js 16 (App Router), React 19, TypeScript and Mongoose "
    "code generator. Thinking is disabled: start immediately with the first code token. Never emit "
    "analysis, a plan, private thoughts, self-check narration, or channel/control markers. "
    "You write production code that compiles with `next build` under strict TypeScript. "
    "You output ONLY the code for the single requested file — no markdown fences, no prose, "
    "no explanation, no notes. Emit exactly one implementation and one default export; never append "
    "a second corrected/reimplemented version of the file. Follow the RULE exactly and stay consistent with the complete "
    "PRODUCT CONTEXT. The UI stack is Tailwind CSS + the installed shadcn primitives + Lucide icons."
)

REPAIR_SYSTEM = (
    "You repair one small TypeScript file from exact compiler diagnostics. Return only one or more "
    "<<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks. SEARCH text must be copied exactly from the "
    "candidate. Thinking is disabled; begin with <<<<<<< SEARCH and emit no analysis or channel "
    "markers. Make the smallest real fix; never suppress a diagnostic or change product behaviour."
)

_FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
_CODE_START = ("'use client'", '"use client"', "import ", "export ", "//", "/*",
               "const ", "let ", "type ", "interface ", "function ", "async ")
_preflight_lock = threading.Lock()
_preflight_metrics = {"candidates": 0, "rawClean": 0, "microRepaired": 0, "failed": 0}


def reset_preflight_metrics() -> None:
    with _preflight_lock:
        for key in _preflight_metrics:
            _preflight_metrics[key] = 0


def preflight_metrics() -> dict:
    with _preflight_lock:
        value = dict(_preflight_metrics)
    value["rawFirstCandidateCleanRate"] = round(
        value["rawClean"] / value["candidates"], 4) if value["candidates"] else None
    return value


def _count_preflight(key: str) -> None:
    with _preflight_lock:
        _preflight_metrics[key] += 1

# `className="p-8 text-red-500\">` — the model occasionally escapes the closing quote of a JSX
# attribute. JSX attribute values are raw (no escape processing), so the backslash ends the value
# early and SWC dies with `Expected '</', got 'jsx text'`. It is unfixable by the repair LLM (three
# passes and a cloud escalation never landed it) and trivially fixable here. Matching `name="` with no
# space leaves real JS escapes (`const s = "he said \"hi\""`) untouched — those never follow `name="`.
_JSX_ESCAPED_QUOTE = re.compile(r'(\s[A-Za-z][\w:.-]*=")([^"\n]*?)\\+(")')
# A multiline Tailwind template starts with ``className={` `` but Gemma occasionally closes it
# with a plain double quote. Everything after that is parsed as an unterminated template, obscuring
# otherwise-correct closing tags. The opening delimiter makes the intended `` `}`` unambiguous.
_MISMATCHED_TEMPLATE_CLASS = re.compile(
    r"className=\{`(?P<body>(?:(?!`}\s*>).)*?)\"(?P<close>\s*>)", re.DOTALL
)
# The inverse delimiter typo also occurs: a plain quoted class starts with ``className="`` and
# Gemma closes it as though it were a template expression (```} >``).  There can be no useful
# interpolation in this form, so restoring the matching quote is an exact lexical correction.
_MISMATCHED_QUOTED_CLASS = re.compile(
    r'className="(?P<body>[^"`\r\n]*)`}(?P<close>\s*>)'
)

# `{error && <Alert …>{error}</Alert}` — inside a JSX expression container the model types the
# container's `}` but drops the tag's `>`. A closing tag can only end in `>`, so this is always a typo
# and always fatal ("Expected '</', got '}'"); the repair model burned a whole build-fix loop on it and
# gave up. Rewriting to `</Alert>` alone just moves the error — that `}` was closing the container — so
# brace balance decides whether the `}` is kept.
_BAD_CLOSE = re.compile(r"</\s*([A-Za-z][\w.]*)\s*\}")
_BAD_FRAGMENT_CLOSE = re.compile(r"</>\s*>")
_EXTRA_CLOSING_TAG_CHEVRON = re.compile(r"</([A-Za-z][\w.-]*)>\s*>")
_UNCLOSED_TRUE_TERNARY_FRAGMENT = re.compile(
    r"(?P<open>\?\s*\(\s*<>)(?P<body>(?:(?!</>).)*?)(?P<boundary>\)\s*:\s*\()",
    re.DOTALL,
)
_UNCLOSED_FALSE_TERNARY_FRAGMENT = re.compile(
    r"(?P<open>:\s*\(\s*<>)(?P<body>(?:(?!</>).)*?)(?P<boundary>\)\s*\})",
    re.DOTALL,
)


def _close_ternary_fragment(match: re.Match) -> str:
    body = match.group("body")
    trailing_indent = re.search(r"\n([ \t]*)\Z", body)
    indent = trailing_indent.group(1) if trailing_indent else ""
    return (match.group("open") + body.rstrip() + f"\n{indent}</>\n{indent}"
            + match.group("boundary"))


def _fix_bad_closes(content: str) -> tuple[str, int]:
    out, fixed = [], 0
    for line in content.split("\n"):
        if _BAD_CLOSE.search(line):
            # Balanced braces mean this `}` closes a container opened on this line → keep it (`>}`).
            # A surplus `}` means the container closes elsewhere → the brace is spurious (`>`).
            keep = line.count("}") <= line.count("{")
            line, k = _BAD_CLOSE.subn(r"</\1>}" if keep else r"</\1>", line)
            fixed += k
        out.append(line)
    return "\n".join(out), fixed


def _fix_malformed_data_image_class(content: str) -> tuple[str, int]:
    """Drop an unterminated Tailwind data-image token while preserving its gradient children."""
    out, fixed = [], 0
    for line in content.split("\n"):
        marker = "bg-[url('data:image/"
        if "<div" in line and 'className="' in line and marker in line:
            prefix = line.split(marker, 1)[0].rstrip()
            if "absolute" in prefix and "pointer-events-none" not in prefix:
                prefix = prefix.replace('className="', 'className="pointer-events-none ', 1)
            line = prefix + '">' 
            fixed += 1
        out.append(line)
    return "\n".join(out), fixed


def _fix_split_self_closing_tag(content: str) -> tuple[str, int]:
    """Join ``<div ...>`` followed only by ``/>`` into one valid self-closing tag."""
    pattern = re.compile(
        r"<(?P<tag>[A-Za-z][\w.-]*)(?P<attrs>[^<>]*?)>\s*\n[ \t]*/>", re.DOTALL
    )
    return pattern.subn(
        lambda match: f"<{match.group('tag')}{match.group('attrs').rstrip()} />", content)


def _fix_unclosed_text_only_links(content: str) -> tuple[str, int]:
    """Close a Link whose text body reaches the next JSX tag without ``</Link>``.

    This is lexical and unambiguous: a text-only Link cannot legally absorb the following sibling.
    Links that intentionally contain another JSX element, or already meet ``</Link>``, are untouched.
    """
    pattern = re.compile(r"<Link\b[^>]*>(?P<body>[^<]+)", re.DOTALL)
    fixed = 0

    def close(match: re.Match) -> str:
        nonlocal fixed
        if content.startswith("</Link", match.end()):
            return match.group(0)
        body = match.group("body")
        if not body.strip():
            return match.group(0)
        trailing = body[len(body.rstrip()):]
        fixed += 1
        return match.group(0)[:match.start("body") - match.start()] + body.rstrip() + "</Link>" + trailing

    return pattern.sub(close, content), fixed


def _fix_surplus_jsx_closing_tags(content: str) -> tuple[str, int]:
    """Remove closing tags that have no matching open tag in the parsed JSX stack."""
    stack: list[str] = []
    removals: list[tuple[int, int]] = []
    for start, closing, name, self_closing in _iter_jsx_tags(content):
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
            elif name in stack:
                while stack and stack[-1] != name:
                    stack.pop()
                if stack:
                    stack.pop()
            else:
                end = content.find(">", start)
                if end >= 0:
                    removals.append((start, end + 1))
        elif not self_closing and name not in _VOID_TAGS:
            stack.append(name)
    for start, end in reversed(removals):
        content = content[:start] + content[end:]
    return content, len(removals)

# `from '@types'` — the model drops the slash out of the path alias. tsconfig maps `@/*` and nothing
# else, so `@types`, `@components/x`, `@lib/x` are never resolvable; the intent is unambiguous.
_ALIAS_IMPORT = re.compile(r"(from\s+['\"])@(types|components|lib|models)(['\"/])")

# `import { Link } from 'next/link'` — these modules export a DEFAULT, and only a default. The named
# form is always wrong ("has no exported member 'Link'"); the compiler even suggests the fix, but that
# costs a regeneration to apply. `{ useRouter }` from next/navigation is a real named export — only
# the single-default modules belong here.
_DEFAULT_IMPORT = re.compile(r"import\s*\{\s*(Link|Image|Head|Script|Document)\s*\}\s*from\s*"
                             r"(['\"])next/(link|image|head|script|document)\2")

# A model completion can contain one unambiguous omitted child closing tag, for example
# `<CardHeader><CardTitle>...</CardHeader>`.  That is not a design decision and asking an LLM to
# rewrite 20KB of otherwise-valid source to add nine characters is both slow and less reliable.
# Repair only the unambiguous case where a closing tag names an ancestor already on the open-tag
# stack; the compiler still validates the result immediately afterwards.
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
              "param", "source", "track", "wbr"}


def _iter_jsx_tags(content: str):
    """Yield JSX tag boundaries while ignoring `>` inside quoted values and `{expressions}`."""
    i, size = 0, len(content)
    while i < size:
        start = content.find("<", i)
        if start < 0:
            return
        pos = start + 1
        while pos < size and content[pos].isspace():
            pos += 1
        closing = pos < size and content[pos] == "/"
        if closing:
            pos += 1
            while pos < size and content[pos].isspace():
                pos += 1
        name_start = pos
        while pos < size and (content[pos].isalnum() or content[pos] in "_:.-"):
            pos += 1
        name = content[name_start:pos]
        if not name or not (name[0].isalpha()) or (pos < size and not content[pos].isspace()
                                                    and content[pos] not in "/>" ):
            i = start + 1
            continue
        quote, braces, escaped = "", 0, False
        end = pos
        while end < size:
            ch = content[end]
            if quote:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    quote = ""
            elif ch in "\"'`":
                quote = ch
            elif ch == "{":
                braces += 1
            elif ch == "}" and braces:
                braces -= 1
            elif ch == ">" and braces == 0:
                before = end - 1
                while before > pos and content[before].isspace():
                    before -= 1
                yield start, closing, name, content[before] == "/"
                i = end + 1
                break
            end += 1
        else:
            return


def _fix_unclosed_jsx_ancestors(content: str) -> tuple[str, int]:
    """Insert only missing tags proven by a later ancestor close.

    We deliberately do not append tags at EOF and do not guess when a close is absent from the
    stack. Those ambiguous cases stay compiler errors and go through normal regeneration/repair.
    """
    stack: list[str] = []
    inserts: list[tuple[int, str]] = []
    for start, closing, name, self_closing in _iter_jsx_tags(content):
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
                continue
            if name not in stack:
                continue
            missing: list[str] = []
            while stack and stack[-1] != name:
                missing.append(stack.pop())
            if stack and stack[-1] == name:
                stack.pop()
            if missing:
                indent_start = content.rfind("\n", 0, start) + 1
                indent = content[indent_start:start]
                if not indent.isspace():
                    indent = ""
                replacement = "".join(f"</{tag}>" for tag in missing)
                if indent:
                    replacement = "".join(f"</{tag}>\n{indent}" for tag in missing)
                inserts.append((start, replacement))
        elif not self_closing and name not in _VOID_TAGS:
            stack.append(name)
    for position, value in reversed(inserts):
        content = content[:position] + value + content[position:]
    return content, len(inserts)


def _fix_unclosed_jsx_before_return_end(content: str) -> tuple[str, int]:
    """Close tags still open immediately before a complete component ``return (...);``."""
    returns = list(re.finditer(r"\breturn\s*\(", content))
    if not returns:
        return content, 0
    start = returns[-1].end()
    ending = re.search(r"\n(?P<indent>[ \t]*)\);(?P<tail>\s*(?:\n|\Z))", content[start:])
    if not ending:
        return content, 0
    end = start + ending.start()
    region = content[start:end]
    stack: list[str] = []
    for _position, closing, name, self_closing in _iter_jsx_tags(region):
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
            elif name in stack:
                while stack and stack[-1] != name:
                    stack.pop()
                if stack:
                    stack.pop()
        elif not self_closing and name not in _VOID_TAGS:
            stack.append(name)
    if not stack:
        return content, 0
    indent = ending.group("indent")
    closings = "".join(f"{indent}</{name}>\n" for name in reversed(stack))
    return content[:end] + "\n" + closings + content[end + 1:], len(stack)


def _fix_surplus_final_braces(content: str) -> tuple[str, int]:
    """Remove an unmistakable extra final `}` while leaving ambiguous brace errors to TypeScript."""
    surplus = content.count("}") - content.count("{")
    fixed = 0
    while surplus > 0:
        match = re.search(r"(?:\r?\n)?[ \t]*\}[ \t]*(?:\r?\n)?\Z", content)
        if not match:
            break
        content = content[:match.start()] + ("\n" if content.endswith(("\n", "\r")) else "")
        surplus -= 1
        fixed += 1
    return content, fixed


def _fix_callback_result_shadow(content: str) -> tuple[str, int]:
    """Rename an impossible ``const fn = fn(...)`` result without touching the callback call."""
    fixed = 0
    pattern = re.compile(
        r"\bconst\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?P=name)\s*\([^\r\n;]*\)"
    )
    while True:
        match = pattern.search(content)
        if not match:
            break
        name = match.group("name")
        result_name = name + "Result"
        declaration = match.group(0)
        left_start = match.start("name") - match.start()
        left_end = match.end("name") - match.start()
        declaration = declaration[:left_start] + result_name + declaration[left_end:]
        line_end = content.find("\n", match.end())
        if line_end < 0:
            line_end = len(content)
        prefix = content[:match.start()] + declaration + content[match.end():line_end]
        suffix = content[line_end:]
        suffix = re.sub(r"\b" + re.escape(name) + r"\b(?!\s*\()", result_name, suffix)
        content = prefix + suffix
        fixed += 1
    return content, fixed


def _fix_missing_final_component_brace(content: str) -> tuple[str, int]:
    """Close one complete default function whose sole final brace was omitted.

    This deliberately applies only when the file has reached a complete ``return (...);``.  A
    genuinely cut-off completion normally ends inside JSX and remains a compiler failure instead
    of being disguised by an invented closing brace.
    """
    if not re.search(r"\)\s*;\s*\Z", content):
        return content, 0
    function = re.search(
        r"export\s+default\s+(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\([^)]*\)\s*\{",
        content,
        re.DOTALL,
    )
    if not function:
        return content, 0
    opening = function.end() - 1
    if _matching_function_brace(content, opening) is not None:
        return content, 0
    return content.rstrip() + "\n}\n", 1


def _fix_missing_complete_return_tail(content: str) -> tuple[str, int]:
    """Finish ``); }`` when a default function stops after one balanced root JSX close."""
    stripped = content.rstrip()
    if not re.search(r"</[A-Za-z][\w.-]*>\Z", stripped) or re.search(r"\)\s*;\s*\Z", stripped):
        return content, 0
    function = re.search(
        r"export\s+default\s+(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\([^)]*\)\s*\{",
        content,
        re.DOTALL,
    )
    returns = list(re.finditer(r"\breturn\s*\(", content))
    if not function or not returns or _matching_function_brace(content, function.end() - 1) is not None:
        return content, 0
    region = content[returns[-1].end():]
    stack: list[str] = []
    tag_count = 0
    for _position, closing, name, self_closing in _iter_jsx_tags(region):
        tag_count += 1
        if closing:
            if not stack or stack[-1] != name:
                return content, 0
            stack.pop()
        elif not self_closing and name not in _VOID_TAGS:
            stack.append(name)
    if stack or not tag_count:
        return content, 0
    return stripped + "\n  );\n}\n", 1


def _matching_function_brace(content: str, opening: int) -> int | None:
    """Return the matching function brace while ignoring strings and comments."""
    depth, quote, escaped, line_comment, block_comment = 0, "", False, False, False
    index = opening
    while index < len(content):
        char = content[index]
        nxt = content[index + 1] if index + 1 < len(content) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "/" and nxt == "/":
            line_comment = True
            index += 1
        elif char == "/" and nxt == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _prefer_final_reimplementation(content: str) -> tuple[str, int]:
    """Keep the explicitly labelled final implementation when Gemma appends a second version."""
    first = re.search(r"export\s+default\s+function\s+([A-Za-z_$][\w$]*)\s*\(", content)
    terminal = re.search(r"export\s+default\s+([A-Za-z_$][\w$]*)\s*;?\s*$", content)
    if not first or not terminal or terminal.start() <= first.end():
        return content, 0
    final_name = terminal.group(1)
    final_function = re.search(rf"function\s+{re.escape(final_name)}\s*\(", content[first.end():])
    if not final_function:
        return content, 0
    final_start = first.end() + final_function.start()
    bridge = content[first.end():final_start]
    if not re.search(r"re-implement|final\s+(?:implementation|export|version)", bridge, re.I):
        return content, 0
    body_match = re.search(r"\)\s*(?::[^\r\n{]+)?\s*\{", content[first.end():final_start])
    opening = (first.end() + body_match.end() - 1) if body_match else -1
    if opening < 0 or opening >= final_start:
        return content, 0
    closing = _matching_function_brace(content, opening)
    if closing is None or closing >= final_start:
        return content, 0
    content = content[:first.start()] + content[closing + 1:]
    return content, 1

def scrub_jsx(rel: str, content: str, project_dir=None) -> tuple[str, int]:
    """Fix the mechanical TSX mistakes the model repeats and neither repair model can undo.

    Returns (content, n_fixed). Prevention beats repair: each of these that reaches `next build` costs
    minutes of LLM repair that historically failed anyway. `project_dir` grounds the icon check in the
    package actually installed."""
    if not rel.endswith((".tsx", ".jsx")):
        return content, 0
    original = content
    content, n = _JSX_ESCAPED_QUOTE.subn(r"\1\2\3", content)
    content, template_fixes = _MISMATCHED_TEMPLATE_CLASS.subn(
        lambda match: "className={`" + match.group("body") + "`}" + match.group("close"),
        content,
    )
    content, quoted_class_fixes = _MISMATCHED_QUOTED_CLASS.subn(
        lambda match: 'className="' + match.group("body") + '"' + match.group("close"),
        content,
    )
    mojibake = {
        "Â©": "©", "Â°": "°", "â€“": "–", "â€”": "—", "â€™": "’",
        "â€œ": "“", "â€": "”", "â€¢": "•", "â€¦": "…",
    }
    m = 0
    for broken, correct in mojibake.items():
        count = content.count(broken)
        if count:
            content = content.replace(broken, correct)
            m += count
    content, r = _prefer_final_reimplementation(content)
    content, fragment_fixes = _BAD_FRAGMENT_CLOSE.subn("</>", content)
    content, extra_chevron_fixes = _EXTRA_CLOSING_TAG_CHEVRON.subn(r"</\1>", content)
    content, true_fragment_fixes = _UNCLOSED_TRUE_TERNARY_FRAGMENT.subn(
        _close_ternary_fragment, content)
    content, false_fragment_fixes = _UNCLOSED_FALSE_TERNARY_FRAGMENT.subn(
        _close_ternary_fragment, content)
    content, c = _fix_bad_closes(content)
    content, data_image_fixes = _fix_malformed_data_image_class(content)
    content, split_self_close_fixes = _fix_split_self_closing_tag(content)
    content, text_link_fixes = _fix_unclosed_text_only_links(content)
    content, u = _fix_unclosed_jsx_ancestors(content)
    content, surplus_tag_fixes = _fix_surplus_jsx_closing_tags(content)
    content, return_close_fixes = _fix_unclosed_jsx_before_return_end(content)
    content, shadow_fixes = _fix_callback_result_shadow(content)
    content, return_tail_fixes = _fix_missing_complete_return_tail(content)
    content, f = _fix_missing_final_component_brace(content)
    content, b = _fix_surplus_final_braces(content)
    content, a = _ALIAS_IMPORT.subn(r"\1@/\2\3", content)
    content, d = _DEFAULT_IMPORT.subn(r"import \1 from \2next/\3\2", content)
    a += d
    fixed_total = (n + template_fixes + quoted_class_fixes + m + r + fragment_fixes
            + extra_chevron_fixes
            + true_fragment_fixes + false_fragment_fixes + c
            + data_image_fixes + u
            + split_self_close_fixes + text_link_fixes + surplus_tag_fixes + return_close_fixes
            + shadow_fixes + return_tail_fixes + f + b + a)
    return content, fixed_total if content != original else 0


def fix_missing_ui_imports(content: str, diagnostics: list[dict]) -> tuple[str, int]:
    """Add a compiler-proven missing named import from an already imported UI module.

    `AlertTitle` used beside `Alert`/`AlertDescription` is not a product decision. When the exact
    audited registry says one and only one already imported module exports the missing identifier,
    adding it to that import is safer and faster than asking the model to rewrite the file.
    """
    from agents.component_registry import component_export_map
    export_map = component_export_map()
    fixed = 0
    missing = []
    for diagnostic in diagnostics:
        match = re.search(r"Cannot find name ['\"]([A-Za-z_$][\w$]*)['\"]", str(
            diagnostic.get("message") or ""))
        if match and match.group(1) not in missing:
            missing.append(match.group(1))
    for symbol in missing:
        modules = [module for module, exports in export_map.items()
                   if symbol in (exports.get("values") or [])]
        if len(modules) != 1:
            continue
        module = modules[0]
        pattern = re.compile(
            r"import\s*\{(?P<names>[^}]*)\}\s*from\s*(['\"])" + re.escape(module) + r"\2"
        )
        match = pattern.search(content)
        if not match:
            continue
        names = [name.strip() for name in match.group("names").split(",") if name.strip()]
        if symbol in names:
            continue
        names.append(symbol)
        replacement = "import { " + ", ".join(sorted(names)) + " } from '" + module + "'"
        content = content[:match.start()] + replacement + content[match.end():]
        fixed += 1
    return content, fixed


def fix_missing_entity_type_import(content: str, diagnostics: list[dict],
                                   contract: dict | None) -> tuple[str, int]:
    """Import a canonical DTO when TypeScript proves its type name is unresolved."""
    entities = {str(item.get("name") or "") for item in ((contract or {}).get("collections") or [])}
    missing = []
    for diagnostic in diagnostics:
        match = re.search(r"Cannot find name ['\"]([A-Za-z_$][\w$]*)['\"]",
                          str(diagnostic.get("message") or ""))
        if match and match.group(1) in entities:
            missing.append(match.group(1))
    fixed = 0
    for entity in dict.fromkeys(missing):
        if re.search(rf"import(?:\s+type)?\s*\{{[^}}]*\b{re.escape(entity)}\b", content):
            continue
        type_position = re.search(
            rf"(?::\s*{re.escape(entity)}(?:\[\])?\b|\bas\s+{re.escape(entity)}\b|"
            rf"<\s*{re.escape(entity)}(?:\[\])?\s*>)",
            content,
        )
        if not type_position:
            continue
        directive = re.match(r"\s*['\"]use client['\"]\s*;?\s*", content)
        position = directive.end() if directive else 0
        content = content[:position] + f"\nimport type {{ {entity} }} from '@/types'\n" + content[position:]
        fixed += 1
    return content, fixed


def fix_invalid_lucide_imports(content: str, diagnostics: list[dict]) -> tuple[str, int]:
    """Apply TypeScript's exact Lucide export suggestion inside a Lucide import only."""
    suggestions: list[tuple[str, str]] = []
    diagnostic_pattern = re.compile(
        r"['\"]lucide-react['\"] has no exported member named ['\"]"
        r"([A-Za-z_$][\w$]*)['\"]\. Did you mean ['\"]([A-Za-z_$][\w$]*)['\"]\?"
    )
    for diagnostic in diagnostics:
        match = diagnostic_pattern.search(str(diagnostic.get("message") or ""))
        if match and match.groups() not in suggestions:
            suggestions.append(match.groups())

    import_pattern = re.compile(
        r"import\s*\{(?P<names>[^}]*)\}\s*from\s*(['\"])lucide-react\2"
    )
    fixed = 0
    for wrong, right in suggestions:
        match = import_pattern.search(content)
        if not match or not re.search(r"\b" + re.escape(wrong) + r"\b", match.group("names")):
            continue
        names, count = re.subn(r"\b" + re.escape(wrong) + r"\b", right,
                               match.group("names"), count=1)
        if not count:
            continue
        relative_start = match.start("names") - match.start()
        relative_end = match.end("names") - match.start()
        whole = match.group(0)
        replacement = whole[:relative_start] + names + whole[relative_end:]
        content = content[:match.start()] + replacement + content[match.end():]
        fixed += 1
    return content, fixed


def fix_compiler_suggested_identifier(content: str, diagnostics: list[dict]) -> tuple[str, int]:
    """Accept an exact TypeScript local-name suggestion on the diagnosed source line only."""
    lines = content.splitlines(keepends=True)
    fixed = 0
    pattern = re.compile(
        r"Cannot find name ['\"]([A-Za-z_$][\w$]*)['\"]\. "
        r"Did you mean ['\"]([A-Za-z_$][\w$]*)['\"]\?"
    )
    for diagnostic in diagnostics:
        match = pattern.search(str(diagnostic.get("message") or ""))
        line_number = diagnostic.get("line")
        if not match or not isinstance(line_number, int) or not (1 <= line_number <= len(lines)):
            continue
        wrong, right = match.groups()
        line = lines[line_number - 1]
        if len(re.findall(r"\b" + re.escape(wrong) + r"\b", line)) != 1:
            continue
        lines[line_number - 1] = re.sub(r"\b" + re.escape(wrong) + r"\b", right, line, count=1)
        fixed += 1
    return "".join(lines), fixed


def fix_missing_canonical_prop_field(content: str, diagnostics: list[dict],
                                     contract: dict | None) -> tuple[str, int]:
    """Add a compiler-proven nested prop field only when the canonical entity declares it.

    Architect component contracts sometimes list a compact inline ``story: { ... }`` prop and a
    candidate then uses another real Story field.  TypeScript identifies both the missing field and
    its exact use; the canonical product contract supplies its type.  This is a type-contract repair,
    not a product or UI decision.
    """
    collections = (contract or {}).get("collections") or []
    entities = {str(item.get("name") or "").lower(): item for item in collections}
    lines = content.splitlines()
    requests: list[tuple[str, str, str]] = []
    diagnostic_pattern = re.compile(
        r"Property ['\"]([A-Za-z_$][\w$]*)['\"] does not exist on type ['\"]?\{"
    )
    ts_types = {
        "String": "string", "Number": "number", "Boolean": "boolean", "Date": "string",
        "ObjectId": "string", "[String]": "string[]",
    }
    for diagnostic in diagnostics:
        match = diagnostic_pattern.search(str(diagnostic.get("message") or ""))
        line_number = diagnostic.get("line")
        if not match or not isinstance(line_number, int) or not (1 <= line_number <= len(lines)):
            continue
        field_name = match.group(1)
        uses = re.findall(r"\b([A-Za-z_$][\w$]*)\." + re.escape(field_name) + r"\b",
                          lines[line_number - 1])
        if len(set(uses)) != 1:
            continue
        variable = uses[0]
        entity = entities.get(variable.lower())
        if not entity:
            continue
        field = next((item for item in (entity.get("fields") or [])
                      if item.get("name") == field_name), None)
        if not field or field.get("type") not in ts_types:
            continue
        requests.append((variable, field_name, ts_types[field["type"]]))

    fixed = 0
    for variable, field_name, field_type in dict.fromkeys(requests):
        prop_pattern = re.compile(
            r"(?P<prefix>\b" + re.escape(variable) + r"\s*:\s*\{)(?P<body>.*?)(?P<suffix>\}\s*;)",
            re.DOTALL,
        )
        match = prop_pattern.search(content)
        if not match or re.search(r"\b" + re.escape(field_name) + r"\s*:", match.group("body")):
            continue
        body = match.group("body")
        indent_match = re.search(r"\n(?P<indent>[ \t]+)[A-Za-z_$][\w$]*\s*:", body)
        if indent_match:
            trailing = body[len(body.rstrip()):]
            body = body.rstrip() + f"\n{indent_match.group('indent')}{field_name}: {field_type};" + trailing
        else:
            body = body.rstrip() + f" {field_name}: {field_type}; "
        content = content[:match.start("body")] + body + content[match.end("body"):]
        fixed += 1
    return content, fixed


def fix_uncalled_boolean_prop(content: str, diagnostics: list[dict],
                              contract: dict | None) -> tuple[str, int]:
    """Call a boolean callback when TS2774, its prop signature, and entity key agree.

    For example, ``isBookmarked: (slug: string) => boolean`` used as
    ``isBookmarked ? ...`` is always true.  If the same props declare ``story: Story`` and the
    canonical Story owns ``slug``, the only contract-correct call is
    ``isBookmarked(story.slug)``.  Only the exact compiler-diagnosed lines are changed.
    """
    callback_pattern = re.compile(
        r"\b(?P<name>[A-Za-z_$][\w$]*)\s*:\s*\(\s*"
        r"(?:(?P<param>[A-Za-z_$][\w$]*)\s*:\s*[^)]*)?\)\s*=>\s*boolean\s*;"
    )
    callbacks = {match.group("name"): match.group("param")
                 for match in callback_pattern.finditer(content)}
    if not callbacks:
        return content, 0

    entities = {str(item.get("name") or ""): item
                for item in ((contract or {}).get("collections") or [])}
    resources: list[tuple[str, str, set[str]]] = []
    for variable, entity_name in re.findall(
            r"\b([A-Za-z_$][\w$]*)\s*:\s*([A-Z][A-Za-z0-9_$]*)\s*;", content):
        entity = entities.get(entity_name)
        if entity:
            resources.append((variable, entity_name, {
                str(field.get("name") or "") for field in (entity.get("fields") or [])
            }))

    lines = content.splitlines(keepends=True)
    fixed = 0
    for diagnostic in diagnostics:
        if str(diagnostic.get("code") or "") != "2774" or "Did you mean to call it instead?" not in str(
                diagnostic.get("message") or ""):
            continue
        line_number = diagnostic.get("line")
        if not isinstance(line_number, int) or not (1 <= line_number <= len(lines)):
            continue
        line = lines[line_number - 1]
        candidates = [name for name in callbacks
                      if len(re.findall(r"\b" + re.escape(name) + r"\b(?!\s*\()", line)) == 1]
        if len(candidates) != 1:
            continue
        name = candidates[0]
        param = callbacks[name]
        if param is None:
            call = f"{name}()"
        else:
            matches = [(variable, field_names) for variable, _entity, field_names in resources
                       if param in field_names]
            if len(matches) != 1:
                continue
            call = f"{name}({matches[0][0]}.{param})"
        lines[line_number - 1] = re.sub(
            r"\b" + re.escape(name) + r"\b(?!\s*\()", call, line, count=1)
        fixed += 1
    return "".join(lines), fixed


def fix_redundant_unsafe_html_prop(content: str, diagnostics: list[dict]) -> tuple[str, int]:
    """Render a simple text expression safely when Gemma invents an HTML-injection prop.

    The observed failure emits both ``dangerously_html_from={content}`` and React's real
    ``dangerouslySetInnerHTML`` on one self-closing element.  TypeScript proves the invented prop is
    invalid.  For a simple identifier/member expression, rendering it as a child preserves the text,
    fixes the diagnostic, and avoids turning stored user content into executable markup.
    """
    invalid = set()
    pattern = re.compile(
        r"Property ['\"](dangerously_[A-Za-z0-9_$]+)['\"] does not exist on type"
    )
    for diagnostic in diagnostics:
        match = pattern.search(str(diagnostic.get("message") or ""))
        if match:
            invalid.add(match.group(1))
    fixed = 0
    for prop in invalid:
        tag_pattern = re.compile(
            r"<(?P<tag>[a-z][A-Za-z0-9-]*)(?P<attrs>[^<>]*?)\s+" + re.escape(prop)
            + r"=\{(?P<source>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\}[^\r\n]*"
              r"(?P<space>\s*)dangerouslySetInnerHTML=\{\{\s*__html:\s*"
              r"(?P<html>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\}\}\s*/>",
            re.DOTALL,
        )

        def replacement(match: re.Match) -> str:
            nonlocal fixed
            if match.group("source") != match.group("html"):
                return match.group(0)
            fixed += 1
            attrs = match.group("attrs").rstrip()
            return f"<{match.group('tag')}{attrs}>{{{match.group('html')}}}</{match.group('tag')}>"

        content = tag_pattern.sub(replacement, content)
    return content, fixed


def fix_duplicate_jsx_classname(content: str, diagnostics: list[dict]) -> tuple[str, int]:
    """Merge two className attributes on the exact TS17001-diagnosed JSX tag."""
    lines = content.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    fixed = 0
    attr_pattern = re.compile(
        r"\bclassName\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|"
        r"\{(?P<expr>[^{}\r\n]+)\})"
    )
    for diagnostic in sorted(diagnostics, key=lambda item: int(item.get("line") or 0), reverse=True):
        if str(diagnostic.get("code") or "") != "17001":
            continue
        line_number = diagnostic.get("line")
        if not isinstance(line_number, int) or not (1 <= line_number < len(offsets)):
            continue
        position = offsets[line_number - 1] + len(lines[line_number - 1])
        tag_start = content.rfind("<", 0, position + 1)
        tag_end = content.find("/>", position)
        if tag_start < 0 or tag_end < 0:
            continue
        segment = content[tag_start:tag_end + 2]
        matches = list(attr_pattern.finditer(segment))
        if len(matches) != 2:
            continue

        def value(match: re.Match) -> tuple[str, bool]:
            static = match.group("double") if match.group("double") is not None else match.group("single")
            return (static, True) if static is not None else (match.group("expr").strip(), False)

        first_value, first_static = value(matches[0])
        second_value, second_static = value(matches[1])
        if first_static and second_static:
            merged = f'className="{first_value} {second_value}"'
        else:
            first_part = first_value if first_static else "${" + first_value + "}"
            second_part = second_value if second_static else "${" + second_value + "}"
            merged = "className={`" + first_part + " " + second_part + "`}"
        segment = (segment[:matches[0].start()] + merged
                   + segment[matches[0].end():matches[1].start()] + segment[matches[1].end():])
        content = content[:tag_start] + segment + content[tag_end + 2:]
        fixed += 1
    return content, fixed


def fix_interactive_badge_as_button(content: str, diagnostics: list[dict]) -> tuple[str, int]:
    """Use the audited Button primitive when a Badge is given button-only props."""
    if not re.search(r"import\s*\{[^}]*\bButton\b[^}]*\}\s*from\s*['\"]@/components/ui/button", content):
        return content, 0
    lines = content.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)
    fixed = 0
    for diagnostic in sorted(diagnostics, key=lambda item: int(item.get("line") or 0), reverse=True):
        message = str(diagnostic.get("message") or "")
        line_number = diagnostic.get("line")
        if (str(diagnostic.get("code") or "") != "2322" or "BadgeProps" not in message or
                "Property 'type' does not exist" not in message or not isinstance(line_number, int) or
                not (1 <= line_number <= len(offsets))):
            continue
        position = offsets[line_number - 1] + len(lines[line_number - 1])
        opening = content.rfind("<Badge", 0, position + 1)
        closing = content.find("</Badge>", opening)
        if opening < 0 or closing < 0:
            continue
        content = (content[:opening] + "<Button" + content[opening + len("<Badge"):closing]
                   + "</Button>" + content[closing + len("</Badge>"):])
        fixed += 1
    return content, fixed


def fix_forbidden_external_decorative_image(content: str,
                                             diagnostics: list[dict]) -> tuple[str, int]:
    """Remove an empty external texture layer when the contract explicitly forbids it.

    This is deliberately limited to a self-closing absolute overlay: it owns no product content,
    controls, or children, while its sole purpose is the forbidden network image. Meaningful image
    elements remain diagnostics and require an intentional model edit.
    """
    if not any(str(item.get("code") or "") == "forbidden-external-image"
               for item in diagnostics):
        return content, 0
    overlay = re.compile(
        r"[ \t]*<(?P<tag>div|span)\b(?P<attrs>[^>]*\babsolute\b[^>]*"
        r"https?://[^>]*)/?>[ \t]*(?:\r?\n)?", re.I
    )
    fixed = 0

    def remove(match: re.Match) -> str:
        nonlocal fixed
        whole = match.group(0)
        if "/>" not in whole:
            return whole
        fixed += 1
        return ""

    return overlay.sub(remove, content), fixed


def fix_date_literal_for_serialized_dto(content: str,
                                        diagnostics: list[dict]) -> tuple[str, int]:
    """Serialize a Date literal when TypeScript proves the DTO field is a string.

    The canonical DTO generator represents Mongoose ``Date`` fields as ISO strings.  On an exact
    TS2322 line, ``new Date(...)`` therefore has one contract-preserving spelling.  Restricting the
    edit to a single constructor on the diagnosed line avoids changing Date values used for real
    date arithmetic elsewhere in the component.
    """
    lines = content.splitlines(keepends=True)
    fixed = 0
    date_literal = re.compile(
        r"new\s+Date\((?:[^()\r\n'\"`]|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|"
        r"`(?:\\.|[^`\\])*`)*\)(?!\.toISOString\(\))"
    )
    for diagnostic in diagnostics:
        message = str(diagnostic.get("message") or "")
        line_number = diagnostic.get("line")
        if (str(diagnostic.get("code") or "") != "2322" or
                "Type 'Date' is not assignable to type 'string'" not in message or
                not isinstance(line_number, int) or not (1 <= line_number <= len(lines))):
            continue
        line = lines[line_number - 1]
        matches = list(date_literal.finditer(line))
        if len(matches) != 1:
            continue
        lines[line_number - 1] = date_literal.sub(
            lambda match: match.group(0) + ".toISOString()", line, count=1)
        fixed += 1
    return "".join(lines), fixed


def fix_transition_misused_as_boolean_state(content: str,
                                             diagnostics: list[dict]) -> tuple[str, int]:
    """Replace a compiler-proven ``useTransition`` boolean setter with ``useState``.

    React's second transition tuple member accepts a callback, never ``true``/``false``. When the
    candidate calls that exact member with booleans on TS2345 lines, its pending flag is ordinary
    async loading state. Converting the hook preserves the implemented submit flow and button state.
    """
    invalid_lines = {
        item.get("line") for item in diagnostics
        if str(item.get("code") or "") == "2345" and
        "Argument of type 'boolean' is not assignable to parameter of type 'TransitionFunction'"
        in str(item.get("message") or "") and isinstance(item.get("line"), int)
    }
    if not invalid_lines:
        return content, 0
    source_lines = content.splitlines()
    declarations = list(re.finditer(
        r"const\s*\[\s*(?P<pending>[A-Za-z_$][\w$]*)\s*,\s*"
        r"(?P<setter>[A-Za-z_$][\w$]*)\s*\]\s*=\s*useTransition\(\s*\)\s*;?", content
    ))
    chosen = None
    for declaration in declarations:
        setter = declaration.group("setter")
        matching = [line for line in invalid_lines if 1 <= line <= len(source_lines) and
                    re.search(r"\b" + re.escape(setter) + r"\s*\(\s*(?:true|false)\s*\)",
                              source_lines[line - 1])]
        if matching:
            chosen = declaration
            break
    if not chosen:
        return content, 0
    replacement = chosen.group(0).replace("useTransition()", "useState(false)")
    content = content[:chosen.start()] + replacement + content[chosen.end():]

    react_import = re.compile(
        r"import(?P<prefix>\s+(?:React\s*,\s*)?)\{(?P<names>[^}]*)\}"
        r"\s*from\s*(['\"])react\3"
    )
    match = react_import.search(content)
    if not match:
        return content, 0
    names = [name.strip() for name in match.group("names").split(",") if name.strip()]
    names = [name for name in names if name != "useTransition"]
    if "useState" not in names:
        names.append("useState")
    replacement_import = ("import" + match.group("prefix") + "{ " + ", ".join(names)
                          + " } from 'react'")
    content = content[:match.start()] + replacement_import + content[match.end():]
    return content, 1


def _matching_square_bracket(content: str, opening: int) -> int | None:
    """Return a matching ``]`` while ignoring brackets in strings and comments."""
    depth, quote, escaped, line_comment, block_comment = 0, "", False, False, False
    index = opening
    while index < len(content):
        char = content[index]
        nxt = content[index + 1] if index + 1 < len(content) else ""
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "/" and nxt == "/":
            line_comment = True
            index += 1
        elif char == "/" and nxt == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def fix_missing_dto_metadata(content: str, diagnostics: list[dict],
                             contract: dict | None) -> tuple[str, int]:
    """Complete compiler-proven curated DTO array records with canonical metadata."""
    entities = {str(item.get("name") or ""): item
                for item in ((contract or {}).get("collections") or [])}
    requested: dict[str, set[str]] = {}
    metadata = {"_id", "createdAt", "updatedAt"}
    for diagnostic in diagnostics:
        message = str(diagnostic.get("message") or "")
        if str(diagnostic.get("code") or "") not in {"2322", "2739"}:
            continue
        for entity in entities:
            if re.search(r"from type ['\"]" + re.escape(entity) + r"['\"]", message):
                missing = {field for field in metadata if re.search(r"\b" + re.escape(field) + r"\b", message)}
                if missing:
                    requested.setdefault(entity, set()).update(missing)

    fixed = 0
    for entity, missing in requested.items():
        declaration = re.compile(
            r"\b[A-Za-z_$][\w$]*\s*:\s*" + re.escape(entity) + r"\s*\[\s*\]\s*="
        )
        regions: list[tuple[int, int]] = []
        for match in declaration.finditer(content):
            opening = content.find("[", match.end())
            closing = _matching_square_bracket(content, opening) if opening >= 0 else None
            if closing is not None:
                regions.append((opening + 1, closing))
        entity_fields = {str(field.get("name") or "")
                         for field in (entities[entity].get("fields") or [])}
        for start, end in reversed(regions):
            region = content[start:end]
            objects = list(re.finditer(r"\{(?P<body>[^{}]*)\}", region, re.DOTALL))
            for index, obj in reversed(list(enumerate(objects, 1))):
                body = obj.group("body")
                present_entity_fields = {
                    field for field in entity_fields
                    if re.search(r"(?m)^\s*" + re.escape(field) + r"\s*:", body)
                }
                if len(present_entity_fields) < 2:
                    continue
                additions = []
                if "_id" in missing and not re.search(r"(?m)^\s*_id\s*:", body):
                    slug = re.search(r"(?m)^\s*slug\s*:\s*(['\"])([^'\"]+)\1", body)
                    stable_id = slug.group(2) if slug else f"locode-{entity.lower()}-{index}"
                    additions.append(f"_id: '{stable_id}',")
                for field in ("createdAt", "updatedAt"):
                    if field in missing and not re.search(r"(?m)^\s*" + field + r"\s*:", body):
                        additions.append(f"{field}: '2025-01-01T00:00:00.000Z',")
                if not additions:
                    continue
                indent_match = re.search(r"\n(?P<indent>[ \t]+)[A-Za-z_$][\w$]*\s*:", body)
                indent = indent_match.group("indent") if indent_match else "  "
                trailing = body[len(body.rstrip()):]
                replacement_body = (body.rstrip() + "\n" +
                                    "\n".join(indent + line for line in additions) + trailing)
                obj_start = start + obj.start("body")
                obj_end = start + obj.end("body")
                content = content[:obj_start] + replacement_body + content[obj_end:]
                fixed += len(additions)
    return content, fixed


def fix_navigator_share_feature_test(content: str,
                                     diagnostics: list[dict]) -> tuple[str, int]:
    """Use an explicit function feature test when TS2774 proves ``navigator.share`` is callable."""
    lines = content.splitlines(keepends=True)
    fixed = 0
    for diagnostic in diagnostics:
        line_number = diagnostic.get("line")
        if (str(diagnostic.get("code") or "") != "2774" or
                "Did you mean to call it instead?" not in str(diagnostic.get("message") or "") or
                not isinstance(line_number, int) or not (1 <= line_number <= len(lines))):
            continue
        line = lines[line_number - 1]
        pattern = re.compile(r"(?<!typeof\s)(?:window\.)?navigator\.share(?!\s*\()")
        if len(pattern.findall(line)) != 1:
            continue
        lines[line_number - 1] = pattern.sub("typeof window.navigator.share === 'function'", line, count=1)
        fixed += 1
    return "".join(lines), fixed


def fix_unsupported_button_link_variant(content: str,
                                        diagnostics: list[dict]) -> tuple[str, int]:
    """Map an unsupported shadcn ``link`` Button variant to the declared ``ghost`` variant."""
    lines = content.splitlines(keepends=True)
    fixed = 0
    for diagnostic in diagnostics:
        message = str(diagnostic.get("message") or "")
        line_number = diagnostic.get("line")
        if (str(diagnostic.get("code") or "") != "2322" or
                "Type '\"link\"' is not assignable" not in message or
                "\"ghost\"" not in message or not isinstance(line_number, int) or
                not (1 <= line_number <= len(lines))):
            continue
        line = lines[line_number - 1]
        if len(re.findall(r'\bvariant\s*=\s*["\']link["\']', line)) != 1:
            continue
        lines[line_number - 1], count = re.subn(
            r'(\bvariant\s*=\s*)["\']link["\']', r'\1"ghost"', line, count=1)
        fixed += count
    return "".join(lines), fixed


def fix_missing_gradient_artwork_colors(content: str,
                                        diagnostics: list[dict]) -> tuple[str, int]:
    """Supply semantic palette variables to a compiler-proven bare GradientArtwork instance."""
    lines = content.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    fixed = 0
    for diagnostic in sorted(diagnostics, key=lambda item: int(item.get("line") or 0), reverse=True):
        message = str(diagnostic.get("message") or "")
        line_number = diagnostic.get("line")
        if (str(diagnostic.get("code") or "") != "2741" or
                "Property 'colors' is missing" not in message or
                "GradientArtwork" not in content or not isinstance(line_number, int) or
                not (1 <= line_number < len(offsets))):
            continue
        line_start, line_end = offsets[line_number - 1], offsets[line_number]
        opening = content.find("<GradientArtwork", line_start, line_end)
        if opening < 0:
            continue
        close = content.find("/>", opening)
        if close < 0 or "colors=" in content[opening:close]:
            continue
        prop = " colors={['var(--primary)', 'var(--secondary)', 'var(--accent)']}"
        content = content[:close].rstrip() + prop + " " + content[close:]
        fixed += 1
    return content, fixed


def repair_output_budget(content: str, diagnostics: list[dict]) -> int:
    """Bound a SEARCH/REPLACE response from the actual file and diagnostic scope."""
    approximate_file_tokens = max(1, (len(content.encode("utf-8")) + 2) // 3)
    diagnostic_allowance = min(1_800, len(diagnostics) * 90)
    return max(1_800, min(4_096, 500 + approximate_file_tokens + diagnostic_allowance))


def fix_public_reference_empty_fallback(content: str) -> tuple[str, int]:
    """Do not let a successful empty API erase explicit first-load reference content."""
    if not re.search(r"const\s+INITIAL_[A-Z0-9_]+\s*:", content):
        return content, 0
    pattern = re.compile(
        r"if\s*\(\s*(?P<result>[A-Za-z_$][\w$]*)\.success\s*&&\s*"
        r"(?P=result)\.data\s*\)"
    )
    return pattern.subn(
        lambda match: (f"if ({match.group('result')}.success && "
                       f"Array.isArray({match.group('result')}.data) && "
                       f"{match.group('result')}.data.length > 0)"),
        content,
    )


def fix_unwired_filter_state(content: str) -> tuple[str, int]:
    """Wire a comment-only filter callback to a sibling's constant-null filter prop."""
    if "filter={null}" not in content or "onFilterChange" not in content:
        return content, 0
    callback = re.compile(
        r"onFilterChange=\{\s*\([A-Za-z_$][\w$]*\)\s*=>\s*\{(?P<body>.*?)\}\s*\}",
        re.DOTALL,
    )
    match = callback.search(content)
    if not match:
        return content, 0
    executable = re.sub(r"/\*.*?\*/|//[^\r\n]*", "", match.group("body"), flags=re.DOTALL).strip()
    if executable:
        return content, 0
    content = content[:match.start()] + "onFilterChange={setFilter}" + content[match.end():]
    content, prop_count = re.subn(r"\bfilter=\{null\}", "filter={filter}", content, count=1)
    if not prop_count:
        return content, 0
    function_open = re.search(r"export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{", content)
    if not function_open:
        return content, 0
    declaration = (
        "\n  const [filter, setFilter] = useState<"
        "Parameters<React.ComponentProps<typeof FilterControls>['onFilterChange']>[0]>(null)"
    )
    content = content[:function_open.end()] + declaration + content[function_open.end():]
    return content, 3


def fix_missing_controlled_filter_props(content: str, diagnostics: list[dict],
                                        contract: dict | None) -> tuple[str, int]:
    """Wire an omitted controlled Filter contract and apply it to the declared resource field."""
    contract = contract or {}
    missing_message = next((str(item.get("message") or "") for item in diagnostics
                            if "missing the following properties" in str(item.get("message") or "")
                            and "Filter" in content), "")
    if not missing_message:
        return content, 0
    tail = missing_message.rsplit(":", 1)[-1]
    missing = {name.strip().strip(".") for name in tail.split(",") if name.strip()}
    callback_prop = next((name for name in missing if re.fullmatch(r"on[A-Z]\w*Change", name)), None)
    value_prop = next((name for name in missing if name != callback_prop and
                       ("filter" in name.lower() or name.lower() in {"value", "selected"})), None)
    if not callback_prop or not value_prop:
        return content, 0

    filters = list(re.finditer(r"<(?P<name>[A-Za-z_$][\w$]*Filter[\w$]*)\s*/>", content))
    if len(filters) != 1:
        return content, 0
    component = filters[0].group("name")
    state_name = value_prop
    setter = "set" + state_name[:1].upper() + state_name[1:]
    prop_type = re.search(rf"\b{re.escape(value_prop)}\s*:\s*([^;}}]+)", missing_message)
    type_text = prop_type.group(1).strip() if prop_type else "unknown"
    is_array = "[]" in type_text or "Array<" in type_text
    initializer = "[]" if is_array else "null"
    function_open = re.search(r"export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{", content)
    if not function_open or re.search(rf"\[\s*{re.escape(state_name)}\s*,", content):
        return content, 0
    declaration = (
        f"\n  const [{state_name}, {setter}] = useState<"
        f"React.ComponentProps<typeof {component}>['{value_prop}']>({initializer})"
    )
    replacement = (f"<{component} {value_prop}={{{state_name}}} "
                   f"{callback_prop}={{{setter}}} />")
    content = content[:filters[0].start()] + replacement + content[filters[0].end():]
    content = content[:function_open.end()] + declaration + content[function_open.end():]
    fixed = 2

    subject = re.sub(r"Filter.*$", "", component, flags=re.I).lower()
    fields = [str(field.get("name") or "") for collection in (contract.get("collections") or [])
              for field in (collection.get("fields") or []) if isinstance(field, dict)]
    field = next((name for name in fields if subject and subject in name.lower()), "")
    array_state = re.search(
        r"const\s*\[\s*(?P<name>[A-Za-z_$][\w$]*)\s*,[^]]+\]\s*=\s*useState<[^>]*\[\]>",
        content,
    )
    filtered = re.search(
        r"const\s+(?P<name>filtered[A-Za-z0-9_$]*)\s*=\s*useMemo\(\(\)\s*=>\s*\{.*?"
        r"\},\s*\[[^]]*\]\s*\)",
        content,
        re.DOTALL,
    )
    if field and array_state and filtered:
        data_name = array_state.group("name")
        filtered_name = filtered.group("name")
        if is_array:
            logic = (
                f"const {filtered_name} = useMemo(() => {{\n"
                f"    if ({state_name}.length === 0) return {data_name}\n"
                f"    return {data_name}.filter((item) => {state_name}.includes(String(item.{field})))\n"
                f"  }}, [{data_name}, {state_name}])"
            )
        else:
            logic = (
                f"const {filtered_name} = useMemo(() => {{\n"
                f"    if (!{state_name}) return {data_name}\n"
                f"    return {data_name}.filter((item) => String(item.{field}).toLowerCase() === "
                f"String({state_name}).toLowerCase())\n"
                f"  }}, [{data_name}, {state_name}])"
            )
        content = content[:filtered.start()] + logic + content[filtered.end():]
        fixed += 1
    return content, fixed


def fix_unwired_selection_state(content: str, contract: dict | None) -> tuple[str, int]:
    """Connect a map-card selection callback to its selected-detail sibling."""
    callback = re.search(
        r"onSelect=\{\s*\([^)]*\)\s*=>\s*\{(?P<body>.*?)\}\s*\}", content, re.DOTALL)
    if not callback:
        return content, 0
    executable = re.sub(r"/\*.*?\*/|//[^\r\n]*", "", callback.group("body"),
                        flags=re.DOTALL).strip()
    if executable:
        return content, 0
    nearby = content[max(0, callback.start() - 500):callback.start()]
    item_match = list(re.finditer(r"\b(?P<item>[a-z][\w$]*)=\{(?P=item)\}", nearby))
    detail = re.search(
        r"(?P<prop>selected[A-Z][\w$]*)=\{[^}\r\n]*\[0\]\s*\|\|\s*null\}", content)
    collections = (contract or {}).get("collections") or []
    entity = str(collections[0].get("name") or "") if len(collections) == 1 else ""
    if not item_match or not detail or not entity:
        return content, 0
    item = item_match[-1].group("item")
    state_name = detail.group("prop")
    setter = "set" + state_name[:1].upper() + state_name[1:]
    function_open = re.search(r"export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{", content)
    if not function_open or re.search(rf"\[\s*{re.escape(state_name)}\s*,", content):
        return content, 0

    content = content[:callback.start()] + f"onSelect={{() => {setter}({item})}}" + content[callback.end():]
    content, selected_count = re.subn(
        r"\bisSelected=\{false\}", f"isSelected={{{state_name}?._id === {item}._id}}",
        content, count=1)
    detail = re.search(
        r"(?P<prop>selected[A-Z][\w$]*)=\{[^}\r\n]*\[0\]\s*\|\|\s*null\}", content)
    if not detail:
        return content, 0
    content = content[:detail.start()] + f"{detail.group('prop')}={{{state_name}}}" + content[detail.end():]
    declaration = f"\n  const [{state_name}, {setter}] = useState<{entity} | null>(null)"
    content = content[:function_open.end()] + declaration + content[function_open.end():]
    return content, 3 + selected_count


def fix_single_route_topnav(content: str, contract: dict | None) -> tuple[str, int]:
    """Turn repeated home links in a one-route topnav into real in-page anchors."""
    contract = contract or {}
    if ((contract.get("design") or {}).get("navStyle") != "topnav" or
            set(contract.get("routes") or []) != {"/"}):
        return content, 0
    nav = re.search(r"<nav\b[^>]*>(?P<body>.*?)</nav>", content, re.DOTALL | re.I)
    if not nav:
        return content, 0
    links = list(re.finditer(r"<a\b(?P<before>[^>]*?)href=(?P<q>['\"])(?:/|#)(?P=q)(?P<after>[^>]*)>"
                             r"(?P<label>.*?)</a>", nav.group("body"), re.DOTALL | re.I))
    if len(links) <= 1:
        return content, 0
    labels = [re.sub(r"<[^>]+>", "", match.group("label")).strip() for match in links[1:]]
    anchors = []
    for index, label in enumerate(labels, 1):
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or f"section-{index}"
        anchors.append(slug)

    body = nav.group("body")
    offset = 0
    for match, anchor in zip(links[1:], anchors):
        start = match.start() + offset
        end = match.end() + offset
        original = body[start:end]
        replacement = re.sub(r"href=(['\"])(?:/|#)\1", f'href="#{anchor}"', original, count=1)
        body = body[:start] + replacement + body[end:]
        offset += len(replacement) - len(original)
    content = content[:nav.start("body")] + body + content[nav.end("body"):]

    sections = list(re.finditer(r"<section\b(?P<attrs>[^>]*)>", content, re.I))
    targets = sections[-len(anchors):]
    if len(targets) != len(anchors):
        return content, 0
    offset = 0
    for section, anchor in zip(targets, anchors):
        if re.search(r"\bid\s*=", section.group("attrs")):
            continue
        position = section.end() - 1 + offset
        insertion = f' id="{anchor}"'
        content = content[:position] + insertion + content[position:]
        offset += len(insertion)
    return content, (len(anchors) * 2)


def fix_decorative_overlay_pointer_events(content: str) -> tuple[str, int]:
    """Keep self-closing full-surface decorative layers from intercepting real controls."""
    pattern = re.compile(r"<div\b(?P<attrs>[^>]*\babsolute\s+inset-0[^>]*)/>", re.DOTALL)
    fixed = 0

    def replace(match: re.Match) -> str:
        nonlocal fixed
        whole = match.group(0)
        if "pointer-events-none" in whole:
            return whole
        fixed += 1
        return whole.replace("absolute inset-0", "pointer-events-none absolute inset-0", 1)

    return pattern.sub(replace, content), fixed


_FIXED_COLOR_CLASS = re.compile(
    r"\b(?P<utility>bg|text|border|ring|from|via|to)-"
    r"(?P<family>white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|"
    r"emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)"
    r"(?:-\d{2,3})?(?P<opacity>/\d{1,3})?\b"
)
_HEX_COLOR_CLASS = re.compile(
    r"\b(?P<utility>bg|text|border|ring|from|via|to)-\[#(?P<hex>[0-9a-fA-F]{3,8})\]"
    r"(?P<opacity>/\d{1,3})?"
)
_HEX_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_RGB_LITERAL = re.compile(
    r"rgba?\(\s*(?P<red>\d{1,3})\s*,\s*(?P<green>\d{1,3})\s*,\s*"
    r"(?P<blue>\d{1,3})(?:\s*,\s*(?P<alpha>0(?:\.\d+)?|1(?:\.0+)?))?\s*\)", re.I
)


def fix_nonsemantic_color_classes(content: str, design: dict | None) -> tuple[str, int]:
    """Map literal colours onto the Architect's semantic CSS-token surface.

    The palette already lives in globals.css, so copying the same hex into TSX (including inline CSS
    gradients) is redundant and breaks light/dark theming. Only exact Architect palette matches are
    converted outside Tailwind classes; unknown literals remain diagnostics rather than being guessed.
    """
    palette = (design or {}).get("palette") or {}
    by_hex: dict[str, str] = {}
    for key, value in palette.items():
        if value:
            # primary/text and background/surface may intentionally share a hex. Preserve the first
            # Architect semantic role rather than silently letting the later compatibility role win.
            by_hex.setdefault(str(value).lstrip("#").lower(), key)

    def semantic(utility: str, role: str, opacity: str = "") -> str:
        role = {"surface": "card", "text": "foreground", "textSecondary": "muted-foreground",
                "error": "destructive"}.get(role, role)
        if utility == "bg":
            token = {"foreground": "foreground", "muted-foreground": "muted", "border": "muted",
                     "warning": "warning", "success": "success"}.get(role, role)
        elif utility == "text":
            token = {"background": "foreground", "card": "foreground", "border": "muted-foreground",
                     "warning": "warning", "success": "success"}.get(role, role)
        elif utility == "border":
            token = "border" if role in {"background", "card", "foreground", "muted-foreground", "border"} else role
        elif utility == "ring":
            token = "ring" if role in {"background", "card", "foreground", "muted-foreground", "border"} else role
        elif utility in {"from", "via", "to"}:
            token = role if role in {"primary", "secondary", "accent"} else "primary"
        else:
            token = role
        return f"{utility}-{token}{opacity}"

    def hex_replacement(match: re.Match) -> str:
        raw = match.group("hex").lower()
        if len(raw) in {3, 4}:
            raw = "".join(char * 2 for char in raw)
        role = by_hex.get(raw[:6])
        if not role:
            role = {"bg": "muted", "text": "foreground", "border": "border", "ring": "ring",
                    "from": "primary", "via": "accent", "to": "secondary"}[match.group("utility")]
        return semantic(match.group("utility"), role, match.group("opacity") or "")

    content, hex_count = _HEX_COLOR_CLASS.subn(hex_replacement, content)

    css_role = {"surface": "card", "text": "foreground", "textSecondary": "muted-foreground",
                "error": "destructive"}

    literal_count = 0

    def literal_replacement(match: re.Match) -> str:
        nonlocal literal_count
        raw = match.group(0)[1:].lower()
        if len(raw) in {3, 4}:
            raw = "".join(char * 2 for char in raw)
        role = by_hex.get(raw[:6])
        if not role:
            return match.group(0)
        literal_count += 1
        return f"var(--{css_role.get(role, role)})"

    content = _HEX_LITERAL.sub(literal_replacement, content)

    def rgb_replacement(match: re.Match) -> str:
        nonlocal literal_count
        channels = tuple(int(match.group(name)) for name in ("red", "green", "blue"))
        if any(channel > 255 for channel in channels):
            return match.group(0)
        raw = "".join(f"{channel:02x}" for channel in channels)
        role = by_hex.get(raw)
        if not role:
            return match.group(0)
        role = css_role.get(role, role)
        alpha = match.group("alpha")
        literal_count += 1
        if alpha is None or float(alpha) >= 1:
            return f"var(--{role})"
        percent = f"{float(alpha) * 100:g}%"
        return f"color-mix(in srgb, var(--{role}) {percent}, transparent)"

    content = _RGB_LITERAL.sub(rgb_replacement, content)

    def fixed_replacement(match: re.Match) -> str:
        utility, family = match.group("utility"), match.group("family")
        opacity = match.group("opacity") or ""
        if family == "white":
            if utility == "text":
                return "text-primary-foreground" + opacity
            return semantic(utility, "card", opacity)
        if family == "black":
            return semantic(utility, "foreground", opacity)
        if family in {"red", "rose", "pink"}:
            role = "destructive"
        elif family in {"orange", "amber", "yellow"}:
            role = "warning"
        elif family in {"lime", "green", "emerald", "teal"}:
            role = "success"
        elif family in {"slate", "gray", "zinc", "neutral", "stone"}:
            role = "muted" if utility == "bg" else ("border" if utility in {"border", "ring"} else "muted-foreground")
        else:
            role = "primary" if utility != "to" else "accent"
        if not opacity and utility == "bg" and role in {"destructive", "warning", "success"}:
            opacity = "/10"
        if not opacity and utility == "border" and role in {"destructive", "warning", "success"}:
            opacity = "/30"
        return semantic(utility, role, opacity)

    content, fixed_count = _FIXED_COLOR_CLASS.subn(fixed_replacement, content)
    return content, hex_count + literal_count + fixed_count


def design_ctx(spec: dict) -> str:
    """Architect-authored visual identity for UI-specific emphasis."""
    design = spec.get("design") or {}
    palette = design.get("palette") or {}
    typography = design.get("typography") or {}
    from agents.component_registry import component_export_map, installed_components
    available = ", ".join(installed_components())
    brand = spec.get("brand_name") or spec.get("title") or "the app"
    lines = [
        "DESIGN — authoritative Architect choices; do not replace them with a generic dashboard:",
        f"- Brand: **{brand}**. Preset: {design.get('preset')}. Mode: {design.get('mode')}.",
        f"- Audience: {spec.get('target_audience') or 'everyday users'}.",
        f"- Visual signature: {design.get('visualSignature')}.",
        f"- Navigation: {design.get('navStyle')}; spacing: {design.get('spacing')}; "
        f"radius: {design.get('radius')}; shadow: {design.get('shadow')}; motion: {design.get('motion')}.",
        f"- Typography: headings `{typography.get('heading')}`, body `{typography.get('body')}`.",
        "- Semantic palette: " + ", ".join(f"{k}={v}" for k, v in palette.items()) + ".",
        "- Style with Tailwind semantic tokens (`bg-background`, `bg-card`, `text-foreground`, "
        "`text-muted-foreground`, `bg-primary`, `border-border`) and installed `@/components/ui/*`; "
        "never use MUI, Emotion, or fixed slate/dark colours.",
        "- The hex palette above is already serialized into CSS variables. NEVER copy a hex value "
        "into TSX and never use fixed Tailwind colour families (`white`, `red-*`, `green-*`, "
        "`slate-*`, etc.); use semantic primary/muted/destructive/success/warning tokens only.",
        f"- Exact installed UI module names: {available}. No other `@/components/ui/*` module exists.",
        "- Exact UI module/export map (import only these value/type names): "
        + json.dumps(component_export_map(), sort_keys=True, separators=(",", ":")) + ".",
        "- Apply the Architect fonts with `font-heading` and `font-sans`; never invent font-named "
        "components or a `components/ui/typography` module.",
        "- Clipboard actions use `navigator.clipboard` with Button and a Lucide icon; there is no "
        "`components/ui/clipboard-copy` module.",
        "- Badge is presentational only. Every clickable/filter/toggle control must use Button (with "
        "`type=\"button\"` and `aria-pressed` where stateful), never Badge with onClick/type.",
        "- Build artwork with semantic CSS gradients. Never embed data-image/SVG URL textures in a "
        "Tailwind class. Every decorative overlay that is empty must close on the SAME tag with `/>`; "
        "never emit `/>` on a separate line.",
        "- Do not load external images, textures, or CSS background URLs unless the complete raw "
        "product request explicitly requires an external asset. Prefer layered semantic CSS gradients.",
        "- Lucide value exports are PascalCase with no underscores (for example `ClipboardCopy`, "
        "never `Clipboard_Copy`); alias them only after importing the exact export.",
        ("- REQUIRED TOP NAVIGATION: render a semantic `<nav aria-label=\"Primary\">` with useful "
         "route or in-page section links; `topnav` is a required layout element, not merely a style hint."
         if design.get("navStyle") == "topnav" else
         "- Do not invent navigation outside the Architect-selected navigation style."),
        "- Hold the DESIGN BAR in the RULE above. A page that compiles but looks unfinished is a FAIL.",
    ]
    return "\n".join(lines) + "\n\n"


def read_rule(name: str) -> str:
    try:
        return (RULES_DIR / f"{name}.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def extract_code(text: str) -> str:
    """Pull the file body out of possibly-fenced, possibly-chatty model output."""
    text = llm.strip_think(text or "")
    fences = _FENCE.findall(text)
    if fences:
        text = max(fences, key=len)
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith(_CODE_START):
            start = i
            break
    body = "\n".join(lines[start:]).strip()
    # drop a stray trailing ``` if the fence regex missed it
    body = re.sub(r"\n```+\s*$", "", body)
    return body + "\n"


_EDIT_BLOCK = re.compile(
    r"<<<<<<<\s*SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>>\s*REPLACE",
    re.DOTALL,
)


def apply_search_replace(content: str, output: str) -> tuple[str, int]:
    """Apply exact, non-overlapping Gemma micro-repair blocks in memory."""
    result, applied = content, 0
    for search, replacement in _EDIT_BLOCK.findall(output or ""):
        if not search or result.count(search) != 1:
            continue
        result = result.replace(search, replacement, 1)
        applied += 1
    return result, applied


class GenerationPreflightError(RuntimeError):
    pass


def _stable_seed(label: str, prompt: str) -> int:
    digest = hashlib.sha256(f"{label}\0{prompt}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def field_lines(model: dict) -> str:
    out = []
    for f in (model.get("fields") or []):
        if not f.get("name"):
            continue
        bits = [f"{f['name']}: {f.get('type', 'String')}"]
        if f.get("enum"):
            bits.append("enum=" + "|".join(str(v) for v in f["enum"]))
        if f.get("ref"):
            bits.append(f"ref={f['ref']}")
        if f.get("required"):
            bits.append("required")
        if f.get("unique"):
            bits.append("unique+sparse" if not f.get("required") else "unique")
        if f.get("isEmbeddedArray"):
            bits.append("embedded-array")
        if "default" in f:
            bits.append(f"default={f['default']}")
        out.append("  - " + ", ".join(bits))
    return "\n".join(out)


def ref_hints(model: dict | None, memory=None) -> str:
    """Prescriptive dropdown instructions for every ObjectId-ref field (prevents Cast errors)."""
    lines = []
    for f in ((model or {}).get("fields") or []):
        if f.get("ref"):
            rseg = route_name(f["ref"])
            lines.append(f"- `{f['name']}` references {f['ref']} → dropdown from `/api/{rseg}` "
                         f"(option value = `_id`, {_ref_label(f['ref'], memory)})")
    if not lines:
        return ""
    return ("REFERENCE FIELDS (render each as a <Select> loading its endpoint, NEVER a text input):\n"
            + "\n".join(lines) + "\n\n")


def _ref_label(ref: str, memory) -> str:
    """What to SHOW for a referenced record — its real display field, not a guess.

    The rules' example reaches for `o.name`, so the model writes `o.name` even when the entity has
    `companyName` and TypeScript rejects it. The answer is already computed
    (`contract.display_field`); it just never reached the prompt."""
    rmodel = memory.entity(pascal(ref)) if memory else None
    if not rmodel:
        return "show its display field"
    from agents.contract import display_field
    field = display_field(rmodel)
    names = [f.get("name") for f in (rmodel.get("fields") or []) if f.get("name")]
    return (f"option label = `o.{field}` — the ONLY fields it has are: "
            f"{', '.join(f'`{n}`' for n in ['_id'] + names)}")


class GenAgent:
    """Base: prompt local Gemma with full product context, preflight, and write."""
    name = "agent"

    # A file that fails the compiler twice will not pass on a third identical ask; two regenerations
    # cost ~2 min against a repair phase that costs 10-30 and often still ends red.
    ANALYZER_RETRIES = 1

    def __init__(self, project_dir, memory, emit=None, model=None, get_analyzer=None, contract=None):
        self.project_dir = Path(project_dir)
        self.memory = memory
        self.emit = emit or (lambda *a, **k: None)
        self.model = llm.pinned_model(model or llm.GEN_MODEL)
        # Callable returning the shared Analyzer (built lazily, after install). Absent → the loop is
        # skipped entirely and the harness stays the safety net.
        self.get_analyzer = get_analyzer
        # The route/API contract, for the checks a compiler cannot make: a "Login" button in an app
        # with no login page compiles perfectly and 404s on click.
        self.contract = contract or {}

    # ── llm ───────────────────────────────────────────────────────────────────
    def _gen(self, label: str, user: str, num_predict: int = 4096) -> str:
        self.emit("start", {"label": label})
        full = ""
        try:
            user = self.memory.full_context(output_tokens=num_predict) + user
            from agents.product_context import ensure_fits
            ensure_fits(user, output_tokens=num_predict)
            # think=False, and it must stay false: thinking tokens are spent from num_predict, not from
            # the (huge) context window. Measured on this build — the real route prompt at its real
            # budget: think=False → 3978 chars of complete code (`stop`); think='low' → 6505 chars of
            # thinking and ZERO code (`length`); raising the budget to 4096 just bought 15256 chars of
            # thinking and still no code. Every file came back truncated or empty.
            for tok in llm.stream_chat([{"role": "user", "content": user}],
                                       model=self.model, system=SYSTEM,
                                       num_predict=num_predict, think=False,
                                       extra_opts={"temperature": 0,
                                                   "seed": _stable_seed(label, user)}):
                full += tok
                self.emit("token", tok)
        except Exception as e:  # noqa: BLE001
            self.emit("log", {"text": f"gen error ({label}): {e}"})
            raise
        finally:
            self.emit("end", {})
        return extract_code(full)

    # ── compiler in the loop ──────────────────────────────────────────────────
    def _contract_diagnostics(self, rel: str, code: str) -> list[dict]:
        """The faults a green build hides: a link to a route that doesn't exist, a fetch to an API
        that doesn't exist, invented metrics. Shaped like compiler diagnostics so one loop fixes
        both — these checks existed and reported at the very end, where nothing acted on them."""
        if not self.contract or not rel.endswith((".ts", ".tsx")):
            return []
        try:
            from agents.quality import scan_source
            return [{"line": None, "code": f["signature"].split(":")[0], "message": f["message"]}
                    for f in scan_source(rel, code, self.contract)]
        except Exception:  # noqa: BLE001
            return []

    def exemplar_ctx(self, shape: str) -> str:
        """A sibling of this shape that the compiler already passed, as a worked example.

        The 11 stuck files in a 97-file app were almost all invented API surface (`labelId` on a
        TextField, `fullWeight`, `warning`) — the compiler names the fix and the model still misses it
        twice, so writing a rule per invention is a losing race. A real, compiling example of the same
        shape settles it by showing rather than arguing."""
        code = self.memory.exemplar(shape) if (shape and self.memory) else None
        if not code:
            return ""
        return (
            "── A COMPONENT OF THIS EXACT SHAPE THAT ALREADY COMPILES IN THIS APP ──\n"
            "Copy its proven React structure and semantic shadcn/Tailwind usage. Do NOT copy its entity, fields, "
            "labels or copy — yours are different and are specified below.\n"
            f"```tsx\n{code.strip()}\n```\n\n"
        )

    def _record_preflight_failure(self, rel: str, code: str, diagnostics: list[dict]) -> None:
        """Preserve an unpublished failing candidate so a recurring model fault can become a rule.

        The containing staging workspace is never promoted after a preflight failure, so these
        artifacts are diagnostic evidence only and cannot leak broken source into the project.
        """
        try:
            folder = self.project_dir / ".locode" / "preflight-failures"
            folder.mkdir(parents=True, exist_ok=True)
            stem = re.sub(r"[^A-Za-z0-9_.-]+", "__", rel)
            (folder / f"{stem}.candidate.txt").write_text(code, encoding="utf-8")
            (folder / f"{stem}.diagnostics.json").write_text(
                json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except Exception:  # diagnostic recording must never mask the actual generation failure
            pass

    def _gen_checked_regenerate_legacy(self, rel: str, user: str,
                                       num_predict: int = 4096, shape: str = "") -> str:
        """Generate `rel`, then let the real TypeScript compiler read it BEFORE it lands.

        The old flow wrote whatever came back and discovered the truth from `next build` ten minutes
        later, when only the repair LLM could help — and it routinely couldn't: three guarded regens
        and a cloud escalation never landed a one-character `</Alert}`. Here the same model rewrites
        its own file against the compiler's exact words, seconds after writing it, while the whole
        prompt that produced it is still the prompt."""
        code = self._gen(rel, user, num_predict)
        code, _ = scrub_jsx(rel, code, self.project_dir)
        az = self.get_analyzer() if self.get_analyzer else None
        if not az or not az.ok or not rel.endswith((".ts", ".tsx")):
            return code

        # Keep the BEST attempt, not the last: a regeneration can make things worse (measured — one
        # page went 5 diagnostics → 9), and the harness learned this lesson the expensive way.
        best, best_diags = code, None

        for attempt in range(self.ANALYZER_RETRIES + 1):
            diags = az.check(rel, code) + self._contract_diagnostics(rel, code)
            if not diags:
                self.emit("log", {"text": f"analyzer: {rel} clean"
                                          + (f" (after {attempt} regeneration(s))" if attempt else "")})
                az.release(rel)
                # Only a FIRST-try pass earns the exemplar slot: a file that needed the compiler's
                # help is not the example to hand the next one.
                if shape and attempt == 0 and self.memory:
                    self.memory.store_exemplar(shape, code)
                return code
            if best_diags is None or len(diags) < len(best_diags):
                best, best_diags = code, diags
            if attempt == self.ANALYZER_RETRIES:
                self.emit("log", {"text": f"analyzer: {rel} still has {len(best_diags)} diagnostic(s) after "
                                          f"{attempt} regeneration(s) — keeping the best attempt for the "
                                          f"repair harness"})
                break
            # Name the top diagnostic: a class that recurs across files is a RULE bug, and the log is
            # where that becomes visible (every one found so far was the rule teaching the mistake).
            top = " ".join(str(diags[0].get("message", "")).split())[:90]
            self.emit("log", {"text": f"analyzer: {rel} — {len(diags)} diagnostic(s), regenerating "
                                      f"({attempt + 1}/{self.ANALYZER_RETRIES}); top = {top}"})
            # A truncated file is a different failure: the model stopped mid-JSX, so handing the stump
            # back with "fix these errors" reproduces it — measured, 4 diagnostics → 4 → 4, and the
            # cut-off is nowhere near the token budget (215 lines of a 5000-token allowance). It needs
            # to be told it ran out of rope and to write something it can finish, not to patch.
            truncated = any(d.get("code") in (17008, 1005) or
                            "no corresponding closing tag" in str(d.get("message", ""))
                            for d in diags)
            if truncated:
                fix = (
                    f"{user}\n\n"
                    "── YOUR PREVIOUS ATTEMPT WAS CUT OFF PART-WAY THROUGH ──\n"
                    f"{format_diagnostics(diags, limit=2)}\n\n"
                    "You stopped mid-JSX and the file was never closed. Do NOT try to patch it — write "
                    "the file again from the start, SHORTER and COMPLETE:\n"
                    "- keep it under ~150 lines;\n"
                    "- fewer, simpler sections — every tag you open, close;\n"
                    "- drop decorative markup before you drop working behaviour (the form, the list, "
                    "the states must all still be there);\n"
                    "- finish with the closing brace of the component.\n"
                    "Output only the complete TSX file."
                )
            else:
                fix = (
                    f"{user}\n\n"
                    "── YOUR PREVIOUS ATTEMPT AT THIS FILE FAILED THE TYPESCRIPT COMPILER ──\n"
                    f"{format_diagnostics(diags)}\n\n"
                    "This is the file you wrote:\n"
                    f"```tsx\n{code}\n```\n"
                    "Fix EVERY error above and output the COMPLETE corrected file — same task, same "
                    "rules, no explanation, no markdown fence. Do not suppress errors with `any`, "
                    "`@ts-ignore` or by deleting the feature; fix the actual cause."
                )
            new = self._gen(rel, fix, num_predict)
            if not new.strip():
                break            # empty regeneration — keep the best we have
            code, _ = scrub_jsx(rel, new, self.project_dir)
        az.release(rel)
        return best

    # This definition intentionally supersedes the legacy whole-file regeneration loop above.
    # A candidate either becomes clean in memory through one exact micro-edit or generation stops;
    # a knowingly broken "best attempt" is never published.
    def _gen_checked(self, rel: str, user: str, num_predict: int = 4096, shape: str = "") -> str:
        code = self._gen(rel, user, num_predict)
        code, _ = scrub_jsx(rel, code, self.project_dir)
        az = self.get_analyzer() if self.get_analyzer else None
        if not az or not az.ok or not rel.endswith((".ts", ".tsx")):
            return code
        try:
            diags = az.check(rel, code) + self._contract_diagnostics(rel, code)
            _count_preflight("candidates")
            code, reference_fixes = fix_public_reference_empty_fallback(code)
            code, wiring_fixes = fix_unwired_filter_state(code)
            code, controlled_filter_fixes = fix_missing_controlled_filter_props(
                code, diags, self.contract)
            code, selection_fixes = fix_unwired_selection_state(code, self.contract)
            code, nav_fixes = fix_single_route_topnav(code, self.contract)
            code, overlay_fixes = fix_decorative_overlay_pointer_events(code)
            functional_fixes = (reference_fixes + wiring_fixes + controlled_filter_fixes +
                                selection_fixes + nav_fixes + overlay_fixes)
            if functional_fixes:
                diags = az.check(rel, code) + self._contract_diagnostics(rel, code)
                if not diags:
                    _count_preflight("microRepaired")
                    self.emit("log", {"text": f"preflight: {rel} clean after "
                                              f"{functional_fixes} proven behavior/wiring fix(es)"})
                    return code
            if not diags:
                _count_preflight("rawClean")
                self.emit("log", {"text": f"preflight: {rel} clean on raw candidate"})
                return code

            code, import_fixes = fix_missing_ui_imports(code, diags)
            code, entity_import_fixes = fix_missing_entity_type_import(code, diags, self.contract)
            code, lucide_fixes = fix_invalid_lucide_imports(code, diags)
            code, identifier_fixes = fix_compiler_suggested_identifier(code, diags)
            code, prop_field_fixes = fix_missing_canonical_prop_field(code, diags, self.contract)
            code, callback_fixes = fix_uncalled_boolean_prop(code, diags, self.contract)
            code, unsafe_html_fixes = fix_redundant_unsafe_html_prop(code, diags)
            code, duplicate_class_fixes = fix_duplicate_jsx_classname(code, diags)
            code, interactive_badge_fixes = fix_interactive_badge_as_button(code, diags)
            code, external_image_fixes = fix_forbidden_external_decorative_image(code, diags)
            code, date_literal_fixes = fix_date_literal_for_serialized_dto(code, diags)
            code, transition_state_fixes = fix_transition_misused_as_boolean_state(code, diags)
            code, dto_metadata_fixes = fix_missing_dto_metadata(code, diags, self.contract)
            code, share_test_fixes = fix_navigator_share_feature_test(code, diags)
            code, button_variant_fixes = fix_unsupported_button_link_variant(code, diags)
            code, artwork_colour_fixes = fix_missing_gradient_artwork_colors(code, diags)
            code, colour_fixes = fix_nonsemantic_color_classes(
                code, self.contract.get("design") if isinstance(self.contract, dict) else {})
            deterministic_fixes = (import_fixes + entity_import_fixes + lucide_fixes + identifier_fixes +
                                   prop_field_fixes + callback_fixes + unsafe_html_fixes
                                   + duplicate_class_fixes + interactive_badge_fixes
                                   + external_image_fixes
                                   + date_literal_fixes + transition_state_fixes
                                   + dto_metadata_fixes + share_test_fixes
                                   + button_variant_fixes
                                   + artwork_colour_fixes + colour_fixes)
            if deterministic_fixes:
                diags = az.check(rel, code) + self._contract_diagnostics(rel, code)
                if not diags:
                    _count_preflight("microRepaired")
                    self.emit("log", {"text": f"preflight: {rel} clean after "
                                              f"{deterministic_fixes} proven token/import fix(es)"})
                    return code

            top = " ".join(str(diags[0].get("message", "")).split())[:110]
            self.emit("log", {"text": f"preflight: {rel} has {len(diags)} diagnostic(s); "
                                      f"one bounded micro-repair; top = {top}"})
            repair_budget = repair_output_budget(code, diags)
            repair_prompt = (
                self.memory.full_context(output_tokens=repair_budget)
                + "CURRENT FILE TASK:\n" + user + "\n\n"
                + "DIAGNOSTICS:\n" + format_diagnostics(diags) + "\n\n"
                + "FULL FAILING FILE:\n```tsx\n" + code + "\n```\n\n"
                + "Return one or more exact SEARCH/REPLACE blocks. Keep the edit minimal."
            )
            from agents.product_context import ensure_fits
            ensure_fits(repair_prompt, output_tokens=repair_budget)
            try:
                repair = llm.chat(
                    [{"role": "user", "content": repair_prompt}],
                    model=self.model,
                    system=REPAIR_SYSTEM,
                    num_predict=repair_budget,
                    think=False,
                    extra_opts={"temperature": 0, "seed": _stable_seed(rel + ":repair", repair_prompt)},
                )
            except Exception:
                self._record_preflight_failure(rel, code, diags)
                raise
            fixed, applied = apply_search_replace(code, repair)
            if not applied:
                _count_preflight("failed")
                self._record_preflight_failure(rel, code, diags)
                raise GenerationPreflightError(
                    f"{rel}: Gemma returned no unambiguous SEARCH/REPLACE edit for "
                    f"{len(diags)} preflight diagnostic(s)."
                )
            fixed, _ = scrub_jsx(rel, fixed, self.project_dir)
            remaining = az.check(rel, fixed) + self._contract_diagnostics(rel, fixed)
            if remaining:
                _count_preflight("failed")
                self._record_preflight_failure(rel, fixed, remaining)
                raise GenerationPreflightError(
                    f"{rel}: bounded micro-repair left {len(remaining)} preflight diagnostic(s): "
                    f"{format_diagnostics(remaining, limit=3)}"
                )
            self.emit("log", {"text": f"preflight: {rel} clean after {applied} bounded compiler edit(s)"})
            _count_preflight("microRepaired")
            return fixed
        finally:
            az.release(rel)

    # ── disk + streaming ──────────────────────────────────────────────────────
    def write(self, rel: str, content: str):
        content, scrubbed = scrub_jsx(rel, content, self.project_dir)
        if scrubbed:
            self.emit("log", {"text": f"scrubbed {scrubbed} mechanical TSX fix(es) in {rel}"})
        fp = self.project_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        self.emit("file", {"path": rel, "content": content})
        try:
            self.memory.note_progress(f"{self.name}: wrote {rel} ({len(content)}B)")
        except Exception:
            pass
        return rel


class ModelAgent(GenAgent):
    name = "model"

    def generate(self, model: dict) -> str:
        name = pascal(model.get("name", "Item"))
        others = [n for n in self.memory.model_names() if n != name]
        user = (
            f"RULE:\n{read_rule('model')}\n\n"
            f"TASK: Generate `models/{name}.ts` for model **{name}** with EXACTLY these fields:\n"
            f"{field_lines(model)}\n\n"
            f"Valid ref targets: {', '.join(others) or '(none)'}.\n"
            f"Output only the TypeScript file."
        )
        budget = max(800, min(1800, 650 + len(model.get("fields") or []) * 110))
        code = self._gen_checked(f"models/{name}.ts", user, num_predict=budget)
        return self.write(f"models/{name}.ts", code)


class RouteAgent(GenAgent):
    name = "route"

    def generate(self, model: dict) -> list[str]:
        from agents.scaffold import auth_enabled
        name = pascal(model.get("name", "Item"))
        seg = route_name(name)
        written = []
        # The RULE documents `requireUser`/`requireRole` and says to apply "the auth rule supplied by the
        # TASK" — so the TASK must supply one. Left unsaid, the model imports '@/lib/auth', which only
        # exists in auth-enabled apps: a no-auth app then fails to build with "Can't resolve '@/lib/auth'".
        if auth_enabled(self.memory.spec):
            auth_ctx = ("AUTH: this app HAS authentication. Apply the auth rule from the RULE section "
                        "(`requireUser()` / `requireRole('admin')` from '@/lib/auth') before any database "
                        "access, and derive ownership from the session — never from the request body.\n\n")
        else:
            auth_ctx = ("AUTH: this app has NO authentication and NO user accounts. '@/lib/auth' DOES NOT "
                        "EXIST — importing it breaks the build. Never import it; never call requireUser, "
                        "requireRole, getSession or auth(); never reference session/owner/userId fields. "
                        "Every handler is public: connect to the DB and act directly.\n\n")
        base = (
            f"RULE:\n{read_rule('route')}\n\n"
            f"{auth_ctx}"
            f"MEMORY (this model's fields):\n## {name}\n{field_lines(model)}\n\n"
        )
        route_budget = max(1200, min(2200, 1100 + len(model.get("fields") or []) * 100))
        coll = self._gen_checked(
            f"app/api/{seg}/route.ts",
            base + f"TASK: Generate the COLLECTION handler `app/api/{seg}/route.ts` "
                   f"(GET list + POST create) for model **{name}** (import from '@/models/{name}'). "
                   f"Output only the file.",
            num_predict=route_budget)
        written.append(self.write(f"app/api/{seg}/route.ts", coll))
        one = self._gen_checked(
            f"app/api/{seg}/[id]/route.ts",
            base + f"TASK: Generate the ITEM handler `app/api/{seg}/[id]/route.ts` "
                   f"(GET one + PUT + DELETE, validate ObjectId) for model **{name}** "
                   f"(import from '@/models/{name}'). Each handler signature MUST be exactly "
                   f"`(_req: Request, {{ params }}: {{ params: Promise<{{ id: string }}> }})` and use "
                   f"`const {{ id }} = await params`. NEVER read the id from req.url. Output only the file.",
            num_predict=route_budget)
        written.append(self.write(f"app/api/{seg}/[id]/route.ts", one))
        return written


class PageAgent(GenAgent):
    name = "page"

    def _page_file(self, path: str) -> str:
        clean = str(path or "/").strip("/")
        return f"app/{clean}/page.tsx" if clean else "app/page.tsx"

    def generate(self, page: dict, component: str) -> str:
        path = str(page.get("path") or "/")
        kind = str(page.get("kind") or "static")
        declared_resource = page.get("resource") or next(iter(page.get("resources") or []), "")
        resource = pascal(declared_resource) if declared_resource else ""

        # The body is generated first, so its signature is a FACT — read it from the file instead of
        # having two rule docs agree about it by convention. They didn't: `rules/page.md` said "pass
        # `initialItem` for every `[id]` route" while the section agent only declared props for
        # `kind == "detail"`, so an edit page passed a prop to a body that took none. Every such
        # mismatch was a type error the model could not have known about.
        body_rel = f"components/pages/{component}.tsx"
        signature = ""
        az = self.get_analyzer() if self.get_analyzer else None
        if az and az.ok:
            itf = az.interface(body_rel)
            if itf.get("found") and itf.get("name"):
                props = itf.get("props")
                signature = (
                    f"THE BODY COMPONENT ALREADY EXISTS. Its real signature, read from the file:\n"
                    f"  `export default function {itf['name']}({props or ''})`\n"
                    + ("It takes NO props — render it as `<%s />` and pass nothing.\n" % itf["name"]
                       if not props else
                       "Pass EXACTLY those props, with those exact names — nothing else.\n")
                )

        user = (
            f"RULE:\n{read_rule('page')}\n\n"
            f"{signature}"
            f"TASK: Generate the route wrapper `{self._page_file(path)}` for route `{path}` "
            f"(kind=`{kind}`). It renders the body component `@/components/pages/{component}`"
            + (f" and the resource model is **{resource}**." if resource else ".")
            + " Output only the file."
        )
        code = self._gen_checked(self._page_file(path), user, num_predict=900)
        return self.write(self._page_file(path), code)


class SectionAgent(GenAgent):
    name = "section"

    def generate(self, page: dict, component: str, imports=None,
                 archetype: str = "", pattern: str = "") -> str:
        path = str(page.get("path") or "/")
        kind = str(page.get("kind") or "static")
        declared_resource = page.get("resource") or next(iter(page.get("resources") or []), "")
        resource = pascal(declared_resource) if declared_resource else ""
        model = self.memory.entity(resource) if resource else None
        seg = route_name(resource) if resource else ""
        fields_ctx = f"Resource **{resource}** (`/api/{seg}`) fields:\n{field_lines(model)}\n\n" if model else ""
        # Reference fields → exact dropdown endpoints (prevents 'Cast to ObjectId' runtime crashes).
        # One builder for both agents: this used to be a second copy that drifted — it never learned
        # to name the referenced entity's real display field.
        ref_ctx = ref_hints(model, self.memory)
        # Sections may be plain strings (AutoHub SRS) or objects {section_name, components}
        # (role-wise SRS). Normalize to labels; collect declared component hints.
        sections, comp_hints = [], []
        for s in (page.get("sections") or []):
            if isinstance(s, dict):
                if s.get("section_name"):
                    sections.append(str(s["section_name"]))
                comp_hints += [str(c) for c in (s.get("components") or [])]
            elif str(s).strip():
                sections.append(str(s))
        funcs = page.get("functions") or []
        # `Record<string, any>` (not `unknown`): a detail page renders `{initialItem.field}` directly,
        # and `unknown` is not a ReactNode — every field render would be a type error.
        # The page wrapper server-fetches the record for EVERY `[id]` route and passes `initialItem`
        # (see rules/page.md) — an edit route is `kind: form` but still has an id, and only `detail`
        # was told about the prop. So the page passed one and the body took none: a type error on
        # every edit page in every role-wise app.
        takes_item = kind == "detail" or (kind in ("form", "admin") and "[id]" in path)
        detail = "initialItem: Record<string, any>" if takes_item else ""
        seg_detail = f"/{seg}/[id]" if seg else ""
        has_detail = seg_detail in self.memory.valid_routes() if seg else False
        api_contract = self.contract.get("api") if isinstance(self.contract, dict) else {}
        api_ctx = ""
        if not api_contract:
            api_ctx = (
                "API BOUNDARY: this product declares NO API endpoints. Never call `fetch`, never invent "
                "an `/api/...` route, and never simulate a server response. Implement all declared "
                "interactions as typed local client logic.\n\n"
            )
        # When declared components have already been generated as their own files, the page
        # body COMPOSES them (imports + layout) instead of re-implementing all UI. This keeps
        # each generation small, so it is not truncated.
        imports = imports or []
        compose_ctx = ""
        if imports:
            imp_lines = "\n".join(f"import {pascal(n)} from '{p}'" for n, p in imports)
            component_names = ", ".join(pascal(n) for n, _ in imports)
            # Show each chunk's REAL signature, read from the file just written. The page is the only
            # place that knows the state, so a chunk with props must be WIRED here — and a wiring
            # invented against a remembered contract is exactly the mismatch this whole loop exists to
            # stop. The compiler checks it a second later, but only if the page was told the truth.
            az = self.get_analyzer() if self.get_analyzer else None
            sig_lines = []
            for n, p in imports:
                itf = az.interface(p.replace("@/", "") + ".tsx") if az and az.ok else {}
                if itf.get("name"):
                    sig_lines.append(f"  `export default function {itf['name']}({itf.get('props') or ''})`")
            sigs = ("Their REAL signatures, read from the files:\n" + "\n".join(sig_lines) + "\n"
                    "Pass EXACTLY those props — this page owns the state they need.\n"
                    if sig_lines else "")
            compose_ctx = (
                "COMPOSE existing components — these are ALREADY generated. Import each EXACTLY as shown "
                "and place it inside its section; do NOT re-implement their internals:\n"
                + imp_lines + "\n" + sigs
                + f"Place every component within its matching section: {component_names}. NEVER render a "
                  "bare `<Component />` when its real signature above has required props; create and wire "
                  "the page-owned state/callbacks first. Add only section headings/layout around them.\n\n")
        # A composing page and a standalone one are different shapes: the first wires chunks, the
        # second writes the whole surface. Keying them together would teach the wrong lesson.
        shape = f"section:{kind}" + (":composed" if imports else "")
        content_ctx = ""
        raw_request = str(self.memory.spec.get("_raw_idea") or "")
        fixed_count = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
            r"([a-z][a-z0-9-]*)\s+types?\b", raw_request, re.I)
        public_reference = (str(page.get("access") or "public") == "public" and
                            not (self.memory.spec.get("auth") or {}).get("enabled") and
                            (re.search(r"guide|reference|comparison|educational", kind, re.I) or
                             re.search(r"\bcompare\b", raw_request, re.I)))
        if fixed_count and public_reference and resource:
            words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                     "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
            token = fixed_count.group(1).lower()
            expected_count = words.get(token, int(token) if token.isdigit() else 0)
            content_ctx = (
                "FIRST-LOAD REFERENCE CONTENT (explicit user requirement): this no-account public "
                f"guide must be useful with a new/empty database. Define exactly {expected_count} "
                f"domain-accurate `{resource}` reference records in this file and display them on "
                "first load; an empty GET response must not turn the requested guide into a blank "
                "product. Include every required DTO field plus stable `_id`, `createdAt`, and "
                "`updatedAt` values. A failed API may show a non-blocking error while preserving the "
                "reference content. Filtering may still produce the designed empty state. These are "
                "requested educational examples, not fake business records or metrics.\n\n"
            )
        user = (
            f"RULE:\n{read_rule('section')}\n\n"
            f"{design_ctx(self.memory.spec)}"
            f"{fields_ctx}{ref_ctx}{api_ctx}{content_ctx}{compose_ctx}"
            f"TASK: Generate the page body `components/pages/{component}.tsx`.\n"
            f"Route: `{path}`  Kind: `{kind}`  Access: `{page.get('access', 'public')}`\n"
            + (f"PAGE ARCHETYPE — build the page in THIS shape (not a generic table/dashboard): "
               f"**{archetype}** — {pattern}\n" if archetype and pattern else "")
            + (f"Declared sections (render each as its own <section>, min 4): {', '.join(sections)}\n" if sections else "")
            + (f"Declared UI blocks to include: {', '.join(dict.fromkeys(comp_hints))}\n" if comp_hints and not imports else "")
            + (f"Declared functions to support: {', '.join(funcs)}\n" if funcs else "")
            + (f"Component props: {{ {detail} }}\n" if detail else "")
            + (f"Type records with the entity DTO: `import type {{ {resource} }} from '@/types'` and use "
               f"ONLY its exact field names (see CONTRACT). NEVER redeclare a local `{resource}` "
               f"interface/type and NEVER invent a field name.\n" if resource else "")
            + "IMPORT COMPLETENESS: every JSX component identifier used in the file must be imported. "
              "For shadcn modules, import every used named export from the exact UI export map.\n"
            + "DTO DATE RULE: generated DTOs serialize Date fields as ISO strings. In typed record literals, "
              "use `new Date(...).toISOString()`, never a Date object.\n"
            + "CURATED DTO RECORD RULE: every typed entity record literal must include its canonical "
              "`_id`, `createdAt`, and `updatedAt` string metadata from `@/types`, using stable values.\n"
            + "LINK RULES: only use <a href> / navigation to a route in VALID ROUTES above. "
              "NEVER invent a route or link to one not listed (it will 404). For per-record actions, "
              "call the API with fetch — do not navigate.\n"
            + (f"A detail page `{seg_detail}` EXISTS — list rows may link to it.\n" if has_detail
               else (f"There is NO detail page for this resource — do NOT link rows to `/{seg}/<id>`; "
                     f"edit inline via a modal + the API instead.\n" if seg else ""))
            + "Output only the TSX file (first line 'use client')."
        )
        # Composing pages are small (imports + layout). Standalone pages must have enough output
        # headroom for every declared interaction and state; unfamiliar Architect-authored kinds
        # (calculator, editor, map, timeline, etc.) are often the richest and must not fall into a
        # smaller generic budget.
        if not imports:
            user += ("\nKeep this standalone file focused and complete (normally 180-320 lines). "
                     "Prefer compact data-driven controls over repeated decorative markup, and close "
                     "every JSX tag and JavaScript brace before ending the response.\n")
        # A composed page still owns all cross-component state and callback wiring. Four imported
        # blocks routinely need ~170 lines; the old fixed 1,800-token allowance once returned an
        # empty `done_reason=length` response. Size this file from its actual composition contract.
        expected_lines = min(240, 70 + (30 * len(imports))) if imports else 240
        if content_ctx:
            expected_lines = min(240, expected_lines + 50)
        np = max(3200, min(5200, expected_lines * 24))
        rel = f"components/pages/{component}.tsx"
        code = self._gen_checked(rel, user, num_predict=np, shape=shape)
        # Record the produced page-body component so COMPONENTS.md + LOCATIONS.md are complete (page
        # bodies used to be invisible to memory — COMPONENTS.md always read "(none yet)").
        self.memory.note_component(rel)
        return self.write(rel, code)


class LogicAgent(GenAgent):
    name = "logic"

    def generate(self, rel: str, task: str, num_predict: int = 2400) -> str:
        user = (
            f"RULE:\n{read_rule('logic')}\n\n"
            f"TASK: Generate `{rel}`. {task}\nOutput only the TypeScript file."
        )
        code = self._gen_checked(rel, user, num_predict=num_predict)
        return self.write(rel, code)


class ComponentAgent(GenAgent):
    name = "component"

    def generate(self, rel: str, task: str, num_predict: int = 1800) -> str:
        user = (
            f"RULE:\n{read_rule('component')}\n\n"
            f"TASK: Generate `{rel}`. {task}\nOutput only the TSX file."
        )
        code = self._gen_checked(rel, user, num_predict=num_predict)
        self.memory.note_component(rel)
        return self.write(rel, code)


class UpdateAgent(GenAgent):
    """Full-context, complete-file update that must pass the same in-memory preflight."""
    name = "update"

    def generate_update(self, rel: str, request: str, existing: str,
                        dependency_context: str, *, is_new: bool = False) -> str:
        lines = max(60, min(180, len(existing.splitlines()) or 120))
        forbidden = (
            "Do not add routes, APIs, fields, packages, or `@/components/ui/*` modules absent from "
            "the PRODUCT CONTEXT. Never import MUI or Emotion. Never replace this product with a "
            "generic page or fixed dashboard template."
        )
        user = (
            f"RULE:\n{read_rule('component')}\n\n"
            f"{design_ctx(self.memory.spec)}"
            f"TASK: {'Create' if is_new else 'Update'} the complete file `{rel}` for this latest request:\n"
            f"{request}\n\n"
            f"FULL CURRENT FILE ({'new file; currently empty' if is_new else 'authoritative'}):\n"
            f"```tsx\n{existing}\n```\n\n"
            "RELEVANT IMPORTED/DEPENDENT FILES AND SIGNATURES:\n"
            f"{dependency_context}\n\n"
            "Required: preserve every unaffected behavior; implement responsive 375px and 1440px "
            "layouts, keyboard/focus accessibility, real domain copy, and complete loading, empty, "
            "error, success, validation, and interaction states wherever relevant.\n"
            f"{forbidden}\n"
            f"Keep the complete result within 60-{lines} lines by extracting no undeclared modules.\n"
            "Output only the complete file, with every tag and brace closed."
        )
        budget = max(1000, min(2800, lines * 13))
        code = self._gen_checked(rel, user, num_predict=budget, shape="update:component")
        self.memory.note_component(rel)
        return self.write(rel, code)


# Final public component generator: combines the generic helper with the Architect-contract path.
class ComponentAgent(UpdateAgent):
    name = "component"

    def generate(self, rel: str, task: str, num_predict: int = 1800) -> str:
        user = (
            f"RULE:\n{read_rule('component')}\n\n"
            f"TASK: Generate `{rel}`. {task}\nOutput only the TSX file."
        )
        code = self._gen_checked(rel, user, num_predict=num_predict)
        self.memory.note_component(rel)
        return self.write(rel, code)

    def generate_contract(self, contract: dict, rel: str) -> str:
        """Generate one declared, self-contained reusable component from its contract."""
        name = pascal(contract.get("name", "Component"))
        ctype = str(contract.get("type", "display"))
        resources = [pascal(r) for r in (contract.get("allowed_resources") or [])]
        model, primary = None, ""
        for rn in resources:
            model = self.memory.entity(rn)
            if model:
                primary = rn
                break
        if not primary and resources:
            primary = resources[0]
        seg = route_name(primary) if primary else ""
        fields_ctx = (f"Primary resource **{primary}** (`/api/{seg}`) fields:\n{field_lines(model)}\n\n"
                      if model else "")
        detail_seg = f"/{seg}/[id]" if seg else ""
        has_detail = detail_seg in self.memory.valid_routes() if seg else False
        # A CHUNK declares its props and is driven by its parent; a self-contained component fetches
        # for itself. Chunking exists because a 340-line page body is where the model loses the thread
        # and truncates mid-JSX — the one failure regeneration cannot fix, because the rewrite is just
        # as long. Small pieces converge; the analyzer then verifies the wiring between them.
        props = str(contract.get("props") or "").strip()
        signature = f"function {name}({{ {', '.join(p.split(':')[0].strip() for p in props.split(';') if p.strip())} }}: {{ {props} }})" if props else f"function {name}()"
        expected = max(60, min(180, int(contract.get("expectedLines") or 120)))
        state = [str(v) for v in (contract.get("state") or [])]
        actions = [str(v) for v in (contract.get("actions") or [])]
        dependencies = [str(v) for v in (contract.get("dependencies") or [])]

        # Dependency paths in the Architect plan are intent; the interfaces of files already accepted
        # by TypeScript are facts. Consumers must see those real signatures or they guess named versus
        # default exports and add callback props that do not exist.
        dependency_ctx = ""
        az = self.get_analyzer() if self.get_analyzer else None
        if dependencies and az and az.ok:
            facts = []
            for dependency in dependencies:
                dep_rel = dependency.replace("\\", "/").lstrip("/")
                itf = az.interface(dep_rel)
                module = "@/" + re.sub(r"\.(?:tsx?|jsx?)$", "", dep_rel)
                exported = az.exports(module)
                names = ", ".join(exported.get("names") or []) or "(default only or no named values)"
                if itf.get("found") and itf.get("name"):
                    facts.append(
                        f"- `{module}`: default `function {itf['name']}({itf.get('props') or ''})`; "
                        f"named value exports: {names}. Pass no props beyond this signature."
                    )
                else:
                    facts.append(f"- `{module}`: named value exports: {names}.")
            dependency_ctx = (
                "COMPILER-VERIFIED DEPENDENCY EXPORTS (these override guesses or remembered APIs):\n"
                + "\n".join(facts) + "\nImport default exports with a default import and named exports "
                "with braces. Do not add props absent from the verified signature.\n\n"
            )

        # An app asks for a dozen of each shape (12 tables, 12 form dialogs). Key the exemplar on the
        # shape, not the entity, so the second Table learns from the first.
        shape = f"component:{ctype}"
        user = (
            f"RULE:\n{read_rule('component')}\n\n"
            f"{design_ctx(self.memory.spec)}"
            f"{fields_ctx}{ref_hints(model, self.memory)}{dependency_ctx}"
            f"TASK: Generate the reusable component `{rel}`.\n"
            f"Default export EXACTLY `{signature}` (kind: {ctype}). The default-exported function "
            f"itself must be named `{name}`; do not create a differently named default wrapper.\n"
            f"Architect responsibility: {contract.get('responsibility') or contract.get('task') or name}.\n"
            f"State owned here: {', '.join(state) or '(none)'}.\n"
            f"Actions implemented here: {', '.join(actions) or '(none)'}.\n"
            f"Dependencies already available: {', '.join(dependencies) or '(none)'}.\n"
            + (f"These props are its ENTIRE input — the parent page passes exactly these and nothing "
               f"else. Declare them exactly as written, add no others, and give none a default.\n"
               if props else "")
            + ("" if props else
               (f"It works with **{primary}** at `/api/{seg}` — fetch its own data on mount and handle "
                f"loading/empty/error states.\n" if seg else
                "If it needs data, fetch a real endpoint from the API memory; otherwise render its UI.\n"))
            + (f"Type records with the entity DTO: `import type {{ {primary} }} from '@/types'` and use "
               f"ONLY its exact field names (see CONTRACT). NEVER invent a field name.\n" if primary else "")
            + f"Keep it COMPLETE in the Architect-approved range of 60-{expected} lines; close every tag and brace.\n"
            + "ACCESSIBILITY: stateful choice/filter buttons must use `type=\"button\"` and "
              "`aria-pressed={isActive}`; icon-only buttons need an aria-label; all controls need a "
              "visible or programmatic label.\n"
            + "LINK RULES: only <a href> to a route in VALID ROUTES; for record actions call the API with fetch.\n"
            + (f"A detail page `{detail_seg}` EXISTS — rows may link to it.\n" if has_detail
               else (f"There is NO detail page for `{primary}` — edit inline via a modal + the API.\n" if seg else ""))
            + "Output only the TSX file (first line 'use client')."
        )
        budget = max(1000, min(2800, expected * 13))
        code = self._gen_checked(rel, user, num_predict=budget, shape=shape)
        self.memory.note_component(rel)
        return self.write(rel, code)
