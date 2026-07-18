"""Input-driven application architect.

Gemma 4 receives the user's complete input once and returns the authoritative
product, data, page, access, and design plan.  This module validates that plan;
it never replaces missing structure with a Locode template.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from copy import deepcopy

from agents import llm

log = logging.getLogger("architect")

SCHEMA_VERSION = "locode-spec/v3"
VALID_TYPES = {"String", "Number", "Boolean", "Date", "ObjectId", "[String]"}
DESIGN_PRESETS = {
    "minimal", "modern", "carbon", "material", "flat", "neobrutalism",
    "glassmorphism", "claymorphism", "retro", "neumorphism", "cyberpunk",
}
PALETTE_KEYS = {
    "primary", "secondary", "accent", "background", "surface", "text",
    "textSecondary", "border", "success", "warning", "error",
}
RESERVED_MODELS = {"User", "Account", "Auth", "Session"}
ACTION_PATTERNS = {
    "add": r"\b(?:add|adds|added|adding)\b",
    "approve": r"\bapprov(?:e|es|ed|ing|al)\b",
    "assign": r"\bassign(?:s|ed|ing|ment)?\b",
    "book": r"\bbook(?:s|ed|ing)?\b",
    "bookmark": r"\bbookmark(?:s|ed|ing)?\b",
    "calculate": r"\bcalculat(?:e|es|ed|ing|or|ion)\b",
    "comment": r"\bcomment(?:s|ed|ing)?\b",
    "compare": r"\bcompar(?:e|es|ed|ing|ison)\b",
    "convert": r"\bconvert(?:s|ed|ing|er|ion)?\b",
    "copy": r"\b(?:copy|copies|copied|copying)\b",
    "delete": r"\bdelet(?:e|es|ed|ing|ion)\b",
    "download": r"\bdownload(?:s|ed|ing)?\b",
    "edit": r"\bedit(?:s|ed|ing|or)?\b",
    "export": r"\bexport(?:s|ed|ing)?\b",
    "filter": r"\bfilter(?:s|ed|ing)?\b",
    "import": r"\bimport(?:s|ed|ing)?\b",
    "invite": r"\binvit(?:e|es|ed|ing|ation)\b",
    "pay": r"\b(?:pay|pays|paid|paying|payment)\b",
    "print": r"\bprint(?:s|ed|ing)?\b",
    "record": r"\brecord(?:s|ed|ing)?\b",
    "save": r"\bsav(?:e|es|ed|ing)\b",
    "search": r"\bsearch(?:es|ed|ing)?\b",
    "share": r"\bshar(?:e|es|ed|ing)\b",
    "sort": r"\bsort(?:s|ed|ing)?\b",
    "track": r"\btrack(?:s|ed|ing|er)?\b",
    "upload": r"\bupload(?:s|ed|ing)?\b",
}
EXPLICIT_ONLY_ACTIONS = {
    "approve", "assign", "book", "delete", "download", "export", "import",
    "invite", "pay", "print", "upload",
}
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

DESIGN_BAR = """
<design_instructions>
Build a professional, beautiful, unique, production-worthy product with Apple/Stripe-level polish.
Avoid generic dashboards and default-template layouts. Every screen needs a visual signature suited
to its job and domain. Use a disciplined 3-5 colour brand palette plus neutrals, deliberate typography,
an 8px spacing rhythm, responsive mobile-first layouts, WCAG-readable contrast, accessible focus and
touch states, real domain copy, purposeful motion, and complete loading/empty/error/success states.
Every visible control must do something useful. Never invent testimonials, customers, awards, usage
numbers, or business metrics. Choose roles, authentication, navigation, routes, entities, page count,
and per-page functions only from the user's actual product needs. When the user omits a visual choice,
choose one that fits this specific domain instead of using a universal default.
</design_instructions>
""".strip()

ARCHITECT_SYSTEM = f"""You are Locode's senior product architect and design director.
Return exactly one raw JSON object and no markdown. The user's input is authoritative. You decide the
application structure from that input; never force a CRUD dashboard, auth, roles, or a fixed page list.
Use Next.js App Router, MongoDB where persistence is needed, Tailwind CSS, shadcn UI, and Lucide icons.
Thinking is disabled. Return the complete JSON contract directly. Keep descriptive string values
specific but concise (normally 4-12 words and one phrase); never repeat words, intensifiers, percentage
claims, or the same intent within or across fields.

{DESIGN_BAR}

The JSON must use this contract:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "project_name": "kebab-case",
  "site_type": "short domain category",
  "title": "Product title",
  "tagline": "specific product promise",
  "description": "complete product description",
  "brand_name": "Brand name",
  "target_audience": "specific audience",
  "key_features": ["specific feature"],
  "special_instructions": "important behaviour and content intent",
  "auth": {{"enabled": false, "reason": "why", "signup": false}},
  "roles": [{{
    "name": "lowercase-key", "label": "Display label", "home": "/route",
    "selfSignup": false, "permissions": ["specific capability"]
  }}],
  "design": {{
    "preset": "concise domain-specific visual preset label",
    "mode": "light|dark", "navStyle": "sidebar|topnav|none",
    "palette": {{
      "primary": "#RRGGBB", "secondary": "#RRGGBB", "accent": "#RRGGBB",
      "background": "#RRGGBB", "surface": "#RRGGBB", "text": "#RRGGBB",
      "textSecondary": "#RRGGBB", "border": "#RRGGBB", "success": "#RRGGBB",
      "warning": "#RRGGBB", "error": "#RRGGBB"
    }},
    "typography": {{"heading": "font family", "body": "font family"}},
    "radius": "none|sm|md|lg|xl", "shadow": "none|sm|md|lg|xl",
    "spacing": "tight|normal|relaxed|loose", "motion": "none|subtle|expressive",
    "visualSignature": "specific visual concept used across the app"
  }},
  "data_model": [{{
    "name": "PascalCase domain noun", "ownedBy": "User or omit",
    "fields": [{{"name": "camelCase", "type": "String|Number|Boolean|Date|ObjectId|[String]",
                "required": true, "default": "optional", "enum": ["optional"], "ref": "Model"}}]
  }}],
  "pages": [{{
    "path": "/exact-route", "title": "Page title", "kind": "descriptive-kind",
    "access": "public|authenticated|role:<role>", "purpose": "why this page exists",
    "userJob": "what the user completes", "resource": "optional Model",
    "resources": ["optional Models"], "sections": ["ordered section names"],
    "functions": ["testable behaviour"], "primaryAction": "main action",
    "archetype": "domain-appropriate layout name", "layout": "specific layout composition",
    "visualSignature": "what makes this page visually distinctive"
  }}],
  "generation_plan": {{
    "components": [{{
      "name": "PascalCase feature component", "path": "components/features/.../Name.tsx",
      "page": "/exact-existing-page", "type": "section|form|results|list|detail|navigation",
      "responsibility": "one precise input-specific responsibility",
      "props": "TypeScript prop members separated by semicolons, or empty",
      "state": ["state this component owns"], "actions": ["declared action it implements"],
      "dependencies": ["other planned component paths used by this component"],
      "allowed_resources": ["exact Model names"], "expectedLines": 120
    }}],
    "dependencyWaves": [["component paths that can generate concurrently"]]
  }}
}}

