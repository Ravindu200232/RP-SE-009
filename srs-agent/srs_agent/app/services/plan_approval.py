"""The gate between a plan and the SRS.

Approval is the point where a plan stops being a proposal and becomes the record
of what gets specified, so the refusals here are deliberate: you cannot approve
a superseded version, and you cannot approve a plan that still has a question we
said we needed answered. `state()` returns the same verdict the approve endpoint
would, so the button is never offered for something that will be refused.
"""
from __future__ import annotations

import hashlib
import json

from ..models import repositories as repo
from ..schemas.project import now_iso


def content_hash(plan: dict) -> str:
    """A stable fingerprint of the plan itself.

    Deliberately excludes approval, timestamps and rendering, so recording an
    approval cannot change what was approved.
    """
    payload = json.dumps(plan or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def required_open_questions(plan: dict) -> list[str]:
    return [
        str(q.get("question", "")).strip()
        for q in (plan or {}).get("open_questions") or []
        if isinstance(q, dict) and q.get("required") and str(q.get("question", "")).strip()
    ]


def _verdict(doc: dict | None, version: int | None = None) -> tuple[bool, str]:
    if not doc:
        return False, "no plan has been generated yet"
    if version is not None and int(version) != int(doc.get("version", 0)):
        return False, "superseded — a newer version of the plan exists"
    if doc.get("approved"):
        return False, "already approved"
    blocking = required_open_questions(doc.get("plan") or {})
    if blocking:
        head = blocking[0]
        more = f" (+{len(blocking) - 1} more)" if len(blocking) > 1 else ""
        return False, f"still to settle: {head}{more}"
    return True, ""


async def state(project_id: str) -> dict:
    """The latest plan plus whether it can be approved, and why not."""
    doc = await repo.latest_plan(project_id)
    can, reason = _verdict(doc)
    plans = await repo.list_plans(project_id)
    return {
        "plan": (doc or {}).get("plan"),
        "markdown": (doc or {}).get("markdown", ""),
        "version": (doc or {}).get("version"),
        "versions": [p.get("version") for p in plans],
        "content_hash": (doc or {}).get("content_hash", ""),
        "change_request": (doc or {}).get("change_request", ""),
        "approved": bool((doc or {}).get("approved")),
        "approved_at": (doc or {}).get("approved_at"),
        "can_approve": can,
        "reason": reason,
        "open_questions": (doc or {}).get("plan", {}).get("open_questions", []),
    }


async def approve(project_id: str, version: int | None = None) -> dict:
    """Approve the latest plan, or explain why it cannot be approved."""
    doc = await repo.latest_plan(project_id)
    can, reason = _verdict(doc, version)
    if not can:
        return {"approved": False, "reason": reason,
                "version": (doc or {}).get("version")}

    await repo.update_plan(doc["id"], {
        "approved": True,
        "approved_at": now_iso(),
        "approved_by": "local-user",
    })
    await repo.update_project(project_id, {"status": "plan_approved"})
    return {"approved": True, "reason": "", "version": doc["version"],
            "content_hash": doc.get("content_hash", "")}


async def approved_plan(project_id: str) -> dict | None:
    """The approved plan document, or None if nothing has been approved."""
    for doc in reversed(await repo.list_plans(project_id)):
        if doc.get("approved"):
            return doc
    return None
