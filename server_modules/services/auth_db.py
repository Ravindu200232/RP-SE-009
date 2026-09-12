"""Accounts for a shared AgentForge: who is signed in, what is theirs, and their accounts.

One machine, many people, each with an AgentForge of their own - their own
projects, specifications, deployments and settings, and their own GitHub, AWS,
Vercel and MongoDB. Nothing here is shared between accounts, and nothing one
person does can reach another person's.

Where it is kept: AGENTFORGE_ATLAS_URI, or `auth_mongodb_uri` in the settings
file, if one is set; otherwise the MongoDB AgentForge already runs for the apps
it builds. The address is never written into the code, because it carries a
password.

What is kept:
- users: a name, an address and a salted PBKDF2 hash of the password.
- sessions: the SHA-256 of each sign-in's token and when it stops working, so
  a copy of the table signs nobody in.
- who owns each project and each specification - claimed once, never moved.
- each person's deployment accounts, the secrets among them encrypted
  (secret_box.py).
"""
from __future__ import annotations

import datetime
import hashlib
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from server_modules.services import secret_box

log = logging.getLogger("agentforge.auth")

DB_NAME = "agentforge_cloud"
SESSION_DAYS = 30
MIN_PASSWORD = 8
# Wrong passwords for one name before it has to wait, and for how long.
MAX_FAILURES = 8
LOCKOUT_SECONDS = 15 * 60
# A signed-in person is looked up on every request; the answer is kept briefly.
USER_CACHE_SECONDS = 30
UNREACHABLE = "The account database is not reachable - try again in a moment"

# The deployment accounts each person keeps for themselves. The secret ones
# are sealed before they are stored.
SECRET_KEYS = ("github_token", "vercel_token", "deploy_mongodb_uri")
PLAIN_KEYS = ("aws_profile", "aws_region", "aws_start_url", "aws_sso_region", "github_login")

# What can be owned, and where its owner is written down.
_KINDS = {"project": ("user_projects", "project_name"), "srs": ("user_specs", "srs_id")}

# Where the projects live; set by the server, so the first account can adopt
# the ones made before there were accounts.
projects_dir: Optional[Path] = None

_client = None
_db = None
_lock = threading.RLock()
_indexed = False
_owners: Dict[tuple, str] = {}
_owners_loaded: set = set()
_user_cache: Dict[str, tuple] = {}
_failures: Dict[str, list] = {}


def _now() -> datetime.datetime:
    # Naive UTC, which is what the driver hands back.
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _uri() -> str:
    explicit = os.environ.get("AGENTFORGE_ATLAS_URI", "").strip()
    if explicit:
        return explicit
    try:
        from builder_agent.llm import load_settings
        saved = str(load_settings().get("auth_mongodb_uri", "")).strip()
    except Exception:                                                # noqa: BLE001
        saved = ""
    if saved:
        return saved
    from server_modules.services.mongo import MONGO
    from server_modules.services.mongo_common import get_uri_override
    return get_uri_override() or f"mongodb://127.0.0.1:{MONGO.port}/"


def get_db():
    global _client, _db
    with _lock:
        if _db is None:
            _client = MongoClient(_uri(), serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
            _db = _client[DB_NAME]
        _ensure_indexes(_db)
        return _db


def use_db(db) -> None:
    """Point the store at another database - the tests' in-memory one."""
    global _db, _indexed
    with _lock:
        _db, _indexed = db, False
        _owners.clear()
        _owners_loaded.clear()
        _user_cache.clear()
        _failures.clear()


def _ensure_indexes(db) -> None:
    global _indexed
    if _indexed:
        return
    for collection, field in (("users", "email"), ("users", "username"),
                              ("sessions", "token_hash"), ("user_projects", "project_name"),
                              ("user_specs", "srs_id"), ("user_credentials", "user_id")):
        try:
            db[collection].create_index(field, unique=True)
        except Exception as error:                                   # noqa: BLE001
            log.warning(f"auth index {collection}.{field}: {error}")
    _indexed = True


def _id_of(user_id: str):
    """Accounts made before this module are keyed by ObjectId; new ones by a string."""
    text = str(user_id or "")
    if re.fullmatch(r"[0-9a-f]{24}", text):
        from bson import ObjectId
        return ObjectId(text)
    return text


# -- passwords -------------------------------------------------------------
def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"),
                                 salt.encode("utf-8"), 100_000).hex()
    return hashed, salt


def _verify_password(password: str, hashed: str, salt: str) -> bool:
    check, _ = _hash_password(password, salt)
    return secrets.compare_digest(check, str(hashed or ""))


