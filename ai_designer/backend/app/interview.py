"""Requirements-gathering interview (the 'human-ask planner agent').

The user just types what they want to build (no SRS upload needed) + picks the
app TYPE and a LANGUAGE. Gemma then writes a SHORT, NON-TECHNICAL, domain- and
type-tailored questionnaire IN THAT LANGUAGE: which pages, what sections on each
page, login/roles, the data records, the look. Every question has selectable
options AND lets the user type their own. The answers (assemble_intake) drive
generation directly - nothing to edit afterwards.

rule-base + LLM: the rules fix the COVERAGE (pages / sections / auth / roles /
data / style) and the JSON contract; the LLM fills domain-specific options and
wording per app, in the user's language. Deterministic fallback if the LLM is
unavailable, so the studio never blocks.
"""
import json
import os
import re
from app import srs

# ------------------------------------------------------------------ vocab
LANGUAGES = [
    {"value": "en", "label": "English"},
    {"value": "si", "label": "සිංහල"},
    {"value": "si-en", "label": "Sinhala + English"},
    {"value": "ta", "label": "தமிழ்"},
]
_LANG_NAME = {"en": "English", "si": "Sinhala", "si-en": "mixed Sinhala and English", "ta": "Tamil"}

# The 3 app archetypes the generator builds (drives auth + the public tier).
APP_TYPES = [
    {"value": "public", "label": "Public website",
     "desc": "Open to everyone — company site, e-commerce storefront, portfolio. No login."},
    {"value": "internal", "label": "Internal app",
     "desc": "Private, login-only — POS, inventory, staff portal, admin dashboard."},
    {"value": "hybrid", "label": "Hybrid",
     "desc": "Public pages + a secure logged-in area (students / staff / admins)."},
]
_APP_TYPE_VALUES = {a["value"] for a in APP_TYPES}

COMPONENT_LIBRARY = [
    {"value": "hero", "label": "Hero banner"}, {"value": "features", "label": "Feature grid"},
    {"value": "steps", "label": "How-it-works steps"}, {"value": "stats", "label": "Stats band"},
    {"value": "split", "label": "Image + text"}, {"value": "gallery", "label": "Image gallery"},
    {"value": "pricing", "label": "Pricing tiers"}, {"value": "faq", "label": "FAQ"},
    {"value": "testimonial", "label": "Testimonial"}, {"value": "terminology", "label": "Highlight chips"},
    {"value": "contact_form", "label": "Contact form"}, {"value": "cta", "label": "Call to action"},
]
_COMPONENT_VALUES = {c["value"] for c in COMPONENT_LIBRARY}
_LABEL_BY_VALUE = {c["value"]: c["label"] for c in COMPONENT_LIBRARY}
PAGE_COMPONENT_DEFAULTS = {
    "features": ["hero", "features", "steps", "stats", "cta"],
    "content":  ["hero", "split", "features", "terminology", "cta"],
    "about":    ["hero", "split", "stats", "testimonial", "cta"],
    "gallery":  ["hero", "gallery", "split", "cta"],
    "pricing":  ["hero", "pricing", "faq", "cta"],
    "contact":  ["hero", "contact_form"],
}
_PARADIGMS = [
    {"value": "minimal", "label": "Minimal (clean, airy)"},
    {"value": "neo-brutalism", "label": "Neo-brutalism (bold, hard shadows)"},
    {"value": "glassmorphism", "label": "Glassmorphism (frosted glass)"},
    {"value": "cyberpunk", "label": "Cyberpunk (dark, neon glow)"},
]
_LAYOUTS = ["table", "kanban", "split-pane", "spreadsheet", "timeline"]
_VALID_THEMES = {p["value"] for p in _PARADIGMS}
# Public-page slugs that collide with the app's own routes or the landing.
_RESERVED_PAGE = {"", "home", "index", "dashboard", "login", "register", "logout", "e", "entity",
                  "workspace", "notifications", "profile", "settings", "api", "assets", "auth", "admin"}

# Design presets the user can pick (values match the scaffold's NAV/DASH/LIST_STYLES).
NAV_OPTIONS = [{"value": "blur", "label": "Glassy / blur"}, {"value": "solid", "label": "Solid bar"},
               {"value": "pill", "label": "Pill buttons"}, {"value": "dark", "label": "Dark bar"},
               {"value": "minimal", "label": "Minimal"}, {"value": "accent-top", "label": "Accent top line"},
               {"value": "underline", "label": "Underline links"}, {"value": "floating", "label": "Floating bar"},
               {"value": "tinted", "label": "Tinted"}]
DASH_OPTIONS = [{"value": "classic", "label": "Classic cards"}, {"value": "band", "label": "Colour band"},
                {"value": "glass", "label": "Glass cards"}, {"value": "outline", "label": "Outlined"},
                {"value": "bold", "label": "Bold shadow"}, {"value": "gradient-cards", "label": "Gradient cards"},
                {"value": "flat", "label": "Flat"}, {"value": "ring", "label": "Ring accent"}, {"value": "mono", "label": "Mono"}]
