"""A model service that does not answer: the "Try again" a person can press while the run waits."""
from __future__ import annotations

import threading

import httpx

# How long a request to the model service may go without a single byte coming back before it is given up on (and asked for again, `session.RetryingClient`).
MODEL_READ_SECONDS = 900.0
MODEL_CONNECT_SECONDS = 30.0


def model_timeout() -> httpx.Timeout:
    return httpx.Timeout(MODEL_READ_SECONDS, connect=MODEL_CONNECT_SECONDS)


_lock = threading.Lock()
_pressed: dict[str, int] = {}


def retry(project: str) -> bool:
    """The person pressed "Try again" for `project`."""
    if not project:
        return False
    with _lock:
        _pressed[project] = _pressed.get(project, 0) + 1
    return True


def presses(project: str) -> int:
    """How many times "Try again" has been pressed for `project` so far."""
    with _lock:
        return _pressed.get(project, 0)
