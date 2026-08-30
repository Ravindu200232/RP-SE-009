"""Reads imports and exports from local JavaScript files."""
# Source: import_rules.py — imported helper(s) come from this file.
from agents.core.imports.import_rules import *

# Returns the public names from an export list.
def _clause_names(body: str) -> list:
    """Return the public names from an export list."""
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


# Read exports one in the format expected by the next pipeline steps.
def _parse_exports_one(src: str) -> ModuleExports:
    """Read exports one in the standard shape used by the rest of the pipeline."""
    # From: agents/core/imports/import_rules.py
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


# Read every export while avoiding false matches in comments.
def parse_exports(src: str) -> ModuleExports:
    """Read every export while avoiding false matches in comments."""
    a = _parse_exports_one(src)
    # From: agents/core/imports/import_rules.py
    b = _parse_exports_one(strip_noncode(src))
    # From: agents/core/imports/import_rules.py
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


# Import lists can continue on the next line.
_IMPORT_RE = re.compile(
    r"""\bimport\s+(?!\()((?:(?!\bimport\b)[^;])*?)\s*from\s*['"]([^'"]+)['"]""",
    re.S)


# Read import statements while ignoring commented code.
def parse_imports(src: str) -> list:
    """Read import statements while ignoring commented code."""
    # From: agents/core/imports/import_rules.py
    clean = strip_noncode(src)
    out = []
    for m in _IMPORT_RE.finditer(clean):
        clause, spec = m.group(1).strip(), m.group(2)
        if "import" in clause or "'" in clause or '"' in clause:
            continue
        # From: agents/data/database_server.py
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
            # From: agents/data/database_server.py
            clause = clause[:block.start()] + clause[block.end():]
        ns = re.search(r"\*\s*as\s+([A-Za-z_$][\w$]*)", clause)
        if ns:
            st.namespace = ns.group(1)
            # From: agents/data/database_server.py
            clause = clause[:ns.start()] + clause[ns.end():]
        head = clause.strip().strip(",").strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", head):
            st.default = head
        out.append(st)
    return out


# Normalize a relative import path by resolving dot and parent segments into one stable path form used by import
# checks.
def _normalise(path: str) -> str:
    """Convert current step in the standard shape used by the rest of the pipeline."""
    parts = []
    for seg in path.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in (".", ""):
            parts.append(seg)
    return "/".join(parts)


# Finds the local file named by an import.
def resolve_local(importer_rel: str, spec: str, files: dict) -> str | None:
    """Find the local file named by an import."""
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


# Collect exports from this file and any files it re-exports. Return ``None`` when the full list cannot be known
# safely.
def effective_exports(rel: str, files: dict, _seen: set = None) -> set | None:
    """Collect exports from this file and any files it re-exports.

    Return ``None`` when the full list cannot be known safely.
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

__all__ = [name for name in globals() if not name.startswith("__")]
