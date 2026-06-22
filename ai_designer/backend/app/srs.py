"""SRS-JSON ingest: when the user pastes a Software Requirements Specification
JSON into the input (instead of a one-line prompt), THIS is the source of truth
and the generated app must fulfill it 100% - every entity becomes a CRUD
section, every role gets access, every public module becomes a page.

Handles the rich nested shape (srs_report -> data_model.entities / ui_pages /
functional_requirements / user_roles_and_permissions) but is defensive: any
missing branch degrades gracefully. json.loads(strict=False) tolerates the raw
newlines real SRS exports often contain inside string values.
"""
import json
import re

_PUBLIC_ROLE = {"guest", "public", "visitor", "anonymous", "everyone"}

# Auth/RBAC system tables. These describe the login+role system itself, which
# this codebase already generates via auth_required + _user_entity + the
# role-access layer - they never become separate manageable CRUD entities.
_AUTH_TABLE_NAMES = {"users", "user", "roles", "role", "permissions", "permission",
                     "role_permissions", "audit_logs", "audit_log", "sessions"}


def detect(prompt: str) -> bool:
    """Does the input contain an SRS JSON? (PDF-extracted text can have page
    headers around the JSON, so we look for the markers anywhere, not just at
    the start.)"""
    s = prompt or ""
    if "{" not in s:
        return False
    return any(k in s for k in ('"srs_report"', '"srs_document"', '"functional_requirements"',
                                '"data_model"', '"database_design"', '"user_roles_and_permissions"',
                                '"ui_pages"', '"project_title"', '"application_pages"',
                                '"role_access_matrix"', '"app_summary"'))


def _load(prompt: str):
    s = (prompt or "").strip()
    # extract the JSON object even when wrapped in PDF page headers / trailing text
    if "{" in s and "}" in s:
        s = s[s.index("{"):s.rindex("}") + 1]
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    try:
        return json.loads(s, strict=False)   # strict=False tolerates raw control chars
    except Exception:
        pass
    # PDF extraction injects page numbers / short header lines INTO the JSON
    # (e.g. ...enabled",\n1\n"View...). Drop standalone short lines and retry.
    s2 = re.sub(r"\n[ \t]*\d{1,3}[ \t]*\n", "\n", s)
    s2 = re.sub(r"\n[ \t]*(?:Page\s*\d+|[A-Z][\w &|/-]{0,60}SRS[\w &|/-]{0,40})[ \t]*\n", "\n", s2)
    try:
        return json.loads(s2, strict=False)
    except Exception:
        return None


def _label(name):
    return re.sub(r"[_\-]+", " ", str(name)).strip().title()


def _singularize_last_word(name):
    """Singularize ONLY the last underscore/space-separated segment of a SQL-style
    table name ("room_types" -> "room_type", "pos_order_items" -> "pos_order_item").
    Scoped to table_name input specifically (never applied to hand-authored SRS
    entity names like "Status") because every downstream collection-name pluralizer
    (data_model_planner._collection, mongoose_schema_generator._guess_collection)
    re-pluralizes the entity name - feeding it an already-plural "Hotels" produces
    a malformed "hotelses" collection name."""
    parts = re.split(r"[_\s-]+", str(name).strip())
    if not parts:
        return name
    last = parts[-1]
    low = last.lower()
    if low.endswith("ies") and len(last) > 3:
        last = last[:-3] + "y"
    elif low.endswith(("sses", "ches", "shes", "xes", "zes")) and len(last) > 4:
        last = last[:-2]   # classes->class, branches->branch, batches->batch, boxes->box
    elif low.endswith("s") and not low.endswith("ss") and len(last) > 1:
        last = last[:-1]   # warehouses->warehouse, houses->house, sales->sale
    parts[-1] = last
    return "_".join(parts)


def _pascal(name):
    s = str(name).strip()
    if re.search(r"[ _\-]", s):            # has separators -> title-case the words
        s = _label(s)
    s = re.sub(r"[^A-Za-z0-9]", "", s) or "Item"
    return s[:1].upper() + s[1:]           # single-word names (e.g. SQL table "hotels")
                                            # have no separator to trigger _label() above -
                                            # always capitalize the first letter regardless.


