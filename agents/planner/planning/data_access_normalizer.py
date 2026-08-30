"""Data Access Normalizer.

One planning responsibility lives in this file so the flow is easy to follow.
"""
from __future__ import annotations

# Source: image_plan.py — imported helper(s) come from this file.
from agents.planner.planning.image_plan import _app_file, _demo_accounts

# Source: planning_helpers.py — shared planning constants and small helper functions.
from agents.planner.planning.planning_helpers import (
    Any,
    _canonical_actor,
    _dict,
    _records,
    _strings,
    _text,
)

class DataAccessNormalizerMixin:
    """Keep data access normalizer behavior together."""

    # Converts data in the format expected by the next pipeline steps.
    def _normalize_data(self, value: Any) -> list[dict]:
        """Convert data in the standard shape used by the rest of the pipeline."""
        out = []
        # From: agents/planner/planning/planning_helpers.py
        for item in _records(value):
            # From: agents/planner/planning/planning_helpers.py
            collection = _text(item.get("collection"), 100)
            if not collection:
                continue
            fields = []
            # From: agents/planner/planning/planning_helpers.py
            for field in _records(item.get("fields")):
                if field.get("name"):
                    # From: agents/planner/planning/planning_helpers.py
                    fields.append({
                        "name": _text(field.get("name"), 100),
                        "type": _text(field.get("type") or "string", 50),
                        "required": bool(field.get("required")),
                        "rules": _text(field.get("rules"), 400),
                    })
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "collection": collection, "purpose": _text(item.get("purpose"), 500),
                "fields": fields, "indexes": _strings(item.get("indexes"), 200),
                "seed": _dict(item.get("seed")),
                "relationships": _strings(item.get("relationships"), 240),
            })
        return out

    # Converts access in the format expected by the next pipeline steps.
    def _normalize_access(self, value: Any) -> dict:
        """Convert access in the standard shape used by the rest of the pipeline."""
        # From: agents/planner/planning/planning_helpers.py
        access = _dict(value)
        roles = []
        # From: agents/planner/planning/planning_helpers.py
        for role in _records(access.get("roles")):
            # From: agents/planner/planning/planning_helpers.py
            name = _text(role.get("name"), 80)
            if name:
                # From: agents/planner/planning/planning_helpers.py
                roles.append({
                    "name": _canonical_actor(name, name), "home": _text(role.get("home"), 180),
                    "permissions": _strings(role.get("permissions"), 300),
                    "restrictions": _strings(role.get("restrictions"), 300),
                })
        accounts = []
        # From: agents/planner/planning/planning_helpers.py
        for account in _records(access.get("demo_accounts")):
            if account.get("email") and account.get("password"):
                # From: agents/planner/planning/planning_helpers.py
                accounts.append({
                    "email": _text(account.get("email"), 160),
                    "password": str(account.get("password")),
                    "role": _canonical_actor(account.get("role"), "user"),
                    "name": _text(account.get("name") or "Demo User", 120),
                })
        required = bool(access.get("authentication_required"))
        # From: agents/planner/planning/image_plan.py
        # From: agents/planner/planning/planning_helpers.py
        return {
            "authentication_required": required,
            "signup": _text(access.get("signup") or "not-applicable", 30),
            "signup_role": _text(access.get("signup_role"), 80),
            "roles": roles,
            "demo_accounts": _demo_accounts(accounts, roles) if required else accounts,
        }

    # Converts apis in the format expected by the next pipeline steps.
    def _normalize_apis(self, value: Any) -> list[dict]:
        """Convert apis in the standard shape used by the rest of the pipeline."""
        out = []
        # From: agents/planner/planning/planning_helpers.py
        for item in _records(value):
            # From: agents/planner/planning/planning_helpers.py
            path = _text(item.get("path"))
            if not path:
                continue
            # From: agents/planner/planning/image_plan.py
            # From: agents/planner/planning/planning_helpers.py
            handler = (_text(item.get("handler_file")).replace("\\", "/")
                       or _app_file(path, "route.js"))
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "name": _text(item.get("name") or f"api-{len(out)+1}", 120),
                "method": _text(item.get("method") or "GET", 10).upper(), "path": path,
                "handler_file": handler, "called_from": _strings(item.get("called_from"), 200),
                "audience": _text(item.get("audience") or "PUBLIC", 100),
                "request": _records(item.get("request")),
                "response": _records(item.get("response")), "errors": _records(item.get("errors")),
                "side_effects": _strings(item.get("side_effects"), 400),
                "success_effect": _text(item.get("success_effect"), 500),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
            })
        return out

    # Converts capabilities in the format expected by the next pipeline steps.
    def _normalize_capabilities(self, value: Any) -> list[dict]:
        """Convert capabilities in the standard shape used by the rest of the pipeline."""
        out = []
        # From: agents/planner/planning/planning_helpers.py
        for index, item in enumerate(_records(value), 1):
            # From: agents/planner/planning/planning_helpers.py
            behavior = _text(item.get("behavior") or item.get("requirement"), 700)
            if not behavior:
                continue
            # From: agents/planner/planning/planning_helpers.py
            actor = _canonical_actor(item.get("actor") or item.get("who"), "user")
            # From: agents/planner/planning/planning_helpers.py
            proof_points = (_strings(item.get("proof"), 500)
                            if isinstance(item.get("proof"), list)
                            else [_text(item.get("proof"), 500)] if item.get("proof") else [])
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "id": _text(item.get("id") or f"CAP-{index:03d}").upper(),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
                "actor": actor, "who": actor,
                "behavior": behavior, "requirement": behavior,
                "proof": "; ".join(proof_points), "proof_points": proof_points,
                "files": _strings(item.get("files"), 200),
                "route": _text(item.get("route"), 180), "e2e": bool(item.get("e2e", True)),
            })
        return out
