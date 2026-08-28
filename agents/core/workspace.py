"""Gives agents safe, read-only access to the current project."""
from __future__ import annotations

import json
import re
from pathlib import Path

TOOL_HELP = r"""
AGENTIC WORKSPACE TOOLS — use them only when current context is insufficient.
Ask for at most four read-only tools in one turn, one tag per line.  AgentForge
will return the observations and you continue the SAME task.  Do not repeat an
identical request.

<read_file path="app/cart/page.jsx"/>
<search_code query="stock_quantity"/>
<list_files prefix="components/"/>
<route_source path="/products/123"/>
<importers path="components/ProductCard.jsx"/>
<dependency_closure path="app/checkout/page.jsx"/>
<dependency_neighborhood path="app/checkout/page.jsx"/>
<tests_for path="components/ProductCard.jsx"/>
<route_map prefix="/"/>
<plan_query query="checkout"/>

After the observations, make the smallest complete change.  Never ask the user
to copy a file that these tools can inspect.
"""

_TAGS = {
    "read_file": re.compile(r"<read_file\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "search_code": re.compile(r"<search_code\s+query=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "list_files": re.compile(r"<list_files\s+prefix=[\"']([^\"']*)[\"']\s*/?>", re.I),
    "route_source": re.compile(r"<route_source\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "importers": re.compile(r"<importers\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "dependency_closure": re.compile(r"<dependency_closure\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "dependency_neighborhood": re.compile(r"<dependency_neighborhood\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "tests_for": re.compile(r"<tests_for\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "route_map": re.compile(r"<route_map\s+prefix=[\"']([^\"']*)[\"']\s*/?>", re.I),
    "plan_query": re.compile(r"<plan_query\s+query=[\"']([^\"']+)[\"']\s*/?>", re.I),
}

_IMPORT_RE = re.compile(r"(?:from\s+|import\s*\(\s*)['\"]([^'\"]+)['\"]")
_SIDE_EFFECT_IMPORT_RE = re.compile(
    r"(?:^|[;\n])\s*import\s*['\"]([^'\"]+)['\"]", re.M)


def _import_specs(body: str) -> list[str]:
    specs = list(_IMPORT_RE.findall(str(body or "")))
    specs.extend(_SIDE_EFFECT_IMPORT_RE.findall(str(body or "")))
    return list(dict.fromkeys(specs))



def _clean(value: str) -> str:
    value = str(value or "").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


class WorkspaceTools:
    def __init__(self, arch):
        self.arch = arch
        self.project_dir = Path(getattr(arch, "project_dir", "."))
        self.cache = getattr(arch, "_workspace_tool_cache", None)
        if self.cache is None:
            self.cache = {}
            setattr(arch, "_workspace_tool_cache", self.cache)

    @property
    def files(self) -> dict:
        return getattr(self.arch, "files", None) or {}

    def requests(self, reply: str) -> list[tuple[str, str]]:
        hits = []
        text = str(reply or "")
        for name, rx in _TAGS.items():
            for m in rx.finditer(text):
                hits.append((m.start(), name, m.group(1)))
        hits.sort(key=lambda x: x[0])
        return [(name, arg) for _, name, arg in hits[:4]]

    def serve(self, reply: str, *, max_calls: int = 4) -> tuple[str, int]:
        out, used = [], 0
        for name, arg in self.requests(reply)[:max_calls]:
            key = f"{name}::{arg}".lower()
            if key in self.cache:
                out.append(f"### {name} {arg}\n(refused: exact tool request already served; use the observation already in context)")
                continue
            body = self.run(name, arg)
            self.cache[key] = body
            used += 1
            out.append(f"### {name} {arg}\n{body}")
        return ("\n\n".join(out), used)

    def run(self, name: str, arg: str) -> str:
        name = name.lower().strip()
        if name == "read_file":
            return self.read_file(arg)
        if name == "search_code":
            return self.search_code(arg)
        if name == "list_files":
            return self.list_files(arg)
        if name == "route_source":
            return self.route_source(arg)
        if name == "importers":
            return self.importers(arg)
        if name == "dependency_closure":
            return self.dependency_closure(arg)
        if name == "dependency_neighborhood":
            return self.dependency_neighborhood(arg)
        if name == "tests_for":
            return self.tests_for(arg)
        if name == "route_map":
            return self.route_map(arg)
        if name == "plan_query":
            return self.plan_query(arg)
        return f"unknown workspace tool: {name}"

    def read_file(self, rel: str) -> str:
        rel = _clean(rel)
        if not rel or ".." in Path(rel).parts:
            return "refused unsafe path"
        body = self.files.get(rel)
        if body is None:
            return f"not found: {rel}"
        return f"--- {rel} COMPLETE ---\n{str(body)[:18000]}"

    def search_code(self, query: str) -> str:
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

    def list_files(self, prefix: str) -> str:
        prefix = _clean(prefix)
        if ".." in Path(prefix or ".").parts:
            return "refused unsafe prefix"
        rows = [p for p in sorted(self.files) if not prefix or p.startswith(prefix)]
        return "\n".join(rows[:200]) or "no files"

    def route_source(self, route: str) -> str:
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

    def importers(self, target: str) -> str:
        target = _clean(target)
        stem = re.sub(r"\.(?:jsx?|mjs)$", "", target)
        aliases = {"@/" + stem, "@/" + target}
        rows = []
        for rel, body in sorted(self.files.items()):
            for spec in _import_specs(str(body or "")):
                if spec in aliases or spec.rstrip("/") == "@/" + stem:
                    rows.append(rel)
                    break
                if spec.startswith("."):
                    base = Path(rel).parent
                    resolved = _clean(str(base / spec))
                    resolved = re.sub(r"\.(?:jsx?|mjs)$", "", resolved)
                    if resolved == stem:
                        rows.append(rel)
                        break
        return "\n".join(rows[:100]) or f"no importers found for {target}"

    def _resolve_local_spec(self, importer: str, spec: str) -> str:
        if spec.startswith("@/"):
            base = spec[2:]
        elif spec.startswith("."):
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

    def dependency_closure(self, target: str) -> str:
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
            local = [self._resolve_local_spec(rel, x) for x in _import_specs(body)]
            local = [x for x in local if x]
            rows.append(f"{'  '*depth}{rel} -> {', '.join(local) if local else '(no local imports)'}")
            queue.extend((child, depth + 1) for child in local)
        return "\n".join(rows)

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

    @staticmethod
    def _api_literals(body: str) -> set[str]:
        return set(re.findall(r"['\"](/api/[A-Za-z0-9_./\[\]-]+(?:\?[^'\"]*)?)['\"]",
                              str(body or "")))

    @staticmethod
    def _collection_names(body: str) -> set[str]:
        text = str(body or "")
        out = set(re.findall(r"getCollection\(\s*['\"]([^'\"]+)['\"]", text))
        out.update(re.findall(r"\.collection\(\s*['\"]([^'\"]+)['\"]", text))
        return {x for x in out if x and len(x) < 100}

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
            for spec in _import_specs(body):
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

    def dependency_neighborhood(self, target: str) -> str:
        paths = self.dependency_paths([target], max_depth=3, cap=32)
        if not paths:
            return f"not found: {_clean(target)}"
        rows = []
        for i, rel in enumerate(paths):
            tag = "root" if i == 0 else "connected"
            rows.append(f"{tag}: {rel}")
        return "\n".join(rows)

    def tests_for(self, target: str) -> str:
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

    def route_map(self, prefix: str = "/") -> str:
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

    def plan_query(self, query: str) -> str:
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
