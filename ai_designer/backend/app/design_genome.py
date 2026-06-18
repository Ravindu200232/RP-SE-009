"""App Understanding Layer (Part A) + Design Genome (Part B).

Works for ANY prompt - not a fixed hospital/hotel/POS list. `infer_app_understanding`
classifies the prompt into a category + domain via keyword inference (falling back to
"custom" and inferring from the prompt). `make_genome` then produces a SEEDED, anti-
similarity-scored structural genome so the same prompt generated twice yields a
STRUCTURALLY different app (different layout family, navigation, dashboard, CRUD style,
section order) - not just different colours/content. The genome is stored in project
metadata so future generations can avoid repeating recent structures.
"""
import json
import os
import random

# ---- Part B option spaces (the structural axes) ----
LAYOUT_FAMILIES = ["portal-first", "dashboard-first", "marketing-first", "admin-first",
                   "workflow-first", "marketplace", "content-first", "mobile-first", "command-center"]
NAV_PATTERNS = ["topnav", "sidebar", "split-nav", "tabs", "command-palette", "stepper", "mobile-bottom-nav"]
PAGE_STRATEGIES = ["landing-heavy", "dashboard-heavy", "workflow-heavy", "data-heavy", "content-heavy", "booking-heavy"]
DASHBOARD_STYLES = ["kpi-cards", "table-first", "kanban", "calendar", "analytics", "activity-feed", "split-pane", "map-based"]
CRUD_STYLES = ["table-dense", "card-grid", "split-pane", "wizard", "kanban", "timeline", "calendar"]
SECTION_STRATEGIES = ["storytelling", "conversion", "operations", "directory", "analytics", "community", "productized-service"]
VISUAL_STYLES = ["clean", "bold", "premium-dark", "glass", "editorial", "playful", "enterprise", "minimal", "dense-admin"]
DENSITIES = ["compact", "balanced", "spacious"]
INTERACTION_STYLES = ["modal-heavy", "inline-edit", "wizard-flow", "bulk-actions", "command-actions"]

_AXES = ["layout_family", "navigation_pattern", "page_strategy", "dashboard_style",
         "crud_style", "section_strategy", "visual_style", "density", "interaction_style"]
_SIG_AXES = ["layout_family", "navigation_pattern", "page_strategy", "dashboard_style", "crud_style", "section_strategy"]

# category -> per-axis PREFERENCES (bias only; never the sole option, so apps still vary)
_BIAS = {
    "booking":     {"page_strategy": ["booking-heavy"], "dashboard_style": ["calendar"], "crud_style": ["calendar", "timeline"]},
    "marketplace": {"layout_family": ["marketplace"], "crud_style": ["card-grid"], "section_strategy": ["directory"], "page_strategy": ["content-heavy"]},
    "education":   {"page_strategy": ["workflow-heavy"], "dashboard_style": ["activity-feed", "kpi-cards"], "crud_style": ["card-grid", "timeline"]},
    "healthcare":  {"layout_family": ["portal-first", "workflow-first"], "dashboard_style": ["activity-feed", "kpi-cards"], "crud_style": ["split-pane", "table-dense"]},
    "finance":     {"page_strategy": ["data-heavy"], "dashboard_style": ["analytics", "kpi-cards"], "crud_style": ["table-dense"], "visual_style": ["enterprise", "premium-dark"]},
    "inventory":   {"page_strategy": ["data-heavy"], "dashboard_style": ["table-first", "kpi-cards"], "crud_style": ["table-dense", "split-pane"], "density": ["compact"]},
    "content":     {"layout_family": ["content-first"], "page_strategy": ["content-heavy"], "section_strategy": ["storytelling"], "visual_style": ["editorial"]},
    "social":      {"layout_family": ["mobile-first"], "dashboard_style": ["activity-feed"], "section_strategy": ["community"], "interaction_style": ["inline-edit"]},
    "internal_tool": {"layout_family": ["admin-first", "command-center"], "navigation_pattern": ["sidebar", "command-palette"], "dashboard_style": ["table-first", "split-pane"], "visual_style": ["dense-admin", "enterprise"], "density": ["compact"]},
    "business":    {"layout_family": ["marketing-first", "dashboard-first"], "section_strategy": ["conversion", "productized-service"]},
}