def _guess_type(fname, declared=""):
    n = str(fname).lower()
    d = str(declared).lower()
    opts = None
    if any(k in d for k in ("enum", "select", "status")) or n in ("status", "state", "stage", "type", "priority", "gender"):
        return "select", ["Active", "Pending", "Completed", "Cancelled"]
    if any(k in d for k in ("date", "time", "datetime")) or any(k in n for k in ("date", "_at", "dob", "deadline", "_on", "time")):
        return "date", None
    if any(k in d for k in ("int", "number", "decimal", "float", "money", "currency")) or any(
            k in n for k in ("price", "amount", "total", "cost", "fee", "qty", "quantity", "count", "age", "number", "balance", "rate", "score")):
        return "number", None
    if "email" in n or "email" in d:
        return "email", None
    if any(k in n for k in ("description", "notes", "summary", "details", "address", "message", "comment", "bio")) or "textarea" in d:
        return "textarea", None
    return "text", opts


def _norm_fields(raw_fields):
    out = []
    for f in (raw_fields or []):
        required = False
        explicit_opts = None
        if isinstance(f, str):
            name = f
            declared = ""
        elif isinstance(f, dict):
            name = f.get("name") or f.get("field_name") or f.get("field") or ""
            declared = f.get("type") or f.get("data_type") or ""
            if f.get("primary_key") or str(declared).lower() in ("foreign_key", "fk"):
                continue   # PKs are implicit; FKs become relationships, not form fields
            # absent "nullable" defaults to NOT-nullable (required) - standard SQL
            # convention, and how this SRS shape itself uses the field (it only sets
            # nullable:true on genuinely optional columns).
            required = not bool(f.get("nullable", False))
            if str(declared).lower() == "enum" and f.get("values"):
                explicit_opts = [str(v) for v in f["values"]]
        else:
            continue
        name = re.sub(r"[^a-z0-9_]", "", str(name).strip().lower().replace(" ", "_"))
        if not name or name in ("id", "_id", "created_at", "updated_at"):
            continue
        if explicit_opts:
            t, opts = "select", explicit_opts
        else:
            t, opts = _guess_type(name, declared)
        out.append({"name": name, "label": _label(name), "type": t, "options": opts, "required": required, "form": True})
        if len(out) >= 30:
            break
    return out or [{"name": "name", "label": "Name", "type": "text", "options": None, "required": False, "form": True}]


def layout_for(entity: dict) -> str:
    """Pick a CRUD layout from an entity's shape (SRS doesn't specify one)."""
    fields = entity.get("fields", [])
    names = " ".join(f.get("name", "") for f in fields) + " " + str(entity.get("name", "")).lower()
    types = [f.get("type") for f in fields]
    # money / numeric records -> spreadsheet (before kanban: an invoice with a
    # status is still fundamentally a numbers grid)
    if types.count("number") >= 2 or any(k in names for k in ("amount", "price", "total", "invoice", "bill", "payment", "salary", "budget")):
        return "spreadsheet"
    # time-series / logs -> timeline (an appointment is time-based even with a status)
    if "date" in types or any(k in names for k in ("log", "history", "appointment", "schedule", "audit", "event", "booking", "visit", "transaction")):
        return "timeline"
    # workflow with a status/select -> kanban
    if any(f.get("type") == "select" for f in fields) or "status" in names:
        return "kanban"
    if len(fields) >= 5:
        return "split-pane"
    return "table"


def _page_template(name: str) -> str:
    n = name.lower()
    if "contact" in n or "inquiry" in n or "enquiry" in n:
        return "contact"
    if any(k in n for k in ("pricing", "package", "plan", "fee", "tariff")):
        return "pricing"
    if any(k in n for k in ("gallery", "doctor", "department", "service", "facilit", "team", "menu", "product", "listing", "course", "room")):
        return "gallery"
    if any(k in n for k in ("about", "news", "blog", "story", "mission", "emergency", "faq", "info")):
        return "content"
    return "features"


