"""Guard against refactor drift: a moved module must not leave stale imports behind.

Splitting a large module into a subpackage is easy to get half-right: the file moves
but an import that named it as a sibling keeps pointing at the old level. Python only
raises then at the moment the importing line runs, so a function-local import can sit
broken for a long time and surface as a runtime error in the middle of a user request.
These checks resolve every in-repo import statically, so the break is a failing test.
"""
from __future__ import annotations

import ast
import os
import unittest
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".next", "venv", ".venv",
             "dist", "build", "out", "site-packages"}
# Top-level Python packages that live in this repository.
LOCAL_ROOTS = {"agents", "server_modules", "qa_agent", "test"}


def _runtime_fragments() -> set[Path]:
    """Files that server_runtime.py exec's into one shared namespace.

    They deliberately carry no imports of their own -- names come from the parts
    loaded before them -- so they are not importable on their own and are read
    statically here rather than being treated as standalone modules.
    """
    tree = ast.parse((ROOT / "server_runtime.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", "") == "_RUNTIME_PARTS" for t in node.targets):
            continue
        return {ROOT / part.value for part in node.value.elts
                if isinstance(part, ast.Constant)}
    return set()


@lru_cache(maxsize=1)
def _parsed_sources() -> tuple[tuple[Path, ast.Module], ...]:
    """Every repository module, parsed once and shared by the checks below.

    os.walk prunes in place so the scan never descends into node_modules or
    .next -- walking those costs far more than parsing everything we keep.
    """
    out = []
    for folder, subfolders, filenames in os.walk(ROOT):
        subfolders[:] = [d for d in subfolders if d not in SKIP_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = Path(folder) / filename
            out.append((path, ast.parse(path.read_text(encoding="utf-8"),
                                        filename=str(path))))
    return tuple(out)


def _module_exists(target: Path) -> bool:
    """True when a dotted path resolves to either a module file or a package."""
    return target.with_suffix(".py").is_file() or (target / "__init__.py").is_file()


class ImportIntegrityTests(unittest.TestCase):
    """Every in-repo import must name a module that actually exists."""

    def test_relative_imports_resolve(self):
        """`from .x import y` must resolve against the file's own package level."""
        broken = []
        for path, tree in _parsed_sources():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue
                target = path.parent
                for _ in range(node.level - 1):
                    target = target.parent
                for segment in (node.module or "").split("."):
                    if segment:
                        target = target / segment
                if not _module_exists(target):
                    broken.append(f"{path.relative_to(ROOT)}:{node.lineno}: "
                                  f"from {'.' * node.level}{node.module or ''} import ...")
        self.assertEqual(broken, [], "unresolvable relative import(s):\n" + "\n".join(broken))

    def test_absolute_in_repo_imports_resolve(self):
        """`from agents.a.b import c` must name a module that exists on disk."""
        broken = []
        for path, tree in _parsed_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                    modules = [node.module]
                elif isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                else:
                    continue
                for module in modules:
                    head, *rest = module.split(".")
                    if head not in LOCAL_ROOTS or not rest:
                        continue
                    if not _module_exists(ROOT.joinpath(*module.split("."))):
                        broken.append(f"{path.relative_to(ROOT)}:{node.lineno}: {module}")
        self.assertEqual(broken, [], "unresolvable in-repo import(s):\n" + "\n".join(broken))

    def test_runtime_fragments_are_listed_and_present(self):
        """server_runtime.py's exec'd parts must all still exist where it expects them."""
        fragments = _runtime_fragments()
        self.assertTrue(fragments, "could not read _RUNTIME_PARTS from server_runtime.py")
        missing = sorted(str(p.relative_to(ROOT)) for p in fragments if not p.is_file())
        self.assertEqual(missing, [], f"server_runtime.py loads missing file(s): {missing}")


if __name__ == "__main__":
    unittest.main()
