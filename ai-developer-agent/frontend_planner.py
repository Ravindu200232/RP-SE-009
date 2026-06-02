"""
Frontend planner -- FULLY DETERMINISTIC.

The frontend_spec coming from the architect is already complete and aligned to
the backend, so there is nothing for the 7B model to "guess" here. We template
each page/component blueprint and build the router directly. Result: a 100%
complete, 100% accurate plan every run -- the Coder Agent can rely on it.

(Creative UI / real JSX is the Coder Agent's job; this stage just produces an
exact, machine-checkable build spec.)

Outputs (unchanged file names, sync-agent compatible):
  plans/frontend/component_<Name>.json
  plans/frontend/page_<Page_Name>.json
  plans/frontend/App_Router.json
"""

import json
import os
import re

from state import GraphState


# ---------------------------------------------------------------- helpers

def _slug(name: str) -> str:
    return str(name).replace(" ", "_")


def _component_name(page_name: str) -> str:
    """'Billing Invoice Form' -> 'BillingInvoiceForm'."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", str(page_name or "")) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Page"


_COMPONENT_SPECS = {
    "Glassmorphic Sidebar": {
        "sections": ["Brand / logo", "Role-aware navigation links", "Active-route highlight", "User profile + logout"],
        "logic": [
            "Import useNavigate; read user role from storage",
            "Render the nav links allowed for that role",
            "Highlight the active route",
            "Logout clears storage and navigates to '/login'",
        ],
    },
    "Navbar": {
        "sections": ["Brand", "Page title / breadcrumbs", "User menu (profile, logout)"],
        "logic": [
            "Import useNavigate; read auth state from storage",
            "Render brand and a user menu",
            "Logout clears the JWT and navigates to '/login'",
        ],
    },
    "ProtectedRoute": {
        "sections": ["Auth gate (renders children or redirects)"],
        "logic": [
            "Read the JWT and user role from storage",
            "If there is no token, navigate('/login')",
            "If allowedRole is set and the role does not match, navigate('/dashboard')",
            "Otherwise render the children",
        ],
    },
}


def _component_blueprint(comp: str) -> dict:
    spec = _COMPONENT_SPECS.get(comp, {"sections": ["Content"], "logic": ["Implement the component"]})
    cname = _component_name(comp)
    return {
        "file_type": "Component",
        "name": cname,
        "file_path": f"src/components/{cname}.jsx",
        "allowed_role": None,
        "ui_layout_spec": {"theme_style": "Premium glassmorphism with backdrop-blur", "sections": spec["sections"]},
        "data_bindings_and_forms": {},
        "navigation_flow": {},
        "routes_map": [],
        "logic_steps_for_coder": spec["logic"],
    }


def _sections_for(page_kind: str, has_form: bool) -> list:
    if page_kind in ("auth_login", "auth_register"):
        return ["Centered glass card", "Brand / logo header", "Form fields", "Primary action button", "Secondary link"]
    if page_kind == "dashboard":
        return ["Welcome header", "Summary stat cards", "Recent activity", "Quick-action shortcuts"]
    if page_kind == "list":
        return ["Header with search", "Glassmorphic data table", "Row actions", "Pagination"]
    if has_form:
        return ["Page header with title", "Glassmorphic form card", "Grouped input fields", "Submit and Cancel actions"]
    return ["Page header", "Content area"]


def _page_blueprint(page: dict) -> dict:
    name = page.get("page_name", "Page")
    comp = _component_name(name)
    kind = page.get("page_kind")
    role = page.get("allowed_role", "Public")
    protected = str(role).lower() != "public"
    nav = page.get("navigation_flow") or {"on_success": "/dashboard", "on_cancel": "/"}

    forms = page.get("forms") or []
    form = forms[0] if forms else None
    has_form = bool(form and form.get("fields"))

    data_block = {}
    logic = ["Import useState, useNavigate and axios"]

    if has_form:
        fields_to_bind = []
        for f in form["fields"]:
            fb = {
                "field_name": f["field_name"],
                "type": f.get("input_type", "text"),
                "validation": "required" if f.get("required") else "optional",
            }
            if f.get("options"):
                fb["options"] = f["options"]
            if "min" in f:
                fb["min"] = f["min"]
            if "max" in f:
                fb["max"] = f["max"]
            fields_to_bind.append(fb)

        endpoint = form.get("api_endpoint", "")
        method = (form.get("method") or "POST").upper()
        data_block = {
            "form_name": form.get("form_name", f"{comp}Form"),
            "api_endpoint": endpoint,
            "method": method,
            "fields_to_bind": fields_to_bind,
        }
        logic.append("Hold every field in component state")
        logic.append(f"On submit, send axios {method} to '{endpoint}' with the form data")
        if protected:
            logic.append("Attach the JWT from storage as an Authorization Bearer header")
        logic.append(f"On success, navigate('{nav.get('on_success', '/dashboard')}')")
        logic.append("On error, surface a validation / error message")
    elif kind == "dashboard":
        logic += [
            "On mount, fetch summary data with axios (Bearer token)",
            "Render the stat cards and quick links",
            "Wire each shortcut to its route with navigate()",
        ]
    elif kind == "list":
        endpoint = page.get("read_endpoint", "")
        logic += [
            f"On mount, fetch records with axios GET from '{endpoint}' (Bearer token)",
            "Render the rows in a glassmorphic table",
            "Wire row actions with navigate()",
        ]
    else:
        logic += ["Fetch any needed data on mount", "Render the content"]

    return {
        "file_type": "Page",
        "name": comp,
        "file_path": f"src/pages/{comp}.jsx",
        "allowed_role": role,
        "ui_layout_spec": {
            "theme_style": "Premium glassmorphism with backdrop-blur, soft borders, subtle gradients; fully responsive",
            "sections": _sections_for(kind, has_form),
        },
        "data_bindings_and_forms": data_block,
        "navigation_flow": nav,
        "routes_map": [],
        "logic_steps_for_coder": logic,
    }


def _build_router(pages: list) -> dict:
    """One Route per page; protected = true for any non-Public role."""
    routes_map = []
    for p in pages:
        role = p.get("allowed_role") or "Public"
        comp = _component_name(p.get("page_name"))
        routes_map.append({
            "path": p.get("route_path") or "/",
            "component": comp,
            "import_path": f"src/pages/{comp}.jsx",
            "allowed_role": role,
            "protected": str(role).lower() != "public",
        })
    return {
        "file_type": "Config",
        "name": "App.jsx",
        "file_path": "src/App.jsx",
        "allowed_role": "None (Public)",
        "ui_layout_spec": {"theme_style": "Routing configuration (no UI)", "sections": []},
        "data_bindings_and_forms": {},
        "navigation_flow": {},
        "routes_map": routes_map,
        "logic_steps_for_coder": [
            "Import BrowserRouter, Routes, Route, Navigate from react-router-dom",
            "Import ProtectedRoute and every page component listed in routes_map",
            "Render BrowserRouter wrapping a single Routes block",
            "Add one Route per routes_map entry using its path and component",
            "For entries where protected is true, wrap the element in <ProtectedRoute allowedRole={entry.allowed_role}>",
            "Add a catch-all Route path='*' that redirects to '/' using Navigate",
        ],
    }


# ---------------------------------------------------------------- agent

def frontend_planner_agent(state: GraphState):
    frontend_spec = state["frontend_spec"]
    pages = frontend_spec.get("pages", [])
    components = frontend_spec.get("structural_components", [])

    print(f"\n=== [PARENT FRONTEND PLANNER (deterministic): {len(components)} COMPONENTS & {len(pages)} PAGES] ===")
    os.makedirs("plans/frontend", exist_ok=True)
    all_frontend_plans = []

    # 1. Components
    for comp in components:
        bp = _component_blueprint(comp)
        all_frontend_plans.append(bp)
        with open(f"plans/frontend/component_{_slug(comp)}.json", "w") as f:
            json.dump(bp, f, indent=2)
        print(f"  [COMPONENT] {comp} -> {bp['file_path']}")

    # 2. Pages
    for page in pages:
        bp = _page_blueprint(page)
        all_frontend_plans.append(bp)
        with open(f"plans/frontend/page_{_slug(page.get('page_name', 'Page'))}.json", "w") as f:
            json.dump(bp, f, indent=2)
        nfields = len(bp["data_bindings_and_forms"].get("fields_to_bind", [])) if bp["data_bindings_and_forms"] else 0
        print(f"  [PAGE] {page.get('page_name'):<26} -> {bp['file_path']}  ({nfields} fields)")

    # 3. Central router (deterministic, always complete)
    router_plan = _build_router(pages)
    all_frontend_plans.append(router_plan)
    with open("plans/frontend/App_Router.json", "w") as f:
        json.dump(router_plan, f, indent=2)
    print(f"  [ROUTER] App.jsx -> {len(router_plan['routes_map'])} routes")

    print("=== [PARENT FRONTEND PLANNER: ALL ENTERPRISE BLUEPRINTS SAVED] ===")
    return {"frontend_plan": json.dumps({"complete_frontend_roadmap": all_frontend_plans}, indent=2)}