from __future__ import annotations

import json
import random
import re
from typing import Any

from .common import (
    answer_text,
    get_dataset_examples,
    has_answer_value,
    infer_domain,
    now_iso,
    parse_json_object,
    template_excerpt,
    to_list,
)
from .config import (
    AUTH_METHOD_OPTIONS,
    COMPLIANCE_OPTIONS,
    CORE_FEATURE_OPTIONS,
    DEEPSEEK_MODEL,
    DOMAIN_KEYWORDS,
    END,
    INTEGRATION_OPTIONS,
    LANGGRAPH_AVAILABLE,
    NON_INTERVIEW_QUESTION_KEYS,
    PLATFORM_OPTIONS,
    QUESTION_COUNT_MAX,
    QUESTION_DEFAULT_MAP,
    QUESTION_DEFAULTS,
    QUESTION_INPUT_TYPES,
    QUESTION_SECTIONS,
    REPORT_OPTIONS,
    SCALE_OPTIONS,
    START,
    StateGraph,
    TARGET_USER_OPTIONS,
)
from .orchestrator import call_ollama_text


def sanitize_question_key(value: str, index: int) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(value or f"detail_{index + 1}").strip().lower()).strip("_")
    return key or f"detail_{index + 1}"


def unique_options(options: list[str], max_items: int = 12) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for option in options:
        value = re.sub(r"\s+", " ", str(option or "")).strip()
        if not value:
            continue
        signature = value.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        cleaned.append(value)
        if len(cleaned) >= max_items:
            break
    return cleaned


def infer_selection_input_type(key: str, section: str, question_text: str) -> str:
    fallback = QUESTION_DEFAULT_MAP.get(key) or {}
    if fallback.get("inputType") in QUESTION_INPUT_TYPES:
        return str(fallback["inputType"])

    signature = f"{key} {section} {question_text}".lower()
    multiselect_hints = [
        "users",
        "roles",
        "features",
        "functions",
        "actions",
        "tasks",
        "platforms",
        "devices",
        "integrations",
        "services",
        "alerts",
        "notifications",
        "reports",
        "documents",
        "rules",
        "requirements",
        "permissions",
        "languages",
        "channels",
    ]
    if any(hint in signature for hint in multiselect_hints):
        return "multiselect"
    return "select"


def infer_selection_options(key: str, section: str, question_text: str, input_type: str) -> list[str]:
    fallback = QUESTION_DEFAULT_MAP.get(key) or {}
    if fallback.get("options"):
        return unique_options(list(fallback["options"]))

    signature = f"{key} {section} {question_text}".lower()
    option_sets = [
        (["domain", "industry", "business area"], list(DOMAIN_KEYWORDS.keys()) + ["General", "Not sure yet"]),
        (["user", "audience", "role", "who will use"], TARGET_USER_OPTIONS + ["Guests or visitors", "Clients or patients", "Vendors or partners"]),
        (["feature", "function", "workflow", "action", "task"], CORE_FEATURE_OPTIONS),
        (["platform", "device", "where will people use"], PLATFORM_OPTIONS),
        (["sign-in", "sign in", "login", "log in", "authentication", "auth"], AUTH_METHOD_OPTIONS),
        (["integration", "connect", "third-party", "third party", "service"], INTEGRATION_OPTIONS),
        (["report", "alert", "notification", "reminder", "update"], REPORT_OPTIONS),
        (["privacy", "legal", "safety", "security", "compliance"], COMPLIANCE_OPTIONS),
        (["scale", "users at launch", "how many people", "expected traffic", "volume"], SCALE_OPTIONS),
        (["timeline", "launch", "go live"], ["As soon as possible", "Within 1 to 3 months", "Within 3 to 6 months", "More than 6 months away", "Not sure yet"]),
        (["language", "localization", "region", "country"], ["English only", "English plus one more language", "Multiple languages", "Multiple regions", "Not sure yet"]),
        (["payment", "billing"], ["Online card payments", "Bank transfer", "Cash handling", "Invoice billing", "No payments needed", "Not sure yet"]),
        (["approval", "review"], ["Yes, before key actions", "Yes, for some actions only", "No approvals needed", "Not sure yet"]),
        (["data migration", "import", "existing data"], ["Need to import old data", "Need export only", "Need both import and export", "No migration needed", "Not sure yet"]),
    ]
    for patterns, options in option_sets:
        if any(pattern in signature for pattern in patterns):
            return unique_options(options)

    section_fallbacks = {
        "basics": list(DOMAIN_KEYWORDS.keys()) + ["General", "Not sure yet"],
        "users": TARGET_USER_OPTIONS + ["Guests or visitors", "Clients or patients"],
        "features": CORE_FEATURE_OPTIONS,
        "interfaces": PLATFORM_OPTIONS,
        "accounts": AUTH_METHOD_OPTIONS,
        "integrations": INTEGRATION_OPTIONS,
        "operations": REPORT_OPTIONS,
        "privacy": COMPLIANCE_OPTIONS,
        "technical": SCALE_OPTIONS,
    }
    if section in section_fallbacks:
        return unique_options(section_fallbacks[section])
    if input_type == "multiselect":
        return ["Important right away", "Helpful later", "Not needed now", "Not sure yet"]
    return ["Yes", "No", "Not sure yet"]


