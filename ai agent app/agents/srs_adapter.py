"""
agents/srs_adapter.py — ingest a structured SRS JSON into locode's internal spec.

A user can hand locode a full SRS (the "AutoHub" shape: app_summary, roles, pages,
database_design.collections, api_requirements.route_groups, seed_data_requirements).
This adapter maps it DETERMINISTICALLY to the spec the pipeline already consumes — no
LLM guessing. Anything the SRS doesn't specify falls back to sensible defaults.

The internal spec keys produced here mirror what refiner._build_spec emits, plus
`kits` (matched backend behaviours) and richer field/collection metadata.
"""
from __future__ import annotations

import re


# ── field-string parsing ──────────────────────────────────────────────────────

_TYPE_WORDS = {
    "string": "String", "text": "String", "number": "Number", "int": "Number",
    "float": "Number", "boolean": "Boolean", "bool": "Boolean", "date": "Date",
    "datetime": "Date", "objectid": "ObjectId", "mixed": "Mixed",
}


def _singularize(name: str) -> str:
    """SRS collection names are plural (vehicles, vehicleSales); models are singular."""
    n = str(name)
    if n.endswith("ies"):
        return n[:-3] + "y"
    if n.endswith(("ses", "xes", "ches", "shes")):
        return n[:-2]
    if n.endswith("s") and not n.endswith("ss"):
        return n[:-1]
    return n


def _pascal(name: str, singular: bool = False) -> str:
    if singular:
        name = _singularize(str(name))
    parts = re.split(r"[^A-Za-z0-9]+", str(name))
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Item"


def parse_field(fname: str, spec_str) -> dict:
    """Parse an AutoHub field spec string like
    'ObjectId ref vehicles required' / 'enum: a | b | c' / 'string array max 6'
    / 'number default 0 min 0' into a locode field dict."""
    s = str(spec_str).strip()
    low = s.lower()
    field: dict = {"name": fname}

    # enum — accepts every AutoHub/user spelling: "enum: a | b | c" (colon),
    # "enum a | b | c" (space, the user's SRS style), or bare "enum" (String,
    # no fixed values). Trailing flag words are stripped so they never leak into
    # the last value. A colon-less bare "enum" must NOT swallow a following type
    # word, so the word "enum" must stand alone or be followed by ':'/values.
    m = re.match(r"enum\b\s*:?\s*(.*)$", s, re.IGNORECASE)
    if m:
        field["type"] = "String"
        vals = []
        for v in re.split(r"\|", m.group(1)):
            v = re.sub(r"\b(required|unique|optional|indexed?)\b", "", v,
                       flags=re.IGNORECASE).strip()
            if v:
                vals.append(v)
        if vals:
            field["enum"] = vals
            field["default"] = vals[0]
        return _flags(field, low)

    # array: "string array", "string array max 6", "ObjectId array"
    if "array" in low:
        base = "String"
        for w, t in _TYPE_WORDS.items():
            if low.startswith(w):
                base = t
                break
        field["type"] = f"[{base}]"
        mx = re.search(r"max\s+(\d+)", low)
        if mx:
            field["max"] = int(mx.group(1))
        return _flags(field, low)

    # ObjectId ref <collection>
    if low.startswith("objectid"):
        field["type"] = "ObjectId"
        rm = re.search(r"ref\s+(\w+)", low)
        if rm:
            field["ref"] = _pascal(rm.group(1), singular=True)
        return _flags(field, low)

    # scalar types
    for w, t in _TYPE_WORDS.items():
        if re.search(rf"\b{w}\b", low):
            field["type"] = t
            break
    field.setdefault("type", "String")

    # default value
    dm = re.search(r"default\s+([^\s]+)", low)
    if dm:
        raw = dm.group(1)
        if field["type"] == "Number":
            field["default"] = float(raw) if "." in raw else int(raw) if raw.lstrip("-").isdigit() else 0
        elif field["type"] == "Boolean":
            field["default"] = raw in ("true", "1", "yes")
        else:
            field["default"] = raw
    return _flags(field, low)


def _flags(field: dict, low: str) -> dict:
    if re.search(r"\brequired\b", low):
        field["required"] = True
    if re.search(r"\bunique\b", low):
        field["unique"] = True
    return field


