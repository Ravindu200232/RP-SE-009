"""Customer-led requirement interview endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..schemas.questions import InterviewAnswer
from ..services import orchestrator
from ..services import integrations
from ..models import repositories as repo

log = logging.getLogger("agentforge.srs.interview")

router = APIRouter(prefix="/projects", tags=["interview"])


class IntegrationAnswers(BaseModel):
    answers: list[dict]


@router.get("/{project_id}/integrations")
async def integration_questions(project_id: str):
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        q = integrations.questions()
    except Exception as exc:
        log.warning("integrations.questions failed: %s", exc)
        q = []
    return {"questions": q, "answers": project.get("integrations", []),
            "confirmed": bool(project.get("integrations_confirmed"))}


@router.post("/{project_id}/integrations")
async def integration_answers(project_id: str, payload: IntegrationAnswers):
    if not await repo.get_project(project_id):
        raise HTTPException(404, "Project not found")
    try:
        metadata = integrations.save(project_id, payload.answers)
    except ValueError as error:
        raise HTTPException(400, str(error))
    await repo.update_project(project_id, {"integrations": metadata, "integrations_confirmed": True})
    return {"answers": metadata, "confirmed": True}


@router.get("/{project_id}/interview")
async def interview_state(project_id: str):
    try:
        return await orchestrator.interview_state(project_id)
    except Exception as exc:
        log.error("Failed to retrieve interview state for %s: %s", project_id, exc, exc_info=True)
        raise HTTPException(500, f"Interview could not load: {exc}")


@router.post("/{project_id}/interview/answer")
async def interview_answer(project_id: str, payload: InterviewAnswer):
    try:
        return await orchestrator.interview_answer(
            project_id,
            key=payload.key,
            value=payload.value,
            text=payload.text or "",
            selected=payload.selected,
            custom=payload.custom or "",
            attachments=payload.attachments,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc) or "project not found")
