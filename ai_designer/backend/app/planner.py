"""
Rich deterministic site planner.

Turns the user's input -- a short natural-language prompt OR a full SRS JSON like
the HMS example -- into a COMPLETE multi-page site plan (15+ pages) with a real
navigation flow:

    Home (landing) -> Login / Register -> Dashboard
    per entity: List -> Create, List -> Detail -> Edit
    plus Profile, Settings (+ Reports/Notifications/Help padding to >= 15).

Split of responsibility:
  - parse_srs(text)  : DETERMINISTIC entity/role extraction from an SRS JSON.
  - normalize_spec() : clean an LLM-extracted spec (used for NL prompts).
  - build_pages(spec): DETERMINISTIC page list + flow (never guessed).
  - shell_rule()/kind_brief(): per-page coder instructions (content-only shell,
    field lists, and the exact navigation each page should wire up).
"""

import re

NAV_KINDS = {"dashboard", "list", "profile", "settings", "reports", "notifications", "help", "role_home"}
MAX_ENTITIES = 5  # cap so a huge SRS does not explode into a 40-page (slow) build


# ----------------------------------------------------------------- naming

def entity_class_name(raw: str) -> str:
    """'4_1_patient_profile_entity' -> 'PatientProfile'."""
    s = re.sub(r"^\d+[_.]\d+[_.]?", "", str(raw or ""))
    s = re.sub(r"(_entity|_node|_ledger|_table|_model|_record)$", "", s, flags=re.I)
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", s) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Item"


def label_from(name: str) -> str:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(name or ""))
    return s.replace("_", " ").strip().title() or "Item"


def slug_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", entity_class_name(name).lower()).strip("-") or "item"


# ----------------------------------------------------------------- field typing

def _input_type(field_name: str, data_type: str, validation: str):
    name = (field_name or "").lower()
    dt = (data_type or "").lower()
    val = validation or ""
    options = None
    m = re.search(r"\[([^\]]+)\]", val)  # enum options listed in the validation text
    # Only a quoted bracket list is an enum (avoids matching regexes like [1-9]).
    has_enum_list = bool(m and ("'" in m.group(1) or '"' in m.group(1)))
    if "enum" in dt or has_enum_list:
        if has_enum_list:
            options = [o.strip().strip("'\"") for o in m.group(1).split(",") if o.strip()]
        return "select", options
    if "password" in name:
        return "password", None
    if "email" in name:
        return "email", None
    if "phone" in name or name.endswith("_tel"):
        return "tel", None
    if "bool" in dt:
        return "checkbox", None
    if "date" in dt and "time" in dt:
        return "datetime-local", None
    if "date" in dt or "time" in dt:
        return "date", None
    if any(k in dt for k in ("int", "numeric", "decimal", "number", "float", "smallint")):
        return "number", None
    if any(k in dt for k in ("text", "json", "array")) or any(
        k in name for k in ("notes", "narrative", "description", "address", "summary", "comment", "bio")
    ):
        return "textarea", None
    return "text", None


def _is_form_field(field_name: str, db_mapping: str) -> bool:
    """Whether a field is user-editable in a create/edit form (skip primary keys
    and auto-managed defaults; everything else is editable)."""
    dm = (db_mapping or "").upper()
    if "PRIMARY KEY" in dm:
        return False
    if "DEFAULT" in dm and ("CURRENT_TIMESTAMP" in dm or "UUID" in dm):
        return False
    return True


def _field_from_srs(fd: dict) -> dict:
    fn = fd.get("field_name")
    itype, opts = _input_type(fn, fd.get("data_type", ""), fd.get("validation", ""))
    return {
        "name": fn,
        "label": label_from(fn),
        "type": itype,
        "required": not bool(fd.get("nullable", True)),
        "options": opts,
        "form": _is_form_field(fn, fd.get("db_mapping", "")),
    }


# ----------------------------------------------------------------- SRS parsing

