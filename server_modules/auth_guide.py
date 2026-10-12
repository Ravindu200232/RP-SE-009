"""The one authentication guide the wireframes, the prototype and the build all read."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import prompts, reference_staging

PROMPT = "shared/authentication"
FOLDER = ".agentforge/auth"
NAME = "AUTHENTICATION.md"
PATH = f"{FOLDER}/{NAME}"


def needed(doc: Any) -> bool:
    """Whether the specification has anyone signing in."""
    if not isinstance(doc, dict):
        return False
    auth = doc.get("authentication_requirement")
    if isinstance(auth, dict) and auth.get("login_required"):
        return True
    pages = [p for p in (doc.get("public_pages") or []) + (doc.get("protected_pages") or []) if isinstance(p, dict)]
    return any(p.get("login_required") for p in pages)


def stage(workspace: Path) -> str:
    """Put the guide in the workspace, where an agent's read_file reaches it; returns its workspace path."""
    return reference_staging.stage(workspace, FOLDER, {NAME: prompts.load(PROMPT)})[0]


def staged_for(workspace: Path, doc: Any) -> str:
    """The guide's workspace path when the product has sign-in, staged fresh; "" when it has none."""
    return stage(workspace) if needed(doc) else ""
