"""Part of the `data_model_planner` package (auto-split, verbatim). See data_model_planner/__init__.py."""
from __future__ import annotations
import copy
import json
import os
import re
from ._analyze import _entities_from_srs, _generic_model, _user_entity, auth_required, infer_roles
from ._domains import _DOMAIN_LIBRARY
from ._primitives import _title, detect_domain, ent, f

def plan_data_model(prompt: str, app_name: str = None, srs: dict = None) -> dict:
    """Plan a relationship-aware data model from a prompt (and optional SRS)."""
    prompt = str(prompt or "")
    domain = detect_domain(prompt)               # cosmetic when SRS is authoritative
                                                   # (dashboard title lookup only) - does
                                                   # NOT gate which entities get built below.

    srs_base = _entities_from_srs(srs)
    if srs_base is not None:
        base = srs_base
        roles = list(srs_base["roles"]) or ["Admin", "User"]
    else:
        builder = _DOMAIN_LIBRARY.get(domain)
        base = builder() if builder else _generic_model(prompt, domain)
        roles = infer_roles(prompt, domain, base.get("roles"))

    entities = copy.deepcopy(base["entities"])
    # Extra SRS-derived metadata keys (passed through from _entities_from_srs)
    _srs_extra = {k: base.get(k, base.get(k[4:], [])) for k in (
        "srs_workflows", "srs_notifications", "srs_reports", "srs_security",
        "srs_ui_ux", "srs_acceptance", "srs_future", "srs_validation",
        "srs_auth", "srs_modules", "srs_system_category",
    )} if srs_base is not None else {}

    # SRS entity overrides/additions (generic, optional) - only when the SRS
    # WASN'T rich enough to be authoritative above (bare {"name": ...} shape).
    if srs_base is None and isinstance(srs, dict) and isinstance(srs.get("entities"), list):
        existing = {e["name"].lower() for e in entities}
        for se_ in srs["entities"]:
            nm = _title(str(se_.get("name") or "")).replace(" ", "")
            if nm and nm.lower() not in existing:
                entities.append(ent(nm, fields=[f("name", required=True),
                                                f("status", "enum", enum=["active", "inactive"])]))
                existing.add(nm.lower())

    needs_auth = auth_required(prompt, entities) or bool(srs_base)   # an SRS with explicit
                                                                       # roles always implies login
    if needs_auth:
        entities.insert(0, _user_entity(roles))

    entities = _validate_and_link(entities)
    model = {
        "app_name": app_name or _infer_app_name(prompt, domain),
        "domain": domain,
        "auth_required": needs_auth,
        "roles": roles,
        "entity_count": len(entities),
        "entities": entities,
        "relationships_summary": _relationship_summary(entities),
        "workflows": _workflow_summary(entities),
        "generated_by": "data_model_planner",
        **_srs_extra,   # propagate all SRS coverage sections (workflows, notifications, reports, etc.)
    }
    return model
def _validate_and_link(entities):
    """Drop refs whose target isn't in the model; compute derived fields and
    referenced-by back-links; mark embedded child collections."""
    names = {e["name"] for e in entities}
    for e in entities:
        e["relationships"] = [rel for rel in e["relationships"]
                              if rel["target"] in names or rel["target"] == "User"]
        # ensure every ref field is an index for query performance
        for rel in e["relationships"]:
            if rel["field"] not in e["indexes"]:
                e["indexes"].append(rel["field"])
        # derived fields used by side effects (counters)
        for eff in e["side_effects"]:
            if eff["action"] in ("increment", "decrement") and eff.get("field"):
                _ensure_counter(entities, eff["target"], eff["field"])
    # referenced_by back-links
    ref_map = {}
    for e in entities:
        for rel in e["relationships"]:
            ref_map.setdefault(rel["target"], []).append({"entity": e["name"], "field": rel["field"]})
    for e in entities:
        e["referenced_by"] = ref_map.get(e["name"], [])
    return entities
def _ensure_counter(entities, target_name, field):
    for e in entities:
        if e["name"] == target_name:
            if not any(fl["name"] == field for fl in e["fields"]):
                e["fields"].append(f(field, "number", label=_title(field)))
            return
def _relationship_summary(entities):
    out = []
    for e in entities:
        for rel in e["relationships"]:
            out.append(f"{e['name']} -> {rel['target']} ({rel['cardinality']}, {rel['field']})")
    return out
def _workflow_summary(entities):
    out = []
    for e in entities:
        for eff in e["side_effects"]:
            tgt = f"{eff['target']}.{eff['field']}" if eff.get("field") else eff["target"]
            out.append(f"on {eff['on']} {e['name']}: {eff['action']} {tgt}"
                       + (f" — {eff['note']}" if eff.get("note") else ""))
    return out
def _infer_app_name(prompt, domain):
    # Neutral, non-branded working title derived from the domain (never a real brand).
    return _title(domain.replace("-", " ")) + " Platform"
def write_data_model(out_dir: str, model: dict, filename: str = "app_data_model.json") -> str:
    path = os.path.join(out_dir, filename)
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(model, fh, indent=2)
    except OSError:
        pass
    return path
