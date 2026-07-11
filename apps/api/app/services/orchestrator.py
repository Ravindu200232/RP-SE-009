"""Orchestration service — ties the LangGraph workflows to persistence.

Routers stay thin; all multi-step flows (analyze, answer, generate, customize)
live here so the same logic is reused by tests.
"""
from __future__ import annotations

import re

from ..agents.coverage_auditor import build_followups, compute_coverage
from ..extraction.brief import build_brief
from ..graph.workflow import run_analysis, run_customization, run_generation
from ..models import repositories as repo
from ..schemas.project import now_iso
from ..schemas.srs import summarize_srs
from ..services import storage
from ..services.events import bus


def _title_from_idea(idea: str) -> str:
    t = re.sub(r"\s+", " ", (idea or "").strip())
    if not t:
        return "Untitled Project"
    first = re.split(r"[.!?\n]", t)[0]
    return (first[:60] + "…") if len(first) > 60 else first


def _bump_minor(version: str) -> str:
    parts = (version or "1.0.0").split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        parts[1] = str(int(parts[1]) + 1)
        parts[2] = "0"
    except ValueError:
        return "1.1.0"
    return ".".join(parts[:3])


# ── create / inputs ──────────────────────────────────────────
async def create_project(idea: str, language: str | None = None) -> dict:
    pid = repo.new_id("prj_")
    project = {
        "id": pid, "title": _title_from_idea(idea), "raw_idea": idea,
        "detected_domain": "Custom", "domain_key": "custom", "status": "intake",
        "current_version": "0.0.0", "language": language or "English",
        "classification": None, "complexity": None, "suggested_stack": None,
        "coverage_score": 0.0, "needs_clarification": False, "clarification_reason": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await repo.create_project(project)
    # The raw idea is carried on the project itself and merged by build_brief,
    # so we do not duplicate it as a separate source.
    await bus.emit(pid, "System", "Project created.", channel="agent_events", level="success")
    return project


async def add_source(project_id: str, mode: str, text: str, filename: str | None = None,
                     meta: dict | None = None) -> dict:
    src = {"id": repo.new_id("src_"), "project_id": project_id, "mode": mode,
           "filename": filename, "text": text or "", "meta": meta or {}, "created_at": now_iso()}
    await repo.add_source(src)
    await bus.emit(project_id, "IntakeExtractorAgent",
                   f"Added {mode} source" + (f" ({filename})" if filename else "") +
                   f" — {len(text or '')} chars extracted.", channel="agent_events")
    return src


async def _brief_for(project: dict) -> str:
    sources = await repo.list_sources(project["id"])
    return build_brief(project.get("raw_idea", ""), sources)


def _fallback_analysis(state: dict) -> dict:
    """Pure-deterministic analysis (no LLM, no graph) used as the last-resort net."""
    from ..agents.domain_classifier import _complexity, _stack
    from ..agents.intake import _content_only, detect_language, looks_like_nonsense
    from ..agents.question_planner import _deterministic_questions
    from ..graph.workflow import _CLARIFY_QUESTIONS
    from ..knowledge.domains import classify_domain, get_domain

    brief = state.get("brief", "")
    nonsense, reason = looks_like_nonsense(_content_only(brief))
    key, conf, label = classify_domain(brief)
    dom = get_domain(key)
    classification = {
        "domain_key": key, "detected_domain": label, "app_type": dom["app_type_primary"],
        "confidence": conf, "similar_patterns": 2 if key != "custom" else 0,
        "reasoning": "Deterministic keyword classification (LLM path unavailable).",
    }
    questions = list(_CLARIFY_QUESTIONS) if nonsense else _deterministic_questions(brief, key, conf)
    return {
        **state, "classification": classification, "questions": questions,
        "needs_clarification": nonsense, "clarification_reason": reason,
        "language": detect_language(brief),
        "project": {**state.get("project", {}),
                    "complexity": _complexity(key, brief), "suggested_stack": _stack(key)},
    }


# ── analyze ──────────────────────────────────────────────────
async def analyze(project_id: str) -> dict:
    project = await repo.get_project(project_id)
    if not project:
        raise KeyError("project not found")
    await repo.update_project(project_id, {"status": "analyzing"})
    brief = await _brief_for(project)

    state = {
        "project_id": project_id, "project": project, "raw_idea": project.get("raw_idea", ""),
        "brief": brief, "language": project.get("language", "English"),
    }
    # The graph nodes already fall back to deterministic on LLM failure; this
    # outer net guarantees /analyze NEVER 500s on any unexpected error.
    try:
        result = await run_analysis(state)
        if not result.get("questions"):
            raise RuntimeError("analysis produced no questions")
    except Exception as exc:  # noqa: BLE001
        await bus.error(project_id, "AnalyzerWorkflow",
                        f"Analysis failed ({exc}); using deterministic fallback.")
        result = _fallback_analysis(state)

    classification = result.get("classification") or {}
    questions = result.get("questions", [])
    needs_clar = bool(result.get("needs_clarification"))
    rproject = result.get("project", project)

    update = {
        "classification": classification or None,
        "detected_domain": classification.get("detected_domain", project.get("detected_domain", "Custom")),
        "domain_key": classification.get("domain_key", project.get("domain_key", "custom")),
        "complexity": rproject.get("complexity"),
        "suggested_stack": rproject.get("suggested_stack"),
        "language": result.get("language", project.get("language")),
        "needs_clarification": needs_clar,
        "clarification_reason": result.get("clarification_reason"),
        "status": "needs_clarification" if needs_clar else "questioning",
    }
    await repo.update_project(project_id, update)

    session = {"id": repo.new_id("qs_"), "project_id": project_id, "questions": questions,
               "total": len(questions), "coverage_score": 0.0, "complete": False, "created_at": now_iso()}
    await repo.save_question_session(session)

    project = await repo.get_project(project_id)
    return {"project": project, "classification": classification,
            "needs_clarification": needs_clar, "clarification_reason": update["clarification_reason"],
            "questions": questions}


async def get_questions(project_id: str) -> dict:
    session = await repo.get_question_session(project_id)
    if not session:
        return {"session": None, "questions": []}
    return {"session": session, "questions": session.get("questions", [])}


# ── answers ──────────────────────────────────────────────────
async def submit_answers(project_id: str, answers: list[dict]) -> dict:
    project = await repo.get_project(project_id)
    if not project:
        raise KeyError("project not found")
    await repo.save_answers(project_id, answers)
    brief = await _brief_for(project)
    session = await repo.get_question_session(project_id) or {"questions": []}
    questions = session.get("questions", [])

    cov = compute_coverage(brief, questions, answers)
    follow_ups: list[dict] = []
    if not cov["complete"] and cov["critical_missing"]:
        follow_ups = build_followups(project.get("domain_key", "custom"),
                                     cov["critical_missing"], start_index=len(questions) + 1)
        if follow_ups:
            questions = questions + follow_ups
            session["questions"] = questions
            session["total"] = len(questions)

    session["coverage_score"] = cov["score"]
    session["complete"] = cov["complete"]
    await repo.save_question_session(session)
    await repo.update_project(project_id, {"coverage_score": cov["score"]})
    await bus.emit(project_id, "CoverageAuditorAgent",
                   f"Answers recorded — coverage {cov['score']}%.",
                   channel="agent_events", level="success", data={"coverage": cov})
    return {"coverage_score": cov["score"], "complete": cov["complete"], "follow_up_questions": follow_ups}


# ── generate ─────────────────────────────────────────────────
async def generate_srs(project_id: str) -> dict:
    project = await repo.get_project(project_id)
    if not project:
        raise KeyError("project not found")
    brief = await _brief_for(project)
    session = await repo.get_question_session(project_id) or {"questions": []}
    answers = await repo.get_answers(project_id)

    state = {
        "project_id": project_id, "project": project, "raw_idea": project.get("raw_idea", ""),
        "brief": brief, "language": project.get("language", "English"),
        "classification": project.get("classification") or {},
        "questions": session.get("questions", []), "answers": answers, "session": session,
    }
    result = await run_generation(state)
    srs = result["srs"]
    version = "1.0.0"
    srs["srs_document"]["version"] = version

    storage.save_srs_json(project_id, srs, version)
    await repo.save_version({"id": repo.new_id("ver_"), "project_id": project_id, "version": version,
                             "label": "Initial generation", "srs": srs, "diff_summary": [],
                             "created_at": now_iso()})
    await repo.save_diagrams(project_id, srs["srs_document"].get("diagrams", []))
    await repo.update_project(project_id, {"status": "generated", "current_version": version})

    summary = summarize_srs(srs)
    project = await repo.get_project(project_id)
    return {"project": project, "version": version, "summary": summary, "srs": srs}


# ── customize ────────────────────────────────────────────────
async def customize(project_id: str, prompt: str) -> dict:
    project = await repo.get_project(project_id)
    if not project:
        raise KeyError("project not found")
    latest = await repo.latest_version(project_id)
    if not latest:
        raise ValueError("no SRS to customize yet; generate first")

    state = {"project_id": project_id, "project": project, "srs": latest["srs"],
             "customization_prompt": prompt}
    result = await run_customization(state)
    srs = result["srs"]
    diff = result.get("diff_summary", [])
    version = _bump_minor(latest["version"])
    srs["srs_document"]["version"] = version

    storage.save_srs_json(project_id, srs, version)
    await repo.save_version({"id": repo.new_id("ver_"), "project_id": project_id, "version": version,
                             "label": f"Customized: {prompt[:60]}", "srs": srs, "diff_summary": diff,
                             "created_at": now_iso()})
    await repo.save_diagrams(project_id, srs["srs_document"].get("diagrams", []))
    await repo.update_project(project_id, {"status": "customized", "current_version": version})

    summary = summarize_srs(srs)
    project = await repo.get_project(project_id)
    return {"project": project, "version": version, "diff_summary": diff, "summary": summary, "srs": srs}


# ── read helpers ─────────────────────────────────────────────
async def project_detail(project_id: str) -> dict:
    project = await repo.get_project(project_id)
    if not project:
        raise KeyError("project not found")
    latest = await repo.latest_version(project_id)
    versions = await repo.list_versions(project_id)
    srs = latest["srs"] if latest else None
    return {"project": project, "srs": srs,
            "summary": summarize_srs(srs) if srs else None,
            "versions": versions}


async def latest_srs(project_id: str) -> dict | None:
    latest = await repo.latest_version(project_id)
    return latest["srs"] if latest else None
