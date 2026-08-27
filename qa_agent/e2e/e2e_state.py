"""Checkpoint state restoration for focused browser reruns."""
from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from qa_agent.e2e.flows import is_auth_submit_step


class E2EStateMixin:
    def _journey_role(self, journey=None, scenario=None) -> str:
        return str(getattr(scenario, "auth_role", "") or
                   (journey or {}).get("role") or
                   getattr(scenario, "role", "") or "").strip().lower()

    def _role_requires_session(self, journey=None, scenario=None,
                               at_index: int | None = None) -> bool:
        role = self._journey_role(journey, scenario)
        if not role:
            return False
        signed_out = set(getattr(self, "_SIGNED_OUT", ()) or ())
        declared = str((journey or {}).get("role") or
                       getattr(scenario, "role", "") or "").strip().lower()
        if declared not in signed_out:
            return True
        # A public journey needs a session only after it has actually submitted
        # credentials.  This keeps pre-login checkpoint replays signed out.
        if getattr(scenario, "auth_role", ""):
            if at_index is None:
                return True
            return any(is_auth_submit_step(scenario, index)
                       for index in range(min(max(0, at_index), len(scenario.steps))))
        return False

    def _session_snapshot(self, page) -> dict:
        try:
            got = page.evaluate(
                """async () => { try {
                    const r = await fetch('/api/auth/get-session', {cache:'no-store'});
                    let body = null; try { body = await r.json(); } catch (_) {}
                    return {status:r.status, body};
                } catch (e) { return {status:0, error:String(e)}; } }""")
            return got if isinstance(got, dict) else {"status": 0, "body": got}
        except Exception as exc:
            return {"status": 0, "error": str(exc)[:180]}

    @staticmethod
    def _session_identity(body) -> tuple[str, str]:
        if not isinstance(body, dict):
            return "", ""
        user = body.get("user") if isinstance(body.get("user"), dict) else body
        email = str(user.get("email") or "").strip().lower() if isinstance(user, dict) else ""
        role = str(user.get("role") or body.get("role") or "").strip().lower() if isinstance(user, dict) else ""
        return email, role

    def _session_matches_expected_role(self, page, journey=None, scenario=None,
                                       at_index: int | None = None) -> bool:
        if not self._role_requires_session(journey, scenario, at_index):
            return True
        snap = self._session_snapshot(page)
        if int(snap.get("status") or 0) != 200 or not snap.get("body"):
            return False
        expected_role = self._journey_role(journey, scenario)
        account = self.account_for(expected_role)
        expected_email = str((account or {}).get("email") or "").strip().lower()
        email, role = self._session_identity(snap.get("body"))
        if expected_email and email:
            return email == expected_email
        if expected_role and role:
            return role == expected_role
        return bool(snap.get("body"))

    def _restore_checkpoint_session(self, page, journey=None, scenario=None,
                                    route: str = "", start_index: int = 0) -> tuple[bool, str]:
        """Restore the expected demo identity without replaying business steps."""
        if not self._role_requires_session(journey, scenario, start_index):
            return True, "signed-out journey"
        if self._session_matches_expected_role(page, journey, scenario, start_index):
            return True, "checkpoint session valid"

        role = self._journey_role(journey, scenario)
        account = self.account_for(role)
        if not account:
            return False, f"no demo account exists for role {role or '?'}"
        try:
            if not self._sign_in(page, account):
                return False, f"could not restore the {role or 'required'} demo session"
            if route:
                page.goto(self.base_url + route, wait_until="domcontentloaded")
            if not self._session_matches_expected_role(page, journey, scenario,
                                                       start_index):
                return False, f"restored session does not match role {role or '?'}"
            self._log("INFO", f"   🔐 restored {role} session at the browser checkpoint")
            return True, "session restored"
        except Exception as exc:
            return False, f"checkpoint auth restore failed: {type(exc).__name__}: {exc}"

    def _safe_checkpoint_route(self, route: str) -> str:
        """Strip credentials/tokens from routes persisted in logs and resumes."""
        raw = str(route or "").strip()
        if not raw:
            return raw
        try:
            split = urlsplit(raw)
            path = split.path or "/"
            if self._is_auth_route(path):
                return path
            secret = {"email", "password", "passwd", "passcode", "token",
                      "secret", "authorization", "session"}
            query = [(key, value) for key, value in parse_qsl(
                split.query, keep_blank_values=True) if key.lower() not in secret]
            fragment = "" if any(word in split.fragment.lower() for word in secret) \
                else split.fragment
            return urlunsplit(("", "", path, urlencode(query), fragment))
        except Exception:
            return raw.split("?", 1)[0] if "password" in raw.lower() else raw

    def _checkpoint_business_values(self, route: str, sc=None, upto: int = 0) -> dict:
        """Persist dynamic query values and values already entered before a repair."""
        out = {"query": {}, "filled": {}}
        secret = {"email", "password", "passwd", "passcode", "token",
                  "secret", "authorization", "cookie", "session"}
        try:
            out["query"] = {
                key: value for key, value in parse_qsl(
                    urlsplit(str(route or "")).query, keep_blank_values=True)
                if key.lower() not in secret
            }
        except Exception:
            pass
        for step in (getattr(sc, "steps", []) or [])[:max(0, int(upto or 0))]:
            sel = getattr(step, "selector", None)
            if getattr(step, "verb", "") not in ("FILL", "SELECT") or not sel:
                continue
            key = str(getattr(sel, "pattern", "") or getattr(sel, "role", "") or "").strip()
            selector_text = " ".join((key, str(getattr(sel, "role", "") or ""))).lower()
            if key and not any(word in selector_text for word in secret):
                out["filled"][key] = str(getattr(step, "value", "") or "")[:220]
        return out