Rules:
- Return every page the product needs and no formulaic extras. Even a one-page product must list `/`.
- Authentication is independent of page count. Roles exist only when distinct permissions are needed.
- Never add a User/Account/Auth/Session data model; Locode owns authentication infrastructure.
- Persist every real domain entity the product needs; there is no arbitrary 1-3 model limit.
- Never use generic entities such as Item, Entry, Record, Data, or Thing.
- Each functional page lists its concrete functions, resources, and an appropriate non-generic layout.
- `ownedBy` is per entity and is never implied merely because authentication exists.
- Decompose every page into input-specific feature components, normally 80-180 lines each. Do not use
  generic page templates. Each page needs at least one component; complex interactive sections get
  separate components. A dependency wave contains at most two independent component paths.
"""

_STRING_ARRAY = {"type": "array", "items": {"type": "string", "maxLength": 120},
                 "maxItems": 8}
_NONEMPTY_STRING_ARRAY = {"type": "array", "items": {"type": "string", "maxLength": 120},
                          "minItems": 1, "maxItems": 8}
_WAVE_SCHEMA = {"type": "array", "items": {"type": "string"},
                "minItems": 1, "maxItems": 2}
_PALETTE_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}
                   for key in sorted(PALETTE_KEYS)},
    "required": sorted(PALETTE_KEYS),
}
_DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "preset": {"type": "string"},
        "mode": {"type": "string", "enum": ["light", "dark"]},
        "navStyle": {"type": "string", "enum": ["sidebar", "topnav", "none"]},
        "palette": _PALETTE_SCHEMA,
        "typography": {"type": "object", "properties": {
            "heading": {"type": "string"}, "body": {"type": "string"}},
            "required": ["heading", "body"]},
        "radius": {"type": "string", "enum": ["none", "sm", "md", "lg", "xl"]},
        "shadow": {"type": "string", "enum": ["none", "sm", "md", "lg", "xl"]},
        "spacing": {"type": "string", "enum": ["tight", "normal", "relaxed", "loose"]},
        "motion": {"type": "string", "enum": ["none", "subtle", "expressive"]},
        "visualSignature": {"type": "string", "maxLength": 180},
    },
    "required": ["preset", "mode", "navStyle", "palette", "typography", "radius",
                 "shadow", "spacing", "motion", "visualSignature"],
}
_PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "pattern": "^/.*$"}, "title": {"type": "string"},
        "kind": {"type": "string"},
        "access": {"type": "string", "pattern": "^(public|authenticated|role:[a-z][a-z0-9_-]*)$"},
        "purpose": {"type": "string", "maxLength": 180},
        "userJob": {"type": "string", "maxLength": 180},
        "resource": {"type": ["string", "null"]}, "resources": _STRING_ARRAY,
        "sections": _NONEMPTY_STRING_ARRAY, "functions": _NONEMPTY_STRING_ARRAY,
        "primaryAction": {"type": "string"}, "archetype": {"type": "string"},
        "layout": {"type": "string", "maxLength": 180},
        "visualSignature": {"type": "string", "maxLength": 180},
    },
    "required": ["path", "title", "kind", "access", "purpose", "userJob", "resources",
                 "sections", "functions", "primaryAction", "archetype", "layout",
                 "visualSignature"],
}
_COMPONENT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": "^[A-Z][A-Za-z0-9]*$"},
        "path": {"type": "string", "pattern": "^components/(features|pages|layout|layouts)/.+\\.tsx$"},
        "page": {"type": "string", "pattern": "^/.*$"}, "type": {"type": "string"},
        "responsibility": {"type": "string", "maxLength": 180},
        "props": {"type": "string", "maxLength": 320},
        "state": _STRING_ARRAY, "actions": _STRING_ARRAY, "dependencies": _STRING_ARRAY,
        "allowed_resources": _STRING_ARRAY,
        "expectedLines": {"type": "integer", "minimum": 60, "maximum": 180},
    },
    "required": ["name", "path", "page", "type", "responsibility", "props", "state",
                 "actions", "dependencies", "allowed_resources", "expectedLines"],
}
ARCHITECT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
        "project_name": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"},
        "site_type": {"type": "string"}, "title": {"type": "string"},
        "tagline": {"type": "string"},
        "description": {"type": "string", "maxLength": 180},
        "brand_name": {"type": "string"}, "target_audience": {"type": "string"},
        "key_features": _NONEMPTY_STRING_ARRAY,
        "special_instructions": {"type": "string", "maxLength": 180},
        "auth": {"type": "object", "properties": {
            "enabled": {"type": "boolean"}, "reason": {"type": "string"},
            "signup": {"type": "boolean"}}, "required": ["enabled", "reason", "signup"]},
        "roles": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string", "pattern": "^[a-z][a-z0-9_-]*$"},
            "label": {"type": "string"},
            "home": {"type": "string", "pattern": "^/.*$"}, "selfSignup": {"type": "boolean"},
            "permissions": _STRING_ARRAY},
            "required": ["name", "label", "home", "selfSignup", "permissions"]}},
        "design": _DESIGN_SCHEMA,
        "data_model": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string", "pattern": "^[A-Z][A-Za-z0-9]*$"},
            "ownedBy": {"type": ["string", "null"]},
            "fields": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "enum": sorted(VALID_TYPES)},
                "required": {"type": "boolean"},
                "default": {"type": ["string", "number", "boolean", "null"]},
                "enum": _STRING_ARRAY,
                "ref": {"type": ["string", "null"]}},
                "required": ["name", "type", "required"]}}},
            "required": ["name", "fields"]}},
        "pages": {"type": "array", "items": _PAGE_SCHEMA, "minItems": 1},
        "generation_plan": {"type": "object", "properties": {
            "components": {"type": "array", "items": _COMPONENT_SCHEMA, "minItems": 1},
            "dependencyWaves": {"type": "array", "items": _WAVE_SCHEMA, "minItems": 1}},
            "required": ["components", "dependencyWaves"]},
    },
    "required": ["schema_version", "project_name", "site_type", "title", "tagline",
                 "description", "brand_name", "target_audience", "key_features",
                 "special_instructions", "auth", "roles", "design", "data_model", "pages",
                 "generation_plan"],
}


def _seal_schema_objects(node) -> None:
    """Make structured output exact instead of accepting invented JSON keys."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            node.setdefault("additionalProperties", False)
        if node.get("type") == "string" and "enum" not in node:
            node.setdefault("maxLength", 96)
        for value in node.values():
            _seal_schema_objects(value)
    elif isinstance(node, list):
        for value in node:
            _seal_schema_objects(value)


