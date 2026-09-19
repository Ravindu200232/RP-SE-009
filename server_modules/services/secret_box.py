"""Secrets at rest: a GitHub token or a database password is never stored as typed.

Each person's deployment accounts live in the account database. If that
database is ever read by someone it was not meant for - a copy of an Atlas
cluster, a backup - it must not hand them everyone's cloud accounts, so every
secret in it is encrypted with a key that is not in the database: an
AGENTFORGE_SECRET_KEY in the environment, or a key file beside the settings,
made on first use and readable only by its owner.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_LOCK = threading.Lock()
_BOX = None


def key_path() -> Path:
    raw = os.environ.get("AGENTFORGE_SECRET_KEY_FILE", "").strip()
    return Path(raw) if raw else Path.home() / ".agentforge" / "secret.key"


def _key() -> bytes:
    raw = os.environ.get("AGENTFORGE_SECRET_KEY", "").strip()
    if raw:
        return raw.encode("ascii")
    path = key_path()
    if path.is_file():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    # Made exclusively, so two processes starting at once cannot each write a
    # different key and lock the other's secrets away.
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes().strip()
    with os.fdopen(handle, "wb") as out:
        out.write(key)
    return key


def _box() -> Fernet:
    global _BOX
    with _LOCK:
        if _BOX is None:
            _BOX = Fernet(_key())
        return _BOX


def seal(text: str) -> str:
    """The secret, encrypted - or "" for nothing."""
    return _box().encrypt(str(text).encode("utf-8")).decode("ascii") if text else ""


def unseal(sealed: str) -> str:
    """The secret again, or "" if it cannot be read with this key."""
    if not sealed:
        return ""
    try:
        return _box().decrypt(str(sealed).encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def reset() -> None:
    """Forget the loaded key, so the next use reads it again (tests move it)."""
    global _BOX
    with _LOCK:
        _BOX = None
