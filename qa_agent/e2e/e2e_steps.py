"""E2E sweep and deterministic scenario step execution."""
from qa_agent.e2e.e2e_common import *
from qa_agent.e2e.e2e_semantics import resolve_runtime_value, semantic_words


class E2EStepsMixin:
    def sweep(self, page) -> list:
        """
        Open every page the app serves, signed in, and report what breaks.

        The scenario proves one journey works. This proves the rest of the app
        renders at all, and it runs on the context the flow just used — so the
        session cookie it earned is still attached. That is the whole point:
        `agents/build/tester.py` probes routes signed out, so an admin area answers
        with a redirect to its auth entry and its pages are never rendered.

        Measured on a real build: `/admin` logged five "Only plain objects can
        be passed to Client Components" errors — a server page passing lucide
        icons down to a client card — and returned HTTP 200 every time. No gate
        in the pipeline had ever seen that page.

        Returns `(route, message)` for each distinct fault.
        """
        if not self.az:
            return []
        try:
            routes = [u for u, m in sorted(self.az.enumerate_routes().items())
                      if m.get("kind") == "page" and not m.get("dynamic")
                      and not self.SWEEP_SKIP_RE.search(u)]
        except Exception as e:
            log.debug(f"sweep routes: {e}")
            return []
        if not routes:
            return []
        if len(routes) > self.SWEEP_CAP:
            self._log("WARN", f"   ⚠ {len(routes)} routes — sweeping the "
                              f"first {self.SWEEP_CAP}")
            routes = routes[:self.SWEEP_CAP]

        self._log("INFO", f"   🔍 Checking {len(routes)} page(s) while signed in")
        seen, out = set(), []
        for url in routes:
            try:
                resp = page.goto(self.base_url + url, timeout=GOTO_TIMEOUT,
                                 wait_until="domcontentloaded")
            except Exception as e:
                if "ERR_ABORTED" in str(e):
                    try:
                        page.wait_for_timeout(250)
                        resp = page.goto(self.base_url + url, timeout=GOTO_TIMEOUT,
                                         wait_until="domcontentloaded")
                    except Exception as again:
                        out.append((url, f"{type(again).__name__}: {again}"[:250]))
                        continue
                else:
                    out.append((url, f"{type(e).__name__}: {e}"[:250]))
                    continue

            status = resp.status if resp else None
            if status and status >= 400:
                body = ""
                try:
                    body = page.inner_text("body")[:250]
                except Exception:
                    pass
                out.append((url, f"HTTP {status}. {body}".strip()))
                continue

            msg = overlay_error(page)
            if not msg or len(msg) <= 15:
                continue

            key = msg.splitlines()[0][:90]
            if key in seen:
                self._log("INFO", f"   ↳ {url} — same fault again")
                continue
            seen.add(key)
            out.append((url, msg[:500]))

        if out:
            self._log("WARN", f"   ❌ {len(out)} page(s) broken while signed in")
        else:
            self._log("INFO", "   ✅ every page rendered clean")
        return out

    def _auth_bounce(self, page, intended: str):
        """`None` when fine; a failure tuple only when the app truly rejects.

        A protected page silently swapping itself for an auth entry is the single
        symptom behind most "nothing matched <control>" reports: the control
        was never absent, the page was. Two cases, told apart by the session:

          • session dead  — cookies got lost somewhere; re-login through the
            auth API and take the same route again. Costs one request, saves
            a whole agentic round.
          • session alive — the page's own guard rejects a valid session.
            That is an app defect with a known owner, so say exactly that
            instead of letting the next selector report the wrong thing.
        """
        intended = str(intended or "").split("?", 1)[0].rstrip("/") or "/"
        if intended == "/" or self._is_auth_route(intended):
            return None
        here = self._route_from_page(page)
        if not self._is_auth_route(here):
            return None
        journey = getattr(self, "_active_journey", {}) or {}
        role = str(journey.get("role") or "").strip().lower()
        if not role or role in set(getattr(self, "_SIGNED_OUT", ()) or ()):
            return None
        acc = self.account_for(role)
        if not acc:
            return None
        try:
            if not self._session_alive(page, timeout_ms=1500):
                if self._sign_in(page, acc):
                    page.goto(self.base_url + intended,
                              timeout=GOTO_TIMEOUT,
                              wait_until="domcontentloaded")
                    self._wait_hydrated(page)
                    if not self._is_auth_route(self._route_from_page(page)):
                        self._log("INFO", f"   🔐 session re-established — "
                                          f"{intended} reached on retry")
                        return None
        except Exception as e:
            log.debug(f"auth bounce recovery {intended}: {e}")
        src = self._page_for(intended)
        auth_route = self.entry_route() or self._route_from_page(page) or "the auth entry"
        return (KIND_BEHAVIOR,
                f"{intended} redirected an authenticated {role} session to "
                f"{auth_route} — the guard in {src or 'that page'} rejects a live "
                f"session instead of the missing one it was written for")

    @staticmethod
    def _is_business_step(st) -> bool:
        """Whether a successful step has started the feature mutation itself."""
        if st.verb == "SELECT":
            return False
        if st.verb != "CLICK":
            return False
        sel = getattr(st, "selector", None)
        text = " ".join([str(getattr(sel, "pattern", "") or ""),
                         str(getattr(sel, "role", "") or "")]).lower()
        return bool(re.search(
            r"\b(?:add|apply|approve|book|buy|cancel|complete|confirm|"
            r"create|delete|mark|pay|purchase|reject|remove|reserve|save|send|"
            r"submit|update)\b", text))

    @staticmethod
    def _concept_words(text: str) -> set:
        return semantic_words(text)

    def _route_for_page_copy(self, sel) -> str:
        """Best concrete workflow route described by a missing page-copy check."""
        if not getattr(self, "_active_journey", None):
            return ""
        desired = self._concept_words(getattr(sel, "pattern", ""))
        if not desired:
            return ""
        best = (0, "")
        try:
            routes = self._journey_routes(self._active_journey)
        except Exception:
            routes = []
        for url in routes:
            if url == "/" or self._is_auth_route(url) or "[" in url:
                continue
            got = self._concept_words(url.replace("/", " "))
            score = len(desired & got)
            if score > best[0]:
                best = (score, url)
        return best[1] if best[0] else ""

    def _recover_page_identity(self, page, st) -> bool:
        """Turn guessed pre-work copy into an exact journey-route assertion.

        This is intentionally limited to the setup portion of a journey. Once a
        price/status/booking mutation has started, text is evidence of the result
        and we must not navigate around a failing assertion.
        """
        if getattr(self, "_business_started", False):
            return False
        sel = getattr(st, "selector", None)
        if not sel or getattr(sel, "kind", "") not in {"text", "role"}:
            return False
        target = self._route_for_page_copy(sel)
        if not target:
            return False
        current = self._route_from_page(page)
        if current == target:
            # We are already on the semantic route.
            st.verb = "EXPECT_URL"
            st.selector = Selector(kind="text", pattern=re.escape(target),
                                   flags="", is_regex=True)
            self._scenario_changed = True
            self._log("INFO", f"   ↪ page identity recovered from copy → URL {target}")
            return True
        try:
            resp = page.goto(self.base_url + target, timeout=GOTO_TIMEOUT,
                             wait_until="load")
            if resp and resp.status >= 400:
                return False
            self._wait_hydrated(page)
        except Exception:
            return False
        st.verb = "GOTO"
        st.value = target
        st.selector = None
        self._scenario_changed = True
        self._log("INFO", f"   ↪ page identity recovered from copy → GOTO {target}")
        return True

    def _step(self, page, st, next_step=None):
        """`None` when the step passed, else `(kind, message)`.

        Selector recovery is deterministic and observation-driven. It never
        edits application code: it only replaces a brittle scenario locator
        with an equivalent locator that exists in the DOM, then mutates the
        Scenario so the exported Playwright spec uses the same locator.
        """
        if st.verb == "GOTO":

            try:
                resp = page.goto(self.base_url + st.value, timeout=GOTO_TIMEOUT,
                                 wait_until="domcontentloaded")
            except Exception as e:
                if "ERR_ABORTED" not in str(e):
                    raise
                page.wait_for_timeout(250)
                resp = page.goto(self.base_url + st.value, timeout=GOTO_TIMEOUT,
                                 wait_until="domcontentloaded")
            if resp and resp.status >= 500:
                body = ""
                try:
                    body = page.inner_text("body")[:300]
                except Exception:
                    pass
                return (KIND_CRASH, f"{st.value} returned HTTP {resp.status}"
                                    + (f"\n{body}" if body else ""))
            if resp and resp.status >= 400:
                return (KIND_CRASH, f"{st.value} returned HTTP {resp.status}")
            self._wait_hydrated(page)
            self._wait_app_settled(page, timeout=1400)
            bounce = self._auth_bounce(page, st.value)
            if bounce:
                return bounce
            return None

        if st.verb in ("FILL", "SELECT", "CLICK", "WAIT_FOR"):
            loc, replacement, note = self._smart_locator(
                page, st.selector, verb=st.verb, next_step=next_step)
            if replacement is not None:
                old = st.selector.describe()
                st.selector = replacement
                self._scenario_changed = True
                self._log("INFO", f"   ↪ selector recovered: {old} → "
                                  f"{replacement.describe()}"
                                  + (f" ({note})" if note else ""))
            if loc is None or self._count(loc) == 0:
                if st.verb == "WAIT_FOR" and self._recover_page_identity(page, st):
                    return None
                # A control cannot match on a page we were bounced off of.
                bounce = self._auth_bounce(
                    page, getattr(self, "_intended_route", "") or "")
                if bounce:
                    return bounce
                inv = self._selector_inventory(page)
                kind = (KIND_BEHAVIOR if st.verb == "WAIT_FOR" and
                        getattr(self, "_business_started", False) else KIND_SELECTOR)
                return (kind,
                        f"nothing matched {st.selector.describe()}"
                        + (f"\n{inv}" if inv else ""))
            loc = loc.first
            loc.wait_for(state="visible", timeout=STEP_TIMEOUT)
            if st.verb == "FILL":
                loc.fill(resolve_runtime_value(st.value), timeout=STEP_TIMEOUT)
            elif st.verb == "SELECT":
                # Prefer the human-visible option label; fall back to its value.
                value = resolve_runtime_value(st.value)
                try:
                    loc.select_option(label=value, timeout=STEP_TIMEOUT)
                except Exception:
                    loc.select_option(value, timeout=STEP_TIMEOUT)
            elif st.verb == "CLICK":
                active = getattr(self, "_active_scenario", None)
                try:
                    active_index = int(getattr(self, "_active_step_index", -1))
                except Exception:
                    active_index = -1
                auth_click = (is_auth_submit_step(active, active_index)
                              if active is not None else self._is_auth_action(st))
                loc.click(timeout=STEP_TIMEOUT)
                page.wait_for_timeout(350)
                if auth_click:
                    if not self._session_alive(page):
                        return (KIND_BEHAVIOR,
                                "sign-in returned, but no authenticated browser "
                                "session was established")
            return None

        if st.verb == "EXPECT_TEXT":
            deadline = time.time() + ASSERT_TIMEOUT / 1000
            pat, seen = st.selector.compiled(), ""
            while time.time() < deadline:
                try:
                    seen = page.inner_text("body")
                except Exception:
                    seen = ""
                if (pat.search(seen) if hasattr(pat, "search")
                        else pat.lower() in seen.lower()):
                    return None
                page.wait_for_timeout(400)
            if self._recover_page_identity(page, st):
                return None
            kind = KIND_BEHAVIOR if getattr(self, "_business_started", False) else "ASSERTION"
            return (kind,
                    f"the page never showed {st.selector.describe()}\n"
                    f"what it showed: {seen[:300]}")

        if st.verb == "EXPECT_URL":
            deadline = time.time() + ASSERT_TIMEOUT / 1000
            pat, url = st.selector.compiled(), page.url
            while time.time() < deadline:
                url = page.url
                if (pat.search(url) if hasattr(pat, "search") else pat in url):
                    return None
                page.wait_for_timeout(300)
            kind = KIND_BEHAVIOR if getattr(self, "_business_started", False) else "ASSERTION"
            return (kind, f"the url stayed at {url}, expected "
                          f"{st.selector.describe()}")

        if st.verb == "EXPECT_VALUE":
            loc, replacement, note = self._smart_locator(
                page, st.selector, verb=st.verb, next_step=next_step)
            if replacement is not None:
                old = st.selector.describe()
                st.selector = replacement
                self._scenario_changed = True
                self._log("INFO", f"   ↪ selector recovered: {old} → "
                                  f"{replacement.describe()}"
                                  + (f" ({note})" if note else ""))
            if loc is None or self._count(loc) == 0:
                kind = (KIND_BEHAVIOR if getattr(self, "_business_started", False)
                        else KIND_SELECTOR)
                return (kind,
                        f"nothing matched {st.selector.describe()}\n"
                        + self._selector_inventory(page))
            deadline = time.time() + ASSERT_TIMEOUT / 1000
            seen = ""
            while time.time() < deadline:
                try:
                    seen = loc.first.input_value(timeout=2000)
                except Exception:
                    try:
                        seen = loc.first.get_attribute("value") or ""
                    except Exception:
                        seen = ""
                if str(seen) == str(resolve_runtime_value(st.value)):
                    return None
                page.wait_for_timeout(300)
            return (KIND_BEHAVIOR,
                    f"{st.selector.describe()} stayed at {seen!r}, "
                    f"expected {resolve_runtime_value(st.value)!r}")

        if st.verb == "EXPECT_MUTATION":
            deadline = time.time() + ASSERT_TIMEOUT / 1000
            while time.time() < deadline:
                events = list(getattr(self, "_active_mutation_events", []) or [])
                start = int(getattr(self, "_mutation_mark", 0) or 0)
                business = [row for row in events[start:]
                            if not self._is_auth_api_url(str(row.get("url") or ""))]
                if business:
                    return None
                page.wait_for_timeout(250)
            return (KIND_BEHAVIOR,
                    "the action produced no successful non-auth mutation request")

        if st.verb == "EXPECT_NO_ERROR":
            return None
        return None

    @staticmethod
    def _wait_hydrated(page):
        """
        Wait until React has attached its handlers.

        This is the single most important line in the runner, and it was
        missing. Playwright acts within milliseconds of `load`, and until
        hydration finishes a `'use client'` page is inert markup: the click
        lands on a real, enabled, correctly-named submit button and **nothing
        happens** — no request, no error, no console message. The run then
        reports "the url stayed at the auth entry" about an app whose login is
        provably fine, which is the worst possible output for this stage.
        Measured: with no wait the click was lost; with one, the same flow
        signs in and redirects.

        React writes `__reactFiber$…` / `__reactProps$…` keys onto the DOM
        nodes it owns during hydration, and only then, so their presence is the
        signal. Failing to find it is never fatal — a short settle and carry on
        is better than refusing to test.
        """
        try:
            page.wait_for_function(
                """() => {
                    const el = document.querySelector('button, input, a[href]')
                    return !!el && Object.keys(el).some(
                        (k) => k.startsWith('__react'))
                }""", timeout=HYDRATE_TIMEOUT)
        except Exception:
            page.wait_for_timeout(1500)

    @staticmethod
    def _wait_app_settled(page, timeout: int = 2600):
        """Wait briefly for a data-driven page to become actionable.

        A checkpoint/navigation can return a valid 200 while the DOM contains
        only `Loading.` for a few hundred milliseconds.  Looking up Checkout
        during that window produced a false selector miss and an LLM repair.
        This is a bounded readiness wait, not network-idle (which never arrives
        for many auth-enabled dev pages).
        """
        try:
            page.wait_for_function(
                """() => {
                    const txt=(document.body?.innerText||'').trim().toLowerCase();
                    if (!txt || /^(loading[.…]*|please wait[.…]*)$/.test(txt)) return false;
                    const busy=[...document.querySelectorAll('[aria-busy="true"]')];
                    return busy.length===0;
                }""", timeout=timeout)
        except Exception:
            try:
                page.wait_for_timeout(180)
            except Exception:
                pass

    def warm(self, sc):
        """
        Visit each page the flow will reach, once, before the flow runs.

        `next dev` compiles a route on its first request, so the first visit
        can take many seconds — and when that visit is a client-side navigation
        after a click, the wait is charged to the assertion that follows and
        reads as "the app never navigated". Paying it up front, over plain
        HTTP, makes the assertions measure the app rather than the compiler.
        """
        import requests

        targets = {st.value for st in sc.steps if st.verb == "GOTO"}

        known = list((self.az.enumerate_routes() if self.az else {}) or {})
        for st in sc.steps:
            if st.verb == "EXPECT_URL" and st.selector:
                for url in known:
                    if url != "/" and url.strip("/") in st.selector.pattern:
                        targets.add(url)
        todo = [path for path in sorted(targets) if path not in self._warmed_routes]
        if todo:
            # Next dev compiles first-hit routes independently. Warm a few in
            # parallel so a six-page journey does not pay six sequential
            # compiler stalls before the browser can start. Keep the pool small
            # to avoid overwhelming low-memory local machines.
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def hit(path):
                try:
                    requests.get(self.base_url + path, timeout=12)
                    return path, ""
                except Exception as e:
                    return path, str(e)

            with ThreadPoolExecutor(max_workers=min(3, len(todo))) as pool:
                futures = [pool.submit(hit, path) for path in todo]
                for fut in as_completed(futures):
                    path, error = fut.result()
                    if error:
                        log.debug(f"warm {path}: {error}")
                    else:
                        self._warmed_routes.add(path)
        return sorted(targets)