def _locked_out(login: str) -> bool:
    cutoff = time.time() - LOCKOUT_SECONDS
    recent = [at for at in _failures.get(login, []) if at > cutoff]
    _failures[login] = recent
    return len(recent) >= MAX_FAILURES


def _fail(login: str) -> None:
    _failures.setdefault(login, []).append(time.time())


# -- people ------------------------------------------------------------------
def _admin_emails() -> set:
    raw = os.environ.get("AGENTFORGE_ADMIN_EMAILS", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _is_admin(user: dict) -> bool:
    """The admin changes what is AgentForge's rather than anyone's: its models,
    its database, its image host. Named by AGENTFORGE_ADMIN_EMAILS, or else the
    first account there was."""
    admins = _admin_emails()
    if admins:
        return str(user.get("email", "")).lower() in admins
    try:
        everyone = list(get_db().users.find({}))
    except Exception:                                                # noqa: BLE001
        return False
    first = min(everyone, key=lambda doc: doc.get("created_at") or _now(), default=None)
    return bool(first) and str(first.get("_id")) == str(user.get("_id"))


def _public(user: dict) -> dict:
    return {"id": str(user["_id"]), "username": user.get("username"),
            "email": user.get("email"), "name": user.get("name") or user.get("username"),
            "admin": _is_admin(user)}


def signup_user(username: str, email: str, password: str, name: str = "") -> Dict[str, Any]:
    username = (username or "").strip().lower()
    email = (email or "").strip().lower()
    name = " ".join((name or "").split())[:80] or username
    if not re.fullmatch(r"[a-z0-9_.\-]{3,32}", username):
        return {"error": "A username is 3 to 32 letters, numbers, dots, dashes or underscores"}
    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}", email):
        return {"error": "A valid email address is required"}
    if len(password or "") < MIN_PASSWORD:
        return {"error": f"The password needs at least {MIN_PASSWORD} characters"}
    try:
        db = get_db()
        if db.users.find_one({"username": username}):
            return {"error": "Username is already taken"}
        if db.users.find_one({"email": email}):
            return {"error": "Email is already registered"}
        first = db.users.count_documents({}) == 0
        hashed, salt = _hash_password(password)
        now = _now()
        doc = {"_id": "u" + secrets.token_hex(12), "username": username, "email": email,
               "name": name, "password_hash": hashed, "salt": salt,
               "created_at": now, "last_login": now}
        db.users.insert_one(doc)
        if first:
            # What was on this machine before there were accounts belongs to
            # whoever sets it up, and to nobody after them.
            _adopt_unowned_projects(doc["_id"])
        token = _open_session(doc["_id"])
    except DuplicateKeyError:
        return {"error": "That username or email is already registered"}
    except Exception as error:                                       # noqa: BLE001
        log.error(f"sign up: {error}")
        return {"error": UNREACHABLE}
    return {"ok": True, "token": token, "user": _public(doc)}


def login_user(login: str, password: str) -> Dict[str, Any]:
    login = (login or "").strip().lower()
    if not login or not password:
        return {"error": "Email/username and password are required"}
    if _locked_out(login):
        return {"error": "Too many wrong passwords - wait fifteen minutes and try again"}
    try:
        db = get_db()
        user = db.users.find_one({"username": login}) or db.users.find_one({"email": login})
    except Exception as error:                                       # noqa: BLE001
        log.error(f"sign in: {error}")
        return {"error": UNREACHABLE}
    if not user:
        _hash_password(password)       # as slow as a wrong password, so it tells nothing
        _fail(login)
        return {"error": "Invalid email/username or password"}
    if not _verify_password(password, user.get("password_hash", ""), user.get("salt", "")):
        _fail(login)
        return {"error": "Invalid email/username or password"}
    _failures.pop(login, None)
    try:
        # A token stored in the clear by the earlier sign-in is dropped here.
        db.users.update_one({"_id": user["_id"]},
                            {"$set": {"last_login": _now()}, "$unset": {"token": ""}})
        token = _open_session(str(user["_id"]))
    except Exception as error:                                       # noqa: BLE001
        log.error(f"sign in: {error}")
        return {"error": UNREACHABLE}
    return {"ok": True, "token": token, "user": _public(user)}


