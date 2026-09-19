"""Render the approved specification into the four shared agent handoff files.

Each file is the agent's *only* view of the product specification — the sandbox
prevents reading ``srs_latest.json`` directly.  Every field that a designer or
developer needs to avoid inventing (routes, schemas, roles, auth, validation,
branding) must be present in the file that agent reads first.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

FILES = ("app.md", "sitemap.md", "prototype.md", "builder.md")

# ── tiny formatting helpers ──────────────────────────────────────────────

def _val(obj, *keys, default=""):
    """Safely drill into nested dicts."""
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k)
        else:
            return default
    return obj if obj not in (None, "", [], {}) else default


def _bullet(items, key=None, id_key=None):
    """One bullet per item, whatever shape it is."""
    out = []
    for item in (items or []):
        if isinstance(item, str):
            out.append(f"- {item}")
        elif isinstance(item, dict):
            ident = f"{item[id_key]} " if id_key and item.get(id_key) else ""
            text = (item.get(key) if key else None) or (
                item.get("requirement") or item.get("description")
                or item.get("criterion") or item.get("rule")
                or item.get("text") or item.get("name") or "")
            text = " ".join(str(text).split())
            if text:
                out.append(f"- {ident}{text}")
    return "\n".join(out)

# ── section builders ─────────────────────────────────────────────────────

def _identity_section(spec) -> str:
    """App identity and summary."""
    summary = spec.get("app_summary") or {}
    parts = ["## Identity\n"]
    for label, val in [
        ("App name", summary.get("app_name") or spec.get("project_name")),
        ("Description", summary.get("short_description")),
        ("Business goal", summary.get("business_goal")),
        ("System category", spec.get("system_category")),
    ]:
        if val:
            parts.append(f"- **{label}**: {val}")
    users = summary.get("target_users") or []
    if users:
        parts.append(f"- **Target users**: {', '.join(str(u) for u in users)}")
    return "\n".join(parts)


def _auth_section(spec) -> str:
    """Authentication configuration."""
    auth = spec.get("authentication_requirement")
    if not auth or not isinstance(auth, dict):
        return ""
    parts = ["## Authentication\n"]
    for label, key in [
        ("Login required", "login_required"),
        ("Sign-in route", "sign_in_route"),
        ("Sign-up route", "sign_up_route"),
        ("Registration mode", "registration_mode"),
        ("Self-registration", "self_registration"),
        ("Default registration role", "registration_role"),
        ("Auth transport", "auth_transport"),
        ("When signed out visits protected page", "signed_out_protected_access"),
        ("When wrong role visits page", "wrong_role_access"),
        ("Password reset required", "password_reset_required"),
    ]:
        val = auth.get(key)
        if val is not None and val != "":
            parts.append(f"- **{label}**: {val}")
    for label, key in [
        ("Identity fields", "identity_fields"),
        ("Registration fields", "registration_fields"),
        ("Registration roles", "registration_roles"),
    ]:
        vals = auth.get(key)
        if vals:
            parts.append(f"- **{label}**: {', '.join(str(v) for v in vals)}")
    return "\n".join(parts) if len(parts) > 1 else ""


def _roles_section(spec) -> str:
    """User roles."""
    roles = spec.get("roles")
    if not roles:
        return ""
    parts = ["## Roles\n"]
    for r in roles:
        if isinstance(r, str):
            parts.append(f"- {r}")
        elif isinstance(r, dict):
            name = r.get("role_name") or r.get("name") or ""
            desc = r.get("description") or ""
            parts.append(f"- **{name}**" + (f": {desc}" if desc else ""))
    return "\n".join(parts)


def _access_matrix_section(spec) -> str:
    """Role access matrix."""
    matrix = spec.get("role_access_matrix")
    if not matrix:
        return ""
    parts = ["## Access Matrix\n"]
    for row in matrix:
        if not isinstance(row, dict):
            continue
        role = row.get("role") or row.get("role_name") or ""
        pages = ", ".join(str(p) for p in (row.get("allowed_pages") or []))
        fns = ", ".join(str(f) for f in (row.get("allowed_functions") or []))
        line = f"- **{role}**"
        if pages:
            line += f" — pages: {pages}"
        if fns:
            line += f" — can: {fns}"
        parts.append(line)
    return "\n".join(parts)


def _pages_section(spec, key, title) -> str:
    """Public or protected pages list."""
    pages = spec.get(key)
    if not pages:
        return ""
    parts = [f"## {title}\n"]
    for p in pages:
        if isinstance(p, str):
            parts.append(f"- {p}")
            continue
        if not isinstance(p, dict):
            continue
        name = p.get("page_name") or p.get("name") or ""
        route = p.get("route") or ""
        line = f"- **{name}**"
        if route:
            line += f" `{route}`"
        roles = [str(r) for r in (p.get("allowed_roles") or []) if str(r).strip()]
        if roles:
            line += f" — roles: {', '.join(roles)}"
        fns = [str(f) for f in (p.get("functions") or []) if str(f).strip()]
        if fns:
            line += f" — {'; '.join(fns)}"
        sections = [str(s) for s in (p.get("sections") or []) if str(s).strip()]
        if sections:
            line += f" — sections: {', '.join(sections)}"
        parts.append(line)
    return "\n".join(parts)


def _screens_section(spec) -> str:
    """Screens list (from plan or custom spec)."""
    screens = spec.get("screens")
    if not screens:
        return ""
    parts = ["## Screens\n"]
    for s in screens:
        if isinstance(s, str):
            parts.append(f"- {s}")
        elif isinstance(s, dict):
            name = s.get("name") or s.get("screen_name") or s.get("title") or ""
            route = s.get("route") or ""
            purpose = s.get("purpose") or s.get("description") or ""
            line = f"- **{name}**" if name else "-"
            if route:
                line += f" `{route}`"
            if purpose:
                line += f" — {purpose}"
            parts.append(line)
    return "\n".join(parts)


def _requirements_section(spec) -> str:
    """Functional requirements."""
    reqs = spec.get("functional_requirements") or spec.get("requirements")
    if not reqs:
        return ""
    parts = ["## Functional Requirements\n"]
    for r in reqs:
        if isinstance(r, str):
            parts.append(f"- {r}")
            continue
        if not isinstance(r, dict):
            continue
        rid = r.get("id") or ""
        mod = r.get("module") or ""
        text = " ".join(str(r.get("requirement") or r.get("description") or r.get("text") or "").split())
        pri = r.get("priority") or ""
        line = f"- **{rid}**" if rid else "-"
        if mod:
            line += f" [{mod}]"
        if text:
            line += f" {text}"
        if pri:
            line += f" (priority: {pri})"
        parts.append(line)
    return "\n".join(parts)


def _database_section(spec) -> str:
    """Database schema — compact one-line-per-field format."""
    db = spec.get("database_design")
    if not db or not isinstance(db, dict):
        return ""
    tables = db.get("tables") or []
    if not tables:
        return ""
    parts = ["## Database Schema\n"]
    for table in tables:
        if not isinstance(table, dict):
            continue
        tname = table.get("table_name") or table.get("name") or ""
        tdesc = table.get("description") or ""
        parts.append(f"### {tname}" + (f" — {tdesc}" if tdesc else ""))
        parts.append("")
        for field in (table.get("fields") or table.get("columns") or []):
            if isinstance(field, str):
                parts.append(f"- `{field}`")
                continue
            if not isinstance(field, dict):
                continue
            fname = field.get("name") or field.get("column") or ""
            ftype = field.get("type") or ""
            flags = []
            if ftype:
                flags.append(ftype)
            if field.get("primary_key") or field.get("primary"):
                flags.append("PK")
            if field.get("unique"):
                flags.append("unique")
            ref = field.get("references") or field.get("foreign_key")
            if ref:
                flags.append(f"→ {ref}")
            vals = field.get("values") or field.get("enum")
            if vals:
                shown = ", ".join(str(v) for v in list(vals)[:8])
                flags.append(f"enum: {shown}")
            if field.get("default") is not None and field.get("default") != "":
                flags.append(f"default: {field['default']}")
            if field.get("nullable") is True or field.get("required") is False:
                flags.append("optional")
            parts.append(f"- `{fname}` ({'; '.join(flags)})" if flags else f"- `{fname}`")
        parts.append("")

    rels = db.get("relationships") or []
    if rels:
        parts.append("### Relationships\n")
        for rel in rels:
            if not isinstance(rel, dict):
                continue
            fr = rel.get("from") or ""
            to = rel.get("to") or ""
            rtype = rel.get("type") or ""
            parts.append(f"- `{fr}` → `{to}` ({rtype})")
        parts.append("")
    return "\n".join(parts)


def _api_section(spec) -> str:
    """API route design."""
    apis = spec.get("api_design")
    if not apis:
        return ""
    parts = ["## API Routes\n"]
    parts.append("| Method | Path | Auth | Roles | Description |")
    parts.append("|--------|------|------|-------|-------------|")
    for ep in apis:
        if isinstance(ep, str):
            parts.append(f"| | {ep} | | | |")
            continue
        if not isinstance(ep, dict):
            continue
        method = str(ep.get("method") or "GET").upper()
        path = ep.get("path") or ep.get("endpoint") or ""
        desc = " ".join(str(ep.get("description") or "").split())
        auth = "yes" if ep.get("auth_required") else "no"
        roles = ", ".join(str(r) for r in (ep.get("allowed_roles") or []))
        parts.append(f"| {method} | `{path}` | {auth} | {roles} | {desc} |")
    return "\n".join(parts)


def _workflows_section(spec) -> str:
    """Business workflows."""
    flows = spec.get("business_workflows")
    if not flows:
        return ""
    parts = ["## Business Workflows\n"]
    for w in flows:
        if not isinstance(w, dict):
            continue
        name = w.get("workflow_name") or w.get("name") or ""
        who = w.get("who") or ""
        steps = [" ".join(str(s).split()) for s in (w.get("steps") or []) if str(s).strip()]
        if not name:
            continue
        header = f"### {name}"
        if who:
            header += f" ({who})"
        parts.append(header)
        for i, step in enumerate(steps, 1):
            parts.append(f"{i}. {step}")
        parts.append("")
    return "\n".join(parts)


def _validation_section(spec) -> str:
    """Validation rules."""
    rules = spec.get("validation_rules")
    if not rules:
        return ""
    parts = ["## Validation Rules\n"]
    for r in rules:
        if isinstance(r, str):
            parts.append(f"- {r}")
        elif isinstance(r, dict):
            field = r.get("field") or ""
            rule = r.get("rule") or ""
            parts.append(f"- `{field}`: {rule}")
    return "\n".join(parts)


def _notification_section(spec) -> str:
    """Notification rules."""
    notifs = spec.get("notification_rules")
    if not notifs:
        return ""
    parts = ["## Notification Rules\n"]
    for n in notifs:
        if not isinstance(n, dict):
            continue
        event = n.get("event") or ""
        recip = ", ".join(str(r) for r in (n.get("recipients") or []))
        chan = ", ".join(str(c) for c in (n.get("channels") or []))
        parts.append(f"- **{event}** → {recip}" + (f" via {chan}" if chan else ""))
    return "\n".join(parts)


def _acceptance_section(spec) -> str:
    """Acceptance criteria."""
    criteria = spec.get("acceptance_criteria")
    if not criteria:
        return ""
    parts = ["## Acceptance Criteria\n"]
    return "\n".join(parts) + "\n" + _bullet(criteria, key="criterion", id_key="id")


def _traceability_section(spec) -> str:
    """Requirement traceability matrix."""
    rows = spec.get("requirement_traceability_matrix")
    if not rows:
        return ""
    parts = ["## Requirement Traceability\n"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("requirement_id") or row.get("id") or ""
        pages = ", ".join(str(p) for p in (row.get("pages") or []))
        tables = ", ".join(str(t) for t in (row.get("tables") or []))
        test = row.get("test_case") or ""
        bits = []
        if pages:
            bits.append(f"pages: {pages}")
        if tables:
            bits.append(f"data: {tables}")
        if test:
            bits.append(f"test: {test}")
        if bits:
            parts.append(f"- **{rid}** → {'; '.join(bits)}")
    return "\n".join(parts)


def _nfr_section(spec) -> str:
    """Non-functional requirements."""
    nfrs = spec.get("non_functional_requirements")
    if not nfrs:
        return ""
    parts = ["## Non-Functional Requirements\n"]
    for r in nfrs:
        if isinstance(r, str):
            parts.append(f"- {r}")
        elif isinstance(r, dict):
            rid = r.get("id") or ""
            cat = r.get("category") or ""
            text = r.get("requirement") or r.get("description") or ""
            parts.append(f"- **{rid}** [{cat}] {text}" if rid else f"- [{cat}] {text}")
    return "\n".join(parts)


def _reporting_section(spec) -> str:
    """Reporting requirements."""
    reports = spec.get("reporting_requirements")
    if not reports:
        return ""
    parts = ["## Reports\n"]
    for r in reports:
        if isinstance(r, str):
            parts.append(f"- {r}")
            continue
        if not isinstance(r, dict):
            continue
        name = r.get("report_name") or r.get("name") or ""
        bits = []
        if r.get("filters"):
            bits.append("filtered by " + ", ".join(str(f) for f in r["filters"]))
        if r.get("exports"):
            bits.append("exports " + ", ".join(str(e) for e in r["exports"]))
        parts.append(f"- **{name}**" + (f" — {'; '.join(bits)}" if bits else ""))
    return "\n".join(parts)


def _integration_section(spec) -> str:
    """Integration requirements."""
    integ = spec.get("integration_requirements")
    if not integ:
        return ""
    parts = ["## Integrations\n"]
    for item in integ:
        if isinstance(item, str):
            parts.append(f"- {item}")
        elif isinstance(item, dict):
            name = item.get("name") or ""
            itype = item.get("type") or ""
            desc = item.get("description") or ""
            parts.append(f"- **{name}** ({itype}): {desc}" if itype else f"- **{name}**: {desc}")
    return "\n".join(parts)


def _branding_section(spec) -> str:
    """Branding (colors, typography, logo)."""
    brand = spec.get("branding")
    if not brand or not isinstance(brand, dict):
        return ""
    parts = ["## Branding\n"]
    for key, val in brand.items():
        if val and isinstance(val, (str, int)):
            parts.append(f"- **{key.replace('_', ' ').title()}**: {val}")
    return "\n".join(parts) if len(parts) > 1 else ""


def _ux_section(spec) -> str:
    """UI/UX requirements."""
    ux = spec.get("ui_ux_requirements")
    if not ux or not isinstance(ux, dict):
        return ""
    parts = ["## UI/UX Requirements\n"]
    components = ux.get("required_components") or []
    for key, val in ux.items():
        if key == "required_components":
            continue
        if val and isinstance(val, (str, bool, int)):
            parts.append(f"- **{key.replace('_', ' ').title()}**: {val}")
    if components:
        parts.append(f"- **Required components**: {', '.join(str(c) for c in components)}")
    return "\n".join(parts) if len(parts) > 1 else ""


# ── main file assembly ───────────────────────────────────────────────────

_KNOWN_KEYS = {
    "document_title", "project_name", "version", "document_language",
    "system_category", "prepared_for", "app_summary", "app_type",
    "authentication_requirement", "roles", "role_access_matrix",
    "public_pages", "protected_pages", "screens", "functional_requirements",
    "requirements", "database_design", "api_design", "business_workflows",
    "validation_rules", "notification_rules", "security_requirements",
    "acceptance_criteria", "requirement_traceability_matrix",
    "non_functional_requirements", "reporting_requirements",
    "integration_requirements", "branding", "ui_ux_requirements",
    "assumptions", "constraints", "main_modules", "approved_plan",
    "approved_plan_markdown", "builder_handoff", "diagrams",
    "standards_profile", "document_control", "requirements_quality_review",
    "ambiguities", "risk_priority", "customer_notes",
    # Preserve effective plan structure without generating redundant document sections during sync.
    "effective_plan",
}


def _generic_markdown(value, level=2) -> str:
    if isinstance(value, dict):
        return "\n\n".join(f"{'#' * min(level, 6)} {str(k).replace('_', ' ').title()}\n\n{_generic_markdown(v, level + 1)}"
                           for k, v in value.items() if v not in (None, "", [], {}))
    if isinstance(value, list):
        return "\n\n".join(_generic_markdown(item, level) if isinstance(item, (dict, list)) else f"- {item}" for item in value)
    return str(value if value is not None else "")


def _build_app_md(spec) -> str:
    """Full structured application specification."""
    extra_sections = [
        f"## {str(k).replace('_', ' ').title()}\n\n{_generic_markdown(v, 3)}"
        for k, v in spec.items()
        if k not in _KNOWN_KEYS and v not in (None, "", [], {})
    ]

    sections = [
        "# Application Specification\n",
        _identity_section(spec),
        _auth_section(spec),
        _roles_section(spec),
        _access_matrix_section(spec),
        _pages_section(spec, "public_pages", "Public Pages"),
        _pages_section(spec, "protected_pages", "Protected Pages"),
        _screens_section(spec),
        _requirements_section(spec),
        _database_section(spec),
        _api_section(spec),
        _workflows_section(spec),
        _validation_section(spec),
        _notification_section(spec),
        _bullet(spec.get("security_requirements")) and
            "## Security Requirements\n\n" + _bullet(spec.get("security_requirements")) or "",
        _acceptance_section(spec),
        _traceability_section(spec),
        _nfr_section(spec),
        _reporting_section(spec),
        _integration_section(spec),
        _bullet(spec.get("assumptions")) and
            "## Assumptions\n\n" + _bullet(spec.get("assumptions")) or "",
        _bullet(spec.get("constraints")) and
            "## Constraints\n\n" + _bullet(spec.get("constraints")) or "",
        _bullet(spec.get("main_modules")) and
            "## Main Modules\n\n" + _bullet(spec.get("main_modules")) or "",
        *extra_sections,
    ]
    return "\n\n".join(s for s in sections if s.strip()) + "\n"


def _build_sitemap_md(spec) -> str:
    """Explicit route table with navigation structure."""
    parts = ["# Site Map\n"]

    # Screens (from plan or general spec)
    screens = spec.get("screens") or []
    if screens:
        parts.append("## Screens\n")
        parts.append("| Screen | Route | Purpose |")
        parts.append("|--------|-------|---------|")
        for s in screens:
            if isinstance(s, dict):
                name = s.get("name") or s.get("screen_name") or s.get("title") or "Screen"
                route = s.get("route") or ""
                purpose = s.get("purpose") or s.get("description") or ""
                parts.append(f"| {name} | `{route}` | {purpose} |")
            elif isinstance(s, str):
                parts.append(f"| {s} | | |")
        parts.append("")

    # Public pages
    pub = spec.get("public_pages") or []
    if pub:
        parts.append("## Public Pages\n")
        parts.append("| Page | Route | Functions |")
        parts.append("|------|-------|-----------|")
        for p in pub:
            if isinstance(p, str):
                parts.append(f"| {p} | | |")
                continue
            if not isinstance(p, dict):
                continue
            name = p.get("page_name") or p.get("name") or ""
            route = p.get("route") or ""
            fns = "; ".join(str(f) for f in (p.get("functions") or []) if str(f).strip())
            parts.append(f"| {name} | `{route}` | {fns} |")
        parts.append("")

    # Protected pages
    prot = spec.get("protected_pages") or []
    if prot:
        parts.append("## Protected Pages (Login Required)\n")
        parts.append("| Page | Route | Allowed Roles | Functions |")
        parts.append("|------|-------|---------------|-----------|")
        for p in prot:
            if isinstance(p, str):
                parts.append(f"| {p} | | | |")
                continue
            if not isinstance(p, dict):
                continue
            name = p.get("page_name") or p.get("name") or ""
            route = p.get("route") or ""
            roles = ", ".join(str(r) for r in (p.get("allowed_roles") or []))
            fns = "; ".join(str(f) for f in (p.get("functions") or []) if str(f).strip())
            parts.append(f"| {name} | `{route}` | {roles} | {fns} |")
        parts.append("")

    # API routes
    apis = spec.get("api_design") or []
    if apis:
        parts.append("## API Routes\n")
        parts.append("| Method | Path | Auth | Roles | Description |")
        parts.append("|--------|------|------|-------|-------------|")
        for ep in apis:
            if isinstance(ep, str):
                parts.append(f"| | {ep} | | | |")
                continue
            if not isinstance(ep, dict):
                continue
            method = str(ep.get("method") or "GET").upper()
            path = ep.get("path") or ep.get("endpoint") or ""
            desc = " ".join(str(ep.get("description") or "").split())
            auth = "yes" if ep.get("auth_required") else "no"
            roles = ", ".join(str(r) for r in (ep.get("allowed_roles") or []))
            parts.append(f"| {method} | `{path}` | {auth} | {roles} | {desc} |")
        parts.append("")

    # Auth flow navigation
    auth = spec.get("authentication_requirement") or {}
    if auth.get("login_required"):
        parts.append("## Navigation Flow\n")
        parts.append(f"- Unauthenticated → `{auth.get('sign_in_route', '/login')}`")
        if auth.get("sign_up_route"):
            parts.append(f"- Registration → `{auth['sign_up_route']}`")
        parts.append(f"- After login → role-based dashboard / landing page")
        parts.append(f"- Wrong role → {auth.get('wrong_role_access', 'forbidden page')}")
        parts.append(f"- Signed out → {auth.get('signed_out_protected_access', 'redirect to sign-in')}")
        parts.append("")

    if not pub and not prot and not screens and not apis:
        parts.append("Use the screens, roles and navigation described in app.md. "
                      "Preserve their routes and relationships; do not invent an application category.\n")

    return "\n".join(parts) + "\n"


def _build_prototype_md(spec) -> str:
    """Complete design brief for the HTML prototype designer."""
    parts = [
        "# Design and HTML Prototype\n",
        "Read app.md, sitemap.md and builder.md to understand the whole application. "
        "Apply the user's design customization. "
        "Build every specified screen as a complete, responsive HTML application in .agentforge/prototype/, "
        "using CSS for its design and JavaScript for working interactions. "
        "Start with index.html and link the screens so the specified journeys can be explored. "
        "Use meaningful content from the specification and include the relevant loading, empty, error and success states. "
        "Keep shared visual choices in styles.css and behavior in local scripts. "
        "Scope browser storage keys to this project. "
        "The prototype demonstrates interactions with sample data; never put credentials into it. "
        "Read existing files when continuing and change only what the request needs. "
        "Report missing information or failed validation clearly.\n",
    ]

    # Branding
    brand_text = _branding_section(spec)
    if brand_text:
        parts.append(brand_text)

    # UI/UX
    ux_text = _ux_section(spec)
    if ux_text:
        parts.append(ux_text)

    # Page inventory — all pages the prototype must draw
    pub = spec.get("public_pages") or []
    prot = spec.get("protected_pages") or []
    screens = spec.get("screens") or []
    if pub or prot or screens:
        parts.append("## Pages to Build\n")
        for p in pub:
            if isinstance(p, dict):
                name = p.get("page_name") or p.get("name") or ""
                route = p.get("route") or ""
                fns = "; ".join(str(f) for f in (p.get("functions") or []) if str(f).strip())
                parts.append(f"- **{name}** `{route}` (public)" + (f" — {fns}" if fns else ""))
        for p in prot:
            if isinstance(p, dict):
                name = p.get("page_name") or p.get("name") or ""
                route = p.get("route") or ""
                roles = ", ".join(str(r) for r in (p.get("allowed_roles") or []))
                fns = "; ".join(str(f) for f in (p.get("functions") or []) if str(f).strip())
                parts.append(f"- **{name}** `{route}` (roles: {roles})" + (f" — {fns}" if fns else ""))
        for s in screens:
            if isinstance(s, dict):
                name = s.get("name") or s.get("screen_name") or s.get("title") or "Screen"
                route = s.get("route") or ""
                purpose = s.get("purpose") or s.get("description") or ""
                parts.append(f"- **{name}** `{route}`" + (f" — {purpose}" if purpose else ""))
        parts.append("")

    # User journeys from business workflows
    flows = spec.get("business_workflows") or []
    if flows:
        parts.append("## User Journeys\n")
        for w in flows:
            if not isinstance(w, dict):
                continue
            name = w.get("workflow_name") or w.get("name") or ""
            who = w.get("who") or ""
            steps = [" ".join(str(s).split()) for s in (w.get("steps") or []) if str(s).strip()]
            if name and steps:
                parts.append(f"### {name}" + (f" ({who})" if who else ""))
                for i, step in enumerate(steps, 1):
                    parts.append(f"{i}. {step}")
                parts.append("")

    # Auth flow for the prototype
    auth = spec.get("authentication_requirement") or {}
    if auth.get("login_required"):
        parts.append("## Auth Flow\n")
        parts.append(f"- Sign-in page at `{auth.get('sign_in_route', '/login')}`")
        if auth.get("sign_up_route"):
            parts.append(f"- Sign-up page at `{auth['sign_up_route']}`")
        id_fields = auth.get("identity_fields") or []
        if id_fields:
            parts.append(f"- Login form fields: {', '.join(id_fields)}")
        reg_fields = auth.get("registration_fields") or []
        if reg_fields:
            parts.append(f"- Registration form fields: {', '.join(reg_fields)}")
        parts.append("")

    # Validation rules for forms
    val_text = _validation_section(spec)
    if val_text:
        parts.append(val_text)

    return "\n\n".join(s for s in parts if s.strip()) + "\n"


def _build_builder_md(spec, selected) -> str:
    """Complete technical contract for the developer/QA agent."""
    parts = [
        f"# Developer and QA Handoff\n",
        f"**Selected stack**: {selected.tech}. **Language**: {selected.language}.\n",
        "Read app.md and sitemap.md, then the generated files in .agentforge/prototype/. "
        "Build the application in the selected stack from that specification and the user's latest prototype. "
        "Preserve its screens, navigation, layout, content and interactions while connecting the real data and integrations. "
        "The planning and SRS reviews have already happened; proceed with implementation without generating another product plan. "
        "Use environment variables for configured credentials and this project's assigned runtime ports. "
        "Implement the specified access rules, validation and error handling. Verify the behavior changed with appropriate unit, integration and browser checks, "
        "repair actionable failures, and stop with a clear explanation if the same failure repeats without progress. "
        "Keep tests and their results with this application and report verification limitations accurately.\n",
    ]

    # Include the authoritative builder_handoff contract if available
    handoff = spec.get("builder_handoff")
    if isinstance(handoff, dict):
        prompt = handoff.get("prompt")
        if prompt and isinstance(prompt, str):
            parts.append("## Authoritative Build Contract\n")
            parts.append(prompt.strip())
            parts.append("")

        # Include invariants if the prompt is missing or as a supplement
        invariants = handoff.get("invariants") or []
        if invariants:
            parts.append("## Build Invariants\n")
            for inv in invariants:
                if isinstance(inv, str):
                    parts.append(f"- {inv}")
                elif isinstance(inv, dict):
                    text = inv.get("rule") or inv.get("text") or inv.get("description") or ""
                    if text:
                        parts.append(f"- {text}")
            parts.append("")

    # MongoDB ObjectId handling — critical rule that prevents silent query bugs
    parts.append("## Critical: MongoDB ObjectId Handling\n")
    parts.append(
        "For Mongo ObjectId/reference fields, URL/form/session IDs arrive as strings. "
        "Always validate and convert with `new ObjectId(id)` before querying, and serialize "
        "ObjectIds to strings (`doc.field?.toString()`) at browser boundaries. "
        "The `doc.ownerId?.toString() === user.id` pattern is required — comparing an ObjectId "
        "to a string directly returns false silently and finds nothing.\n")

    # Database schema
    db_text = _database_section(spec)
    if db_text:
        parts.append(db_text)

    # API contracts
    api_text = _api_section(spec)
    if api_text:
        parts.append(api_text)

    # Auth config
    auth_text = _auth_section(spec)
    if auth_text:
        parts.append(auth_text)

    # Access matrix
    access_text = _access_matrix_section(spec)
    if access_text:
        parts.append(access_text)

    # Validation rules
    val_text = _validation_section(spec)
    if val_text:
        parts.append(val_text)

    return "\n\n".join(s for s in parts if s.strip()) + "\n"


# ── public entry point ───────────────────────────────────────────────────

def write_handoff(target: Path, srs: dict, stack: str = "", *, refresh=False) -> Path:
    """Write the four agent handoff markdown files from the approved SRS.

    Each file is structured with compact, agent-readable sections instead of a
    raw recursive dump — the agents are sandboxed and cannot read the SRS JSON
    directly, so every field they need must be in these files.
    """
    target = Path(target)
    spec = srs.get("srs_document") or srs

    tech = {
        "nextjs-mongo": "Next.js (App Router) + React + MongoDB/Mongoose",
        "mern-microservices": "React (Vite) + Express microservices + MongoDB/Mongoose + API gateway",
    }
    selected = SimpleNamespace(
        id=stack or "nextjs-mongo",
        tech=tech.get(stack or "nextjs-mongo", stack),
        language="JavaScript (ESM)",
    )

    # Cache signature — skip rewrite if the SRS has not changed.
    sig_input = json.dumps(spec, sort_keys=True, default=str) + selected.id
    signature = hashlib.sha256(sig_input.encode()).hexdigest()
    marker = target / "manifest.json"
    if not refresh and marker.is_file():
        try:
            previous = json.loads(marker.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
        if previous.get("source") == signature and all(
            (target / name).is_file() for name in FILES
        ):
            return target

    target.mkdir(parents=True, exist_ok=True)

    contents = {
        "app.md": _build_app_md(spec),
        "sitemap.md": _build_sitemap_md(spec),
        "prototype.md": _build_prototype_md(spec),
        "builder.md": _build_builder_md(spec, selected),
    }

    for name, content in contents.items():
        from ..services.storage import write_text
        write_text(target / name, content)

    from ..services.storage import write_text
    write_text(marker, json.dumps({
        "source": signature,
        "stack": selected.id,
        "files": list(FILES),
    }))
    return target