_CATEGORY_KEYWORDS = {
    "booking": ["book", "reservation", "appointment", "schedule", "availability", "rental", "salon", "hotel", "table", "slot"],
    "marketplace": ["marketplace", "seller", "buyer", "listing", "vendor", "ecommerce", "classified", "auction", "storefront"],
    "education": ["course", "student", "teacher", "school", "lms", "exam", "assignment", "lesson", "tutor", "learning"],
    "healthcare": ["patient", "hospital", "clinic", "medical", "doctor", "pharmacy", "lab", "health record", "telehealth"],
    "finance": ["bank", "loan", "payment", "invoice", "budget", "accounting", "wallet", "trading", "fintech", "microloan"],
    "inventory": ["inventory", "stock", "warehouse", "supplier", "sku", "procurement", "logistics", "fulfilment", "shipment"],
    "content": ["blog", "cms", "article", "news", "magazine", "publishing", "portfolio", "newsletter"],
    "social": ["social", "community", "feed", "forum", "network", "follow", "messaging", "chat app"],
    "internal_tool": ["internal", "admin panel", "crm", "erp", "back office", "ops dashboard", "staff portal", "ticketing"],
    "business": ["business", "agency", "saas", "b2b", "platform", "service company", "startup"],
}


def infer_app_understanding(prompt: str) -> dict:
    """Classify ANY prompt -> the App Understanding schema (Part A). Deterministic
    keyword inference with a 'custom' fallback that still infers a domain from the text."""
    p = " " + (prompt or "").lower() + " "
    category = next((c for c, kws in _CATEGORY_KEYWORDS.items() if any(k in p for k in kws)), "custom")
    words = [w for w in __import__("re").findall(r"[a-z]{3,}", p)
             if w not in ("the", "and", "for", "with", "app", "application", "build", "create", "make", "that", "this", "want")]
    domain = " ".join(words[:4]) if category == "custom" else category
    internal = any(k in p for k in ("internal", "admin", "staff", "back office", "ops", "employee", "dashboard only"))
    public = any(k in p for k in ("public", "marketing", "landing", "customers", "marketplace", "storefront", "website"))
    pvp = "internal" if internal and not public else ("public" if public and not internal else "hybrid")
    complexity = "advanced" if len(p) > 240 or p.count(",") >= 5 else ("simple" if len(p) < 60 else "medium")
    return {
        "app_category": category,
        "domain": domain.strip() or "custom",
        "primary_users": [], "user_roles": [], "core_workflows": [], "main_entities": [],
        "data_relationships": [], "required_pages": [], "dashboard_needs": [],
        "public_vs_private": pvp,
        "app_complexity": complexity,
        "business_goal": "", "design_tone": "", "unique_angle": "",
    }


def _pick(rng, axis, options, category):
    pref = _BIAS.get(category, {}).get(axis)
    if pref and rng.random() < 0.6:
        return rng.choice(pref)
    return rng.choice(options)


def _roll(rng, category) -> dict:
    return {
        "layout_family": _pick(rng, "layout_family", LAYOUT_FAMILIES, category),
        "navigation_pattern": _pick(rng, "navigation_pattern", NAV_PATTERNS, category),
        "page_strategy": _pick(rng, "page_strategy", PAGE_STRATEGIES, category),
        "dashboard_style": _pick(rng, "dashboard_style", DASHBOARD_STYLES, category),
        "crud_style": _pick(rng, "crud_style", CRUD_STYLES, category),
        "section_strategy": _pick(rng, "section_strategy", SECTION_STRATEGIES, category),
        "visual_style": _pick(rng, "visual_style", VISUAL_STYLES, category),
        "density": _pick(rng, "density", DENSITIES, category),
        "interaction_style": _pick(rng, "interaction_style", INTERACTION_STYLES, category),
    }


def genome_signature(genome: dict) -> str:
    return "|".join(str(genome.get(a, "")) for a in _SIG_AXES)


def _sig_tuple(genome):
    return tuple(genome.get(a, "") for a in _SIG_AXES)


def make_genome(prompt: str, history=None, rng=None) -> dict:
    """Produce a Design Genome that is category-appropriate yet STRUCTURALLY distinct
    from `history` (a list of prior genomes). Uses fresh entropy each call, so the SAME
    prompt twice yields different genomes; anti-similarity picks the candidate that shares
    the FEWEST structural axes with any recent genome."""
    rng = rng or random.Random()                      # fresh OS entropy -> same prompt varies
    und = infer_app_understanding(prompt)
    cat = und["app_category"]
    hist_sigs = [_sig_tuple(h) for h in (history or [])]
    best, best_score = None, 99
    for _ in range(28):
        g = _roll(rng, cat)
        s = _sig_tuple(g)
        score = max((sum(1 for a, b in zip(s, hs) if a == b) for hs in hist_sigs), default=0)
        if score < best_score:
            best, best_score = g, score
        if best_score == 0:
            break
    best["app_seed"] = "%08x" % rng.getrandbits(32)
    best["app_category"] = cat
    best["domain"] = und["domain"]
    return best


