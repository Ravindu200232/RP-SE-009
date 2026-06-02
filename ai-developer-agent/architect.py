"""
Architect agents.

BACKEND  = LLM, two-phase (discover service index -> detail each service one at a
           time). Small calls => qwen2.5-coder:7b always finishes.

FRONTEND = DETERMINISTIC. The frontend is derived directly from the backend
           services/models/routes -- NOT guessed by the 7B model. This guarantees
           completeness (every entity gets its page) and perfect field/endpoint
           alignment with the backend. (The previous LLM discovery copied the
           2-entry example and stopped at 2 pages.)

Public functions (names kept so main.py imports unchanged):
  - backend_architect_agent(state)  -> {"microservices": [...]}
  - frontend_architect_agent(state) -> {"frontend_spec": {...}}
"""

import json
import re

from langchain_core.prompts import ChatPromptTemplate

from llm_config import get_llm, extract_json, stream_to_string
from state import GraphState


# =========================================================================
# 1. BACKEND ARCHITECT  (LLM, two-phase)
# =========================================================================

_BACKEND_DISCOVERY_PROMPT = """You are a Principal Backend Microservices Architect.
Read the SRS and decide how to split it into microservices. Output ONLY a high-level service index as raw JSON. No prose, no markdown, no code fences.

RULES:
- One service per bounded context. Group related entities together.
- If the SRS mentions users, login, roles, RBAC or authentication anywhere, you MUST include an "Auth-Service" first.
- Assign each service a UNIQUE port starting at 5001 and incrementing.
- List the model/entity names each service owns (copy entity names from the SRS data dictionary).
- needs_auth = true if any operation in the service must be protected.

Respond ONLY with raw JSON in EXACTLY this structure:
{{
  "services": [
    {{ "service_name": "Auth-Service", "database_name": "app_auth_db", "port": 5001, "models": ["User"], "needs_auth": false }},
    {{ "service_name": "Patient-Profile-Service", "database_name": "app_patient_db", "port": 5002, "models": ["PatientProfile"], "needs_auth": true }}
  ]
}}
Output compact JSON. No comments, no trailing text. Close every bracket."""


_BACKEND_DETAIL_PROMPT = """You are a Principal Backend Microservices Architect.
You are given the SRS and ONE service to fully specify. Output that ONE service as raw JSON. Backend only. No prose, no markdown, no code fences.

RULES:
- Copy field names VERBATIM from the SRS data dictionary (keep snake_case). Never rename or invent fields.
- Every model field needs the exact constraints that apply: type, required, unique, enum, min, max, ref, default.
- controllers: one per operation, each with a one-line logic note.
- routes: method, full /api/... path, handler (MUST match a controller name), requires_auth boolean.
- For an Auth-Service add "bcryptjs" and "jsonwebtoken" to packages and "JWT_SECRET" to env_variables, and the User model MUST contain "email" and "password" fields.

Respond ONLY with raw JSON in EXACTLY this structure:
{{
  "service_name": "Auth-Service",
  "database_config": {{ "database_name": "app_auth_db" }},
  "port_assignment": 5001,
  "env_variables": ["MONGO_URI", "JWT_SECRET", "PORT"],
  "required_npm_packages": ["express", "cors", "dotenv", "mongoose", "bcryptjs", "jsonwebtoken"],
  "models": [
    {{ "model_name": "User", "fields": {{
      "email": {{ "type": "String", "required": true, "unique": true }},
      "password": {{ "type": "String", "required": true }},
      "role": {{ "type": "String", "enum": ["ADMIN", "STAFF"], "required": true }}
    }} }}
  ],
  "controllers": [
    {{ "name": "registerUser", "logic": "Hash password, create user, return token" }},
    {{ "name": "loginUser", "logic": "Verify password, sign and return JWT" }}
  ],
  "routes": [
    {{ "method": "POST", "endpoint": "/api/auth/register", "handler": "registerUser", "requires_auth": false }},
    {{ "method": "POST", "endpoint": "/api/auth/login", "handler": "loginUser", "requires_auth": false }}
  ]
}}
Output compact JSON. No comments, no trailing text. Close every bracket."""