def _collect_entities(node, parent_key, out):
    if isinstance(node, dict):
        fields = node.get("fields")
        if isinstance(fields, list) and fields and isinstance(fields[0], dict) and "field_name" in fields[0]:
            name = entity_class_name(parent_key or node.get("description", "Item"))
            built = [_field_from_srs(f) for f in fields if f.get("field_name")]
            out.append({"name": name, "label": label_from(name), "storage_key": name, "fields": built})
            return
        for k, v in node.items():
            _collect_entities(v, k, out)
    elif isinstance(node, list):
        for v in node:
            _collect_entities(v, parent_key, out)


def _short_role(persona: str) -> str:
    p = (persona or "").split("/")[0].strip()
    low = p.lower()
    for key, short in (("admin", "Admin"), ("physician", "Doctor"), ("doctor", "Doctor"),
                       ("nurse", "Nurse"), ("receptionist", "Receptionist"), ("consult", "Doctor"),
                       ("teacher", "Teacher"), ("student", "Student"), ("manager", "Manager"),
                       ("staff", "Staff"), ("cashier", "Cashier")):
        if key in low:
            return short
    words = [w for w in re.split(r"[^A-Za-z]+", p) if w]
    return words[-1].title() if words else "User"


def _parse_srs_roles(data) -> list:
    roles = []

    def walk(n):
        if isinstance(n, dict):
            if "persona" in n:
                roles.append(_short_role(n.get("persona")))
            if "role" in n and isinstance(n["role"], str):
                roles.append(_short_role(n["role"]))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(data)
    seen = []
    for r in roles:
        if r and r not in seen:
            seen.append(r)
    return seen or ["Admin", "Staff", "User"]


def _find_app_name(data) -> str:
    def search(keys):
        found = {"v": None}

        def walk(n):
            if found["v"] or not isinstance(n, (dict, list)):
                return
            if isinstance(n, dict):
                for key in keys:
                    if isinstance(n.get(key), str) and n[key].strip():
                        found["v"] = n[key].strip()
                        return
                for v in n.values():
                    walk(v)
            else:
                for v in n:
                    walk(v)

        walk(data)
        return found["v"]

    # Prefer the real product name over the document title.
    return search(["product_name", "app_name"]) or search(["title", "name"]) or "Prototype App"


def parse_srs(text: str):
    """Deterministically extract a spec from an SRS JSON string. Returns None if
    the input has no recognizable entities (then the caller uses the LLM).

    Lenient: tolerates a pasted wrapper (e.g. `sample_srs_json = \"\"\" {...} \"\"\"`)
    or leading/trailing prose by falling back to the outer {...} block."""
    import json
    s = (text or "").strip()
    data = None
    candidates = []
    if s.startswith("{") or s.startswith("["):
        candidates.append(s)
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(s[start:end + 1])
    for cand in candidates:
        try:
            data = json.loads(cand)
            break
        except Exception:
            continue
    if not isinstance(data, (dict, list)):
        return None
    entities = []
    _collect_entities(data, None, entities)
    if not entities:
        return None
    return {"app_name": _find_app_name(data), "roles": _parse_srs_roles(data), "entities": entities}


# ----------------------------------------------------------------- normalize (LLM output)

def normalize_spec(raw: dict) -> dict:
    roles = [str(r) for r in (raw.get("roles") or []) if r] or ["Admin", "User"]
    entities = []
    for e in raw.get("entities") or []:
        name = entity_class_name(e.get("name") or e.get("label") or "Item")
        fields = []
        for f in e.get("fields") or []:
            if isinstance(f, str):
                fields.append({"name": f, "label": label_from(f), "type": "text", "required": False, "options": None, "form": True})
            elif isinstance(f, dict) and f.get("name"):
                fields.append({
                    "name": f["name"], "label": f.get("label") or label_from(f["name"]),
                    "type": f.get("type", "text"), "required": bool(f.get("required", False)),
                    "options": f.get("options"), "form": True,
                })
        if not fields:
            fields = [{"name": "name", "label": "Name", "type": "text", "required": True, "options": None, "form": True}]
        entities.append({"name": name, "label": e.get("label") or label_from(name), "storage_key": name, "fields": fields})
    if not entities:
        entities = [{"name": "Item", "label": "Item", "storage_key": "Item",
                     "fields": [{"name": "name", "label": "Name", "type": "text", "required": True, "options": None, "form": True}]}]
    return {"app_name": raw.get("app_name") or "Prototype App", "roles": roles, "entities": entities}


