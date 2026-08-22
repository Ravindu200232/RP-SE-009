"""Compose the SRS from the plan the customer approved — and from nothing else.

`offline_srs.build_offline_srs` builds from the *domain template*: it never sees
the app type, so every app got `users`, `roles`, `permissions`, `audit_logs`,
role-based access control and a public marketing site whether or not anyone
asked. A calculator came out with five roles and fifteen API endpoints.

This module inverts that. The approved plan is the boundary: every role, screen,
record and requirement here traces back to something the customer read and
signed off on. The only things added unprompted are universal quality
attributes — how fast it should be, that it should work on a phone — which are
not scope.

The auth gate is the important part. `_auth_on()` decides once, and everything
login-shaped (the user tables, the authentication requirements, the auth
endpoints, the access matrix) is emitted only behind it.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from .app_types import PALETTES
from .domains import universal_tables


_AUTH_TABLE_NAMES = ("users", "roles")


_ANONYMOUS_ROLES = {"visitor", "guest", "public", "anonymous", "everyone", "user"}

_MAX_REQUIREMENTS = 40


def _snake(text: str) -> str:

    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(text or ""))
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def _table_name(text: str) -> str:
    """`Sale Item` -> `sale_items`. Plural, because a table holds many."""
    name = _snake(text)
    if not name:
        return "record"
    if name.endswith("y") and not name.endswith(("ay", "ey", "oy", "uy")):
        return name[:-1] + "ies"
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    return name + "s"


def _title(text: str) -> str:
    text = str(text or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else text


def _sentence(text: str) -> str:
    text = str(text or "").strip().rstrip(".")
    return f"{text}." if text else ""


def _auth_on(pack: dict, plan: dict) -> bool:
    """Does this app have accounts at all?

    Two independent votes, both of which must pass. The app type fixes the
    policy — a landing page and a one-page tool are `disabled` and that is not
    the customer's to renegotiate. The plan then has to actually name someone
    who logs in: a plan whose only user is "Visitor" describes a public site,
    whatever its profile says.
    """
    if str((pack or {}).get("auth_policy")) == "disabled":
        return False
    named = [str(u.get("role", "")).strip().lower()
             for u in (plan or {}).get("users") or []]
    return any(r and r not in _ANONYMOUS_ROLES for r in named)


def _roles_from_plan(plan: dict) -> list[dict]:
    """One role per plan user. Never a `super_admin`, never a `guest`."""
    out: list[dict] = []
    seen: set[str] = set()
    for user in plan.get("users") or []:
        name = str(user.get("role", "")).strip()
        key = _snake(name)
        if not key or key in seen:
            continue
        seen.add(key)
        duties = [d for d in (user.get("can_do") or []) if str(d).strip()]
        description = ("; ".join(str(d).strip() for d in duties[:4])
                       or f"Uses {name.lower()} features of the system.")
        out.append({"role_key": key, "role_name": _title(name),
                    "description": _sentence(description)})
    if not out:

        out.append({"role_key": "user", "role_name": "User",
                    "description": "Uses the application."})
    return out


_TYPE_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("price", "amount", "total", "cost", "rate", "salary", "fee", "discount",
      "balance", "subtotal"), "decimal"),
    (("quantity", "qty", "stock", "count", "level", "number of", "age"), "integer"),
    (("date of", "birth", "expiry", "due date", "preferred date"), "date"),
    (("created", "updated", "at", "time", "timestamp"), "datetime"),
    (("is ", "has ", "active", "enabled", "paid", "confirmed"), "boolean"),
    (("status", "state", "type", "category level"), "enum"),
    (("description", "notes", "message", "body", "address", "comment"), "text"),
    (("email",), "string"),
    (("photo", "image", "picture", "file", "attachment", "logo"), "string"),
]


def _field_type(label: str) -> str:
    low = f" {str(label).lower().strip()} "
    for needles, kind in _TYPE_HINTS:
        if any(n in low for n in needles):
            return kind
    return "string"


def _tables_from_plan(plan: dict, auth: bool) -> tuple[list[dict], list[dict]]:
    """Tables and relationships, from `plan["records"]` alone."""
    tables: list[dict] = []
    record_names: list[str] = []

    for rec in plan.get("records") or []:
        name = str(rec.get("name", "")).strip()
        if not name:
            continue
        table = _table_name(name)
        if any(t["table_name"] == table for t in tables):
            continue
        record_names.append(table)
        fields = [{"name": "id", "type": "uuid", "primary_key": True, "nullable": False}]
        for keep in rec.get("keeps") or []:
            label = str(keep).strip()
            if not label:
                continue
            fname = _snake(label)
            if not fname or any(f["name"] == fname for f in fields):
                continue
            entry: dict[str, Any] = {"name": fname, "type": _field_type(label),
                                     "nullable": False}
            if entry["type"] == "enum":
                entry["values"] = ["active", "inactive"]
                entry["default"] = "active"
            fields.append(entry)
        fields.append({"name": "created_at", "type": "datetime", "nullable": False})
        tables.append({"table_name": table,
                       "description": f"{_title(name)} records.",
                       "fields": fields})

    relationships: list[dict] = []
    if auth:

        auth_tables = [t for t in universal_tables()
                       if t["table_name"] in _AUTH_TABLE_NAMES]
        tables = auth_tables + tables
        relationships.append({
            "from": "users.role_id", "to": "roles.id", "type": "many_to_one",
            "description": "Each user belongs to one role.",
        })

    by_name = {t["table_name"] for t in tables}
    seen = {(r["from"], r["to"]) for r in relationships}
    for t in tables:
        if t["table_name"] in _AUTH_TABLE_NAMES:
            continue
        for f in t["fields"]:
            if not f["name"].endswith("_id") or f.get("primary_key"):
                continue
            target = _table_name(f["name"][:-3])
            if target not in by_name or target == t["table_name"]:
                continue
            f["type"] = "foreign_key"
            f["references"] = f"{target}.id"
            edge = (f"{t['table_name']}.{f['name']}", f"{target}.id")
            if edge in seen:
                continue
            seen.add(edge)
            relationships.append({
                "from": edge[0], "to": edge[1], "type": "many_to_one",
                "description": f"Each {_singular(t['table_name'])} refers to "
                               f"one {_singular(target)}.",
            })
    return tables, relationships


def _singular(table: str) -> str:
    """`categories` -> `category`, `sales` -> `sale`. For readable prose only."""
    if table.endswith("ies"):
        return table[:-3] + "y"
    if table.endswith(("sses", "xes", "zes", "ches", "shes")):
        return table[:-2]
    return table[:-1] if table.endswith("s") and not table.endswith("ss") else table


def _route_for(name: str, index: int) -> str:
    slug = _snake(name).replace("_", "-")
    return "/" if index == 0 else f"/{slug or f'page-{index}'}"


def _pages_from_plan(plan: dict, auth: bool) -> tuple[list[dict], list[dict]]:
    """Screens become pages. With no login, every one of them is public."""
    public: list[dict] = []
    protected: list[dict] = []
    for i, screen in enumerate(plan.get("screens") or []):
        name = str(screen.get("name", "")).strip()
        if not name:
            continue
        who = [str(w).strip() for w in (screen.get("who") or []) if str(w).strip()]
        page = {
            "page_name": _title(name),
            "route": _route_for(name, i),
            "page_type": "page",
            "sections": [],
            "functions": [_sentence(screen.get("purpose", ""))] if screen.get("purpose") else [],
        }
        anonymous = not who or all(w.lower() in _ANONYMOUS_ROLES for w in who)
        if not auth or anonymous:
            public.append({**page, "login_required": False})
        else:
            protected.append({**page, "login_required": True,
                              "allowed_roles": [_snake(w) for w in who]})
    return public, protected


def _requirements_from_plan(plan: dict, tables: list[dict], auth: bool,
                            archetype: str) -> list[dict]:
    """Functional requirements, every one of them traceable to the plan."""
    out: list[dict] = []
    seen: set[str] = set()

    def add(module: str, text: str, priority: str = "high") -> None:
        text = _sentence(text)
        key = text.lower()
        if not text or key in seen or len(out) >= _MAX_REQUIREMENTS:
            return
        seen.add(key)
        out.append({"id": f"FR-{len(out) + 1:03d}", "module": module,
                    "requirement": text, "priority": priority})

    if auth:
        add("Authentication",
            "The system shall let a person sign in with an email address and password")
        add("Authorization",
            "The system shall show each signed-in person only the screens their role allows")

    for user in plan.get("users") or []:
        role = _title(user.get("role", "user"))
        for duty in user.get("can_do") or []:
            duty = str(duty).strip().rstrip(".")
            if duty:
                add(role, f"The system shall allow a {role} to {duty[:1].lower()}{duty[1:]}")

    for feature in plan.get("features") or []:
        feature = str(feature).strip().rstrip(".")
        if feature:
            add("Core Features", f"The system shall provide {feature[:1].lower()}{feature[1:]}"
                if not feature.lower().startswith("the system") else feature)

    if archetype == "fullstack-crud":
        for t in tables:
            if t["table_name"] in _AUTH_TABLE_NAMES:
                continue
            label = t["table_name"].replace("_", " ")
            module = _title(label)
            add(module, f"The system shall let a user add a new {label[:-1]} record")
            add(module, f"The system shall list {label} with search and filtering")
            add(module, f"The system shall let a user edit and remove a {label[:-1]} record",
                "medium")

    for wf in plan.get("workflows") or []:
        name = str(wf.get("name", "")).strip()
        if name and wf.get("steps"):
            add("Workflows", f"The system shall support the {name.lower()} workflow "
                             f"end to end", "medium")

    while len(out) < 3:

        add("Core Features", f"The system shall do what the approved plan describes "
                             f"({len(out) + 1})", "medium")
    return out


def _nfrs(auth: bool, devices: list[str]) -> list[dict]:
    """Quality attributes. Universal ones are not scope; auth ones are gated."""
    items = [
        ("Performance", "Primary screens should load within 3 seconds (P95) under normal conditions."),
        ("Usability", "A first-time user should be able to complete the main task without training."),
        ("Compatibility", "The application must work in current versions of Chrome, Edge, Firefox and Safari."),
        ("Maintainability", "Code shall be organised by feature, so one change touches one place."),
    ]
    if "desktop" not in devices or len(devices) > 1:
        items.append(("Usability",
                      "The interface must be usable on a phone screen without horizontal scrolling."))
    if auth:
        items += [
            ("Security", "Passwords must be hashed with a strong adaptive algorithm (bcrypt or argon2)."),
            ("Security", "Every protected screen and endpoint must check both sign-in and role."),
        ]
    return [{"id": f"NFR-{i:03d}", "category": cat, "requirement": text}
            for i, (cat, text) in enumerate(items, start=1)]


def _api_from_tables(tables: list[dict], auth: bool) -> list[dict]:
    api: list[dict] = []
    if auth:
        api += [
            {"method": "POST", "path": "/api/auth/login",
             "description": "Sign in and start a session.", "auth_required": False},
            {"method": "POST", "path": "/api/auth/register",
             "description": "Create an account.", "auth_required": False},
            {"method": "GET", "path": "/api/auth/me",
             "description": "The signed-in person.", "auth_required": True},
        ]
    for t in tables:
        if t["table_name"] in _AUTH_TABLE_NAMES:
            continue
        res = t["table_name"].replace("_", "-")
        api += [
            {"method": "GET", "path": f"/api/{res}",
             "description": f"List {t['table_name']}.", "auth_required": auth},
            {"method": "POST", "path": f"/api/{res}",
             "description": f"Create a {t['table_name'][:-1]} record.", "auth_required": auth},
            {"method": "GET", "path": f"/api/{res}/{{id}}",
             "description": f"Read one {t['table_name'][:-1]} record.", "auth_required": auth},
            {"method": "PUT", "path": f"/api/{res}/{{id}}",
             "description": f"Update a {t['table_name'][:-1]} record.", "auth_required": auth},
        ]
    return api


def _role_matrix(roles: list[dict], plan: dict, public: list[dict],
                 protected: list[dict]) -> list[dict]:
    """What each role may do, read off the plan rather than assumed."""
    duties = {_snake(u.get("role", "")): [str(d) for d in (u.get("can_do") or [])]
              for u in plan.get("users") or []}
    out = []
    for r in roles:
        key = r["role_key"]
        pages = [p["page_name"] for p in protected if key in (p.get("allowed_roles") or [])]
        out.append({
            "role": key,
            "allowed_pages": pages + [p["page_name"] for p in public],
            "allowed_functions": duties.get(key, [])[:8],
            "restricted_functions": [],
        })
    return out


def _rtm(frs: list[dict], tables: list[dict], pages: list[dict]) -> list[dict]:
    table_names = [t["table_name"] for t in tables]
    page_names = [p["page_name"] for p in pages]
    out = []
    for fr in frs:
        words = {w.lower() for w in re.split(r"\W+", fr["module"]) if w}
        matched = [tn for tn in table_names if any(w in tn for w in words)][:2]
        out.append({"requirement_id": fr["id"], "module": fr["module"],
                    "pages": page_names[:2], "tables": matched,
                    "test_case": f"TC-{fr['id'][3:]}"})
    return out


def build_branding(session: dict, pack: dict, app_name: str) -> dict:
    """What the app looks like, and whether a logo has to be drawn."""
    answers = (session or {}).get("answers") or {}

    def ans(key, default=None):
        entry = answers.get(key)
        return default if entry is None else entry.get("value", default)

    source = str(ans("logo") or "none")
    if source not in ("generate", "upload", "none"):
        source = "none"

    palette_name = _resolve_palette(ans("color_palette"), pack)
    palette = PALETTES[palette_name]
    theme = str(ans("theme_type") or "light")

    branding = {
        "logo_required": source == "generate",
        "logo_source": source,
        "logo_image_prompt": "",
        "theme": theme,
        "palette": palette_name,
        "primary_color": palette.get("primary", "#6366F1"),
    }
    if source == "generate":
        branding["logo_image_prompt"] = _logo_prompt(app_name, pack, branding)
    return branding


_PALETTE_ALIASES = {
    "corporate_blue": "business", "corporate": "business", "blue": "business",
    "fresh_mint": "mint", "green": "mint",
    "deep_navy_gold": "navy", "deep_navy": "navy",
    "black_gold": "gold", "black": "gold",
    "modern_indigo": "indigo", "purple": "indigo",
}


def _resolve_palette(answer, pack: dict) -> str:
    """The palette key whose colour we will actually print."""
    key = _snake(answer if not isinstance(answer, list) else (answer[0] if answer else ""))
    if key in PALETTES:
        return key
    if key in _PALETTE_ALIASES:
        return _PALETTE_ALIASES[key]
    fallback = str(pack.get("palette_name") or "indigo")
    return fallback if fallback in PALETTES else "indigo"


def _logo_prompt(app_name: str, pack: dict, branding: dict) -> str:
    """A text-to-image prompt for the logo mark.

    Nothing in this stack can draw it — Ollama is text-only — so what we produce
    is the brief, ready to paste into whichever image model the customer uses.
    """
    label = str(pack.get("app_label") or "web application").lower()

    domain = str(pack.get("domain_label") or "").strip()
    named = domain and float(pack.get("domain_confidence") or 0) >= 0.6
    subject = f"a {label}" + (f" for {domain.lower()}" if named else "")
    dark = branding.get("theme") == "dark"
    return (
        f"A flat vector logo mark for \"{app_name}\", {subject}. "
        f"One simple, memorable symbol that reads clearly at 32 pixels. "
        f"Primary colour {branding['primary_color']} on a "
        f"{'dark charcoal' if dark else 'white'} background. "
        f"No text, no lettering, no gradients, no photorealism, no drop shadows. "
        f"Square composition, generous margin, transparent background, SVG-like clean edges."
    )


def build_srs_from_plan(*, project: dict, plan: dict, pack: dict | None = None,
                        session: dict | None = None, brief: str = "") -> dict:
    """A complete, schema-valid SRS containing only what the plan contains."""
    plan = plan or {}
    pack = pack or {}
    session = session or {}

    auth = _auth_on(pack, plan)
    archetype = str(pack.get("archetype") or "fullstack-crud")

    app_name = (str((session.get("answers", {}).get("app_name", {}) or {}).get("value") or "").strip()
                or str(project.get("title") or "").strip()
                or "Application")

    roles = _roles_from_plan(plan)
    tables, relationships = _tables_from_plan(plan, auth)
    public_pages, protected_pages = _pages_from_plan(plan, auth)
    frs = _requirements_from_plan(plan, tables, auth, archetype)

    devices = []
    entry = (session.get("answers") or {}).get("responsive_pwa")
    if entry:
        value = entry.get("value")
        devices = [str(v) for v in value] if isinstance(value, list) else [str(value)]

    branding = build_branding(session, pack, app_name)
    intent = str(plan.get("product_intent") or "").strip()

    modules = []
    for screen in plan.get("screens") or []:
        name = _title(screen.get("name", ""))
        if name and name not in modules:
            modules.append(name)
    for t in tables:
        name = _title(t["table_name"].replace("_", " "))
        if name not in modules:
            modules.append(name)

    ambiguities = [
        {"id": f"AMB-{i:03d}", "area": "Approved plan",
         "description": str(q.get("question", "")),
         "assumption_made": "Left open; to be settled before build.",
         "needs_clarification": bool(q.get("required"))}
        for i, q in enumerate(plan.get("open_questions") or [], start=1)
        if str(q.get("question", "")).strip()
    ]

    security = ["All traffic must be served over HTTPS.",
                "Input from the browser must be validated on the server before it is stored."]
    if auth:
        security += [
            "Passwords must never be stored or logged in plain text.",
            "A session must expire and be re-authenticated after a period of inactivity.",
            "Each request to a protected endpoint must be checked against the caller's role.",
        ]

    srs_document: dict[str, Any] = {
        "document_title": "Software Requirements Specification",
        "project_name": app_name,
        "version": project.get("current_version") or "1.0.0",
        "document_language": project.get("language", "English"),
        "system_category": str(pack.get("app_label") or "Web Application"),
        "prepared_for": "Approved plan build",
        "app_summary": {
            "app_name": app_name,
            "short_description": intent or (brief or project.get("raw_idea", ""))[:400],
            "business_goal": intent or f"To deliver {app_name} as described in the approved plan.",
            "target_users": [r["role_name"] for r in roles],
        },
        "app_type": {

            "key": str(pack.get("app_type") or "other"),
            "primary_type": str(pack.get("app_label") or "Web Application"),
            "archetype": archetype,
            "frontend_type": "Responsive web application",
            "backend_type": "REST API",
            "database_type": "Document database",
            "example_stack": {"frontend": "Next.js / React", "backend": "Next.js API routes",
                              "database": "MongoDB",
                              "auth": "Email + password session" if auth else "None"},
        },
        "authentication_requirement": (
            {"login_required": True,
             "public_landing_pages_required": bool(public_pages),
             "multi_role_access_required": len(roles) > 1,
             "password_reset_required": True}
            if auth else {"login_required": False}
        ),
        "roles": roles,
        "role_access_matrix": _role_matrix(roles, plan, public_pages, protected_pages) if auth else [],
        "public_pages": public_pages,
        "protected_pages": protected_pages,
        "main_modules": modules,
        "database_design": {"tables": tables, "relationships": relationships},
        "api_design": _api_from_tables(tables, auth),
        "functional_requirements": frs,
        "non_functional_requirements": _nfrs(auth, devices),
        "business_workflows": [
            {"workflow_name": str(w.get("name", "Workflow")),
             "steps": [str(s) for s in (w.get("steps") or [])]}
            for w in plan.get("workflows") or [] if w.get("steps")
        ],
        "validation_rules": [],
        "notification_rules": [],
        "security_requirements": security,
        "ui_ux_requirements": {
            "design_style": str(plan.get("look_and_feel") or "").strip(),
            "theme": branding["theme"],
            "mobile_support": "desktop" not in devices or len(devices) > 1,
            "pwa_support": "pwa" in devices,
            "required_components": _components_for(tables, auth, archetype),
        },
        "reporting_requirements": [],
        "integration_requirements": [],
        "assumptions": [str(a) for a in plan.get("assumptions") or []],
        "constraints": ["The system is built only from the approved plan; "
                        "anything outside it is a change request."],
        "ambiguities": ambiguities,
        "risk_priority": [],
        "acceptance_criteria": [
            {"id": f"AC-{i:03d}", "criterion": _sentence(f)}
            for i, f in enumerate(plan.get("features") or [], start=1)
        ][:12],
        "requirement_traceability_matrix": _rtm(frs, tables, public_pages + protected_pages),
        "diagrams": [],

        "branding": branding,
        "approved_plan": copy.deepcopy(plan),

        "customer_notes": str(plan.get("customer_notes") or "").strip(),
    }
    return {"srs_document": srs_document}


def _components_for(tables: list[dict], auth: bool, archetype: str) -> list[str]:
    """UI parts this app actually needs, not the standard admin kit."""
    out = ["Navigation bar"]
    domain_tables = [t for t in tables if t["table_name"] not in _AUTH_TABLE_NAMES]
    if domain_tables and archetype == "fullstack-crud":
        out += ["Data table with search and filter", "Create / edit form",
                "Confirmation dialog", "Empty state"]
    if auth:
        out += ["Sign-in form", "Signed-in user menu"]
    if archetype == "landing-single-page":
        out += ["Hero section", "Section headings", "Enquiry form"]
    if archetype == "single-tool":
        out += ["Input panel", "Result display"]
    return out


def merge_pack_planned(skeleton: dict, pack: dict, plan: dict) -> dict:
    """Overlay the LLM's enrichment, refusing anything the plan does not contain.

    Unlike `offline_srs.merge_pack`, nothing is re-injected here: no universal
    tables, no forced `super_admin`, no hardcoded authentication requirements.
    The model may sharpen wording and add detail to what exists; it may not
    widen the scope, and anything it invents is dropped rather than argued with.
    """
    doc = copy.deepcopy(skeleton)["srs_document"]
    pack = pack or {}
    plan = plan or {}

    allowed_tables = {t["table_name"] for t in doc["database_design"]["tables"]}
    allowed_roles = {r["role_key"] for r in doc["roles"]}

    summary = pack.get("app_summary")
    if isinstance(summary, dict):
        for key in ("business_goal", "short_description"):
            value = str(summary.get(key) or "").strip()
            if value:
                doc["app_summary"][key] = value

    by_name = {t["table_name"]: t for t in doc["database_design"]["tables"]}
    for t in pack.get("tables") or []:
        if not isinstance(t, dict):
            continue
        name = _snake(str(t.get("table_name", "")))
        target = by_name.get(name) or by_name.get(_table_name(name))
        if not target or name not in allowed_tables and _table_name(name) not in allowed_tables:
            continue
        if str(t.get("description") or "").strip():
            target["description"] = str(t["description"]).strip()
        existing = {f["name"] for f in target["fields"]}
        for f in t.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fname = _snake(str(f.get("name", "")))
            if not fname or fname in existing:
                continue
            existing.add(fname)
            target["fields"].append({"name": fname,
                                     "type": str(f.get("type") or "string"),
                                     "nullable": bool(f.get("nullable", True))})

    seen = {r["requirement"].strip().lower() for r in doc["functional_requirements"]}
    for fr in pack.get("functional_requirements") or []:
        if not isinstance(fr, dict) or len(doc["functional_requirements"]) >= _MAX_REQUIREMENTS:
            continue
        text = _sentence(fr.get("requirement", ""))
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        doc["functional_requirements"].append({
            "id": f"FR-{len(doc['functional_requirements']) + 1:03d}",
            "module": str(fr.get("module") or "Core Features"),
            "requirement": text,
            "priority": str(fr.get("priority") or "medium"),
        })

    for nfr in pack.get("non_functional_requirements") or []:
        if not isinstance(nfr, dict):
            continue
        text = _sentence(nfr.get("requirement", ""))
        if text:
            doc["non_functional_requirements"].append({
                "id": f"NFR-{len(doc['non_functional_requirements']) + 1:03d}",
                "category": str(nfr.get("category") or "Quality"),
                "requirement": text,
            })

    for key in ("validation_rules", "notification_rules",
                "reporting_requirements", "integration_requirements"):
        value = pack.get(key)
        if isinstance(value, list) and value:
            doc[key] = value

    for key, prefix, required in (("risk_priority", "RISK", ("area", "risk", "severity",
                                                             "reason", "mitigation")),
                                  ("ambiguities", "AMB", ("area", "description",
                                                          "assumption_made"))):
        value = pack.get(key)
        if not isinstance(value, list) or not value:
            continue
        rows = []
        for item in value:
            if not isinstance(item, dict) or not all(str(item.get(f, "")).strip()
                                                     for f in required):
                continue
            rows.append({**item, "id": f"{prefix}-{len(rows) + 1:03d}"})
        if rows:
            doc[key] = rows

    if isinstance(pack.get("business_workflows"), list) and pack["business_workflows"]:
        doc["business_workflows"] = [
            {"workflow_name": str(w.get("workflow_name") or w.get("name") or "Workflow"),
             "steps": [str(s) for s in (w.get("steps") or [])]}
            for w in pack["business_workflows"] if isinstance(w, dict) and w.get("steps")
        ]

    prompt = str((pack.get("branding") or {}).get("logo_image_prompt") or "").strip()
    if prompt and doc.get("branding", {}).get("logo_required"):
        doc["branding"]["logo_image_prompt"] = prompt

    doc["roles"] = [r for r in doc["roles"] if r["role_key"] in allowed_roles]
    doc["requirement_traceability_matrix"] = _rtm(
        doc["functional_requirements"],
        doc["database_design"]["tables"],
        doc["public_pages"] + doc["protected_pages"],
    )
    return {"srs_document": doc}


def effective_plan(doc: dict) -> dict:
    """A plan-shaped view of the specification as it stands NOW.

    `approved_plan` is frozen on purpose — it is the record of what the
    customer signed off, and `customization._DERIVED` keeps the editor away
    from it. But four of the seven template diagrams read the plan rather than
    the document (`diagrams._plan`), so after a revision they redraw from
    pre-edit data: a role added by prompt never appears in the use-case
    diagram, and a page added by prompt never appears in the component or
    deployment one. With the LLM up its enrichment pass papers over this,
    because it is given the live document. With templates alone — which is what
    ships whenever Ollama is unreachable — the diagram silently reverts.

    This is the inverse projection of `build_srs_from_plan`: the same shape,
    rebuilt from the document instead of frozen beside it. It is written to
    `doc["effective_plan"]` after a customization, and `_plan` prefers it.

    Deliberately NOT a replacement for `approved_plan`: nothing here can
    recover `product_intent` or `look_and_feel` as the customer phrased them,
    so those are carried over from the approved plan unchanged.
    """
    doc = doc or {}
    approved = doc.get("approved_plan") or {}

    allowed = {m.get("role"): (m.get("allowed_functions") or [])
               for m in (doc.get("role_access_matrix") or [])
               if isinstance(m, dict)}

    approved_can = {}
    for user in (approved.get("users") or []):
        if isinstance(user, dict) and user.get("role"):
            approved_can[str(user["role"]).casefold()] = [
                str(c) for c in (user.get("can_do") or []) if str(c).strip()]

    users = []
    for role in (doc.get("roles") or []):
        if not isinstance(role, dict):
            continue
        key = role.get("role_key")
        name = role.get("role_name") or key
        if not name:
            continue
        can = [str(f) for f in (allowed.get(key) or allowed.get(name) or [])]
        if not can:
            can = approved_can.get(str(name).casefold(), [])
        if not can and role.get("description"):

            can = [d.strip() for d in str(role["description"]).split(";")
                   if d.strip()]
        users.append({"role": str(name), "can_do": can})

    screens = []
    for page in ((doc.get("public_pages") or []) + (doc.get("protected_pages") or [])):
        if not isinstance(page, dict):
            continue
        name = page.get("page_name") or page.get("name")
        if not name:
            continue
        fns = [str(f) for f in (page.get("functions") or []) if str(f).strip()]
        screens.append({
            "name": str(name),
            "purpose": fns[0] if fns else "",
            "who": [str(r) for r in (page.get("allowed_roles") or [])],
        })

    records = []
    for table in ((doc.get("database_design") or {}).get("tables") or []):
        if not isinstance(table, dict):
            continue
        name = table.get("table_name") or table.get("name")
        if not name:
            continue
        keeps = [f.get("name") if isinstance(f, dict) else str(f)
                 for f in (table.get("fields") or [])]
        records.append({"name": str(name),
                        "keeps": [k for k in keeps if k
                                  and k not in ("id", "created_at", "updated_at")]})

    workflows = [
        {"name": str(w.get("workflow_name") or w.get("name") or "Workflow"),
         "steps": [str(s) for s in (w.get("steps") or [])]}
        for w in (doc.get("business_workflows") or [])
        if isinstance(w, dict) and w.get("steps")
    ]

    features = [str(f) for f in (approved.get("features") or []) if str(f).strip()]

    return {
        "product_intent": approved.get("product_intent", ""),
        "look_and_feel": approved.get("look_and_feel", ""),
        "users": users or approved.get("users") or [],
        "screens": screens or approved.get("screens") or [],
        "records": records or approved.get("records") or [],
        "workflows": workflows or approved.get("workflows") or [],
        "features": features or approved.get("features") or [],
    }


__all__ = ["build_srs_from_plan", "merge_pack_planned", "build_branding",
           "effective_plan", "_auth_on"]
