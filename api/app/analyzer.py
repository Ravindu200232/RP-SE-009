"""JavaScript / Node service analyzer.

Walks any folder, finds Node services at any depth, classifies them as
CommonJS or ESM, and extracts exported function-like symbols using regex
heuristics (no full parser - this is a research prototype).
"""
from __future__ import annotations

import json as _json
import re
from pathlib import Path
from typing import Iterable, Literal

from .models import DiscoveredFile, FunctionInfo

# Folders we never recurse into when scanning for services or sources.
IGNORED_DIRS = {
    "node_modules", "__tests__", "tests", "test", "__mocks__",
    "dist", "build", ".next", ".nuxt", "coverage", ".git", ".cache",
    "out", "public", "static",
}

SOURCE_EXTS = {".js", ".mjs", ".cjs", ".jsx"}
TEST_FILE_PATTERNS = (".test.js", ".test.mjs", ".test.cjs", ".test.jsx",
                      ".spec.js", ".spec.mjs", ".spec.cjs", ".spec.jsx")

ModuleKind = Literal["cjs", "esm"]


# ── Service discovery ───────────────────────────────────────────────────────
def is_node_project(path: Path) -> bool:
    return (path / "package.json").is_file()


def _read_pkg(path: Path) -> dict:
    try:
        return _json.loads((path / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_workspace_root(pkg: dict) -> bool:
    return bool(pkg.get("workspaces"))


def _has_node_source(path: Path) -> bool:
    """Treat a package.json as belonging to a real service only if it has source code."""
    for entry in path.rglob("*"):
        if any(part in IGNORED_DIRS for part in entry.parts):
            continue
        if entry.is_file() and entry.suffix.lower() in SOURCE_EXTS:
            if not any(entry.name.endswith(p) for p in TEST_FILE_PATTERNS):
                return True
    return False


def discover_services(root: Path, *, max_depth: int = 6) -> list[Path]:
    """Find every Node service under `root`, at any depth, in deterministic order.

    Rules:
     - A directory is a "service" if it contains a `package.json` with at least
       one `.js`/`.mjs`/`.cjs` source file (not just a workspace root).
     - When we hit a workspace root (`"workspaces": [...]`), recurse into its
       children rather than treating the root itself as the service.
     - We never descend into node_modules, build outputs, or VCS dirs.
     - We don't double-list nested services: once we accept a folder as a
       service, we still keep walking into its children (some monorepos put
       sub-services inside a parent service folder), but we deduplicate so
       each service path appears exactly once.
    """
    if not root.is_dir():
        return []

    services: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if path in seen:
            return
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts) and path != root:
            return
        seen.add(path)

        pkg = _read_pkg(path) if is_node_project(path) else {}
        is_workspace = _is_workspace_root(pkg)

        if is_node_project(path) and not is_workspace and _has_node_source(path):
            services.append(path)
            # don't recurse into a real service's children - tests/source live here
            return

        # workspace root or a plain folder: descend
        try:
            children = sorted(p for p in path.iterdir() if p.is_dir())
        except OSError:
            return
        for child in children:
            visit(child, depth + 1)

    visit(root.resolve(), 0)
    return services


# ── Per-service classification ──────────────────────────────────────────────
def classify_service(service_root: Path) -> ModuleKind:
    """Return 'esm' if the service is an ECMAScript-module project, else 'cjs'."""
    pkg = _read_pkg(service_root)
    if pkg.get("type") == "module":
        return "esm"
    # Heuristic: if any .mjs files or top-level source uses `import ... from`
    src_dir = service_root / "src" if (service_root / "src").is_dir() else service_root
    for p in src_dir.rglob("*"):
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() == ".mjs":
            return "esm"
    return "cjs"


def classify_file(file_path: Path, fallback: ModuleKind = "cjs") -> ModuleKind:
    suffix = file_path.suffix.lower()
    if suffix == ".cjs":
        return "cjs"
    if suffix == ".mjs":
        return "esm"
    return fallback


# ── Source discovery ────────────────────────────────────────────────────────
def discover_source_files(service_root: Path) -> list[DiscoveredFile]:
    files: list[DiscoveredFile] = []
    src_dir = service_root / "src"
    base = src_dir if src_dir.is_dir() else service_root
    pkg_kind = classify_service(service_root)

    for p in _walk(base, service_root):
        if p.suffix.lower() not in SOURCE_EXTS:
            continue
        if any(p.name.endswith(pat) for pat in TEST_FILE_PATTERNS):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        # skip empty files and entry-points that are mostly server-bootstrap (often hard to unit-test)
        if size == 0:
            continue
        rel = p.relative_to(service_root).as_posix()
        files.append(
            DiscoveredFile(
                path=str(p),
                relative=rel,
                service=service_root.name,
                bytes=size,
            )
        )
    return files


def _walk(base: Path, service_root: Path) -> Iterable[Path]:
    if base.is_file():
        yield base
        return
    for entry in base.rglob("*"):
        try:
            rel_parts = entry.relative_to(service_root).parts
        except ValueError:
            rel_parts = entry.parts
        if any(part in IGNORED_DIRS for part in rel_parts):
            continue
        if entry.is_file():
            yield entry


# ── Function extraction ─────────────────────────────────────────────────────
_FUNC_DECL = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)",
    re.MULTILINE,
)
_ARROW_DECL = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?\(([^)]*)\)\s*=>",
    re.MULTILINE,
)
_ARROW_SINGLEPARAM = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?([A-Za-z_$][\w$]*)\s*=>",
    re.MULTILINE,
)
_EXPORTS_FN = re.compile(
    r"^\s*exports\.([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
    r"(?:function\s*\(([^)]*)\)|\(([^)]*)\)\s*=>|([A-Za-z_$][\w$]*)\s*=>)",
    re.MULTILINE,
)
_MODULE_EXPORTS_OBJ = re.compile(r"module\.exports\s*=\s*\{([^}]*)\}", re.DOTALL)
_MODULE_EXPORTS_NAME = re.compile(r"module\.exports\s*=\s*([A-Za-z_$][\w$]*)\s*;?")
_EXPORT_LIST = re.compile(r"^\s*export\s*\{([^}]+)\}", re.MULTILINE)
_EXPORT_DEFAULT_FN = re.compile(
    r"^\s*export\s+default\s+(?:async\s+)?function\s*([A-Za-z_$][\w$]*)?\s*\(([^)]*)\)",
    re.MULTILINE,
)