LIST_OPTIONS = [{"value": "classic", "label": "Classic table"}, {"value": "striped", "label": "Striped rows"},
                {"value": "cards", "label": "Card rows"}, {"value": "dense", "label": "Dense"}, {"value": "soft", "label": "Soft"},
                {"value": "bordered", "label": "Bordered"}, {"value": "pill-rows", "label": "Pill rows"},
                {"value": "airy", "label": "Airy"}, {"value": "accent-edge", "label": "Accent edge"}]
_DESIGN_STEPS = [("nav", "Top menu bar (navbar) style?", NAV_OPTIONS),
                 ("dash", "Dashboard style?", DASH_OPTIONS),
                 ("list", "Data list / table style?", LIST_OPTIONS)]

_DEFAULT_LABELS = {
    "title": "Let’s design your app", "subtitle": "Pick what each part should have — I’ll build exactly this.",
    "pages": "Which pages?", "sections": "What goes on each page?",
    "auth": "Do you need user login?", "auth_yes": "Yes — login & roles", "auth_no": "No — public site",
    "roles": "Who are the users (roles)?", "data": "What information will it manage?",
    "style": "Visual style", "add_page": "+ add a page, press Enter",
    "add_section": "+ add a section", "add_role": "+ add a role", "add_data": "+ add a data section",
    "generate": "Generate website →", "loading": "Thinking of the right questions…",
}


# ---------------------------------------------------------------- coverage rule
# The RULE: areas distilled from the full SRS question list that MUST be covered
# (count doesn't matter). Asked in plain, non-technical language, one at a time,
# but only the ones relevant to the app type. `needs_auth` -> only login apps;
# `types` -> which app types; `depends` -> only after a related yes.
COVERAGE = [
    # Accounts & access
    {"id": "login_method", "group": "Accounts", "kind": "single", "needs_auth": True,
     "label": "How should people sign in?", "options": ["Email & password", "Mobile & password", "Email + OTP code", "Google sign-in"]},
    {"id": "register_fields", "group": "Accounts", "kind": "multi", "needs_auth": True,
     "label": "What details do you collect when someone signs up?", "options": ["Full name", "Email", "Mobile number", "Password", "NIC / ID", "Address", "Profile photo"]},
    {"id": "account_extras", "group": "Accounts", "kind": "multi", "needs_auth": True,
     "label": "Which account features do you want?", "options": ["Forgot / reset password", "Email verification", "Mobile OTP", "Two-factor for staff", "Block / suspend accounts"]},
    {"id": "audit_log", "group": "Accounts", "kind": "toggle", "needs_auth": True,
     "label": "Keep an activity history (audit log) of important changes?"},
    # Modules
    {"id": "reports", "group": "Modules", "kind": "toggle", "types": ["internal", "hybrid"],
     "label": "Do you want a reports & analytics area?"},
    {"id": "notifications", "group": "Modules", "kind": "toggle", "types": ["internal", "hybrid"],
     "label": "Should the app show notifications?"},
    {"id": "notify_events", "group": "Modules", "kind": "multi", "depends": {"id": "notifications", "truthy": True},
     "label": "What should send a notification?", "options": ["New record added", "Status changed", "Payment received", "Low stock", "Due date / reminder"]},
    {"id": "file_uploads", "group": "Modules", "kind": "toggle", "types": ["public", "internal", "hybrid"],
     "label": "Will users upload files or images?"},
    {"id": "approval", "group": "Modules", "kind": "toggle", "needs_auth": True,
     "label": "Is there an approval / review step (e.g. approve a request)?"},
    {"id": "multi_branch", "group": "Modules", "kind": "toggle", "needs_auth": True,
     "label": "Multiple branches or locations to manage?"},
    # Data
    {"id": "record_actions", "group": "Data", "kind": "multi", "needs_auth": True,
     "label": "What can users do with each record?", "options": ["Add", "Edit", "Delete", "View details", "Export", "Print", "Approve / Reject"]},
    {"id": "export_formats", "group": "Data", "kind": "multi", "needs_auth": True,
     "label": "Let users download data as?", "options": ["PDF", "Excel", "CSV"]},
    {"id": "bulk_import", "group": "Data", "kind": "toggle", "needs_auth": True,
     "label": "Import data in bulk (Excel / CSV upload)?"},
    {"id": "data_view", "group": "Data", "kind": "single", "needs_auth": True,
     "label": "How should the main data lists look by default?", "options": ["Standard table", "Spreadsheet grid", "Kanban board", "Split (list + details)", "Cards"]},
    # Functions
    {"id": "documents", "group": "Functions", "kind": "multi", "types": ["internal", "hybrid"],
     "label": "Generate documents to download or print?", "options": ["Invoice", "Report", "Certificate", "Receipt"]},
    {"id": "payments", "group": "Functions", "kind": "toggle", "types": ["public", "internal", "hybrid"],
     "label": "Do you take online payments?"},
    {"id": "payment_gateway", "group": "Functions", "kind": "single", "depends": {"id": "payments", "truthy": True},
     "label": "Which payment method?", "options": ["PayHere", "Stripe", "PayPal", "Bank transfer"]},
    {"id": "messaging", "group": "Functions", "kind": "multi", "types": ["public", "internal", "hybrid"],
     "label": "Send messages to users?", "options": ["Email", "SMS", "WhatsApp"]},
    # Look & feel
    {"id": "brand_color", "group": "Look", "kind": "single", "types": ["public", "internal", "hybrid"],
     "label": "Main brand colour?", "options": ["Blue", "Green", "Purple", "Red", "Orange", "Black & white"]},
    {"id": "dark_mode", "group": "Look", "kind": "toggle", "types": ["public", "internal", "hybrid"],
     "label": "Offer a dark mode?"},
    {"id": "animations", "group": "Look", "kind": "toggle", "types": ["public", "internal", "hybrid"],
     "label": "Add smooth animations & hover effects?"},
    # AI
    {"id": "ai_features", "group": "AI", "kind": "multi", "types": ["public", "internal", "hybrid"],
     "label": "Any AI features?", "options": ["Chatbot assistant", "Smart search", "Auto-generated reports", "Recommendations", "None"]},
    # Free text - the user's own functional requirements in their own words
    {"id": "other_features", "group": "More", "kind": "text", "types": ["public", "internal", "hybrid"],
     "label": "Anything else you need? Type any other features in your own words."},
]


