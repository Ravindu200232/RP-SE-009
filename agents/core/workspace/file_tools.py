"""Read-only workspace helpers grouped by responsibility."""
import json
import re
from pathlib import Path
# Source: workspace_shared.py — imported helper(s) come from this file.
from agents.core.workspace.workspace_shared import _clean, _import_specs

class WorkspaceFileToolsMixin:
    # Read file in the format expected by the next pipeline steps.
    def read_file(self, rel: str) -> str:
        """Read file in the standard shape used by the rest of the pipeline."""
        # From: agents/core/workspace/workspace_shared.py
        rel = _clean(rel)
        if not rel or ".." in Path(rel).parts:
            return "refused unsafe path"
        body = self.files.get(rel)
        if body is None:
            return f"not found: {rel}"
        return f"--- {rel} COMPLETE ---\n{str(body)[:18000]}"

    # Search current source files for a literal or regular-expression pattern.
    def search_code(self, query: str) -> str:
        """Search current source files for a literal or regular-expression pattern."""
        q = str(query or "").strip()
        if not q:
            return "empty search"
        try:
            rx = re.compile(q, re.I)
        except re.error:
            rx = re.compile(re.escape(q), re.I)
        rows = []
        for rel, body in sorted(self.files.items()):
            if not rel.startswith(("app/", "components/", "lib/", "tests/")):
                continue
            for n, line in enumerate(str(body or "").splitlines(), 1):
                if rx.search(line):
                    rows.append(f"{rel}:{n}: {line.strip()[:260]}")
                    if len(rows) >= 80:
                        return "\n".join(rows)
        return "\n".join(rows) or "no matches"

    # List source files that match the requested folder or extension filters.
    def list_files(self, prefix: str) -> str:
        """List source files that match the requested folder or extension filters."""
        # From: agents/core/workspace/workspace_shared.py
        prefix = _clean(prefix)
        if ".." in Path(prefix or ".").parts:
            return "refused unsafe prefix"
        rows = [p for p in sorted(self.files) if not prefix or p.startswith(prefix)]
        return "\n".join(rows[:200]) or "no files"

    # Resolves a browser/API route to the source file that owns it.
    def route_source(self, route: str) -> str:
        """Resolve a browser/API route to the source file that owns it."""
        route = str(route or "").strip().split("?", 1)[0]
        if not route.startswith("/"):
            return "route must start with /"
        clean = route.rstrip("/") or "/"
        api = clean.startswith("/api/")
        segs = [s for s in (clean[5:] if api else clean.strip("/")).split("/") if s]
        prefix, leaf = ("app/api", "route.js") if api else ("app", "page.jsx")
        candidates = []
        if not segs and not api:
            candidates.extend(["app/page.jsx", "app/page.js"])
        else:
            stem = prefix + "/" + "/".join(segs)
            candidates.extend([stem + "/" + leaf])
            if leaf.endswith("jsx"):
                candidates.append(stem + "/page.js")
        for rel in candidates:
            if rel in self.files:
                return f"{clean} -> {rel}\n{str(self.files[rel])[:12000]}"
        # Try matching routes with variable path parts.
        endings = ("/route.js",) if api else ("/page.jsx", "/page.js")
        for rel in sorted(self.files):
            if not rel.startswith(prefix + "/") or not rel.endswith(endings):
                continue
            middle = rel[len(prefix) + 1:]
            middle = re.sub(r"/(?:page\.jsx|page\.js|route\.js)$", "", middle)
            parts = [p for p in middle.split("/") if not (p.startswith("(") and p.endswith(")"))]
            if len(parts) != len(segs):
                continue
            if all(a == b or (a.startswith("[") and a.endswith("]")) for a, b in zip(parts, segs)):
                return f"{clean} -> {rel}\n{str(self.files[rel])[:12000]}"
        return f"no source mapped for {clean}"

    # Returns files that directly import the selected source file.
    def importers(self, target: str) -> str:
        """Return files that directly import the selected source file."""
        # From: agents/core/workspace/workspace_shared.py
        target = _clean(target)
        stem = re.sub(r"\.(?:jsx?|mjs)$", "", target)
        aliases = {"@/" + stem, "@/" + target}
        rows = []
        for rel, body in sorted(self.files.items()):
            # From: agents/core/workspace/workspace_shared.py
            for spec in _import_specs(str(body or "")):
                if spec in aliases or spec.rstrip("/") == "@/" + stem:
                    rows.append(rel)
                    break
                if spec.startswith("."):
                    base = Path(rel).parent
                    # From: agents/core/workspace/workspace_shared.py
                    resolved = _clean(str(base / spec))
                    resolved = re.sub(r"\.(?:jsx?|mjs)$", "", resolved)
                    if resolved == stem:
                        rows.append(rel)
                        break
        return "\n".join(rows[:100]) or f"no importers found for {target}"

    # Resolves local spec in the format expected by the next pipeline steps.
    def _resolve_local_spec(self, importer: str, spec: str) -> str:
        """Resolve local spec in the standard shape used by the rest of the pipeline."""
        if spec.startswith("@/"):
            base = spec[2:]
        elif spec.startswith("."):
            # From: agents/core/workspace/workspace_shared.py
            base = _clean(str(Path(importer).parent / spec))
        else:
            return ""
        for rel in (base, base + ".jsx", base + ".js", base + ".mjs",
                    base + ".tsx", base + ".ts", base + ".css",
                    base + "/index.jsx", base + "/index.js",
                    base + "/index.tsx", base + "/index.ts"):
            if rel in self.files:
                return rel
        return ""