_seal_schema_objects(ARCHITECT_JSON_SCHEMA)


class ArchitectError(RuntimeError):
    """Raised when Gemma cannot produce a valid, input-faithful plan."""


def _parse_json(text: str) -> dict:
    text = llm.strip_think(text or "").strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
        text = match.group(1).strip() if match else text
    decoder = json.JSONDecoder()
    candidates = []
    for match in re.finditer(r"\{", text):
        try:
            value, consumed = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict):
                candidates.append((consumed, value))
        except json.JSONDecodeError:
            continue
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    # A conservative repair for the common trailing-comma failure only.
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(re.sub(r",\s*([}\]])", r"\1", text[start:end + 1]))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def _deep_merge(base, patch):
    """Apply a corrective JSON patch without losing valid prior contract fields."""
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = deepcopy(base)
        for key, value in patch.items():
            merged[key] = _deep_merge(merged.get(key), value) if key in merged else deepcopy(value)
        return merged
    return deepcopy(patch)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "locode-app"


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _hex_color(value):
    """Normalize an unambiguous CSS color spelling without choosing a new color."""
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3,4}", text):
        return "#" + "".join(ch * 2 for ch in text[1:4])
    if re.fullmatch(r"#[0-9a-fA-F]{8}", text):
        return text[:7]
    match = re.fullmatch(
        r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*[\d.]+)?\s*\)",
        text, re.I)
    if match:
        channels = [max(0, min(255, int(part))) for part in match.groups()]
        return "#" + "".join(f"{channel:02X}" for channel in channels)
    return text


def _safe_dependency_waves(components: list[dict], declared) -> list[list[str]]:
    """Serialize declared dependencies into deterministic waves of at most two."""
    paths = [str(item.get("path") or "") for item in components]
    path_set = set(paths)
    waves = [_string_list(wave) for wave in (declared or []) if _string_list(wave)]
    flat = [path for wave in waves for path in wave]
    positions = {path: index for index, wave in enumerate(waves) for path in wave}
    valid = (len(flat) == len(set(flat)) and set(flat) == path_set and
             all(len(wave) <= 2 for wave in waves))
    if valid:
        for item in components:
            for dependency in item.get("dependencies") or []:
                if dependency in path_set and positions[dependency] >= positions[item["path"]]:
                    valid = False
                    break
    if valid:
        return waves

    remaining = list(paths)
    scheduled: set[str] = set()
    rebuilt: list[list[str]] = []
    dependency_map = {
        item["path"]: {dep for dep in (item.get("dependencies") or []) if dep in path_set}
        for item in components
    }
    while remaining:
        ready = [path for path in remaining if dependency_map[path] <= scheduled]
        batch = (ready or remaining)[:2]
        rebuilt.append(batch)
        scheduled.update(batch)
        remaining = [path for path in remaining if path not in batch]
    return rebuilt


def _pascal(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(value or ""))
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Section"


def _fallback_generation_plan(spec: dict) -> dict:
    """Input-derived decomposition for structured/legacy specs without Architect topology.

    This selects no visual layout or product behaviour. It only turns the declared page sections into
    small feature-file contracts so a legacy SRS receives the same bounded generation path.
    """
    components, seen = [], set()
    for page in spec.get("pages") or []:
        path = str(page.get("path") or "/")
        page_key = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"
        page_name = _pascal(page.get("title") or page_key)
        sections = list(page.get("sections") or []) or [page.get("title") or "Main"]
        for index, section in enumerate(sections):
            name = f"{page_name}{_pascal(section)}"
            if name in seen:
                name += str(index + 1)
            seen.add(name)
            component_path = f"components/features/{page_key}/{name}.tsx"
            components.append({
                "name": name,
                "path": component_path,
                "page": path,
                "type": "section",
                "responsibility": f"{section}: {page.get('userJob') or page.get('purpose') or ''}".strip(),
                "props": "",
                "state": [],
                "actions": list(page.get("functions") or []) if index == 0 else [],
                "dependencies": [],
                "allowed_resources": list(dict.fromkeys(
                    ([page.get("resource")] if page.get("resource") else [])
                    + list(page.get("resources") or [])
                )),
                "expectedLines": 120,
            })
    paths = [item["path"] for item in components]
    return {"components": components,
            "dependencyWaves": [paths[i:i + 2] for i in range(0, len(paths), 2)]}


