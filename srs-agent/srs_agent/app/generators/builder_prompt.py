"""Render the SRS as a natural, builder-ready implementation handoff."""
from __future__ import annotations

from collections import defaultdict

from .builder_constants import MAX_CHARS, MAX_WORDS
from .builder_utils import _clean


def _items(values) -> list[str]:
    out = []
    for value in values or []:
        text = _clean(value.get("text") if isinstance(value, dict) else value)
        if text and text not in out:
            out.append(text.rstrip("."))
    return out


def _section(lines: list[str], title: str, body: list[str]) -> None:
    body = [x for x in body if x]
    if body:
        lines += [f"## {title}", "", *body, ""]


def _bullets(values) -> list[str]:
    return [f"* {x}." for x in _items(values)]


def _role_sections(handoff: dict) -> list[str]:
    lines = []
    access = {str(x.get("role") or "").casefold(): x for x in handoff.get("access") or []}
    caps = handoff.get("feature_contracts") or []
    for role in handoff.get("roles") or []:
        name = _clean(role.get("name") or role.get("key"))
        if not name:
            continue
        actions = _items((access.get(name.casefold()) or {}).get("allowed_functions"))
        if not actions:
            for cap in caps:
                if name.casefold() in {str(r).casefold() for r in cap.get("roles") or []}:
                    req = _clean(cap.get("requirement"))
                    if req and req not in actions:
                        actions.append(req)
        lines += [f"### {name}", "", f"A {name.lower()} can:", "", *_bullets(actions or [role.get("description")]), ""]
    return lines


def _feature_sections(handoff: dict) -> list[str]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    reserved = ("auth", "seed", "quality", "security", "business rule")
    for cap in handoff.get("feature_contracts") or []:
        title = _clean(cap.get("module") or "Core Features")
        if any(word in title.lower() for word in reserved):
            continue
        grouped[title].append(cap)
    lines = []
    for title, caps in grouped.items():
        body, routes = [], []
        for cap in caps:
            for route in cap.get("routes") or []:
                if route not in routes:
                    routes.append(route)
            req = _clean(cap.get("requirement"))
            if req and req not in body:
                body.append(req.rstrip("."))
        chunk = []
        if routes:
            chunk.append("Create " + ", ".join(f"`{r}`" for r in routes) + ".")
            chunk.append("")
        chunk += _bullets(body)
        if chunk:
            _section(lines, title, chunk)
    return lines


def _auth_section(handoff: dict) -> list[str]:
    auth = handoff.get("auth_contract") or {}
    if not auth.get("enabled"):
        return []
    body = []
    if auth.get("sign_in_route"):
        body.append(f"Create `{auth['sign_in_route']}` for sign in using " + ", ".join(auth.get("identity_fields") or ["email", "password"]) + ".")
    if auth.get("self_registration"):
        body.append(f"Create `{auth.get('sign_up_route')}` for public registration.")
        roles = ", ".join(auth.get("registration_roles") or [])
        body.append(f"Public registration may create only {roles or 'the approved default'} accounts; assign the role on the server and never expose a privileged role picker.")
    else:
        body.append("Do not invent public registration; use the approved account-provisioning flow.")
    for cap in handoff.get("feature_contracts") or []:
        if "auth" in _clean(cap.get("module")).lower():
            req = _clean(cap.get("requirement"))
            if req and req not in body:
                body.append(req.rstrip(".") + ".")
    for role in auth.get("roles") or []:
        who = _clean(role.get("role"))
        allowed = [str(x) for x in role.get("allowed_routes") or [] if x]
        if who and allowed:
            body.append(f"{who} may access " + ", ".join(f"`{r}`" for r in allowed) + "; other protected routes are forbidden.")
    body += [
        "Authorization must be enforced server-side before protected data is read or written.",
        "Signed-out users opening protected pages must be redirected to sign in; signed-in users with the wrong role must be refused.",
        "Use the session user record as the role source; never trust role values supplied by the browser.",
    ]
    return ["## Authentication", "", *body, ""]


