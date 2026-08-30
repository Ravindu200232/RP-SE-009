"""Scope and safety rules for selected UI elements."""
import difflib
import re
# Source: import_reader.py — imported helper(s) come from this file.
from agents.core.imports.import_reader import parse_exports, resolve_local
# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import feature_prompt

LOCAL_IMPORT_RE = re.compile(r"""(?:from|import)\s*['"]((?:\.{1,2}/|@/)[^'"]+)['"]""")

# Map each local source path to the files that import it.
def render_index(files: dict) -> dict:
    """Map each local source path to the files that import it."""
    out = {}
    for rel, body in (files or {}).items():
        if not rel.endswith((".js", ".jsx")):
            continue
        for spec in LOCAL_IMPORT_RE.findall(body or ""):
            # From: agents/core/imports/import_reader.py
            target = resolve_local(rel, spec, files)
            if target:
                out.setdefault(target, set()).add(rel)
    return out


# `app/(auth)/login/page.jsx` -> `/login`. Groups and the root handled.
def _route_of_page(rel: str) -> str:
    """`app/(auth)/login/page.jsx` -> `/login`. Groups and the root handled."""
    parts = rel.split("/")[1:-1]
    segs = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
    return "/" + "/".join(segs) if segs else "/"


# Walk importers to return every page route that renders ``target``.
def routes_rendering(files: dict, target: str) -> list:
    """Walk importers to return every page route that renders ``target``."""
    files = files or {}
    target = (target or "").lstrip("./").replace("\\", "/")
    if not target:
        return []

    pages = [r for r in files if re.fullmatch(r"app/.*page\.jsx?", r)]
    index = render_index(files)

    seen, queue, roots = set(), [target], set()
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        name = rel.rsplit("/", 1)[-1]
        if re.fullmatch(r"(page|layout)\.jsx?", name):
            roots.add(rel)

            continue
        for importer in index.get(rel, ()):
            if importer not in seen:
                queue.append(importer)

    out = set()
    for rel in roots:
        name = rel.rsplit("/", 1)[-1]
        if name.startswith("page."):
            out.add(_route_of_page(rel))
            continue

        under = rel.rsplit("/", 1)[0] + "/"
        for p in pages:
            if p.startswith(under):
                out.add(_route_of_page(p))
    return sorted(out)


# Returns a repairable reason when a whole-file edit violates scope.
def guard_scope(old: str, new: str, *, anchor: str = "", removing: bool = False,
                adding: bool = False, retexting: bool = False,
                designing: bool = False,
                max_changed_frac: float = 0.20, min_abs: int = 25) -> str | None:
    """Return a repairable reason when a whole-file edit violates scope."""
    if not new or not new.strip():
        return "the rewrite is empty"
    floor = 0.25 if designing else 0.6
    if len(new) < floor * len(old):
        return (f"the rewrite is {len(new)} characters against {len(old)} before "
                f"— the file was truncated rather than edited")
    if designing:
        return None

    old_lines, new_lines = old.splitlines(), new.splitlines()
    changed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, old_lines, new_lines).get_opcodes():
        if tag != "equal":
            changed += max(i2 - i1, j2 - j1)
    ceiling = max(min_abs, int(len(old_lines) * max_changed_frac))
    if changed > ceiling and not adding:
        return (f"{changed} lines changed out of {len(old_lines)}; this edit "
                f"should touch at most {ceiling}. Rewrite the file again, "
                f"identical to the original except for the one element")

    # From: agents/core/imports/import_reader.py
    a, b = parse_exports(old), parse_exports(new)
    lost = a.named - b.named
    if lost:
        return (f"the rewrite dropped {', '.join(sorted(lost))} from the file's "
                f"exports — other files import those")
    if a.has_default and not b.has_default:
        return "the rewrite dropped the default export"

    if (anchor and not removing and not retexting and len(anchor) >= 4
            and anchor not in new):
        return (f"the element is gone: {anchor[:60]!r} no longer appears in the "
                f"file, but the instruction was not to remove it")
    return None


REMOVAL_WORDS = ("remove", "delete", "hide", "get rid", "take out", "drop",
                 "ain karanna", "ayin karanna", "නැති කරන්න", "ඉවත් කරන්න")


GLOBAL_WORDS = ("everywhere", "all pages", "every page", "site-wide",
                "sitewide", "whole site", "across the site", "globally",
                "all routes", "hama thanama", "hama page ekakama",
                "siyaluma", "හැම තැනම", "හැම පිටුවකම", "සියලුම")


# Whether the user said, in so many words, that they mean every page.
def looks_like_global(instruction: str) -> bool:
    """Whether the user said, in so many words, that they mean every page."""
    low = (instruction or "").lower()
    return any(w in low for w in GLOBAL_WORDS)