# ── collection → data_model entry ─────────────────────────────────────────────

def adapt_collection(coll: dict) -> dict:
    name = _pascal(coll.get("name", "Item"), singular=True)
    fields = []
    for fname, spec_str in (coll.get("fields") or {}).items():
        if fname in ("createdAt", "updatedAt", "_id"):
            continue
        # embedded array field carries its own shape → stored as an array of mixed
        # objects (kits in later phases build/validate the items server-side).
        if "embedded" in str(spec_str).lower():
            fields.append({"name": fname, "type": "[Mixed]", "isEmbeddedArray": True})
        else:
            fields.append(parse_field(fname, spec_str))
    entry = {"name": name, "fields": fields, "collection": coll.get("name")}
    embedded = coll.get("embedded_item_shape")
    if embedded:
        entry["embedded_item_shape"] = {
            fn: parse_field(fn, sp) for fn, sp in embedded.items()
        }
    if coll.get("purpose"):
        entry["purpose"] = coll["purpose"]
    return entry


# ── roles ─────────────────────────────────────────────────────────────────────

def adapt_roles(srs: dict) -> list:
    raw = srs.get("roles") or []
    roles = []
    n = len(raw)
    for i, r in enumerate(raw):
        key = re.sub(r"[^a-z0-9_]", "", str(r.get("role_key") or r.get("name") or "").lower())
        if not key:
            continue
        is_admin = key == "admin"
        roles.append({
            "name": key,
            "label": r.get("role_name") or key.replace("_", " ").title(),
            "rank": 100 if is_admin else max(10, 90 - i * 10),
            "selfSignup": False,   # SRS staff systems: accounts are created by admin/seed
            "home": "/dashboard",  # AutoHub uses ONE shared staff dashboard
            "access": r.get("access", ""),
        })
    if not roles:
        roles = [{"name": "admin", "label": "Administrator", "rank": 100,
                  "selfSignup": False, "home": "/dashboard"}]
    if not any(x["name"] == "admin" for x in roles):
        roles.insert(0, {"name": "admin", "label": "Administrator", "rank": 100,
                         "selfSignup": False, "home": "/dashboard"})
    roles.sort(key=lambda x: x["rank"])
    return roles


# ── pages ──────────────────────────────────────────────────────────────────────

_PAGE_KIND = {
    # AutoHub vocabulary
    "public": "public", "authentication": "auth", "staff_dashboard": "dashboard",
    "staff_crud": "table-crud", "transaction": "transaction", "workflow": "workflow",
    "pos": "pos", "staff_crud_transaction": "table-crud", "finance": "finance",
    "analytics": "reports",
    # User-SRS vocabulary (short forms) → same internal page kinds
    "auth": "auth", "dashboard": "dashboard", "crud": "table-crud", "detail": "detail",
}


def _kind_for_page(page: dict) -> str:
    pt = str(page.get("page_type") or "").lower()
    route = str(page.get("route") or "")
    if pt == "public":
        if route == "/":
            return "landing"
        if route.endswith("/[id]"):
            return "detail"
        if "contact" in route or "about" in route:
            return "static"
        if "request" in route:
            return "form"
        return "list"
    return _PAGE_KIND.get(pt, "static")


def _resource_for_route(route: str, model_segs: dict) -> str:
    """Best-effort map a route to a resource model name via its path segments."""
    for seg in [s for s in route.strip("/").split("/") if s and not s.startswith("[")]:
        if seg in model_segs:
            return model_segs[seg]
    return ""


def adapt_pages(srs: dict, data_model: list, roles: list) -> list:
    from agents.scaffold import route_name
    role_names = {r["name"] for r in roles}
    model_segs = {}
    for m in data_model:
        model_segs[route_name(m["name"])] = m["name"]
        if m.get("collection"):
            model_segs[str(m["collection"]).lower()] = m["name"]
    pages = []
    for p in srs.get("pages") or []:
        route = str(p.get("route") or "").strip()
        if not route:
            continue
        allowed = [str(a).lower() for a in (p.get("allowed_roles") or [])]
        if "guest" in allowed:
            access = "public"
        else:
            staff = [a for a in allowed if a in role_names]
            if "all_staff" in allowed or not staff:
                access = "authed"
            else:
                access = "role:" + "|".join(staff)   # multi-role gate
        pages.append({
            "path": route,
            "title": p.get("page_name") or route,
            "kind": _kind_for_page(p),
            "access": access,
            "resource": _resource_for_route(route, model_segs),
            "allowed_roles": allowed,
            "functions": p.get("functions") or [],
            "sections": p.get("sections") or [],
        })
    return pages


