#!/usr/bin/env python3
"""
Tester Agent — Python Playwright API only. No JS files, no require(), no ES module issues.
Streams all output live to UI. Retries until clean or max attempts reached.
"""
import subprocess, sys, time, logging
from pathlib import Path
from urllib.parse import urlparse

from . import nextmcp

log = logging.getLogger("tester")
_emit = None

def set_emit(fn):
    global _emit
    _emit = fn

def elog(lvl, txt):
    if _emit:
        _emit({"type": "log", "level": lvl, "text": txt})
    log.info(f"[{lvl}] {txt}")

def etest(status, msg, detail=""):
    """Emit a structured test result event to the UI."""
    if _emit:
        _emit({"type": "test_result", "status": status, "msg": msg, "detail": detail})


_VITE_NOISE = [
    "favicon", "Warning:", "DevTools", "Download the React",
    "ReactDOM.render", "StrictMode", "[HMR]", "[vite]", "vite",
    "hot update", "connecting", "react-refresh",
    "net::ERR_", "Failed to load resource",
    "Cross-Origin", "Content-Security-Policy",
]
_VITE_SIGNALS = [
    "is not defined", "is not a function",
    "Cannot read prop", "Cannot read properties",
    "SyntaxError", "ReferenceError", "TypeError",
    "Failed to resolve import", "does not provide an export",
]

STACKS = {
    "vite": {
        "label": "Vite",
        "ready_timeout": 30, "req_timeout": 5, "poll": 1.5,
        "goto_timeout": 30000, "mount_timeout": 8000,
        "mount_selectors": ["#root > *", "#app > *", "canvas", "svg", "main"],
        "overlay_tag": "vite-error-overlay",
        "noise": _VITE_NOISE,
        "signals": _VITE_SIGNALS,
    },
    "next": {
        "label": "Next.js",

        "ready_timeout": 180, "req_timeout": 90, "poll": 2.0,
        "goto_timeout": 120000, "mount_timeout": 20000,

        "mount_selectors": ["main", "header", "nav", "section", "table",
                            "body > div"],
        "overlay_tag": "nextjs-portal",
        "noise": [
            "favicon", "Warning:", "DevTools", "Download the React",
            "[Fast Refresh]", "Fast Refresh", "react-refresh", "hot-reloader",
            "webpack-hmr", "next-dev", "<Suspense>", "Image with src",
            "net::ERR_", "Failed to load resource",
            "Cross-Origin", "Content-Security-Policy",
        ],
        "signals": [
            "is not defined", "is not a function",
            "Cannot read prop", "Cannot read properties",
            "SyntaxError", "ReferenceError", "TypeError",

            "Module not found", "Can't resolve", "is not exported from",
            "only works in a Client Component", "Hydration failed",
            "Text content does not match", "Only plain objects",
            "Unhandled Runtime Error",
            "MongoServerSelectionError", "MongoNetworkError", "ECONNREFUSED",
        ],
    },
}


OVERLAY_SIGNAL_RE = (r"Build Error|Runtime Error|Console Error|"
                     r"Failed to compile|Unhandled|Module not found|"
                     r"Only plain objects|Functions cannot be passed|"
                     r"Event handlers cannot be passed|"
                     r"cannot be passed directly|Error:")

_OVERLAY_JS = """(re) => {
    const rx = new RegExp(re, 'i');
    for (const p of document.querySelectorAll('nextjs-portal')) {
        const r = p.shadowRoot; if (!r) continue;
        const dlg = r.querySelector('[data-nextjs-dialog],'
            + '#nextjs__container_errors_desc,'
            + '[data-nextjs-terminal],[data-nextjs-dialog-body]');
        if (!dlg) continue;
        const t = (dlg.innerText || dlg.textContent || '').trim();
        if (!rx.test(t)) continue;
        return t.slice(0, 800);
    }
    return '';
}"""

_VITE_OVERLAY_JS = """() => {
    const ov = document.querySelector('vite-error-overlay');
    if (ov && ov.shadowRoot) {
        const el = ov.shadowRoot.querySelector('.message-body,.message,pre,.err-message');
        return el ? el.textContent.trim().slice(0,600)
                  : ov.shadowRoot.textContent.trim().slice(0,600);
    }
    return '';
}"""