GENOME_FILE = "_design_genome.json"
HISTORY_FILE = "_genome_history.json"


def _hist_path(base_dir):
    return os.path.join(base_dir, HISTORY_FILE)


def load_history(base_dir: str, limit: int = 12) -> list:
    try:
        with open(_hist_path(base_dir), encoding="utf-8") as f:
            return json.load(f)[-limit:]
    except (OSError, ValueError):
        return []


def write_genome(out_dir: str, prompt: str, base_dir: str = "output", genome: dict = None) -> dict:
    """Persist a genome (made fresh if not supplied) that avoids recent structures, and
    append it to the shared history. Pass `genome` to persist the SAME genome that already
    drove this build (graph.py makes it early so it can shape the actual code, then stores it)."""
    history = load_history(base_dir)
    if genome is None:
        genome = make_genome(prompt, history=history)
    try:
        with open(os.path.join(out_dir, GENOME_FILE), "w", encoding="utf-8") as f:
            json.dump(genome, f, indent=2)
        history.append(genome)
        with open(_hist_path(base_dir), "w", encoding="utf-8") as f:
            json.dump(history[-24:], f, indent=2)
    except OSError:
        pass
    return genome


# ======================================================================
# GENOME -> BUILD MAPPING (Part 1): translate the abstract genome axes into the
# CONCRETE scaffold knobs that change real generated code. Every returned value
# is one the scaffold already supports (so `next build` stays green): site.styles
# (nav/dash/dashLayout/list/appNav) + per-entity crud_layout + marketing section
# order. This is what makes layout_family / navigation_pattern / dashboard_style /
# crud_style / section_strategy produce STRUCTURALLY different apps - not metadata.
# ======================================================================

# scaffold-supported values (mirror next_scaffold exactly - do NOT emit anything else)
NAV_PRESETS = ["solid", "blur", "pill", "dark", "minimal", "accent-top", "underline", "accent-solid", "floating", "tinted"]
DASH_PRESETS = ["classic", "band", "tinted", "glass", "outline", "bold", "gradient-cards", "flat", "ring", "mono"]
LIST_PRESETS = ["classic", "striped", "cards", "dense", "soft", "dark-head", "bordered", "pill-rows", "airy", "accent-edge"]
CRUD_LAYOUTS = ["table", "kanban", "split-pane", "spreadsheet", "timeline"]
DASH_LAYOUTS = ["kpi-cards", "analytics", "activity-feed", "table-first", "operations"]   # widget composition (scaffold)
APP_NAVS = ["sidebar", "topnav"]                                                          # app-shell orientation (scaffold)

_VISUAL_NAV = {"clean": "blur", "bold": "accent-top", "premium-dark": "dark", "glass": "floating",
               "editorial": "minimal", "playful": "pill", "enterprise": "solid", "minimal": "minimal", "dense-admin": "underline"}
_VISUAL_DASH = {"clean": "classic", "bold": "bold", "premium-dark": "glass", "glass": "glass",
                "editorial": "mono", "playful": "gradient-cards", "enterprise": "outline", "minimal": "flat", "dense-admin": "ring"}
_DENSITY_LIST = {"compact": "dense", "spacious": "airy"}
_VISUAL_LIST = {"enterprise": "bordered", "editorial": "soft", "playful": "pill-rows", "premium-dark": "dark-head",
                "bold": "accent-edge", "glass": "striped", "minimal": "classic", "clean": "classic", "dense-admin": "dense"}
_DASHBOARD_LAYOUT = {"kpi-cards": "kpi-cards", "analytics": "analytics", "activity-feed": "activity-feed",
                     "table-first": "table-first", "split-pane": "table-first", "kanban": "operations",
                     "calendar": "analytics", "map-based": "analytics"}
_NAV_ORIENT = {"sidebar": "sidebar", "topnav": "topnav", "split-nav": "sidebar", "tabs": "topnav",
               "command-palette": "sidebar", "stepper": "topnav", "mobile-bottom-nav": "topnav"}
# crud_style -> (concrete scaffold crud_layout, the table list-preset to pair with it)
_CRUD_MAP = {"table-dense": ("table", "dense"), "card-grid": ("table", "cards"), "split-pane": ("split-pane", "classic"),
             "wizard": ("table", "soft"), "kanban": ("kanban", "classic"), "timeline": ("timeline", "classic"),
             "calendar": ("timeline", "striped"), "spreadsheet": ("spreadsheet", "classic")}
