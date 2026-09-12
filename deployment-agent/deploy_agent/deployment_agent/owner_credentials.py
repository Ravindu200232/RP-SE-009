"""Whose accounts a deployment signs in with.

Run on its own, the agent uses whatever this machine is signed in to: the `gh`
login, the Vercel CLI's token, the AWS profiles in ~/.aws. Run inside
AgentForge for many people, that would put every deployment in the machine
owner's accounts. So AgentForge registers a provider, and every run names its
owner: the run's GitHub and Vercel tokens are that person's, looked up when
they are needed. With a provider registered the machine's own logins are never
used - a run whose owner has not connected GitHub fails asking them to, rather
than pushing to somebody else's account.

The owner is kept per thread, because a run is one: `acting_for` sets it, and
`carry` takes it along to a thread a run starts.
"""
from __future__ import annotations

import contextlib
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

_PROVIDER: Optional[Callable[[str], dict]] = None
_LOCAL = threading.local()
# An empty GitHub CLI home: `gh` pointed here knows no machine login at all.
_NO_MACHINE_GH = Path(tempfile.gettempdir()) / "agentforge-gh-none"


def register(provider: Optional[Callable[[str], dict]]) -> None:
    global _PROVIDER
    _PROVIDER = provider


def active() -> bool:
    """Is this agent deploying for many people, each with their own accounts?"""
    return _PROVIDER is not None


def owner() -> str:
    return str(getattr(_LOCAL, "owner", "") or "")


def set_owner(value: str) -> None:
    _LOCAL.owner = str(value or "")


@contextlib.contextmanager
def acting_for(value: str):
    previous = owner()
    set_owner(value)
    try:
        yield
    finally:
        set_owner(previous)


def carry(fn, value: Optional[str] = None):
    """`fn`, to run on another thread as this thread's owner (or as `value`)."""
    who = owner() if value is None else str(value or "")

    def run(*args, **kwargs):
        with acting_for(who):
            return fn(*args, **kwargs)
    return run


def current() -> dict:
    """This thread's owner's tokens - {} with no owner, or no provider."""
    who = owner()
    if not (_PROVIDER and who):
        return {}
    try:
        return dict(_PROVIDER(who) or {})
    except Exception:                                                # noqa: BLE001
        return {}


def command_env() -> dict:
    """What a command run for this thread's owner carries in its environment."""
    if not active():
        return {}
    env = {}
    github = str(current().get("github_token") or "")
    if github:
        env["GH_TOKEN"] = github
        env["GITHUB_TOKEN"] = github
    # Never the machine's own `gh` login, whether or not they have a token.
    _NO_MACHINE_GH.mkdir(parents=True, exist_ok=True)
    env["GH_CONFIG_DIR"] = str(_NO_MACHINE_GH)
    return env
