"""
The end-to-end pass: sign in as a real seeded account and use the app.

This is the only gate in AgentForge that exercises a page. Unit tests cannot:
Next's own bundled documentation says Vitest does not support async Server
Components, which is every page that reads data. The route probe proves a page
returns 200; nothing until here proves that filling the login form and pressing
the button actually signs you in.

Two decisions shape the whole file.

**The model writes a scenario, not code.** `flows.py` maps each line to one
fixed Python call, so nothing the model produced is ever executed in AgentForge's
process. The same parsed scenario is also emitted as a real
`tests/e2e/<flow>.spec.js`, which the user can run and export — generated from
the parsed form, so what AgentForge ran and what ships cannot diverge.

**AgentForge runs it through the Python Playwright it already has.** Measured on
this machine: `playwright==1.60.0` wants chromium **1223**, which is already in
`~/AppData/Local/ms-playwright`. So the run costs no npm install and no browser
download, while `npx playwright test` would cost ~50 MB per project and might
want a revision that is not cached. The `.spec.js` is the deliverable; the
Python path is the runner.

Failures are split before anyone is asked to fix anything, because the two
kinds mean opposite things:

* **the scenario is wrong** — a control it named does not exist. That is the
  model's description being off, not the app being broken, and it costs one
  re-author, never a code edit.
* **the app is broken** — a 500, an uncaught exception, an assertion about
  content that is genuinely absent. Only these reach the bug fixer.
"""
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from agents.architect import FileStreamParser
from agents.tester import overlay_error

from .flows import (CLICKABLE_CSS, GRAMMAR, PLAYWRIGHT_CONFIG, Scenario,
                    parse_scenario, to_playwright_js)
from .session import QASession
from .spec import TestFailure

log = logging.getLogger("qa.e2e")

TEMPERATURE = 0.3
STEP_TIMEOUT = 15_000


ASSERT_TIMEOUT = 30_000
GOTO_TIMEOUT = 45_000
HYDRATE_TIMEOUT = 15_000
MAX_FLOWS = 2
MAX_REAUTHOR = 1


KIND_CRASH = "CRASH"
KIND_SELECTOR = "SELECTOR"

SYSTEM = """\
You describe ONE end-to-end user journey through a Next.js app, as a scenario.

You are NOT writing code. You emit only the lines below, and AgentForge runs them
with a real browser. Anything that is not one of these verbs is discarded.

""" + GRAMMAR + """
RULES THAT DECIDE WHETHER THIS WORKS
  • Selectors must be REGEXES WITH ALTERNATION, because the exact wording
    varies per app: use /sign in|log in|login/i, never 'Sign In'. A scenario
    that pins exact wording fails on an app that is working perfectly.
  • For a TEXT INPUT, reach for `placeholder=` first, then
    `role=textbox name=…`. Do NOT use `label=` unless the field has no
    placeholder: a `<label>` only matches when it is tied to the input by
    htmlFor/id, and measured across this codebase only 6 of 57 labelled forms
    are — so `label=/email/i` finds nothing on a login form that works
    perfectly. `placeholder=` is present on 60 of 76 forms and is reliable.
  • CLICK must name a control: `role=button name=/…/i` or
    `role=link name=/…/i`. A bare text match is ambiguous with prose — a login
    page whose heading reads "Sign in to manage your tickets" puts that
    sentence before the button, so `text=/sign in/i` matches the paragraph.
  • NEVER click a control and then refer to it again. A submit button becomes
    "Signing in..." the moment it is pressed, so the second lookup finds
    nothing and reports a bug that does not exist.
  • Assert something the seeded data guarantees. Do not assert a number, a
    date, or a name you are guessing at.
  • Prefer the shortest journey that proves the feature works end to end:
    sign in, reach the page that needs the session, see the thing that only
    a signed-in user sees.
  • Between 4 and 12 steps. Finish with DONE.

Emit the scenario and nothing else — no explanation, no code fences.
"""


