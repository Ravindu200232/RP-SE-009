"""Privacy-safe, cross-run learning for the generic E2E debugger.

The store remembers whether a *kind* of diagnosis moved the browser forward.
It deliberately does not persist source, URLs, project names, response bodies,
credentials, or suggested patches.  Failure and hypothesis text is represented
only by a one-way fingerprint, so one generated app cannot leak data into the
next app's debugger prompt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


STORE_VERSION = 1
MAX_FAILURES = 256
MAX_DECISIONS_PER_FAILURE = 12


def _stable_text(value: str) -> str:
    """Normalize volatile values before hashing; the normalized text is not saved."""
    text = str(value or "").lower()
    text = re.sub(r"https?://[^\s]+", "<url>", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", "<email>", text)
    text = re.sub(r"\b[0-9a-f]{24,}\b", "<id>", text, flags=re.I)
    text = re.sub(r"\b\d{3,}\b", "<n>", text)
    text = re.sub(r"[a-z]:[/\\][^\s]+", "<path>", text, flags=re.I)
    return " ".join(text.split())[:1800]


def _digest(value: str) -> str:
    return hashlib.sha256(_stable_text(value).encode("utf-8")).hexdigest()[:24]


def failure_fingerprint(failures) -> str:
    rows = []
    for failure in list(failures or [])[:4]:
        rows.append("|".join([
            str(getattr(failure, "kind", "") or "").upper(),
            str(getattr(failure, "name", "") or ""),
            str(getattr(failure, "message", "") or ""),
        ]))
    return _digest("\n".join(rows)) if rows else ""


def decision_fingerprint(decision: dict) -> str:
    decision = decision or {}
    return _digest("|".join([
        str(decision.get("verdict") or "UNKNOWN").upper(),
        str(decision.get("evidence_rule") or "model-reasoned").lower(),
        str(decision.get("hypothesis") or decision.get("root") or ""),
    ]))


def default_learning_path() -> Path:
    override = os.environ.get("AGENTFORGE_E2E_LEARNING_PATH")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "AgentForge" / "qa" / "e2e-learning.json"
    state = os.environ.get("XDG_STATE_HOME")
    if state:
        return Path(state) / "agentforge" / "e2e-learning.json"
    return Path(tempfile.gettempdir()) / "agentforge" / "e2e-learning.json"


class E2ELearningStore:
    """A bounded, atomic outcome counter keyed only by one-way fingerprints."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_learning_path()
        self.data = self._load()

    def _empty(self) -> dict:
        return {"version": STORE_VERSION, "failures": {}}

    def _load(self) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if (isinstance(raw, dict) and raw.get("version") == STORE_VERSION
                    and isinstance(raw.get("failures"), dict)):
                return raw
        except (OSError, ValueError, TypeError):
            pass
        return self._empty()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, sort_keys=True, separators=(",", ":"))
        handle, temporary_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _decision_meta(decision: dict) -> tuple[str, str]:
        verdict = str((decision or {}).get("verdict") or "UNKNOWN").upper()
        rule = re.sub(r"[^a-z0-9_-]+", "-", str(
            (decision or {}).get("evidence_rule") or "model-reasoned").lower()
        ).strip("-")[:80] or "model-reasoned"
        return verdict[:32], rule

    def record(self, failure_key: str, decision: dict, *, progressed: bool) -> None:
        if not re.fullmatch(r"[0-9a-f]{24}", str(failure_key or "")):
            return
        decision_key = decision_fingerprint(decision)
        verdict, rule = self._decision_meta(decision)
        failures = self.data.setdefault("failures", {})
        row = failures.setdefault(failure_key, {"seen": 0, "decisions": {}})
        row["seen"] = int(row.get("seen") or 0) + 1
        row["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        decisions = row.setdefault("decisions", {})
        item = decisions.setdefault(decision_key, {
            "verdict": verdict, "rule": rule, "progress": 0, "stalled": 0,
        })
        key = "progress" if progressed else "stalled"
        item[key] = int(item.get(key) or 0) + 1

        if len(decisions) > MAX_DECISIONS_PER_FAILURE:
            ordered = sorted(decisions, key=lambda k: (
                int(decisions[k].get("progress") or 0)
                + int(decisions[k].get("stalled") or 0), k))
            for old in ordered[:len(decisions) - MAX_DECISIONS_PER_FAILURE]:
                decisions.pop(old, None)
        if len(failures) > MAX_FAILURES:
            oldest = sorted(failures, key=lambda k: str(
                failures[k].get("updated") or ""))
            for old in oldest[:len(failures) - MAX_FAILURES]:
                failures.pop(old, None)
        try:
            self._save()
        except OSError:
            # Learning is advisory and must never break a build/test run.
            pass

    def observations(self, failure_key: str) -> list[dict]:
        row = self.data.get("failures", {}).get(str(failure_key or ""), {})
        values = []
        for decision_key, item in (row.get("decisions") or {}).items():
            if not isinstance(item, dict):
                continue
            values.append({
                "key": str(decision_key),
                "verdict": str(item.get("verdict") or "UNKNOWN"),
                "rule": str(item.get("rule") or "model-reasoned"),
                "progress": int(item.get("progress") or 0),
                "stalled": int(item.get("stalled") or 0),
            })
        return sorted(values, key=lambda x: (x["progress"], -x["stalled"]),
                      reverse=True)[:8]

    def repeatedly_stalled(self, failure_key: str, decision: dict,
                           minimum: int = 2) -> bool:
        wanted = decision_fingerprint(decision)
        for item in self.observations(failure_key):
            if item["key"] == wanted:
                return item["stalled"] >= minimum and item["progress"] == 0
        return False


__all__ = ["E2ELearningStore", "failure_fingerprint", "decision_fingerprint",
           "default_learning_path"]
