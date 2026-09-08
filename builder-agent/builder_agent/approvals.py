"""Asking the person watching, without stranding the run when nobody is.

The engine removed its interaction modes because a studio build is unattended
and an approval prompt with nobody in front of it is a hang. Two decisions are
worth asking about anyway, because both are cheap to change now and expensive
to change later: the plan, and what the application will look like.

So this is a gate that expires. It publishes the question, waits, and if no
answer arrives it proceeds with the default it was given. A studio user gets a
real choice; a CLI run, a test, or a browser that was closed mid-build gets the
default and carries on. Nothing can wait forever.
"""
from __future__ import annotations

import threading
import uuid


class Decision:
    """One pending question and the answer it is waiting for."""

    __slots__ = ("id", "kind", "payload", "default", "answer", "ready")

    def __init__(self, kind: str, payload: dict, default: dict) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.payload = payload
        self.default = default
        self.answer: dict | None = None
        self.ready = threading.Event()


class Approvals:
    """The questions a run may ask, and how long it will wait for an answer."""

    def __init__(self, events, enabled: bool = False, timeout: float = 300.0) -> None:
        self.events = events
        # Off unless a surface that can actually answer turns it on.
        self.enabled = enabled
        self.timeout = timeout
        self.pending: dict[str, Decision] = {}
        self._lock = threading.Lock()

    def ask(self, kind: str, payload: dict, default: dict,
            timeout: float | None = None, cancel=None) -> dict:
        """Publish a question and wait, or return `default`."""
        if not self.enabled:
            return dict(default, decision=default.get("decision", "default"), asked=False)

        decision = Decision(kind, payload, default)
        with self._lock:
            self.pending[decision.id] = decision
        self.events.emit("approval", id=decision.id, kind=kind, timeout=timeout or self.timeout,
                         **payload)

        deadline = timeout if timeout is not None else self.timeout
        waited = 0.0
        while waited < deadline:
            if decision.ready.wait(0.5):
                break
            waited += 0.5
            if cancel and cancel():
                break

        with self._lock:
            self.pending.pop(decision.id, None)

        answer = decision.answer or dict(default, decision=default.get("decision", "default"),
                                         timedOut=True)
        self.events.emit("approval:resolved", id=decision.id, kind=kind,
                         decision=answer.get("decision"))
        return {**answer, "asked": True}

    def resolve(self, decision_id: str, answer: dict) -> bool:
        with self._lock:
            decision = self.pending.get(str(decision_id or ""))
        if not decision:
            return False
        decision.answer = dict(answer or {})
        decision.ready.set()
        return True

    def cancel_all(self) -> None:
        """Nothing may be left waiting on a run that has ended."""
        with self._lock:
            waiting = list(self.pending.values())
            self.pending.clear()
        for decision in waiting:
            decision.answer = dict(decision.default, decision=decision.default.get("decision"),
                                   cancelled=True)
            decision.ready.set()

    def list(self) -> list[dict]:
        with self._lock:
            return [{"id": d.id, "kind": d.kind} for d in self.pending.values()]
