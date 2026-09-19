"""What one page of the specification knows about itself.

The drawing pass used to be told the page's name, its route, its functions and
a list of bare column names. That is enough to decide a page lists invoices and
not enough to decide what an invoice row looks like, so the model filled the
gap the only way it could - a heading, a box, a button - and every screen came
back the same thin shape regardless of what the specification actually said.

The prototype does not work from that. It is handed the whole approved
document: every page and its route, the schema with types and enumerations, the
requirements traced to each screen, the workflows that pass through it, the
components the customer asked for. This module gives the wireframe pass the
same material, sliced per page.

Two functions because the split matters for cost: `product_context` is the same
for every page of a run and is built once, `page_context` is the part that
differs. Eleven pages therefore pay for the document once, not eleven times.
"""
from __future__ import annotations

# Enough to draw from, not so much that the page's own facts are buried.
MAX_PAGES = 24
MAX_TABLES = 14
MAX_FIELDS = 14
MAX_REQS = 8
MAX_ENDPOINTS = 8
MAX_STEPS = 10


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _pages_of(doc: dict) -> list[dict]:
    return [p for p in ((doc.get("public_pages") or []) + (doc.get("protected_pages") or []))
            if isinstance(p, dict)]


def _field_line(field) -> str:
    """One column with the part a model cannot guess: its type and its values.

    The enumeration is the single most useful thing here. `status (one of:
    pending, confirmed, checked_in, cancelled)` gives a status column four real
    badge values to draw; `status` alone gets "Active" on every row, which is a
    table nobody can review.
    """
    if isinstance(field, str):
        return field
    if not isinstance(field, dict):
        return ""
    name = _clean(field.get("name") or field.get("column"))
    if not name:
        return ""
    flags = []
    if field.get("type"):
        flags.append(_clean(field["type"]))
    values = field.get("values") or field.get("enum")
    if values:
        flags.append("one of: " + ", ".join(_clean(v) for v in list(values)[:8]))
    reference = field.get("references") or field.get("foreign_key")
    if reference:
        flags.append(f"references {_clean(reference)}")
    if field.get("unique"):
        flags.append("unique")
    return f"{name} ({'; '.join(flags)})" if flags else name


def _table_block(table: dict) -> str:
    name = _clean(table.get("table_name") or table.get("name"))
    if not name:
        return ""
    columns = table.get("fields") or table.get("columns") or []
    lines = [line for line in (_field_line(c) for c in columns[:MAX_FIELDS]) if line]
    head = f"- {name}"
    why = _clean(table.get("description"))
    if why:
        head += f" - {why}"
    return head + ("\n    " + "\n    ".join(lines) if lines else "")


