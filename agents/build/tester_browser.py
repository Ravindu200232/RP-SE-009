"""Focused browser responsibilities for TesterAgent."""
# Source: tester_common.py — imported helper(s) come from this file.
from agents.build.tester_common import *


class TesterAgentBrowserMixin:
    # Decide what `page.goto` returning None actually meant. Playwright hands back no response when the navigation
    # produced none, and in a Next app that is nearly always a client-side redirect firing during load —
    # `router.replace('/login')` on a page that requires a session aborts the request that was already in flight.
    # Reported as a bare failure it became `Route /cart returned HTTP error` in the fix prompt, and the model then
    # rewrote a page whose only crime was asking the visitor to sign in first. Auth-gated routes are exactly the ones
    # this hit: /admin, /cart, /checkout. So the destination decides. Landed elsewhere → a redirect, and the route is
    # fine. Still on the same path → something did fail, and the page body plus Next's own source-mapped report is
    # what makes it fixable.
    def _no_response(self, page, route):
        """
        Decide what `page.goto` returning None actually meant.

        Playwright hands back no response when the navigation produced none,
        and in a Next app that is nearly always a client-side redirect firing
        during load — `router.replace('/login')` on a page that requires a
        session aborts the request that was already in flight. Reported as a
        bare failure it became `Route /cart returned HTTP error` in the fix
        prompt, and the model then rewrote a page whose only crime was asking
        the visitor to sign in first. Auth-gated routes are exactly the ones
        this hit: /admin, /cart, /checkout.

        So the destination decides. Landed elsewhere → a redirect, and the
        route is fine. Still on the same path → something did fail, and the
        page body plus Next's own source-mapped report is what makes it
        fixable.
        """
        landed = ""
        try:
            landed = urlparse(page.url).path or ""
        except Exception:
            pass

        if landed and landed.rstrip("/") != route.rstrip("/"):
            # From: agents/build/tester_common.py
            elog("INFO", f"   {route} → redirected to {landed}")
            return 302, ""

        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        landed = ""
        try:
            landed = urlparse(page.url).path or ""
        except Exception:
            pass
        if landed and landed.rstrip("/") != route.rstrip("/"):
            # From: agents/build/tester_common.py
            elog("INFO", f"   {route} → redirected to {landed}")
            return 302, ""
        try:
            resp = page.goto(self.base_url + route,
                             timeout=self.cfg["goto_timeout"],
                             wait_until="load")
        except Exception:
            resp = None
        if resp is not None:
            # From: agents/build/tester_common.py
            elog("INFO", f"   {route} → HTTP {resp.status} (compiled on retry)")
            # From: agents/build/tester_common.py
            return resp.status, ("" if resp.status < 400
                                 else self._body_text(page))
        try:
            landed = urlparse(page.url).path or ""
        except Exception:
            landed = ""
        if landed and landed.rstrip("/") != route.rstrip("/"):
            # From: agents/build/tester_common.py
            elog("INFO", f"   {route} → redirected to {landed}")
            return 302, ""

        # From: agents/build/tester_common.py
        body = self._body_text(page)
        # From: agents/build/tester_routes.py
        self._collect_mcp(route)
        # From: agents/build/tester_common.py
        elog("WARN", f"   {route} → no response from the dev server")
        return None, (body or "The dev server returned no response and the "
                              "page stayed blank — the request was aborted "
                              "before any HTML arrived.")

    # Make sure playwright is ready before the pipeline continues.
    def _ensure_playwright(self) -> bool:
        """Prepare the ensure playwright value or state used by this focused pipeline step."""
        try:
            import playwright  # noqa
            # From: agents/build/tester_common.py
            elog("INFO", "✅ Playwright Python package present")
            return True
        except ImportError:
            pass

        # From: agents/build/tester_common.py
        elog("INFO", "📦 Installing playwright Python package...")
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright",
             "--break-system-packages", "-q"],
            capture_output=True, timeout=120
        )
        if r.returncode != 0:
            # From: agents/build/tester_common.py
            elog("WARN", f"pip install failed: {r.stderr.decode()[:120]}")
            return False

        # From: agents/build/tester_common.py
        elog("INFO", "📦 Installing Chromium browser (may take a minute)...")
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            # From: agents/build/tester_common.py
            elog("WARN", f"Chromium install failed: {r.stderr[:120]}")
            return False

        # From: agents/build/tester_common.py
        elog("INFO", "✅ Playwright + Chromium ready")
        return True

    # Runs the browser tests step and returns the result.
    def _run_browser_tests(self) -> list:
        """Run the browser tests step and return its observable result."""
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        # From: agents/build/tester_common.py
        elog("INFO", "🎭 Launching Chromium (headless)...")
        # From: agents/build/tester_common.py
        etest("run", "Browser launch")
        errors = []
        console_errors = []

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(viewport={"width": 1280, "height": 720})
                page = ctx.new_page()

                page.on("console", lambda m: console_errors.append(m.text)
                        if m.type == "error" else None)
                page.on("pageerror", lambda e: console_errors.append(f"PageError: {e}"))

                # From: agents/build/tester_common.py
                elog("INFO", f"→ Navigating to {self.base_url}...")
                try:
                    resp = page.goto(self.base_url,
                                     timeout=self.cfg["goto_timeout"],
                                     wait_until="load")
                    code = resp.status if resp else "?"
                    if resp and resp.status >= 400:
                        # From: agents/build/tester_routes.py
                        self._collect_mcp("/")
                        body = ""
                        try:
                            body = page.inner_text("body")[:400]
                        except Exception:
                            pass
                        msg = f"Page returned HTTP {code}"
                        errors.append(f"{msg}\n{body}" if body else msg)
                        # From: agents/build/tester_common.py
                        etest("fail", msg, body[:120])
                        # From: agents/planner/builder/write_stream.py
                        browser.close(); return errors
                    # From: agents/build/tester_common.py
                    elog("INFO", f"✅ Page loaded (HTTP {code})")
                    # From: agents/build/tester_common.py
                    etest("pass", f"Page loaded HTTP {code}")
                except PWTimeout:
                    msg = (f"Page load timeout — {self.cfg['label']} may still "
                           f"be compiling")
                    # From: agents/build/tester_common.py
                    errors.append(msg); etest("fail", msg)
                    # From: agents/planner/builder/write_stream.py
                    browser.close(); return errors
                except Exception as e:
                    msg = f"Navigation error: {e}"
                    # From: agents/build/tester_common.py
                    errors.append(msg); etest("fail", msg)
                    # From: agents/planner/builder/write_stream.py
                    browser.close(); return errors

                # From: agents/build/tester_common.py
                elog("INFO", "→ Waiting for app to render...")
                react_mounted = False
                per_sel = max(2000, self.cfg["mount_timeout"] //
                              max(len(self.cfg["mount_selectors"]), 1))
                for _sel in self.cfg["mount_selectors"]:
                    try:
                        page.wait_for_selector(_sel, timeout=per_sel)
                        react_mounted = True
                        # From: agents/build/tester_common.py
                        elog("INFO", f"✅ App rendered (selector: {_sel})")
                        # From: agents/build/tester_common.py
                        etest("pass", "App rendered")
                        break
                    except PWTimeout:
                        continue
                if not react_mounted:
                    real_content = page.evaluate("""() => {
                        const skip = new Set(['NEXTJS-PORTAL','NEXT-ROUTE-ANNOUNCER',
                            'SCRIPT','NOSCRIPT','TEMPLATE','STYLE','LINK']);
                        return Array.from(document.body.children).some(
                            el => !skip.has(el.tagName)
                                  && el.getBoundingClientRect().height > 0);
                    }""")
                    if real_content:
                        react_mounted = True
                        # From: agents/build/tester_common.py
                        elog("INFO", "✅ Body has visible content — rendered")
                        # From: agents/build/tester_common.py
                        etest("pass", "App rendered")
                    else:
                        msg = "App never rendered — likely a compile/runtime error"
                        # From: agents/build/tester_common.py
                        errors.append(msg); etest("fail", msg)
                        # From: agents/build/tester_common.py
                        elog("WARN", f"❌ {msg}")

                # From: agents/build/tester_common.py
                overlay_txt = self._overlay_error(page)

                label = self.cfg["label"]
                if overlay_txt and len(overlay_txt) > 15:
                    errors.append(f"{label} compile error: {overlay_txt[:500]}")
                    # From: agents/build/tester_common.py
                    etest("fail", f"{label} compile error", overlay_txt[:120])
                    # From: agents/build/tester_common.py
                    elog("WARN", f"❌ {label} compile error: {overlay_txt[:120]}")
                else:
                    # From: agents/build/tester_common.py
                    etest("pass", f"No {label} error overlay")

                if self.stack == "next":
                    try:
                        health = page.evaluate("""async () => {
                            try {
                                const r = await fetch('/api/health')
                                return r.status + ' ' + (await r.text()).slice(0, 300)
                            } catch (e) { return 'ERR ' + e }
                        }""")
                        if '"ok":true' in (health or ""):
                            # From: agents/build/tester_common.py
                            etest("pass", "Database reachable")
                            # From: agents/build/tester_common.py
                            elog("INFO", "✅ MongoDB reachable via /api/health")
                        else:

                            errors.append(f"DB: /api/health failed → {health[:300]}")
                            # From: agents/build/tester_common.py
                            etest("fail", "Database check", str(health)[:120])
                            # From: agents/build/tester_common.py
                            elog("WARN", f"❌ /api/health → {str(health)[:120]}")
                    except Exception:
                        pass

                if react_mounted:
                    try:
                        has_visible = page.evaluate("""() => {
                            const sels = ['#root *', '#app *', 'main *',
                                          'body > div *', 'canvas', 'svg'];
                            for (const s of sels) {
                                for (const el of document.querySelectorAll(s)) {
                                    const r = el.getBoundingClientRect();
                                    if (r.width > 5 && r.height > 5) return true;
                                }
                            }
                            return false;
                        }""")
                        body_text = ""
                        try:
                            body_text = page.inner_text("body").strip()
                        except Exception:
                            pass
                        if not has_visible and len(body_text) < 10:
                            msg = "Page appears completely blank — nothing rendered"
                            # From: agents/build/tester_common.py
                            errors.append(msg); etest("fail", msg)
                            # From: agents/build/tester_common.py
                            elog("WARN", f"❌ {msg}")
                        else:
                            info = f"{len(body_text)} chars" if body_text else "visual content only"
                            # From: agents/build/tester_common.py
                            elog("INFO", f"✅ Content visible ({info})")
                            # From: agents/build/tester_common.py
                            etest("pass", "Content visible")
                    except Exception:
                        pass

                probed, bad_routes = 0, 0
                dynamic_probed, dynamic_bad = 0, 0
                if not self.smoke_only:
                    # From: agents/build/tester_routes.py
                    for route, status, detail, overlay in self._probe_routes(page):
                        probed += 1
                        if overlay:
                            bad_routes += 1
                            msg = f"Route {route} renders with a dev-server error"
                            errors.append(f"{msg}\n{overlay}")
                            # From: agents/build/tester_common.py
                            etest("fail", msg, overlay[:120])
                            continue
                        if status and status < 400:
                            continue
                        bad_routes += 1
                        msg = (f"Route {route} returned HTTP {status}" if status
                               else f"Route {route} never responded")
                        errors.append(f"{msg}\n{detail}" if detail else msg)
                        # From: agents/build/tester_common.py
                        etest("fail", msg, (detail or "")[:120])
                        # From: agents/build/tester_common.py
                        elog("WARN", f"❌ {msg}")
                    if probed:
                        # From: agents/build/tester_common.py
                        etest("pass" if not bad_routes else "fail",
                              f"Checked {probed} extra route(s)",
                              f"{bad_routes} failing" if bad_routes else "")

                    # From: agents/build/tester_routes.py
                    for route, status, detail, overlay, pattern, origin in self._probe_dynamic_links(page):
                        dynamic_probed += 1
                        if overlay:
                            dynamic_bad += 1
                            msg = f"Linked dynamic route {route} renders with a dev-server error"
                            errors.append(f"{msg}\n{overlay}")
                            # From: agents/build/tester_common.py
                            etest("fail", msg, overlay[:120])
                            continue
                        if status is not None and status < 400:
                            continue
                        dynamic_bad += 1
                        msg = (f"Real link {route} matching {pattern} returned HTTP {status}"
                               if status else
                               f"Real link {route} matching {pattern} never responded")
                        detail2 = (f"linked from {origin}. " + (detail or "")).strip()
                        errors.append(f"{msg}\n{detail2}" if detail2 else msg)
                        # From: agents/build/tester_common.py
                        etest("fail", msg, detail2[:120])
                        # From: agents/build/tester_common.py
                        elog("WARN", f"❌ {msg}")
                    if dynamic_probed:
                        # From: agents/build/tester_common.py
                        etest("pass" if not dynamic_bad else "fail",
                              f"Checked {dynamic_probed} real dynamic link(s)",
                              f"{dynamic_bad} failing" if dynamic_bad else "")

                    if probed or dynamic_probed:
                        try:
                            page.goto(self.base_url, timeout=self.cfg["goto_timeout"],
                                      wait_until="load")
                        except Exception:
                            pass
                else:
                    # From: agents/build/tester_common.py
                    elog("INFO", "⚡ smoke-only browser check — exhaustive routes are owned by final E2E integrity")

                noise = self.cfg["noise"]
                real_signals = self.cfg["signals"]

                real_errors = [
                    e for e in console_errors
                    if not any(n.lower() in e.lower() for n in noise)
                    and any(s in e for s in real_signals)
                ]
                if real_errors:
                    for ce in real_errors[:5]:
                        short = ce[:160]
                        # From: agents/build/tester_common.py
                        elog("WARN", f"⚠ JS error: {short}")
                        # From: agents/build/tester_common.py
                        etest("fail", "JS runtime error", short)
                        errors.append(f"Console error: {short}")
                else:
                    # From: agents/build/tester_common.py
                    elog("INFO", "✅ No blocking JS errors")
                    # From: agents/build/tester_common.py
                    etest("pass", "No JS errors")

                try:
                    ss_path = self.project_dir / "test_screenshot.png"
                    page.screenshot(path=str(ss_path), full_page=False)
                    # From: agents/build/tester_common.py
                    elog("INFO", f"📸 Screenshot saved → test_screenshot.png")
                    # From: agents/build/tester_common.py
                    etest("pass", "Screenshot captured")
                except Exception as e:
                    # From: agents/build/tester_common.py
                    elog("WARN", f"Screenshot failed: {e}")

                # From: agents/planner/builder/write_stream.py
                browser.close()

        except Exception as e:
            msg = f"Playwright runtime error: {e}"
            # From: agents/build/tester_common.py
            elog("WARN", f"⚠ {msg}")
            # From: agents/build/tester_common.py
            etest("fail", msg)
            errors.append(msg)

        if errors:
            # From: agents/build/tester_common.py
            elog("WARN", f"❌ {len(errors)} issue(s) found")
        else:
            # From: agents/build/tester_common.py
            elog("INFO", "🎉 All browser tests passed!")
            # From: agents/build/tester_common.py
            etest("pass", "All tests passed!")

        return errors

# Source: tester_routes.py — imported helper(s) come from this file.
from agents.build.tester_routes import TesterAgentRoutesMixin


class TesterAgent(TesterAgentRoutesMixin, TesterAgentBrowserMixin, TesterAgentBase):
    """Concrete route + browser tester used by the build pipeline."""
    pass