# ----------------------------------------------------------------- page expansion

def build_pages(spec: dict) -> list:
    """Deterministically expand a spec into a complete, well-connected page set."""
    roles = spec.get("roles") or ["Admin", "User"]
    primary = roles[0]
    app = spec.get("app_name") or "Prototype App"
    entities = (spec.get("entities") or [])[:MAX_ENTITIES]

    pages = []

    def add(name, path, role, kind, entity=None, desc=""):
        pages.append({"name": name, "path": path, "role": role, "kind": kind, "entity": entity, "description": desc})

    # --- Public marketing tier (top Navbar + Login button; no auth, no CRUD) ---
    add("Home", "/", "Public", "landing", None, f"Marketing landing page for {app}")
    add("Features", "/features", "Public", "features", None, f"Features overview for {app}")
    add("About", "/about", "Public", "about", None, f"About {app}")
    add("Contact", "/contact", "Public", "contact", None, f"Contact page for {app}")
    # --- Auth bridge ---
    add("Login", "/login", "Public", "auth_login", None, "Login form")
    add("Register", "/register", "Public", "auth_register", None, "Registration form")
    # --- Authenticated app tier (sidebar) ---
    add("Dashboard", "/dashboard", primary, "dashboard", None, f"{app} overview dashboard")

    for e in entities:
        en, sl, lb = e["name"], slug_of(e["name"]), e.get("label", e["name"])
        add(f"{en}List", f"/{sl}", primary, "list", en, f"All {lb} records")
        add(f"{en}Create", f"/{sl}/new", primary, "create", en, f"Add a new {lb}")
        add(f"{en}Detail", f"/{sl}/detail", primary, "detail", en, f"Selected {lb} details")
        add(f"{en}Edit", f"/{sl}/edit", primary, "edit", en, f"Edit the selected {lb}")

    # --- Role-specific workspaces: every non-primary role gets its OWN page
    # tailored to its daily work (Doctor -> appointments view, Student -> my
    # courses, Teacher -> my classes ...), so the prototype shows role flows.
    for role in roles[1:4]:
        rn = re.sub(r"[^A-Za-z0-9]", "", str(role)) or "User"
        add(f"{rn}Workspace", f"/{slug_of(rn)}-workspace", role, "role_home", None,
            f"Personal workspace for the {role} role in {app}")

    add("Profile", "/profile", primary, "profile", None, "Signed-in user's profile")
    add("Settings", "/settings", primary, "settings", None, "App settings and preferences")

    extras = [
        ("Reports", "/reports", "reports", "Reports and analytics"),
        ("Notifications", "/notifications", "notifications", "Recent notifications"),
        ("Help", "/help", "help", "Help center and FAQ"),
    ]
    i = 0
    while len(pages) < 15 and i < len(extras):
        n, p, k, d = extras[i]
        add(n, p, primary, k, None, d)
        i += 1
    return pages


def nav_label(page: dict) -> str:
    """Sidebar label for a page (entity label for list pages, prettified otherwise)."""
    if page.get("kind") == "list" and page.get("entity"):
        return label_from(page["entity"])
    return label_from(page.get("name", "Page"))


# ----------------------------------------------------------------- tiers

MARKETING_KINDS = {"landing", "about", "features", "contact"}
AUTH_KINDS = {"auth_login", "auth_register"}

