"""
Named imports that the target module does not export.

JavaScript has no compile-time export checking, so `next build` happily compiles
a file that does `import { findUserByEmail } from '@/lib/auth'` against a module
exporting no such name.  The failure only appears at request time as a 500 —
which is exactly the "login goes to the dashboard then bounces back" bug.

This module is the deterministic detector.  Pure Python, no dependency, shared
by ArchitectAgent.lint_generated(), AnalyzerAgent.scan() and
server.verify_after_edit().

Every decision is biased away from false positives, because a false positive
sends the model off to "fix" working code:

  * only local specs (`./`, `../`, `@/`) are checked — an npm package's export
    surface is unknowable from source, and `lucide-react` would light up
    instantly;
  * exports are read from the raw source *and* the comment-stripped source and
    unioned, so a stripper confused by an apostrophe in JSX text
    (`<p>Don't have an account?</p>`) can never make a real export vanish;
  * imports are read from the stripped source only, so a commented-out import
    is never checked;
  * a module that re-exports from something unresolvable has an unknown export
    surface and is suppressed entirely rather than guessed at.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

LOCAL_PREFIXES = ("./", "../", "@/")
SKIP_SUFFIXES = (".css", ".scss", ".json", ".svg", ".png", ".jpg", ".webp")
CODE_SUFFIXES = (".js", ".jsx")


FRAMEWORK_EXPORTS = {

    "next/server": {"NextRequest", "NextResponse", "ImageResponse", "userAgent",
                    "userAgentFromString", "URLPattern", "after", "connection",
                    "unstable_rootParams"},
    "next/headers": {"cookies", "headers", "draftMode"},

    "next/navigation": {"redirect", "permanentRedirect", "notFound", "forbidden",
                        "unauthorized", "useRouter", "usePathname",
                        "useSearchParams", "useParams", "unstable_rethrow",
                        "useSelectedLayoutSegment", "useSelectedLayoutSegments",
                        "ReadonlyURLSearchParams", "RedirectType",
                        "ServerInsertedHTMLContext", "useServerInsertedHTML",
                        "unstable_isUnrecognizedActionError"},

    "next/cache": {"revalidatePath", "revalidateTag", "unstable_cache",
                   "unstable_noStore", "unstable_expirePath",
                   "unstable_expireTag",
                   "cacheLife", "cacheTag", "io", "refresh", "updateTag",
                   "unstable_cacheLife", "unstable_cacheTag"},
}


_REGEX_OK_AFTER = set("(,=:[!&|?{};+-*%~^")
_REGEX_OK_WORDS = {"return", "typeof", "case", "in", "of", "new", "delete",
                   "void", "instanceof", "do", "else", "yield", "await"}


def _regex_can_start(src: str, i: int) -> bool:
    j = i - 1
    while j >= 0 and src[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return True
    ch = src[j]
    if ch in _REGEX_OK_AFTER:
        return True
    if ch.isalnum() or ch in "_$":
        k = j
        while k >= 0 and (src[k].isalnum() or src[k] in "_$"):
            k -= 1
        return src[k + 1:j + 1] in _REGEX_OK_WORDS
    return False


def strip_noncode(src: str) -> str:
    """Comments and regex literals blanked; strings and offsets preserved."""
    out = list(src)
    n = len(src)
    i = 0
    stack: list = []

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]

        if stack and stack[-1] in "'\"":
            if c == "\\":
                i += 2
                continue

            if c == stack[-1] or c == "\n":
                stack.pop()
            i += 1
            continue

        if stack and stack[-1] == "`":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                stack.pop()
            elif c == "$" and i + 1 < n and src[i + 1] == "{":
                stack.append("{")
                i += 2
                continue
            i += 1
            continue

        if c == "}" and stack and stack[-1] == "{":
            stack.pop()
            i += 1
            continue

        if c == "/" and i + 1 < n:
            nxt = src[i + 1]
            if nxt == "/":
                j = src.find("\n", i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
                continue
            if nxt == "*":
                j = src.find("*/", i + 2)
                j = n if j < 0 else j + 2
                blank(i, j)
                i = j
                continue
            if _regex_can_start(src, i):
                end = _regex_end(src, i, n)
                if end > 0:
                    blank(i, end)
                    i = end
                    continue

        if c in "'\"`":
            stack.append(c)
            i += 1
            continue

        i += 1

    return "".join(out)


def _regex_end(src: str, i: int, n: int) -> int:
    """Index just past a regex literal starting at `i`, or 0 if it is not one.

    A regex never spans a line, which bounds the blast radius when JSX's
    `</div>` is mistaken for one.
    """
    j = i + 1
    in_class = False
    while j < n:
        d = src[j]
        if d == "\\":
            j += 2
            continue
        if d == "\n":
            return 0
        if d == "[":
            in_class = True
        elif d == "]":
            in_class = False
        elif d == "/" and not in_class:
            return j + 1
        j += 1
    return 0


@dataclass
class ModuleExports:
    named: set = field(default_factory=set)
    has_default: bool = False
    star_from: list = field(default_factory=list)
    named_from: dict = field(default_factory=dict)


_EXPORT_DECL_RE = re.compile(
    r"\bexport\s+(?:async\s+)?(?:function\s*\*?|class|const|let|var)\s+"
    r"([A-Za-z_$][\w$]*)")

_EXPORT_DESTRUCT_RE = re.compile(
    r"\bexport\s+(?:const|let|var)\s*([{\[])([^}\]]*)[}\]]\s*=")
_EXPORT_DEFAULT_RE = re.compile(r"\bexport\s+default\b")
_EXPORT_STAR_RE = re.compile(
    r"""\bexport\s*\*\s*(?:as\s+([A-Za-z_$][\w$]*)\s*)?from\s*['"]([^'"]+)['"]""")
_EXPORT_BLOCK_RE = re.compile(
    r"""\bexport\s*\{([^}]*)\}\s*(?:from\s*['"]([^'"]+)['"])?""")


def _clause_names(body: str) -> list:
    """`a, b as c, default as D` -> ['a', 'c', 'D'] — the *exported* names."""
    names = []
    for part in body.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(
            r"(?:[A-Za-z_$][\w$]*|default)\s+as\s+([A-Za-z_$][\w$]*)", part)
        if m:
            names.append(m.group(1))
        elif re.fullmatch(r"[A-Za-z_$][\w$]*", part) and part != "default":
            names.append(part)
    return names


def _parse_exports_one(src: str) -> ModuleExports:
    ex = ModuleExports()
    for m in _EXPORT_DECL_RE.finditer(src):
        ex.named.add(m.group(1))
    for m in _EXPORT_DESTRUCT_RE.finditer(src):
        for part in m.group(2).split(","):
            part = part.split(":")[-1].split("=")[0].strip().lstrip(". ")
            if re.fullmatch(r"[A-Za-z_$][\w$]*", part):
                ex.named.add(part)
    ex.has_default = bool(_EXPORT_DEFAULT_RE.search(src))
    for m in _EXPORT_STAR_RE.finditer(src):
        if m.group(1):
            ex.named.add(m.group(1))
        else:
            ex.star_from.append(m.group(2))
    for m in _EXPORT_BLOCK_RE.finditer(src):
        names = _clause_names(m.group(1))
        if m.group(2):
            ex.named_from.update({nm: m.group(2) for nm in names})
        else:
            ex.named.update(names)
    return ex


def parse_exports(src: str) -> ModuleExports:
    """Union of what the raw and the stripped source declare — see module doc."""
    a = _parse_exports_one(src)
    b = _parse_exports_one(strip_noncode(src))
    return ModuleExports(
        named=a.named | b.named,
        has_default=a.has_default or b.has_default,
        star_from=sorted(set(a.star_from) | set(b.star_from)),
        named_from={**b.named_from, **a.named_from},
    )


@dataclass
class ImportStmt:
    spec: str
    line: int
    names: list = field(default_factory=list)
    default: str = ""
    namespace: str = ""


_IMPORT_RE = re.compile(
    r"""\bimport\s+(?!\()([^;]*?)\s*from\s*['"]([^'"]+)['"]""", re.S)


def parse_imports(src: str) -> list:
    """Import statements, read from the stripped source only — see module doc."""
    clean = strip_noncode(src)
    out = []
    for m in _IMPORT_RE.finditer(clean):
        clause, spec = m.group(1).strip(), m.group(2)
        if "import" in clause or "'" in clause or '"' in clause:
            continue
        st = ImportStmt(spec=spec, line=clean[:m.start()].count("\n") + 1)
        block = re.search(r"\{([^}]*)\}", clause)
        if block:
            for part in block.group(1).split(","):
                part = part.strip()
                as_m = re.fullmatch(
                    r"([A-Za-z_$][\w$]*)\s+as\s+([A-Za-z_$][\w$]*)", part)
                if as_m:
                    st.names.append((as_m.group(1), as_m.group(2)))
                elif re.fullmatch(r"[A-Za-z_$][\w$]*", part):
                    st.names.append((part, part))
            clause = clause[:block.start()] + clause[block.end():]
        ns = re.search(r"\*\s*as\s+([A-Za-z_$][\w$]*)", clause)
        if ns:
            st.namespace = ns.group(1)
            clause = clause[:ns.start()] + clause[ns.end():]
        head = clause.strip().strip(",").strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", head):
            st.default = head
        out.append(st)
    return out


def _normalise(path: str) -> str:
    parts = []
    for seg in path.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in (".", ""):
            parts.append(seg)
    return "/".join(parts)


def resolve_local(importer_rel: str, spec: str, files: dict) -> str | None:
    """The project-relative path `spec` refers to, or None if unresolvable."""
    if spec.startswith("@/"):
        target = _normalise(spec[2:])
    elif spec.startswith(("./", "../")):
        target = _normalise((PurePosixPath(importer_rel).parent / spec).as_posix())
    else:
        return None
    if not target:
        return None

    for cand in (target, f"{target}.jsx", f"{target}.js",
                 f"{target}/index.jsx", f"{target}/index.js"):
        if cand in files:
            return cand
    return None


def effective_exports(rel: str, files: dict, _seen: set = None) -> set | None:
    """
    Every name `rel` exports, following re-exports transitively.

    Returns None when the surface is unknowable — an `export * from` whose
    target cannot be resolved.  Callers must treat None as "do not check this
    module", never as "exports nothing".
    """
    _seen = _seen or set()
    if rel in _seen:
        return set()
    src = files.get(rel)
    if not isinstance(src, str):
        return None
    ex = parse_exports(src)
    names = set(ex.named) | set(ex.named_from)
    for spec in ex.star_from:
        target = resolve_local(rel, spec, files)
        if target is None:
            return None
        inner = effective_exports(target, files, _seen | {rel})
        if inner is None:
            return None
        names |= inner
    return names


@dataclass
class BrokenImport:
    importer: str
    line: int
    name: str
    module: str
    spec: str
    available: list

    def close_match(self) -> str | None:
        """
        A very near neighbour, or None.

        Casing is checked exactly rather than by ratio: `getsession` vs
        `getSession` scores only 0.90 on SequenceMatcher, below any cutoff that
        is safe for semantic guesses.  Everything else needs 0.92, which is
        tight enough to reject `setSessionCookie` → `createSession` — a rename
        that would compile and then fail at runtime with the wrong behaviour.
        """
        lower = self.name.lower()
        same = [n for n in self.available if n.lower() == lower]
        if len(same) == 1:
            return same[0]
        hit = difflib.get_close_matches(self.name, self.available, n=1,
                                        cutoff=0.92)
        return hit[0] if hit else None

    def message(self) -> str:
        return (f"{self.importer}:{self.line}: imports {{ {self.name} }} from "
                f"'{self.spec}', which exports only: "
                f"{', '.join(self.available) or '(nothing)'}")


def check_named_imports(files: dict) -> list:
    """Every named import of a local module that the module does not export."""
    cache: dict = {}
    out = []
    for rel, src in sorted(files.items()):
        if not rel.endswith(CODE_SUFFIXES) or not isinstance(src, str):
            continue
        for st in parse_imports(src):
            if not st.names:
                continue
            surface = FRAMEWORK_EXPORTS.get(st.spec)
            if surface is not None:
                for imported, _local in st.names:
                    if imported not in surface:
                        out.append(BrokenImport(
                            importer=rel, line=st.line, name=imported,
                            module=st.spec, spec=st.spec,
                            available=sorted(surface)))
                continue
            if not st.spec.startswith(LOCAL_PREFIXES):
                continue
            if st.spec.endswith(SKIP_SUFFIXES):
                continue
            target = resolve_local(rel, st.spec, files)
            if target is None or not target.endswith(CODE_SUFFIXES):
                continue
            if target not in cache:
                cache[target] = effective_exports(target, files)
            avail = cache[target]
            if avail is None:
                continue
            for imported, _local in st.names:
                if imported not in avail:
                    out.append(BrokenImport(
                        importer=rel, line=st.line, name=imported,
                        module=target, spec=st.spec, available=sorted(avail)))
    return out


def group_messages(broken: list) -> list:
    """One line per (importer, module) pair, listing every missing name.

    The available-export list is the whole value of this message — it is
    precisely what `next build` can never tell anyone.
    """
    groups: dict = {}
    for b in broken:
        groups.setdefault((b.importer, b.module), []).append(b)
    out = []
    for (importer, module), items in sorted(groups.items()):
        first = items[0]
        names = ", ".join(sorted({i.name for i in items}))
        head = (f"{importer}:{first.line}: imports {{ {names} }} from "
                f"'{first.spec}', which exports only: "
                f"{', '.join(first.available) or '(nothing)'}.")
        if module in FRAMEWORK_EXPORTS:

            out.append(f"{head} Use one of those instead (NextResponse.json(…) "
                       f"is almost always what is meant).")
        else:
            out.append(f"{head} Either add the missing export to {module} or "
                       f"use one that exists — do not rename or remove the "
                       f"existing exports, other files import them.")
    return out


_SYNTAX_SCRIPT = r"""
const fs = require('fs');
const path = require('path');
const esbuild = require(process.argv[2]);
const files = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = [];
for (const rel of files) {
  let src;
  try { src = fs.readFileSync(path.join(process.argv[4], rel), 'utf8'); }
  catch (e) { continue; }
  try {
    // `jsx` for .js too: Next lets a .js file contain JSX and the generated
    // apps use both extensions for components.
    esbuild.transformSync(src, { loader: 'jsx', sourcefile: rel });
  } catch (e) {
    const first = (e.errors && e.errors[0]) || {};
    out.push({
      path: rel,
      line: (first.location && first.location.line) || 0,
      message: first.text || String(e.message || e),
    });
  }
}
process.stdout.write(JSON.stringify(out));
"""


def check_syntax(project_dir, files, node_cmd=None) -> tuple[list, str]:
    """Every generated file that is not parseable JavaScript.

    Returns `(problems, reason)`. `problems` is a list of
    `{"path", "line", "message"}`. `reason` is empty when the check actually
    ran, and says why not when it did not — "no problems" and "not checked"
    are different facts and the caller has to be able to tell them apart.
    """
    import json
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    root = Path(project_dir).resolve()
    esbuild_dir = root / "node_modules" / "esbuild"
    if not esbuild_dir.exists():
        return [], "esbuild is not installed in this project"

    node = node_cmd or shutil.which("node")
    if not node:
        return [], "node is not on PATH"

    targets = sorted(
        rel for rel in files
        if rel.endswith((".js", ".jsx")) and isinstance(files.get(rel), str)
        and not rel.startswith(("node_modules/", ".next/"))

        and not rel.endswith((".config.js", ".config.mjs"))
    )
    if not targets:
        return [], ""

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "parse.js"
        listing = Path(tmp) / "files.json"
        script.write_text(_SYNTAX_SCRIPT, encoding="utf-8")
        listing.write_text(json.dumps(targets), encoding="utf-8")
        try:
            done = subprocess.run(
                [node, str(script), str(esbuild_dir), str(listing), str(root)],
                capture_output=True, text=True, timeout=120)
        except Exception as exc:                        # noqa: BLE001
            return [], f"the parser could not be run ({exc})"

    if done.returncode != 0:
        detail = (done.stderr or "").strip().splitlines()
        return [], f"the parser failed: {detail[-1] if detail else 'no output'}"
    try:
        return json.loads(done.stdout or "[]"), ""
    except ValueError:
        return [], "the parser returned nothing readable"


def syntax_messages(problems: list) -> list:
    """One repair-ready sentence per unparseable file."""
    return [
        f"{p['path']}:{p.get('line') or 0}: {p['message']} — this file is not "
        f"valid JavaScript and nothing that imports it can compile. Fix the "
        f"syntax without changing what the file does."
        for p in problems
    ]
