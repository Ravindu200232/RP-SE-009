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


def detect(prompt: str) -> bool:
    """Does the input contain an SRS JSON? (PDF-extracted text can have page
    headers around the JSON, so we look for the markers anywhere, not just at
    the start.)"""
    s = prompt or ""
    if "{" not in s:
        return False
    return any(k in s for k in ('"srs_report"', '"functional_requirements"', '"data_model"',
                                '"user_roles_and_permissions"', '"ui_pages"', '"project_title"'))


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


def _pascal(name):
    s = str(name).strip()
    if re.search(r"[ _\-]", s):            # has separators -> title-case the words
        s = _label(s)
    return re.sub(r"[^A-Za-z0-9]", "", s) or "Item"


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
    if any(k in n for k in ("description", "notes", "summary", "details", "address", "message", "comment", "bio")) or "text" in d:
        return "textarea", None
    return "text", opts


def _norm_fields(raw_fields):
    out = []
    for f in (raw_fields or []):
        if isinstance(f, str):
            name = f
            declared = ""
        elif isinstance(f, dict):
            name = f.get("name") or f.get("field_name") or f.get("field") or ""
            declared = f.get("type") or f.get("data_type") or ""
        else:
            continue
        name = re.sub(r"[^a-z0-9_]", "", str(name).strip().lower().replace(" ", "_"))
        if not name or name in ("id", "_id", "created_at", "updated_at"):
            continue
        t, opts = _guess_type(name, declared)
        out.append({"name": name, "label": _label(name), "type": t, "options": opts, "required": False, "form": True})
        if len(out) >= 8:
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

    # explicit UI pages
    for p in (d.get("ui_pages") or d.get("pages") or []):
        if not isinstance(p, dict):
            continue
        path = str(p.get("path") or p.get("route") or "")
        if any(seg in path.lower() for seg in ("/admin", "/dashboard", "/portal", "/staff", "/api")):
            continue
        nm = p.get("name") or p.get("title") or p.get("purpose") or path.strip("/").replace("-", " ")
        add(nm)
    # public-website functional requirements
    for fr in (d.get("functional_requirements") or []):
        if not isinstance(fr, dict):
            continue
        title = str(fr.get("title") or fr.get("name") or "")
        module = str(fr.get("module") or fr.get("group") or "")
        if "public" in module.lower() or "public website" in title.lower():
            add(title or module)
    return pages[:6]


def parse_srs_input(prompt: str):
    """Return a normalized structure when the input is an SRS JSON, else None."""
    if not detect(prompt):
        return None
    obj = _load(prompt)
    if not isinstance(obj, dict):
        return None
    d = obj.get("srs_report") or obj.get("srs") or obj
    if not isinstance(d, dict):
        d = obj

    app_name = (d.get("system_name") or d.get("project_title") or obj.get("project_title") or "App")
    app_name = str(app_name)[:40]

    # roles (login roles only - Guest/Public means the public site)
    roles = []
    for r in (d.get("user_roles_and_permissions") or []):
        nm = r.get("role") if isinstance(r, dict) else r
        if nm and str(nm).lower() not in _PUBLIC_ROLE and str(nm) not in roles:
            roles.append(str(nm)[:24])
    if not roles:
        for s in (d.get("stakeholders") or []):
            nm = s.get("name") if isinstance(s, dict) else s
            if nm and str(nm).lower() not in _PUBLIC_ROLE:
                roles.append(str(nm)[:24])
    roles = roles[:6] or ["Admin", "User"]

    # entities from the data model
    ents = []
    dm = d.get("data_model") or {}
    raw_ents = dm.get("entities") if isinstance(dm, dict) else None
    raw_ents = raw_ents or d.get("entities") or []
    for e in raw_ents:
        if not isinstance(e, dict):
            continue
        nm = e.get("name") or e.get("entity") or e.get("title")
        if not nm:
            continue
        fields = _norm_fields(e.get("fields") or e.get("attributes") or e.get("columns"))
        ent = {"name": _pascal(nm), "label": _label(nm), "storage_key": _pascal(nm), "fields": fields}
        ent["crud_layout"] = layout_for(ent)
        ents.append(ent)
        if len(ents) >= 8:
            break

    # key features from FR titles + objectives
    feats = []
    for fr in (d.get("functional_requirements") or []):
        t = fr.get("title") if isinstance(fr, dict) else fr
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

    domain = str(d.get("scope_type") or d.get("project_title") or app_name).split("+")[0].strip()[:30]
    terminology = [e["label"] for e in ents] + [r for r in roles]

    return {
        "app_name": app_name,
        "domain": domain,
        "roles": roles,
        "entities": ents or [{"name": "Record", "label": "Records", "storage_key": "Record",
                              "fields": _norm_fields(["name", "status", "notes"]), "crud_layout": "table"}],
        "marketing_pages": pages[:6],
        "key_features": feats,
        "terminology": terminology[:12],
        "image_subjects": [],
        "query": (domain + " " + str(d.get("scope_type") or "")).strip()[:80],
    }