def normalize_question(raw_question: dict[str, Any], index: int) -> dict[str, Any]:
    fallback = QUESTION_DEFAULT_MAP.get(raw_question.get("key")) or {}
    key = sanitize_question_key(raw_question.get("key") or fallback.get("key"), index)
    section = raw_question.get("section") if raw_question.get("section") in QUESTION_SECTIONS else fallback.get("section", "basics")
    question_text = str(raw_question.get("question") or fallback.get("question") or f"Please provide detail {index + 1}.").strip()
    input_type = raw_question.get("inputType") if raw_question.get("inputType") in QUESTION_INPUT_TYPES else fallback.get("inputType")
    input_type = input_type if input_type in QUESTION_INPUT_TYPES else infer_selection_input_type(key, section, question_text)
    raw_options = raw_question.get("options") if isinstance(raw_question.get("options"), list) else fallback.get("options", [])
    options = unique_options([str(option).strip() for option in raw_options if str(option).strip()])
    if not options:
        options = infer_selection_options(key, section, question_text, input_type)
    return {
        "key": key,
        "section": section,
        "question": question_text,
        "inputType": input_type,
        "placeholder": str(raw_question.get("placeholder") or fallback.get("placeholder") or "").strip(),
        "options": options,
    }


def dedupe_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    ordered = []
    for index, question in enumerate(questions):
        normalized = normalize_question(question, index)
        if normalized["key"] in seen:
            continue
        seen.add(normalized["key"])
        ordered.append(normalized)
    return ordered


def missing_default_questions(info: dict[str, Any], existing_keys: set[str] | None = None) -> list[dict[str, Any]]:
    existing_keys = existing_keys or set()
    return [
        dict(question)
        for question in QUESTION_DEFAULTS
        if question["key"] not in existing_keys and not has_answer_value(info.get(question["key"]))
    ]


