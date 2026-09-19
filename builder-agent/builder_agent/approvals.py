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
import time
import uuid


class Decision:
    """One pending question and the answer it is waiting for."""

    __slots__ = ("id", "kind", "payload", "default", "answer", "ready", "asked_at",
                 "timeout")

    def __init__(self, kind: str, payload: dict, default: dict,
                 timeout: float = 300.0) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.payload = payload
        self.default = default
        self.timeout = float(timeout)
        self.asked_at = time.time()
        self.answer: dict | None = None
        self.ready = threading.Event()

    def as_question(self) -> dict:
        """The whole question, for a surface that was not listening when it was asked."""
        left = self.timeout - (time.time() - self.asked_at)
        return {"id": self.id, "kind": self.kind,
                "timeout": max(1, int(left)), **self.payload}


class Approvals:
    """The questions a run may ask, and how long it will wait for an answer."""

    def __init__(self, events, enabled=False, timeout: float = 300.0) -> None:
        self.events = events
        # Enable approval gates selectively according to the requesting surface's capabilities.
        self.enabled = enabled if isinstance(enabled, bool) else frozenset(enabled or ())
        self.timeout = timeout
        self.pending: dict[str, Decision] = {}
        # How many of each kind this run has already put to them. A question is
        # worth asking; being asked six of them is an interview, and the person
        # came here to watch something get built.
        self.counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def asks(self, kind: str) -> bool:
        return bool(self.enabled) and (self.enabled is True or kind in self.enabled)

    def asked(self, kind: str) -> int:
        """How many of this kind have been put to them so far in this run."""
        with self._lock:
            return int(self.counts.get(kind, 0))

    def ask(self, kind: str, payload: dict, default: dict,
            timeout: float | None = None, cancel=None) -> dict:
        """Publish a question and wait, or return `default`."""
        # Counted before the gate, not after it: a surface that cannot answer
        # still must not be asked the same thing forty times, and a budget that
        # only applied when somebody was watching would be no budget at all.
        with self._lock:
            self.counts[kind] = self.counts.get(kind, 0) + 1
        if not self.asks(kind):
            return dict(default, decision=default.get("decision", "default"), asked=False)

        decision = Decision(kind, payload, default,
                            timeout if timeout is not None else self.timeout)
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
        """Every question still waiting, in full.

        A websocket message is delivered once. A studio that reloaded, or that
        was mid-request when the next question arrived, has no other way to
        find out that a run is waiting on it - and the run then sits there
        until it times out.
        """
        with self._lock:
            return [d.as_question() for d in self.pending.values()]