class E2EAgent:
    """Author a journey, run it, and say what actually broke."""

    def __init__(self, arch, project_dir=None, *, callbacks=None, session=None,
                 analyzer=None, base_url="http://localhost:5173"):
        self.arch = arch
        self.project_dir = Path(project_dir or arch.project_dir)
        self.cb = callbacks or {}
        self.qa = session
        self.az = analyzer
        self.base_url = base_url.rstrip("/")
        self.scenarios = []

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

    def account_for(self, role) -> dict:
        accs = self.accounts()
        if not accs:
            return {}
        if role:
            for a in accs:
                if (a.get("role") or "").lower() == role.lower():
                    return a
        return accs[0]

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
            return fp.read_text(encoding="utf-8", errors="replace")[:cap] \
                if fp.is_file() else ""
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
            for url, meta in (self.az.enumerate_routes() or {}).items():
                if meta.get("kind") == "page" and re.search(
                        r"log[-_ ]?in|sign[-_ ]?in", url, re.I):
                    return meta.get("file", "")
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
    JOURNEY_PAGES = 6

    def _journey_pages(self) -> list:
        """
        The page files a journey is likely to walk through.

        Entry and landing first, because every journey signs in and then lands
        — then the app's other pages, shallowest route first, since that is
        where a journey goes. Only two pages used to be shown, and a journey
        touches four or five: the flow that failed on this build asked for a
        placeholder matching /collection date/i, which lives on the reservation
        page, which the model was never shown and could only invent. Every
        selector a scenario writes should come from markup it has read.
        """
        out = [self.entry_page(), self.landing_page()]
        if not self.az:
            return [p for p in out if p]
        try:
            routes = self.az.enumerate_routes() or {}
        except Exception as e:
            log.debug(f"journey pages: {e}")
            return [p for p in out if p]
        rest = [(url, meta.get("file", "")) for url, meta in routes.items()
                if meta.get("kind") == "page" and not meta.get("dynamic")
                and "[" not in url]
        rest.sort(key=lambda t: (t[0].count("/"), t[0]))
        for _, f in rest:
            if f and f not in out:
                out.append(f)
        return [p for p in out if p][:self.JOURNEY_PAGES]

    def author(self, previous: Scenario = None, why: str = "",
               page: str = "") -> Scenario:
        """One model call. Returns a parsed scenario — possibly an empty one."""
        accs = self.accounts()
        roles = ", ".join(sorted({(a.get("role") or "user") for a in accs})) \
            or "there are no demo accounts — write a signed-out journey"
        idea = self._idea()

        ask = (f"## The app\n{idea}\n\n"
               f"## Pages and endpoints it serves\n{self._routes() or '  (unknown)'}\n\n"
               f"## Demo accounts available\nRoles: {roles}\n"
               f"Use {{{{email}}}} and {{{{password}}}} — AgentForge fills in the "
               f"real values for the role you name with AS.\n")

        shown = ([page] if page else []) + self._journey_pages()
        blocks, used = [], 0
        for rel in dict.fromkeys(s for s in shown if s):
            block = self.markup_for(rel)
            if not block:
                continue
            if used + len(block) > self.MARKUP_BUDGET and blocks:
                break
            blocks.append(block)
            used += len(block)
        body = "\n\n".join(blocks)
        if body:
            ask += (f"\n## The real markup\n```jsx\n{body}\n```\n"
                    f"Copy the placeholders, button labels and visible text "
                    f"above into your selectors. Do not guess at wording that "
                    f"is written down right here — and do not assert text that "
                    f"is not in it.\n")

        ask += ("\nWrite ONE scenario for the most important journey this app "
                "exists to support.")
        if previous is not None and why:
            ask += (f"\n\n## Your previous scenario did not work\n{why}\n\n"
                    f"It was:\n{self._render(previous)}\n\n"
                    f"Write it again. Match the markup above exactly where it "
                    f"is shown, and widen the selectors that missed.")

        convo = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": ask}]
        raw = []
        parser = FileStreamParser(on_text=lambda t: raw.append(t),
                                  on_file_start=lambda p: None,
                                  on_file_token=lambda t: None,
                                  on_file_end=lambda p, c: None)
        try:
            self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                              model=QASession.model_for(self.qa, self.arch))
        except Exception as e:
            self._log("WARN", f"   ⚠ could not write an end-to-end flow: {e}")
            return Scenario()
        parser.close()

        text = "".join(raw)
        sc = parse_scenario(text, account=self.account_for(
            self._role_in(text)))
        for _, line, reason in sc.dropped[:4]:
            self._log("WARN", f"   ⚠ dropped `{line}` — {reason}")
        return sc

    @staticmethod
    def _role_in(text):
        m = re.search(r"^\s*(?:AS|ROLE)\s*::\s*(.+)$", text or "", re.M | re.I)
        role = (m.group(1).strip().lower() if m else "")
        return "" if role in ("guest", "anonymous", "none") else role

    def _idea(self):
        try:
            convo = getattr(self.arch, "convo", None) or []
            if len(convo) > 1 and convo[1].get("role") == "user":
                return convo[1]["content"][:3000]
        except Exception:
            pass
        return (getattr(self.arch, "plan_md", "") or "")[:3000]

    @staticmethod
    def _render(sc: Scenario) -> str:
        lines = [f"FLOW :: {sc.title}", f"AS :: {sc.role or 'GUEST'}"]
        lines += [s.describe() for s in sc.steps]
        return "\n".join(lines)

    def write_spec(self, sc: Scenario) -> str:
        """
        Write the scenario as a real Playwright spec in the project.

        Not through `arch.write_file`: a spec under `tests/` must never enter
        `arch.files`, where `unresolved_packages()` would report
        `@playwright/test` as a missing import mid-build.
        """
        rel = sc.spec_path()
        try:
            fp = self.project_dir / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            body = to_playwright_js(sc, base_url=self.base_url)
            fp.write_text(body, encoding="utf-8")
            cfg = self.project_dir / "playwright.config.js"
            if not cfg.is_file():
                cfg.write_text(PLAYWRIGHT_CONFIG, encoding="utf-8")
        except Exception as e:
            self._log("WARN", f"   ⚠ could not write {rel}: {e}")
            return ""
        size = f"{len(body) / 1024:.1f}KB" if len(body) >= 1024 else f"{len(body)}B"
        self._fire("on_file_written", rel, size, body)
        self._log("INFO", f"   🎭 {rel}")
        return rel

    def run(self, sc: Scenario) -> list:
        """
        Drive the scenario in a real browser. Returns `TestFailure`s.

        Every step is a fixed Python call chosen by verb; the model's text is
        data throughout.
        """
        try:
            from playwright.sync_api import TimeoutError as PWTimeout
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self._log("WARN", f"   ⚠ Playwright is not available: {e}")
            return []

        self.warm(sc)
        spec = sc.spec_path()
        failures, problems, net = [], [], []
        route = "/"

        def fail(kind, name, message, stack=""):
            failures.append(TestFailure(
                test_file=spec, target=self._page_for(route), name=name[:200],
                message=message[:400], stack=stack[:2000], kind=kind))

        def context(n=6):
            """What the browser saw, console first and then the requests."""
            return "\n".join(problems[-n:] + net[-n:])

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.on("pageerror", lambda e: problems.append(f"PageError: {e}"))

            def _console(m):
                if m.type != "error":
                    return
                url = (m.location or {}).get("url") or ""
                problems.append(f"{m.text}  [{url}]" if url else m.text)

            page.on("console", _console)

            def _response(r):
                if r.status < 400:
                    return
                body = ""
                try:
                    body = " ".join(r.text().split())[:200]
                except Exception:
                    pass
                net.append(f"HTTP {r.status} {r.request.method} {r.url}"
                           + (f" — {body}" if body else ""))

            page.on("response", _response)

            try:
                for st in sc.steps:
                    if st.verb == "GOTO":
                        route = st.value
                    label = st.describe()
                    try:
                        err = self._step(page, st)
                    except PWTimeout:

                        if st.verb == "GOTO":
                            err = (KIND_CRASH,
                                   f"{st.value} never finished loading within "
                                   f"{GOTO_TIMEOUT // 1000}s")
                        elif st.selector:
                            err = (KIND_SELECTOR,
                                   f"nothing matched {st.selector.describe()}")
                        else:
                            err = (KIND_CRASH, "the step timed out")
                    except Exception as e:
                        err = (KIND_CRASH, f"{type(e).__name__}: {e}")
                    if err:
                        kind, msg = err
                        self._test("fail", label, msg)
                        fail(kind, label, msg, context())
                        break
                    self._test("pass", label)
                else:

                    for r, msg in self.sweep(page):
                        route = r
                        self._test("fail", f"{r} is broken", msg)
                        fail(KIND_CRASH, f"{r} is broken", msg, context())
                    for r, msg, seen in self.role_separation(page):
                        route = r
                        self._test("fail", f"{r} is not protected", msg)

                        fail(KIND_CRASH, f"{r} is not protected", msg,
                             seen + "\n" + context())
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        real = [p for p in problems if not _is_noise(p)]
        if real and not failures:
            fail(KIND_CRASH, "the page logged an error",
                 real[0][:300], "\n".join(real[:6]))
        return failures

    SWEEP_SKIP_RE = re.compile(r"log[-_ ]?out|sign[-_ ]?out", re.I)
    def _sign_in(self, page, acc) -> bool:
        """
        Sign in through Better Auth's own endpoint, not through the form.

        The form is what the scenario tests and it is the wrong tool here: this
        check needs to switch role four times in a row, and driving a login
        form four times turns a fast check into a slow one and couples it to
        whatever the login page looks like this build.
        """
        try:

            page.context.clear_cookies()
            page.evaluate(
                """async ({ email, password }) => {
                    const r = await fetch('/api/auth/sign-in/email', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password }),
                    });
                    if (!r.ok) throw new Error('sign-in ' + r.status);
                }""",
                {"email": acc.get("email"), "password": acc.get("password")})
            return True
        except Exception as e:
            log.debug(f"sign in as {acc.get('email')}: {e}")
            return False

    def role_separation(self, page) -> list:
        """
        Every demo role, against every other role's pages.

        The sweep signs in as ONE role and asks whether each page renders. It
        has no opinion about whether a page that renders SHOULD have, and that
        is where the real hole was: a clinic where `/reception` correctly
        bounced a nurse and `/reception/book` — the page that creates
        appointments — answered them 200, because Next does not inherit guards
        and that page was a Client Component with no session to read. The
        browser pass, the route probe and the unit tests all passed the app.

        The check needs no knowledge of the app's rules. If signing in as role
        A can reach a page that redirects role B, that page belongs to A; if
        role B reaches it too, either it is public — in which case nobody is
        redirected from it — or it is a hole. Only routes that SOMEONE is
        bounced from are considered, so a wholly public app reports nothing.

        Returns `(route, message)` for each page reachable by a role that
        another page in the same section refuses.
        """
        accs = [a for a in self.accounts() if a.get("role")]
        if len(accs) < 2:
            return []
        try:
            routes = [u for u, m in sorted(self.az.enumerate_routes().items())
                      if m.get("kind") == "page" and "[" not in u
                      and u not in ("/login", "/signup", "/")]
        except Exception as e:
            log.debug(f"role separation routes: {e}")
            return []
        if not routes:
            return []
        routes = routes[:self.SWEEP_CAP]

        self._log("INFO", f"   🔒 Checking {len(routes)} page(s) against "
                          f"{len(accs)} role(s)")

        reach = {}
        for acc in accs:
            role = acc.get("role") or acc.get("email", "?")
            if not self._sign_in(page, acc):
                log.debug(f"role separation: could not sign in as {role}")
                continue
            opened = set()
            for url in routes:
                try:
                    page.goto(self.base_url + url, timeout=GOTO_TIMEOUT,
                              wait_until="domcontentloaded")

                    if _landed_on(page.url, url):
                        opened.add(url)
                except Exception as e:
                    log.debug(f"role separation {role} {url}: {e}")
            reach[role] = opened

        allowed = {u: {r for r, o in reach.items() if u in o} for u in routes}
        sections = {}
        for u in routes:
            sections.setdefault(u.strip("/").split("/")[0], []).append(u)

        out = []
        for name, urls in sections.items():
            if len(urls) < 2:
                continue

            tightest = min(allowed[u] for u in urls if allowed[u]) \
                if any(allowed[u] for u in urls) else set()
            if not tightest or len(tightest) >= len(reach):
                continue
            for u in urls:
                extra = allowed[u] - tightest

                extra = {r for r in sorted(extra)
                         if self._still_open(page, u, r, accs)}
                if extra:
                    out.append((u, f"/{name} admits only "
                                   f"{', '.join(sorted(tightest))}, and {u} "
                                   f"also opens for "
                                   f"{', '.join(sorted(extra))} — the guard on "
                                   f"the section is missing from this page",
                                self._reach_table(urls, reach)))
        return out

    @staticmethod
    def _reach_table(urls, reach) -> str:
        """
        The measurement the finding is made of: who reached what.

        A claim travelling without the observation behind it is how twelve
        repair rounds got spent on a status code nobody could attribute. The
        conclusion — "the guard is missing" — is an inference; this is the
        reading it was inferred from, so whoever reads it next can check the
        inference instead of taking it.
        """
        wide = max((len(u) for u in urls), default=10)
        lines = ["what each role reached (the reading this is based on):"]
        for role in sorted(reach):
            got = ", ".join(f"{u}{'  OPEN' if u in reach[role] else '  redirected'}"
                            for u in sorted(urls))
            lines.append(f"  {role:>10}: {got}")
        del wide
        return "\n".join(lines)

    def _still_open(self, page, url, role, accs) -> bool:
        """
        Ask again, down a different road, before calling a page unguarded.

        Re-running the same navigation would re-run its bug with it, so this
        does not: it takes the session cookie the browser earned and makes a
        plain HTTP request with redirects switched OFF, then reads the status
        code directly. No rendering, no final-URL inference, no Playwright —
        the two measurements share only the app.

        That matters because the first measurement is a single reading of
        `page.url` after one navigation, and one flaky reading accuses a page
        that is correctly guarded. Measured on a nursery build:
        `/grower/add-plant` was reported open to the owner, and re-checked over
        HTTP it answered 307 to `/` every time, exactly like the `/grower` page
        beside it. The cost of being wrong is not a wasted round — it is the
        repair loop rewriting a guard that was right.

        Anything that stops the re-check — no account for the role, no cookie,
        a request that will not go through — KEEPS the finding. This can only
        ever remove a claim it actively disproved.
        """
        acc = next((a for a in accs if (a.get("role") or "") == role), None)
        if not acc:
            return True
        if not self._sign_in(page, acc):
            return True
        try:
            jar = {c["name"]: c["value"] for c in page.context.cookies()}
        except Exception as e:
            log.debug(f"re-check {role} {url}: no cookies: {e}")
            return True
        if not jar:
            return True
        try:
            r = requests.get(self.base_url + url, cookies=jar,
                             allow_redirects=False, timeout=20)
        except Exception as e:
            log.debug(f"re-check {role} {url}: {e}")
            return True
        if r.status_code in (301, 302, 303, 307, 308):
            self._log("INFO", f"   ✓ {url} answers {role} with "
                              f"{r.status_code} → {r.headers.get('location', '?')}"
                              f" — it is guarded, not reporting it")
            return False
        return True

    SWEEP_CAP = 25

    def sweep(self, page) -> list:
        """
        Open every page the app serves, signed in, and report what breaks.

        The scenario proves one journey works. This proves the rest of the app
        renders at all, and it runs on the context the flow just used — so the
        session cookie it earned is still attached. That is the whole point:
        `agents/tester.py` probes routes signed out, so an admin area answers
        with a redirect to /login and its pages are never rendered by anything.

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
                                 wait_until="load")
            except Exception as e:
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

    def _step(self, page, st):
        """`None` when the step passed, else `(kind, message)`."""
        if st.verb == "GOTO":

            resp = page.goto(self.base_url + st.value, timeout=GOTO_TIMEOUT,
                             wait_until="load")
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
            return None

        if st.verb in ("FILL", "CLICK", "WAIT_FOR"):
            loc = self._locator(page, st.selector,
                                clickable=st.verb == "CLICK").first
            loc.wait_for(state="visible", timeout=STEP_TIMEOUT)
            if st.verb == "FILL":
                loc.fill(st.value, timeout=STEP_TIMEOUT)
            elif st.verb == "CLICK":
                loc.click(timeout=STEP_TIMEOUT)

                page.wait_for_timeout(700)
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
            return ("ASSERTION",
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
            return ("ASSERTION", f"the url stayed at {url}, expected "
                                 f"{st.selector.describe()}")

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
        reports "the url stayed at /login" about an app whose login is
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
        for path in sorted(targets):
            try:
                requests.get(self.base_url + path, timeout=60)
            except Exception as e:
                log.debug(f"warm {path}: {e}")
        return sorted(targets)

    @staticmethod
    def _locator(page, sel, clickable=False):
        """
        Must mirror `Selector.js_locator` exactly — the emitted spec and this
        run are supposed to be the same test, and a locator that differs
        between them is a spec that passes here and fails for the user.
        """
        if sel.kind == "role":
            return page.get_by_role(sel.role, name=sel.compiled())
        if sel.kind == "label":
            return page.get_by_label(sel.compiled())
        if sel.kind == "placeholder":
            return page.get_by_placeholder(sel.compiled())
        if sel.kind == "testid":
            return page.get_by_test_id(sel.pattern)
        if clickable:

            return page.locator(CLICKABLE_CSS).filter(has_text=sel.compiled())
        return page.get_by_text(sel.compiled())

    def _page_for(self, url) -> str:
        """The file that renders `url`, so a real failure has a target."""
        if not self.az:
            return ""
        try:
            meta = self.az.enumerate_routes().get(url or "/") or {}
            return meta.get("file", "")
        except Exception:
            return ""


_NOISE = ("[Fast Refresh]", "webpack-hmr", "Download the React DevTools",
          "[browser]", "hydrat", "favicon.ico", "DevTools")


def _is_noise(text: str) -> bool:
    return any(n.lower() in (text or "").lower() for n in _NOISE)


def _landed_on(current: str, route: str) -> bool:
    """
    Whether the browser is on `route` — the whole path, not the tail of it.

    `current.rstrip("/").endswith(route)` was close enough to pass and wrong
    in a way that matters: `http://x` ends with `/x`, so a short route matched
    the bare origin the guard had just redirected to, and a page that
    correctly bounced somebody was recorded as having let them in. Whether a
    guard fired is the entire question this file answers.
    """
    try:
        path = urlparse(current or "").path or "/"
    except Exception:
        return False
    return path.rstrip("/") == (route or "/").rstrip("/")