PAGE_ONLY_WORDS = ("only", "just this", "just on", "this page", "here only",
                   "on this route", "witharai", "vitharai", "විතරයි",
                   "මේ පිටුවේ", "me page eke")


# Whether the user has said they mean this one route.
def looks_like_page_only(instruction: str) -> bool:
    """Whether the user has said they mean this one route."""
    low = (instruction or "").lower()
    if looks_like_global(low):
        return False
    return any(w in low for w in PAGE_ONLY_WORDS)


ADDITION_WORDS = ("add", "insert", "append", "put a", "put an", "create",
                  "new section", "another", "extra", "include a", "include an",
                  "danna", "add karanna", "aluth", "අලුත්", "එකතු කරන්න")


# Checks whether looks like removal is true for the current pipeline state.
def looks_like_removal(instruction: str) -> bool:
    """Return whether looks like removal is true for the current pipeline state."""
    low = (instruction or "").lower()
    return any(w in low for w in REMOVAL_WORDS)


# Checks whether looks like addition is true for the current pipeline state.
def looks_like_addition(instruction: str) -> bool:
    """Return whether looks like addition is true for the current pipeline state."""
    low = (instruction or "").lower()
    if looks_like_removal(low):
        return False
    return any(w in low for w in ADDITION_WORDS)


RETEXT_RE = re.compile(
    r"\b(?:rename|retitle|reword|relabel)\b"
    r"|\bchange\b[^.]{0,60}\b(?:to|into)\b"
    r"|\breplace\b[^.]{0,60}\bwith\b"
    r"|\b(?:text|wording|label|caption|title|heading|copy)\b[^.]{0,40}"
    r"\b(?:to|say|reads?|instead)\b"
    r"|\bmake it (?:say|read)\b|\bcall it\b|\bset it to\b"
    r"|\bwenas karanna\b|වෙනස් කරන්න",
    re.I)


# Whether the instruction is asking for the element's words to change.
def looks_like_retext(instruction: str) -> bool:
    """Whether the instruction is asking for the element's words to change."""
    return bool(RETEXT_RE.search(instruction or ""))


# From: agents/features/feature_prompts.py
ELEMENT_EDIT_SYSTEM = feature_prompt("ELEMENT_EDIT", foundation=True)


# A compact, human-readable rendering of the clicked element.
def describe(el: dict) -> str:
    """A compact, human-readable rendering of the clicked element."""
    attrs = el.get("attrs") or {}
    bits = [f"<{el.get('tag', 'div')}"]
    if el.get("id"):
        bits.append(f' id="{el["id"]}"')
    if el.get("className"):
        bits.append(f' class="{el["className"][:120]}"')
    for k in ("href", "type", "placeholder", "aria-label"):
        if attrs.get(k):
            bits.append(f' {k}="{attrs[k]}"')
    bits.append(">")
    text = (el.get("text") or "").strip()
    if text:
        bits.append(text[:160])
        bits.append(f"</{el.get('tag', 'div')}>")
    chain = " › ".join(a.get("tag", "") for a in (el.get("chain") or [])[:4])
    out = "".join(bits)
    if chain:
        out += f"\nInside: {chain}"
    return out


JSX_TEXT_RE = re.compile(r">\s*([^<>{}\n][^<>{}]{2,80}?)\s*<")


ARRAY_STR_RE = re.compile(r"\[[^\]]*?\]")
QUOTED_RE = re.compile(r"""['"]([^'"\n]{3,60})['"]""")


# The words a page shows, normalised. Empty for a file with no JSX.
def visible_strings(src: str) -> set:
    """The words a page shows, normalised. Empty for a file with no JSX."""
    out = {text for match in JSX_TEXT_RE.finditer(src or "")
           if (text := " ".join(match.group(1).split()))
           and not text.startswith(("/", "*"))
           and any(char.isalpha() for char in text)}
    for arr in ARRAY_STR_RE.findall(src or ""):
        # From: agents/planner/builder/project_memory.py
        out.update(text for value in QUOTED_RE.findall(arr)
                   if (text := " ".join(value.split()))
                   and not re.search(r"\b(?:bg|text|border|flex|grid|p|m)-", text))
    return out


# Report when a rewrite silently drops too much visible content.
def lost_content(old: str, new: str, tolerance: float = 0.2) -> str | None:
    """Report when a rewrite silently drops too much visible content."""
    before = visible_strings(old)
    if len(before) < 4:
        return None
    gone = sorted(t for t in before if t not in (new or ""))
    if len(gone) <= max(1, int(len(before) * tolerance)):
        return None
    sample = ", ".join(repr(t) for t in gone[:5])
    return (f"the rewrite dropped {len(gone)} of {len(before)} things the page "
            f"showed — {sample}. Put them back: this edit was meant to change "
            f"the layout, not remove content")
