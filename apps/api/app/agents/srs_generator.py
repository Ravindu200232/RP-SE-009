"""SrsJsonGeneratorAgent — produce the full SRS JSON.

Strategy (robust by construction):
  1. Build a deterministic, domain-specific, schema-valid skeleton from the
     domain library + the user's answers. This always succeeds.
  2. If Ollama is reachable, ask the model for a focused ENRICHMENT PACK — just
     the domain content (tables, modules, requirements, workflows, risks…) — and
     merge it into the skeleton here, assembling a guaranteed-valid SRS. This is
     far more reliable and faster than asking the model to regenerate ~1500
     lines of strict JSON in one shot.
  3. On any failure, keep the deterministic SRS (never a generic empty one).
"""
from __future__ import annotations

from ..knowledge.offline_srs import build_offline_srs, merge_pack
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..schemas.srs import summarize_srs, validate_srs
from ..services.events import bus
from .state import AgentState

_SYS = (
    "You are a senior requirements engineer. Given a non-technical user's app "
    "idea and their answers, produce the DOMAIN-SPECIFIC content for a software "
    "requirements specification as STRICT JSON (no prose, no markdown). Tailor "
    "everything to THIS idea — real tables, real modules, real requirements. "
    "Return ONLY a JSON object with these keys:\n"
    "{\n"
    '  "system_category": str,\n'
    '  "app_summary": {"business_goal": str, "short_description": str, "target_users": [str]},\n'
    '  "roles": [{"role_key": snake_case, "role_name": str, "description": str}],\n'
    '  "main_modules": [str],\n'
    '  "tables": [{"table_name": snake_case, "description": str, "fields": ['
    '{"name": str, "type": "uuid|string|text|integer|decimal|boolean|date|datetime|enum|json|foreign_key", '
    '"primary_key": bool, "nullable": bool, "unique": bool, "references": "table.id", "values": [str], "default": any}]}],\n'
    '  "relationships": [{"from": "table.col", "to": "table.col", "type": "one_to_many|many_to_one|one_to_one|many_to_many", "description": str}],\n'
    '  "functional_requirements": [{"module": str, "requirement": "The system shall …", "priority": "high|medium|low"}],\n'
    '  "non_functional_requirements": [{"category": str, "requirement": str}],\n'
    '  "business_workflows": [{"workflow_name": str, "steps": [str]}],\n'
    '  "validation_rules": [{"field": str, "rule": str}],\n'
    '  "notification_rules": [{"event": str, "recipients": [str], "channels": [str]}],\n'
    '  "reporting_requirements": [{"report_name": str, "filters": [str], "exports": ["PDF","Excel"]}],\n'
    '  "integration_requirements": [{"name": str, "type": str, "description": str, "required": bool}],\n'
    '  "security_requirements": [str],\n'
    '  "risk_priority": [{"area": str, "risk": str, "severity": "High|Medium|Low", "reason": str, "mitigation": str}],\n'
    '  "ambiguities": [{"area": str, "description": str, "assumption_made": str, "needs_clarification": bool}]\n'
    "}\n"
    "Do NOT include users/roles/permissions/audit_logs tables — those are added "
    "automatically. Provide at least 6 domain tables and at least 8 functional "
    "requirements. Reference foreign keys with the exact 'table.id' form."
)


def _answers_digest(questions: list[dict], answers: list[dict]) -> str:
    by_id = {q["id"]: q for q in questions}
    lines = []
    for a in answers:
        q = by_id.get(a.get("question_id"))
        if not q:
            continue
        val = a.get("raw_text") or a.get("value")
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        lines.append(f"- {q['question']} → {val}")
    return "\n".join(lines) or "(no explicit answers; use sensible defaults)"


def _validate_pack(d: dict) -> None:
    """Minimal gate so the repair loop only fires when essentials are missing."""
    if not isinstance(d, dict):
        raise ValueError("pack must be a JSON object")
    tables = d.get("tables")
    if not isinstance(tables, list) or len([t for t in tables if isinstance(t, dict) and t.get("table_name")]) < 4:
        raise ValueError("provide at least 4 domain 'tables' (each with a table_name and fields)")
    frs = d.get("functional_requirements")
    if not isinstance(frs, list) or len([f for f in frs if isinstance(f, dict) and f.get("requirement")]) < 5:
        raise ValueError("provide at least 5 'functional_requirements' (each with a 'requirement')")


async def generate_srs_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    project = state.get("project", {})
    brief = state.get("brief", "")
    questions = state.get("questions", [])
    answers = state.get("answers", [])

    await bus.log(pid, "SrsJsonGeneratorAgent", "Composing domain-specific SRS skeleton…", progress=10)
    skeleton = build_offline_srs(project=project, answers=answers, session=state.get("session"), brief=brief)
    try:
        validate_srs(skeleton)
    except Exception as exc:  # noqa: BLE001 - should not happen; log if it does
        await bus.error(pid, "SrsJsonGeneratorAgent", f"Skeleton failed validation: {exc}")

    srs = skeleton
    try:
        llm = get_llm()
        await bus.emit(pid, "SrsJsonGeneratorAgent", "Asking the LLM for domain-specific content…", progress=35)
        digest = _answers_digest(questions, answers)
        user = (
            f"DETECTED DOMAIN: {state.get('classification', {}).get('detected_domain')}\n\n"
            f"USER IDEA / BRIEF:\n{brief[:3000]}\n\n"
            f"USER ANSWERS:\n{digest}\n\n"
            "Now produce the enrichment JSON described in the system message, "
            "tailored precisely to this idea."
        )
        pack = await llm.complete_json(
            system=_SYS, user=user, validator=_validate_pack,
            label="srs_enrich", trace_sink=lambda p: bus.trace(pid, p),
        )
        merged = merge_pack(skeleton, pack)
        validate_srs(merged)  # guaranteed by construction, but be safe
        srs = merged
        doc = srs["srs_document"]
        await bus.emit(pid, "SrsJsonGeneratorAgent",
                       f"LLM enrichment merged: {len(doc['database_design']['tables'])} tables, "
                       f"{len(doc['functional_requirements'])} FR.", level="success", progress=60)
    except LLMUnavailable as exc:
        await bus.emit(pid, "SrsJsonGeneratorAgent",
                       f"LLM not used ({str(exc)[:140]}) — using the deterministic domain SRS.",
                       level="warn", progress=60)
    except LLMRepairFailed as exc:
        await bus.error(pid, "SrsJsonGeneratorAgent",
                        f"LLM enrichment didn't validate after retries; kept deterministic SRS. ({exc.label})",
                        data={"raw_preview": (exc.raw or "")[:500]})
    except Exception as exc:  # noqa: BLE001
        await bus.error(pid, "SrsJsonGeneratorAgent", f"SRS enrichment error: {exc}; kept deterministic SRS.")

    summary = summarize_srs(srs)
    await bus.emit(
        pid, "SrsJsonGeneratorAgent",
        f"SRS ready: {summary['functional']} FR, {summary['non_functional']} NFR, "
        f"{summary['tables']} tables, {summary['roles']} roles.",
        level="success", progress=70, data={"summary": summary},
    )
    return {**state, "srs": srs}
