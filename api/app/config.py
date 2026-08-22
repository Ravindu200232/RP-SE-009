from __future__ import annotations

import os
from pathlib import Path

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
OLLAMA_CHAT_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_CHAT_TIMEOUT_SECONDS", "90"))
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
