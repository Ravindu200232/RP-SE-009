"""One build at a time, and everyone waiting knows where they are.

The pipeline keeps one run's state — what a Stop cancels, which project the
output belongs to — so two builds at once would write over each other's. On one
machine they would also run each other out of memory: two model sessions, two
npm installs, two dev servers, for a machine sized for one.

So runs take turns. One is active, the rest wait in the order they arrived, and
each one that has to wait is told how many are ahead of it rather than sitting
in front of a studio that looks broken. Someone who gives up before their turn
comes leaves the line, which is what Stop does for a build that has not started.
"""
from __future__ import annotations

import itertools
import threading
from typing import Callable, Optional


class RunQueue:
    def __init__(self):
        self._lock = threading.Lock()
        self._waiting: list = []
        self._active: Optional[dict] = None
        self._numbers = itertools.count(1)

    def active(self) -> Optional[dict]:
        """The run that has the machine right now, or None."""
        with self._lock:
            return self._public(self._active) if self._active else None

    def waiting(self) -> list:
        with self._lock:
            return [self._public(entry) for entry in self._waiting]

    def run(self, work: Callable, *, user: str = "", project: str = "", kind: str = "",
            agent: str = "",
            on_wait: Optional[Callable[[int], None]] = None):
        """Run `work` when it is its turn, and answer with what it answered.

        Answers None without running anything if whoever asked for it left the
        line first.
        """
        entry = {"id": next(self._numbers), "user": str(user or ""),
                 "project": str(project or ""), "kind": str(kind or ""),
                 "agent": agent,
                 "turn": threading.Event(), "left": False}
        with self._lock:
            ahead = (1 if self._active else 0) + len(self._waiting)
            if ahead:
                self._waiting.append(entry)
            else:
                self._active = entry
        if ahead:
            if on_wait:
                on_wait(ahead)
            entry["turn"].wait()
            if entry["left"]:
                return None
        try:
            return work()
        finally:
            self._finish(entry)

    def set_agent(self, agent: str) -> None:
        with self._lock:
            if self._active:
                self._active["agent"] = agent

    def leave(self, user: str, project: str = "", agent: str = "") -> int:
        """Take this person's waiting runs out of the line; how many left.

        The active run is not one of them: stopping that is cancelling it.
        """
        user = str(user or "")
        if not user:
            return 0
        with self._lock:
            leaving = [entry for entry in self._waiting if entry["user"] == user
                       and (not project or entry["project"] == project)
                       and (not agent or entry["agent"] == agent)]
            self._waiting = [entry for entry in self._waiting if entry not in leaving]
            for entry in leaving:
                entry["left"] = True
                entry["turn"].set()
        return len(leaving)

    def _finish(self, entry: dict) -> None:
        with self._lock:
            if self._active is entry:
                self._active = None
            # Whoever is next gets the machine before this thread lets go of
            # the lock, so a second run cannot slip in between the two.
            while self._active is None and self._waiting:
                following = self._waiting.pop(0)
                self._active = following
                following["turn"].set()

    @staticmethod
    def _public(entry: dict) -> dict:
        return {key: value for key, value in entry.items() if key not in ("turn", "left")}
