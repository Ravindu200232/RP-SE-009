"""Analyze + requirement-gathering endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.questions import AnswersPayload
from ..services import orchestrator

router = APIRouter(prefix="/projects", tags=["analyze"])


@router.post("/{project_id}/analyze")
async def analyze(project_id: str):
    try:
        return await orchestrator.analyze(project_id)
    except KeyError:
        raise HTTPException(404, "project not found")


@router.get("/{project_id}/questions")
async def get_questions(project_id: str):
    return await orchestrator.get_questions(project_id)


@router.post("/{project_id}/answers")
async def submit_answers(project_id: str, payload: AnswersPayload):
    try:
        answers = [a.model_dump() for a in payload.answers]
        return await orchestrator.submit_answers(project_id, answers)
    except KeyError:
        raise HTTPException(404, "project not found")