def backend_architect_agent(state: GraphState):
    srs_data = state["srs_input"]
    llm = get_llm()

    print("\n--- [BACKEND ARCHITECT: PHASE 1 - DISCOVERING SERVICES] ---")
    discovery_chain = ChatPromptTemplate.from_messages([
        ("system", _BACKEND_DISCOVERY_PROMPT),
        ("user", "SRS Input:\n\n{srs}")
    ]) | llm
    discovery_str = stream_to_string(discovery_chain, {"srs": srs_data})
    try:
        services = extract_json(discovery_str).get("services", [])
    except Exception as e:
        print("\nBackend discovery parse error:", e)
        services = []

    detail_chain = ChatPromptTemplate.from_messages([
        ("system", _BACKEND_DETAIL_PROMPT),
        ("user", "SRS Data:\n{srs}\n\nService to specify in full:\n{service}")
    ]) | llm

    microservices = []
    for i, svc in enumerate(services):
        name = svc.get("service_name", f"Service-{i + 1}")
        print(f"\n\n--- [BACKEND ARCHITECT: PHASE 2 - DETAILING {name} ({i + 1}/{len(services)})] ---")
        detail_str = stream_to_string(detail_chain, {"srs": srs_data, "service": json.dumps(svc)})
        try:
            microservices.append(extract_json(detail_str))
        except Exception as e:
            print(f"\nBackend detail parse error for {name}: {e}")

    print(f"\n\n--- [BACKEND ARCHITECT: DONE - {len(microservices)} SERVICES] ---")
    return {"microservices": microservices}


# =========================================================================
# 2. FRONTEND ARCHITECT  (DETERMINISTIC, derived from the backend)
# =========================================================================

def _is_auth_service(svc: dict) -> bool:
    if "auth" in (svc.get("service_name") or "").lower():
        return True
    return any("/auth/" in (r.get("endpoint") or "") for r in svc.get("routes", []))


def _service_label(service_name: str) -> str:
    """'Patient-Profile-Service' -> 'Patient Profile'."""
    s = re.sub(r"-?service$", "", str(service_name or ""), flags=re.IGNORECASE)
    return re.sub(r"[-_]+", " ", s).strip() or "Item"


def _route_slug(label: str) -> str:
    return "/" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def _input_type(field_name: str, spec: dict) -> str:
    name = (field_name or "").lower()
    if spec.get("enum"):
        return "select"
    t = str(spec.get("type", "String"))
    if "password" in name:
        return "password"
    if "email" in name:
        return "email"
    if "phone" in name:
        return "tel"
    if t == "Number":
        return "number"
    if t == "Boolean":
        return "checkbox"
    if t == "Date":
        return "datetime-local" if "time" in name else "date"
    if t == "Object" or t.startswith("Array"):
        return "textarea"
    if any(k in name for k in ("notes", "narrative", "description", "comment", "address", "bio", "summary")):
        return "textarea"
    return "text"


def _model_to_form_fields(model: dict) -> list:
    """Build create-form fields from a backend model. Auto-managed fields
    (those with a default) are skipped; everything else maps to an input."""
    out = []
    for fname, spec in (model.get("fields") or {}).items():
        if not isinstance(spec, dict) or "default" in spec:
            continue
        field = {
            "field_name": fname,
            "input_type": _input_type(fname, spec),
            "required": bool(spec.get("required", False)),
        }
        if spec.get("enum"):
            field["options"] = spec["enum"]
        if "min" in spec:
            field["min"] = spec["min"]
        if "max" in spec:
            field["max"] = spec["max"]
        out.append(field)
    return out


def _route_by_method(svc: dict, method: str):
    for r in svc.get("routes", []):
        if (r.get("method") or "").upper() == method.upper():
            return r
    return None