def normalize_generation_plan(value, spec: dict) -> dict:
    raw = value if isinstance(value, dict) else {}
    has_declared_plan = isinstance(value, dict) and "components" in value
    page_paths = {str(page.get("path") or "") for page in spec.get("pages") or []}
    model_names = {str(model.get("name") or "") for model in spec.get("data_model") or []}
    components = []
    for component in raw.get("components") or []:
        if not isinstance(component, dict):
            continue
        item = deepcopy(component)
        item["name"] = _pascal(item.get("name"))
        item["path"] = str(item.get("path") or "").replace("\\", "/").lstrip("/")
        item["page"] = str(item.get("page") or "")
        item["type"] = str(item.get("type") or "section")
        item["responsibility"] = str(item.get("responsibility") or "").strip()
        item["props"] = str(item.get("props") or "").strip()
        item["state"] = _string_list(item.get("state"))
        item["actions"] = _string_list(item.get("actions"))
        item["dependencies"] = _string_list(item.get("dependencies"))
        item["allowed_resources"] = [name for name in _string_list(item.get("allowed_resources"))
                                     if name in model_names]
        try:
            item["expectedLines"] = max(60, min(180, int(item.get("expectedLines") or 120)))
        except (TypeError, ValueError):
            item["expectedLines"] = 120
        if item["page"] in page_paths and item["path"]:
            components.append(item)
    if not components and not has_declared_plan:
        return _fallback_generation_plan(spec)

    # Cloud planners occasionally use the declared component name (`TeaCard`) where the contract
    # asks for its path (`components/features/TeaCard.tsx`). This is a lossless identifier
    # normalization, not a structural correction: resolve it locally so a good plan does not need a
    # second long cloud response merely to repeat the same component inventory.
    by_name = {str(item.get("name") or ""): str(item.get("path") or "") for item in components}
    by_stem = {str(item.get("path") or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]:
               str(item.get("path") or "") for item in components}
    for item in components:
        resolved = []
        for dependency in item.get("dependencies") or []:
            dependency = str(dependency).replace("\\", "/").lstrip("/")
            target = by_name.get(dependency) or by_stem.get(dependency) or dependency
            if target and target not in resolved:
                resolved.append(target)
        item["dependencies"] = resolved
    waves = _safe_dependency_waves(components, raw.get("dependencyWaves"))
    return {"components": components, "dependencyWaves": waves}


def normalize_spec(raw: dict, raw_input: str) -> dict:
    """Normalize shapes and compatibility fields without inventing product structure."""
    spec = deepcopy(raw) if isinstance(raw, dict) else {}
    title = str(spec.get("title") or spec.get("brand_name") or "").strip()
    spec["schema_version"] = SCHEMA_VERSION
    spec["title"] = title
    spec["brand_name"] = str(spec.get("brand_name") or title).strip()
    spec["project_name"] = _slug(str(spec.get("project_name") or title))
    spec["site_type"] = str(spec.get("site_type") or "app").strip().lower()
    spec["tagline"] = str(spec.get("tagline") or "").strip()
    spec["description"] = str(spec.get("description") or "").strip()
    spec["target_audience"] = str(spec.get("target_audience") or "").strip()
    spec["key_features"] = _string_list(spec.get("key_features"))
    spec["special_instructions"] = str(spec.get("special_instructions") or "").strip()

    auth = spec.get("auth") if isinstance(spec.get("auth"), dict) else {}
    spec["auth"] = {
        "enabled": bool(auth.get("enabled")),
        "reason": str(auth.get("reason") or auth.get("why") or "").strip(),
        "signup": bool(auth.get("signup")),
    }

    roles = []
    for role in spec.get("roles") or []:
        if not isinstance(role, dict):
            continue
        name = re.sub(r"[^a-z0-9_-]", "", str(role.get("name") or "").lower())
        if not name:
            continue
        roles.append({
            **role,
            "name": name,
            "label": str(role.get("label") or name.replace("-", " ").title()),
            "home": str(role.get("home") or ""),
            "selfSignup": bool(role.get("selfSignup")),
            "permissions": _string_list(role.get("permissions")),
        })
    spec["roles"] = roles

    design = spec.get("design") if isinstance(spec.get("design"), dict) else {}
    palette = design.get("palette") if isinstance(design.get("palette"), dict) else {}
    design["palette"] = {key: _hex_color(value) for key, value in palette.items()}
    design["typography"] = design.get("typography") if isinstance(design.get("typography"), dict) else {}
    spec["design"] = design

    models = []
    for model in spec.get("data_model") or []:
        if not isinstance(model, dict):
            continue
        item = deepcopy(model)
        item["name"] = str(item.get("name") or "").strip()
        item["fields"] = [deepcopy(f) for f in (item.get("fields") or []) if isinstance(f, dict)]
        models.append(item)
    spec["data_model"] = models

    count_pattern = r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+([a-z][a-z0-9-]*)\s+types?\b"
    for match in re.finditer(count_pattern, raw_input, re.I):
        sentence = next((part.strip() for part in re.split(r"[.!?\n]+", raw_input)
                         if match.group(0).lower() in part.lower()), match.group(0))
        requirement = f"Exact user requirement: {sentence}"
        if requirement.lower() not in spec["special_instructions"].lower():
            spec["special_instructions"] = (spec["special_instructions"] + "\n" + requirement).strip()

    pages = []
    for page in spec.get("pages") or []:
        if not isinstance(page, dict):
            continue
        item = deepcopy(page)
        item["path"] = str(item.get("path") or "").strip()
        item["title"] = str(item.get("title") or item["path"]).strip()
        item["kind"] = str(item.get("kind") or "static").strip()
        item["access"] = str(item.get("access") or "public").strip()
        item["purpose"] = str(item.get("purpose") or "").strip()
        item["userJob"] = str(item.get("userJob") or item.get("user_job") or "").strip()
        item["sections"] = _string_list(item.get("sections"))
        item["functions"] = _string_list(item.get("functions"))
        item["resources"] = _string_list(item.get("resources"))
        item["primaryAction"] = str(item.get("primaryAction") or "").strip()
        item["archetype"] = str(item.get("archetype") or "").strip()
        item["layout"] = str(item.get("layout") or "").strip()
        item["visualSignature"] = str(item.get("visualSignature") or "").strip()
        pages.append(item)

    raw_lower = raw_input.lower()
    if re.search(r"\b(?:no|without) (?:accounts?|authentication|auth|login|sign-?up)\b", raw_lower):
        spec["auth"] = {
            "enabled": False,
            "reason": "The user explicitly requested no accounts or authentication.",
            "signup": False,
        }
        spec["roles"] = []
    if re.search(r"\b(?:top navigation|top nav|topnav)\b", raw_lower):
        design["navStyle"] = "topnav"
    if re.search(r"\b(?:one|single)[ -]page\b", raw_lower):
        pages = [page for page in pages if page.get("path") == "/"]

    for action, pattern in ACTION_PATTERNS.items():
        if not re.search(pattern, raw_lower) or not pages:
            continue
        page_text = json.dumps(pages, ensure_ascii=False, default=str).lower()
        if re.search(pattern, page_text):
            continue
        sentence = next((part.strip() for part in re.split(r"[.!?\n]+", raw_input)
                         if re.search(pattern, part.lower())), action)
        pages[0].setdefault("functions", []).append(
            f"Explicit user behavior: {sentence}")

    spec["pages"] = pages
    spec["generation_plan"] = normalize_generation_plan(spec.get("generation_plan"), spec)

    # Compatibility fields are projections only; downstream code must read the
    # authoritative auth/design/pages contracts above.
    spec["app_kind"] = "multipage-app" if len(pages) > 1 else "single-page"
    palette = design.get("palette") or {}
    spec["theme"] = {"accent": palette.get("primary", ""), "accent2": palette.get("secondary", "")}
    spec["style"] = str(design.get("preset") or "")
    spec["color_scheme"] = ", ".join(
        str(palette.get(k)) for k in ("primary", "secondary", "accent") if palette.get(k)
    )
    home = next((p for p in pages if p.get("path") == "/"), pages[0] if pages else {})
    spec["sections"] = list(home.get("sections") or [])
    spec["_raw_idea"] = raw_input
    spec["input_hash"] = hashlib.sha256(raw_input.encode("utf-8")).hexdigest()
    return spec