def _models_section(handoff: dict) -> list[str]:
    lines = ["## Main Data Models", "", "Create connected database models for:", ""]
    for model in handoff.get("models") or []:
        name = _clean(model.get("name") or model.get("table"))
        if not name:
            continue
        lines += [f"### {name}", ""]
        for field in model.get("field_specs") or []:
            fname = _clean(field.get("name"))
            if not fname:
                continue
            ref = _clean(field.get("references"))
            flags = []
            if ref:
                flags.append(f"→ {ref}")
            if field.get("required") is True:
                flags.append("required")
            if field.get("unique"):
                flags.append("unique")
            if field.get("enum"):
                flags.append("one of: " + ", ".join(str(x) for x in field["enum"]))
            lines.append(f"* `{fname}`" + (" — " + "; ".join(flags) if flags else ""))
        lines.append("")
    return lines if len(lines) > 4 else []


def _relationships_section(handoff: dict) -> list[str]:
    body = []
    for rel in handoff.get("relationships") or []:
        left, right = _clean(rel.get("from")), _clean(rel.get("to"))
        if left and right:
            text = f"{left} → {right}"
            if rel.get("type"):
                text += f" = {rel['type']}"
            if rel.get("via"):
                text += f" via `{rel['via']}`"
            body.append(text)
    if body:
        body += ["Every relationship visible in the UI must resolve to human-readable values; never expose raw database ids where a user-facing name exists."]
    return ["## Required Relationships", "", *_bullets(body), ""] if body else []


def _routes_section(handoff: dict) -> list[str]:
    groups: dict[str, list[str]] = defaultdict(list)
    for page in handoff.get("pages") or []:
        route = _clean(page.get("route"))
        if not route:
            continue
        if page.get("public"):
            groups["Public"].append(route)
        elif page.get("allowed_roles"):
            groups[" / ".join(page["allowed_roles"])].append(route)
        else:
            groups["Signed-in"].append(route)
    if not groups:
        return []
    lines = ["## Required Routes", ""]
    for label, routes in groups.items():
        lines += [f"{label}:", "", *[f"* `{r}`" for r in routes], ""]
    lines += [
        "Every route above must have a real working page. No required route may return 404. Every navigation link and CTA must point to implemented behavior, and dynamic routes must work with real persisted data.", ""
    ]
    return lines


def _journeys_section(handoff: dict) -> list[str]:
    lines = ["## Required End-to-End Journeys", ""]
    count = 0
    for flow in handoff.get("workflows") or []:
        name = _clean(flow.get("name") or "Journey")
        routes = [str(x) for x in flow.get("routes") or [] if x]
        steps = _items(flow.get("steps"))
        if not routes and not steps:
            continue
        count += 1
        lines += [f"### {name}", ""]
        if routes:
            lines += ["`" + " → ".join(routes) + "`", ""]
        lines += _bullets(steps)
        lines.append("")
    if count:
        lines += ["Every journey must be walkable end to end using real controls and persisted data; a page that exists without a working action does not complete the journey.", ""]
        return lines
    return []



def _server_sections(handoff: dict) -> list[str]:
    lines = []
    apis = []
    for ep in handoff.get("apis") or []:
        method, path = _clean(ep.get("method")), _clean(ep.get("path"))
        if method and path:
            desc = _clean(ep.get("description"))
            apis.append(f"`{method} {path}`" + (f" — {desc}" if desc else ""))
    if apis:
        _section(lines, "Required Server / API Behavior", _bullets(apis))
    for title, key, name_key in (("Integrations", "integration_requirements", "name"),
                                  ("Notifications", "notification_rules", "event"),
                                  ("Reporting Requirements", "reporting_requirements", "report_name")):
        values = []
        for item in handoff.get(key) or []:
            if not isinstance(item, dict):
                continue
            name = _clean(item.get(name_key) or item.get("name"))
            desc = _clean(item.get("description"))
            if name:
                values.append(name + (f" — {desc}" if desc else ""))
        if values:
            _section(lines, title, _bullets(values))
    return lines