def product_context(doc: dict) -> str:
    """The document-level facts every page of this product is drawn against."""
    summary = doc.get("app_summary") or {}
    parts = [
        f"PRODUCT: {_clean(summary.get('app_name') or doc.get('project_name'))} - "
        f"{_clean(summary.get('short_description'))[:400]}"
    ]
    goal = _clean(summary.get("business_goal"))
    if goal:
        parts.append(f"BUSINESS GOAL: {goal[:300]}")
    users = [_clean(u) for u in (summary.get("target_users") or []) if _clean(u)]
    if users:
        parts.append("TARGET USERS: " + ", ".join(users[:8]))

    roles = []
    for role in (doc.get("roles") or []):
        if not isinstance(role, dict):
            continue
        name = _clean(role.get("role_name") or role.get("role_key"))
        if name:
            why = _clean(role.get("description"))
            roles.append(f"- {name}" + (f" - {why[:160]}" if why else ""))
    if roles:
        parts.append("ROLES\n" + "\n".join(roles[:10]))

    modules = [_clean(m) for m in (doc.get("main_modules") or []) if _clean(m)]
    if modules:
        parts.append("MODULES: " + ", ".join(modules[:16]))

    # Provide complete screen list so layout navigation headers link only to existing pages.
    pages = []
    for page in _pages_of(doc)[:MAX_PAGES]:
        name = _clean(page.get("page_name"))
        if not name:
            continue
        line = f"- {name}  ({_clean(page.get('route')) or '/'})"
        seen_by = [_clean(r) for r in (page.get("allowed_roles") or []) if _clean(r)]
        pages.append(line + (f"  - {', '.join(seen_by)}" if seen_by else "  - signed out"))
    if pages:
        parts.append("EVERY PAGE IN THIS PRODUCT (navigation links to these, "
                     "and to nothing else)\n" + "\n".join(pages))

    tables = [t for t in ((doc.get("database_design") or {}).get("tables") or [])
              if isinstance(t, dict)]
    blocks = [b for b in (_table_block(t) for t in tables[:MAX_TABLES]) if b]
    if blocks:
        parts.append("STORED DATA\n" + "\n".join(blocks))

    look = []
    branding = doc.get("branding")
    if isinstance(branding, dict):
        bits = [f"{k.replace('_', ' ')}: {v}" for k, v in branding.items()
                if isinstance(v, (str, int)) and v]
        if bits:
            look.append("- " + "; ".join(bits[:8]))
    ux = doc.get("ui_ux_requirements")
    if isinstance(ux, dict):
        need = [_clean(c) for c in (ux.get("required_components") or []) if _clean(c)]
        if need:
            look.append("- every screen is built from: " + ", ".join(need[:16]))
        rest = [f"{k.replace('_', ' ')}: {v}" for k, v in ux.items()
                if k != "required_components" and isinstance(v, (str, bool, int)) and v != ""]
        if rest:
            look.append("- " + "; ".join(rest[:8]))
    if look:
        parts.append("WHAT THE CUSTOMER ASKED THE PRODUCT TO LOOK LIKE\n" + "\n".join(look))

    integrations = [_clean(i.get("name")) for i in (doc.get("integration_requirements") or [])
                    if isinstance(i, dict) and _clean(i.get("name"))]
    if integrations:
        parts.append("INTEGRATIONS: " + ", ".join(integrations[:10]))

    return "\n\n".join(parts)


def _entity_for(page: dict, doc: dict) -> str:
    """The table this page is most likely about, by name overlap alone.

    Deliberately no vocabulary of its own: it matches the page's title and
    route against the table names this document declared, so it carries across
    products instead of knowing about one.
    """
    haystack = f"{_clean(page.get('page_name'))} {_clean(page.get('route'))}".lower()
    best, score = "", 0
    for table in ((doc.get("database_design") or {}).get("tables") or []):
        if not isinstance(table, dict):
            continue
        name = _clean(table.get("table_name") or table.get("name"))
        stem = name.lower().rstrip("s")
        if stem and stem in haystack and len(stem) > score:
            best, score = name, len(stem)
    return best


def _requirements_for(page_name: str, route: str, doc: dict) -> list[str]:
    """Traced through the document's own matrix, by module name if it is silent."""
    traced = set()
    for row in (doc.get("requirement_traceability_matrix") or []):
        if not isinstance(row, dict):
            continue
        named = [_clean(p).lower() for p in (row.get("pages") or [])]
        if page_name.lower() in named or route.lower() in named:
            rid = _clean(row.get("requirement_id") or row.get("id"))
            if rid:
                traced.add(rid)
    out = []
    for req in (doc.get("functional_requirements") or []):
        if not isinstance(req, dict):
            continue
        text = _clean(req.get("requirement") or req.get("description"))
        if not text:
            continue
        rid = _clean(req.get("id"))
        module = _clean(req.get("module")).lower()
        if (rid and rid in traced) or (not traced and module and module in page_name.lower()):
            out.append(f"- {rid + '  ' if rid else ''}{text}")
    return out


