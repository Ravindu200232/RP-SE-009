"""SRS generation + read endpoints (requirements, diagrams, ambiguities, risks)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import repositories as repo
from ..services import orchestrator

router = APIRouter(prefix="/projects", tags=["srs"])


async def _doc_or_404(project_id: str) -> dict:
    srs = await orchestrator.latest_srs(project_id)
    if not srs:
        raise HTTPException(404, "no SRS generated yet")
    return srs["srs_document"]


@router.post("/{project_id}/generate-srs")
async def generate_srs(project_id: str):
    try:
        result = await orchestrator.generate_srs(project_id)
    except KeyError:
        raise HTTPException(404, "project not found")
    return {"project": result["project"], "version": result["version"], "summary": result["summary"]}


@router.get("/{project_id}/srs-json")
async def srs_json(project_id: str):
    srs = await orchestrator.latest_srs(project_id)
    if not srs:
        raise HTTPException(404, "no SRS generated yet")
    return srs


@router.get("/{project_id}/requirements")
async def requirements(project_id: str):
    doc = await _doc_or_404(project_id)
    return {
        "functional_requirements": doc.get("functional_requirements", []),
        "non_functional_requirements": doc.get("non_functional_requirements", []),
    }


@router.get("/{project_id}/diagrams")
async def diagrams(project_id: str):
    stored = await repo.list_diagrams(project_id)
    if stored:
        return {"diagrams": stored}
    doc = await _doc_or_404(project_id)
    return {"diagrams": doc.get("diagrams", [])}


@router.get("/{project_id}/ambiguities")
async def ambiguities(project_id: str):
    doc = await _doc_or_404(project_id)
    return {"ambiguities": doc.get("ambiguities", []), "assumptions": doc.get("assumptions", [])}


@router.get("/{project_id}/risks")
async def risks(project_id: str):
    doc = await _doc_or_404(project_id)
    return {"risk_priority": doc.get("risk_priority", [])}