# ── kit matching ───────────────────────────────────────────────────────────────

def match_kits(srs: dict, data_model: list) -> list:
    names = {m["name"].lower() for m in data_model}
    colls = {str(m.get("collection") or m["name"]).lower() for m in data_model}
    kits = ["crud", "auth", "rbac"]
    text = str(srs).lower()
    if any("stockmovement" in c for c in colls) or "stockmovements" in names:
        kits.append("inventory")
    if any("invoice" in c for c in colls) and any("payment" in c for c in colls):
        kits.append("invoicing")
    if "pos" in text or any("possale" in c or "possales" in c for c in colls):
        kits.append("pos")
    if any("rental" in c or "booking" in c for c in colls):
        kits.append("booking")
    if any("sale" in c and "pos" not in c for c in colls):
        kits.append("sales")
    if any("jobcard" in c or "appointment" in c for c in colls):
        kits.append("workflow")
    if any("report" in str(p.get("page_type", "")).lower() or p.get("page_type") == "analytics"
           for p in (srs.get("pages") or [])):
        kits.append("reports")
    if srs.get("seed_data_requirements"):
        kits.append("seed")
    return list(dict.fromkeys(kits))


# ── public entrypoint ──────────────────────────────────────────────────────────

def is_srs(data) -> bool:
    if not isinstance(data, dict):
        return False
    d = data.get("srs_document", data)
    from agents.rolewise import is_rolewise_srs
    if is_rolewise_srs(d):
        return True
    return isinstance(d, dict) and bool(
        d.get("pages") and (d.get("database_design") or d.get("collections"))
    )


def adapt(data: dict) -> dict:
    """SRS JSON (AutoHub shape) → internal locode spec."""
    from agents.rolewise import is_rolewise_srs, adapt_rolewise
    if is_rolewise_srs(data):
        spec = adapt_rolewise(data)
        from agents.quality import build_contract
        spec["quality_contract"] = build_contract(spec)
        return spec
    srs = data.get("srs_document", data)
    summary = srs.get("app_summary") or {}
    title = summary.get("app_name") or srs.get("project_name") or "App"
    project_name = re.sub(r"[^a-z0-9]+", "-", str(title).lower())[:40].strip("-") or "app"

    collections = ((srs.get("database_design") or {}).get("collections")
                   or srs.get("collections") or [])
    data_model = [adapt_collection(c) for c in collections
                  if _pascal(c.get("name", ""), singular=True) not in ("User",)]

    roles = adapt_roles(srs)
    pages = adapt_pages(srs, data_model, roles)
    kits = match_kits(srs, data_model)

    spec = {
        "project_name": project_name,
        "site_type": "app",
        "app_kind": "multipage-app",
        "strategy": "fullstack-next",
        "title": title,
        "tagline": summary.get("short_description", title)[:120],
        "description": summary.get("short_description") or summary.get("business_goal") or title,
        "color_scheme": (srs.get("ui_ux_requirements") or {}).get("design_direction")
                        or "dark graphite with an amber accent",
        "style": "modern",
        "brand_name": title,
        "target_audience": ", ".join(summary.get("target_users") or []) or "Staff",
        "key_features": [str(m.get("requirement", m)) for m in (srs.get("functional_requirements") or [])][:8],
        "data_model": data_model,
        "sections": ["Hero", "Features", "CTA"],
        "auth": {"enabled": True, "roles": [r["name"] for r in roles], "signup": False},
        "roles": roles,
        "pages": pages,
        "kits": kits,
        "seed": srs.get("seed_data_requirements") or {},
        "srs": srs,
        "special_instructions": summary.get("business_goal", ""),
        "_raw_idea": title,
    }
    # Keep the normalized contract beside the spec so every downstream stage and
    # the tester consume identical route/API/role truth.
    from agents.quality import build_contract
    spec["quality_contract"] = build_contract(spec)
    return spec