def page_tier(page: dict) -> str:
    """Which shell a page lives in: 'marketing' (public Navbar), 'auth' (full
    screen), or 'app' (authenticated Sidebar)."""
    k = page.get("kind")
    if k in MARKETING_KINDS:
        return "marketing"
    if k in AUTH_KINDS:
        return "auth"
    return "app"

def navbar_pages(pages: list) -> list:
    """Public marketing pages, in order, for the top navbar."""
    return [p for p in pages if page_tier(p) == "marketing"]


# ----------------------------------------------------------------- coder briefs

def shell_rule(page: dict) -> str:
    tier = page_tier(page)
    if tier == "marketing":
        return ("This is a PUBLIC marketing page rendered INSIDE a site shell that ALREADY provides a top "
                "navigation bar. Render ONLY the page's own content (rich, full-width marketing sections) - "
                "do NOT render your own navbar/header/sidebar. You MAY use full-width hero/section bands; "
                "start the root with `<div className=\"w-full\">`.")
    if tier == "auth":
        return ("This is a standalone auth page with NO shell. Render a full-screen layout "
                "(`min-h-screen` + the page background) with a single centered card.")
    return ("This page renders INSIDE an app shell that ALREADY provides the left sidebar and the page "
            "background. Render ONLY this page's own content: a header row (title + a primary action button) "
            "then the content. Your ROOT must be a content wrapper like `<div className=\"p-6 md:p-8\">` - do "
            "NOT render a sidebar, a top navbar, or a full-screen background of your own.")


def _fields_brief(fields: list) -> str:
    out = []
    for f in fields:
        t = f.get("type", "text")
        if t == "select" and f.get("options"):
            out.append(f"{f['name']} (select of {', '.join(f['options'][:6])})")
        else:
            out.append(f"{f['name']} ({t})")
    return "; ".join(out) or "name (text)"