def validate_spec(spec: dict) -> list[str]:
    """Validate the Architect contract without selecting replacement structure."""
    errors: list[str] = []
    if not spec.get("title"):
        errors.append("title is required")
    if not spec.get("description"):
        errors.append("description is required")

    def inspect_text(value, path="spec"):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).startswith("_") or str(key) == "props":
                    continue
                inspect_text(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect_text(child, f"{path}[{index}]")
        elif isinstance(value, str):
            words = re.findall(r"[a-z0-9%]+", value.lower())
            if (len(words) >= 12 and
                    max((words.count(word) for word in set(words)), default=0) >= 6):
                errors.append(f"{path} contains repetitive filler")

    inspect_text(spec)

    auth = spec.get("auth") or {}
    if not auth.get("reason"):
        errors.append("auth.reason must explain the authentication decision")
    roles = spec.get("roles") or []
    role_names = [r.get("name") for r in roles]
    if len(role_names) != len(set(role_names)):
        errors.append("role names must be unique")
    if roles and not auth.get("enabled"):
        errors.append("roles require auth.enabled=true")
    for role in roles:
        if not str(role.get("home") or "").startswith("/"):
            errors.append(f"role {role.get('name')} needs an absolute home route")

    design = spec.get("design") or {}
    if not str(design.get("preset") or "").strip():
        errors.append("design.preset is required")
    if design.get("mode") not in ("light", "dark"):
        errors.append("design.mode must be light or dark")
    if design.get("navStyle") not in ("sidebar", "topnav", "none"):
        errors.append("design.navStyle must be sidebar, topnav, or none")
    palette = design.get("palette") or {}
    missing = sorted(PALETTE_KEYS - set(palette))
    if missing:
        errors.append("design.palette is missing: " + ", ".join(missing))
    for key in PALETTE_KEYS & set(palette):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(palette.get(key) or "")):
            errors.append(f"design.palette.{key} must be #RRGGBB")
    typography = design.get("typography") or {}
    if not typography.get("heading") or not typography.get("body"):
        errors.append("design.typography.heading and body are required")
    if not design.get("visualSignature"):
        errors.append("design.visualSignature is required")

    models = spec.get("data_model") or []
    model_names = [str(m.get("name") or "") for m in models]
    if len(model_names) != len(set(model_names)):
        errors.append("data model names must be unique")
    for model in models:
        name = str(model.get("name") or "")
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
            errors.append(f"model name {name!r} must be PascalCase")
        if name in RESERVED_MODELS:
            errors.append(f"model {name} is reserved for Locode authentication")
        if name.lower() in {"item", "entry", "record", "data", "thing"}:
            errors.append(f"model {name} is a generic placeholder")
        field_names = []
        for field in model.get("fields") or []:
            fname, ftype = str(field.get("name") or ""), str(field.get("type") or "")
            field_names.append(fname)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", fname):
                errors.append(f"{name} has an invalid field name {fname!r}")
            if ftype not in VALID_TYPES:
                errors.append(f"{name}.{fname} has unsupported type {ftype!r}")
            if field.get("ref") and field.get("ref") not in model_names:
                errors.append(f"{name}.{fname} references unknown model {field.get('ref')}")
        if len(field_names) != len(set(field_names)):
            errors.append(f"{name} field names must be unique")

    pages = spec.get("pages") or []
    if not pages:
        errors.append("at least one explicit page is required")
    paths = [p.get("path") for p in pages]
    if len(paths) != len(set(paths)):
        errors.append("page paths must be unique")
    raw_input = str(spec.get("_raw_idea") or "").lower()
    coverage_value = {key: value for key, value in spec.items()
                      if not str(key).startswith("_") and key != "input_hash"}
    coverage_json = json.dumps(coverage_value, ensure_ascii=False, default=str)
    coverage_text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", coverage_json).lower()
    for action, pattern in ACTION_PATTERNS.items():
        if re.search(pattern, raw_input) and not re.search(pattern, coverage_text):
            errors.append(
                f"explicit user action {action!r} is missing from page functions and component responsibilities")
        if (action in EXPLICIT_ONLY_ACTIONS and not re.search(pattern, raw_input) and
                re.search(pattern, coverage_text)):
            errors.append(f"state-changing user action {action!r} was invented without an input requirement")
    if (not re.search(ACTION_PATTERNS["save"], raw_input) and
            not re.search(ACTION_PATTERNS["bookmark"], raw_input) and
            re.search(r"\b(?:save(?:d)? teas?|save favorites?|saved favorites?|bookmark(?:s|ed|ing)?)\b",
                      coverage_text)):
        errors.append("persistent saved-tea/favorites capability was invented without an input requirement")

    page_count = re.search(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)[ -]pages?\b",
        raw_input,
    )
    if page_count:
        token = page_count.group(1)
        expected_pages = NUMBER_WORDS[token] if token in NUMBER_WORDS else int(token)
        if len(pages) != expected_pages:
            errors.append(
                f"the user explicitly requested {expected_pages} pages, but the plan declares {len(pages)}")

        # When the user names exactly that many routes/pages after a colon, those labels are part of
        # the product contract, not optional inspiration.  This prevents a valid five-route plan from
        # silently replacing "Field Notes" and "About" with unrelated "Create" and "Bookmarks" pages.
        named_list = re.search(r"\b(?:routes?|pages?)\s*:\s*([^.!?\n]+)", raw_input, re.I)
        if named_list:
            labels = [re.sub(r"^(?:(?:and|one|a|an|the)\s+)+", "", part.strip(), flags=re.I)
                      for part in re.split(r"\s*,\s*|\s+and\s+", named_list.group(1), flags=re.I)
                      if part.strip()]
            if len(labels) == expected_pages:
                def stem(word: str) -> str:
                    if len(word) > 4 and word.endswith("ies"):
                        return word[:-3] + "y"
                    if len(word) > 3 and word.endswith("s"):
                        return word[:-1]
                    return word

                for label in labels:
                    label_words = [stem(word) for word in re.findall(r"[a-z0-9]+", label.lower())
                                   if word not in {"page", "route"}]
                    if label_words == ["home"] and "/" in paths:
                        continue
                    covered = False
                    for page in pages:
                        page_value = " ".join(str(page.get(key) or "") for key in (
                            "path", "title", "kind", "purpose", "userJob", "archetype"))
                        page_words = {stem(word) for word in re.findall(r"[a-z0-9]+", page_value.lower())}
                        if label_words and all(word in page_words for word in label_words):
                            covered = True
                            break
                    if not covered:
                        errors.append(
                            f"the explicitly named page/route {label!r} is missing from the plan")

    count_pattern = r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+([a-z][a-z0-9-]*)\s+types?\b"
    for match in re.finditer(count_pattern, raw_input, re.I):
        count_text, noun = match.group(1).lower(), match.group(2).lower().rstrip("s")
        expected = NUMBER_WORDS[count_text] if count_text in NUMBER_WORDS else int(count_text)
        matching_models = [model for model in models
                           if str(model.get("name") or "").lower().rstrip("s") == noun]
        for model in matching_models:
            type_field = next((field for field in model.get("fields") or []
                               if str(field.get("name") or "").lower() == "type" and field.get("enum")), None)
            if type_field and len(type_field.get("enum") or []) != expected:
                errors.append(
                    f"the input requires exactly {expected} {noun} types, but "
                    f"{model.get('name')}.type declares {len(type_field.get('enum') or [])}")
    if re.search(r"\b(?:one|single)[ -]page\b", raw_input):
        if len(pages) != 1 or paths != ["/"]:
            errors.append("the user explicitly requested one page, so pages must contain only /")
    if re.search(r"\b(?:no|without) (?:accounts?|authentication|auth|login|sign-?up)\b", raw_input):
        if auth.get("enabled") or roles:
            errors.append("the user explicitly requested no accounts/auth, so auth must be disabled and roles empty")
    if re.search(r"\b(?:top navigation|top nav|topnav)\b", raw_input):
        if design.get("navStyle") != "topnav":
            errors.append("the user explicitly requested top navigation")
    for page in pages:
        path = str(page.get("path") or "")
        if not path.startswith("/"):
            errors.append(f"page path {path!r} must start with /")
        access = str(page.get("access") or "")
        if access == "authenticated" and not auth.get("enabled"):
            errors.append(f"{path} requires authentication but auth is disabled")
        if access.startswith("role:"):
            role = access.split(":", 1)[1]
            if not auth.get("enabled") or role not in role_names:
                errors.append(f"{path} references unknown or disabled role {role}")
        resources = list(page.get("resources") or [])
        if page.get("resource"):
            resources.append(page.get("resource"))
        for resource in resources:
            if resource not in model_names:
                errors.append(f"{path} references unknown resource {resource}")
        for key in ("purpose", "userJob", "archetype", "layout", "visualSignature"):
            if not page.get(key):
                errors.append(f"{path} is missing {key}")
        if not page.get("functions"):
            errors.append(f"{path} must declare at least one testable function")

    generation = spec.get("generation_plan") or {}
    components = generation.get("components") or []
    component_names = [item.get("name") for item in components]
    component_paths = [item.get("path") for item in components]
    if len(component_names) != len(set(component_names)):
        errors.append("generation component names must be unique")
    if len(component_paths) != len(set(component_paths)):
        errors.append("generation component paths must be unique")
    for page in pages:
        if not any(item.get("page") == page.get("path") for item in components):
            errors.append(f"{page.get('path')} needs at least one generation component")
    for item in components:
        name, path = str(item.get("name") or ""), str(item.get("path") or "")
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
            errors.append(f"generation component {name!r} must be PascalCase")
        if not re.fullmatch(r"components/(?:features|pages|layout|layouts)/[A-Za-z0-9_./-]+\.tsx", path):
            errors.append(f"generation component {name} has invalid path {path!r}")
        if item.get("page") not in paths:
            errors.append(f"generation component {name} references unknown page {item.get('page')}")
        if not item.get("responsibility"):
            errors.append(f"generation component {name} is missing responsibility")
        prop_names = set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*:", str(item.get("props") or "")))
        state_names = {str(value).split(":", 1)[0].strip() for value in (item.get("state") or [])
                       if str(value).strip()}
        collisions = sorted(prop_names & state_names)
        if collisions:
            errors.append(
                f"generation component {name} reuses prop name(s) as local state: "
                + ", ".join(collisions))
        if not 60 <= int(item.get("expectedLines") or 0) <= 180:
            errors.append(f"generation component {name} expectedLines must be 60-180")
    planned_paths = set(component_paths)
    flattened = [path for wave in generation.get("dependencyWaves") or [] for path in wave]
    if set(flattened) != planned_paths or len(flattened) != len(set(flattened)):
        errors.append("generation dependencyWaves must schedule every component exactly once")
    if any(len(wave) > 2 for wave in generation.get("dependencyWaves") or []):
        errors.append("generation dependency waves may contain at most two components")
    wave_index = {path: index for index, wave in enumerate(
        generation.get("dependencyWaves") or []) for path in wave}
    for item in components:
        consumer = item.get("path")
        for dependency in item.get("dependencies") or []:
            if dependency not in planned_paths:
                errors.append(f"generation component {item.get('name')} has unknown dependency {dependency}")
            elif wave_index.get(dependency, -1) >= wave_index.get(consumer, -1):
                errors.append(
                    f"generation dependency {dependency} must be scheduled before consumer {consumer}")
    return errors