# -- sessions -----------------------------------------------------------------
def _digest(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _open_session(user_id) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    get_db().sessions.insert_one({
        "token_hash": _digest(token), "user_id": str(user_id), "created_at": now,
        "expires_at": now + datetime.timedelta(days=SESSION_DAYS)})
    return token


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """The person a sign-in's token belongs to, while it lasts."""
    token = (token or "").strip()
    if not token:
        return None
    digest = _digest(token)
    cached = _user_cache.get(digest)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    try:
        db = get_db()
        session = db.sessions.find_one({"token_hash": digest})
        if not session or (session.get("expires_at") or _now()) <= _now():
            return None
        user = db.users.find_one({"_id": _id_of(session.get("user_id"))})
    except Exception as error:                                       # noqa: BLE001
        log.error(f"session lookup: {error}")
        return None
    if not user:
        return None
    public = _public(user)
    _user_cache[digest] = (public, time.monotonic() + USER_CACHE_SECONDS)
    return public


def logout_user(token: str) -> bool:
    token = (token or "").strip()
    if not token:
        return True
    digest = _digest(token)
    _user_cache.pop(digest, None)
    try:
        get_db().sessions.delete_one({"token_hash": digest})
        return True
    except Exception:                                                # noqa: BLE001
        return False


# -- who owns what -------------------------------------------------------------
def _load(kind: str) -> None:
    if kind in _owners_loaded:
        return
    collection, field = _KINDS[kind]
    for doc in get_db()[collection].find({}):
        if doc.get(field):
            _owners[(kind, str(doc[field]))] = str(doc.get("user_id") or "")
    _owners_loaded.add(kind)


def owner_of(kind: str, key: str) -> Optional[str]:
    """Who owns it, or None. Read on every message the server sends, so kept in memory."""
    with _lock:
        _load(kind)
        return _owners.get((kind, str(key or "")))


def claim(kind: str, key: str, user_id: str) -> bool:
    """Record that `user_id` owns this. False if someone else does - it never moves."""
    key, user_id = str(key or ""), str(user_id or "")
    if not key or not user_id:
        return False
    with _lock:
        current = owner_of(kind, key)
        if current:
            return current == user_id
        collection, field = _KINDS[kind]
        try:
            get_db()[collection].insert_one({field: key, "user_id": user_id, "created_at": _now()})
        except DuplicateKeyError:
            doc = get_db()[collection].find_one({field: key}) or {}
            _owners[(kind, key)] = str(doc.get("user_id") or "")
            return _owners[(kind, key)] == user_id
        _owners[(kind, key)] = user_id
        return True


def release(kind: str, key: str) -> None:
    key = str(key or "")
    with _lock:
        collection, field = _KINDS[kind]
        get_db()[collection].delete_many({field: key})
        _owners.pop((kind, key), None)


def owned(kind: str, user_id: str) -> set:
    with _lock:
        _load(kind)
        return {key for (k, key), owner in _owners.items() if k == kind and owner == str(user_id)}


def owns(user: Optional[dict], kind: str, key: str) -> bool:
    """Is it theirs? Something nobody owns - from before accounts - is the admin's."""
    if not user or not key:
        return False
    owner = owner_of(kind, key)
    if owner is None:
        return bool(user.get("admin"))
    return owner == user.get("id")


def _adopt_unowned_projects(user_id: str) -> None:
    folder = projects_dir
    if not folder or not Path(folder).is_dir():
        return
    for entry in Path(folder).iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            claim("project", entry.name, user_id)


# -- each person's deployment accounts ------------------------------------------
def user_settings(user_id: str) -> Dict[str, str]:
    """This person's deployment accounts, the secrets unsealed."""
    doc = get_db().user_credentials.find_one({"user_id": str(user_id)}) or {}
    plain, sealed = doc.get("plain") or {}, doc.get("sealed") or {}
    out = {key: str(plain.get(key) or "") for key in PLAIN_KEYS}
    out.update({key: secret_box.unseal(sealed.get(key) or "") for key in SECRET_KEYS})
    return out


def save_user_settings(user_id: str, patch: Dict[str, Any]) -> Dict[str, str]:
    """Merge into this person's deployment accounts. An empty value clears one."""
    db = get_db()
    doc = db.user_credentials.find_one({"user_id": str(user_id)}) or {}
    plain, sealed = dict(doc.get("plain") or {}), dict(doc.get("sealed") or {})
    for key, value in (patch or {}).items():
        value = str(value or "").strip()
        if key in PLAIN_KEYS:
            plain[key] = value
        elif key in SECRET_KEYS:
            sealed[key] = secret_box.seal(value)
    db.user_credentials.update_one(
        {"user_id": str(user_id)},
        {"$set": {"plain": plain, "sealed": sealed, "updated_at": _now()}}, upsert=True)
    return user_settings(user_id)


def deploy_secrets(user_id: str) -> Dict[str, str]:
    """What a deployment run for this person signs in with."""
    if not user_id:
        return {}
    settings = user_settings(user_id)
    return {"github_token": settings.get("github_token", ""),
            "vercel_token": settings.get("vercel_token", "")}