def _quality_section(handoff: dict, doc: dict) -> list[str]:
    body = []
    for item in handoff.get("non_functional_requirements") or []:
        body.append(_clean(item.get("requirement") or item.get("description")) if isinstance(item, dict) else _clean(item))
    body += _items(doc.get("security_requirements"))
    body += _items(handoff.get("constraints"))
    for cap in handoff.get("feature_contracts") or []:
        if any(word in _clean(cap.get("module")).lower() for word in ("quality", "security")):
            req = _clean(cap.get("requirement"))
            if req:
                body.append(req)
    body = [x for i, x in enumerate(body) if x and x not in body[:i]]
    body += [
        "Every required route, navigation link and CTA must work without blocking runtime errors.",
        "Every mutation must persist and the next visible state must prove the change.",
        "Do not replace difficult requirements with TODO pages, decorative buttons, fake forms or hard-coded success states.",
        "Before completion, verify the app can be used from start to finish with the required roles, seeded data and relationships.",
    ]
    return ["## Quality Requirements", "", *_bullets(body), ""]


def render_prompt(handoff: dict, plan: dict, *, auth: bool = False,
                  srs_document: dict | None = None) -> str:
    """Render a proportional SRS handoff in the same shape as a strong product brief."""
    plan, doc = plan or {}, srs_document or {}
    name = _clean(handoff.get("app_name") or plan.get("app_name") or "the application")
    kind = _clean(handoff.get("appType") or "web application").lower()
    intent = _clean(handoff.get("product_intent") or plan.get("product_intent"))
    look = _clean(plan.get("look_and_feel"))

    lines = [f"Build a complete production-quality {kind} called **{name}**.", ""]
    if intent:
        lines += [intent.rstrip(".") + ".", ""]
    if look:
        lines += [look.rstrip(".") + ".", ""]

    roles = _role_sections(handoff)
    if roles:
        lines += ["## Main User Roles", "", *roles]
    lines += _feature_sections(handoff)
    lines += _auth_section(handoff)
    lines += _models_section(handoff)
    lines += _relationships_section(handoff)
    lines += _routes_section(handoff)
    lines += _server_sections(handoff)

    rules = []
    for rule in handoff.get("validation_rules") or []:
        if isinstance(rule, dict):
            text = _clean(rule.get("rule"))
            if text:
                rules.append(((_clean(rule.get("field")) + ": ") if rule.get("field") else "") + text)
        elif _clean(rule):
            rules.append(_clean(rule))
    for cap in handoff.get("feature_contracts") or []:
        if "business rule" in _clean(cap.get("module")).lower():
            text = _clean(cap.get("requirement"))
            if text and text not in rules:
                rules.append(text.rstrip("."))
    rules += _items(handoff.get("assumptions"))
    rules += _items(handoff.get("invariants"))
    if rules:
        _section(lines, "Important Business Rules", [f"{i}. {r}." for i, r in enumerate(rules, 1)])

    seed_rules = [r.get("text") for r in handoff.get("requirements") or []
                  if isinstance(r, dict) and ("seed" in _clean(r.get("module")).lower()
                  or any(k in _clean(r.get("text")).lower() for k in ("seed", "demo data", "sample data")))]
    if handoff.get("models") or handoff.get("auth_contract", {}).get("enabled") or any("[" in str(p.get("route")) for p in handoff.get("pages") or []):
        seed_rules += [
            "Provide realistic, idempotent demo data sufficient to open every dynamic route and complete every required journey",
            "When authentication is enabled, provision demo identities through the application's approved authentication system rather than fake seed-route authentication logic",
        ]
        _section(lines, "Seed Data", _bullets(seed_rules))

    lines += _journeys_section(handoff)
    lines += _quality_section(handoff, doc)

    acceptance = [_clean(x.get("criterion")) for x in handoff.get("acceptance_criteria") or [] if isinstance(x, dict) and _clean(x.get("criterion"))]
    if acceptance:
        _section(lines, "Before Declaring the Application Complete", _bullets(acceptance))

    compact = []
    for line in lines:
        if line == "" and compact and compact[-1] == "":
            continue
        compact.append(line)
    return _cap("\n".join(compact).strip() + "\n")


def _cap(text: str) -> str:
    if not MAX_WORDS and not MAX_CHARS:
        return text.rstrip() + "\n"
    kept, words, chars = [], 0, 0
    for line in text.split("\n"):
        count = len(line.split())
        if MAX_WORDS and words + count > MAX_WORDS:
            break
        if MAX_CHARS and chars + len(line) + 1 > MAX_CHARS:
            break
        kept.append(line); words += count; chars += len(line) + 1
    return "\n".join(kept).rstrip() + "\n"
