"""Deterministic compiler for Locode's role-wise SRS JSON format.

The accepted input is intentionally close to the user's documents: ``app``, nested
``roles[].pages``, ``tables`` and ``relationships``.  This module never asks an LLM
to infer the application inventory.  It produces the same internal spec consumed by
the existing scaffold plus a richer canonical IR used by the planner and quality
gates.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SCHEMA_ID = "role-wise-srs/v1"


def is_rolewise_srs(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    value = data.get("srs_document", data)
    return bool(
        isinstance(value, dict)
        and isinstance(value.get("app"), dict)
        and isinstance(value.get("roles"), list)
        and isinstance(value.get("tables"), list)
        and isinstance(value.get("relationships"), list)
    )


def _slug(value: Any, sep: str = "-") -> str:
    text = re.sub(r"[^a-z0-9]+", sep, str(value or "").lower()).strip(sep)
    return text or "item"


def _extract_theme(raw: dict, app: dict) -> dict:
    """Optional colour palette from the input, any of: app.theme / app.colors /
    top-level theme / colors. Returns a dict of colour values (e.g. accent, accent2,
    primary). When absent the scaffold derives a per-app palette from the seed."""
    for source in (app.get("theme"), app.get("colors"), raw.get("theme"), raw.get("colors")):
        if isinstance(source, dict) and source:
            return {str(k): v for k, v in source.items()}
    return {}


def _role_slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_") or "user"


def _singular(value: str) -> str:
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith(("sses", "shes", "ches", "xes", "zes")):
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


def _pascal(value: Any, singular: bool = False) -> str:
    raw = str(value or "Item")
    if singular:
        raw = _singular(raw)
    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", raw.replace("-", " ").replace("_", " "))
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Item"


def _stable_id(*parts: Any) -> str:
    base = ":".join(_slug(p) for p in parts if str(p or "").strip())
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return f"{base[:72]}:{digest}"


TYPE_MAP = {
    "string": "String",
    "number": "Number",
    "boolean": "Boolean",
    "date": "Date",
    "objectid": "ObjectId",
    "enum": "String",
    "object": "Mixed",
    "array": "[String]",
    "array<object>": "[Mixed]",
}


def _field(raw: dict, table_to_model: dict[str, str]) -> dict:
    name = re.sub(r"[^A-Za-z0-9_]", "", str(raw.get("name") or "field")) or "field"
    original_type = str(raw.get("type") or "string").strip()
    result: dict[str, Any] = {
        "name": name,
        "type": TYPE_MAP.get(original_type.lower(), "String"),
        "source_type": original_type,
    }
    constraints = {str(x).lower() for x in (raw.get("constraints") or [])}
    if "required" in constraints:
        result["required"] = True
    if "unique" in constraints:
        result["unique"] = True
    if "default" in raw:
        result["default"] = raw.get("default")
    values = raw.get("values") or []
    if isinstance(values, list) and values:
        result["enum"] = [str(x) for x in values]
    reference = str(raw.get("references") or "")
    if reference:
        target_table = reference.split(".", 1)[0]
        result["ref"] = table_to_model.get(target_table, _pascal(target_table, singular=True))
        result["reference"] = reference
    if isinstance(raw.get("item_shape"), dict):
        result["item_shape"] = {
            str(key): _field({"name": key, "type": value}, table_to_model)
            for key, value in raw["item_shape"].items()
        }
        result["isEmbeddedArray"] = True
    return result


def _component_type(name: str, declared: dict | None = None) -> str:
    if declared and declared.get("type"):
        return str(declared["type"])
    low = name.lower()
    rules = (
        (("sidebar", "navbar", "breadcrumb"), "navigation"),
        (("layout", "shell"), "layout"),
        (("form",), "form"),
        (("table",), "data_table"),
        (("grid",), "interactive_grid"),
        (("chart",), "chart"),
        (("card", "summary"), "card"),
        (("select", "filter", "picker", "input", "switch", "search"), "form_control"),
        (("dialog", "modal", "drawer"), "overlay"),
        (("list", "queue", "board"), "list"),
    )
    for needles, kind in rules:
        if any(n in low for n in needles):
            return kind
    return "display"


ACTION_WORDS = {
    "query": {"view", "search", "filter", "review", "verify", "select", "open", "switch"},
    "create": {"create", "add", "request", "start"},
    "update": {"edit", "update", "change", "set", "enter", "map", "adjust", "reset"},
    "delete": {"remove", "archive", "deactivate"},
    "assignment": {"assign", "link"},
    "transition": {"mark", "submit", "publish", "confirm", "cancel", "complete", "seat", "send", "receive", "block"},
    "payment": {"record", "apply", "increase", "reduce"},
    "calculation": {"calculate", "validate", "hash"},
    "export": {"export", "download"},
    "print": {"print"},
    "management": {"manage"},
    "report": {"report", "revenue", "sales", "occupancy", "attendance", "exam", "fee", "maintenance"},
}


def _action_kind(label: str) -> str | None:
    words = re.findall(r"[a-z]+", label.lower())
    if not words:
        return None
    first = words[0]
    if first == "generate":
        return "create" if any(x in words for x in ("invoice", "receipt")) else "report"
    if first == "check" and any(x in words for x in ("in", "out")):
        return "transition"
    for kind, verbs in ACTION_WORDS.items():
        if first in verbs:
            return kind
    if any(x in words for x in ("report", "dashboard", "balance", "status")):
        return "query"
    if any(x in words for x in ("stock", "order", "booking", "waste", "item", "ingredient", "student")):
        return "command"
    return None


def _page_kind(page: dict) -> str:
    route = str(page.get("route") or "").lower()
    name = str(page.get("page_name") or "").lower()
    component_names = " ".join(
        str(c) for section in (page.get("sections") or []) for c in (section.get("components") or [])
    ).lower()
    if "dashboard" in route or "dashboard" in name:
        return "dashboard"
    if "report" in route or "report" in name:
        return "reports"
    if "[" in route and "]" in route:
        return "detail"
    if route.endswith("/create") or "form" in component_names:
        return "form"
    if any(x in component_names for x in ("table", "grid", "board", "queue")):
        return "table-crud"
    return "workflow"


def _page_resources(page: dict, resources: list[dict]) -> list[str]:
    haystack = " ".join([
        str(page.get("route") or ""), str(page.get("page_name") or ""),
        *[str(x) for x in (page.get("functions") or [])],
        *[str(x) for s in (page.get("sections") or []) for x in (s.get("components") or [])],
    ]).lower().replace("-", "")
    matches = []
    for resource in resources:
        words = {
            token.lower()
            for value in (resource["table"], resource["name"])
            for token in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", value.replace("_", " "))
            if len(token) > 2
        }
        generic_field_words = {"name", "title", "status", "email", "date", "total", "amount", "created", "updated"}
        words.update({
            token.lower()
            for field in (resource.get("fields") or [])
            for token in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", str(field.get("name") or ""))
            if len(token) > 4 and token.lower() not in generic_field_words
        })
        candidates = {
            resource["table"].lower().replace("_", ""),
            resource["name"].lower(),
            _singular(resource["table"].lower()).replace("_", ""),
        }
        if any(c and c in haystack for c in candidates) or any(word in haystack for word in words):
            matches.append(resource["name"])
    return matches


def adapt_rolewise(data: dict) -> dict:
    raw = data.get("srs_document", data)
    app = raw.get("app") or {}
    title = str(app.get("name") or "App")
    project_name = _slug(title)[:40]
    raw_tables = [x for x in (raw.get("tables") or []) if isinstance(x, dict) and x.get("table_name")]
    table_to_model = {
        str(t["table_name"]): _pascal(str(t["table_name"]), singular=True) for t in raw_tables
    }

    resources: list[dict] = []
    data_model: list[dict] = []
    for table in raw_tables:
        table_name = str(table["table_name"])
        model = table_to_model[table_name]
        fields = [
            _field(f, table_to_model) for f in (table.get("fields") or [])
            if isinstance(f, dict) and str(f.get("name")) not in {"_id", "createdAt", "updatedAt"}
        ]
        resource = {
            "id": _stable_id("resource", table_name),
            "name": model,
            "table": table_name,
            "fields": fields,
            "source_fields": table.get("fields") or [],
        }
        resources.append(resource)
        if model != "User":
            data_model.append({"name": model, "collection": table_name, "fields": fields})

    roles: list[dict] = []
    pages: list[dict] = []
    declared_components: dict[str, dict] = {}
    actions: list[dict] = []
    unresolved_actions: list[str] = []
    sidebar_errors: list[str] = []

    for index, source_role in enumerate(raw.get("roles") or []):
        if not isinstance(source_role, dict):
            continue
        role_name = _role_slug(source_role.get("role_key") or source_role.get("role_name"))
        role_pages = [p for p in (source_role.get("pages") or []) if isinstance(p, dict) and p.get("route")]
        dashboard = next((p for p in role_pages if "dashboard" in str(p.get("route", "")).lower()), None)
        home = str((dashboard or (role_pages[0] if role_pages else {})).get("route") or f"/{role_name}")
        role = {
            "name": role_name,
            "label": source_role.get("role_name") or role_name.replace("_", " ").title(),
            "summary": source_role.get("summary") or "",
            "rank": 100 if role_name == "admin" else max(10, 90 - index * 10),
            "selfSignup": False,
            "home": home,
            "sidebar_items": [],
            "role_functions": [str(x) for x in (source_role.get("role_functions") or [])],
        }
        for declared in source_role.get("components") or []:
            if not isinstance(declared, dict) or not declared.get("name"):
                continue
            name = str(declared["name"])
            declared_components.setdefault(name, {**declared, "roles": []})["roles"].append(role_name)
            if str(declared.get("type")) == "navigation":
                role["sidebar_items"].extend(str(x) for x in (declared.get("items") or []))
        roles.append(role)

        page_titles = {str(p.get("page_name") or "").lower(): str(p.get("route")) for p in role_pages}
        for item in role["sidebar_items"]:
            item_low = item.lower()
            candidates = [route for label, route in page_titles.items() if item_low in label or label in item_low]
            if len(candidates) == 1:
                continue
            # Dashboard is a safe exact semantic mapping even when the title is role-prefixed.
            if item_low == "dashboard" and dashboard:
                continue
            if len(candidates) > 1:
                sidebar_errors.append(f"AMBIGUOUS_NAV_ITEM:{role_name}:{item}")

        for page_index, source_page in enumerate(role_pages):
            route = str(source_page["route"])
            resource_names = _page_resources(source_page, resources)
            sections = []
            for section_index, source_section in enumerate(source_page.get("sections") or []):
                section_name = str(source_section.get("section_name") or f"Section {section_index + 1}")
                sections.append({
                    "id": _stable_id("section", role_name, route, section_name),
                    "section_name": section_name,
                    "components": [str(x) for x in (source_section.get("components") or [])],
                    "content": [str(x) for x in (source_section.get("content") or [])],
                })
            page_actions = []
            for action_index, label in enumerate(source_page.get("functions") or []):
                label = str(label)
                kind = _action_kind(label)
                action_id = _stable_id("action", role_name, route, action_index, label)
                if not kind:
                    unresolved_actions.append(f"UNMAPPED_ACTION:{role_name}:{route}:{label}")
                    kind = "unresolved"
                action = {
                    "id": action_id,
                    "label": label,
                    "kind": kind,
                    "role": role_name,
                    "page": route,
                    "resources": resource_names,
                }
                actions.append(action)
                page_actions.append(action_id)
            pages.append({
                "id": _stable_id("page", role_name, route),
                "path": route,
                "title": source_page.get("page_name") or route,
                "kind": _page_kind(source_page),
                "access": f"role:{role_name}",
                "owner_role": role_name,
                "resource": resource_names[0] if resource_names else "",
                "resources": resource_names,
                "functions": [str(x) for x in (source_page.get("functions") or [])],
                "action_ids": page_actions,
                "sections": sections,
                "source_index": page_index,
            })

    # Role-level functions are actions too, and are linked to the role home.
    for role in roles:
        for index, label in enumerate(role.get("role_functions") or []):
            kind = _action_kind(label)
            if not kind:
                unresolved_actions.append(f"UNMAPPED_ROLE_ACTION:{role['name']}:{label}")
                kind = "unresolved"
            actions.append({
                "id": _stable_id("role-action", role["name"], index, label),
                "label": label,
                "kind": kind,
                "role": role["name"],
                "page": role["home"],
                "resources": [],
                "scope": "role",
            })

    # Compile resource-level RBAC once in the canonical IR.  Every referenced
    # resource grants read access to its owning page role; mutation permissions
    # come only from explicitly classified functions.  Admin remains the
    # deterministic break-glass application administrator.
    role_names = {role["name"] for role in roles}
    permission_map: dict[str, dict[str, set[str]]] = {
        resource["name"]: {} for resource in resources
    }
    mutating = {
        "create": {"create"},
        "update": {"update"},
        "delete": {"delete"},
        "assignment": {"update"},
        "transition": {"update"},
        "payment": {"create", "update"},
        "calculation": {"update"},
        "management": {"create", "update", "delete"},
        "command": {"update"},
    }
    actions_by_id = {action["id"]: action for action in actions}
    for page in pages:
        role_name = page["owner_role"]
        for resource_name in page["resources"]:
            permission_map.setdefault(resource_name, {}).setdefault(role_name, set()).add("read")
        for action_id in page.get("action_ids") or []:
            action = actions_by_id[action_id]
            operations = mutating.get(action["kind"], set())
            for resource_name in action.get("resources") or []:
                permission_map.setdefault(resource_name, {}).setdefault(role_name, set()).update(operations)
    for model in data_model:
        permissions = permission_map.get(model["name"], {})
        if "admin" in role_names:
            permissions.setdefault("admin", set()).update({"read", "create", "update", "delete"})
        model["permissions"] = {
            role: sorted(operations) for role, operations in sorted(permissions.items())
        }
        model["allowedRoles"] = sorted(permissions)

    component_contracts: list[dict] = []
    usage_map: dict[str, list[dict]] = {}
    for page in pages:
        for section in page["sections"]:
            for name in section["components"]:
                usage_map.setdefault(name, []).append({
                    "page": page["path"], "role": page["owner_role"], "section": section["section_name"]
                })
    all_component_names = sorted(set(declared_components) | set(usage_map))
    for name in all_component_names:
        declared = declared_components.get(name)
        usages = usage_map.get(name, [])
        allowed_resources = sorted({r for u in usages for p in pages if p["path"] == u["page"] for r in p["resources"]})
        allowed_fields = sorted({
            f["name"] for resource in resources if resource["name"] in allowed_resources for f in resource["fields"]
        })
        component_contracts.append({
            "id": _stable_id("component", name),
            "name": name,
            "type": _component_type(name, declared),
            "declared": bool(declared),
            "metadata": {k: v for k, v in (declared or {}).items() if k not in {"name", "roles"}},
            "roles": sorted(set((declared or {}).get("roles") or []) | {u["role"] for u in usages}),
            "usages": usages,
            "allowed_resources": allowed_resources,
            "allowed_fields": allowed_fields,
            "states": ["loading", "empty", "error", "ready"],
        })

    table_names = {r["table"] for r in resources}
    relationship_errors = []
    relationships = []
    for index, relationship in enumerate(raw.get("relationships") or []):
        if not isinstance(relationship, dict):
            continue
        source = str(relationship.get("from") or "")
        target = str(relationship.get("to") or "")
        source_table = source.split(".", 1)[0]
        target_table = target.split(".", 1)[0]
        if source_table not in table_names or target_table not in table_names:
            relationship_errors.append(f"BROKEN_RELATIONSHIP:{source}->{target}")
        relationships.append({
            "id": _stable_id("relationship", index, source, target),
            "from": source,
            "to": target,
            "type": relationship.get("type") or "one_to_many",
        })

    analysis_errors = list(dict.fromkeys(unresolved_actions + sidebar_errors + relationship_errors))
    design_brief = {
        "domain": app.get("app_type") or "Business Web Application",
        "personality": "polished, confident, role-aware",
        "component_system": "locode-shadcn",
        "density": "comfortable",
        "radius": "large",
        "seed": int(hashlib.sha1(title.encode("utf-8")).hexdigest()[:8], 16),
    }
    canonical_ir = {
        "schema": SCHEMA_ID,
        "app": app,
        "roles": roles,
        "resources": resources,
        "relationships": relationships,
        "pages": pages,
        "components": component_contracts,
        "actions": actions,
        "design_brief": design_brief,
        "acceptance_tests": [
            "all-declared-routes-render", "all-components-imported", "all-actions-covered",
            "role-matrix-enforced", "all-resources-persist", "desktop-mobile-clean",
        ],
    }
    source_hash = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    spec = {
        "input_schema": SCHEMA_ID,
        "input_hash": source_hash,
        "project_name": project_name,
        "site_type": "app",
        "app_kind": "multipage-app",
        "strategy": "component-wise-next",
        "title": title,
        "tagline": str(app.get("summary") or title)[:120],
        "description": app.get("summary") or title,
        "color_scheme": "domain-seeded shadcn CSS variables",
        "theme": _extract_theme(raw, app),
        "style": "modern",
        "brand_name": title,
        "target_audience": ", ".join(r["label"] for r in roles),
        "key_features": [a["label"] for a in actions[:8]],
        "data_model": data_model,
        "resources": resources,
        "sections": ["Hero", "Features", "CTA"],
        "auth": {"enabled": True, "roles": [r["name"] for r in roles], "signup": False},
        "roles": roles,
        "pages": pages,
        "component_contracts": component_contracts,
        "actions": actions,
        "relationships": relationships,
        "design_brief": design_brief,
        "canonical_ir": canonical_ir,
        "analysis": {
            "errors": analysis_errors,
            "warnings": [],
            "counts": {
                "roles": len(roles), "pages": len(pages), "components": len(component_contracts),
                "used_components": len(usage_map),
                "tables": len(resources), "models": len(data_model), "relationships": len(relationships),
                "actions": len(actions),
            },
        },
        "kits": [],
        "seed": {},
        "srs": raw,
        "special_instructions": app.get("summary") or "",
        "_raw_idea": title,
    }
    # Reuse Locode's existing deterministic behaviour kits based on the normalized
    # table inventory.  The import is intentionally lazy to avoid a module cycle.
    from agents.srs_adapter import match_kits
    spec["kits"] = match_kits({**raw, "pages": pages}, data_model)
    return spec
