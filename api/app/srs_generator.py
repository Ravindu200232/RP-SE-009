from __future__ import annotations

import json
import re
from typing import Any

from .common import (
    get_dataset_examples,
    guess_project_name,
    has_answer_value,
    infer_domain,
    load_template,
    normalize_project_name,
    parse_json_object,
    template_excerpt,
    to_list,
    today_iso,
)
from .config import DEEPSEEK_MODEL, QUESTION_DEFAULTS, REQUIRED_PATHS
from .orchestrator import call_ollama_text, model_config
from .question_maker import build_interview_workspace, build_question_plan, infer_features, missing_interview_questions
from .srs_sections import apply_deepseek_srs_content_pack, build_appendices_payload, build_sections_payload
from .srs_sections import build_service_catalog


def deepseek_srs_content_pack(session: dict[str, Any], srs: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
    domain = info.get("domain") or infer_domain(session.get("idea", ""))
    examples = get_dataset_examples(domain) if domain and domain != "General" else []
    interview_workspace = build_interview_workspace(session)
    interview_answers = [
        {
            "section": item["section"],
            "question": item["question"],
            "answer": item["answer_text"],
        }
        for item in interview_workspace["interview_questions"]
        if item["answered"]
    ]
    seed = {
        "metadata": srs.get("metadata", {}),
        "sections": {
            "introduction": srs.get("sections", {}).get("introduction", {}),
            "overall_description": srs.get("sections", {}).get("overall_description", {}),
            "external_interface_requirements": srs.get("sections", {}).get("external_interface_requirements", {}),
            "system_features": srs.get("sections", {}).get("system_features", []),
            "other_nonfunctional_requirements": srs.get("sections", {}).get("other_nonfunctional_requirements", {}),
            "other_requirements": srs.get("sections", {}).get("other_requirements", {}),
        },
        "services": srs.get("services", []),
    }
    prompt = f"""You are generating an IEEE-style Software Requirements Specification using DeepSeek through Ollama.

PROJECT IDEA:
{session.get("idea", "")}

INTERVIEW ANSWERS:
{json.dumps(interview_answers, indent=2)}

KNOWN INFO:
{json.dumps(info, indent=2)}

DATASET EXAMPLES:
{json.dumps(examples, indent=2)}

TEMPLATE OUTLINE:
{template_excerpt(4200)}

CURRENT SEED SRS:
{json.dumps(seed, indent=2)}

TASK:
1. Use the interview answers as the main source of truth.
2. Improve the SRS wording so it reads like a complete analyst-written IEEE SRS.
3. Fill the important narrative sections, functional requirements, non-functional requirements, service summaries, and analyst summary.
4. Keep the language clear, concrete, and business-friendly.
5. Do not generate diagrams.
6. Do not mention diagrams.
7. Return only valid JSON.

RETURN JSON SHAPE:
{{
  "analyst_summary": "string",
  "introduction": {{
    "purpose": "string",
    "product_scope_summary": "string",
    "business_objectives": ["string"],
    "benefits": ["string"],
    "goals": ["string"]
  }},
  "product_perspective": {{
    "system_context": "string",
    "related_systems": [{{"name": "string", "interface_summary": "string"}}]
  }},
  "product_functions": [
    {{"name": "string", "description": "string"}}
  ],
  "user_classes": [
    {{
      "name": "string",
      "description": "string",
      "technical_expertise": "string",
      "frequency_of_use": "string"
    }}
  ],
  "user_interfaces": [
    {{"name": "string", "description": "string"}}
  ],
  "software_interfaces": [
    {{"name": "string", "description": "string"}}
  ],
  "system_features": [
    {{
      "name": "string",
      "description": "string",
      "priority": "High",
      "functional_requirements": [
        {{
          "title": "string",
          "description": "string",
          "actor": "string",
          "acceptance_criteria": ["string"],
          "priority": "High"
        }}
      ]
    }}
  ],
  "performance_requirements": ["string"],
  "security_requirements": ["string"],
  "database_requirements": ["string"],
  "legal_requirements": ["string"],
  "business_rules": ["string"],
  "additional_requirements": ["string"],
  "services": [
    {{"service_name": "string", "summary": "string"}}
  ]
}}"""
    response = call_ollama_text(
        prompt,
        system_prompt="You are a senior SRS analyst. Produce complete, precise JSON for the SRS content pack. Return JSON only.",
        temperature=0.15,
    )
    return parse_json_object(response) if response else {}


def merge_info(session: dict[str, Any]) -> dict[str, Any]:
    info = {}
    info.update(session.get("question_plan", {}).get("known", {}))
    info.update(session.get("answers", {}))
    info.setdefault("project_name", session.get("project_name") or guess_project_name(session.get("idea", "")))
    info.setdefault("domain", infer_domain(session.get("idea", "")))
    if session.get("audience") and session.get("audience") != "General users":
        info.setdefault("target_users", [session.get("audience")])
    info.setdefault("core_features", "\n".join(infer_features(session, info)))
    return info


def build_stack(session: dict[str, Any]) -> dict[str, str]:
    text = " ".join([session.get("idea", ""), *(message.get("content", "") for message in session.get("messages", []))]).lower()
    api = "Go (Gin or Fiber) REST API" if re.search(r"\bgo(lang)?\b", text) else "FastAPI REST API"
    return {
        "frontend": "Next.js 15 + Tailwind CSS",
        "api": api,
        "ai_orchestrator": "Python AI worker with LangGraph-compatible orchestration",
        "database": "PostgreSQL",
        "storage": "S3-compatible object storage",
        "deployment": "Docker Compose locally, ECS or Kubernetes in production",
    }


def build_srs(session: dict[str, Any], final: bool) -> dict[str, Any]:
    srs = load_template()
    info = merge_info(session)
    interview_workspace = build_interview_workspace(session)
    name = normalize_project_name(info.get("project_name"))
    domain = info.get("domain") or "General"
    features = infer_features(session, info)
    users = to_list(info.get("target_users"), [session.get("audience") or "General users"])
    platforms = to_list(info.get("platforms"), ["Web browser"])
    auth_method = info.get("auth_method") or "To be confirmed"
    integrations = to_list(info.get("integrations"), ["To be confirmed"])
    reports = to_list(info.get("reports_and_notifications"), ["To be confirmed"])
    compliance = [item for item in to_list(info.get("compliance"), ["To be confirmed"]) if item.lower() != "none"] or ["To be confirmed"]
    expected_scale = info.get("expected_scale") or "To be confirmed"
    stack = build_stack(session)

    srs["document_type"] = "Software Requirements Specification"
    srs["standard"] = "IEEE SRS"
    srs["metadata"] = {
        "project_name": name,
        "project_id": f"SRS-{re.sub(r'[^A-Z0-9]+', '-', name.upper()).strip('-') or 'PROJECT'}",
        "domain": domain,
        "application_type": ", ".join(platforms),
        "version": "1.0",
        "status": "approved" if final else "draft",
        "author": "Agent 1 SRS API",
        "organization": "AgentForge Studio",
        "date_created": today_iso(),
        "last_updated": today_iso(),
        "language": "en",
    }
    srs["revision_history"] = [{"revision_id": "REV-001", "name": "Agent 1 SRS API", "date": today_iso(), "reason_for_changes": "Initial generated draft", "version": "1.0" if final else "0.1"}]
    srs["sections"] = build_sections_payload(session, name, features, users, platforms, auth_method, integrations, compliance, stack)
    srs["appendices"] = build_appendices_payload(info)
    srs["services"] = build_service_catalog()

    generator = {"provider": "template-fallback", "model": None, "used_ai_generation": False}
    if model_config()["ollama"]["available"]:
        try:
            content_pack = deepseek_srs_content_pack(session, srs, info)
            if content_pack:
                srs = apply_deepseek_srs_content_pack(srs, content_pack, interview_workspace)
                generator = {"provider": "ollama", "model": DEEPSEEK_MODEL, "used_ai_generation": True}
        except Exception:
            generator = {"provider": "template-fallback", "model": DEEPSEEK_MODEL, "used_ai_generation": False}

    srs["generated_stack_recommendation"] = stack
    srs["analyst_workspace"] = {
        **interview_workspace,
        "template_standard": srs.get("standard", "IEEE SRS"),
        "template_document_type": srs.get("document_type", "Software Requirements Specification"),
        "generator": generator,
        "stack_summary": stack,
        "expected_scale": expected_scale,
        "integrations": integrations,
        "reports_and_notifications": reports,
        "compliance_focus": compliance,
    }
    srs["diagram_previews"] = []
    return srs


def get_value_at_path(root: dict[str, Any], path: str) -> Any:
    value: Any = root
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def validate_srs(srs: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    issues = []
    merged_info = merge_info(session)
    issue_paths = set()

    def add_issue(path: str, message: str, severity: str) -> None:
        key = (path, message, severity)
        if key in issue_paths:
            return
        issue_paths.add(key)
        issues.append({"path": path, "message": message, "severity": severity})

    for item in missing_interview_questions(session):
        add_issue(item["key"], "Interview answer is still required", "high")
    for path in REQUIRED_PATHS:
        value = get_value_at_path(srs, path)
        if value in (None, "", []) or (isinstance(value, str) and re.search(r"<[^>]+>", value)):
            add_issue(path, "Required content is missing", "high")
    for question in QUESTION_DEFAULTS:
        if not has_answer_value(merged_info.get(question["key"])):
            add_issue(question["key"], f"Clarify {question['key'].replace('_', ' ')}", "medium")
    score = max(0, 100 - len(issues) * 5)
    return {"status": "ready" if score >= 80 else "needs_review", "completeness_score": score, "issues": issues, "summary": "The SRS is ready for review and export." if score >= 80 else "The SRS is usable, but some details still need clarification."}