# complementary layouts so a multi-entity app mixes structure (not all-kanban)
_CRUD_COMPLEMENT = {"table": ["split-pane", "timeline"], "kanban": ["table", "timeline"],
                    "timeline": ["table", "split-pane"], "split-pane": ["table", "kanban"], "spreadsheet": ["table", "timeline"]}

# section_strategy -> ordered marketing section kinds (known to page_sections)
_SECTION_ORDER = {
    "storytelling": ["split", "testimonial", "features", "stats"],
    "conversion": ["features", "pricing", "stats", "faq"],
    "operations": ["steps", "features", "stats", "split"],
    "directory": ["gallery", "features", "terminology"],
    "analytics": ["stats", "features", "split"],
    "community": ["testimonial", "features", "gallery"],
    "productized-service": ["features", "pricing", "steps", "faq"],
}


def genome_to_crud_layout(crud_style: str) -> str:
    """The single concrete CRUD component a crud_style maps to (pure, testable)."""
    return _CRUD_MAP.get(crud_style, ("table", "classic"))[0]


def genome_crud_layouts(genome: dict, n: int) -> list:
    """A per-entity crud_layout list: entity 0 reflects the genome's crud_style; the rest
    rotate complementary layouts (seeded by app_seed) so a multi-entity app mixes structure."""
    primary = genome_to_crud_layout(genome.get("crud_style", "table-dense"))
    comp = _CRUD_COMPLEMENT.get(primary, ["table"])
    seed = int(str(genome.get("app_seed", "0") or "0"), 16) if str(genome.get("app_seed", "0")).strip("0123456789abcdef") == "" else hash(str(genome.get("app_seed")))
    rng = random.Random(seed)
    out = [primary]
    for i in range(1, max(0, n)):
        out.append(comp[(i - 1) % len(comp)] if rng.random() < 0.7 else primary)
    return out[:n]


def genome_to_styles(genome: dict) -> dict:
    """Translate the genome into the scaffold's site.styles knobs (all build-safe)."""
    vis = genome.get("visual_style", "clean")
    dens = genome.get("density", "balanced")
    return {
        "nav": _VISUAL_NAV.get(vis, "blur"),
        "dash": _VISUAL_DASH.get(vis, "classic"),
        "dashLayout": _DASHBOARD_LAYOUT.get(genome.get("dashboard_style", "kpi-cards"), "kpi-cards"),
        "list": _DENSITY_LIST.get(dens) or _VISUAL_LIST.get(vis, "classic"),
        "appNav": _NAV_ORIENT.get(genome.get("navigation_pattern", "sidebar"), "sidebar"),
    }


def genome_section_order(genome: dict, default_pack: list) -> list:
    """Reorder a marketing page's section pack per the genome's section_strategy."""
    order = _SECTION_ORDER.get(genome.get("section_strategy", ""))
    return list(order) if order else list(default_pack or [])


def structure_signature(genome: dict, styles: dict, crud_layouts) -> str:
    """A signature of the REAL generated structure (not just genome metadata): app-shell
    orientation + dashboard composition + nav/list preset + the multiset of CRUD layouts +
    section strategy. Two apps with the same signature look structurally identical."""
    layouts = "+".join(sorted(crud_layouts or [])) or "table"
    return "|".join([
        genome.get("layout_family", ""), styles.get("appNav", ""), styles.get("dashLayout", ""),
        styles.get("nav", ""), styles.get("list", ""), layouts, genome.get("section_strategy", ""),
    ])


# ======================================================================
# UNIVERSAL DOMAIN MODELER (Part 2): infer entities/fields/workflows/roles/pages for
# ANY prompt - including unknown/custom ones - from its nouns, verbs, business goal and
# category. Used as a FALLBACK when research/planner produced nothing, so a generated app
# always has a meaningful, domain-shaped data model (never an empty "Item" stub).
# ======================================================================
import re as _re

_DM_STOP = {"the", "and", "for", "with", "app", "application", "build", "create", "make", "that", "this",
            "want", "need", "system", "platform", "website", "site", "online", "web", "tool", "manage",
            "management", "track", "tracking", "simple", "small", "let", "lets", "allow", "allows", "users",
            "user", "can", "where", "which", "their", "your", "our", "have", "has", "from", "into", "about"}