def finalize_question_list(session: dict[str, Any], known: dict[str, Any], suggested_questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned_questions = [
        question
        for question in dedupe_questions(suggested_questions)
        if question["key"] not in NON_INTERVIEW_QUESTION_KEYS and not has_answer_value(known.get(question["key"]))
    ]
    default_keys = set(QUESTION_DEFAULT_MAP)
    default_questions = [question for question in cleaned_questions if question["key"] in default_keys]
    extra_questions = [question for question in cleaned_questions if question["key"] not in default_keys]
    remaining_defaults = missing_default_questions(known, {question["key"] for question in default_questions})
    random.Random(session.get("id") or session.get("project_name") or "agent1").shuffle(remaining_defaults)
    question_list = default_questions + remaining_defaults
    if len(question_list) < QUESTION_COUNT_MAX:
        question_list.extend(extra_questions[: QUESTION_COUNT_MAX - len(question_list)])
    return question_list[:QUESTION_COUNT_MAX]


def build_known_info(session: dict[str, Any]) -> dict[str, Any]:
    context = " ".join([session.get("idea", ""), *(upload.get("excerpt", "") for upload in session.get("uploads", []))])
    known = {
        "project_name": session.get("project_name") if session.get("project_name") != "Untitled App" else "",
        "domain": infer_domain(context) if infer_domain(context) != "General" else "",
        "target_users": [session.get("audience")] if session.get("audience") and session.get("audience") != "General users" else [],
    }
    known.update({key: value for key, value in (session.get("answers") or {}).items() if has_answer_value(value)})
    return {key: value for key, value in known.items() if has_answer_value(value)}


def normalize_existing_question_plan(session: dict[str, Any]) -> None:
    plan = session.get("question_plan")
    if not isinstance(plan, dict):
        return
    known = build_known_info(session)
    if isinstance(plan.get("known"), dict):
        known.update({key: value for key, value in plan["known"].items() if has_answer_value(value)})
    plan["known"] = {key: value for key, value in known.items() if has_answer_value(value)}
    plan["questions"] = finalize_question_list(session, plan["known"], plan.get("questions") or [])


def infer_features(session: dict[str, Any], info: dict[str, Any]) -> list[str]:
    features = to_list(info.get("core_features"))
    context = " ".join([session.get("idea", ""), *(upload.get("summary", "") for upload in session.get("uploads", []))]).lower()
    patterns = [
        ("Multimodal project intake", ["upload", "pdf", "voice", "image", "picture"]),
        ("AI-guided requirement interview", ["question", "answer", "interview", "clarify"]),
        ("Structured SRS generation", ["srs", "requirements", "specification"]),
        ("JSON and PDF artifact export", ["json", "pdf", "export", "download"]),
        ("Dashboard and project overview", ["dashboard", "overview", "summary"]),
        ("Notifications and status updates", ["notify", "notification", "alert", "email"]),
    ]
    for label, keywords in patterns:
        if any(keyword in context for keyword in keywords):
            features.append(label)
    if not features:
        features = [
            "Dashboard and project overview",
            "Multimodal project intake",
            "AI-guided requirement interview",
            "Structured SRS generation",
            "JSON and PDF artifact export",
        ]
    return list(dict.fromkeys(features))[:8]


def heuristic_question_plan(session: dict[str, Any], known: dict[str, Any], examples: list[dict[str, str]]) -> dict[str, Any]:
    questions = finalize_question_list(session, known, QUESTION_DEFAULTS)
    summary = (
        f"{session.get('project_name') or 'This project'} looks like a {(known.get('domain') or infer_domain(session.get('idea', ''))).lower()} product for "
        f"{', '.join(to_list(known.get('target_users'), [session.get('audience') or 'general users']))}. "
        f"The early scope points to {', '.join(infer_features(session, known)[:4]).lower()}."
    )
    if examples:
        summary += f" Similar dataset examples were found for {examples[0]['domain']}."
    return {
        "summary": summary,
        "known": known,
        "questions": questions,
        "reference_examples": examples,
        "planner": {"provider": "heuristic", "model": None, "orchestrator": "rules"},
    }


def deepseek_question_plan(session: dict[str, Any], known: dict[str, Any], examples: list[dict[str, str]]) -> dict[str, Any]:
    context = {
        "project_name": session.get("project_name"),
        "idea": session.get("idea"),
        "uploads": session.get("uploads", []),
        "messages": session.get("messages", []),
        "known": known,
    }
    prompt = f"""You are an IEEE SRS requirements interviewer using DeepSeek through Ollama.

PROJECT CONTEXT:
{json.dumps(context, indent=2)}

IEEE TEMPLATE OUTLINE:
{template_excerpt(5200)}

DEFAULT QUESTION TYPES:
{json.dumps(QUESTION_DEFAULTS, indent=2)}

SAMPLE DATASET EXAMPLES:
{json.dumps(examples, indent=2)}

TASK:
1. Read the context and identify which IEEE SRS information is still missing.
2. Create a short business-friendly summary.
3. Ask as many questions as needed to complete the IEEE SRS, usually between 6 and 10.
4. Cover missing areas such as project basics, users, core actions, platforms, sign-in, integrations, reports or alerts, privacy or legal needs, scale, security, and constraints when relevant.
5. Vary the question order naturally instead of always using the same order.
6. Questions must be simple, warm, and easy for a non-technical user to understand.
7. Avoid jargon. If you must ask about a technical area, translate it into everyday business language.
8. Every question must use one inputType from: select, multiselect.
9. Every question must include clear answer options. Do not ask for free-text answers.
10. Prefer keys from the default question list when they fit.
11. The project name already comes from intake, so do not ask naming questions.
12. Return only valid JSON.

JSON SHAPE:
{{
  "summary": "short summary",
  "known": {{
    "domain": "...",
    "target_users": ["..."],
    "core_features": ["..."]
  }},
  "questions": [
    {{
      "key": "platforms",
      "section": "interfaces",
      "question": "Where will people use it first?",
      "inputType": "multiselect",
      "placeholder": "",
      "options": ["Web browser", "Mobile app", "Desktop app", "Not sure yet"]
    }}
  ]
}}"""
    response = call_ollama_text(
        prompt,
        system_prompt="You are a senior IEEE SRS analyst. Ask the smallest useful set of missing requirements questions. Respond only with valid JSON.",
        temperature=0.2,
    )
    if not response:
        raise ValueError("DeepSeek returned an empty response")

    payload = parse_json_object(response)
    parsed_known = build_known_info(session)
    parsed_known.update(payload.get("known") or {})
    parsed_questions = finalize_question_list(session, parsed_known, payload.get("questions") or [])
    return {
        "summary": str(payload.get("summary") or "").strip(),
        "known": {key: value for key, value in parsed_known.items() if has_answer_value(value)},
        "questions": parsed_questions,
        "reference_examples": examples,
        "planner": {
            "provider": "ollama",
            "model": DEEPSEEK_MODEL,
            "orchestrator": "langgraph" if LANGGRAPH_AVAILABLE else "direct",
        },
    }


def build_question_plan(session: dict[str, Any]) -> dict[str, Any]:
    known = build_known_info(session)
    domain = known.get("domain") or infer_domain(session.get("idea", ""))
    examples = get_dataset_examples(domain) if domain and domain != "General" else []

    def run_planner() -> dict[str, Any]:
        return deepseek_question_plan(session, known, examples)

    plan: dict[str, Any]
    if LANGGRAPH_AVAILABLE:
        graph = StateGraph(dict)

        def seed_known(state: dict[str, Any]) -> dict[str, Any]:
            state["known"] = known
            state["examples"] = examples
            return state

        def generate_plan(state: dict[str, Any]) -> dict[str, Any]:
            result = run_planner()
            state.update(result)
            return state

        def finalize(state: dict[str, Any]) -> dict[str, Any]:
            heuristic = heuristic_question_plan(session, known, examples)
            state["summary"] = state.get("summary") or heuristic["summary"]
            state["questions"] = finalize_question_list(session, state.get("known") or known, state.get("questions") or heuristic["questions"])
            return state

        graph.add_node("seed_known", seed_known)
        graph.add_node("generate_plan", generate_plan)
        graph.add_node("finalize", finalize)
        graph.add_edge(START, "seed_known")
        graph.add_edge("seed_known", "generate_plan")
        graph.add_edge("generate_plan", "finalize")
        graph.add_edge("finalize", END)
        try:
            compiled = graph.compile()
            result = compiled.invoke({})
            plan = {
                "summary": result.get("summary"),
                "known": result.get("known"),
                "questions": result.get("questions"),
                "reference_examples": result.get("reference_examples", examples),
                "planner": result.get("planner") or {"provider": "ollama", "model": DEEPSEEK_MODEL, "orchestrator": "langgraph"},
            }
        except Exception:
            plan = heuristic_question_plan(session, known, examples)
    else:
        try:
            plan = run_planner()
        except Exception:
            plan = heuristic_question_plan(session, known, examples)

    heuristic = heuristic_question_plan(session, known, examples)
    if not plan.get("summary"):
        plan["summary"] = heuristic["summary"]
    if not plan.get("questions"):
        plan["questions"] = heuristic["questions"]
    plan["questions"] = finalize_question_list(session, plan.get("known") or known, plan.get("questions") or [])
    if not plan.get("planner"):
        plan["planner"] = heuristic["planner"]
    plan["created_at"] = now_iso()
    return plan


def build_interview_workspace(session: dict[str, Any]) -> dict[str, Any]:
    question_plan = session.get("question_plan") or {}
    answers = session.get("answers") or {}
    items = []
    for question in question_plan.get("questions") or []:
        value = answers.get(question["key"])
        items.append(
            {
                "key": question["key"],
                "section": question.get("section", "basics"),
                "question": question["question"],
                "input_type": question.get("inputType", "select"),
                "answered": has_answer_value(value),
                "answer": value,
                "answer_text": answer_text(value),
            }
        )

    answered_count = sum(1 for item in items if item["answered"])
    total_count = len(items)
    missing = [item for item in items if not item["answered"]]
    return {
        "analysis_summary": session.get("analysis_summary") or question_plan.get("summary", ""),
        "planner": question_plan.get("planner") or {},
        "coverage": {
            "total_questions": total_count,
            "answered_questions": answered_count,
            "open_questions": len(missing),
            "completion_percent": int((answered_count / total_count) * 100) if total_count else 100,
        },
        "interview_questions": items,
        "open_items": missing,
    }


def missing_interview_questions(session: dict[str, Any]) -> list[dict[str, Any]]:
    return build_interview_workspace(session)["open_items"]
