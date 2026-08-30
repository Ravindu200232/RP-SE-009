"""Route Checks.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    FETCH_URL_RE,
    Finding,
    HTTP_METHOD_RE,
    LINK_HREF_RE,
    ROUTER_PUSH_RE,
    parse_imports,
    re,
    resolve_local,
)

class RouteChecksMixin:
    """Keep route checks behavior together."""

    # Finds routes from the current project or runtime state and return the best matching result.
    def enumerate_routes(self):
        """Prepare the enumerate routes value or state used by this focused pipeline step."""
        root, out = self.project_dir / "app", {}
        if not root.is_dir(): return out
        for leaf, kind in (("page", "page"), ("route", "api")):
            for suffix in (".js", ".jsx"):
                for fp in sorted(root.rglob(leaf + suffix)):
                    parts = [p for p in fp.relative_to(root).parts[:-1] if not (p.startswith("(") and p.endswith(")"))]
                    url = "/" + "/".join(parts) if parts else "/"
                    if url in out: continue
                    try: body = fp.read_text("utf-8", errors="replace")
                    except OSError: body = ""
                    # From: agents/analysis/analysis_shared.py
                    out[url] = {"file": fp.relative_to(self.project_dir).as_posix(), "kind": kind, "dynamic": "[" in url, "methods": sorted(set(HTTP_METHOD_RE.findall(body))) or (["GET"] if kind == "page" else [])}
        return out

    # Inspect route-related source information for route matches and return the value or problem evidence needed by
    # route checks.
    @staticmethod
    def _route_matches(target, served):
        """Prepare the route matches value or state used by this focused pipeline step."""
        want = [x for x in target.strip("/").split("/") if x]
        for url in served:
            got = [x for x in url.strip("/").split("/") if x]
            if len(got) == len(want) and all(a == b or a.startswith("[") for a, b in zip(got, want)): return True
        return False

    # The route that really serves a URL, preferring the literal one. `/api/rooms/available` and `/api/rooms/[roomId]`
    # both match the shape `api/rooms/*`, and the dynamic folder sorts first, so a first-match lookup handed back the
    # wrong handler and reported the live GET route as unserved — a blocker that no repair could ever clear.
    @staticmethod
    def _route_for(target, routes):
        """The route that really serves a URL, preferring the literal one.

        `/api/rooms/available` and `/api/rooms/[roomId]` both match the shape
        `api/rooms/*`, and the dynamic folder sorts first, so a first-match
        lookup handed back the wrong handler and reported the live GET route as
        unserved — a blocker that no repair could ever clear.
        """
        want = str(target or "").rstrip("/") or "/"
        exact = routes.get(want) or routes.get(want + "/")
        if exact:
            return exact
        for url, meta in routes.items():
            if RouteChecksMixin._route_matches(want, [url]):
                return meta
        return None

    # Inspect the generated source for dead links problems and return evidence only when a real issue is found.
    def dead_links(self, routes=None):
        """Prepare the dead links value or state used by this focused pipeline step."""
        pages = [u for u, m in (routes or self.enumerate_routes()).items() if m["kind"] == "page"]
        dead = set()
        # From: agents/analysis/checks/scan_state.py
        for body in self.code_files().values():
            # From: agents/analysis/analysis_shared.py
            for raw in [a or b for a, b in LINK_HREF_RE.findall(body)] + ROUTER_PUSH_RE.findall(body):
                url = raw.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
                if not url.startswith("/api") and not self._route_matches(url, pages): dead.add(url)
        return sorted(dead)

    # Inspect the generated source for dead endpoints problems and return evidence only when a real issue is found.
    def dead_endpoints(self, routes=None):
        """Prepare the dead endpoints value or state used by this focused pipeline step."""
        apis = [u for u, m in (routes or self.enumerate_routes()).items() if m["kind"] == "api"]
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/scan_state.py
        return sorted({u.rstrip("/") or "/" for body in self.code_files().values() for u in FETCH_URL_RE.findall(body) if not self._route_matches(re.sub(r"\$\{[^}]+\}", "probe", u), apis)})

    # Read contract findings and return the information needed by the next step.
    def fetch_contract_findings(self, routes=None):
        """Prepare the fetch contract findings value or state used by this focused pipeline step."""
        routes, out = routes or self.enumerate_routes(), []
        # From: agents/analysis/analysis_shared.py
        call = re.compile(r"fetch\(\s*([`'\"])(/api/.+?)\1\s*(?:,\s*\{([\s\S]{0,900}?)\}\s*)?\)")
        # From: agents/analysis/checks/scan_state.py
        for rel, body in self.code_files().items():
            for _, raw, options in call.findall(body):
                # From: agents/analysis/analysis_shared.py
                url = re.sub(r"\$\{[^}]+\}", "probe", raw.split("?", 1)[0]).rstrip("/") or "/"
                # From: agents/analysis/analysis_shared.py
                method = (re.search(r"\bmethod\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", options or "", re.I) or [None, "GET"])[1].upper()
                served = self._route_for(url, routes)
                # From: agents/analysis/analysis_shared.py
                if not served: out.append(Finding("blocker", "DEAD_ENDPOINT", f"{method} {raw} has no matching API route", rel, "implement the exact called route/method or correct the caller", [rel])); continue
                # From: agents/analysis/analysis_shared.py
                if method not in served.get("methods", []): out.append(Finding("blocker", "API_METHOD_MISMATCH", f"caller sends {method} {raw}, but {served['file']} serves {', '.join(served.get('methods') or []) or 'no HTTP methods'}", rel, "make caller and handler agree on URL, method, body and identifier", [served["file"]]))
        return out

    # Check the generated source for mentions and return the small result used by the Analyzer.
    def _mentions(self, rel, seen=None):
        """Prepare the mentions value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files, seen = self.code_files(), seen if seen is not None else set()
        if rel not in files or rel in seen: return set()
        seen.add(rel); body = files[rel]
        # From: agents/analysis/analysis_shared.py
        out = {x.rstrip("/") or "/" for x in re.findall(r"[\"'`](/(?:[a-z0-9][a-z0-9/_-]*)?)(?=(?:[?#]|\$\{|[\"'`]))", body, re.I)}
        # From: agents/analysis/analysis_shared.py
        out |= {x.rstrip("/") + "/*" for x in re.findall(r"[`](/(?:[a-z0-9][a-z0-9/_-]*/))\$\{", body, re.I)}
        # From: agents/analysis/analysis_shared.py
        for stmt in parse_imports(body):
            # From: agents/analysis/analysis_shared.py
            target = resolve_local(rel, stmt.spec, files)
            if target: out |= self._mentions(target, seen)
        return out

    # Inspect the generated source for unreachable pages problems and return evidence only when a real issue is found.
    def unreachable_pages(self, routes=None):
        """Prepare the unreachable pages value or state used by this focused pipeline step."""
        pages = {u: m for u, m in (routes or self.enumerate_routes()).items() if m["kind"] == "page"}
        if "/" not in pages: return []
        shell, reached, queue = self._mentions("app/layout.jsx") | self._mentions("app/layout.js"), {"/"}, ["/"]
        while queue:
            meta = pages.get(queue.pop()) or {}
            for named in self._mentions(meta.get("file", "")) | shell:
                for url in pages:
                    dynamic_hit = named.endswith("/*") and "[" in url and url.startswith(named[:-1])
                    if (named == url or dynamic_hit or "[" in url and self._route_matches(named, [url])) and url not in reached: reached.add(url); queue.append(url)
        return sorted(set(pages) - reached)

    # Inspect route-related source information for route from page path and return the value or problem evidence
    # needed by route checks.
    @staticmethod
    def _route_from_page_path(path):
        """Prepare the route from page path value or state used by this focused pipeline step."""
        rel = str(path or "").replace("\\", "/")
        # From: agents/analysis/analysis_shared.py
        if not re.fullmatch(r"app/(?:.+/)?page\.jsx?", rel): return ""
        parts = [p for p in rel.split("/")[1:-1] if not (p.startswith("(") and p.endswith(")"))]
        return "/" + "/".join(parts) if parts else "/"