_COV_LABEL = {a["id"]: a["label"] for a in COVERAGE}


def _applicable_coverage(app_type):
    out = []
    for a in COVERAGE:
        if a.get("needs_auth") and app_type == "public":
            continue
        if a.get("types") and app_type not in a["types"]:
            continue
        out.append({k: a.get(k) for k in ("id", "group", "kind", "label", "options", "needs_auth", "depends") if a.get(k) is not None})
    return out


_COV_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_coverage_i18n.json")


def _load_cov_cache():
    try:
        return json.load(open(_COV_CACHE, encoding="utf-8"))
    except Exception:
        return {}


def _translate_batch(items, language):
    from app.agents import get_llm, extract_json
    from langchain_core.messages import SystemMessage, HumanMessage
    lang = _LANG_NAME.get(language, "English")
    compact = {a["id"]: {"label": a["label"], "options": a.get("options", [])} for a in items}
    sysmsg = (f"Translate the UI strings to {lang}, simple and non-technical, keep meaning. "
              'Reply ONLY JSON mapping each id to {"label":"..","options":["..."]} - SAME ids, SAME number of options.')
    out = extract_json(get_llm(temperature=0.2, num_predict=2200).invoke(
        [SystemMessage(content=sysmsg), HumanMessage(content=json.dumps(compact, ensure_ascii=False))]))
    return out if isinstance(out, dict) else {}


def _build_cov_table(language):
    """Translate the FULL fixed COVERAGE set in small batches (reliable)."""
    table = {}
    full = [{"id": a["id"], "label": a["label"], "options": a.get("options", [])} for a in COVERAGE]
    for i in range(0, len(full), 6):
        batch = full[i:i + 6]
        try:
            res = _translate_batch(batch, language)
        except Exception:
            res = {}
        for a in batch:
            t = res.get(a["id"])
            if isinstance(t, dict) and t.get("label"):
                opts = t.get("options") if (isinstance(t.get("options"), list) and len(t["options"]) == len(a["options"])) else a["options"]
                table[a["id"]] = {"label": str(t["label"])[:90], "options": [str(o)[:40] for o in opts]}
            else:
                table[a["id"]] = {"label": a["label"], "options": a["options"]}
    return table


