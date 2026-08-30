"""Dependency Manager for the application builder.

The methods in this file share one easy-to-find responsibility.
"""
from __future__ import annotations

# Source: builder_shared.py — shared builder constants and helper imports.
from agents.planner.builder.builder_shared import (
    KNOWN_DEPENDENCIES,
    Path,
    json,
    os,
)

class DependencyManagerMixin:
    """Keep dependency manager behavior in one place."""

    # Returns third-party package names imported by generated source files.
    @classmethod
    def imported_packages(cls, content: str) -> list[str]:
        """Return third-party package names imported by generated source files."""
        out = []
        for spec in cls.IMPORT_SPEC_RE.findall(content or ""):
            if spec.startswith((".", "/", "@/", "node:")) or spec.startswith("next/"):
                continue
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            if name not in cls.NODE_BUILTINS and name not in cls.PREINSTALLED and cls.PKG_NAME_RE.match(name) and name not in out:
                out.append(name)
        return out

    # Returns imported packages that are still missing from package.json or node_modules.
    def unresolved_packages(self) -> list[str]:
        """Return imported packages that are still missing from package.json or node_modules."""
        try:
            # From: agents/planner/builder/builder_shared.py
            package = json.loads((self.project_dir / "package.json").read_text(encoding="utf-8"))
        except Exception:
            package = {}
        declared = set(package.get("dependencies") or {}) | set(package.get("devDependencies") or {})
        modules = self.project_dir / "node_modules"
        # From: agents/planner/builder/builder_setup.py
        used = {name for path, body in self.files.items() if self.is_source(path)
                for name in self.imported_packages(body)}
        return sorted(name for name in used if name not in declared or not (modules / name / "package.json").exists())

    # Synchronizes dependencies.
    def sync_dependencies(self) -> int:
        """Synchronize dependencies safely without changing unrelated project behavior."""
        path = self.project_dir / "package.json"
        try:
            # From: agents/planner/builder/builder_shared.py
            package = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        dependencies, added = package.setdefault("dependencies", {}), []
        for file, body in self.files.items():
            # From: agents/planner/builder/builder_setup.py
            if not self.is_source(file):
                continue
            for name in self.imported_packages(body):
                if name not in dependencies and name in KNOWN_DEPENDENCIES:
                    dependencies[name], added = KNOWN_DEPENDENCIES[name], added + [name]
        if added:
            # From: agents/planner/builder/builder_shared.py
            text = json.dumps(package, indent=2) + "\n"
            path.write_text(text, encoding="utf-8")
            self.files["package.json"] = text
            self._log("INFO", "   📦 Declared " + ", ".join(added))
        return len(added)

    # Installs packages.
    def install_packages(self, names: list[str]) -> list[str]:
        """Install packages safely without changing unrelated project behavior."""
        names = list(dict.fromkeys(name for name in names if self.PKG_NAME_RE.match(name)))
        if not names:
            return []
        result = self.cmd.run("npm install " + " ".join(names))
        return names if result.ok else []

    # Installs planned deps.
    def install_planned_deps(self) -> int:
        """Install planned deps safely without changing unrelated project behavior."""
        names = [item.get("name") if isinstance(item, dict) else item for item in self.plan.get("dependencies") or []]
        unknown = [str(name) for name in names if name and name not in KNOWN_DEPENDENCIES and name not in self.PREINSTALLED]
        return len(self.install_packages(unknown))

    # Installs unresolved.
    def install_unresolved(self) -> int:
        """Install unresolved safely without changing unrelated project behavior."""
        return len(self.install_packages(self.unresolved_packages()))

    # Extracts package names explicitly requested in a model command block.
    def packages_named_in(self, text: str) -> list[str]:
        """Extract package names explicitly requested in a model command block."""
        out = []
        for spec in self.UNRESOLVED_RE.findall(text or ""):
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            if self.PKG_NAME_RE.match(name) and name not in out:
                out.append(name)
        return out

    # Resolves import in the format expected by the next pipeline steps.
    def _resolve_import(self, owner: str, spec: str) -> bool:
        """Resolve import in the standard shape used by the rest of the pipeline."""
        if spec.startswith("@/"):
            base = spec[2:]
        elif spec.startswith("."):
            # From: agents/planner/builder/builder_shared.py
            base = os.path.normpath(str(Path(owner).parent / spec)).replace("\\", "/")
        else:
            return True
        return any(candidate in self.files or (self.project_dir / candidate).is_file()
                   for candidate in (base, base + ".js", base + ".jsx", base + "/index.js", base + "/index.jsx"))

    # Repairs missing imports.
    def repair_missing_imports(self) -> int:
        """Repair missing imports safely without changing unrelated project behavior."""
        missing = []
        for owner, body in self.files.items():
            if not owner.endswith((".js", ".jsx")):
                continue
            for spec in self.LOCAL_IMPORT_RE.findall(body) + ["@/" + value for value in self.ALIAS_IMPORT_RE.findall(body)]:
                if not self._resolve_import(owner, spec):
                    missing.append(f"{owner} imports {spec}")
        if not missing:
            return 0
        # From: agents/planner/builder/build_tasks.py
        return self._run_write_loop(
            "Resolve these missing local imports using approved file-plan paths. Create a planned file when absent or correct the importing file.\n"
            + "\n".join("- " + item for item in dict.fromkeys(missing)))
