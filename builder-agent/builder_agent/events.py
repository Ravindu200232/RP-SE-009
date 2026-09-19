"""The one channel between the engine and everything watching it.

The CLI, the studio websocket and the run log all subscribe here rather than
being called directly, so the engine never needs to know which of them exists.
Adding a surface is a subscription; it is not a change to the loop.
"""
from __future__ import annotations

import threading
from typing import Callable


class Events:
    """Named events, published to every subscriber, failures isolated.

    A subscriber that raises must not take the run down with it — a broken log
    line is not a reason to abandon a build — so each callback is guarded.
    """

    START = "agent:start"
    DONE = "agent:done"
    ERROR = "agent:error"
    ABORT = "agent:abort"
    ITERATION = "iteration"
    TOOL_START = "tool:start"
    TOOL_END = "tool:end"
    TOKEN = "token"
    NOTICE = "notice"
    PHASE = "phase"
    PLAN = "plan"
    FILE = "file"
    TEST = "test"
    CONTEXT = "context"

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = {}
        self._any: list[Callable] = []
        self._lock = threading.Lock()

    def on(self, event: str, fn: Callable) -> Callable:
        with self._lock:
            self._subs.setdefault(event, []).append(fn)
        return fn

    def any(self, fn: Callable) -> Callable:
        with self._lock:
            self._any.append(fn)
        return fn

    def emit(self, event, /, **payload) -> None:
        """Publish `event` with its payload.

        `event` is positional-only because payloads legitimately carry keys
        like `name` and `event`; a keyword parameter here would collide with
        them, and the collision only shows up at the one call site that uses
        that key.
        """
        with self._lock:
            named = list(self._subs.get(event, ()))
            wildcard = list(self._any)
        for fn in named:
            self._call(fn, payload)
        for fn in wildcard:
            self._call(fn, payload, event)

    @staticmethod
    def _call(fn, payload, event=None) -> None:
        try:
            fn(payload) if event is None else fn(event, payload)
        except Exception:  # noqa: BLE001 - a bad listener must not stop the run
            pass

    def clear(self) -> None:
        with self._lock:
            self._subs.clear()
            self._any.clear()