def frontend_architect_agent(state: GraphState):
    microservices = state.get("microservices", [])
    print("\n\n--- [FRONTEND ARCHITECT: BUILDING COMPLETE PAGE SET FROM BACKEND] ---")

    auth_svc = next((s for s in microservices if _is_auth_service(s)), None)

    # ---- roles come from the Auth User.role enum (matches backend casing) ----
    roles = ["Public"]
    primary_role = "Admin"
    user_model = None
    if auth_svc:
        models = auth_svc.get("models", []) or []
        user_model = next((m for m in models if (m.get("model_name") or "").lower() == "user"),
                          models[0] if models else None)
        if user_model:
            rspec = (user_model.get("fields") or {}).get("role", {})
            enum_roles = rspec.get("enum") if isinstance(rspec, dict) else None
            if enum_roles:
                roles = ["Public"] + list(enum_roles)
                primary_role = enum_roles[0]

    pages = []
    flow = []

    # ---- auth pages ----
    if auth_svc:
        login_ep = next((r["endpoint"] for r in auth_svc["routes"] if "login" in r.get("endpoint", "")),
                        "/api/auth/login")
        register_ep = next((r["endpoint"] for r in auth_svc["routes"] if "register" in r.get("endpoint", "")),
                           "/api/auth/register")

        pages.append({
            "page_name": "Login", "allowed_role": "Public", "route_path": "/login",
            "page_kind": "auth_login", "entity": "User",
            "navigation_flow": {"on_success": "/dashboard", "on_cancel": "/"},
            "forms": [{
                "form_name": "LoginForm", "api_endpoint": login_ep, "method": "POST",
                "fields": [
                    {"field_name": "email", "input_type": "email", "required": True},
                    {"field_name": "password", "input_type": "password", "required": True},
                ],
            }],
        })

        register_fields = [
            {"field_name": "email", "input_type": "email", "required": True},
            {"field_name": "password", "input_type": "password", "required": True},
        ]
        if user_model:
            rspec = (user_model.get("fields") or {}).get("role")
            if isinstance(rspec, dict) and rspec.get("enum"):
                register_fields.append({
                    "field_name": "role", "input_type": "select",
                    "required": True, "options": rspec["enum"],
                })
        pages.append({
            "page_name": "Register", "allowed_role": "Public", "route_path": "/register",
            "page_kind": "auth_register", "entity": "User",
            "navigation_flow": {"on_success": "/dashboard", "on_cancel": "/"},
            "forms": [{
                "form_name": "RegisterForm", "api_endpoint": register_ep, "method": "POST",
                "fields": register_fields,
            }],
        })
        flow.append({"journey_name": "Login Journey", "steps": ["/", "/login", "/dashboard"]})
        flow.append({"journey_name": "Register Journey", "steps": ["/", "/register", "/dashboard"]})

    # ---- dashboard ----
    pages.append({
        "page_name": "Dashboard", "allowed_role": primary_role, "route_path": "/dashboard",
        "page_kind": "dashboard", "entity": None,
        "navigation_flow": {"on_success": "/dashboard", "on_cancel": "/"},
        "forms": [],
    })

    # ---- one page per non-auth service, aligned to its real routes ----
    for svc in microservices:
        if _is_auth_service(svc):
            continue
        models = svc.get("models", []) or []
        model = models[0] if models else None
        if not model:
            continue
        label = _service_label(svc.get("service_name"))
        base = _route_slug(label)
        comp_form_name = re.sub(r"[^A-Za-z0-9]+", "", label) + "Form"

        post = _route_by_method(svc, "POST")
        get = _route_by_method(svc, "GET")

        if post:  # Create form page (fields from the model)
            pages.append({
                "page_name": f"{label} Form",
                "allowed_role": primary_role,
                "route_path": f"{base}/new",
                "page_kind": "create",
                "entity": model.get("model_name"),
                "navigation_flow": {"on_success": "/dashboard", "on_cancel": "/dashboard"},
                "forms": [{
                    "form_name": comp_form_name,
                    "api_endpoint": post.get("endpoint"),
                    "method": "POST",
                    "fields": _model_to_form_fields(model),
                }],
            })
            flow.append({"journey_name": f"{label} Creation Journey",
                         "steps": ["/dashboard", f"{base}/new", "/dashboard"]})
        elif get:  # read-only view page (no form), aligned to the GET route
            pages.append({
                "page_name": f"{label} View",
                "allowed_role": primary_role,
                "route_path": base,
                "page_kind": "list",
                "entity": model.get("model_name"),
                "navigation_flow": {"on_success": base, "on_cancel": "/dashboard"},
                "forms": [],
                "read_endpoint": get.get("endpoint"),
            })

    frontend_spec = {
        "global_user_roles": roles,
        "structural_components": ["Glassmorphic Sidebar", "Navbar", "ProtectedRoute"],
        "required_npm_packages": ["axios", "react-router-dom", "tailwindcss", "lucide-react"],
        "global_navigation_flow_map": flow,
        "pages": pages,
    }
    print(f"--- [FRONTEND ARCHITECT: DONE - {len(pages)} PAGES] ---")
    for p in pages:
        print(f"      - {p['page_name']:<28} [{p['allowed_role']}]  {p['route_path']}")
    return {"frontend_spec": frontend_spec}