class ArchitectAgent:
    """One strong-model planning call, with validation-driven correction retries."""

    def __init__(self, model: str | None = None):
        self.model = llm.pinned_architect_model(model or llm.ARCHITECT_MODEL)

    def plan(self, raw_input: str, *, locked_spec: dict | None = None) -> dict:
        if not isinstance(raw_input, str) or not raw_input.strip():
            raise ArchitectError("The application input is empty")
        locked = json.dumps(locked_spec, ensure_ascii=False, indent=2) if locked_spec else ""
        base = (
            "FULL USER INPUT (preserve every explicit requirement):\n"
            f"<user_input>\n{raw_input}\n</user_input>\n\n"
            "EXACT OUTPUT JSON SCHEMA (authoritative; follow every required key and type):\n"
            f"{json.dumps(ARCHITECT_JSON_SCHEMA, ensure_ascii=False, separators=(',', ':'))}\n\n"
        )
        if locked:
            base += (
                "LOCKED NORMALIZED SRS (preserve its roles, pages, models, functions, relationships, and "
                "permissions exactly; enrich only missing design/page-intent fields):\n"
                f"<locked_spec>\n{locked}\n</locked_spec>\n\n"
            )
        correction = ""
        # Budget is input-sized; thinking is disabled so all predicted tokens are
        # reserved for the complete structured contract.
        input_bytes = len(raw_input.encode("utf-8"))
        output_budget = max(10_000, min(16_000, 9_000 + input_bytes // 2))
        best_candidate: dict = {}
        best_issues: list[str] = []
        for attempt in range(3):
            prompt = base + correction + "Return the complete normalized JSON object now."
            try:
                from agents.product_context import ensure_fits
                attempt_budget = min(20_000, output_budget + attempt * 2_000)
                ensure_fits(prompt, output_tokens=attempt_budget,
                            context_tokens=llm.CLOUD_CONTEXT_TOKENS,
                            model_label="Nemotron Cloud")
                answer = llm.chat(
                    [{"role": "user", "content": prompt}],
                    model=self.model,
                    system=ARCHITECT_SYSTEM,
                    num_predict=attempt_budget,
                    think=False,
                    extra_opts={**llm.ARCHITECT_OPTS, "seed": int(hashlib.sha256(
                        raw_input.encode("utf-8")).hexdigest()[:8], 16)},
                    route="architect",
                    timeout=600,
                )
            except (llm.LLMTruncatedError, llm.LLMError) as exc:
                raise ArchitectError(f"Nemotron Cloud Architect failed without a usable plan: {exc}") from exc
            parsed = _parse_json(answer)
            if not parsed:
                issues = ["reply was not a raw JSON object"]
            else:
                candidate = _deep_merge(best_candidate, parsed) if best_candidate else parsed
                spec = normalize_spec(candidate, raw_input)
                issues = validate_spec(spec)
                if locked_spec:
                    issues.extend(self._locked_drift(locked_spec, spec))
                if not issues:
                    log.info("Architect produced %d pages, %d models, auth=%s",
                             len(spec["pages"]), len(spec["data_model"]), spec["auth"]["enabled"])
                    return spec
                if not best_candidate or len(issues) < len(best_issues):
                    best_candidate = deepcopy(candidate)
                    best_issues = list(issues)
            if attempt < 2:
                correction_issues = best_issues or issues
                previous = json.dumps(best_candidate, ensure_ascii=False, indent=2) if best_candidate else answer
                correction = (
                    "\nPREVIOUS INVALID ANSWER (edit this exact plan; do not restart or change the product):\n"
                    f"<previous_answer>\n{previous}\n</previous_answer>\n\n"
                    "Correct every validation issue below and return the complete JSON object. Preserve all "
                    "valid input-specific decisions. Dependencies and dependencyWaves must use exact component "
                    "paths declared in generation_plan.components; use an empty dependency list when none.\n- "
                    + "\n- ".join(correction_issues) + "\n"
                )
                log.warning("Architect semantic correction %d/2: %s",
                            attempt + 1, "; ".join(correction_issues))
        raise ArchitectError("Nemotron Cloud Architect could not produce a valid plan after 3 attempts")

    def enrich_structured(self, raw_input: str, locked_spec: dict) -> dict:
        """Add missing visual/page intent to an SRS without allowing inventory drift."""
        source = deepcopy(locked_spec)
        page_paths = [str(page.get("path") or "") for page in source.get("pages") or []]
        system = f"""You are Locode's design architect. Return one raw JSON object only.
{DESIGN_BAR}
Thinking is disabled. Emit the complete JSON directly.
The structured SRS is immutable: do not return or alter roles, models, functions, sections,
permissions, relationships, components, or routes. Return exactly:
{{"design": {{the complete canonical design object from the Locode contract}},
  "pages": [{{"path":"an existing exact path","purpose":"...","userJob":"...",
  "primaryAction":"...","archetype":"...","layout":"...","visualSignature":"..."}}],
  "generation_plan": {{"components":[component contracts from the Locode schema],
  "dependencyWaves":[["component paths, maximum two per wave"]]}}}}
Include every existing path exactly once. Decompose each locked page into input-specific semantic
components without changing the SRS inventory. Choose all missing intent from the complete SRS.
"""
        base = (
            f"FULL STRUCTURED USER INPUT:\n<user_input>\n{raw_input}\n</user_input>\n\n"
            "LOCKED NORMALIZED SRS:\n<locked_spec>\n"
            f"{json.dumps(source, ensure_ascii=False, indent=2)}\n</locked_spec>\n\n"
        )
        enrich_schema = {"type": "object", "properties": {
            "design": _DESIGN_SCHEMA,
            "pages": {"type": "array", "items": {"type": "object", "properties": {
                "path": {"type": "string"}, "purpose": {"type": "string"},
                "userJob": {"type": "string"}, "primaryAction": {"type": "string"},
                "archetype": {"type": "string"}, "layout": {"type": "string"},
                "visualSignature": {"type": "string"}},
                "required": ["path", "purpose", "userJob", "primaryAction", "archetype",
                              "layout", "visualSignature"]}},
            "generation_plan": {"type": "object", "properties": {
                "components": {"type": "array", "items": _COMPONENT_SCHEMA, "minItems": 1},
                "dependencyWaves": {"type": "array", "items": _STRING_ARRAY}},
                "required": ["components", "dependencyWaves"]},
        }, "required": ["design", "pages", "generation_plan"]}
        _seal_schema_objects(enrich_schema)
        base += ("EXACT OUTPUT JSON SCHEMA (authoritative; follow every required key and type):\n"
                 + json.dumps(enrich_schema, ensure_ascii=False, separators=(",", ":")) + "\n\n")
        correction = ""
        input_bytes = len(raw_input.encode("utf-8"))
        output_budget = max(8_000, min(14_000, 7_200 + input_bytes // 3))
        for attempt in range(3):
            prompt = base + correction + "Return the design enrichment JSON."
            from agents.product_context import ensure_fits
            attempt_budget = min(18_000, output_budget + attempt * 2_000)
            ensure_fits(prompt, output_tokens=attempt_budget,
                        context_tokens=llm.CLOUD_CONTEXT_TOKENS,
                        model_label="Nemotron Cloud")
            answer = llm.chat(
                [{"role": "user", "content": prompt}],
                model=self.model, system=system,
                num_predict=attempt_budget, think=False,
                extra_opts={**llm.ARCHITECT_OPTS, "seed": int(hashlib.sha256(
                    raw_input.encode("utf-8")).hexdigest()[:8], 16)},
                route="architect", timeout=600,
            )
            value = _parse_json(answer)
            design = value.get("design") if isinstance(value.get("design"), dict) else {}
            enrichments = value.get("pages") if isinstance(value.get("pages"), list) else []
            generation_value = value.get("generation_plan") if isinstance(
                value.get("generation_plan"), dict) else {}
            got_paths = [str(page.get("path") or "") for page in enrichments if isinstance(page, dict)]
            issues = []
            if not str(design.get("preset") or "").strip():
                issues.append("design.preset is required")
            if design.get("mode") not in ("light", "dark"):
                issues.append("design.mode must be light or dark")
            if design.get("navStyle") not in ("sidebar", "topnav", "none"):
                issues.append("design.navStyle is invalid")
            palette = design.get("palette") if isinstance(design.get("palette"), dict) else {}
            if PALETTE_KEYS - set(palette):
                issues.append("design.palette is incomplete")
            if sorted(got_paths) != sorted(page_paths) or len(got_paths) != len(page_paths):
                issues.append("page enrichment paths must exactly match the locked SRS")
            if not generation_value.get("components"):
                issues.append("generation_plan must decompose the locked pages")
            if not issues:
                by_path = {str(page["path"]): page for page in enrichments if isinstance(page, dict)}
                source["design"] = design
                for page in source.get("pages") or []:
                    extra = by_path.get(str(page.get("path") or ""), {})
                    for key in ("purpose", "userJob", "primaryAction", "archetype", "layout",
                                "visualSignature"):
                        if not page.get(key) and extra.get(key):
                            page[key] = extra[key]
                palette = design.get("palette") or {}
                source["theme"] = {"accent": palette.get("primary", ""),
                                   "accent2": palette.get("secondary", "")}
                source["style"] = design.get("preset", "")
                source["color_scheme"] = ", ".join(
                    str(palette.get(k)) for k in ("primary", "secondary", "accent") if palette.get(k))
                source["_raw_idea"] = raw_input
                source["input_hash"] = hashlib.sha256(raw_input.encode("utf-8")).hexdigest()
                source["generation_plan"] = normalize_generation_plan(generation_value, source)
                generation_issues = [issue for issue in validate_spec(source)
                                     if issue.startswith("generation")]
                if generation_issues:
                    correction = (
                        "\nPREVIOUS INVALID ANSWER:\n<previous_answer>\n" + answer +
                        "\n</previous_answer>\nCorrect these validation errors while preserving all valid "
                        "decisions:\n- " + "\n- ".join(generation_issues) + "\n")
                    continue
                return source
            correction = (
                "\nPREVIOUS INVALID ANSWER:\n<previous_answer>\n" + answer +
                "\n</previous_answer>\nCorrect these validation errors while preserving all valid "
                "decisions:\n- " + "\n- ".join(issues) + "\n")
        raise ArchitectError("Nemotron Cloud could not enrich the structured SRS without changing it")

    @staticmethod
    def _locked_drift(locked: dict, planned: dict) -> list[str]:
        """Prevent design enrichment from silently changing a structured SRS inventory."""
        issues = []
        for key in ("roles", "data_model", "pages", "relationships", "actions", "component_contracts"):
            if key in locked and locked.get(key) != planned.get(key):
                issues.append(f"locked structured-SRS field changed: {key}")
        return issues
