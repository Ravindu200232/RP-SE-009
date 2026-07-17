"""agents/module_gate.py — the AST-ish Module Existence Gate (P2).

Resolves EVERY internal import in the generated app against the virtual generated file system
(the files actually on disk), plus classifies external imports against an approved-dependency
registry. It exists to cure "module not found" in ONE shot, before the build loop:

  - internal `@/…` and relative `./…` imports must resolve to a real generated file
    (respecting index files, `.ts`/`.tsx` extensions, and filename casing);
  - external bare packages must be on the approved list (a hallucinated package is a bug);
  - directives (`'use client'`), status words (`pending`), Next-managed generated-type imports,
    and CSS/asset imports are NEVER treated as packages.

Pure detection — the caller (orchestrator) applies deterministic import fixers or regenerates the
offending file. No LLM here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Always-available externals (Node/Next builtins) on top of whatever package.json declares.
_BUILTIN_EXTERNALS = {"react", "react-dom", "next", "node"}

# Import specifiers that are NOT modules and must never be flagged.
_NON_MODULE = {"use client", "use server", "use strict"}

_SRC_DIRS = ("app", "components", "lib", "models", "hooks", "types", "features", "constants", "styles")
_SKIP_DIRS = {"node_modules", ".next", ".locode", ".git", "dist", "build", "out"}

# import X from 'm' / import {a} from 'm' / import 'm' / export … from 'm' / import('m') / require('m')
_FROM = re.compile(r"""(?:import|export)\b[^;\n]*?\bfrom\s*['"]([^'"]+)['"]""")
_BARE = re.compile(r"""(?:^|[\n;])\s*import\s*['"]([^'"]+)['"]""")
_DYN = re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_REQ = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")


def import_specifiers(text: str) -> set[str]:
    """Every module specifier imported by this file (static, side-effect, dynamic, require)."""
    specs: set[str] = set()
    for rx in (_FROM, _BARE, _DYN, _REQ):
        for m in rx.finditer(text or ""):
            s = m.group(1).strip()
            if s and s not in _NON_MODULE:
                specs.add(s)
    return specs


def collect_valid_modules(project_dir: Path) -> set[str]:
    """The set of importable internal module specifiers, from files actually on disk.

    Each source file `components/features/menu/MenuItemTable.tsx` yields the specifiers
    `@/components/features/menu/MenuItemTable` (extension-less) AND `@/…/MenuItemTable.tsx`
    (extension-ful, so asset imports like `./globals.css` resolve); index files also map to
    their parent dir."""
    project_dir = Path(project_dir)
    valid: set[str] = set()
    for base in _SRC_DIRS:
        root = project_dir / base
        if not root.exists():
            continue
        for fp in root.rglob("*"):
            if fp.suffix not in (".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".json"):
                continue
            if any(part in _SKIP_DIRS for part in fp.parts):
                continue
            rel = fp.relative_to(project_dir).as_posix()
            valid.add("@/" + rel)                        # with extension (assets, explicit imports)
            stem = rel.rsplit(".", 1)[0]
            valid.add("@/" + stem)                       # extension-less (TS/TSX modules)
            if stem.endswith("/index"):
                valid.add("@/" + stem[:-6])              # dir import resolves to index
    return valid


def approved_externals(project_dir: Path) -> set[str]:
    """The approved external-dependency registry = the packages package.json actually declares
    (dependencies + devDependencies), plus Node/Next builtins."""
    approved = set(_BUILTIN_EXTERNALS)
    try:
        pkg = json.loads((Path(project_dir) / "package.json").read_text(encoding="utf-8"))
        approved |= set(pkg.get("dependencies", {}))
        approved |= set(pkg.get("devDependencies", {}))
    except Exception:
        pass
    return approved


def _resolve_relative(rel: str, spec: str) -> str | None:
    """Resolve a relative import from file `rel` to a canonical `@/…` module specifier."""
    here = Path(rel).parent
    target = (here / spec).as_posix()
    parts: list[str] = []
    for seg in target.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "@/" + "/".join(parts) if parts else None


def _external_ok(spec: str, approved: set[str]) -> bool:
    if spec.startswith(("@/", ".", "/")):
        return False  # not external
    if spec.endswith((".css", ".scss")):
        return True
    # package name: `@scope/name` (first two segments) or `name` (subpaths like react-icons/fi are ok)
    pkg = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
    return pkg in approved


def unresolved_imports(rel: str, text: str, valid: set[str], approved: set[str]) -> list[dict]:
    """Imports in `text` that won't resolve: internal targets that don't exist, or unapproved
    external packages. Returns [{spec, kind}] where kind in {internal, external}."""
    bad: list[dict] = []
    for spec in import_specifiers(text):
        if spec.startswith("@/"):
            if spec in valid or (spec + "/index") in valid:
                continue
            bad.append({"spec": spec, "kind": "internal"})
        elif spec.startswith("."):
            tgt = _resolve_relative(rel, spec)
            if tgt and (tgt in valid or (tgt + "/index") in valid):
                continue
            bad.append({"spec": spec, "kind": "internal"})
        else:
            if not _external_ok(spec, approved):
                bad.append({"spec": spec, "kind": "external"})
    return bad


def _norm_base(spec: str) -> str:
    """Loose basename key for matching: lowercase, strip separators, drop a trailing plural 's'
    (so `./payment-table` and `PaymentTable` both normalise to `paymenttable`)."""
    base = re.sub(r"[-_]", "", spec.rstrip("/").rsplit("/", 1)[-1].lower())
    return base[:-1] if base.endswith("s") and not base.endswith("ss") else base


def suggest_module(spec: str, valid: set[str]) -> str | None:
    """Deterministic remap for a bad internal import: if exactly ONE real module shares the loose
    basename, return its `@/…` specifier. Fixes path drift (`@/components/features/x/Foo` →
    the real `@/…/y/Foo`) and case/plural typos (`@/models/invoices` → `@/models/Invoice`)."""
    key = _norm_base(spec)
    cands = {
        v for v in valid
        if not v.endswith((".tsx", ".ts", ".css", ".scss", ".json")) and _norm_base(v) == key
    }
    if len(cands) == 1:
        return next(iter(cands))
    # a hallucinated "types/models" barrel path (`@/typed_models`, `@/model_types`, `@/entities`) that
    # imports entity DTOs → the real `@/types` barrel (which re-exports every entity).
    if (spec.startswith("@/") and "/" not in spec[2:] and "@/types" in valid
            and re.search(r"type|model|entit|dto", spec[2:], re.I)):
        return "@/types"
    return None


def _iter_source_files(project_dir: Path):
    for base in ("app", "components", "lib", "hooks", "features"):
        root = project_dir / base
        if not root.exists():
            continue
        for fp in root.rglob("*"):
            if fp.suffix in (".ts", ".tsx") and not any(p in _SKIP_DIRS for p in fp.parts):
                yield fp


def scan_project(project_dir: Path) -> dict[str, list[dict]]:
    """{rel: [unresolved imports]} for every generated source file. Empty dict == all imports resolve."""
    project_dir = Path(project_dir)
    valid = collect_valid_modules(project_dir)
    approved = approved_externals(project_dir)
    report: dict[str, list[dict]] = {}
    for fp in _iter_source_files(project_dir):
        rel = fp.relative_to(project_dir).as_posix()
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        bad = unresolved_imports(rel, text, valid, approved)
        if bad:
            report[rel] = bad
    return report


def repair_imports(project_dir: Path) -> dict[str, list[str]]:
    """Apply deterministic import remaps in place (basename/case/plural). Returns
    {rel: [specs still unresolved]} for files the caller must regenerate as a last resort."""
    project_dir = Path(project_dir)
    valid = collect_valid_modules(project_dir)
    approved = approved_externals(project_dir)
    remaining: dict[str, list[str]] = {}
    for fp in _iter_source_files(project_dir):
        rel = fp.relative_to(project_dir).as_posix()
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        bad = unresolved_imports(rel, text, valid, approved)
        if not bad:
            continue
        changed, still = False, []
        for b in bad:
            sugg = suggest_module(b["spec"], valid) if b["kind"] == "internal" else None
            if sugg and sugg != b["spec"]:
                text = (text.replace(f"'{b['spec']}'", f"'{sugg}'")
                            .replace(f'"{b["spec"]}"', f'"{sugg}"'))
                changed = True
            else:
                still.append(b["spec"])
        if changed:
            fp.write_text(text, encoding="utf-8")
        if still:
            remaining[rel] = still
    return remaining
