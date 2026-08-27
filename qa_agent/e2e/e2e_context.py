"""Project, route, account and runtime-evidence discovery for E2E journeys."""
from qa_agent.e2e.e2e_common import *


class E2EContextMixin:
    def __init__(self, arch, project_dir=None, *, callbacks=None, session=None,
                 analyzer=None, base_url="http://localhost:5173"):
        self.arch = arch
        self.project_dir = Path(project_dir or arch.project_dir)
        self.cb = callbacks or {}
        self.qa = session
        self.az = analyzer
        self.base_url = base_url.rstrip("/")
        self.scenarios = []
        # Runtime DOM evidence is read-only and cached per role/journey.
        self._runtime_evidence_cache = {}
        # Per-role, per-route DOM snapshots.
        self._runtime_route_cache = {}
        self._runtime_dynamic_cache = {}
        self._warmed_routes = set()
        self._last_run_evidence = {}
        self._last_cookie_jar = {}
        # Browser-loop circuit breaker.
        self._route_loop_fault = ""
        self._page_path_cache = None
        self._accepted_scenarios = {}
        self._auth_route_cache = None


    def remember_scenario(self, journey, scenario) -> None:
        """Keep the last green scenario for the final clean-room replay."""
        import copy
        key = str((journey or {}).get("title") or getattr(scenario, "title", "") or "").strip()
        if key and scenario is not None:
            self._accepted_scenarios[key] = copy.deepcopy(scenario)

    def accepted_scenario(self, journey):
        key = str((journey or {}).get("title") or "").strip()
        return self._accepted_scenarios.get(key)

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):
        self._fire("on_log", lvl, txt)
        log.info(txt)

    def _test(self, status, msg, detail=""):
        self._fire("on_test", status, msg, detail)

    def accounts(self) -> list:
        """
        The demo accounts, from `.agentforge/plan.json` — the machine-readable
        source, so nothing has to be scraped out of prose or guessed.
        """
        plan = getattr(self.arch, "plan", None) or {}
        accs = [a for a in (plan.get("demo_accounts") or [])
                if a.get("email") and a.get("password")]
        if accs:
            return accs
        try:
            fp = self.project_dir / ".agentforge" / "plan.json"
            if fp.is_file():
                data = json.loads(fp.read_text(encoding="utf-8"))
                return [a for a in (data.get("demo_accounts") or [])
                        if a.get("email") and a.get("password")]
        except Exception as e:
            log.debug(f"plan.json: {e}")
        return []

    @staticmethod
    def _role_key(value) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    def account_for(self, role) -> dict:
        """Return the one demo account that owns this exact role."""
        accs = self.accounts()
        wanted = self._role_key(role)
        if not accs or not wanted:
            return {}
        matches = [a for a in accs if self._role_key(a.get("role")) == wanted]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            self._log("WARN", f"   ⚠ role {role} has {len(matches)} demo accounts; "
                              "the role contract must be one account per role")
        else:
            self._log("WARN", f"   ⚠ no demo account exactly matches role {role}")
        return {}

    def account_for_scenario(self, text: str, journey: dict = None) -> dict:
        """Resolve credentials for both single-actor and public-to-user flows.

        ``AS :: visitor`` correctly starts signed out, but a booking or signup
        journey can later cross into the role created by public registration.
        Resolve that target from covered capabilities and ``signup_role``.  No
        first-account fallback is allowed: ambiguous identity is an authoring
        failure, not permission to test the wrong role.
        """
        raw = str(text or "")
        if not re.search(r"\{\{\s*(?:email|password|role)\s*\}\}", raw, re.I):
            return {}

        accounts = [a for a in self.accounts() if isinstance(a, dict)]
        by_key = {}
        for account in accounts:
            key = self._role_key(account.get("role"))
            if key:
                by_key.setdefault(key, []).append(account)

        authored_role = self._role_in(raw)
        authored_key = self._role_key(authored_role)
        exact = by_key.get(authored_key) or []
        if len(exact) == 1:
            return exact[0]

        journey = journey or {}
        plan = getattr(self.arch, "plan", None) or {}
        signed_out = {self._role_key(x) for x in
                      (getattr(self, "_SIGNED_OUT", ()) or ())}
        covers = {str(x or "").upper() for x in (journey.get("covers") or [])}
        candidates = []

        def consider(role):
            key = self._role_key(role)
            rows = by_key.get(key) or []
            if key and key not in signed_out and len(rows) == 1 and rows[0] not in candidates:
                candidates.append(rows[0])

        for capability in plan.get("capabilities") or []:
            if not isinstance(capability, dict):
                continue
            if covers and str(capability.get("id") or "").upper() not in covers:
                continue
            consider(capability.get("who") or capability.get("role") or capability.get("actor"))

        contract = journey.get("contract") or {}
        if isinstance(contract, dict):
            consider(contract.get("authenticated_actor") or contract.get("session_role"))

        if len(candidates) == 1:
            return candidates[0]

        signup_role = plan.get("signup_role")
        signup = by_key.get(self._role_key(signup_role)) or []
        if len(signup) == 1 and (not authored_key or authored_key in signed_out):
            return signup[0]

        if len(accounts) == 1 and (not authored_key or authored_key in signed_out):
            return accounts[0]
        return {}

    def _routes(self) -> str:
        if not self.az:
            return ""
        try:
            rows = []
            for url, meta in sorted(self.az.enumerate_routes().items()):

                note = ("  ← reach this by CLICKING a link, never GOTO"
                        if meta.get("dynamic") else "")
                rows.append(f"  {url}  ({meta['kind']}){note}")
            return "\n".join(rows[:40])
        except Exception as e:
            log.debug(f"routes: {e}")
            return ""

    def source_of(self, rel, cap=7000) -> str:
        if not rel:
            return ""
        try:
            fp = self.project_dir / rel
            if fp.is_file():
                return fp.read_text(encoding="utf-8", errors="replace")[:cap]
        except Exception:
            pass
        try:
            return str((getattr(self.arch, "files", None) or {}).get(rel, "") or "")[:cap]
        except Exception:
            return ""

    LOCAL_IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[\w./-]+)['"]""")

    def markup_for(self, rel, cap=7000) -> str:
        """
        A page's source **and the components it renders**.

        A page is mostly composition: it imports `<StatusToggle/>` and the
        button the flow needs to click is inside that component, not in the
        page. Measured on a real build — the flow signed in correctly and then
        missed on `role=button name=/currently reading|mark as reading/i`
        because the actual label lives in `components/StatusToggle.jsx`, which
        the prompt never showed. Handing over the page alone leaves the model
        guessing at wording that is written down one file away.
        """
        body = self.source_of(rel, cap)
        if not body:
            return ""
        blocks = [f"--- {rel} ---\n{body}"]
        for spec in dict.fromkeys(self.LOCAL_IMPORT_RE.findall(body)):
            for ext in (".jsx", ".js", ""):
                child = f"{spec}{ext}"
                inner = self.source_of(child, 4000)
                if inner:
                    blocks.append(f"--- {child} (rendered by {rel}) ---\n{inner}")
                    break
            if len(blocks) >= 4:
                break
        return "\n\n".join(blocks)

    def auth_routes(self) -> list[str]:
        """Auth UI routes discovered from generated source and the route tree.

        Route names are only a fallback.  Calls to the app's auth client and
        real credential fields are stronger evidence, so custom paths such as
        `/access` work without teaching the E2E engine that name.
        """
        if self._auth_route_cache is not None:
            return list(self._auth_route_cache)
        try:
            routes = self.az.enumerate_routes() or {} if self.az else {}
        except Exception:
            routes = {}
        scored = []
        for url, meta in routes.items():
            if meta.get("kind") != "page" or meta.get("dynamic"):
                continue
            rel = str(meta.get("file") or "")
            body = self.markup_for(rel, 12_000) or self.source_of(rel, 12_000)
            score = 0
            auth_action = bool(re.search(
                r"\bsign(?:in|up)\s*\.\s*email\s*\(", body, re.I))
            credentials = bool(
                re.search(r"type\s*=\s*['\"]password['\"]", body, re.I)
                and re.search(r"type\s*=\s*['\"]email['\"]|name\s*=\s*['\"][^'\"]*email",
                              body, re.I))
            if auth_action:
                score += 8
            if credentials and re.search(
                    r"/api/[^'\"\s]*(?:sign-in|sign-up)", body, re.I):
                score += 6
            if credentials:
                score += 4
            if credentials and re.search(
                    r"(?:^|/)(?:login|log-in|signin|sign-in|signup|sign-up|register)(?:/|$)",
                    str(url or ""), re.I):
                score += 2
            if score:
                scored.append((-score, str(url or "/"), rel))
        self._auth_route_cache = [url for _score, url, _rel in sorted(scored)]
        return list(self._auth_route_cache)

    def entry_route(self) -> str:
        """Best source-proven credential-entry route, or an empty string."""
        candidates = self.auth_routes()
        if not candidates:
            return ""
        # Prefer a page that invokes sign-in over registration-only pages.
        try:
            routes = self.az.enumerate_routes() or {} if self.az else {}
        except Exception:
            routes = {}
        for url in candidates:
            rel = str((routes.get(url) or {}).get("file") or "")
            if re.search(r"\bsignIn\s*\.\s*email\s*\(", self.source_of(rel, 12_000)):
                return url
        return candidates[0]

    def _is_auth_route(self, route: str) -> bool:
        path = str(route or "").split("?", 1)[0].rstrip("/") or "/"
        return path in {(r.rstrip("/") or "/") for r in self.auth_routes()}

    @staticmethod
    def _is_auth_api_url(url: str) -> bool:
        """Infrastructure auth traffic, distinct from product mutations."""
        try:
            return urlparse(str(url or "")).path.startswith("/api/auth/")
        except Exception:
            return False

    def entry_page(self) -> str:
        """
        The sign-in page's file, because every journey starts there.

        Without its markup the model is inventing selectors for HTML it has
        never seen, and it invents plausible ones that do not match — measured:
        it asked for a placeholder matching /email/i on a form whose input says
        `placeholder="name@example.com"`. Nothing about that is guessable.
        """
        if not self.az:
            return ""
        try:
            return ((self.az.enumerate_routes() or {}).get(self.entry_route())
                    or {}).get("file", "")
        except Exception as e:
            log.debug(f"entry page: {e}")
            return ""

    def landing_page(self) -> str:
        """Where signing in lands. Every journey asserts on it."""
        if not self.az:
            return ""
        try:
            return ((self.az.enumerate_routes() or {}).get("/") or {}).get("file", "")
        except Exception:
            return ""

    MARKUP_BUDGET = 30_000
    JOURNEY_PAGES = 8

    def _journey_pages(self, journey: dict = None) -> list:
        """
        Page files this particular journey is likely to touch.

        Generic "first six static routes" was enough for a guest browse flow and
        systematically wrong for role-specific work. On the hotel run, the
        A role-specific journey needed a nested work page while the prompt spent
        its markup budget on public pages; the model then invented auth and
        edit selectors. Prioritize evidence from the journey itself:

        1. login + landing;
        2. route literals named by the workflow;
        3. planner contracts whose trigger/name/effect shares words with it;
        4. pages under the journey's role prefix (admin -> /admin/*);
        5. the remaining static pages.
        """
        out = [self.entry_page(), self.landing_page()]
        if not self.az:
            return [p for p in out if p]
        try:
            routes = self.az.enumerate_routes() or {}
        except Exception as e:
            log.debug(f"journey pages: {e}")
            return [p for p in out if p]

        def add_file(rel):
            if rel and rel not in out:
                out.append(rel)

        def file_for_url(url):
            meta = routes.get(url) or routes.get((url or "").rstrip("/")) or {}
            return meta.get("file", "")

        journey = journey or {}
        jparts = [str(journey.get("title") or ""),
                  str(journey.get("role") or "")]
        jparts += [str(x) for x in (journey.get("steps") or [])]
        jtext = " ".join(jparts).lower()

        for url in re.findall(r"(?<![\w:])(/[A-Za-z0-9_./\[\]-]+)", jtext):
            add_file(file_for_url(url.rstrip("/") or "/"))

        stop = {"the", "and", "then", "from", "with", "into", "that", "this",
                "page", "user", "admin", "guest", "click", "go", "reach"}
        jwords = {w for w in re.findall(r"[a-z0-9]+", jtext)
                  if len(w) > 3 and w not in stop}

        plan = getattr(self.arch, "plan", None) or {}

        covers = {str(x or "").upper() for x in (journey.get("covers") or [])}
        if covers:
            for cap in (plan.get("capabilities") or []):
                if not isinstance(cap, dict):
                    continue
                if str(cap.get("id") or "").upper() not in covers:
                    continue
                for rel in (cap.get("files") or []):
                    add_file(str(rel or "").strip())

        scored = []
        for c in (plan.get("contracts") or []):
            if not isinstance(c, dict):
                continue
            ctext = " ".join(str(c.get(k) or "") for k in
                             ("name", "trigger", "effect", "target")).lower()
            cwords = {w for w in re.findall(r"[a-z0-9]+", ctext)
                      if len(w) > 3 and w not in stop}
            overlap = len(jwords & cwords)
            if overlap:
                scored.append((overlap, c))
        for _, c in sorted(scored, key=lambda x: -x[0]):
            add_file(str(c.get("from") or ""))
            target = str(c.get("target") or "")
            if target and "[" not in target:
                add_file(file_for_url(target.rstrip("/") or "/"))

        role = str(journey.get("role") or "").lower().strip()
        role_rows, rest = [], []
        for url, meta in routes.items():
            if meta.get("kind") != "page" or meta.get("dynamic") or "[" in url:
                continue
            item = (url, meta.get("file", ""))
            if role and (url == f"/{role}" or url.startswith(f"/{role}/")):
                role_rows.append(item)
            else:
                rest.append(item)

        role_rows.sort(key=lambda t: (t[0].count("/"), t[0]))
        rest.sort(key=lambda t: (t[0].count("/"), t[0]))
        for _, rel in role_rows + rest:
            add_file(rel)
            if len([p for p in out if p]) >= self.JOURNEY_PAGES:
                break

        return [p for p in out if p][:self.JOURNEY_PAGES]

    def _url_for_file(self, rel: str) -> str:
        """Static URL served by a planned page file, or ``""``.

        The scenario author reasons in URLs while `_journey_pages` reasons in
        source files. Keeping this translation deterministic prevents the model
        from inventing a conventional dashboard route when the app actually
        serves a differently named work page.
        """
        if not rel or not self.az:
            return ""
        try:
            for url, meta in (self.az.enumerate_routes() or {}).items():
                if meta.get("file") == rel and meta.get("kind") == "page" and \
                        not meta.get("dynamic") and "[" not in url:
                    return url or "/"
        except Exception:
            pass
        return ""

    def _journey_routes(self, journey: dict = None, limit: int = 7) -> list:
        """Concrete static routes that are relevant to one workflow."""
        journey = journey or {}
        out = []
        def add(url):
            url = str(url or "").strip()
            if url and url.startswith("/") and "[" not in url and url not in out:
                out.append(url)

        try:
            route_map = self.az.enumerate_routes() or {} if self.az else {}
        except Exception:
            route_map = {}

        # Explicit URLs in the workflow are authoritative.
        text = " ".join([str(journey.get("title") or ""),
                         str(journey.get("role") or "")] +
                        [str(x) for x in (journey.get("steps") or [])])
        for url in re.findall(r"(?<![\w:])(/[A-Za-z0-9_./\[\]-]+)", text):
            url = url.rstrip("/") or "/"
            if "[" in url:
                parent = re.sub(r"/\[[^/]+\](?:/.*)?$", "", url) or "/"
                if parent in route_map and not (route_map.get(parent) or {}).get("dynamic"):
                    add(parent)
                continue
            add(url)
        for rel in self._journey_pages(journey):
            add(self._url_for_file(rel))
            for pattern, meta in route_map.items():
                if meta.get("file") != rel or "[" not in pattern:
                    continue
                parent = re.sub(r"/\[[^/]+\](?:/.*)?$", "", pattern) or "/"
                if parent in route_map and not route_map[parent].get("dynamic"):
                    add(parent)

        role = str(journey.get("role") or "").strip().lower()
        if role:
            # Put role work pages before generic public pages.
            order = {u: i for i, u in enumerate(out)}
            out.sort(key=lambda u: (0 if (u == f"/{role}" or
                                          u.startswith(f"/{role}/")) else 1,
                                    order.get(u, 10_000)))
        return out[:limit]

    def _journey_dynamic_patterns(self, journey: dict = None) -> list:
        journey = journey or {}
        try:
            route_map = self.az.enumerate_routes() or {} if self.az else {}
        except Exception:
            route_map = {}
        pages = set(self._journey_pages(journey))
        text = " ".join([str(journey.get("title") or "")] +
                        [str(x) for x in (journey.get("steps") or [])])
        out = []
        for url, meta in route_map.items():
            if not meta.get("dynamic"):
                continue
            if meta.get("file") in pages or url in text:
                out.append(url)
        return out[:3]

    @staticmethod
    def _matches_dynamic(pattern: str, url: str) -> bool:
        path = str(url or "").split("?", 1)[0]
        rx = re.escape(str(pattern or ""))
        rx = re.sub(r"\\\[[^]]+\\\]", r"[^/?#]+", rx)
        return bool(re.fullmatch(rx, path))

    def runtime_evidence(self, journey: dict = None, limit: int = 4) -> str:
        """Read-only DOM map, including a real concrete dynamic record page.

        The previous preflight deliberately skipped `[id]` URLs.  That avoided
        fake `/product` 404s but also meant the first scenario was authored
        without ever seeing Add-to-cart, rating controls, edit buttons, etc.
        V14 harvests same-app links from the static parent/list pages and opens
        at most one concrete URL per relevant dynamic pattern.
        """
        journey = journey or {}
        role = str(journey.get("role") or "").strip().lower()
        routes = self._journey_routes(journey, limit=limit)
        patterns = self._journey_dynamic_patterns(journey)
        key = (role, tuple(routes), tuple(patterns))
        if key in self._runtime_evidence_cache:
            return self._runtime_evidence_cache[key]
        if not routes and not patterns:
            return ""

        missing = [u for u in routes if (role, u) not in self._runtime_route_cache]
        dyn_key = (role, tuple(patterns))
        need_dynamic = bool(patterns and dyn_key not in self._runtime_dynamic_cache)
        if missing or need_dynamic:
            try:
                from playwright.sync_api import sync_playwright
            except Exception:
                return ""
            dynamic_blocks = []
            found_dynamic = set()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
                    self._install_route_loop_guard(ctx)
                    page = ctx.new_page()
                    try:
                        page.goto(self.base_url + "/", timeout=GOTO_TIMEOUT,
                                  wait_until="domcontentloaded")
                        self._wait_hydrated(page)
                    except Exception:
                        pass
                    acc = self.account_for(role) if role else {}
                    signed = self._sign_in(page, acc) if acc else True
                    for url in routes:
                        if acc and self._is_auth_route(url):
                            continue
                        if acc and not signed:
                            self._runtime_route_cache[(role, url)] = (
                                f"DOM preflight for {role or 'role'} at {url}: authentication did not establish a session")
                            continue
                        try:
                            page.goto(self.base_url + url, timeout=GOTO_TIMEOUT,
                                      wait_until="domcontentloaded")
                            self._wait_hydrated(page)
                            self._wait_app_settled(page)
                            block = self._selector_inventory(page, limit=22)
                            loop_fault = self._consume_route_loop_fault()
                            if loop_fault:
                                block = loop_fault + "\n" + block
                            if need_dynamic:
                                try:
                                    hrefs = page.eval_on_selector_all(
                                        'a[href]', "els => els.map(e => e.getAttribute('href')).filter(Boolean)")
                                except Exception:
                                    hrefs = []
                                for href in hrefs:
                                    h = str(href or "").strip()
                                    if not h.startswith("/"):
                                        continue
                                    hpath = h.split("?", 1)[0]
                                    pat = next((pat for pat in patterns
                                                if pat not in found_dynamic and self._matches_dynamic(pat, hpath)), "")
                                    if not pat:
                                        continue
                                    try:
                                        detail = ctx.new_page()
                                        detail.goto(self.base_url + h, timeout=GOTO_TIMEOUT,
                                                    wait_until="domcontentloaded")
                                        self._wait_hydrated(detail)
                                        self._wait_app_settled(detail)
                                        dynamic_blocks.append(
                                            f"Dynamic pattern {pat} resolved to real URL {h}\n" +
                                            self._selector_inventory(detail, limit=24))
                                        self._warmed_routes.add(hpath)
                                        found_dynamic.add(pat)
                                        detail.close()
                                    except Exception as e:
                                        log.debug(f"dynamic runtime evidence {h}: {e}")
                        except Exception as e:
                            block = f"DOM at {url}: navigation failed: {type(e).__name__}"
                        self._runtime_route_cache[(role, url)] = block
                        self._warmed_routes.add(url)
                    browser.close()
            except Exception as e:
                log.debug(f"runtime evidence: {e}")
            if patterns:
                self._runtime_dynamic_cache[dyn_key] = "\n\n".join(dynamic_blocks)[:9000]

        blocks = [self._runtime_route_cache.get((role, u), "") for u in routes]
        dyn = self._runtime_dynamic_cache.get(dyn_key, "")
        if dyn:
            blocks.append(dyn)
        text = "\n\n".join(b for b in blocks if b)[:18_000]
        self._runtime_evidence_cache[key] = text
        return text

    def invalidate_runtime_evidence(self):
        """A production edit may change selectors or route output; drop DOM cache."""
        self._runtime_evidence_cache.clear()
        self._runtime_route_cache.clear()
        self._runtime_dynamic_cache.clear()
        self._auth_route_cache = None
