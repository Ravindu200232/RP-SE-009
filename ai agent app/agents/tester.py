#!/usr/bin/env python3
"""
Tester Agent — Python Playwright API only. No JS files, no require(), no ES module issues.
Streams all output live to UI. Retries until clean or max attempts reached.
"""
import subprocess, sys, time, logging, json, os, shutil, uuid, re
from pathlib import Path

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


class TesterAgent:
    def __init__(self, project_dir: Path, port: int = 3000, spec: dict | None = None):
        self.project_dir = project_dir
        self.port        = port
        self.base_url    = f"http://localhost:{port}"
        self.spec        = spec or {}

    def test_build(self) -> list:
        """Run strict typecheck, lint, and production build gates."""
        npm = shutil.which("npm") or ("npm.cmd" if os.name == "nt" else "npm")
        errors = []
        commands = [("typecheck", [npm, "run", "typecheck"]),
                    ("lint", [npm, "run", "lint"]),
                    ("next build", [npm, "run", "build"])]
        for label, command in commands:
            elog("INFO", f"Running strict {label} gate...")
            try:
                result = subprocess.run(
                    command, cwd=self.project_dir,
                    capture_output=True, text=True, timeout=360,
                    env={**os.environ, "CI": "true", "MONGODB_URI": ""},
                )
            except Exception as e:
                msg = f"{label} could not run: {e}"
                etest("fail", label, str(e)[:160])
                errors.append(msg)
                continue
            output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            if result.returncode != 0:
                detail = output[-2200:]
                elog("WARN", f"{label} failed: {detail[:360]}")
                etest("fail", label, detail[:240])
                errors.append(f"{label} failed:\n{detail}")
            else:
                etest("pass", label)
                elog("INFO", f"{label} passed")
        return errors

    def test(self) -> list:
        errors = []

        # ── 1. Wait for Vite to be ready ─────────────────────────────────────
        elog("INFO", f"⏳ Waiting for Next.js at {self.base_url}...")
        ok, err = self._wait_for_server(timeout=60)
        if not ok:
            elog("WARN", f"❌ Vite not reachable: {err}")
            etest("fail", "HTTP check", f"Server not reachable: {err}")
            errors.append(f"HTTP check failed: {err}")
            return errors
        elog("INFO", "✅ HTTP 200 — Vite is serving")
        etest("pass", "HTTP 200 OK")

        # ── 2. Playwright browser tests ───────────────────────────────────────
        if not self._ensure_playwright():
            elog("WARN", "⚠ Playwright unavailable — skipping browser tests")
            etest("skip", "Playwright unavailable")
            return []  # NOT errors — don't trigger a fix loop just because Playwright is missing

        errors.extend(self._run_browser_tests())
        return errors

    # ── Internals ─────────────────────────────────────────────────────────────

    def _wait_for_server(self, timeout=30):
        import urllib.request, urllib.error
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = urllib.request.urlopen(self.base_url, timeout=5)
                if resp.status == 200:
                    return True, None
            except Exception:
                pass
            time.sleep(1.5)
        return False, f"timeout after {timeout}s"

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

                # Navigate — use "load" so JS has run before we check anything.
                # Don't use "networkidle": Vite HMR keeps a WS open forever.
                elog("INFO", f"→ Navigating to {self.base_url}...")
                try:
                    resp = page.goto(self.base_url, timeout=45000, wait_until="load")
                    code = resp.status if resp else "?"
                    if resp and resp.status >= 400:
                        msg = f"Page returned HTTP {code}"
                        errors.append(msg); etest("fail", msg)
                        browser.close(); return errors
                    elog("INFO", f"✅ Page loaded (HTTP {code})")
                    etest("pass", f"Page loaded HTTP {code}")
                except PWTimeout:
                    msg = "Page load timeout — Vite may still be compiling"
                    errors.append(msg); etest("fail", msg)
                    browser.close(); return errors
                except Exception as e:
                    msg = f"Navigation error: {e}"
                    errors.append(msg); etest("fail", msg)
                    browser.close(); return errors

                # React mount — try several selectors; some apps don't use #root
                elog("INFO", "→ Waiting for app to render...")
                react_mounted = False
                for _sel in ["#root > *", "#app > *", "canvas", "svg", "main"]:
                    try:
                        page.wait_for_selector(_sel, timeout=8000)
                        react_mounted = True
                        elog("INFO", f"✅ App rendered (selector: {_sel})")
                        etest("pass", "App rendered")
                        break
                    except PWTimeout:
                        continue
                if not react_mounted:
                    # Last resort: body has any children at all
                    if page.evaluate("() => document.body.children.length") > 0:
                        react_mounted = True
                        elog("INFO", "✅ Body has children — assuming rendered")
                        etest("pass", "App rendered")
                    else:
                        msg = "App never rendered — likely a compile/runtime error"
                        errors.append(msg); etest("fail", msg)
                        elog("WARN", f"❌ {msg}")

                # Next.js dev error overlay — rendered inside a <nextjs-portal>
                # custom element (shadow DOM) on a compile or runtime error.
                overlay_txt = ""
                try:
                    overlay_txt = page.evaluate("""() => {
                        const portal = document.querySelector('nextjs-portal');
                        if (portal && portal.shadowRoot) {
                            const t = portal.shadowRoot.textContent || '';
                            if (/Failed to compile|Unhandled Runtime Error|Build Error|SyntaxError|is not defined/i.test(t))
                                return t.trim().slice(0, 600);
                        }
                        return '';
                    }""") or ""
                except Exception:
                    pass

                if overlay_txt and len(overlay_txt) > 15:
                    errors.append(f"Next.js error overlay: {overlay_txt[:500]}")
                    etest("fail", "Next.js error overlay", overlay_txt[:120])
                    elog("WARN", f"❌ Next.js error overlay: {overlay_txt[:120]}")
                else:
                    etest("pass", "No error overlay")

                # Blank page check — ONLY fail if BOTH:
                #   • no element has a visible bounding box (truly nothing rendered)
                #   • body text is completely empty
                # This avoids false positives for canvas/SVG/icon-only apps which
                # render rich content but have little innerText.
                if react_mounted:
                    try:
                        has_visible = page.evaluate("""() => {
                            const sels = ['#root *', '#app *', 'body > div *', 'canvas', 'svg'];
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

                # Console errors — only report real JS exceptions that broke the app.
                # Ignore HMR noise, React dev warnings, network/CDN errors.
                noise = [
                    "favicon", "Warning:", "DevTools", "Download the React",
                    "ReactDOM.render", "StrictMode", "[HMR]", "[vite]", "vite",
                    "hot update", "connecting", "react-refresh",
                    "net::ERR_", "Failed to load resource",
                    "Cross-Origin", "Content-Security-Policy",
                ]
                real_signals = [
                    "is not defined", "is not a function",
                    "Cannot read prop", "Cannot read properties",
                    "SyntaxError", "ReferenceError", "TypeError",
                    "Failed to resolve import", "does not provide an export",
                ]
                # Filter: must NOT match noise AND MUST match a real signal
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

                # API smoke tests — GET every generated route. Informational:
                # the routes are deterministic, so a 500 is almost always the DB
                # still warming up (in-memory Mongo first boot), not a code bug, so
                # we log it but do NOT feed it into the fix loop.
                errors.extend(self._smoke_test_api(ctx))

                # Strict mode verifies that every collection round-trips through
                # Mongo (create -> read -> update -> delete), not just that GET
                # routes return a status code.
                errors.extend(self._run_api_persistence_tests(ctx, browser))

                if self.spec.get("app_kind") == "multipage-app":
                    errors.extend(self._run_multipage_tests(browser))

                # Screenshot (full page so the long design is captured)
                try:
                    shot_dir = self.project_dir / "verification" / "screenshots"
                    shot_dir.mkdir(parents=True, exist_ok=True)
                    ss_path = shot_dir / "home-desktop.png"
                    page.screenshot(path=str(ss_path), full_page=True)
                    # A second viewport catches responsive overflow and clipped CTAs.
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.goto(self.base_url, timeout=45000, wait_until="load")
                    page.screenshot(path=str(shot_dir / "home-mobile.png"), full_page=True)
                    page.set_viewport_size({"width": 1280, "height": 720})
                    elog("INFO", "📸 Desktop/mobile screenshots captured")
                    etest("pass", "Responsive screenshots captured")
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

    # ── API smoke tests ────────────────────────────────────────────────────────

    def _sample_payload(self, model: dict, suffix: str = "test") -> dict:
        payload = {}
        for field in model.get("fields") or []:
            name = str(field.get("name") or "").strip()
            if not name or name in {"_id", "owner", "createdAt", "updatedAt"}:
                continue
            ftype = str(field.get("type") or "String")
            if ftype.startswith("["):
                payload[name] = []
            elif field.get("enum"):
                payload[name] = (field.get("enum") or ["default"])[0]
            elif ftype == "ObjectId":
                payload[name] = "507f1f77bcf86cd799439011"
            elif ftype == "Number":
                payload[name] = 42
            elif ftype == "Boolean":
                payload[name] = True
            elif ftype == "Date":
                payload[name] = "2026-07-12T00:00:00.000Z"
            else:
                payload[name] = f"Locode {suffix} {name}"
        return payload or {"title": f"Locode {suffix}"}

    def _env_values(self) -> dict:
        values = {}
        env_file = self.project_dir / ".env.local"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
        return values

    def _run_multipage_tests(self, browser) -> list:
        """Verify cookies, role middleware, every page, and owner-or-admin CRUD
        using isolated browser contexts for distinct principals."""
        errors = []
        token = uuid.uuid4().hex[:10]
        password = "LocodeTest!42"
        roles = [r for r in (self.spec.get("roles") or []) if isinstance(r, dict)]
        admin_role = next((r for r in roles if r.get("name") == "admin"), None)
        signup_roles = [r for r in roles if r.get("name") != "admin" and r.get("selfSignup", True)]
        if not signup_roles:
            signup_roles = [{"name": "user", "home": "/"}]
        contexts, role_contexts, users = [], {}, []

        def new_context():
            ctx = browser.new_context(base_url=self.base_url, viewport={"width": 1280, "height": 800})
            contexts.append(ctx)
            return ctx

        def record(ok: bool, label: str, detail: str = ""):
            if ok:
                etest("pass", label)
                elog("INFO", f"   PASS {label}")
            else:
                etest("fail", label, detail[:180])
                elog("WARN", f"   FAIL {label}: {detail[:180]}")
                errors.append(f"{label}: {detail}")

        try:
            for index, role in enumerate(signup_roles):
                ctx = new_context()
                email = f"locode-{token}-{index}@example.test"
                resp = ctx.request.post("/api/auth/register", data={
                    "name": f"Test {role.get('name')}", "email": email,
                    "password": password, "role": role.get("name"),
                }, timeout=120000)
                ok = resp.status == 201
                record(ok, f"Register role {role.get('name')}", f"HTTP {resp.status}: {resp.text()[:160]}")
                if ok:
                    data = resp.json()
                    users.append({"ctx": ctx, "email": email, "role": role.get("name"),
                                  "id": data.get("user", {}).get("id")})
                    role_contexts[str(role.get("name"))] = ctx
            if not users:
                # Staff SRS systems disable public signup; use deterministic
                # role fixtures seeded by lib/seed.ts instead.
                for role in roles:
                    role_name = str(role.get("name"))
                    if role_name == "admin":
                        continue
                    ctx = new_context()
                    seeded = ctx.request.post("/api/auth/login", data={
                        "email": f"{role_name}@demo.com",
                        "password": f"{role_name}1234",
                    }, timeout=120000)
                    record(seeded.status == 200, f"Seeded {role_name} login", f"HTTP {seeded.status}")
                    if seeded.status == 200:
                        users.append({"ctx": ctx, "email": f"{role_name}@demo.com",
                                      "role": role_name, "id": None})
                        role_contexts[role_name] = ctx
            if not users:
                return errors
            user_a = users[0]

            user_b_ctx = new_context()
            if signup_roles:
                rb = user_b_ctx.request.post("/api/auth/register", data={
                    "name": "Other User", "email": f"locode-{token}-other@example.test",
                    "password": password, "role": signup_roles[0].get("name"),
                }, timeout=120000)
            else:
                other_role = next((r for r in roles if r.get("name") not in {"admin", user_a.get("role")}), None)
                other_role = other_role or next((r for r in roles if r.get("name") != "admin"), None)
                other_name = str((other_role or {}).get("name") or "user")
                rb = user_b_ctx.request.post("/api/auth/login", data={
                    "email": f"{other_name}2@demo.com", "password": f"{other_name}1234"
                }, timeout=120000)
            record(rb.status == 201, "Register ownership user B", f"HTTP {rb.status}: {rb.text()[:160]}")

            me = user_a["ctx"].request.get("/api/auth/me", timeout=30000)
            me_data = me.json() if me.status == 200 else {}
            record(me.status == 200 and bool(me_data.get("user")),
                   "Session cookie accepted by /api/auth/me", f"HTTP {me.status}: {me.text()[:160]}")

            anon = new_context()
            protected = next((p for p in (self.spec.get("pages") or [])
                              if str(p.get("access", "")).startswith("role:")), None)
            if protected:
                rr = anon.request.get(protected["path"], max_redirects=0, timeout=30000)
                record(rr.status in {307, 308}, "Anonymous protected-page redirect",
                       f"HTTP {rr.status}, location={rr.headers.get('location')}")

            admin_ctx = new_context()
            env = self._env_values()
            ar = admin_ctx.request.post("/api/auth/login", data={
                "email": env.get("SEED_ADMIN_EMAIL", "admin@demo.com"),
                "password": env.get("SEED_ADMIN_PASSWORD", "admin1234"),
            }, timeout=120000)
            record(ar.status == 200, "Seeded admin login", f"HTTP {ar.status}: {ar.text()[:160]}")
            if ar.status == 200:
                role_contexts["admin"] = admin_ctx
                admin_home = (admin_role or {}).get("home", "/admin")
                admin_only = any(
                    str(p.get("path")) == admin_home and str(p.get("access", "")).startswith("role:admin")
                    for p in (self.spec.get("pages") or [])
                )
                if admin_only:
                    denied = user_a["ctx"].request.get(admin_home, max_redirects=0, timeout=30000)
                    record(denied.status in {307, 308}, "Non-admin rejected by admin gate",
                           f"HTTP {denied.status}, location={denied.headers.get('location')}")
                    allowed = admin_ctx.request.get(admin_home, timeout=30000)
                    record(allowed.status == 200, "Admin gate accepts admin", f"HTTP {allowed.status}")

            ids = {}
            owned_models = [m for m in (self.spec.get("data_model") or []) if m.get("ownedBy") == "User"]
            from agents.scaffold import pascal, route_name
            for model in owned_models:
                name, seg = pascal(model.get("name", "Item")), route_name(model.get("name", "Item"))
                created = user_a["ctx"].request.post(
                    f"/api/{seg}", data=self._sample_payload(model, token), timeout=120000)
                ok = created.status == 201
                record(ok, f"Owner creates {name}", f"HTTP {created.status}: {created.text()[:160]}")
                if not ok:
                    continue
                item_id = str(created.json().get("_id") or "")
                ids[name] = item_id
                mine = user_a["ctx"].request.get(f"/api/{seg}/mine", timeout=30000)
                mine_ids = [str(row.get("_id")) for row in (mine.json() if mine.status == 200 else [])]
                record(mine.status == 200 and item_id in mine_ids,
                       f"Owner /mine includes {name}", f"HTTP {mine.status}: {mine.text()[:160]}")
                update = user_b_ctx.request.put(f"/api/{seg}/{item_id}", data={"title": "forbidden"}, timeout=30000)
                record(update.status == 403, f"User B cannot edit user A {name}", f"HTTP {update.status}: {update.text()[:120]}")
                delete = user_b_ctx.request.delete(f"/api/{seg}/{item_id}", timeout=30000)
                record(delete.status == 403, f"User B cannot delete user A {name}", f"HTTP {delete.status}: {delete.text()[:120]}")

            for spec_page in self.spec.get("pages") or []:
                path = str(spec_page.get("path") or "")
                if not path:
                    continue
                if "[id]" in path:
                    rid = ids.get(pascal(spec_page.get("resource", "")))
                    if not rid:
                        continue
                    path = path.replace("[id]", rid)
                access = str(spec_page.get("access") or "public")
                ctx = anon if access == "public" else role_contexts.get(access.split(":", 1)[-1])
                if ctx is None:
                    continue
                page = ctx.new_page()
                page_errors = []
                page.on("pageerror", lambda e, bag=page_errors: bag.append(str(e)))
                try:
                    response = page.goto(path, wait_until="load", timeout=60000)
                    status = response.status if response else 0
                    body = page.locator("body").inner_text(timeout=10000).strip()
                    record(status < 400 and len(body) >= 10 and not page_errors,
                           f"Page {path} renders", f"HTTP {status}; body={len(body)}; errors={page_errors[:2]}")
                    try:
                        from agents.quality import build_contract
                        allowed = set((self.spec.get("quality_contract") or build_contract(self.spec)).get("routes") or [])
                        hrefs = page.locator("a[href]").evaluate_all("els => els.map(e => e.getAttribute('href'))")
                        for href in hrefs:
                            if not href or not str(href).startswith("/") or str(href).startswith("/#"):
                                continue
                            clean = str(href).split("?", 1)[0].rstrip("/") or "/"
                            if clean not in allowed and not any(
                                clean == r.replace("[id]", "") or r.endswith("[id]") and clean.startswith(r[:-4])
                                for r in allowed
                            ):
                                record(False, f"Declared-link crawl {path}", f"undeclared href {href}")
                    except Exception as link_error:
                        record(False, f"Declared-link crawl {path}", str(link_error))
                except Exception as e:
                    record(False, f"Page {path} renders", str(e))
                finally:
                    page.close()

            if ar.status == 200:
                for model in owned_models:
                    name, seg = pascal(model.get("name", "Item")), route_name(model.get("name", "Item"))
                    item_id = ids.get(name)
                    if not item_id:
                        continue
                    au = admin_ctx.request.put(f"/api/{seg}/{item_id}", data={"title": "Admin reviewed"}, timeout=30000)
                    record(au.status == 200, f"Admin can edit {name}", f"HTTP {au.status}: {au.text()[:120]}")
                    ad = admin_ctx.request.delete(f"/api/{seg}/{item_id}", timeout=30000)
                    record(ad.status == 200, f"Admin can delete {name}", f"HTTP {ad.status}: {ad.text()[:120]}")

            logout = user_a["ctx"].request.post("/api/auth/logout", timeout=30000)
            after = user_a["ctx"].request.get("/api/auth/me", timeout=30000)
            after_user = after.json().get("user") if after.status == 200 else "error"
            record(logout.status == 200 and after_user is None, "Logout clears session",
                   f"logout={logout.status}, me={after.text()[:120]}")
        except Exception as e:
            record(False, "Multipage verification runtime", str(e))
        finally:
            for ctx in contexts:
                try:
                    ctx.close()
                except Exception:
                    pass
        return errors

    def _discover_api_routes(self) -> list:
        """Top-level REST segments from app/api/<seg>/route.ts (skips [id])."""
        if self.spec.get("data_model"):
            from agents.scaffold import route_name
            return [f"/api/{route_name(m.get('name', 'Item'))}"
                    for m in self.spec.get("data_model") or []]
        api_dir = self.project_dir / "app" / "api"
        if not api_dir.exists():
            return []
        segs = sorted({
            p.parent.name
            for p in (list(api_dir.rglob("route.ts")) + list(api_dir.rglob("route.js")))
            if p.parent.name and p.parent.name != "[id]"
        })
        return [f"/api/{s}" for s in segs]

    def _smoke_test_api(self, ctx):
        """
        GET each generated API route via Playwright's request context (same origin).
        A 2xx proves route + Mongoose model + DB connection all work end-to-end.
        Non-2xx is logged but NOT returned as a fix-loop error (routes are
        deterministic — failures are infra, e.g. the in-memory DB still booting).
        """
        routes = self._discover_api_routes()
        errors = []
        if not routes:
            return errors
        elog("INFO", f"🔌 Smoke-testing {len(routes)} API route(s)…")
        for path in routes:
            url = f"{self.base_url}{path}"
            try:
                resp = ctx.request.get(url, timeout=20000)
                status = resp.status
                if 200 <= status < 300:
                    elog("INFO", f"   ✅ GET {path} → {status}")
                    etest("pass", f"API {path} {status}")
                else:
                    body = ""
                    try:
                        body = resp.text()[:120]
                    except Exception:
                        pass
                    elog("WARN", f"   ⚠ GET {path} → {status} {body}")
                    etest("fail", f"API {path} {status}", body)
                    errors.append(f"API {path} returned HTTP {status}")
            except Exception as e:
                elog("WARN", f"   ⚠ GET {path} failed: {e}")
                etest("fail", f"API {path} unreachable", str(e)[:120])
                errors.append(f"API {path} unreachable: {e}")
        return errors

    @staticmethod
    def _unwrap(payload):
        if isinstance(payload, dict) and "data" in payload:
            return payload.get("data")
        return payload

    def _run_api_persistence_tests(self, ctx, browser) -> list:
        """Round-trip every generated collection through its real API and Mongo."""
        errors = []
        models = [m for m in (self.spec.get("data_model") or []) if isinstance(m, dict)]
        if not models:
            return errors
        api_ctx = ctx
        extra_ctx = None
        # Protected SRS collections need an authenticated principal. Admin is
        # deliberately used because it is seeded deterministically for every app.
        if (self.spec.get("auth") or {}).get("enabled") or self.spec.get("app_kind") == "multipage-app":
            extra_ctx = browser.new_context(base_url=self.base_url, viewport={"width": 1280, "height": 800})
            env = self._env_values()
            login = extra_ctx.request.post("/api/auth/login", data={
                "email": env.get("SEED_ADMIN_EMAIL", "admin@demo.com"),
                "password": env.get("SEED_ADMIN_PASSWORD", "admin1234"),
            }, timeout=120000)
            if login.status == 200:
                api_ctx = extra_ctx
            else:
                errors.append(f"Persistence admin login failed: HTTP {login.status}")
                etest("fail", "Persistence admin login", f"HTTP {login.status}")
                return errors

        from agents.scaffold import route_name
        token = uuid.uuid4().hex[:8]

        def check(ok, label, detail=""):
            if ok:
                etest("pass", label); elog("INFO", f"   PASS {label}")
            else:
                etest("fail", label, detail[:180]); elog("WARN", f"   FAIL {label}: {detail[:180]}")
                errors.append(f"{label}: {detail}")

        try:
            for model in models:
                seg = route_name(model.get("name", "Item"))
                payload = self._sample_payload(model, token)
                created = api_ctx.request.post(f"/api/{seg}", data=payload, timeout=120000)
                body = created.json() if created.status in {200, 201} else {}
                record = self._unwrap(body) or {}
                if isinstance(record, list):
                    record = record[-1] if record else {}
                item_id = str(record.get("_id") or record.get("id") or "") if isinstance(record, dict) else ""
                check(created.status == 201 and bool(item_id), f"API create persists {model.get('name')}", f"HTTP {created.status}: {created.text()[:140]}")
                if not item_id:
                    continue
                listed = api_ctx.request.get(f"/api/{seg}", timeout=30000)
                listing = self._unwrap(listed.json() if listed.status == 200 else [])
                listing = listing.get("items", []) if isinstance(listing, dict) and "items" in listing else listing
                found = any(str(row.get("_id")) == item_id for row in (listing or []) if isinstance(row, dict))
                check(listed.status == 200 and found, f"API list read-back {model.get('name')}", f"HTTP {listed.status}")
                fetched = api_ctx.request.get(f"/api/{seg}/{item_id}", timeout=30000)
                fetched_body = self._unwrap(fetched.json() if fetched.status == 200 else {}) or {}
                check(fetched.status == 200 and str(fetched_body.get("_id")) == item_id,
                      f"API detail read-back {model.get('name')}", f"HTTP {fetched.status}")
                update_payload = dict(payload)
                for field in model.get("fields") or []:
                    name = field.get("name")
                    if not name or name in {"owner", "_id"}:
                        continue
                    if str(field.get("type")) == "Number":
                        update_payload[name] = 84
                    elif str(field.get("type")) == "Boolean":
                        update_payload[name] = not bool(update_payload.get(name))
                    else:
                        update_payload[name] = f"Locode updated {token}"
                    break
                updated = api_ctx.request.put(f"/api/{seg}/{item_id}", data=update_payload, timeout=30000)
                updated_body = self._unwrap(updated.json() if updated.status == 200 else {}) or {}
                check(updated.status == 200 and str(updated_body.get("_id") or item_id) == item_id,
                      f"API update {model.get('name')}", f"HTTP {updated.status}")
                reread = api_ctx.request.get(f"/api/{seg}/{item_id}", timeout=30000)
                reread_body = self._unwrap(reread.json() if reread.status == 200 else {}) or {}
                check(reread.status == 200 and any(v == "Locode updated " + token or v == 84 for v in reread_body.values()),
                      f"API update read-back {model.get('name')}", f"HTTP {reread.status}")
                deleted = api_ctx.request.delete(f"/api/{seg}/{item_id}", timeout=30000)
                check(deleted.status == 200, f"API delete {model.get('name')}", f"HTTP {deleted.status}")
                gone = api_ctx.request.get(f"/api/{seg}/{item_id}", timeout=30000)
                check(gone.status == 404, f"API delete read-back {model.get('name')}", f"HTTP {gone.status}")

                required = next((f for f in model.get("fields") or [] if f.get("required")), None)
                if required:
                    invalid = api_ctx.request.post(f"/api/{seg}", data={}, timeout=30000)
                    check(invalid.status in {400, 422}, f"API validation rejects blank {model.get('name')}", f"HTTP {invalid.status}")
        finally:
            if extra_ctx:
                extra_ctx.close()
        return errors
