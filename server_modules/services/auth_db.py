"""MongoDB Atlas authentication and project isolation service for AgentForge."""
from __future__ import annotations

import datetime
import hashlib
import logging
import os
import secrets
import threading
from typing import Any, Dict, List, Optional

import pymongo
from pymongo import MongoClient

log = logging.getLogger("agentforge.auth")

MONGO_ATLAS_URI = os.environ.get(
    "AGENTFORGE_ATLAS_URI",
    "mongodb+srv://ravindu2232_db_user:niVxPPMkUeJGIPMB@cluster0.3xjuesg.mongodb.net/?appName=Cluster0",
)
DB_NAME = "agentforge_cloud"

_client: Optional[MongoClient] = None
_client_lock = threading.Lock()


def get_db():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = MongoClient(MONGO_ATLAS_URI, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
    return _client[DB_NAME]


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return hashed, salt


def _verify_password(password: str, hashed: str, salt: str) -> bool:
    check, _ = _hash_password(password, salt)
    return secrets.compare_digest(check, hashed)


def signup_user(username: str, email: str, password: str, name: str = "") -> Dict[str, Any]:
    """Register a new user in MongoDB Atlas."""
    username = (username or "").strip().lower()
    email = (email or "").strip().lower()
    name = (name or "").strip() or username

    if not username or len(username) < 3:
        return {"error": "Username must be at least 3 characters"}
    if not email or "@" not in email:
        return {"error": "A valid email address is required"}
    if not password or len(password) < 6:
        return {"error": "Password must be at least 6 characters"}

    try:
        db = get_db()
        users = db.users

        # Check existing
        existing = users.find_one({"$or": [{"username": username}, {"email": email}]})
        if existing:
            if existing.get("username") == username:
                return {"error": "Username is already taken"}
            return {"error": "Email is already registered"}

        hashed, salt = _hash_password(password)
        token = secrets.token_hex(32)

        doc = {
            "username": username,
            "email": email,
            "name": name,
            "password_hash": hashed,
            "salt": salt,
            "token": token,
            "created_at": datetime.datetime.utcnow(),
            "last_login": datetime.datetime.utcnow(),
        }
        res = users.insert_one(doc)
        user_id = str(res.inserted_id)

        # Claim any existing untagged projects on disk for the first user
        claim_unassigned_projects(user_id)

        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "name": name,
            },
        }
    except Exception as e:
        log.error(f"Error signing up user: {e}")
        return {"error": f"Failed to register user: {str(e)}"}


def login_user(login: str, password: str) -> Dict[str, Any]:
    """Authenticate user with username or email."""
    login = (login or "").strip().lower()
    if not login or not password:
        return {"error": "Email/username and password are required"}

    try:
        db = get_db()
        users = db.users

        user = users.find_one({"$or": [{"username": login}, {"email": login}]})
        if not user:
            return {"error": "Invalid email/username or password"}

        if not _verify_password(password, user.get("password_hash", ""), user.get("salt", "")):
            return {"error": "Invalid email/username or password"}

        token = secrets.token_hex(32)
        users.update_one(
            {"_id": user["_id"]},
            {"$set": {"token": token, "last_login": datetime.datetime.utcnow()}},
        )

        user_id = str(user["_id"])
        # Ensure projects exist for user
        claim_unassigned_projects(user_id)

        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user_id,
                "username": user.get("username"),
                "email": user.get("email"),
                "name": user.get("name") or user.get("username"),
            },
        }
    except Exception as e:
        log.error(f"Error logging in: {e}")
        return {"error": f"Failed to login: {str(e)}"}


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve user given their session token."""
    token = (token or "").strip()
    if not token:
        return None
    try:
        db = get_db()
        user = db.users.find_one({"token": token})
        if not user:
            return None
        return {
            "id": str(user["_id"]),
            "username": user.get("username"),
            "email": user.get("email"),
            "name": user.get("name") or user.get("username"),
        }
    except Exception as e:
        log.error(f"Error looking up user by token: {e}")
        return None


def logout_user(token: str) -> bool:
    """Clear session token."""
    token = (token or "").strip()
    if not token:
        return True
    try:
        db = get_db()
        db.users.update_one({"token": token}, {"$unset": {"token": ""}})
        return True
    except Exception:
        return False


def assign_project_to_user(user_id: str, project_name: str) -> bool:
    """Assign a project to a specific user."""
    user_id = (user_id or "").strip()
    project_name = (project_name or "").strip()
    if not user_id or not project_name:
        return False
    try:
        db = get_db()
        db.user_projects.update_one(
            {"project_name": project_name},
            {
                "$set": {
                    "project_name": project_name,
                    "user_id": user_id,
                    "updated_at": datetime.datetime.utcnow(),
                },
                "$setOnInsert": {"created_at": datetime.datetime.utcnow()},
            },
            upsert=True,
        )
        return True
    except Exception as e:
        log.error(f"Error assigning project {project_name} to user {user_id}: {e}")
        return False


def get_user_project_names(user_id: str) -> List[str]:
    """Return all project names assigned to this user."""
    user_id = (user_id or "").strip()
    if not user_id:
        return []
    try:
        db = get_db()
        cursor = db.user_projects.find({"user_id": user_id}, {"project_name": 1})
        return [doc["project_name"] for doc in cursor if doc.get("project_name")]
    except Exception as e:
        log.error(f"Error getting projects for user {user_id}: {e}")
        return []


def claim_unassigned_projects(user_id: str) -> None:
    """Claim any existing unassigned projects on disk for this user."""
    user_id = (user_id or "").strip()
    if not user_id:
        return
    try:
        from pathlib import Path
        prod_dir = Path("production-ready")
        if not prod_dir.is_dir():
            return
        db = get_db()
        # Find which projects already have an owner
        assigned = set(doc["project_name"] for doc in db.user_projects.find({}, {"project_name": 1}))
        for d in prod_dir.iterdir():
            if d.is_dir() and not d.name.startswith(".") and d.name not in assigned:
                db.user_projects.insert_one({
                    "project_name": d.name,
                    "user_id": user_id,
                    "created_at": datetime.datetime.utcnow(),
                })
                assigned.add(d.name)
    except Exception as e:
        log.debug(f"claim_unassigned_projects failed: {e}")