def _translate_coverage(areas, language):
    """Apply Sinhala/Tamil translations of the fixed coverage (built once per
    language, then cached in _coverage_i18n.json). English/mixed stay as-is."""
    if language not in ("si", "ta") or not areas:
        return areas
    cache = _load_cov_cache()
    table = cache.get(language)
    if not table:
        table = _build_cov_table(language)
        cache[language] = table
        try:
            json.dump(cache, open(_COV_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass
    for a in areas:
        t = table.get(a["id"])
        if t and t.get("label"):
            a["label"] = t["label"]
            if a.get("options") and len(t.get("options", [])) == len(a["options"]):
                a["options"] = t["options"]
    return areas


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:24] or "page"


def _page_template(name):
    return srs._page_template(name)


# ------------------------------------------------------------------ LLM planner
_PLAN_SCHEMA = """{
 "app_name": "<short product name>",
 "labels": {"title":"..","subtitle":"..","pages":"..","sections":"..","auth":"..","auth_yes":"..","auth_no":"..","roles":"..","data":"..","style":"..","add_page":"..","add_section":"..","add_role":"..","add_data":"..","generate":".."},
 "pages": [ {"label":"<page name>","slug":"<url-slug>","sections":[ {"value":"<one of: hero|features|steps|stats|split|gallery|pricing|faq|testimonial|terminology|contact_form|cta>","label":"<a section name SPECIFIC to THIS page, e.g. on a Rooms page 'Room Gallery'/'Room Rates', not a generic name>"} , 4-7 sections UNIQUE to this page ]} , 3-6 pages ],
 "component_labels": {"hero":"..","features":"..","steps":"..","stats":"..","split":"..","gallery":"..","pricing":"..","faq":"..","testimonial":"..","terminology":"..","contact_form":"..","cta":".."},
 "auth_default": <true|false>,
 "roles": ["<role>", ...0-6 roles, [] if public],
 "entities": [ {"name":"<PascalCaseEnglishForCode>","label":"<display>","layout":"<table|kanban|split-pane|spreadsheet|timeline>"} , 0-6 ],
 "theme_default": "<minimal|neo-brutalism|glassmorphism|cyberpunk>",
 "extra_questions": [ {"id":"<snake>","label":"<question>","type":"<multi|single|toggle>","options":["..."],"allow_custom":true} , 1-4 simple extra questions like key features, brand color, notifications ]
}"""


def _llm_plan(description, app_type, language):
    from app.agents import get_llm, extract_json
    from langchain_core.messages import SystemMessage, HumanMessage
    lang = _LANG_NAME.get(language, "English")
    type_hint = {
        "public": "a PUBLIC website (open to everyone, no login). Focus on marketing pages & sections; auth_default=false; roles=[]; entities optional (e.g. a product catalogue).",
        "internal": "an INTERNAL app (login-only, no public marketing). auth_default=true; few/no marketing pages; focus on roles, data records and dashboards.",
        "hybrid": "a HYBRID app (public pages + a secure logged-in area). auth_default=true; include both marketing pages and roles/data.",
    }.get(app_type, "a web app")
    sys = (
        "You are a friendly product consultant interviewing a NON-TECHNICAL person who wants a website built. "
        f"Write EVERYTHING (labels, page names, options, questions) in {lang}. Keep wording simple - no jargon. "
        f"The app is {type_hint} Tailor pages, sections, roles, data and extra questions to THIS specific app "
        "(a calculator needs few; an e-commerce store needs many). Each page's sections MUST be different and "
        "specific to that page - a Rooms page lists different sections than an Amenities page - and every section "
        "gets a page-specific label; pick each section's value from the allowed list. "
        "Choose each data record's layout by its nature (workflow->kanban, dense record->split-pane, "
        "money/numbers->spreadsheet, history->timeline, else table). Output ONLY raw JSON in EXACTLY this shape:\n"
        + _PLAN_SCHEMA
    )
    user = f"The user wants to build: {str(description)[:600]}"
    res = get_llm(temperature=0.4, num_predict=2048).invoke([SystemMessage(content=sys), HumanMessage(content=user)])
    return extract_json(res.content)


def _sanitize_plan(p, app_type):
    p = p if isinstance(p, dict) else {}
    labels = dict(_DEFAULT_LABELS)
    for k, v in (p.get("labels") or {}).items():
        if k in labels and isinstance(v, str) and v.strip():
            labels[k] = v.strip()[:60]
    pages, seen = [], set()
    for pg in (p.get("pages") or [])[:6]:
        if not isinstance(pg, dict) or not pg.get("label"):
            continue
        sl = _slug(pg.get("slug") or pg["label"])
        if sl in seen or sl in _RESERVED_PAGE:   # never offer Home/Dashboard/etc. as a page
            continue
        seen.add(sl)
        # per-page sections are {value(builder), label(page-specific)}, deduped by value
        secs, seenv = [], set()
        for s in (pg.get("sections") or []):
            if isinstance(s, dict):
                v = str(s.get("value", "")).lower().strip()
                lab = str(s.get("label") or "").strip()[:30]
            else:
                v, lab = str(s).lower().strip(), ""
            if v in _COMPONENT_VALUES and v not in seenv:
                seenv.add(v)
                secs.append({"value": v, "label": lab or _LABEL_BY_VALUE.get(v, v)})
            if len(secs) >= 7:
                break
        if not secs:
            secs = [{"value": x, "label": _LABEL_BY_VALUE[x]} for x in ("hero", "features", "cta")]
        pages.append({"label": str(pg["label"])[:30], "slug": sl, "template": _page_template(pg["label"]),
                      "sections": secs, "section_values": [s["value"] for s in secs]})
    comp_labels = {}
    for c in COMPONENT_LIBRARY:
        lab = (p.get("component_labels") or {}).get(c["value"])
        comp_labels[c["value"]] = (lab.strip()[:30] if isinstance(lab, str) and lab.strip() else c["label"])
    roles = [str(r)[:24] for r in (p.get("roles") or []) if str(r).strip()][:6]
    ents = []
    for e in (p.get("entities") or [])[:6]:
        if not isinstance(e, dict) or not e.get("name"):
            continue
        nm = re.sub(r"[^A-Za-z0-9]", "", str(e["name"])) or "Item"
        lay = str(e.get("layout", "table")).lower()
        ents.append({"name": nm, "label": str(e.get("label") or nm)[:30], "layout": lay if lay in _LAYOUTS else "table"})
    theme = str(p.get("theme_default", "minimal")).lower()
    extra = []
    for q in (p.get("extra_questions") or [])[:4]:
        if not isinstance(q, dict) or not q.get("label"):
            continue
        qt = str(q.get("type", "multi")).lower()
        extra.append({"id": _slug(q.get("id") or q["label"]).replace("-", "_"), "label": str(q["label"])[:90],
                      "type": qt if qt in ("multi", "single", "toggle") else "multi",
                      "options": [str(o)[:40] for o in (q.get("options") or [])][:8], "allow_custom": True})
    auth_default = bool(p.get("auth_default", app_type != "public"))
    if app_type == "public":
        auth_default, roles = False, []
    elif app_type == "internal":
        auth_default = True
    return {
        "app_name": str(p.get("app_name") or "App")[:40], "labels": labels, "pages": pages,
        "component_labels": comp_labels, "auth_default": auth_default, "roles": roles,
        "entities": ents, "theme_default": theme if theme in _VALID_THEMES else "minimal", "extra_questions": extra,
    }


# ------------------------------------------------------------------ fallback (no LLM)
def _fallback_plan(description, app_type):
    parsed = srs.parse_srs_input(description)
    if parsed:
        app_name, roles = parsed["app_name"], parsed["roles"]
        ents = [{"name": e["name"], "label": e["name"], "layout": e.get("crud_layout", "table")} for e in parsed["entities"]]
        sug = parsed["marketing_pages"]
    else:
        try:
            from app import research
            bp = research.deep_research(description) or {}
        except Exception:
            bp = {}
        app_name = bp.get("app_name") or (str(description) or "App").strip()[:40].title()
        roles = bp.get("roles", ["Admin", "User"])
        ents = [{"name": (e.get("name") if isinstance(e, dict) else str(e)), "label": (e.get("name") if isinstance(e, dict) else str(e)),
                 "layout": (e.get("crud_layout", "table") if isinstance(e, dict) else "table")} for e in bp.get("entities", [])]
        sug = bp.get("marketing_pages", [])
    pages = []
    for p in (sug or [{"name": "About", "slug": "about", "template": "about"}, {"name": "Contact", "slug": "contact", "template": "contact"}]):
        nm = p.get("name") if isinstance(p, dict) else str(p)
        tpl = (p.get("template") if isinstance(p, dict) else _page_template(nm)) or _page_template(nm)
        pages.append({"label": nm, "slug": _slug(p.get("slug", nm) if isinstance(p, dict) else nm),
                      "template": tpl, "sections": PAGE_COMPONENT_DEFAULTS.get(tpl, PAGE_COMPONENT_DEFAULTS["content"])})
    return _sanitize_plan({"app_name": app_name, "pages": pages, "roles": roles, "entities": ents,
                           "auth_default": app_type != "public", "theme_default": "minimal"}, app_type)


# ------------------------------------------------------------------ public API
def build_questionnaire(description: str, app_type: str = "hybrid", language: str = "en") -> dict:
    app_type = app_type if app_type in _APP_TYPE_VALUES else "hybrid"
    try:
        plan = _sanitize_plan(_llm_plan(description, app_type, language), app_type)
        source = "gemma"
        if not plan["pages"]:
            raise ValueError("empty plan")
    except Exception:
        plan = _fallback_plan(description, app_type)
        source = "fallback"

    page_opts = [{"value": p["slug"], "label": p["label"], "template": p["template"],
                  "sections": p["sections"], "default": True} for p in plan["pages"]]
    library = [{"value": c["value"], "label": plan["component_labels"].get(c["value"], c["label"])} for c in COMPONENT_LIBRARY]
    page_sections = {p["slug"]: p["sections"] for p in plan["pages"]}

    questions = [
        {"id": "pages", "type": "multi", "label": plan["labels"]["pages"], "options": page_opts, "allow_custom": True},
        {"id": "components", "type": "per_page", "label": plan["labels"]["sections"], "library": library, "allow_custom": True},
    ]
    if app_type != "public":
        questions += [
            {"id": "auth", "type": "toggle", "label": plan["labels"]["auth"], "default": plan["auth_default"],
             "yes": plan["labels"]["auth_yes"], "no": plan["labels"]["auth_no"]},
            {"id": "roles", "type": "multi", "label": plan["labels"]["roles"],
             "options": [{"value": r, "label": r, "default": True} for r in plan["roles"]], "allow_custom": True, "depends_on": "auth"},
            {"id": "entities", "type": "entity_layouts", "label": plan["labels"]["data"],
             "items": [{"name": e["name"], "label": e["label"], "layout": e["layout"]} for e in plan["entities"]],
             "layout_options": _LAYOUTS, "allow_custom": True, "depends_on": "auth"},
        ]
    for q in plan["extra_questions"]:
        questions.append({**q, "extra": True})
    questions.append({"id": "theme", "type": "single", "label": plan["labels"]["style"], "options": _PARADIGMS, "default": plan["theme_default"]})

    return {
        "app_name": plan["app_name"], "app_type": app_type, "language": language, "source": source,
        "labels": plan["labels"], "questions": questions,
        "page_sections": page_sections, "page_component_defaults": PAGE_COMPONENT_DEFAULTS, "default_template": "content",
    }


def _norm_layout(v):
    v = str(v).lower().strip()
    return v if v in _LAYOUTS else "table"


def assemble_intake(answers: dict) -> dict:
    """Normalize the studio's collected answers into the generation spec."""
    answers = answers or {}
    app_type = answers.get("app_type") if answers.get("app_type") in _APP_TYPE_VALUES else "hybrid"
    raw_pages = answers.get("pages") or []
    comp_map = answers.get("components") or {}
    pages = []
    for p in raw_pages:
        if isinstance(p, str):
            name, slug, template = p, _slug(p), _page_template(p)
        else:
            name = p.get("label") or p.get("name") or "Page"
            slug = _slug(p.get("value") or p.get("slug") or name)
            template = p.get("template") or _page_template(name)
        secs = [s for s in (comp_map.get(slug) or comp_map.get(name) or []) if s]
        pages.append({"name": str(name)[:28], "slug": slug, "template": template, "sections": secs})

    roles = [str(r).strip()[:24] for r in (answers.get("roles") or []) if str(r).strip()]
    entities = []
    for e in (answers.get("entities") or []):
        if isinstance(e, dict) and e.get("name"):
            entities.append({"name": re.sub(r"[^A-Za-z0-9]", "", str(e["name"])),
                             "label": str(e.get("label") or e["name"])[:30], "layout": _norm_layout(e.get("layout", "table"))})
    # extra + coverage answers -> a requirements note appended to the build prompt
    notes = []
    cov = answers.get("coverage") or {}
    for k, v in cov.items():
        name = _COV_LABEL.get(k, k.replace("_", " "))
        if v is True:
            notes.append(f"{name} yes")
        elif v is False:
            continue
        elif isinstance(v, list) and v:
            notes.append(f"{name} {', '.join(map(str, v))}")
        elif isinstance(v, str) and v.strip():
            notes.append(f"{name} {v.strip()}")
    extras = answers.get("extras") or {}
    for k, v in extras.items():
        if isinstance(v, list) and v:
            notes.append(f"{k.replace('_', ' ')}: {', '.join(map(str, v))}")
        elif isinstance(v, str) and v.strip():
            notes.append(f"{k.replace('_', ' ')}: {v.strip()}")

    auth = bool(answers.get("auth", app_type != "public")) and app_type != "public"
    theme = str(answers.get("theme", "")).lower().strip()
    return {
        "active": True, "app_type": app_type, "language": answers.get("language", "en"),
        "pages": pages if app_type != "internal" else [],   # internal apps skip the public tier
        "auth": auth, "roles": roles,
        "entities": entities, "entity_layouts": {e["name"]: e["layout"] for e in entities},
        "theme_style": theme if theme in _VALID_THEMES else "",
        "styles": {k: v for k, v in (answers.get("design") or {}).items() if v},   # navbar/dash/list presets
        "coverage": cov,
        "requirements": "; ".join(notes)[:1200],
    }


# ============================================================================
# STEP ENGINE - one question at a time. The next question (and its options) is
# decided from the answers so far; custom pages get LLM-generated sections on
# the spot. The studio holds `plan` + `answers` and echoes them back each step.
# ============================================================================
def _srs_summary(parsed, raw):
    ents = ", ".join(e["name"] for e in parsed.get("entities", []))
    roles = ", ".join(parsed.get("roles", []))
    pgs = ", ".join(p["name"] for p in parsed.get("marketing_pages", []))
    return (f"{parsed.get('app_name', 'App')} - manages: {ents}. User roles: {roles}. "
            f"Modules: {pgs}. Brief: {str(raw)[:400]}")


def _merge_srs_into_plan(plan, parsed):
    """SRS is authoritative for the functions/data: seed entities + roles from it
    (the LLM + interview still own pages/sections/design)."""
    se = parsed.get("entities") or []
    if se:
        plan["entities"] = [{"name": re.sub(r"[^A-Za-z0-9]", "", e["name"]) or "Item",
                             "label": e["name"], "layout": e.get("crud_layout", "table")} for e in se][:6]
    sr = [r for r in (parsed.get("roles") or []) if str(r).lower() != "guest"]
    if sr:
        plan["roles"] = sr[:6]
    if parsed.get("app_name") and plan.get("app_name") in (None, "", "App"):
        plan["app_name"] = parsed["app_name"]
    return plan


def build_plan(description: str, app_type: str = "hybrid", language: str = "en") -> dict:
    app_type = app_type if app_type in _APP_TYPE_VALUES else "hybrid"
    parsed = srs.parse_srs_input(description)          # SRS JSON pasted/uploaded?
    brief = _srs_summary(parsed, description) if parsed else description
    try:
        plan = _sanitize_plan(_llm_plan(brief, app_type, language), app_type)
        plan["source"] = "gemma"
        if not plan["pages"]:
            raise ValueError("empty")
    except Exception:
        plan = _fallback_plan(brief, app_type)
        plan["source"] = "fallback"
    if parsed:
        plan = _merge_srs_into_plan(plan, parsed)
        plan["source"] += "+srs"
    plan["app_type"] = app_type
    plan["language"] = language
    plan["description"] = brief[:300]
    plan["library"] = [{"value": c["value"], "label": plan["component_labels"].get(c["value"], c["label"])} for c in COMPONENT_LIBRARY]
    plan["coverage"] = _translate_coverage(_applicable_coverage(app_type), language)  # the rule (non-technical)
    return plan


def sections_for_page(description: str, language: str, page_label: str) -> dict:
    """LLM picks page-SPECIFIC section options for ONE page (used when the user
    types a custom page). Returns {options:[{value,label}], default:[values]}.
    Falls back to the page-template defaults."""
    lang = _LANG_NAME.get(language, "English")
    try:
        from app.agents import get_llm, extract_json
        from langchain_core.messages import SystemMessage, HumanMessage
        allowed = ", ".join(_COMPONENT_VALUES)
        sysmsg = (f"In {lang}, choose the 4-6 most useful sections for ONE web page, specific to that page. "
                  f"Each section's value is from ONLY this list: {allowed}. Give each a page-specific label. "
                  'Reply with ONLY JSON: {"sections":[{"value":"..","label":".."}]} - no prose.')
        user = f"App: {str(description)[:200]}. The page is called: '{page_label}'."
        out = extract_json(get_llm(temperature=0.3, num_predict=300).invoke(
            [SystemMessage(content=sysmsg), HumanMessage(content=user)]))
        opts, seen = [], set()
        for s in (out.get("sections") or []):
            v = str(s.get("value", "")).lower().strip() if isinstance(s, dict) else str(s).lower().strip()
            lab = str(s.get("label") or "").strip()[:30] if isinstance(s, dict) else ""
            if v in _COMPONENT_VALUES and v not in seen:
                seen.add(v)
                opts.append({"value": v, "label": lab or _LABEL_BY_VALUE.get(v, v)})
        if opts:
            return {"options": opts, "default": [o["value"] for o in opts]}
    except Exception:
        pass
    vals = PAGE_COMPONENT_DEFAULTS.get(_page_template(page_label), ["hero", "features", "cta"])
    return {"options": [{"value": v, "label": _LABEL_BY_VALUE.get(v, v)} for v in vals], "default": list(vals)}


def _q(qid, kind, label, plan, **kw):
    return {"question": {"id": qid, "kind": kind, "label": label, **kw}, "plan": plan}


def _answered_count(plan, answers):
    n = 0
    comps = answers.get("components") or {}
    if answers.get("pages") is not None:
        n += 1 + sum(1 for p in (answers.get("pages") or []) if isinstance(p, dict) and (p.get("value") or p.get("slug")) in comps)
    for k in ("auth", "roles", "entities", "theme"):
        if k in answers:
            n += 1
    n += len(answers.get("coverage") or {})
    n += len(answers.get("extras") or {})
    return n


def next_step(plan: dict, answers: dict) -> dict:
    """Return the next question, or {done, answers} when the interview is over."""
    plan = plan or {}
    answers = answers or {}
    app_type = plan.get("app_type", "hybrid")
    lang = plan.get("language", "en")
    L = plan.get("labels", _DEFAULT_LABELS)
    total = (1 + max(len(answers.get("pages") or []), len(plan.get("pages") or []))
             + (1 if app_type != "public" else 0) + (2 if app_type != "public" else 0)
             + len(plan.get("coverage") or []) + len(plan.get("extra_questions") or []) + 1)
    prog = {"index": _answered_count(plan, answers), "total": total}

    def out(res):
        res["progress"] = prog
        return res

    # 1) pages
    if answers.get("pages") is None:
        opts = [{"value": p["slug"], "label": p["label"], "template": p["template"]} for p in plan.get("pages", [])]
        return out(_q("pages", "multi", L.get("pages", "Which pages do you want?"), plan,
                      options=opts, default=[o["value"] for o in opts], allow_custom=True, hint=L.get("subtitle")))

    # 2) sections for each chosen page, in order. Options are SPECIFIC to that
    # page (from the plan; custom pages get them from the LLM on the spot).
    comp = answers.get("components") or {}
    for p in (answers.get("pages") or []):
        slug = (p.get("value") or p.get("slug")) if isinstance(p, dict) else str(p)
        if slug and slug not in comp:
            known = next((pp for pp in plan.get("pages", []) if pp["slug"] == slug), None)
            if known:
                opts = known.get("sections") or [{"value": v, "label": _LABEL_BY_VALUE.get(v, v)} for v in (known.get("section_values") or ["hero", "features", "cta"])]
                default = known.get("section_values") or [o["value"] for o in opts]
            else:
                r = sections_for_page(plan.get("description", ""), lang, p.get("label", slug))
                opts, default = r["options"], r["default"]
            return out(_q("sections:" + slug, "multi",
                          (L.get("sections", "What sections on this page?")) + " — " + str(p.get("label", slug)),
                          plan, options=opts, default=default, allow_custom=True))

    # 3) auth (skip for public)
    if app_type != "public" and "auth" not in answers:
        return out(_q("auth", "toggle", L.get("auth", "Do you need user login?"), plan,
                      default=plan.get("auth_default", True), yes=L.get("auth_yes", "Yes"), no=L.get("auth_no", "No")))
    auth_on = bool(answers.get("auth")) if app_type != "public" else False

    # 4) roles
    if auth_on and "roles" not in answers:
        opts = [{"value": r, "label": r} for r in plan.get("roles", [])]
        return out(_q("roles", "multi", L.get("roles", "Who are the users?"), plan,
                      options=opts, default=[o["value"] for o in opts], allow_custom=True))

    # 5) data records + layout
    if auth_on and "entities" not in answers:
        items = [{"name": e["name"], "label": e["label"], "layout": e["layout"]} for e in plan.get("entities", [])]
        return out(_q("entities", "entity_layouts", L.get("data", "What information will it manage?"), plan,
                      items=items, layout_options=_LAYOUTS, default=items, allow_custom=True))

    # 5.5) coverage areas - the rule: comprehensive, non-technical, one at a time,
    # skipping the ones that don't apply (auth / app type / depends-on a prior yes).
    cov = answers.get("coverage") or {}
    for area in plan.get("coverage", []):
        if area["id"] in cov:
            continue
        if area.get("needs_auth") and not auth_on:
            continue
        dep = area.get("depends")
        if dep:
            prev = cov.get(dep["id"])
            ok = bool(prev) if dep.get("truthy") else ((isinstance(prev, list) and dep.get("value") in prev) or prev == dep.get("value"))
            if not ok:
                continue
        kind = area["kind"]
        opts = [{"value": o, "label": o} for o in area.get("options", [])]
        if kind == "toggle":
            default = False
        elif kind == "text":
            default = ""
        elif kind == "single" and area.get("options"):
            default = area["options"][0]
        else:
            default = []
        return out(_q("cov:" + area["id"], kind, area["label"], plan,
                      options=opts, default=default, allow_custom=(kind not in ("toggle", "text"))))

    # 6) extra domain questions, one at a time
    extras = answers.get("extras") or {}
    for eq in plan.get("extra_questions", []):
        if eq["id"] not in extras:
            kind = "toggle" if eq["type"] == "toggle" else ("single" if eq["type"] == "single" else "multi")
            return out(_q("extra:" + eq["id"], kind, eq["label"], plan,
                          options=[{"value": o, "label": o} for o in eq.get("options", [])],
                          default=(False if kind == "toggle" else []), allow_custom=eq.get("allow_custom", True)))

    # 7) theme
    if "theme" not in answers:
        return out(_q("theme", "single", L.get("style", "Pick a visual style"), plan,
                      options=_PARADIGMS, default=plan.get("theme_default", "minimal")))

    # 8) design presets - navbar (always), dashboard + list (login apps only)
    design = answers.get("design") or {}
    for did, label, opts in _DESIGN_STEPS:
        if did in ("dash", "list") and not auth_on:
            continue
        if did not in design:
            return out(_q("design:" + did, "single", label, plan, options=opts, default=opts[0]["value"]))

    # done
    return {"done": True, "answers": {**answers, "app_type": app_type, "language": lang}, "plan": plan, "progress": prog}