_DM_VERBS = {"book": "Booking", "order": "Ordering", "approve": "Approvals", "ship": "Shipping",
             "enroll": "Enrollment", "schedule": "Scheduling", "pay": "Payments", "invoice": "Invoicing",
             "review": "Reviews", "track": "Tracking", "assign": "Assignments", "report": "Reporting",
             "rent": "Rentals", "deliver": "Deliveries", "register": "Registration", "submit": "Submissions",
             "publish": "Publishing", "checkout": "Checkout", "subscribe": "Subscriptions"}
_DM_ROLE_WORDS = {"admin": "Admin", "manager": "Manager", "staff": "Staff", "customer": "Customer",
                  "client": "Client", "student": "Student", "teacher": "Teacher", "patient": "Patient",
                  "doctor": "Doctor", "seller": "Seller", "buyer": "Buyer", "member": "Member",
                  "owner": "Owner", "employee": "Employee", "vendor": "Vendor", "guest": "Guest",
                  "agent": "Agent", "host": "Host", "driver": "Driver", "tenant": "Tenant"}
# per-category SEED entities so a recognised domain always models its core records
_CATEGORY_ENTITIES = {
    "booking": ["Booking", "Customer", "Service", "Staff"],
    "marketplace": ["Listing", "Order", "Seller", "Review"],
    "education": ["Course", "Student", "Assignment", "Enrollment"],
    "healthcare": ["Patient", "Appointment", "Doctor", "Record"],
    "finance": ["Account", "Transaction", "Invoice", "Client"],
    "inventory": ["Product", "Supplier", "Order", "Shipment"],
    "content": ["Article", "Author", "Category", "Comment"],
    "social": ["Post", "Member", "Comment", "Group"],
    "internal_tool": ["Ticket", "Team", "Task", "Report"],
    "business": ["Lead", "Deal", "Client", "Task"],
}
_FIELD_BANK = ["name", "status", "email", "phone", "date", "amount", "category", "notes", "owner", "priority"]


def _field(name: str) -> dict:
    n = name.lower()
    t = "text"
    if n in ("status", "priority", "category", "stage"): t = "select"
    elif n in ("date", "due_date", "created_at"): t = "date"
    elif n in ("amount", "price", "total", "quantity", "count"): t = "number"
    elif n == "email": t = "email"
    elif n in ("notes", "description", "details"): t = "textarea"
    out = {"name": name, "label": name.replace("_", " ").title(), "type": t}
    if t == "select":
        out["options"] = ["Active", "Pending", "Completed", "Cancelled"]
    return out


def infer_domain_model(prompt: str, understanding: dict = None) -> dict:
    """Return {entities, roles, workflows, pages, public_vs_private} inferred from the
    prompt. Works for unknown domains by pulling salient nouns/verbs out of the text."""
    u = understanding or infer_app_understanding(prompt)
    cat = u.get("app_category", "custom")
    p = " " + (prompt or "").lower() + " "
    words = [w for w in _re.findall(r"[a-z]{3,}", p) if w not in _DM_STOP]

    roles = [lab for key, lab in _DM_ROLE_WORDS.items() if key in p] or ["Admin", "User"]
    workflows = [lab for vb, lab in _DM_VERBS.items() if _re.search(r"\b" + vb, p)]

    names = list(dict.fromkeys(_CATEGORY_ENTITIES.get(cat, [])))            # category seeds first
    if cat == "custom":
        # singularise + Title-case salient nouns from the prompt as candidate entities
        for w in words:
            cand = (w[:-1] if w.endswith("s") and len(w) > 4 else w).title()
            if cand not in names and cand.lower() not in _DM_ROLE_WORDS:
                names.append(cand)
    names = names[:4] or ["Record"]

    entities = []
    for i, nm in enumerate(names):
        fields = ["name", "status", "notes"] + (["amount"] if cat in ("finance", "marketplace", "inventory") else ["date"])
        entities.append({
            "name": nm, "label": nm + ("s" if not nm.endswith("s") else ""),
            "storage_key": nm, "fields": [_field(f) for f in dict.fromkeys(fields)],
            "crud_layout": "table",
        })
    pages = [w.title() for w in ("features", "about", "contact")] if u.get("public_vs_private") != "internal" else []
    return {"entities": entities, "roles": roles[:3],
            "workflows": workflows or ["Records", "Reporting"], "pages": pages,
            "public_vs_private": u.get("public_vs_private", "hybrid")}


def load_genome(out_dir: str):
    try:
        with open(os.path.join(out_dir, GENOME_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
