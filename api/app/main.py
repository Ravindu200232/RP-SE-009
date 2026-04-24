from .api_entry import app

r'''

from __future__ import annotations

import csv
import json
import os
import random
import re
import urllib.error
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
except Exception:
    StrOutputParser = None
    ChatPromptTemplate = None

try:
    from langchain_ollama import ChatOllama
except Exception:
    ChatOllama = None

try:
    from langgraph.graph import END, START, StateGraph
except Exception:
    END = START = StateGraph = None


APP_DIR = Path(__file__).resolve().parent
API_DIR = APP_DIR.parent
PROJECT_ROOT = API_DIR.parent
DATA_ROOT = API_DIR / "data" / "sessions"
VOICE_NOTE_MARKER = "Voice note:"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v3.1:671b-cloud")
LANGCHAIN_AVAILABLE = bool(StrOutputParser and ChatPromptTemplate)
LANGCHAIN_OLLAMA_AVAILABLE = bool(ChatOllama)
LANGGRAPH_AVAILABLE = bool(StateGraph and START is not None and END is not None)

TEMPLATE_CANDIDATES = [
    Path(os.getenv("SRS_TEMPLATE_PATH", "")).expanduser(),
    PROJECT_ROOT / "ieee_srs_training_template.json",
    Path(r"C:\Users\ravin\Downloads\ieee_srs_training_template.json"),
]
DATASET_CANDIDATES = [
    Path(os.getenv("SRS_DATASET_PATH", "")).expanduser(),
    PROJECT_ROOT / "srs_training_dataset_4000.csv",
    API_DIR / "srs_training_dataset_4000.csv",
    Path(r"C:\Users\ravin\Downloads\srs_training_dataset_4000.csv"),
    Path(r"C:\Users\ravin\Downloads\srs\srs_training_dataset_4000.csv"),
]

DOMAIN_KEYWORDS = {
    "Healthcare": ["health", "patient", "doctor", "medical", "hospital", "clinic"],
    "Education": ["learn", "course", "student", "teacher", "school", "lms"],
    "E-Commerce": ["shop", "product", "cart", "order", "payment", "checkout", "store"],
    "Finance": ["bank", "finance", "invoice", "wallet", "loan", "insurance"],
    "Travel": ["travel", "hotel", "flight", "booking", "reservation"],
    "Task Management": ["task", "todo", "project", "kanban", "workflow", "deadline"],
}

TARGET_USER_OPTIONS = [
    "Customers",
    "Business owners or admins",
    "Staff members",
    "Managers",
    "Students",
    "Teachers or trainers",
    "General public",
    "Internal company team",
]
CORE_FEATURE_OPTIONS = [
    "Dashboard and overview",
    "Create and manage records",
    "Search and filters",
    "File upload",
    "Notifications and reminders",
    "Reports and exports",
    "Approvals and workflows",
    "User accounts and roles",
    "Chat or comments",
    "Payments or billing",
    "Not sure yet",
]
PLATFORM_OPTIONS = ["Web browser", "Mobile app", "Desktop app", "Tablet app", "Internal office system", "Not sure yet"]
AUTH_METHOD_OPTIONS = ["Email and password", "Google or social sign-in", "Company login", "No sign-in needed", "Not sure yet"]
INTEGRATION_OPTIONS = [
    "Email service",
    "SMS or WhatsApp",
    "Calendar",
    "Payment gateway",
    "Cloud storage",
    "ERP or internal system",
    "CRM",
    "Maps or location service",
    "No integrations yet",
    "Not sure yet",
]
REPORT_OPTIONS = [
    "In-app notifications",
    "Email updates",
    "SMS or WhatsApp alerts",
    "Daily reminders",
    "Weekly summary reports",
    "Admin alerts",
    "PDF export",
    "Excel or CSV export",
    "No reports or alerts yet",
    "Not sure yet",
]
COMPLIANCE_OPTIONS = [
    "No special rules",
    "Personal or private data",
    "Health or medical data",
    "Payment or billing data",
    "School or student data",
    "Role-based access needed",
    "Audit trail needed",
    "Not sure yet",
]
SCALE_OPTIONS = ["Under 100", "100 to 1,000", "1,000 to 10,000", "More than 10,000", "Not sure yet"]

QUESTION_DEFAULTS = [
    {"key": "domain", "section": "basics", "question": "Which area is this product closest to?", "inputType": "select", "placeholder": "", "options": list(DOMAIN_KEYWORDS.keys()) + ["General"]},
    {"key": "target_users", "section": "users", "question": "Who will use this product most often?", "inputType": "multiselect", "placeholder": "", "options": TARGET_USER_OPTIONS},
    {"key": "core_features", "section": "features", "question": "What should people be able to do in the first version?", "inputType": "multiselect", "placeholder": "", "options": CORE_FEATURE_OPTIONS},
    {"key": "platforms", "section": "interfaces", "question": "Where will people use it first?", "inputType": "multiselect", "placeholder": "", "options": PLATFORM_OPTIONS},
    {"key": "auth_method", "section": "accounts", "question": "How should people get into the system?", "inputType": "select", "placeholder": "", "options": AUTH_METHOD_OPTIONS},
    {"key": "integrations", "section": "integrations", "question": "Does it need to connect with any other tools or services?", "inputType": "multiselect", "placeholder": "", "options": INTEGRATION_OPTIONS},
    {"key": "reports_and_notifications", "section": "operations", "question": "What updates, reminders, reports, or alerts should it send?", "inputType": "multiselect", "placeholder": "", "options": REPORT_OPTIONS},
    {"key": "compliance", "section": "privacy", "question": "Are there any privacy, legal, or safety rules this product must follow?", "inputType": "multiselect", "placeholder": "", "options": COMPLIANCE_OPTIONS},
    {"key": "expected_scale", "section": "technical", "question": "About how many people may use it when you launch?", "inputType": "select", "placeholder": "", "options": SCALE_OPTIONS},
]

QUESTION_DEFAULT_MAP = {question["key"]: question for question in QUESTION_DEFAULTS}
QUESTION_INPUT_TYPES = {"select", "multiselect"}
QUESTION_SECTIONS = {"basics", "users", "features", "accounts", "privacy", "integrations", "operations", "technical", "interfaces"}
QUESTION_COUNT_MAX = 10
NON_INTERVIEW_QUESTION_KEYS = {"project_name"}

REQUIRED_PATHS = [
    "metadata.project_name",
    "metadata.project_id",
    "sections.introduction.purpose",
    "sections.overall_description.product_functions",
    "sections.system_features",
    "sections.other_nonfunctional_requirements.performance_requirements",
    "sections.other_requirements.database_requirements",
    "services",
]


class SessionCreate(BaseModel):
    idea: str = ""
    project_name: str = "Untitled App"
    audience: str = "General users"


class AnswersRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class MessageRequest(BaseModel):
    message: str


app = FastAPI(title="Agent 1 SRS API", version="0.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SESSIONS: dict[str, dict[str, Any]] = {}
TEMPLATE_CACHE: dict[str, Any] | None = None
DATASET_CACHE: list[dict[str, str]] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def truncate(text: str, limit: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def has_answer_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(str(item or "").strip() for item in value)
    if isinstance(value, dict):
        return any(has_answer_value(item) for item in value.values())
    return bool(str(value or "").strip())


def normalize_project_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:80] if text else "Untitled App"


def guess_project_name(text: str) -> str:
    sentence = re.split(r"[.!?\n]", normalize_project_name(text), maxsplit=1)[0].strip()
    return sentence or "Untitled App"


def resolve_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if str(path).strip() and path.exists():
            return path
    return None


def load_template() -> dict[str, Any]:
    global TEMPLATE_CACHE
    if TEMPLATE_CACHE is not None:
        return deepcopy(TEMPLATE_CACHE)
    path = resolve_existing(TEMPLATE_CANDIDATES)
    if path:
        try:
            TEMPLATE_CACHE = json.loads(path.read_text(encoding="utf-8"))
            return deepcopy(TEMPLATE_CACHE)
        except Exception:
            pass
    TEMPLATE_CACHE = {"document_type": "Software Requirements Specification", "standard": "IEEE SRS", "metadata": {}, "sections": {}, "appendices": {}, "services": []}
    return deepcopy(TEMPLATE_CACHE)


def load_dataset() -> list[dict[str, str]]:
    global DATASET_CACHE
    if DATASET_CACHE is not None:
        return DATASET_CACHE
    path = resolve_existing(DATASET_CANDIDATES)
    if not path:
        DATASET_CACHE = []
        return DATASET_CACHE
    rows: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                rows.append({key: str(value or "") for key, value in row.items()})
                if index >= 999:
                    break
    except Exception:
        rows = []
    DATASET_CACHE = rows
    return DATASET_CACHE


def infer_domain(text: str) -> str:
    text = str(text or "").lower()
    best_domain, best_score = "General", 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_domain, best_score = domain, score
    return best_domain


def get_dataset_examples(domain: str) -> list[dict[str, str]]:
    rows = load_dataset()
    matches = [row for row in rows if (row.get("domain") or "").lower() == domain.lower()]
    pool = matches or rows
    return [{"domain": row.get("domain", domain), "summary": truncate(row.get("summary") or row.get("training_text") or "", 220)} for row in pool[:2]]


def ollama_probe() -> dict[str, Any]:
    request = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "available": True,
            "url": OLLAMA_URL,
            "models": [item.get("name") for item in payload.get("models", []) if item.get("name")],
        }
    except Exception:
        return {"available": False, "url": OLLAMA_URL, "models": []}


def model_config() -> dict[str, Any]:
    return {
        "provider": "ollama",
        "ollama_url": OLLAMA_URL,
        "deepseek_model": DEEPSEEK_MODEL,
        "langchain_enabled": LANGCHAIN_AVAILABLE,
        "langchain_ollama_enabled": LANGCHAIN_OLLAMA_AVAILABLE,
        "langgraph_enabled": LANGGRAPH_AVAILABLE,
        "ollama": ollama_probe(),
    }


def strip_json_fence(text: str) -> str:
    return re.sub(r"^```(?:json)?|```$", "", str(text or "").strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def call_ollama_text(prompt: str, *, system_prompt: str, temperature: float = 0.1) -> str:
    if LANGCHAIN_AVAILABLE and LANGCHAIN_OLLAMA_AVAILABLE:
        try:
            llm = ChatOllama(model=DEEPSEEK_MODEL, base_url=OLLAMA_URL, temperature=temperature)
            chain = (
                ChatPromptTemplate.from_messages(
                    [
                        ("system", system_prompt),
                        ("human", "{prompt}"),
                    ]
                )
                | llm
                | StrOutputParser()
            )
            return str(chain.invoke({"prompt": prompt})).strip()
        except Exception:
            pass

    payload = json.dumps(
        {
            "model": DEEPSEEK_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": temperature},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            content = json.loads(response.read().decode("utf-8"))
        return str(content.get("message", {}).get("content", "")).strip()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return ""


def planner_name() -> str:
    if model_config()["ollama"]["available"]:
        return f"DeepSeek via Ollama ({DEEPSEEK_MODEL})"
    return "Heuristic IEEE planner"


def build_agent_message(session: dict[str, Any], mode: str) -> str:
    question_plan = session.get("question_plan") or {}
    question_count = len(question_plan.get("questions", []))
    fallback_messages = {
        "intake": (
            f"I mapped your idea against the IEEE SRS structure and prepared {question_count} short, user-friendly questions "
            "to fill the missing details."
        ),
        "update": "I refreshed the draft with your latest note and kept the remaining SRS questions simple and user-friendly.",
    }
    prompt = f"""Write a short assistant reply for an SRS intake workflow.

MODE: {mode}
PROJECT NAME: {session.get("project_name")}
ANALYSIS SUMMARY: {question_plan.get("summary") or session.get("analysis_summary") or ""}
QUESTION COUNT: {question_count}
LATEST USER MESSAGE: {truncate((session.get("messages") or [{}])[-1].get("content", ""), 400)}

RULES:
- Keep it to 1 or 2 sentences.
- Sound like an SRS analyst guiding the user.
- Mention IEEE-style requirement gathering naturally.
- Tell the user that no technical knowledge is needed.
- Do not use markdown.
- Do not mention internal tools unless you naturally say DeepSeek or Ollama once.
"""
    response = call_ollama_text(
        prompt,
        system_prompt="You are a concise product analyst helping a user complete an IEEE SRS interview.",
        temperature=0.25,
    )
    return response or fallback_messages.get(mode, fallback_messages["update"])


def safe_decode(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return payload.decode(encoding)
        except Exception:
            continue
    return ""


def answer_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def extract_pdf_text(payload: bytes) -> str:
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(BytesIO(payload))
        return truncate("\n".join((page.extract_text() or "") for page in reader.pages[:6]), 1800)
    except Exception:
        return ""


def summarize_upload(file: UploadFile, payload: bytes) -> dict[str, Any]:
    name = file.filename or "unknown"
    suffix = Path(name).suffix.lower()
    kind = "file"
    excerpt = ""
    summary = f"Registered file '{name}'."
    if (file.content_type or "").startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        try:
            with Image.open(BytesIO(payload)) as image:
                kind = "image"
                summary = f"Uploaded image '{name}' ({image.width}x{image.height})."
                excerpt = f"Image dimensions: {image.width}x{image.height}"
        except Exception:
            pass
    elif suffix == ".pdf" or file.content_type == "application/pdf":
        kind = "pdf"
        excerpt = extract_pdf_text(payload)
        summary = f"Uploaded PDF '{name}' for requirements context."
    elif (file.content_type or "").startswith("audio/") or suffix in {".mp3", ".wav", ".m4a", ".ogg", ".webm"}:
        kind = "audio"
        summary = f"Uploaded voice note '{name}'."
    elif suffix in {".txt", ".md", ".json", ".csv"} or (file.content_type or "").startswith("text/"):
        kind = "text"
        excerpt = truncate(safe_decode(payload), 1800)
        summary = f"Uploaded text document '{name}'."
    return {"asset_id": str(uuid4()), "filename": name, "kind": kind, "summary": summary, "excerpt": excerpt}


def to_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or list(fallback or [])
    text = str(value or "").strip()
    if not text:
        return list(fallback or [])
    return [part.strip(" -*\t") for part in re.split(r"\r?\n+|[,;]+", text) if part.strip(" -*\t")]


def build_template_outline(node: Any, path: str = "root", depth: int = 0, max_depth: int = 3) -> list[str]:
    if depth > max_depth:
        return []
    if isinstance(node, dict):
        lines = [path]
        for key, value in node.items():
            lines.extend(build_template_outline(value, f"{path}.{key}", depth + 1, max_depth))
        return lines
    if isinstance(node, list):
        if not node:
            return [f"{path}[]"]
        return [f"{path}[]", *build_template_outline(node[0], f"{path}[0]", depth + 1, max_depth)]
    return [f"{path}: {str(node)}"]


def template_excerpt(limit: int = 5000) -> str:
    outline = "\n".join(build_template_outline(load_template(), "template", 0, 4))
    return outline if len(outline) <= limit else outline[: limit - 3] + "..."


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


def normalize_existing_question_plan(session: dict[str, Any]) -> None:
    plan = session.get("question_plan")
    if not isinstance(plan, dict):
        return
    known = build_known_info(session)
    if isinstance(plan.get("known"), dict):
        known.update({key: value for key, value in plan["known"].items() if has_answer_value(value)})
    plan["known"] = {key: value for key, value in known.items() if has_answer_value(value)}
    plan["questions"] = finalize_question_list(session, plan["known"], plan.get("questions") or [])


def build_known_info(session: dict[str, Any]) -> dict[str, Any]:
    context = " ".join([session.get("idea", ""), *(upload.get("excerpt", "") for upload in session.get("uploads", []))])
    known = {
        "project_name": session.get("project_name") if session.get("project_name") != "Untitled App" else "",
        "domain": infer_domain(context) if infer_domain(context) != "General" else "",
        "target_users": [session.get("audience")] if session.get("audience") and session.get("audience") != "General users" else [],
    }
    known.update({key: value for key, value in (session.get("answers") or {}).items() if has_answer_value(value)})
    return {key: value for key, value in known.items() if has_answer_value(value)}


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
        features = ["Dashboard and project overview", "Multimodal project intake", "AI-guided requirement interview", "Structured SRS generation", "JSON and PDF artifact export"]
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

    cleaned = strip_json_fence(response)
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    payload = json.loads(cleaned[start:end])
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
            state["summary"] = state.get("summary") or heuristic_question_plan(session, known, examples)["summary"]
            state["questions"] = finalize_question_list(session, state.get("known") or known, state.get("questions") or heuristic_question_plan(session, known, examples)["questions"])
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

    if not plan.get("summary"):
        plan["summary"] = heuristic_question_plan(session, known, examples)["summary"]
    if not plan.get("questions"):
        plan["questions"] = heuristic_question_plan(session, known, examples)["questions"]
    plan["questions"] = finalize_question_list(session, plan.get("known") or known, plan.get("questions") or [])
    if not plan.get("planner"):
        plan["planner"] = heuristic_question_plan(session, known, examples)["planner"]
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


def normalize_priority(value: Any, default: str = "Medium") -> str:
    text = str(value or "").strip().lower()
    if text.startswith("h"):
        return "High"
    if text.startswith("l"):
        return "Low"
    if text.startswith("m"):
        return "Medium"
    return default


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = strip_json_fence(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start < 0 or end <= start:
        return {}
    payload = json.loads(cleaned[start:end])
    return payload if isinstance(payload, dict) else {}


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


def apply_deepseek_srs_content_pack(srs: dict[str, Any], content_pack: dict[str, Any], interview_workspace: dict[str, Any]) -> dict[str, Any]:
    if not content_pack:
        return srs

    sections = srs.setdefault("sections", {})
    introduction = sections.setdefault("introduction", {})
    scope = introduction.setdefault("product_scope", {})
    overall = sections.setdefault("overall_description", {})
    perspective = overall.setdefault("product_perspective", {})
    interfaces = sections.setdefault("external_interface_requirements", {})
    nfr = sections.setdefault("other_nonfunctional_requirements", {})
    other = sections.setdefault("other_requirements", {})

    intro_pack = content_pack.get("introduction") or {}
    if intro_pack.get("purpose"):
        introduction["purpose"] = str(intro_pack["purpose"]).strip()
    if intro_pack.get("product_scope_summary"):
        scope["summary"] = str(intro_pack["product_scope_summary"]).strip()
    if isinstance(intro_pack.get("business_objectives"), list) and intro_pack["business_objectives"]:
        scope["business_objectives"] = [str(item).strip() for item in intro_pack["business_objectives"] if str(item).strip()]
    if isinstance(intro_pack.get("benefits"), list) and intro_pack["benefits"]:
        scope["benefits"] = [str(item).strip() for item in intro_pack["benefits"] if str(item).strip()]
    if isinstance(intro_pack.get("goals"), list) and intro_pack["goals"]:
        scope["goals"] = [str(item).strip() for item in intro_pack["goals"] if str(item).strip()]

    perspective_pack = content_pack.get("product_perspective") or {}
    if perspective_pack.get("system_context"):
        perspective["system_context"] = str(perspective_pack["system_context"]).strip()
    if isinstance(perspective_pack.get("related_systems"), list) and perspective_pack["related_systems"]:
        perspective["related_systems"] = [
            {
                "name": str(item.get("name") or f"System {index + 1}").strip(),
                "relationship": "Integration",
                "interface_summary": str(item.get("interface_summary") or "").strip(),
            }
            for index, item in enumerate(perspective_pack["related_systems"])
            if isinstance(item, dict) and (item.get("name") or item.get("interface_summary"))
        ]

    if isinstance(content_pack.get("product_functions"), list) and content_pack["product_functions"]:
        overall["product_functions"] = [
            {
                "function_id": f"PF-{index + 1:03d}",
                "name": str(item.get("name") or f"Function {index + 1}").strip(),
                "description": str(item.get("description") or "").strip(),
            }
            for index, item in enumerate(content_pack["product_functions"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("user_classes"), list) and content_pack["user_classes"]:
        overall["user_classes_and_characteristics"] = [
            {
                "user_class_id": f"UC-{index + 1:03d}",
                "user_class_name": str(item.get("name") or f"User Class {index + 1}").strip(),
                "description": str(item.get("description") or "").strip(),
                "technical_expertise": str(item.get("technical_expertise") or "Low to Medium").strip(),
                "security_or_privilege_level": "Role-based",
                "education_or_experience": "Basic digital literacy",
                "frequency_of_use": str(item.get("frequency_of_use") or "Weekly").strip(),
                "importance_rank": index + 1,
                "notes": "",
            }
            for index, item in enumerate(content_pack["user_classes"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("user_interfaces"), list) and content_pack["user_interfaces"]:
        interfaces["user_interfaces"] = [
            {
                "ui_id": f"UI-{index + 1:03d}",
                "name": str(item.get("name") or f"Interface {index + 1}").strip(),
                "description": str(item.get("description") or "").strip(),
                "input_elements": ["AI-guided input"],
                "output_elements": ["Structured response"],
                "layout_constraints": ["Responsive layout"],
                "accessibility_requirements": ["Keyboard support"],
                "error_message_standards": ["Human-readable validation"],
                "design_reference": "Agent 1 UI",
            }
            for index, item in enumerate(content_pack["user_interfaces"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("software_interfaces"), list) and content_pack["software_interfaces"]:
        interfaces["software_interfaces"] = [
            {
                "software_interface_id": f"SI-{index + 1:03d}",
                "component_name": str(item.get("name") or f"Integration {index + 1}").strip(),
                "component_version": "Current stable",
                "description": str(item.get("description") or "").strip(),
                "incoming_data_items": ["Request payload"],
                "outgoing_data_items": ["Response payload"],
                "services_needed": ["Authentication"],
                "communication_method": "REST or webhook",
                "shared_data": ["Project metadata"],
                "implementation_constraints": ["Use secure transport"],
            }
            for index, item in enumerate(content_pack["software_interfaces"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("system_features"), list) and content_pack["system_features"]:
        system_features = []
        for feature_index, item in enumerate(content_pack["system_features"]):
            if not isinstance(item, dict):
                continue
            requirement_items = []
            for req_index, requirement in enumerate(item.get("functional_requirements") or []):
                if not isinstance(requirement, dict):
                    continue
                requirement_items.append(
                    {
                        "requirement_id": f"REQ-{feature_index + 1:02d}{req_index + 1}",
                        "title": str(requirement.get("title") or f"Requirement {req_index + 1}").strip(),
                        "description": str(requirement.get("description") or "").strip(),
                        "actor": str(requirement.get("actor") or "Primary User").strip(),
                        "trigger": "User initiates the workflow",
                        "inputs": [{"name": "payload", "type": "json", "required": True, "validation_rules": ["Validate required fields"]}],
                        "processing_logic": ["Validate input", "Persist state", "Return clear status"],
                        "outputs": [{"name": "result", "type": "json", "description": "Structured action result"}],
                        "business_rules_applied": ["BR-001"],
                        "error_conditions": [{"condition": "Invalid input", "system_behavior": "Show a validation message"}],
                        "acceptance_criteria": [
                            str(criteria).strip()
                            for criteria in (requirement.get("acceptance_criteria") or [])
                            if str(criteria).strip()
                        ] or ["The workflow completes successfully."],
                        "priority": normalize_priority(requirement.get("priority")),
                        "status": srs.get("metadata", {}).get("status", "draft"),
                        "traceability": {
                            "linked_user_class_ids": ["UC-001"],
                            "linked_interface_ids": ["UI-001"],
                            "linked_test_case_ids": [f"TC-{feature_index + 1:03d}-{req_index + 1:02d}"],
                        },
                    }
                )

            system_features.append(
                {
                    "feature_id": f"FEAT-{feature_index + 1:03d}",
                    "feature_name": str(item.get("name") or f"Feature {feature_index + 1}").strip(),
                    "description_and_priority": {
                        "description": str(item.get("description") or "").strip(),
                        "priority": normalize_priority(item.get("priority")),
                        "benefit_score": max(6, 10 - feature_index),
                        "penalty_score": 7 if feature_index < 3 else 5,
                        "cost_score": 5,
                        "risk_score": 4,
                    },
                    "stimulus_response_sequences": [
                        {
                            "sequence_id": f"SRSQ-{feature_index + 1:03d}",
                            "stimulus": f"User starts {str(item.get('name') or f'feature {feature_index + 1}').strip().lower()}",
                            "preconditions": ["An active session exists."],
                            "system_response": "The system processes the request and shows a clear status update.",
                            "postconditions": ["The updated result is available for review."],
                        }
                    ],
                    "functional_requirements": requirement_items,
                }
            )

        if system_features:
            sections["system_features"] = system_features

    if isinstance(content_pack.get("performance_requirements"), list) and content_pack["performance_requirements"]:
        nfr["performance_requirements"] = [
            {
                "requirement_id": f"NFR-PERF-{index + 1:03d}",
                "description": str(item).strip(),
                "rationale": "Supports a responsive product experience.",
                "measurement_method": "Monitoring and tracing",
                "target_metric": "Service performance",
                "target_value": "Defined during implementation",
                "conditions": "Normal operating conditions",
            }
            for index, item in enumerate(content_pack["performance_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("security_requirements"), list) and content_pack["security_requirements"]:
        nfr["security_requirements"] = [
            {
                "requirement_id": f"NFR-SEC-{index + 1:03d}",
                "description": str(item).strip(),
                "authentication_requirements": ["Role-based authentication"],
                "authorization_requirements": ["Role-based access"],
                "data_protection_requirements": ["TLS in transit", "Encrypted storage"],
                "privacy_requirements": ["Business and user data protection"],
                "compliance_reference": "Project-dependent",
                "verification_method": "Security review and tests",
            }
            for index, item in enumerate(content_pack["security_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("business_rules"), list) and content_pack["business_rules"]:
        nfr["business_rules"] = [
            {
                "rule_id": f"BR-{index + 1:03d}",
                "description": str(item).strip(),
                "applicable_roles": ["Administrator", "Primary User"],
                "conditions": ["Project workflow is active"],
                "enforcement_requirements": ["REQ-011"],
            }
            for index, item in enumerate(content_pack["business_rules"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("database_requirements"), list) and content_pack["database_requirements"]:
        other["database_requirements"] = [
            {
                "requirement_id": f"DB-{index + 1:03d}",
                "description": str(item).strip(),
                "entities": ["Session", "AnswerSet", "SRSArtifact"],
                "retention_policy": "Policy-based retention",
                "backup_policy": "Scheduled backups",
            }
            for index, item in enumerate(content_pack["database_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("legal_requirements"), list) and content_pack["legal_requirements"]:
        other["legal_requirements"] = [
            {
                "requirement_id": f"LEGAL-{index + 1:03d}",
                "description": str(item).strip(),
                "jurisdiction": "Project-dependent",
                "reference": "Business and regulatory policy",
            }
            for index, item in enumerate(content_pack["legal_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("additional_requirements"), list) and content_pack["additional_requirements"]:
        other["additional_requirements"] = [
            {
                "requirement_id": f"OTH-{index + 1:03d}",
                "description": str(item).strip(),
            }
            for index, item in enumerate(content_pack["additional_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("services"), list) and content_pack["services"]:
        existing_service_map = {service.get("service_name"): service for service in srs.get("services", [])}
        merged_services = []
        for item in content_pack["services"]:
            if not isinstance(item, dict):
                continue
            service_name = str(item.get("service_name") or "").strip()
            if not service_name:
                continue
            existing = existing_service_map.get(service_name, {})
            merged_services.append(
                {
                    "service_name": service_name,
                    "port": existing.get("port", 8200 + len(merged_services)),
                    "summary": str(item.get("summary") or existing.get("summary") or "").strip(),
                    "endpoints": existing.get("endpoints", []),
                }
            )
        if merged_services:
            srs["services"] = merged_services

    if content_pack.get("analyst_summary"):
        interview_workspace["analysis_summary"] = str(content_pack["analyst_summary"]).strip()

    return srs


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
    srs["sections"] = {
        "introduction": {
            "purpose": f"This document defines the functional and non-functional requirements for {name}.",
            "product_scope": {
                "summary": session.get("analysis_summary") or build_question_plan(session)["summary"],
                "business_objectives": ["Clarify scope early", "Create a delivery-ready requirements baseline"],
                "benefits": ["Reduces ambiguity", "Improves downstream handoff", "Transforms guided interview answers into a structured IEEE SRS"],
                "goals": [f"Deliver the first usable release of {name}.", "Support JSON and PDF artifact export"],
            },
        },
        "overall_description": {
            "product_perspective": {
                "system_context": f"{name} is delivered through {', '.join(platforms).lower()} with an API layer, AI orchestration, persistent storage, and downloadable artifacts.",
                "product_origin": "New system",
                "related_systems": [{"name": item, "relationship": "Integration", "interface_summary": f"Used for {item.lower()}."} for item in integrations[:3]],
                "context_diagram_reference": "Diagram generation is deferred. Review the analyst workspace and service breakdown for the current phase.",
            },
            "product_functions": [{"function_id": f"PF-{index + 1:03d}", "name": feature, "description": f"{name} supports {feature.lower()} as part of the core workflow."} for index, feature in enumerate(features[:5])],
            "user_classes_and_characteristics": [{"user_class_id": f"UC-{index + 1:03d}", "user_class_name": user, "description": f"{user} uses the platform to complete the main workflow.", "technical_expertise": "Low to Medium", "security_or_privilege_level": "Role-based", "education_or_experience": "Basic digital literacy", "frequency_of_use": "Daily" if index == 0 else "Weekly", "importance_rank": index + 1, "notes": ""} for index, user in enumerate(users[:4])],
        },
        "external_interface_requirements": {
            "user_interfaces": [
                {"ui_id": "UI-001", "name": "New Project page", "description": "Collects text, files, and optional voice input.", "input_elements": ["Text area", "Upload control", "Voice recorder"], "output_elements": ["Analysis summary", "Upload list"], "layout_constraints": ["Responsive layout"], "accessibility_requirements": ["Keyboard support"], "error_message_standards": ["Human-readable validation"], "design_reference": "New Project"},
                {"ui_id": "UI-002", "name": "Question and answer workspace", "description": "Captures guided interview answers before generation.", "input_elements": ["Chat questions", "Answer composer"], "output_elements": ["Progress state", "Draft readiness"], "layout_constraints": ["Responsive layout"], "accessibility_requirements": ["Touch-friendly controls"], "error_message_standards": ["Inline validation"], "design_reference": "Agent 1 interview"},
                {"ui_id": "UI-003", "name": "Agent 1 review dashboard", "description": "Shows SRS, requirements, JSON, risks, and export actions.", "input_elements": ["Tabs", "Export buttons"], "output_elements": ["SRS document", "JSON", "Validation state"], "layout_constraints": ["Two-column desktop layout"], "accessibility_requirements": ["Semantic tabs"], "error_message_standards": ["Explicit artifact status"], "design_reference": "Agent 1 dashboard"},
            ],
            "software_interfaces": [{"software_interface_id": f"SI-{index + 1:03d}", "component_name": item, "component_version": "Current stable", "description": f"Integration with {item.lower()}.", "incoming_data_items": ["Request payload"], "outgoing_data_items": ["Response payload"], "services_needed": ["Authentication"], "communication_method": "REST or webhook", "shared_data": ["Project metadata"], "implementation_constraints": ["Use secure transport"]} for index, item in enumerate(integrations[:4])],
            "hardware_interfaces": [{"hardware_interface_id": "HI-001", "device_name": "Microphone", "description": "Used for optional voice notes.", "supported_device_types": ["Built-in microphone", "USB microphone"], "data_interaction": "Captures audio", "protocol": "Browser media devices API"}] if any(upload["kind"] == "audio" for upload in session.get("uploads", [])) else [],
            "communications_interfaces": [
                {"communication_interface_id": "CI-001", "name": "Browser to API", "description": "Interactive application traffic.", "protocols": ["HTTPS"], "message_format": "JSON and multipart form data", "security_or_encryption": "TLS 1.2+", "data_transfer_rate": "Interactive", "synchronization_mechanism": "Request-response"},
                {"communication_interface_id": "CI-002", "name": "Artifact delivery", "description": "Downloads JSON and PDF artifacts.", "protocols": ["HTTPS"], "message_format": "JSON and PDF", "security_or_encryption": "TLS 1.2+", "data_transfer_rate": "On demand", "synchronization_mechanism": "Direct download"},
            ],
        },
        "system_features": [
            {
                "feature_id": f"FEAT-{index + 1:03d}",
                "feature_name": feature,
                "description_and_priority": {"description": f"The platform provides {feature.lower()} as part of the main workflow.", "priority": "High" if index < 3 else "Medium", "benefit_score": max(6, 10 - index), "penalty_score": 7 if index < 3 else 5, "cost_score": 5, "risk_score": 4},
                "stimulus_response_sequences": [{"sequence_id": f"SRSQ-{index + 1:03d}", "stimulus": f"User initiates {feature.lower()}", "preconditions": ["An active session exists."], "system_response": f"The system processes {feature.lower()} and returns a visible status update.", "postconditions": [f"{feature} data is available for review."]}],
                "functional_requirements": [
                    {"requirement_id": f"REQ-{index + 1:02d}1", "title": f"{feature} submission", "description": f"The system shall support {feature.lower()} through the primary interface.", "actor": "Primary User", "trigger": "User submits an action", "inputs": [{"name": "payload", "type": "json", "required": True, "validation_rules": ["Validate required fields"]}], "processing_logic": ["Validate input", "Persist state", "Return a clear status"], "outputs": [{"name": "result", "type": "json", "description": "Structured action result"}], "business_rules_applied": ["BR-001"], "error_conditions": [{"condition": "Invalid input", "system_behavior": "Show a validation message"}], "acceptance_criteria": ["Valid actions succeed", "Errors are understandable to non-technical users"], "priority": "High", "status": "draft", "traceability": {"linked_user_class_ids": ["UC-001"], "linked_interface_ids": ["UI-002"], "linked_test_case_ids": [f"TC-{index + 1:03d}-01"]}},
                    {"requirement_id": f"REQ-{index + 1:02d}2", "title": f"{feature} review", "description": f"The system shall display {feature.lower()} history and status to authorized users.", "actor": "Administrator", "trigger": "User opens a review screen", "inputs": [{"name": "filters", "type": "json", "required": False, "validation_rules": ["Ignore empty filters"]}], "processing_logic": ["Load records", "Sort results", "Render the view"], "outputs": [{"name": "history", "type": "json", "description": "Matching records and status"}], "business_rules_applied": ["BR-001"], "error_conditions": [{"condition": "Data unavailable", "system_behavior": "Show a retryable error state"}], "acceptance_criteria": ["Authorized users can review status"], "priority": "Medium", "status": "draft", "traceability": {"linked_user_class_ids": ["UC-001"], "linked_interface_ids": ["UI-003"], "linked_test_case_ids": [f"TC-{index + 1:03d}-02"]}},
                ],
            }
            for index, feature in enumerate(features)
        ],
        "other_nonfunctional_requirements": {
            "performance_requirements": [{"requirement_id": "NFR-PERF-001", "description": "The system shall return primary page loads and standard API actions within 2 seconds under normal load.", "rationale": "Keeps the guided workflow responsive.", "measurement_method": "Monitoring and tracing", "target_metric": "95th percentile response time", "target_value": "<= 2 seconds", "conditions": "Normal business-hour traffic"}],
            "safety_requirements": [{"requirement_id": "NFR-SAFE-001", "description": "The system shall prevent accidental loss of active project work.", "hazard": "Loss of project inputs or artifacts", "safeguards": ["Persist session state", "Confirm destructive actions"], "prevented_actions": ["Silent discard of work"], "compliance_reference": "Internal product policy"}],
            "security_requirements": [{"requirement_id": "NFR-SEC-001", "description": "The system shall protect uploaded materials, generated artifacts, and session metadata.", "authentication_requirements": [auth_method], "authorization_requirements": ["Role-based access to projects and exports"], "data_protection_requirements": ["TLS in transit", "Encrypted storage"], "privacy_requirements": compliance, "compliance_reference": ", ".join(compliance), "verification_method": "Security review and integration tests"}],
            "software_quality_attributes": [{"attribute_id": "QA-001", "attribute_name": "Usability", "description": "Non-technical users should complete the intake and answer flow without training.", "measurement": "Task completion rate", "target_value": ">= 90%", "priority": "High"}],
            "business_rules": [{"rule_id": "BR-001", "description": "The platform only marks an SRS ready when required sections have content and export artifacts can be produced.", "applicable_roles": ["Administrator", "Primary User"], "conditions": ["Required sections exist"], "enforcement_requirements": ["REQ-011", "REQ-021"]}],
        },
        "other_requirements": {
            "database_requirements": [{"requirement_id": "DB-001", "description": "The database shall store sessions, answers, upload metadata, generated SRS JSON, and validation results.", "entities": ["Session", "Upload", "AnswerSet", "SRSArtifact", "ValidationReport"], "retention_policy": "Retain project data until policy-based cleanup", "backup_policy": "Daily backup with point-in-time recovery"}],
            "internationalization_requirements": [{"requirement_id": "I18N-001", "description": "The product should support future localization without changing the API contract.", "supported_languages": ["en"], "locale_rules": ["ISO date formatting for API payloads"]}],
            "legal_requirements": [{"requirement_id": "LEGAL-001", "description": "The platform shall state how uploaded materials are stored and used for generation.", "jurisdiction": "Project-dependent", "reference": ", ".join(compliance)}],
            "reuse_objectives": [{"objective_id": "REUSE-001", "description": "Reuse question planning, validation, and export modules across future agents.", "target_components": ["Question planner", "Validation engine", "Artifact exporter"]}],
            "additional_requirements": [{"requirement_id": "OTH-001", "description": f"Recommended delivery stack: {stack['frontend']} with {stack['api']} and {stack['ai_orchestrator']}."}],
        },
    }
    srs["appendices"] = {
        "glossary": [{"term": "SRS", "definition": "Software Requirements Specification"}, {"term": "NFR", "definition": "Nonfunctional Requirement"}],
        "analysis_models": [
            {"model_id": "AM-001", "model_type": "Interview Coverage Summary", "description": "Summarises AI-driven questions, user answers, and completion coverage for the current SRS.", "reference": "See analyst workspace interview review."},
            {"model_id": "AM-002", "model_type": "Service Outline", "description": "Summarises service responsibilities and handoff boundaries for the current build phase.", "reference": "See risk and stack review."},
        ],
        "to_be_determined_list": [{"tbd_id": f"TBD-{index + 1:03d}", "description": f"Clarify {question['key'].replace('_', ' ')}.", "owner": "Product owner", "status": "open", "target_resolution_date": (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()} for index, question in enumerate(QUESTION_DEFAULTS) if not has_answer_value(info.get(question["key"]))],
    }
    srs["services"] = [
        {"service_name": "api-gateway", "port": 8200, "summary": "Routes frontend requests to backend capabilities.", "endpoints": [{"method": "POST", "path": "/api/v1/sessions", "description": "Create a new session", "entities": ["Session"], "dependencies": ["project-service"]}, {"method": "POST", "path": "/api/v1/sessions/{id}/intake", "description": "Submit idea and files", "entities": ["Session", "Upload"], "dependencies": ["ingestion-service", "srs-service"]}]},
        {"service_name": "project-service", "port": 8201, "summary": "Stores session state, answers, and document metadata.", "endpoints": [{"method": "GET", "path": "/api/v1/sessions/{id}", "description": "Load a session", "entities": ["Session"], "dependencies": ["artifact-service"]}, {"method": "POST", "path": "/api/v1/sessions/{id}/answers", "description": "Save answers and generate the SRS", "entities": ["AnswerSet", "SRSDocument"], "dependencies": ["srs-service"]}]},
        {"service_name": "artifact-service", "port": 8202, "summary": "Publishes JSON and PDF artifacts for download.", "endpoints": [{"method": "GET", "path": "/api/v1/sessions/{id}/artifacts/srs.json", "description": "Download machine-readable JSON", "entities": ["SRSDocument"], "dependencies": ["object-storage"]}, {"method": "GET", "path": "/api/v1/sessions/{id}/artifacts/srs.pdf", "description": "Download the PDF artifact", "entities": ["SRSArtifact"], "dependencies": ["object-storage"]}]},
    ]
    generator = {
        "provider": "template-fallback",
        "model": None,
        "used_ai_generation": False,
    }
    if model_config()["ollama"]["available"]:
        try:
            content_pack = deepseek_srs_content_pack(session, srs, info)
            if content_pack:
                srs = apply_deepseek_srs_content_pack(srs, content_pack, interview_workspace)
                generator = {
                    "provider": "ollama",
                    "model": DEEPSEEK_MODEL,
                    "used_ai_generation": True,
                }
        except Exception:
            generator = {
                "provider": "template-fallback",
                "model": DEEPSEEK_MODEL,
                "used_ai_generation": False,
            }
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


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf")]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, used_font: ImageFont.ImageFont, width: int) -> list[str]:
    lines = []
    for paragraph in (text or "").splitlines() or [""]:
        words = paragraph.split() or [""]
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=used_font)[2] <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def pdf_bytes(srs: dict[str, Any], validation: dict[str, Any]) -> bytes:
    width, height, margin = 1240, 1754, 90
    title_font, heading_font, body_font = font(34, True), font(22, True), font(16)
    pages, page = [], Image.new("RGB", (width, height), "white")
    draw, y = ImageDraw.Draw(page), margin

    def new_page() -> None:
        nonlocal page, draw, y
        pages.append(page)
        page = Image.new("RGB", (width, height), "white")
        draw, y = ImageDraw.Draw(page), margin

    def write_block(text: str, used_font: ImageFont.ImageFont, gap: int = 12) -> None:
        nonlocal y
        for line in wrap(draw, text, used_font, width - margin * 2):
            line_height = draw.textbbox((0, 0), line or " ", font=used_font)[3] + gap
            if y + line_height > height - margin:
                new_page()
            draw.text((margin, y), line, fill="#111827", font=used_font)
            y += line_height

    write_block(srs["document_type"], title_font)
    write_block(srs["metadata"]["project_name"], heading_font)
    write_block(f"Project ID: {srs['metadata']['project_id']} | Status: {srs['metadata']['status']} | Generated: {srs['metadata']['last_updated']}", body_font)
    write_block("1. Introduction", heading_font)
    write_block(srs["sections"]["introduction"]["purpose"], body_font)
    write_block(srs["sections"]["introduction"]["product_scope"]["summary"], body_font)
    write_block("2. Core Features", heading_font)
    for feature in srs["sections"]["system_features"]:
        write_block(f"{feature['feature_id']} - {feature['feature_name']}", heading_font, 8)
        write_block(feature["description_and_priority"]["description"], body_font)
        for requirement in feature["functional_requirements"]:
            write_block(f"{requirement['requirement_id']}: {requirement['description']}", body_font, 8)
    write_block("3. Validation Summary", heading_font)
    write_block(f"Status: {validation['status']} | Completeness: {validation['completeness_score']}", body_font)
    for issue in validation["issues"][:10]:
        write_block(f"- {issue['path']}: {issue['message']}", body_font, 8)
    pages.append(page)
    buffer = BytesIO()
    pages[0].save(buffer, format="PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return buffer.getvalue()


def session_dir(session_id: str) -> Path:
    path = DATA_ROOT / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifact_links(session_id: str) -> dict[str, str | None]:
    folder = session_dir(session_id)
    return {"json": f"/api/v1/sessions/{session_id}/artifacts/srs.json" if (folder / "srs.json").exists() else None, "pdf": f"/api/v1/sessions/{session_id}/artifacts/srs.pdf" if (folder / "srs.pdf").exists() else None}


def serialize_session(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "status": session.get("status"),
        "project_name": session.get("project_name"),
        "audience": session.get("audience"),
        "idea": session.get("idea"),
        "uploads": session.get("uploads", []),
        "messages": session.get("messages", []),
        "answers": session.get("answers", {}),
        "analysis_summary": session.get("analysis_summary", ""),
        "question_plan": session.get("question_plan"),
        "draft_srs": session.get("draft_srs"),
        "final_srs": session.get("final_srs"),
        "validation": session.get("validation"),
        "recommended_stack": session.get("recommended_stack"),
        "diagram_previews": session.get("diagram_previews", []),
        "artifacts": artifact_links(session_id),
    }


def persist_session(session_id: str, session: dict[str, Any]) -> None:
    folder = session_dir(session_id)
    (folder / "session.json").write_text(json.dumps(serialize_session(session_id, session), indent=2), encoding="utf-8")
    if session.get("final_srs"):
        (folder / "srs.json").write_text(json.dumps(session["final_srs"], indent=2), encoding="utf-8")
        (folder / "srs.pdf").write_bytes(pdf_bytes(session["final_srs"], session["validation"]))


def require_session(session_id: str) -> dict[str, Any]:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    normalize_existing_question_plan(session)
    return session


def finalize_session(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    session["recommended_stack"] = build_stack(session)
    session["final_srs"] = build_srs(session, True)
    session["validation"] = validate_srs(session["final_srs"], session)
    session["diagram_previews"] = session["final_srs"].get("diagram_previews", [])
    session["status"] = "finalized"
    persist_session(session_id, session)
    return serialize_session(session_id, session)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "agent1-srs",
        "template_found": resolve_existing(TEMPLATE_CANDIDATES) is not None,
        "dataset_found": resolve_existing(DATASET_CANDIDATES) is not None,
        "planner": planner_name(),
        "models": model_config(),
    }


@app.post("/api/v1/sessions")
def create_session(payload: SessionCreate) -> dict[str, Any]:
    session_id = str(uuid4())
    SESSIONS[session_id] = {
        "id": session_id,
        "status": "created",
        "project_name": normalize_project_name(payload.project_name or guess_project_name(payload.idea)),
        "idea": payload.idea.strip(),
        "audience": payload.audience.strip() or "General users",
        "uploads": [],
        "messages": [],
        "answers": {},
        "analysis_summary": "",
        "question_plan": None,
        "draft_srs": None,
        "final_srs": None,
        "validation": None,
        "recommended_stack": None,
        "diagram_previews": [],
    }
    persist_session(session_id, SESSIONS[session_id])
    return {"session_id": session_id, "project_name": SESSIONS[session_id]["project_name"]}


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    return serialize_session(session_id, require_session(session_id))


@app.post("/api/v1/sessions/{session_id}/intake")
async def intake(session_id: str, message: str = Form(""), browser_transcript: str = Form(""), files: list[UploadFile] = File(default=[])) -> dict[str, Any]:
    session = require_session(session_id)
    combined = (message or "").strip()
    if browser_transcript.strip():
        combined = f"{combined}\n\n{VOICE_NOTE_MARKER}\n{browser_transcript.strip()}".strip()
    if not combined and not files:
        raise HTTPException(status_code=400, detail="Provide a text idea, a voice transcript, or at least one file.")
    for file in files:
        session["uploads"].append(summarize_upload(file, await file.read()))
    if combined:
        session["idea"] = session["idea"] or combined
        session["messages"].append({"role": "user", "content": combined, "created_at": now_iso()})
    session["question_plan"] = build_question_plan(session)
    session["analysis_summary"] = session["question_plan"]["summary"]
    session["recommended_stack"] = build_stack(session)
    session["draft_srs"] = build_srs(session, False)
    session["diagram_previews"] = session["draft_srs"].get("diagram_previews", [])
    session["status"] = "awaiting_answers"
    session["messages"].append({"role": "agent", "content": build_agent_message(session, "intake"), "created_at": now_iso()})
    persist_session(session_id, session)
    return {"reply": session["messages"][-1]["content"], "analysis_summary": session["analysis_summary"], "question_plan": session["question_plan"], "draft_srs": session["draft_srs"], "session": serialize_session(session_id, session)}


@app.post("/api/v1/sessions/{session_id}/message")
def send_message(session_id: str, payload: MessageRequest) -> dict[str, Any]:
    session = require_session(session_id)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    session["messages"].append({"role": "user", "content": message, "created_at": now_iso()})
    session["question_plan"] = build_question_plan(session)
    session["analysis_summary"] = session["question_plan"]["summary"]
    session["draft_srs"] = build_srs(session, False)
    session["messages"].append({"role": "agent", "content": build_agent_message(session, "update"), "created_at": now_iso()})
    persist_session(session_id, session)
    return {"reply": session["messages"][-1]["content"], "draft_srs": session["draft_srs"], "session": serialize_session(session_id, session)}


@app.post("/api/v1/sessions/{session_id}/answers")
def submit_answers(session_id: str, payload: AnswersRequest) -> dict[str, Any]:
    session = require_session(session_id)
    if not payload.answers:
        raise HTTPException(status_code=400, detail="At least one answer is required")
    session["answers"].update(payload.answers)
    missing = missing_interview_questions(session)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Please answer the remaining {len(missing)} interview question(s) before building the final SRS.",
        )
    serialized = finalize_session(session_id, session)
    return {"reply": "The SRS has been generated and validated.", "srs": session["final_srs"], "validation": session["validation"], "session": serialized}


@app.post("/api/v1/sessions/{session_id}/generate-srs")
def generate_srs(session_id: str) -> dict[str, Any]:
    session = require_session(session_id)
    missing = missing_interview_questions(session)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Please answer the remaining {len(missing)} interview question(s) before building the final SRS.",
        )
    serialized = finalize_session(session_id, session)
    return {"srs": session["final_srs"], "validation": session["validation"], "session": serialized}


@app.get("/api/v1/sessions/{session_id}/artifacts/{artifact_name}")
def download_artifact(session_id: str, artifact_name: str) -> Response:
    require_session(session_id)
    file_path = session_dir(session_id) / artifact_name.lower()
    if artifact_name.lower() not in {"srs.json", "srs.pdf"} or not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not ready yet")
    return Response(content=file_path.read_bytes(), media_type="application/pdf" if artifact_name.lower().endswith(".pdf") else "application/json", headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'})
'''