_PAGE_STOP = {"page", "website", "public", "with", "your", "our", "the", "and", "for", "us"}


def _public_pages(d: dict) -> list:
    pages, seen, token_sets = [], set(), []

    def add(name):
        name = re.sub(r"^FR[-\s]*\d+\s*[:\-]?\s*", "", str(name)).strip()
        name = re.sub(r"[^A-Za-z0-9 &/-]", "", name).strip()
        name = re.sub(r"^(public website|website|page)\s*[-:]\s*", "", name, flags=re.I).strip()
        if not name or name.lower() in ("home", "homepage", "landing", "index", "login", "register", "sign in", "sign up"):
            return
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24]
        if not slug or slug in seen:
            return
        # collapse near-duplicates (e.g. "Services & Rates" vs "Services and
        # Rates", or two contact pages) by significant-word overlap.
        toks = {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", name.lower()) if w not in _PAGE_STOP}
        if toks and any(toks & prev for prev in token_sets):
            return
        seen.add(slug)
        token_sets.append(toks)
        pages.append({"name": name[:28], "slug": slug, "template": _page_template(name)})

    # explicit UI pages (older shape) + this shape's public_landing_website.pages
    explicit_pages = (d.get("ui_pages") or d.get("pages")
                      or (d.get("public_landing_website") or {}).get("pages") or [])
    for p in explicit_pages:
        if not isinstance(p, dict):
            continue
        path = str(p.get("path") or p.get("route") or "")
        if any(seg in path.lower() for seg in ("/admin", "/dashboard", "/portal", "/staff", "/api")):
            continue
        nm = p.get("name") or p.get("title") or p.get("page_name") or p.get("purpose") or path.strip("/").replace("-", " ")
        add(nm)
    # public-website functional requirements (only when individually titled -
    # a bare module/group name like "Public Website" is a feature *area*,
    # not a page name, and must not be fabricated into a fake page)
    for fr in (d.get("functional_requirements") or []):
        if not isinstance(fr, dict):
            continue
        title = str(fr.get("title") or fr.get("name") or "")
        module = str(fr.get("module") or fr.get("group") or "")
        if title and ("public" in module.lower() or "public website" in title.lower()):
            add(title)
    return pages[:12]


def _split_table_field(s):
    """'reservations.guest_id' -> ('reservations', 'guest_id'); 'guests.id' -> ('guests', 'id')."""
    s = str(s or "").strip()
    if "." in s:
        tbl, fld = s.rsplit(".", 1)
        return tbl.strip(), fld.strip()
    return s, ""


_CARDINALITY_MAP = {
    "many_to_one": "many-to-one", "one_to_many": "one-to-many",
    "many_to_many": "many-to-many", "one_to_one": "one-to-one",
}


def _map_cardinality(t):
    return _CARDINALITY_MAP.get(str(t or "").strip().lower(), str(t or "many-to-one").replace("_", "-"))


# ----- entity <-> page/function text matching (substring/keyword, no NLP dep) ----- #

_VERB_CREATE = ("create", "add", "new", "register", "book", "submit")
_VERB_UPDATE = ("edit", "update", "change", "assign", "process", "manage", "record",
                "upload", "check-in", "check in", "check-out", "check out", "approve", "confirm")
_VERB_DELETE = ("delete", "remove", "cancel", "void", "deactivate")
_ACCESS_STOPWORDS = {"the", "and", "for", "with", "your", "page", "view", "management", "system"}


def _classify_verb(text):
    t = str(text).strip().lower()
    if any(t.startswith(v) for v in _VERB_DELETE):
        return ("delete",)
    if any(t.startswith(v) for v in _VERB_CREATE):
        return ("create",)
    if any(t.startswith(v) for v in _VERB_UPDATE):
        return ("update",)
    return ("create", "update", "delete")


def _entity_match_info(name, table):
    """Match tokens for an entity: words from its name + its raw table name,
    singularized, plus the full multi-word phrase for disambiguating siblings
    (e.g. Room vs RoomType on the same "Room Management" page)."""
    raw = re.findall(r"[a-zA-Z]+", str(table or name))
    singular = [(w[:-1] if w.lower().endswith("s") and not w.lower().endswith("ss") else w).lower() for w in raw]
    tokens = {w for w in singular if len(w) >= 4 and w not in _ACCESS_STOPWORDS}
    phrase = " ".join(singular)
    return tokens, phrase


def _text_mentions_entity(haystack, tokens, phrase):
    haystack = str(haystack or "").lower()
    if len(phrase.split()) > 1 and phrase in haystack:
        return True
    return any(re.search(r"\b" + re.escape(t) + r"\b", haystack) for t in tokens)


def _build_entity_access(entities, app_pages, role_matrix):
    """Map application_pages[].allowed_roles + role_access_matrix[].allowed_functions
    onto each entity's access dict, by matching entity name/table tokens against
    page names and their function descriptions. Entities matching nothing get no
    access key at all (the existing, already-wired convention: no entry = open
    to everyone)."""
    access_map = {}
    infos = {e["name"]: _entity_match_info(e["name"], e.get("_table")) for e in entities}

    def grant(name, verbs, roles):
        if not roles:
            return
        acc = access_map.setdefault(name, {})
        for v in tuple(verbs) + ("read",):
            lst = acc.setdefault(v, [])
            for rn in roles:
                if rn not in lst:
                    lst.append(rn)

    for page in (app_pages or []):
        roles = page.get("allowed_roles") or []
        if not roles:
            continue
        functions = page.get("functions") or []
        page_name = page.get("name") or ""
        for ename, (tokens, phrase) in infos.items():
            matched_any = False
            for fn in functions:
                if _text_mentions_entity(fn, tokens, phrase):
                    grant(ename, _classify_verb(fn), roles)
                    matched_any = True
            if not matched_any and _text_mentions_entity(page_name, tokens, phrase):
                grant(ename, ("create", "update", "delete"), roles)

    for rm in (role_matrix or []):
        role = rm.get("role")
        if not role:
            continue
        for fn in (rm.get("allowed_functions") or []):
            for ename, (tokens, phrase) in infos.items():
                if _text_mentions_entity(fn, tokens, phrase):
                    grant(ename, _classify_verb(fn), [role])

    return access_map


def parse_srs_input(prompt: str):
    """Return a normalized structure when the input is an SRS JSON, else None."""
    if not detect(prompt):
        return None
    obj = _load(prompt)
    if not isinstance(obj, dict):
        return None
    d = obj.get("srs_document") or obj.get("srs_report") or obj.get("srs") or obj
    if not isinstance(d, dict):
        d = obj

    # app_summary.app_name is the intended display name when present (often
    # shorter/cleaner than project_name, which tends to be a longer formal
    # document title, e.g. "AutoHub Vehicle Business Platform" vs project_name's
    # "AutoHub Vehicle Sales, Rental, Service and Spare Parts Platform").
    app_name = ((d.get("app_summary") or {}).get("app_name") or d.get("system_name")
                or d.get("project_title") or d.get("project_name") or obj.get("project_title") or "App")
    app_name = str(app_name)[:60]

    # roles (login roles only - Guest/Public means the public site). Two shapes:
    # old = list of names/{"role": name}; new = list of {role_key, role_name, description}.
    # Canonical identity is role_name (human-readable) - it's already what every
    # curated domain uses as both display AND comparison value everywhere downstream
    # (sidebar, session, register-page role cards, canAccess()). role_key is kept
    # only as a lookup so application_pages/role_access_matrix's snake_case
    # allowed_roles can be translated to the same vocabulary as `roles` below.
    roles, key_to_name = [], {}
    raw_roles = d.get("user_roles_and_permissions") or d.get("roles") or []
    for r in raw_roles:
        if isinstance(r, dict):
            nm = r.get("role_name") or r.get("role") or r.get("name")
            key = r.get("role_key") or nm
        else:
            nm = key = r
        if not nm:
            continue
        nm = str(nm)[:50]
        if key:
            key_to_name[str(key).lower()] = nm
            key_to_name[str(key).lower().replace("_", " ")] = nm
        if str(nm).lower() not in _PUBLIC_ROLE and nm not in roles:
            roles.append(nm)
    if not roles:
        for s in (d.get("stakeholders") or []):
            nm = s.get("name") if isinstance(s, dict) else s
            if nm and str(nm).lower() not in _PUBLIC_ROLE:
                roles.append(str(nm)[:50])
    roles = roles or ["Admin", "User"]

    def _role_name(key):
        k = str(key or "").strip()
        return key_to_name.get(k.lower(), k)

    # entities: data_model.entities (old) or database_design.tables (new). Auth/RBAC
    # tables are excluded - they describe the login+role system this codebase already
    # generates, not a manageable business entity.
    ents = []
    fk_rels = []   # relationships derived directly from each table's own foreign_key
                   # fields - unambiguous direction (the field's own table always
                   # holds the FK) and far more complete than any curated/highlighted
                   # relationships list, which this SRS shape's "database_design.
                   # relationships" turns out to be (most real FKs aren't in it).
    dm = d.get("data_model") or {}
    db_design = d.get("database_design") or {}
    raw_ents = (dm.get("entities") if isinstance(dm, dict) else None) or db_design.get("tables") or d.get("entities") or []
    for e in raw_ents:
        if not isinstance(e, dict):
            continue
        nm = e.get("name") or e.get("entity") or e.get("title") or e.get("table_name")
        if not nm:
            continue
        table = str(e.get("table_name") or nm).strip().lower()
        if table in _AUTH_TABLE_NAMES or table.rstrip("s") in _AUTH_TABLE_NAMES:
            continue
        # SQL-style table_name is plural by convention - singularize before
        # pascal-casing so downstream collection pluralizers don't double-pluralize
        # ("Hotels" -> collection "hotelses"). Names from name/entity/title are
        # hand-authored SRS entity names and may already be correctly singular
        # ("Status") - only table_name is safe to assume-and-singularize.
        if e.get("table_name") and not (e.get("name") or e.get("entity") or e.get("title")):
            nm = _singularize_last_word(nm)
        raw_fields = e.get("fields") or e.get("attributes") or e.get("columns") or []
        for rf in raw_fields:
            if not (isinstance(rf, dict) and str(rf.get("type") or "").lower() in ("foreign_key", "fk")):
                continue
            ref_table, ref_field = _split_table_field(rf.get("references"))
            if not ref_table:
                continue
            fk_rels.append({
                "from_table": table, "from_field": str(rf.get("name") or ""),
                "to_table": ref_table.lower(), "to_field": ref_field or "id",
                "type": "many-to-one",
                "description": f"{table}.{rf.get('name')} references {ref_table}.{ref_field or 'id'}",
            })
        fields = _norm_fields(raw_fields)
        ent = {"name": _pascal(nm), "label": _label(nm), "storage_key": _pascal(nm),
               "fields": fields, "_table": table}
        ent["crud_layout"] = layout_for(ent)
        ents.append(ent)
        if len(ents) >= 60:
            break

    # key features from FR titles/requirements + objectives. The srs_document
    # format uses "requirement" as the text field; older formats use "title".
    feats = []
    for fr in (d.get("functional_requirements") or []):
        if isinstance(fr, dict):
            # try title, then requirement (srs_document format), then module+requirement
            t = (fr.get("title") or fr.get("requirement") or
                 (str(fr.get("module") or "") + ": " + str(fr.get("requirement") or "")).strip(": "))
        else:
            t = fr
        if t:
            t = re.sub(r"^FR[-\s]*\d+\s*[:\-]?\s*", "", str(t)).strip()
            if t and t not in feats:
                feats.append(t[:60])
    ov = d.get("project_overview") or {}
    for o in (ov.get("main_objectives") or d.get("main_objectives") or []):
        if o and str(o)[:60] not in feats:
            feats.append(str(o)[:60])
    feats = feats[:10]

    pages = _public_pages(d)
    if not any(p["template"] == "contact" for p in pages):
        pages.append({"name": "Contact", "slug": "contact", "template": "contact"})

    # Extract full public pages with section lists from public_landing_website
    srs_public_pages = []
    plw = d.get("public_landing_website") or {}
    for p in (plw.get("pages") or []):
        if not isinstance(p, dict):
            continue
        route = str(p.get("route") or "").strip()
        page_name = str(p.get("page_name") or p.get("name") or "").strip()
        sections = p.get("sections") or []
        if page_name and sections:
            srs_public_pages.append({
                "name": page_name,
                "route": route,
                "sections": [str(s) for s in sections],
                "login_required": bool(p.get("login_required")),
            })

    # system_category is the richest domain signal in srs_document format
    system_category = str(d.get("system_category") or "").strip()
    domain = (system_category or str(d.get("scope_type") or d.get("project_title") or app_name)).split("+")[0].strip()[:80]

    # main_modules - flat list of module names for sidebar structure
    main_modules = []
    for m in (d.get("main_modules") or []):
        nm = str(m.get("module_name") or m.get("name") or m).strip() if isinstance(m, dict) else str(m).strip()
        if nm:
            main_modules.append(nm[:60])

    # authentication_requirement - config flags (2FA, guest booking, password policy, etc.)
    auth_req = d.get("authentication_requirement") or {}

    # app_type - recommended tech stack (informational; we use Next.js anyway)
    app_type_info = d.get("app_type") or {}

    # business_workflows - step-by-step flows mapped to entity workflow_rules
    raw_workflows = d.get("business_workflows") or []
    business_workflows = []
    for wf in raw_workflows:
        if not isinstance(wf, dict):
            continue
        wf_name = str(wf.get("workflow_name") or wf.get("name") or "")[:80]
        steps = [str(s)[:120] for s in (wf.get("steps") or [])][:15]
        if wf_name or steps:
            business_workflows.append({"name": wf_name, "steps": steps})

    # validation_rules - field-level rules for form generation
    validation_rules = []
    for vr in (d.get("validation_rules") or []):
        if isinstance(vr, dict):
            validation_rules.append({
                "field": str(vr.get("field") or "")[:40],
                "rule": str(vr.get("rule") or vr.get("description") or "")[:200],
            })
        elif isinstance(vr, str) and vr:
            validation_rules.append({"field": "", "rule": str(vr)[:200]})

    # non_functional_requirements - performance / scalability / reliability metadata
    # srs_document format: list of {id, category, requirement} dicts
    nfr_raw = d.get("non_functional_requirements") or {}
    if isinstance(nfr_raw, list):
        # extract requirement text from each item (handles {id, category, requirement} shape)
        non_functional_requirements = {}
        for item in nfr_raw:
            if isinstance(item, dict):
                cat = str(item.get("category") or item.get("type") or "nfr")
                req = str(item.get("requirement") or item.get("description") or "")[:120]
                if req:
                    non_functional_requirements.setdefault(cat, req)
            elif isinstance(item, str):
                non_functional_requirements[str(len(non_functional_requirements))] = item[:120]
    elif isinstance(nfr_raw, dict):
        non_functional_requirements = {k: str(v)[:120] for k, v in nfr_raw.items()}
    else:
        non_functional_requirements = {}

    # api_requirements - API endpoints or external integrations
    # srs_document format: dict of {category: [endpoint, ...]} OR list of {api_name, purpose}
    api_req_raw = d.get("api_requirements") or []
    api_requirements = []
    if isinstance(api_req_raw, dict):
        # flatten each category's endpoints into a list of {name, purpose} objects
        for category, endpoints in api_req_raw.items():
            if isinstance(endpoints, list):
                for ep in endpoints[:10]:
                    api_requirements.append({"name": str(category)[:30], "purpose": str(ep)[:120]})
            else:
                api_requirements.append({"name": str(category)[:60], "purpose": str(endpoints)[:120]})
    else:
        for ar in api_req_raw:
            if isinstance(ar, dict):
                api_requirements.append({
                    "name": str(ar.get("api_name") or ar.get("name") or "")[:60],
                    "purpose": str(ar.get("purpose") or ar.get("description") or "")[:120],
                })
            elif isinstance(ar, str) and ar:
                api_requirements.append({"name": "", "purpose": str(ar)[:120]})

    # reporting_requirements - report page stubs
    reporting_requirements = []
    for rr in (d.get("reporting_requirements") or []):
        if isinstance(rr, dict):
            reporting_requirements.append({
                "name": str(rr.get("report_name") or rr.get("name") or "")[:60],
                "filters": [str(f)[:40] for f in (rr.get("filters") or [])][:8],
                "accessible_by": [str(r)[:30] for r in (rr.get("accessible_by") or [])],
            })
        elif isinstance(rr, str) and rr:
            reporting_requirements.append({"name": str(rr)[:60], "filters": [], "accessible_by": []})

    # notification_requirements - event-driven notification events
    notification_requirements = []
    for nr in (d.get("notification_requirements") or []):
        if isinstance(nr, dict):
            notification_requirements.append({
                "event": str(nr.get("event") or nr.get("trigger") or "")[:80],
                "channels": [str(c)[:20] for c in (nr.get("channels") or [])],
                "recipients": [str(r)[:30] for r in (nr.get("recipients") or [])],
                "message": str(nr.get("message") or nr.get("description") or "")[:120],
            })
        elif isinstance(nr, str) and nr:
            notification_requirements.append({"event": str(nr)[:80], "channels": [], "recipients": [], "message": ""})

    # security_requirements - security controls list
    sec_raw = d.get("security_requirements") or []
    if isinstance(sec_raw, list):
        security_requirements = [str(s)[:120] for s in sec_raw if s]
    elif isinstance(sec_raw, dict):
        security_requirements = [f"{k}: {v}" for k, v in sec_raw.items()]
    else:
        security_requirements = []

    # ui_ux_requirements - design guidance (design_style, dashboard_layout, pos_layout, etc.)
    ux_raw = d.get("ui_ux_requirements") or {}
    if isinstance(ux_raw, dict):
        ui_ux_requirements = {k: (bool(v) if isinstance(v, bool) else str(v)[:200]) for k, v in ux_raw.items()}
    else:
        ui_ux_requirements = {}

    # acceptance_criteria - QA checklist
    ac_raw = d.get("acceptance_criteria") or []
    if isinstance(ac_raw, list):
        acceptance_criteria = [str(c)[:120] for c in ac_raw if c]
    elif isinstance(ac_raw, dict):
        acceptance_criteria = [f"{k}: {v}" for k, v in ac_raw.items()]
    else:
        acceptance_criteria = []

    # future_enhancements - planned future features
    fe_raw = d.get("future_enhancements") or []
    if isinstance(fe_raw, list):
        future_enhancements = [str(e)[:100] for e in fe_raw if e]
    elif isinstance(fe_raw, dict):
        future_enhancements = [f"{k}: {v}" for k, v in fe_raw.items()]
    else:
        future_enhancements = []

    terminology = [e["label"] for e in ents] + [r for r in roles]

    # relationships: FK-field-derived ones (unambiguous, the field's own table
    # always holds the FK) are primary and already collected as fk_rels above.
    # The explicit array is secondary/supplementary - it's inconsistent about
    # which side is "from" depending on cardinality (a "many_to_one" entry puts
    # the FK-holder on "from"; a "one_to_many" entry puts it on "to" instead, e.g.
    # {"from":"hotels.id","to":"room_types.hotel_id","type":"one_to_many"} means
    # room_types HOLDS the FK, not hotels) - normalize that here so every
    # relationship dict consistently has from_table/from_field as the FK holder.
    rels = list(fk_rels)
    seen_fk = {(r["from_table"], r["from_field"]) for r in rels}
    dm_rels = (dm if isinstance(dm, dict) else {}).get("relationships") or db_design.get("relationships") or d.get("relationships") or []
    for r in dm_rels:
        if not isinstance(r, dict):
            continue
        frm = str(r.get("from") or r.get("source") or "").strip()
        to = str(r.get("to") or r.get("target") or "").strip()
        if not (frm and to):
            continue
        cardinality = _map_cardinality(r.get("type") or r.get("cardinality"))
        a_table, a_field = _split_table_field(frm)
        b_table, b_field = _split_table_field(to)
        if cardinality == "one-to-many":
            # the "many" (FK-holding) side is "to" here, not "from"
            from_table, from_field, to_table, to_field = b_table, b_field, a_table, a_field
            cardinality = "many-to-one"
        else:
            from_table, from_field, to_table, to_field = a_table, a_field, b_table, b_field
        from_table, to_table = from_table.lower(), to_table.lower()
        if (from_table, from_field) in seen_fk or cardinality == "many-to-many":
            continue   # many-to-many needs a join entity, not a direct ref - skip rather than guess
        seen_fk.add((from_table, from_field))
        rels.append({
            "from": frm, "to": to, "from_table": from_table, "from_field": from_field,
            "to_table": to_table, "to_field": to_field, "type": cardinality,
            "description": str(r.get("description") or r.get("label") or "").strip(),
        })
        if len(rels) >= 60:
            break

    # application_pages: role-gated internal/admin pages (route, allowed_roles,
    # functions) - the actual role -> page -> function authority this SRS shape
    # provides, used by data_model_planner to build per-entity access.
    app_pages = []
    for p in (d.get("application_pages") or []):
        if not isinstance(p, dict):
            continue
        app_pages.append({
            "name": str(p.get("page_name") or p.get("name") or "")[:60],
            "route": str(p.get("route") or "")[:80],
            "page_type": str(p.get("page_type") or "")[:30],
            "login_required": bool(p.get("login_required", True)),
            "allowed_roles": [_role_name(x) for x in (p.get("allowed_roles") or [])],
            "functions": [str(x)[:80] for x in (p.get("functions") or [])][:20],
        })
        if len(app_pages) >= 60:
            break

    # role_access_matrix: per-role allowed/restricted functions, corroborates
    # application_pages for the access heuristic.
    role_matrix = []
    for rm in (d.get("role_access_matrix") or []):
        if not isinstance(rm, dict):
            continue
        role_matrix.append({
            "role": _role_name(rm.get("role")),
            "allowed_pages": [str(x) for x in (rm.get("allowed_pages") or [])],
            "allowed_functions": [str(x)[:80] for x in (rm.get("allowed_functions") or [])][:30],
            "restricted_functions": [str(x)[:80] for x in (rm.get("restricted_functions") or [])][:30],
        })

    entity_access = _build_entity_access(ents, app_pages, role_matrix)

    # Build a rich research query from system_category + app_name (more specific
    # than just domain, so deep_research finds the right sector-specific sites).
    query = (system_category or (domain + " " + app_name)).strip()[:80]

    return {
        # Core planning data (all already-working sections)
        "app_name": app_name,
        "domain": domain,
        "system_category": system_category,
        "roles": roles,
        "entities": ents or [{"name": "Record", "label": "Records", "storage_key": "Record",
                              "fields": _norm_fields(["name", "status", "notes"]), "crud_layout": "table"}],
        "relationships": rels,
        "marketing_pages": pages,
        "srs_public_pages": srs_public_pages,
        "key_features": feats,
        "terminology": terminology[:12],
        "image_subjects": [],
        "query": query,
        "app_pages": app_pages,
        "role_access_matrix": role_matrix,
        "entity_access": entity_access,
        # Newly extracted sections (wired into data_model_planner + blueprint)
        "main_modules": main_modules,
        "authentication_requirement": auth_req,
        "app_type": app_type_info,
        "business_workflows": business_workflows,
        "validation_rules": validation_rules,
        "non_functional_requirements": non_functional_requirements,
        "api_requirements": api_requirements,
        "reporting_requirements": reporting_requirements,
        "notification_requirements": notification_requirements,
        "security_requirements": security_requirements,
        "ui_ux_requirements": ui_ux_requirements,
        "acceptance_criteria": acceptance_criteria,
        "future_enhancements": future_enhancements,
    }