def kind_brief(page: dict, entity_fields: list, all_entities=None, layouts=None) -> str:
    kind = page.get("kind", "content")
    entity = page.get("entity")
    key = entity or ""
    sl = slug_of(entity) if entity else ""
    list_path = f"/{sl}"
    sel = f"__sel_{key}"
    form_fields = [f for f in entity_fields if f.get("form", True)] or entity_fields
    cols = ", ".join(f["name"] for f in entity_fields[:5]) or "name"

    if kind == "landing":
        lay = (layouts or {}).get("landing")
        if lay:
            return ("A premium, VERY LONG, editorial marketing landing page (a top navbar is already provided): HUGE display typography, "
                    "generous whitespace, real photography. Follow THIS layout exactly:\n" + lay["brief"] +
                    "\nGeneral landing rules: USE PHOTOS GENEROUSLY - beyond the hero, weave in at least TWO more photo moments "
                    "(`assets/feature.jpg` as a full-width rounded-3xl band between sections, and `assets/about.jpg` inside a two-column "
                    "highlight section), every <img> with object-cover, rounded corners and onError hide. "
                    "Pricing buttons navigate('/register'); the FAQ accordion really toggles via state; the footer is a REAL multi-column "
                    "footer (brand + logo `assets/logo.jpg` h-8 w-8 rounded, 3 link columns using Links to '/about', '/features', '/contact', "
                    "'/login', '/register', and a small-print bar). Write real domain-specific copy for every section - this page should feel "
                    "like a $99 premium template. No data access.")
        return ("A premium, LONG, editorial marketing landing page (a top navbar is already provided) in the style of modern Figma "
                "landing templates: HUGE display typography, generous whitespace, real photography. Sections top to bottom: "
                "(1) HERO: an oversized display-font headline (text-5xl md:text-7xl font-bold tracking-tight, 2 lines, with ONE key word "
                "in the accent color), a short muted subline (max-w-xl), then two CTAs (Link to '/register' = primary 'Get Started', "
                "Link to '/login' = a subtle text link with an arrow). Beside/below the text place the hero photo "
                "`<img src=\"assets/hero.jpg\" alt=\"\" className=\"rounded-3xl shadow-xl w-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />` "
                "inside a relative container with ONE small decorative accent shape (a blurred accent-color circle div) BEHIND it (-z-10); "
                "(2) a numbered editorial feature trio - rows '01 / 02 / 03', each: the big muted number, a bold title, a 2-line description; "
                "(3) a full-width image band: `<img src=\"assets/feature.jpg\" alt=\"\" className=\"rounded-3xl w-full h-72 object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />` with a stats strip overlapping nothing - place the 4 big stat numbers in a row BELOW the image; "
                "(4) a Pricing section of 3 tier cards (Starter/Professional/Enterprise: price, 4-5 feature bullets with check icons, a working sign-up button -> navigate('/register')); highlight the middle tier with the accent ring and a 'Most popular' pill; "
                "(5) an interactive FAQ (4 questions toggled with local state, chevron rotates); "
                "(6) a testimonials row of 2-3 quote cards (initials avatar, name, role); "
                "(7) a final CTA band with a big headline and a working button to '/register'; "
                "(8) a footer with Links to '/about', '/features', '/contact' and small print. No data access.")
    if kind == "features":
        return ("A LONG, detailed public Features page (navbar provided). A page header with an eyebrow label + big display heading + tagline, then: "
                "(1) a responsive grid of 6-9 rich feature cards (each with an <Icon/> in a rounded accent tile, a bold title, and a descriptive paragraph); "
                "(2) a benefits row with checklist features (check icons); "
                "(3) an interactive feature comparison table comparing Starter, Professional, and Enterprise plans across 6 detailed criteria (wrapped in overflow-x-auto); "
                "(4) a full-width image band `<img src=\"assets/feature.jpg\" alt=\"\" className=\"rounded-3xl w-full h-72 object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />`; "
                "(5) a CTA section with a working button to '/register'. Purely informational, no data access.")
    if kind == "about":
        return ("A LONG public About page (navbar provided). "
                "(1) A mission statement hero section; "
                "(2) a two-column story section with text on the left and `<img src=\"assets/about.jpg\" alt=\"\" className=\"rounded-3xl shadow-lg w-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />` on the right; "
                "(3) a styled values grid of 4 cards with custom icons; "
                "(4) a timeline/milestones visual layout with 4 major company history points; "
                "(5) a team grid of 4 member cards (each showing an initials-in-a-circle avatar with a colored accent background, name, role, and a short bio - NO <img>). No data access.")
    if kind == "contact":
        return ("A public Contact page (navbar provided). A two-column layout: "
                "LEFT = a detailed contact form (name, email, subject, department select, message, newsletter checkbox) with state tracking. Submitting handles e.preventDefault(), checks validation, and displays a beautiful success modal/card; "
                "RIGHT = contact detail cards (address, phone, support email, operating hours) each with an <Icon/> in an accent tile, followed by "
                "`<img src=\"assets/contact.jpg\" alt=\"\" className=\"rounded-2xl w-full h-48 object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />`.")
    if kind == "auth_login":
        shell = ((layouts or {}).get("auth") or {}).get("brief") or (
            "SPLIT-SCREEN, root `<div className=\"min-h-screen flex\">`: LEFT (hidden md:flex md:w-1/2, relative) brand panel - "
            "`<img src=\"assets/auth.jpg\" alt=\"\" className=\"absolute inset-0 w-full h-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />` "
            "+ dark gradient overlay + bottom content (relative z-10 p-10): app name, value line, small quote card. "
            "RIGHT (flex-1 flex items-center justify-center p-6) the form (max-w-sm w-full).")
        return ("A login page. PAGE SHELL (follow exactly):\n" + shell +
                "\nTHE FORM: a welcoming heading + muted subline, labeled email + password inputs, a remember-me checkbox row with a "
                "'Forgot password?' accent link (href='#'), and a full-width primary Login button. "
                "On submit: e.preventDefault(), validate non-empty (inline error message in state if invalid), then "
                "`localStorage.setItem('session', JSON.stringify({email, name: (email.split('@')[0] || 'User'), role:'" + (page.get('role') or 'User') + "'}))` and navigate('/dashboard'). "
                "Below the form a muted line with a Link to '/register'. The page must work standalone (no AppDB calls before submit).")
    if kind == "auth_register":
        shell = ((layouts or {}).get("auth") or {}).get("brief") or (
            "SPLIT-SCREEN, root `<div className=\"min-h-screen flex\">`: LEFT (hidden md:flex md:w-1/2, relative) brand panel - "
            "`<img src=\"assets/auth.jpg\" alt=\"\" className=\"absolute inset-0 w-full h-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />` "
            "+ dark gradient overlay + bottom content (relative z-10 p-10): app name, value line, 3-item benefits checklist. "
            "RIGHT (flex-1 flex items-center justify-center p-6) the form (max-w-sm w-full).")
        return ("A registration page matching the login design. PAGE SHELL (follow exactly):\n" + shell +
                "\nTHE FORM: heading + subline, labeled inputs (name, email, password, role select), an accept-terms checkbox, "
                "a full-width primary 'Create account' button. "
                "On submit: e.preventDefault(), validate (inline error state), then `localStorage.setItem('session', JSON.stringify({name, email, role}))` "
                "(the form's own values) and navigate('/dashboard'). Below the form a muted line with a Link to '/login'.")
    if kind == "dashboard":
        ents = all_entities or []
        if ents:
            tiles = "; ".join(
                f"{e.get('name')} (count = getRecords('{e.get('storage_key', e.get('name'))}').length, Link to /{slug_of(e.get('name'))})"
                for e in ents
            )
            first = ents[0]
            first_name = first.get("name")
            first_key = first.get("storage_key", first_name)
        else:
            tiles = "each data type"; first_name = "records"; first_key = "records"
        lay = (layouts or {}).get("dashboard")
        if lay:
            body = (lay["brief"]
                    .replace("__TILES__", tiles)
                    .replace("__FIRST_NAME__", str(first_name))
                    .replace("__FIRST_KEY__", str(first_key)))
            return ("A rich admin dashboard packed with real data widgets. " + body +
                    " COMMON RULES: a working notification-bell icon button in the header (clicking really toggles a small dropdown panel of 3 notification rows via state); "
                    "use the REAL entity names - NEVER generic 'Users/Posts/Comments'; every button/link must actually navigate or change visible state; "
                    "guard EVERY property read with optional chaining.")
        return (f"A rich, dashboard packed with content and widgets. "
                f"(1) Welcome header banner showing `window.AppDB.getCurrentUser()?.email`, today's date, and an active system status indicator (with a green pulsing dot). "
                f"(2) Top navigation bar widget inside page displaying simulated alert bell (clicking toggles a notification menu dropdown in React state). "
                f"(3) A responsive grid (`grid sm:grid-cols-2 lg:grid-cols-4 gap-6`) of analytics stat cards - ONE PER REAL ENTITY: {tiles}. Each card (Mantis admin style): a muted label, the LIVE count as a big bold number, a small trend pill (`rounded-full px-2 py-0.5 text-xs` accent-tinted, e.g. '+12.4%' with an up arrow - vary the fake percentages, one negative), a muted caption, and the whole card is a Link to its list route with hover shadow. "
                f"(3b) An 'Overview' chart card: a CSS BAR CHART of 12 labelled month bars (divs with hardcoded pixel heights via style, accent-colored, title-attribute tooltips) plus a small legend - next to a narrow 'This week' card with one big number, a trend pill and 5 mini bars (`grid lg:grid-cols-3 gap-6`, chart spans 2). "
                f"(4) A main two-column grid section: "
                f"  - LEFT: a 'Recent {first_name}' table listing the latest 5 records from `window.AppDB.getRecords('{first_key}')` with columns for name, date, and status pill badges. "
                f"  - RIGHT: a Quick Actions card with shortcut buttons linking to create routes AND an interactive Tasks/To-Do agenda list widget (where users can check off 4 items held in local state). "
                f"(5) A bottom analytics insights row containing 3 summary metrics cards with custom progress bars. Guard every property with optional chaining.")
    if kind == "list":
        return (f"A detailed list page for {entity}. Load once: `const [rows,setRows]=useState([]); useEffect(()=>setRows(window.AppDB.getRecords('{key}')||[]),[]);`. "
                f"Sections: "
                f"(1) A header row showing title, total records count badge, and a '+ Add New' button -> navigate('{list_path}/new'). "
                f"(2) A filter panel containing a search input AND status selection filter buttons (All, Active, Inactive, etc.), sorting dropdown (Newest, Oldest). "
                f"(3) A bulk actions bar containing checkboxes to select rows, and a Bulk Delete button. "
                f"(4) A themed table WRAPPED in `<div className=\"overflow-x-auto\">` for responsive scroll. Render columns [{cols}] with optional chaining. Each row has checkboxes, status badges, and action buttons: View (`localStorage.setItem('{sel}', row.id); navigate('{list_path}/detail')`), Edit (`localStorage.setItem('{sel}', row.id); navigate('{list_path}/edit')`), and Delete (`window.AppDB.deleteRecord('{key}', row.id); setRows(window.AppDB.getRecords('{key}')||[])`). "
                f"(5) Pagination controls at the bottom showing 'Page 1 of X', 'Previous' and 'Next' buttons, and rows-per-page selection dropdown. Show a beautiful empty state if no rows found.")
    if kind == "create":
        return (f"A step-by-step wizard style create form for {entity} with inputs for: {_fields_brief(form_fields)}. "
                f"Divide form into 2 visual steps (e.g. Step 1: Core details, Step 2: Options/Notes) with a progress indicator at the top. "
                f"Keep all fields inside one `formData` state object initialized with empty strings. "
                f"On submit: e.preventDefault(), perform required-field validations (if invalid, show prominent error alerts on screen), call `window.AppDB.createRecord('{key}', formData)` and navigate('{list_path}'). "
                f"Provide Back/Next buttons for steps, and a Cancel button navigating to '{list_path}'.")
    if kind == "edit":
        return (f"A structured edit form for {entity}. On mount: read `const id=localStorage.getItem('{sel}'); const rec=(window.AppDB.getRecords('{key}')||[]).find(r=>r?.id===id);` and set initial `formData` state from `rec` (guarded with optional chaining). "
                f"Divide the page into detailed configuration sections with section titles and helper texts. Inputs for: {_fields_brief(form_fields)}. "
                f"On submit: e.preventDefault(), validate inputs, call `window.AppDB.updateRecord('{key}', id, formData)`, and navigate('{list_path}'). "
                f"Cancel button navigates to '{list_path}/detail'. Include field validation error states in red.")
    if kind == "detail":
        return (f"A comprehensive multi-tab detail page for {entity}. Read `const id=localStorage.getItem('{sel}'); const rec=(window.AppDB.getRecords('{key}')||[]).find(r=>r?.id===id);`. If no record, show 'Not found' page with Back button. "
                f"Render: "
                f"(1) Header showing record title/name, and action buttons (Edit: navigate to edit route; Back: navigate to list route). "
                f"(2) Tab selection buttons: 'Overview', 'Detailed Activity', and 'Raw Data'. "
                f"(3) Tab 1 (Overview): shows every field [{cols}] organized in a 2-column grid card with labels and styled values. "
                f"(4) Tab 2 (Detailed Activity): displays a mock visual timeline feed showing 3 action steps (e.g. 'Record created by system', 'Assigned status', 'Last updated'). "
                f"(5) Tab 3 (Raw Data): shows a formatted read-only JSON code block of the record. Guard all reads.")
    if kind == "profile":
        return ("A professional user profile page. (1) Profile header card with large initials avatar, full email, and role badge. "
                "(2) Personal information card with read-only grids of phone, username, timezone, and department. "
                "(3) An interactive section tabs: 'Overview', 'Activity Logs', 'Security Settings'. "
                "(4) Activity list showing recent actions; settings tab showing security tips. Edit button navigates to settings.")
    if kind == "settings":
        return ("A settings dashboard with grouped tabs/sections: (1) General Settings (site title, default dashboard selection), "
                "(2) Notifications (toggle email alerts, push alerts, sms logs), (3) Security (update password inputs). "
                "(4) Hold all form state in local React state variables and show a success notification toast on click of 'Save Changes'. Purely visual, no backend.")
    if kind == "reports":
        ents = all_entities or []
        names = ", ".join(e.get("name") for e in ents) or "the data types"
        keys = [e.get("storage_key", e.get("name")) for e in ents]
        return (f"A rich, interactive reports & analytics dashboard covering {names}. "
                f"(1) Header with print report button, export CSV button (showing toast feedback), and a date-range filter dropdown (clicking updates report stats). "
                f"(2) A row of KPI cards showing counts of records for each entity using `window.AppDB.getRecords('KEY')` (using keys {keys}). "
                f"(3) Visual metric charts using pure Tailwind: "
                f"  - A horizontal bar graph comparison where each bar's width % is determined by the record count. "
                f"  - An SVG circular progress donut chart demonstrating database usage percentage. "
                f"  - An SVG line graph representation showing simulated trends. "
                f"(4) A summary breakdown data table list showing categories, counts, and completion rates. Guard all value reads.")
    if kind == "role_home":
        role = page.get("role", "User")
        ents = all_entities or []
        names = [e.get("name") for e in ents]
        keys = [e.get("storage_key", e.get("name")) for e in ents]
        return (f"A PERSONAL WORKSPACE page for the {role} role - what a {role} sees day-to-day (NOT a generic admin dashboard). "
                f"(1) A header: 'My Workspace' + a personalised greeting using `window.AppDB.getCurrentUser()?.name` and the {role} role badge. "
                f"(2) A 'Today' row of 3 summary cards RELEVANT to a {role}'s work in this app (pick the most relevant of {names}: e.g. items assigned to me, due today, completed - counts from `(window.AppDB.getRecords('KEY')||[]).length` using keys {keys}, with small captions). "
                f"(3) A 'My items' panel: a list of 4-6 rows from the most {role}-relevant entity (guarded `row?.field`), each row with a status pill and a working View button (set `localStorage['__sel_<key>']` + navigate to that entity's detail route). "
                f"(4) A personal SCHEDULE/AGENDA card: 4 time-slotted items for today held in local state, each with a working 'Done' toggle. "
                f"(5) A 'Quick actions' card with 2-3 working buttons navigating to the routes a {role} uses most. "
                f"Make the copy specifically about what a {role} does. Guard every read with optional chaining; every button must work.")
    if kind == "notifications":
        return ("A FULLY FUNCTIONAL notifications center. Hold 6-8 mock notifications in `useState` (each {id, icon, title, message, time, read:false|true, type}). "
                "(1) Header: title + live unread-count badge + a 'Mark all as read' button that really sets every item read. "
                "(2) Filter tabs 'All' / 'Unread' / 'System' that really filter the rendered list (active tab styled with the accent). "
                "(3) The list: each card shows an <Icon/> in a tinted tile, bold title, muted message + time, an unread accent dot when !read, "
                "a 'Mark read' button (sets that item read) and a dismiss 'x' button (removes the item from state). "
                "(4) When the filtered list is empty show a friendly empty state with an <Icon/>. EVERY control must visibly work.")
    if kind == "help":
        return ("A help center and FAQ page. (1) Large search searchbox input with help categories tiles grid (Account, billing, API, troubleshooting). "
                "(2) Accordion FAQ list of 5 questions: clicking a question smoothly expands its answer. "
                "(3) A support ticket contact card with textareas and a submit button showing toast feedback.")
    return page.get("description", "Render the page content with a header and a card.")