def _endpoints_for(route: str, entity: str, doc: dict) -> list[str]:
    stem = route.strip("/").split("/")[0].lower()
    entity_stem = entity.lower().rstrip("s") if entity else ""
    out = []
    for api in (doc.get("api_design") or []):
        if not isinstance(api, dict):
            continue
        path = _clean(api.get("path") or api.get("endpoint"))
        if not path:
            continue
        low = path.lower()
        if not ((entity_stem and entity_stem in low) or (stem and stem in low)):
            continue
        why = _clean(api.get("description"))
        line = f"- {_clean(api.get('method') or 'GET').upper()} {path}"
        out.append(line + (f" - {why}" if why else ""))
    return out


def page_context(page: dict, doc: dict) -> str:
    """This page's own slice of the specification."""
    route = _clean(page.get("route")) or "/"
    name = _clean(page.get("page_name")) or route
    # Check both allowed_roles and frame role definitions when determining audience.
    seen_by = [_clean(r) for r in (page.get("allowed_roles") or page.get("roles") or [])
               if _clean(r)]

    parts = [f"THE PAGE TO DRAW: {name} at {route}",
             f"Seen by: {', '.join(seen_by) if seen_by else 'anyone, signed out'}"]

    # The specification's own section list for this page. It is the page's
    # outline, written by the document, and it was being thrown away.
    sections = [_clean(s) for s in (page.get("sections") or []) if _clean(s)]
    if sections:
        parts.append("SECTIONS THIS PAGE IS MADE OF, in this order\n"
                     + "\n".join(f"- {s}" for s in sections))

    functions = [_clean(f) for f in (page.get("functions") or []) if _clean(f)]
    parts.append("WHAT SOMEONE MUST BE ABLE TO DO HERE\n"
                 + "\n".join(f"- {f}" for f in (functions or ["use the product"])))

    entity = _entity_for(page, doc)
    if entity:
        parts.append(f"THIS PAGE IS MOSTLY ABOUT: {entity}. Draw its rows and "
                     "fields from the columns listed above, using their types "
                     "and their listed values for the sample data.")

    requirements = _requirements_for(name, route, doc)
    if requirements:
        parts.append("REQUIREMENTS THIS PAGE ANSWERS\n" + "\n".join(requirements[:MAX_REQS]))

    endpoints = _endpoints_for(route, entity, doc)
    if endpoints:
        parts.append("WHAT THIS PAGE CALLS (every action drawn here should map "
                     "to one of these)\n" + "\n".join(endpoints[:MAX_ENDPOINTS]))

    flows = []
    for flow in (doc.get("business_workflows") or []):
        if not isinstance(flow, dict):
            continue
        title = _clean(flow.get("workflow_name"))
        steps = [_clean(s) for s in (flow.get("steps") or []) if _clean(s)]
        if not (title and steps):
            continue
        blob = " ".join(steps).lower()
        if name.lower() in blob or (entity and entity.lower().rstrip("s") in blob):
            flows.append(f"- {title}: " + " -> ".join(steps[:MAX_STEPS]))
    if flows:
        parts.append("WORKFLOWS THAT PASS THROUGH THIS PAGE\n" + "\n".join(flows[:3]))

    # Filter page business rules by matching tables explicitly referenced in each requirement.
    if entity:
        stem = entity.lower().rstrip("s")
        rules = []
        for rule in (doc.get("validation_rules") or []):
            if not isinstance(rule, dict):
                continue
            field, text = _clean(rule.get("field")), _clean(rule.get("rule"))
            if not (field and text) or stem not in field.lower():
                continue
            rules.append(f"- {field.split('.')[-1]}: {text}")
        if rules:
            parts.append("INPUT RULES for this page's data (show them as helper "
                         "text under the fields)\n" + "\n".join(rules[:8]))

    for row in (doc.get("role_access_matrix") or []):
        if not isinstance(row, dict):
            continue
        who = _clean(row.get("role") or row.get("role_name"))
        if who and who in seen_by:
            allowed = [_clean(f) for f in (row.get("allowed_functions") or []) if _clean(f)]
            if allowed:
                parts.append(f"{who} may: " + ", ".join(allowed[:12]))
            break

    return "\n\n".join(parts)