def overlay_error(page, stack: str = "next") -> str:
    """
    The dev server's error dialog for whatever page is currently open.

    Module level because the end-to-end sweep needs exactly this check on a
    signed-in session, and two copies of the shadow-DOM traversal would drift.
    """
    try:
        if stack == "next":
            return page.evaluate(_OVERLAY_JS, OVERLAY_SIGNAL_RE) or ""
        return page.evaluate(_VITE_OVERLAY_JS) or ""
    except Exception:
        return ""


class TesterAgent:
    def __init__(self, project_dir: Path, port: int = 5173,
                 stack: str = "vite"):
        self.project_dir = project_dir
        self.port        = port
        self.base_url    = f"http://localhost:{port}"
        self.stack       = stack if stack in STACKS else "vite"
        self.cfg         = STACKS[self.stack]

        self._mcp_parts  = []

    def test(self) -> list:
        errors = []
        label = self.cfg["label"]

        elog("INFO", f"⏳ Waiting for {label} at {self.base_url}...")
        ok, err = self._wait_for_server(timeout=self.cfg["ready_timeout"])
        if not ok:
            elog("WARN", f"❌ {label} not reachable: {err}")
            etest("fail", "HTTP check", f"Server not reachable: {err}")
            errors.append(f"HTTP check failed: {err}")
            return errors
        elog("INFO", f"✅ HTTP 200 — {label} is serving")
        etest("pass", "HTTP 200 OK")

        if not self._ensure_playwright():
            elog("WARN", "⚠ Playwright unavailable — skipping browser tests")
            etest("skip", "Playwright unavailable")
            return []

        errors.extend(self._run_browser_tests())
        return errors

    def _wait_for_server(self, timeout=30):
        import urllib.request, urllib.error
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = urllib.request.urlopen(
                    self.base_url, timeout=self.cfg["req_timeout"])
                if resp.status == 200:
                    return True, None
            except urllib.error.HTTPError:

                return True, None
            except Exception:
                pass
            time.sleep(self.cfg["poll"])
        return False, f"timeout after {timeout}s"

    MAX_EXTRA_ROUTES = 20

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
        return routes[:self.MAX_EXTRA_ROUTES]

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

    def _body_text(self, page) -> str:
        try:
            return page.inner_text("body")[:400]
        except Exception:
            return ""

    def _overlay_error(self, page) -> str:
        """The dev server's error dialog for the page currently open, or ''."""
        return overlay_error(page, self.stack)

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
            elog("INFO", f"   {route} → redirected to {landed}")
            return 302, ""
        try:
            resp = page.goto(self.base_url + route,
                             timeout=self.cfg["goto_timeout"],
                             wait_until="load")
        except Exception:
            resp = None
        if resp is not None:
            elog("INFO", f"   {route} → HTTP {resp.status} (compiled on retry)")
            return resp.status, ("" if resp.status < 400
                                 else self._body_text(page))
        try:
            landed = urlparse(page.url).path or ""
        except Exception:
            landed = ""
        if landed and landed.rstrip("/") != route.rstrip("/"):
            elog("INFO", f"   {route} → redirected to {landed}")
            return 302, ""

        body = self._body_text(page)
        self._collect_mcp(route)
        elog("WARN", f"   {route} → no response from the dev server")
        return None, (body or "The dev server returned no response and the "
                              "page stayed blank — the request was aborted "
                              "before any HTML arrived.")

    def _ensure_playwright(self) -> bool:
        try:
            import playwright  # noqa
            elog("INFO", "✅ Playwright Python package present")
            return True
        except ImportError:
            pass

        elog("INFO", "📦 Installing playwright Python package...")
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright",
             "--break-system-packages", "-q"],
            capture_output=True, timeout=120
        )
        if r.returncode != 0:
            elog("WARN", f"pip install failed: {r.stderr.decode()[:120]}")
            return False

        elog("INFO", "📦 Installing Chromium browser (may take a minute)...")
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            elog("WARN", f"Chromium install failed: {r.stderr[:120]}")
            return False

        elog("INFO", "✅ Playwright + Chromium ready")
        return True

    def _run_browser_tests(self) -> list:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        elog("INFO", "🎭 Launching Chromium (headless)...")
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

                elog("INFO", f"→ Navigating to {self.base_url}...")
                try:
                    resp = page.goto(self.base_url,
                                     timeout=self.cfg["goto_timeout"],
                                     wait_until="load")
                    code = resp.status if resp else "?"
                    if resp and resp.status >= 400:
                        self._collect_mcp("/")
                        body = ""
                        try:
                            body = page.inner_text("body")[:400]
                        except Exception:
                            pass
                        msg = f"Page returned HTTP {code}"
                        errors.append(f"{msg}\n{body}" if body else msg)
                        etest("fail", msg, body[:120])
                        browser.close(); return errors
                    elog("INFO", f"✅ Page loaded (HTTP {code})")
                    etest("pass", f"Page loaded HTTP {code}")
                except PWTimeout:
                    msg = (f"Page load timeout — {self.cfg['label']} may still "
                           f"be compiling")
                    errors.append(msg); etest("fail", msg)
                    browser.close(); return errors
                except Exception as e:
                    msg = f"Navigation error: {e}"
                    errors.append(msg); etest("fail", msg)
                    browser.close(); return errors

                elog("INFO", "→ Waiting for app to render...")
                react_mounted = False
                per_sel = max(2000, self.cfg["mount_timeout"] //
                              max(len(self.cfg["mount_selectors"]), 1))
                for _sel in self.cfg["mount_selectors"]:
                    try:
                        page.wait_for_selector(_sel, timeout=per_sel)
                        react_mounted = True
                        elog("INFO", f"✅ App rendered (selector: {_sel})")
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
                        elog("INFO", "✅ Body has visible content — rendered")
                        etest("pass", "App rendered")
                    else:
                        msg = "App never rendered — likely a compile/runtime error"
                        errors.append(msg); etest("fail", msg)
                        elog("WARN", f"❌ {msg}")

                overlay_txt = self._overlay_error(page)

                label = self.cfg["label"]
                if overlay_txt and len(overlay_txt) > 15:
                    errors.append(f"{label} compile error: {overlay_txt[:500]}")
                    etest("fail", f"{label} compile error", overlay_txt[:120])
                    elog("WARN", f"❌ {label} compile error: {overlay_txt[:120]}")
                else:
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
                            etest("pass", "Database reachable")
                            elog("INFO", "✅ MongoDB reachable via /api/health")
                        else:

                            errors.append(f"DB: /api/health failed → {health[:300]}")
                            etest("fail", "Database check", str(health)[:120])
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
                            errors.append(msg); etest("fail", msg)
                            elog("WARN", f"❌ {msg}")
                        else:
                            info = f"{len(body_text)} chars" if body_text else "visual content only"
                            elog("INFO", f"✅ Content visible ({info})")
                            etest("pass", "Content visible")
                    except Exception:
                        pass

                probed, bad_routes = 0, 0
                for route, status, detail, overlay in self._probe_routes(page):
                    probed += 1
                    if overlay:

                        bad_routes += 1
                        msg = f"Route {route} renders with a dev-server error"
                        errors.append(f"{msg}\n{overlay}")
                        etest("fail", msg, overlay[:120])
                        continue
                    if status and status < 400:
                        continue
                    bad_routes += 1
                    msg = (f"Route {route} returned HTTP {status}" if status
                           else f"Route {route} never responded")
                    errors.append(f"{msg}\n{detail}" if detail else msg)
                    etest("fail", msg, (detail or "")[:120])
                    elog("WARN", f"❌ {msg}")
                if probed:
                    etest("pass" if not bad_routes else "fail",
                          f"Checked {probed} extra route(s)",
                          f"{bad_routes} failing" if bad_routes else "")
                    try:
                        page.goto(self.base_url,
                                  timeout=self.cfg["goto_timeout"],
                                  wait_until="load")
                    except Exception:
                        pass

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
                        elog("WARN", f"⚠ JS error: {short}")
                        etest("fail", "JS runtime error", short)
                        errors.append(f"Console error: {short}")
                else:
                    elog("INFO", "✅ No blocking JS errors")
                    etest("pass", "No JS errors")

                try:
                    ss_path = self.project_dir / "test_screenshot.png"
                    page.screenshot(path=str(ss_path), full_page=False)
                    elog("INFO", f"📸 Screenshot saved → test_screenshot.png")
                    etest("pass", "Screenshot captured")
                except Exception as e:
                    elog("WARN", f"Screenshot failed: {e}")

                browser.close()

        except Exception as e:
            msg = f"Playwright runtime error: {e}"
            elog("WARN", f"⚠ {msg}")
            etest("fail", msg)
            errors.append(msg)

        if errors:
            elog("WARN", f"❌ {len(errors)} issue(s) found")
        else:
            elog("INFO", "🎉 All browser tests passed!")
            etest("pass", "All tests passed!")

        return errors