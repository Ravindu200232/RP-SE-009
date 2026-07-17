"""agents/design/planner.py — human-like product design planner (P4).

The old planner is style-first: every app got the same sidebar + KPI cards + table. This one starts from
the product — domain, roles, the job each page does — and assigns every page a DOMAIN-APPROPRIATE
ARCHETYPE (kanban, pos, receipt, table-crud, dashboard, form, workflow, detail, landing) derived from the
declared component *types* + page kind + functions. A kitchen display becomes a kanban board, a cashier
bill becomes a receipt/POS layout, an admin list becomes a table — instead of one layout everywhere.

Deterministic (no LLM). Produces `design-brief.json` + `page-contracts.json`, and per-page design intent
the generation agents build to.
"""
from __future__ import annotations

# What each archetype MEANS — injected into the page-body prompt so gemma builds the right thing.
ARCHETYPE_PATTERNS = {
    "kanban": ("A column BOARD — one column per workflow status (e.g. Queued / Preparing / Ready). Each "
               "card shows the record (order/table/elapsed time/items) and status-action buttons that move "
               "it to the next column. This is NOT a table."),
    "pos": ("A two-pane point-of-sale: LEFT = searchable item grid grouped by category; RIGHT = a live "
            "cart (line items with qty +/- and notes) showing a running subtotal/total and a primary "
            "'Send to kitchen' / 'Checkout' button."),
    "receipt": ("A receipt / bill summary: itemized lines, then subtotal / discount / tax / grand total / "
                "balance, and the primary payment action. Totals right-aligned and prominent."),
    "table-crud": ("A data TABLE of the first ~5 fields with a prominent 'New' button opening a modal form; "
                   "each row has Edit + Delete. The default staff management pattern."),
    "dashboard": ("A row of KPI stat cards (real numbers from `/api/reports?type=summary`) then quick-nav "
                  "cards to the role's key pages. No fake charts — show real counts or a simple bar from data."),
    "form": ("A focused FORM grouped into the declared sections: labeled inputs, a clear primary submit, "
             "inline validation + server errors. Not a table or dashboard."),
    "workflow": ("A status-driven work QUEUE: filter by status; each item shows its current state and only "
                 "the allowed next-transition actions."),
    "detail": "A record header + grouped field sections + a Back link. Read-only; do not re-fetch.",
    "landing": ("A public marketing page: sticky nav (brand + Login / Sign up), a hero, then >=4 distinct "
                "sections with real domain copy, ending in a footer."),
}

_ACTION_VERBS = ("send", "checkout", "check out", "record payment", "record", "create", "add", "save",
                 "submit", "receive", "seat", "mark", "complete", "generate", "export")


def _contracts_by_name(spec: dict) -> dict:
    return {c.get("name"): c for c in (spec.get("component_contracts") or [])}


def _section_labels(page: dict) -> list[str]:
    """Section names for a page. A section is either {'section_name', 'components'} (role-wise SRS) or a
    plain string label (single-page/AutoHub specs) — SectionAgent accepts both, so this must too."""
    labels = []
    for s in (page.get("sections") or []):
        name = s.get("section_name") if isinstance(s, dict) else s
        if name and str(name).strip():
            labels.append(str(name))
    return labels


def _page_types(page: dict, by_name: dict) -> set[str]:
    """The resolved component TYPES on this page (declared or classified in the contract)."""
    types: set[str] = set()
    for sec in (page.get("sections") or []):
        if not isinstance(sec, dict):
            continue          # a plain-string label (single-page/AutoHub specs) declares no components
        for cn in (sec.get("components") or []):
            c = by_name.get(cn)
            if c and c.get("type"):
                types.add(str(c["type"]).lower())
    return types


def page_archetype(page: dict, by_name: dict) -> str:
    """Pick a domain-appropriate archetype from resolved component types, page kind, route and functions.
    A page that has BOTH a data table and a form is a table-crud (the form is the row/New modal)."""
    types = _page_types(page, by_name)
    route = str(page.get("path") or "").lower()
    kind = str(page.get("kind") or "")
    if "kanban" in types:
        return "kanban"
    if "interactive_order_form" in types or "pos" in route or kind == "pos":
        return "pos"
    if "financial_summary" in types or "billing" in route or ("summary" in types and "payment" in route):
        return "receipt"
    if kind == "landing":
        return "landing"
    if kind == "dashboard":
        return "dashboard"
    if kind == "detail":
        return "detail"
    if "data_table" in types or kind in ("table-crud", "admin", "list", "manage-users"):
        return "table-crud"                 # table is primary; any form is the New/Edit modal
    if kind == "form" or route.endswith(("/create", "/new", "/edit")) or "form" in types:
        return "form"
    if "workflow_card" in types or kind == "workflow":
        return "workflow"
    return kind if kind in ARCHETYPE_PATTERNS else "table-crud"


def _primary_action(page: dict) -> str:
    for fn in (page.get("functions") or []):
        low = str(fn).lower()
        if any(v in low for v in _ACTION_VERBS):
            return str(fn)
    fns = page.get("functions") or []
    return str(fns[0]) if fns else ""


def design_brief(spec: dict) -> dict:
    """The app's visual identity. Read from the fields the refiner actually emits (title/site_type/
    description/style/theme) — it used to look only at `spec['app']`/`spec['design_brief']`, which the
    refiner never produces, so every app got the same generic brief."""
    app = spec.get("app") or {}
    brief = spec.get("design_brief") or {}
    domain = (brief.get("domain") or app.get("app_type") or spec.get("site_type")
              or "Business web application")
    text = " ".join(str(x) for x in (
        domain, app.get("summary", ""), spec.get("title", ""), spec.get("description", ""),
        " ".join(str(f) for f in (spec.get("key_features") or [])),
    )).lower()
    # density: transaction/POS/kitchen apps are dense & fast; content/landing apps are airy.
    dense = any(k in text for k in ("pos", "kitchen", "inventory", "trading", "dashboard", "admin",
                                    "logistics", "warehouse"))
    return {
        "domain": domain,
        "personality": brief.get("personality") or spec.get("style") or "polished and confident",
        "navStyle": "role-sidebar",           # staff apps: a per-role sidebar workspace
        "density": "compact" if dense else "comfortable",
        "radius": brief.get("radius", "large"),
        "seed": brief.get("seed"),
    }


def page_contracts(spec: dict) -> list[dict]:
    by_name = _contracts_by_name(spec)
    out: list[dict] = []
    for p in (spec.get("pages") or []):
        arch = page_archetype(p, by_name)
        out.append({
            "path": p.get("path"),
            "role": p.get("owner_role"),
            "title": p.get("title"),
            "archetype": arch,
            "pattern": ARCHETYPE_PATTERNS.get(arch, ""),
            "userJob": p.get("title") or p.get("path"),
            "primaryAction": _primary_action(p),
            "sections": _section_labels(p),
            "functions": [str(f) for f in (p.get("functions") or [])],
        })
    return out


def plan(spec: dict) -> dict:
    """The design plan: brief + per-page contracts (with archetypes). Keyed by path for lookup."""
    contracts = page_contracts(spec)
    return {
        "brief": design_brief(spec),
        "pages": contracts,
        "by_path": {c["path"]: c for c in contracts},
    }
