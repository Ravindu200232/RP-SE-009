"""Design-system records associated with one SRS project."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import design_spec

router = APIRouter(prefix="/projects", tags=["design-spec"])


class DesignSpecDraft(BaseModel):
    spec: dict = Field(default_factory=dict)
    source: str = Field(default="design-customizer", max_length=80)


@router.get("/{project_id}/design-spec")
async def get_design_spec(project_id: str):
    return design_spec.get(project_id)


@router.post("/{project_id}/design-spec/draft")
async def draft_design_spec(project_id: str, request: DesignSpecDraft):
    return design_spec.draft(project_id, request.spec, request.source)


@router.post("/{project_id}/design-spec/{version}/approve")
async def approve_design_spec(project_id: str, version: int):
    try:
        return design_spec.approve(project_id, version)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
