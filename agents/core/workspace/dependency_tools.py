"""Read-only workspace helpers grouped by responsibility."""
import json
import re
from pathlib import Path
# Source: workspace_shared.py — imported helper(s) come from this file.
from agents.core.workspace.workspace_shared import _clean, _import_specs

class WorkspaceDependencyToolsMixin:
    # Follow local imports to build the connected source neighborhood for a file set.
    def dependency_closure(self, target: str) -> str:
        """Follow local imports to build the connected source neighborhood for a file set."""
        # From: agents/core/workspace/workspace_shared.py
        root = _clean(target)
        if root not in self.files:
            return f"not found: {root}"
        queue = [(root, 0)]
        seen, rows = set(), []
        while queue and len(seen) < 24:
            rel, depth = queue.pop(0)
            if rel in seen or depth > 2:
                continue
            seen.add(rel)
            body = str(self.files.get(rel) or "")
            # From: agents/core/workspace/file_tools.py
            # From: agents/core/workspace/workspace_shared.py
            local = [self._resolve_local_spec(rel, x) for x in _import_specs(body)]
            local = [x for x in local if x]
            rows.append(f"{'  '*depth}{rel} -> {', '.join(local) if local else '(no local imports)'}")
            queue.extend((child, depth + 1) for child in local)
        return "\n".join(rows)

    # Finds the file that handles one API address.
    def _route_file_for_api(self, url: str) -> str:
        """Find the file that handles one API address."""
        clean = str(url or "").split("?", 1)[0].rstrip("/") or "/"
        if not clean.startswith("/api/"):
            return ""
        segs = [x for x in clean[len("/api/"):].split("/") if x]
        for rel in sorted(self.files):
            if not rel.startswith("app/api/") or not rel.endswith(("/route.js", "/route.ts")):
                continue
            mid = re.sub(r"/route\.(?:js|ts)$", "", rel[len("app/api/"):])
            parts = [x for x in mid.split("/") if x]
            if len(parts) != len(segs):
                continue
            if all(a == b or (a.startswith("[") and a.endswith("]"))
                   for a, b in zip(parts, segs)):
                return rel
        return ""

    # Extracts literal /api/... URLs referenced by the selected source files.
    @staticmethod
    def _api_literals(body: str) -> set[str]:
        """Extract literal /api/... URLs referenced by the selected source files."""
        return set(re.findall(r"['\"](/api/[A-Za-z0-9_./\[\]-]+(?:\?[^'\"]*)?)['\"]",
                              str(body or "")))

    # Extracts MongoDB collection names referenced by the selected source files.
    @staticmethod
    def _collection_names(body: str) -> set[str]:
        """Extract MongoDB collection names referenced by the selected source files."""
        text = str(body or "")
        out = set(re.findall(r"getCollection\(\s*['\"]([^'\"]+)['\"]", text))
        # From: agents/planner/builder/project_memory.py
        out.update(re.findall(r"\.collection\(\s*['\"]([^'\"]+)['\"]", text))
        return {x for x in out if x and len(x) < 100}

    # Finds source files connected to the selected files.
    def dependency_paths(self, targets, *, max_depth: int = 3,
                         cap: int = 32) -> list[str]:
        """Find source files connected to the selected files."""
        files = self.files
        source_ext = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".css")
        roots = ("app/", "components/", "lib/", "src/", "hooks/", "utils/",
                 "services/", "store/", "stores/")
        source = {p: str(b or "") for p, b in files.items()
                  if p.startswith(roots) and p.endswith(source_ext)}
        if not source:
            return []

        imports = {p: set() for p in source}
        importers = {p: set() for p in source}
        for rel, body in source.items():
            # From: agents/core/workspace/workspace_shared.py
            for spec in _import_specs(body):
                # From: agents/core/workspace/file_tools.py
                child = self._resolve_local_spec(rel, spec)
                if child in source:
                    imports[rel].add(child)
                    importers[child].add(rel)

        api_edges = {p: set() for p in source}
        for rel, body in source.items():
            for url in self._api_literals(body):
                handler = self._route_file_for_api(url)
                if handler in source and handler != rel:
                    api_edges[rel].add(handler)
                    api_edges[handler].add(rel)

        by_collection = {}
        for rel, body in source.items():
            for name in self._collection_names(body):
                by_collection.setdefault(name, set()).add(rel)
        data_edges = {p: set() for p in source}
        for group in by_collection.values():
            if len(group) > 12:
                continue
            for rel in group:
                data_edges[rel].update(group - {rel})

        seeds = []
        for raw in targets if isinstance(targets, (list, tuple, set)) else [targets]:
            # From: agents/core/workspace/workspace_shared.py
            rel = _clean(raw)
            if rel in source and rel not in seeds:
                seeds.append(rel)
        if not seeds:
            return []

        queue = [(p, 0) for p in seeds]
        seen, out = set(), []
        while queue and len(out) < max(1, int(cap or 32)):
            rel, depth = queue.pop(0)
            if rel in seen or rel not in source or depth > max_depth:
                continue
            seen.add(rel)
            out.append(rel)
            if depth >= max_depth:
                continue
            near = set(imports.get(rel, ())) | set(importers.get(rel, ()))
            near |= set(api_edges.get(rel, ())) | set(data_edges.get(rel, ()))
            # Show direct imports first and keep the rest in a stable order.
            ranked = list(imports.get(rel, ()))
            ranked += sorted(near - set(ranked))
            queue.extend((child, depth + 1) for child in ranked if child not in seen)
        return out

    # Builds a bounded source neighborhood around the evidence files for repair.
    def dependency_neighborhood(self, target: str) -> str:
        """Build a bounded source neighborhood around the evidence files for repair."""
        paths = self.dependency_paths([target], max_depth=3, cap=32)
        if not paths:
            # From: agents/core/workspace/workspace_shared.py
            return f"not found: {_clean(target)}"
        rows = []
        for i, rel in enumerate(paths):
            tag = "root" if i == 0 else "connected"
            rows.append(f"{tag}: {rel}")
        return "\n".join(rows)

    # Returns test files associated with the selected production source files.
    def tests_for(self, target: str) -> str:
        """Return test files associated with the selected production source files."""
        # From: agents/core/workspace/workspace_shared.py
        target = _clean(target)
        stem = re.sub(r"\.(?:jsx?|mjs)$", "", target)
        base = Path(stem).name.lower()
        rows = []
        for rel, body in sorted(self.files.items()):
            if not rel.startswith("tests/"):
                continue
            low = str(body or "").lower()
            if target.lower() in low or ("@/" + stem).lower() in low or base in Path(rel).name.lower():
                rows.append(rel)
        return "\n".join(rows[:80]) or f"no generated tests found for {target}"

    # Builds a route-to-source-file map for the current generated application.
    def route_map(self, prefix: str = "/") -> str:
        """Build a route-to-source-file map for the current generated application."""
        prefix = str(prefix or "/").strip() or "/"
        rows = []
        for rel in sorted(self.files):
            route = kind = ""
            if rel in ("app/page.jsx", "app/page.js"):
                route, kind = "/", "page"
            elif rel.startswith("app/") and rel.endswith(("/page.jsx", "/page.js")):
                mid = re.sub(r"/page\.jsx?$", "", rel[4:])
                parts = [x for x in mid.split("/") if not (x.startswith("(") and x.endswith(")"))]
                route, kind = "/" + "/".join(parts), "page"
            elif rel.startswith("app/api/") and rel.endswith("/route.js"):
                route, kind = "/api/" + rel[len("app/api/"):-len("/route.js")], "api"
            if route and route.startswith(prefix):
                rows.append(f"{route} -> {rel} ({kind})")
        return "\n".join(rows[:200]) or f"no routes under {prefix}"

    # Plan query in the format expected by the next pipeline steps.
    def plan_query(self, query: str) -> str:
        """Plan query in the standard shape used by the rest of the pipeline."""
        plan = getattr(self.arch, "plan", None) or {}
        md = str(getattr(self.arch, "plan_md", "") or "")
        q = str(query or "").strip().lower()
        compact = json.dumps({
            "capabilities": plan.get("capabilities") or [],
            "workflows": plan.get("workflows") or [],
            "contracts": plan.get("contracts") or [],
            "phases": plan.get("phases") or [],
        }, ensure_ascii=False, indent=2)
        text = compact + "\n\n" + md
        if not q or q == "current":
            return text[:18000]
        rows = [line for line in text.splitlines() if q in line.lower()]
        return "\n".join(rows[:160]) or "no matching plan lines"