def parse_functions(source: str, kind: ModuleKind = "cjs") -> list[FunctionInfo]:
    """Extract callable, externally visible symbols from a JS source string."""
    found: dict[str, FunctionInfo] = {}

    for match in _FUNC_DECL.finditer(source):
        name = match.group(1)
        params = _split_params(match.group(2))
        found[name] = FunctionInfo(
            name=name,
            kind="function",
            params=params,
            snippet=_snippet(source, match.start()),
        )

    for match in _ARROW_DECL.finditer(source):
        name = match.group(1)
        params = _split_params(match.group(2))
        found.setdefault(
            name,
            FunctionInfo(name=name, kind="arrow", params=params, snippet=_snippet(source, match.start())),
        )

    for match in _ARROW_SINGLEPARAM.finditer(source):
        name = match.group(1)
        single = match.group(2)
        if name == single:
            continue  # `const x = x => ...` malformed
        found.setdefault(
            name,
            FunctionInfo(name=name, kind="arrow", params=[single], snippet=_snippet(source, match.start())),
        )

    for match in _EXPORTS_FN.finditer(source):
        name = match.group(1)
        params = _split_params(match.group(2) or match.group(3) or "")
        if not params and match.group(4):
            params = [match.group(4)]
        found[name] = FunctionInfo(
            name=name,
            kind="function",
            params=params,
            snippet=_snippet(source, match.start()),
        )

    for match in _EXPORT_DEFAULT_FN.finditer(source):
        name = match.group(1) or "default"
        params = _split_params(match.group(2))
        found.setdefault(
            name,
            FunctionInfo(name=name, kind="export-default", params=params, snippet=_snippet(source, match.start())),
        )

    exported = _exported_names(source, kind)
    if exported:
        kept = {n: info for n, info in found.items() if n in exported}
        if kept:
            found = kept

    # Drop conventional private helpers and ALL_CAPS constants.
    return [
        info
        for name, info in found.items()
        if not name.startswith("_") and not name.isupper()
    ]


def _exported_names(source: str, kind: ModuleKind) -> set[str]:
    names: set[str] = set()

    # CommonJS: exports.foo = ...
    for match in _EXPORTS_FN.finditer(source):
        names.add(match.group(1))

    # CommonJS: module.exports = { foo, bar: baz }
    for obj_match in _MODULE_EXPORTS_OBJ.finditer(source):
        body = obj_match.group(1)
        for token in re.split(r",|\n", body):
            token = token.strip().rstrip(",")
            if not token:
                continue
            ident = token.split(":")[0].strip()
            if re.match(r"^[A-Za-z_$][\w$]*$", ident):
                names.add(ident)

    # CommonJS: module.exports = SomeName
    for name_match in _MODULE_EXPORTS_NAME.finditer(source):
        names.add(name_match.group(1))

    # ESM: export { foo, bar }
    for list_match in _EXPORT_LIST.finditer(source):
        body = list_match.group(1)
        for token in re.split(r",|\n", body):
            token = token.strip().rstrip(",")
            if not token:
                continue
            # support `export { foo as bar }`
            parts = token.split(" as ")
            ident = parts[-1].strip()
            if re.match(r"^[A-Za-z_$][\w$]*$", ident):
                names.add(ident)

    # ESM: export function foo / export const foo / export default function foo
    for line in source.splitlines():
        m = re.match(r"\s*export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", line)
        if m:
            names.add(m.group(1))
            continue
        m = re.match(r"\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)", line)
        if m:
            names.add(m.group(1))
            continue
        m = re.match(r"\s*export\s+default\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", line)
        if m:
            names.add(m.group(1))

    return names


def _split_params(raw: str) -> list[str]:
    params: list[str] = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        p = p.split("=")[0].strip()
        if p.startswith("{") or p.startswith("["):
            params.append("opts")
            continue
        if p.startswith("..."):
            p = p[3:]
        if re.match(r"^[A-Za-z_$][\w$]*$", p):
            params.append(p)
        else:
            params.append("arg")
    return params


def _snippet(source: str, offset: int, lines: int = 3) -> str:
    start = source.rfind("\n", 0, offset) + 1
    pieces = []
    cursor = start
    for _ in range(lines):
        nl = source.find("\n", cursor)
        if nl == -1:
            pieces.append(source[cursor:])
            break
        pieces.append(source[cursor:nl])
        cursor = nl + 1
    return "\n".join(pieces).strip()
