"""Focused routes responsibilities for TesterAgent."""
from agents.build.tester_common import *


class TesterAgentRoutesMixin:
    def _discover_routes(self) -> list:
        """
        URL paths the app claims to serve, read off the generated tree.

        Dynamic segments (`[id]`, `[...slug]`) are skipped — without knowing a
        real id they would only produce misleading 404s. Route groups
        (`(marketing)`) contribute no URL segment.
        """
        if self.stack != "next":
            return []
        app_dir = Path(self.project_dir) / "app"
        if not app_dir.is_dir():
            return []
        routes = []
        for fp in sorted(app_dir.rglob("page.js")) + sorted(app_dir.rglob("page.jsx")):
            parts = fp.relative_to(app_dir).parts[:-1]
            if any(p.startswith("[") for p in parts):
                continue
            segs = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
            path = "/" + "/".join(segs)
            if path != "/" and path not in routes:
                routes.append(path)
        routes = routes[:self.MAX_EXTRA_ROUTES]

        # One API route, because no page can speak for it.
        if (app_dir / "api" / "auth" / "[...all]" / "route.js").is_file():
            routes.append("/api/auth/get-session")
        return routes

    def _discover_dynamic_routes(self) -> list:
        """Dynamic App Router page patterns present on disk.

        These cannot be probed with the literal ``[id]`` path.  They become
        testable once a rendered list/detail page gives us a concrete href.
        Route groups disappear from the URL; catch-all segments are supported.
        """
        if self.stack != "next":
            return []
        app_dir = Path(self.project_dir) / "app"
        if not app_dir.is_dir():
            return []
        out = []
        for fp in sorted(app_dir.rglob("page.js")) + sorted(app_dir.rglob("page.jsx")):
            parts = fp.relative_to(app_dir).parts[:-1]
            if not any(p.startswith("[") for p in parts):
                continue
            segs = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
            route = "/" + "/".join(segs)
            if route not in out:
                out.append(route)
        return out

    @staticmethod
    def _dynamic_pattern_re(pattern: str):
        """Compile a Next App Router dynamic path into a concrete URL matcher."""
        parts = [p for p in (pattern or "").strip("/").split("/") if p]
        rx = "^"
        for part in parts:
            if part.startswith("[[...") and part.endswith("]]" ):
                rx += r"(?:/.*)?"
            elif part.startswith("[...") and part.endswith("]"):
                rx += r"/.+"
            elif part.startswith("[") and part.endswith("]"):
                rx += r"/[^/]+"
            else:
                rx += "/" + re.escape(part)
        return re.compile(rx + r"/?$")

    def _dynamic_pattern_for(self, href: str) -> str:
        path = urlparse(href or "").path or "/"
        for pattern in self._discover_dynamic_routes():
            try:
                if self._dynamic_pattern_re(pattern).match(path):
                    return pattern
            except re.error:
                continue
        return ""

    def _harvest_dynamic_links(self, page, origin: str):
        """Remember real links in the DOM that exercise a dynamic page.

        A record list already knows the only id worth testing.  Reading its href
        is safer than inventing an ObjectId and catches the exact class where the
        detail page exists but compares a URL string to a Mongo ObjectId.
        """
        try:
            landed = urlparse(page.url).path or "/"
        except Exception:
            landed = origin
        if origin and landed.rstrip("/") != origin.rstrip("/"):
            return
        try:
            hrefs = page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.getAttribute('href')).filter(Boolean)")
        except Exception:
            return
        known = {(x.get("href"), x.get("pattern")) for x in self._runtime_dynamic_links}
        for href in hrefs or []:
            href = str(href).strip()
            if not href.startswith("/") or href.startswith(("/_next", "/api/", "/generated/")):
                continue
            pattern = self._dynamic_pattern_for(href)
            if not pattern or (href, pattern) in known:
                continue
            self._runtime_dynamic_links.append(
                {"origin": origin or landed, "href": href, "pattern": pattern})
            known.add((href, pattern))

    def _probe_dynamic_links(self, page):
        """Yield concrete dynamic links discovered during the static sweep."""
        seen = set()
        for item in self._runtime_dynamic_links[:24]:
            href = item.get("href") or ""
            pattern = item.get("pattern") or ""
            if not href or href in seen:
                continue
            seen.add(href)
            url = self.base_url + href
            try:
                resp = page.goto(url, timeout=self.cfg["goto_timeout"], wait_until="load")
                if resp is None:
                    status, detail = self._no_response(page, urlparse(href).path or href)
                else:
                    status = resp.status
                    detail = "" if status < 400 else self._body_text(page)
                overlay = ""
                if status is None or status < 400:
                    overlay = self._overlay_error(page)
                if status is not None:
                    elog("INFO", f"   {href} [{pattern}] → HTTP {status}")
                if (status == 404 or (status is not None and status >= 500) or overlay):
                    self._collect_mcp(href)
                yield href, status, detail, overlay, pattern, item.get("origin") or ""
            except Exception as e:
                detail = f"{type(e).__name__}: {e}"[:300]
                self._collect_mcp(href)
                yield href, None, detail, "", pattern, item.get("origin") or ""

    def _collect_mcp(self, route: str):
        """
        Ask the dev server what it thinks just broke, while we are still on it.

        Next 16.2+ serves `/_next/mcp`, whose `get_errors` returns structured,
        source-mapped errors — file, line, column, per URL — instead of the
        terminal text AgentForge otherwise has to pattern-match.

        Two measured constraints shape this:
          * it refuses without a live browser session, and Playwright here is
            the only one AgentForge ever has;
          * it reports the state of the page **currently open**, and navigating
            away clears it. Calling once at the end of a run therefore returns
            nothing, which is exactly what the first attempt did.

        So it is called per failing route, on the spot, and the results are
        accumulated. Silent on Next 15, which has no such endpoint.
        """
        if self.stack != "next":
            return
        try:
            report = nextmcp.errors(self.base_url)
        except Exception as e:
            log.debug(f"mcp get_errors skipped for {route}: {e}")
            return
        if not report:
            return

        body = "\n".join(l for l in report.splitlines()
                         if l and not l.startswith(("#", "```", "Source-mapped")))
        if body.strip() and body not in self._mcp_parts:
            self._mcp_parts.append(body)
            first = body.splitlines()[0] if body.splitlines() else ""
            elog("WARN", f"   ↳ Next reports: {first[:110]}")

    @property
    def mcp_report(self) -> str:
        if not self._mcp_parts:
            return ""
        return ("## What Next.js itself reports is broken\n"
                "Source-mapped, straight from the dev server — the file and "
                "line are exact.\n\n```\n"
                + "\n".join(self._mcp_parts[:8]) + "\n```")

    def _probe_routes(self, page):
        """Yield (route, status, detail, overlay) for every page route."""
        for route in self._discover_routes():
            url = self.base_url + route
            try:
                resp = page.goto(url, timeout=self.cfg["goto_timeout"],
                                 wait_until="load")
                detail = ""
                if resp is None:
                    status, detail = self._no_response(page, route)
                else:
                    status = resp.status
                    if status >= 400:
                        detail = self._body_text(page)
                        self._collect_mcp(route)
                    elog("INFO", f"   {route} → HTTP {status}")

                if status is not None and status < 400:
                    self._harvest_dynamic_links(page, route)

                overlay = ""
                if status is None or status < 400:
                    overlay = self._overlay_error(page)
                    if overlay and len(overlay) > 15:
                        self._collect_mcp(route)
                        elog("WARN", f"   ❌ {route} → "
                                     f"{overlay.splitlines()[0][:110]}")
                yield route, status, detail, overlay
            except Exception as e:

                if "ERR_ABORTED" in str(e):
                    elog("INFO", f"   {route} → aborted mid-compile, asking again")
                    try:
                        resp = page.goto(url, timeout=self.cfg["goto_timeout"],
                                         wait_until="load")
                    except Exception as again:
                        detail = f"{type(again).__name__}: {again}"[:300]
                        elog("WARN", f"   {route} → navigation failed twice: "
                                     f"{detail[:100]}")
                        self._collect_mcp(route)
                        yield route, None, detail, ""
                        continue
                    status = resp.status if resp is not None else None
                    if status is None:
                        status, detail = self._no_response(page, route)
                    else:
                        detail = "" if status < 400 else self._body_text(page)
                        elog("INFO", f"   {route} → HTTP {status} (on retry)")
                    if status is not None and status < 400:
                        self._harvest_dynamic_links(page, route)
                    overlay = ""
                    if status is None or status < 400:
                        overlay = self._overlay_error(page)
                        if overlay and len(overlay) > 15:
                            self._collect_mcp(route)
                    yield route, status, detail, overlay
                    continue

                detail = f"{type(e).__name__}: {e}"[:300]
                elog("WARN", f"   {route} → navigation failed: {detail[:110]}")
                self._collect_mcp(route)
                yield route, None, detail, ""


