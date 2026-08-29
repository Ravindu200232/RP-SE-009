"""Scenario grounding, rendering and spec persistence."""
import re
from .e2e_common import *

class E2EGroundingMixin:
    _FIELD_ALIASES = {
        "email": ("email", "e-mail"),
        "password": ("password", "passcode", "passwd"),
        "phone": ("phone", "mobile", "telephone", "tel"),
        "name": ("name", "full name", "first name", "last name"),
        "price": ("price", "rate", "cost", "nightly"),
        "amount": ("amount", "total", "charge"),
        "status": ("status", "state"),
        "rating": ("rating", "stars", "score"),
        "review": ("review", "comment", "feedback"),
        "quantity": ("quantity", "stock", "qty"),
        "discount": ("discount", "percent", "percentage"),
        "category": ("category", "type", "group"),
        "start": ("start", "checkin", "check-in"),
        "end": ("end", "checkout", "check-out"),
    }

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


