"""Scenario grounding, rendering and spec persistence."""
from datetime import date
import re
from qa_agent.e2e.e2e_common import *
from qa_agent.e2e.e2e_semantics import (is_iso_date, relative_date_token,
                                        semantic_words)

class E2EGroundingMixin:
    _FIELD_ALIASES = {
        "email": ("email", "e-mail"),
        "password": ("password", "passcode", "passwd"),
        "phone": ("phone", "mobile", "telephone", "tel"),
        "name": ("name", "full name", "first name", "last name"),
        "date": ("date",),
        "number": ("number",),
        "search": ("search",),
    }

    @staticmethod
    def _date_field_words(evidence: str) -> set[str]:
        """Names of actual date controls observed in DOM/source evidence."""
        words = set()
        blob = str(evidence or "")
        # Runtime inventory has a deterministic `type=date name=… id=…` shape.
        for match in re.finditer(
                r"\btype=date\b[^\n|]{0,260}\bname=([^\s|]+)[^\n|]{0,180}\bid=([^\s|]+)",
                blob, re.I):
            for value in match.groups():
                if value and value != "-":
                    words |= semantic_words(value)
        # Source attributes can appear in any order, so inspect one input tag.
        for tag in re.findall(r"<input\b[^>]{0,1200}>", blob, re.I):
            if not re.search(r"\btype\s*=\s*['\"]date['\"]", tag, re.I):
                continue
            for attr in ("name", "id", "aria-label", "placeholder"):
                match = re.search(rf"\b{attr}\s*=\s*['\"]([^'\"]+)['\"]", tag, re.I)
                if match:
                    words |= semantic_words(match.group(1))
        return words

    def normalize_temporal_values(self, sc: Scenario, journey: dict = None) -> list[str]:
        """Replace decaying guessed date literals with run-time relative dates.

        A fixed date is preserved when it is explicitly present in the accepted
        journey/contract.  Only values attached to controls proven to be date
        inputs are touched, so ids, prices, and arbitrary ISO-looking text are
        outside this normalization.
        """
        journey = journey or {}
        evidence = self.runtime_evidence(journey)
        blocks = []
        for rel in self._journey_pages(journey):
            block = self.markup_for(rel)
            if block:
                blocks.append(block)
        hay = (evidence + "\n" + "\n".join(blocks))[:60_000]
        date_words = self._date_field_words(hay)
        if not date_words:
            return []

        accepted = " ".join(
            [str(journey.get("title") or "")]
            + [str(x) for x in (journey.get("steps") or [])]
            + [json.dumps(journey.get("contract") or {}, ensure_ascii=False)]
        )
        candidates = []
        for step in getattr(sc, "steps", []) or []:
            if step.verb not in {"FILL", "EXPECT_VALUE"} or not is_iso_date(step.value):
                continue
            sel = getattr(step, "selector", None)
            selector_words = semantic_words(
                " ".join([str(getattr(sel, "pattern", "") or ""),
                          str(getattr(sel, "role", "") or "")]))
            # An ISO value on a field selector, in a journey whose real form
            # contains date controls, is sufficient even when an older author
            # used a generic range word instead of the observed name/id.
            is_field = str(getattr(sel, "kind", "") or "") == "field"
            if ((selector_words & date_words) or is_field) and step.value not in accepted:
                candidates.append(step)
        if not candidates:
            return []

        ordered = sorted({step.value for step in candidates})
        base = date.fromisoformat(ordered[0])
        tokens = {}
        for value in ordered:
            delta = (date.fromisoformat(value) - base).days
            tokens[value] = relative_date_token(7 + max(0, min(delta, 120)))

        notes = []
        for step in candidates:
            old = step.value
            step.value = tokens[old]
            notes.append(f"{old} -> {step.value} for {step.selector.describe()}")
        return notes

    def _grounded_testids(self, journey: dict, evidence: str,
                          blocks: list[str]) -> set[str]:
        """Test ids available on this journey's pages, not elsewhere in the app."""
        out = set(re.findall(r"\btestid=([^\s|]+)", evidence or "", re.I))
        for block in blocks:
            out.update(self._TESTID_RE.findall(block or ""))
        return out

    def _journey_requires_field(self, journey: dict, key: str) -> bool:
        """Whether the accepted workflow explicitly requires this field.

        This is intentionally lexical and conservative.  It is only used to
        decide whether a selector invented by the scenario author may be
        rejected before a browser run.  If the product workflow actually says
        "full name"/"discount"/etc., we preserve the step so the browser can
        expose a missing production control as an app defect.
        """
        journey = journey or {}
        text = " ".join([str(journey.get("title") or "")]
                        + [str(x) for x in (journey.get("steps") or [])]).lower()
        aliases = self._FIELD_ALIASES.get(str(key or "").lower(), (str(key or "").lower(),))
        return any(re.search(r"\b" + re.escape(a) + r"\b", text, re.I)
                   for a in aliases if a)

    def _field_is_grounded(self, key: str, hay: str) -> bool:
        """True when runtime/source evidence actually exposes a matching form field."""
        key = str(key or "").strip().lower()
        if not key or not hay:
            return False
        aliases = self._FIELD_ALIASES.get(key, (key,))
        blob = str(hay or "")

        attrs = ("name", "id", "label", "placeholder", "aria",
                 "aria-label", "autocomplete")
        for alias in aliases:
            token = re.escape(alias).replace(r"\ ", r"[\s_-]*")
            for attr in attrs:
                if re.search(
                    rf"\b{re.escape(attr)}\s*(?:=|:)\s*(?:['\"])?[^\n|'\"]*{token}",
                    blob, re.I):
                    return True

        if key == "email" and re.search(r"\btype\s*=\s*['\"]?email\b", blob, re.I):
            return True
        if key == "password" and re.search(r"\btype\s*=\s*['\"]?password\b", blob, re.I):
            return True
        if key == "phone" and re.search(r"\btype\s*=\s*['\"]?tel\b", blob, re.I):
            return True
        if key == "date" and re.search(r"\btype\s*=\s*['\"]?date\b", blob, re.I):
            return True
        return False

    def _text_absent_from_app(self, st) -> bool:
        """
        True only when the step's literal text is in none of the app's files.

        Deliberately one-sided. A pattern with alternation, character classes
        or anchors is not searched at all — the point is to catch plain copy
        that was invented, not to re-implement matching against source that is
        JSX rather than rendered output. Anything it cannot be sure about is
        left for the browser to decide.
        """
        sel = getattr(st, "selector", None)
        if not sel or getattr(sel, "kind", "") not in {"text", "role"}:
            return False
        raw = str(getattr(sel, "pattern", "") or "").strip()
        if not raw or re.search(r"[\\[\]()|^$*+?{}]", raw):
            return False
        if len(raw) < 4:
            return False

        files = getattr(self.arch, "files", None) or {}
        needle = raw.lower()
        for path, body in files.items():
            if not str(path).startswith(("app/", "components/", "lib/")):
                continue
            if needle in str(body or "").lower():
                return False
        return bool(files)

    @staticmethod
    def _assertion_matches_entered_value(st, values: list[str]) -> bool:
        """Whether a later text assertion proves data the scenario itself entered.

        Dynamic user content is not supposed to exist in source code. A review
        body, booking note or freshly-created title is often typed in an earlier
        step and then asserted after save. Treating "not found in source" as an
        authoring error for those values made legitimate CRUD journeys
        impossible to ground.
        """
        sel = getattr(st, "selector", None)
        if not sel or not values:
            return False
        try:
            pat = sel.compiled()
        except Exception:
            pat = None
        raw = str(getattr(sel, "pattern", "") or "").strip().strip('"\'')
        for value in values:
            value = str(value or "").strip()
            if not value:
                continue
            try:
                if hasattr(pat, "search") and pat.search(value):
                    return True
            except Exception:
                pass
            if raw and (raw.lower() in value.lower() or value.lower() in raw.lower()):
                return True
        return False

    def grounding_issue(self, sc: Scenario, journey: dict = None) -> str:
        """Reject guessed page-copy assertions before spending a browser run.

        Before the workflow performs its first business mutation, text checks are
        normally just trying to prove page identity. That is better expressed as
        EXPECT_URL, and if the author insists on text it must exist in either the
        real runtime DOM or the actual source markup. Later assertions are left
        alone because they may describe state created by the workflow itself.
        """
        evidence = self.runtime_evidence(journey)
        blocks = []
        for rel in self._journey_pages(journey):
            try:
                block = self.markup_for(rel)
            except Exception:
                block = ""
            if block:
                blocks.append(block)
        hay = (evidence + "\n" + "\n".join(blocks))[:50_000]
        if not hay:
            return ""

        grounded_testids = self._grounded_testids(journey or {}, evidence, blocks)
        for st in sc.steps:
            sel = getattr(st, "selector", None)
            if (sel and getattr(sel, "kind", "") == "testid"
                    and str(getattr(sel, "pattern", "") or "") not in grounded_testids):
                return (f"ungrounded testid {st.describe()}: that data-testid is "
                        "absent from the runtime/source pages for this journey. "
                        "Use an observed accessible name/href, or keep the required "
                        "business action naturally named so a genuinely missing "
                        "production control is reported as an app defect.")

        business_started = False
        entered_values = []
        for st in sc.steps:
            sel = getattr(st, "selector", None)
            if (st.verb in {"FILL", "SELECT", "EXPECT_VALUE"} and sel and
                    getattr(sel, "kind", "") == "field"):
                key = str(getattr(sel, "pattern", "") or "").strip()
                if (key and not self._field_is_grounded(key, hay) and
                        not self._journey_requires_field(journey or {}, key)):
                    return (f"ungrounded form field {st.describe()}: field={key} "
                            "is absent from the observed DOM/source and is not "
                            "required by the accepted workflow. Re-author using "
                            "an observed field instead of inventing one.")

            if st.verb == "SELECT":
                # A select often commits through onChange.
                if str(getattr(st, "value", "") or "").strip():
                    entered_values.append(str(st.value).strip())
                business_started = True
            elif st.verb == "FILL":
                if str(getattr(st, "value", "") or "").strip():
                    entered_values.append(str(st.value).strip())
            elif st.verb == "CLICK":
                sel = getattr(st, "selector", None)
                text = " ".join([str(getattr(sel, "pattern", "") or ""),
                                 str(getattr(sel, "role", "") or "")]).lower()
                if not re.search(r"sign.?in|log.?in|login|authenticate", text):
                    business_started = True

            if st.verb not in {"WAIT_FOR", "EXPECT_TEXT"}:
                continue
            if business_started:
                if self._assertion_matches_entered_value(st, entered_values):
                    continue
                sel = getattr(st, "selector", None)
                raw = str(getattr(sel, "pattern", "") or "").strip()
                contract_text = json.dumps((journey or {}).get("contract") or {},
                                           ensure_ascii=False)
                if (re.match(r"^(?:\^\s*)?(?:no|none|nothing|empty|zero)\b",
                             raw, re.I)
                        and raw.lower() not in contract_text.lower()):
                    return (f"brittle empty-state proof {st.describe()}: a successful "
                            "record mutation does not imply every other record is "
                            "absent. Use EXPECT_MUTATION plus a record-specific URL, "
                            "entered value, or observed state proof.")
                if self._text_absent_from_app(st):
                    return (f"ungrounded page-copy check {st.describe()}: that "
                            "text appears nowhere in the app's source, so no "
                            "run of it can produce the text. Assert something "
                            "the app actually renders, or use EXPECT_URL.")
                continue
            sel = getattr(st, "selector", None)
            if not sel or getattr(sel, "kind", "") not in {"text", "role"}:
                continue
            try:
                pat = sel.compiled()
                ok = bool(pat.search(hay) if hasattr(pat, "search")
                          else str(pat).lower() in hay.lower())
            except Exception:
                ok = True
            if not ok:
                prev = getattr(self, "_active_journey", None)
                try:
                    self._active_journey = journey or {}
                    target = self._route_for_page_copy(sel)
                finally:
                    self._active_journey = prev
                if target:
                    continue
                return (f"ungrounded page-copy check {st.describe()}: that text "
                        "is absent from the real DOM/source. Use EXPECT_URL for "
                        "page identity or choose text/control evidence that was "
                        "actually observed.")
        return ""

    def _role_in(self, text):
        """The role a scenario runs as, or "" for signed out.

        "guest" used to be hard-coded as meaning signed-out, alongside
        "anonymous" and "none" — reasonable for a shop, wrong for a hotel,
        where `guest` is the paying customer and has a demo account of its
        own. The collision was silent and expensive: the guest journey's role
        was thrown away, `account_for("")` handed back the first account —
        the admin's — and the generated spec signed in as the administrator
        while asserting it reached the guest dashboard. Two of the E2E
        repair rounds then went into "fixing" an app that was behaving
        correctly.

        So the demo accounts decide. A word that names a real account is that
        role, whatever the word is; only words that name nobody, and that
        read as nobody, mean signed out.
        """
        m = re.search(r"^\s*(?:AS|ROLE)\s*::\s*(.+)$", text or "", re.M | re.I)
        role = (m.group(1).strip().lower() if m else "")
        if any((a.get("role") or "").lower() == role for a in self.accounts()):
            return role
        return "" if role in self._SIGNED_OUT else role

    def _idea(self):
        try:
            convo = getattr(self.arch, "convo", None) or []
            if len(convo) > 1 and convo[1].get("role") == "user":
                return convo[1]["content"][:3000]
        except Exception:
            pass
        return (getattr(self.arch, "plan_md", "") or "")[:3000]

    def preground(self, sc: Scenario, journey: dict = None) -> int:
        """Bind FILL/SELECT/CLICK selectors to the live DOM before the run.

        The runtime recovery in `_smart_locator` already finds the right
        control — but only after the primary selector has burned its timeout,
        and only on the page the run happens to be on. Doing the same lookup
        up front, read-only, moves "selector recovered" to before step 1: the
        first browser run starts with locators the DOM has actually shown us.

        Strictly non-mutating: pages are visited with GOTO only, nothing is
        clicked or filled, and any page past the first business mutation is
        skipped because its controls may not exist until the flow creates
        them. Failures here change nothing — the run recovers as before.
        """
        steps = list(getattr(sc, "steps", []) or [])
        if not steps:
            return 0
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return 0

        # Selectors grouped by the route they will be used on, pre-mutation.
        route, per_route, order = "/", {}, []
        for st in steps:
            if st.verb == "GOTO":
                route = str(st.value or "/").split("#", 1)[0]
                continue
            if self._is_business_step(st):
                break
            if st.verb not in ("FILL", "SELECT", "CLICK"):
                continue
            sel = getattr(st, "selector", None)
            if sel is None:
                continue
            if route not in per_route:
                per_route[route] = []
                order.append(route)
            per_route[route].append(st)
        if not per_route:
            return 0

        fixed = 0
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(viewport={"width": 1280,
                                                    "height": 800})
                page = ctx.new_page()
                role = str((journey or {}).get("role") or sc.role or "")
                acc = self.account_for(role) if role else None
                if acc:
                    try:
                        page.goto(self.base_url + "/",
                                  timeout=GOTO_TIMEOUT,
                                  wait_until="domcontentloaded")
                        self._sign_in(page, acc)
                    except Exception as e:
                        log.debug(f"preground sign-in: {e}")
                for r in order[:6]:
                    try:
                        page.goto(self.base_url + r, timeout=GOTO_TIMEOUT,
                                  wait_until="domcontentloaded")
                        self._wait_hydrated(page)
                    except Exception as e:
                        log.debug(f"preground goto {r}: {e}")
                        continue
                    for st in per_route[r]:
                        sel = st.selector
                        if self._count(self._locator(
                                page, sel, clickable=st.verb == "CLICK")):
                            continue
                        _, replacement, note = self._smart_locator(
                            page, sel, verb=st.verb)
                        if replacement is None:
                            continue
                        old = st.selector.describe()
                        st.selector = replacement
                        self._scenario_changed = True
                        fixed += 1
                        self._log("INFO",
                                  f"   🧲 pre-grounded: {old} → "
                                  f"{replacement.describe()}"
                                  + (f" ({note})" if note else ""))
                browser.close()
        except Exception as e:
            log.debug(f"preground: {e}")
        return fixed

    @staticmethod
    def _render(sc: Scenario) -> str:
        lines = [f"FLOW :: {sc.title}", f"AS :: {sc.role or 'SIGNED OUT'}"]
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

from qa_agent.e2e.e2e_journeys import E2EJourneyAuthoringMixin


class E2EAuthoringMixin(E2EJourneyAuthoringMixin, E2EGroundingMixin):
    """Concrete journey discovery + source/DOM grounding behavior."""
    pass
