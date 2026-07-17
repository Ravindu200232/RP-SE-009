"""agents/contract.py — the Canonical Contract Registry (P2).

ONE source of truth for entities + fields. Everything downstream (Mongoose model, Zod create/
update, TS DTOs, API response types, form-field metadata, table columns, seed shapes) is derived
from here, so an agent can never invent a different field name in a page/API/form than the model
declares. The frontend consumes the generated `types/<Entity>.ts` DTOs, so TypeScript itself catches
field-name drift at build time; the AST ContractUsageScanner catches it before the build.

Pure + deterministic — built from the normalized `spec.data_model`. No LLM.
"""
from __future__ import annotations

from pathlib import Path

from agents.scaffold import pascal, route_name

# Fields the server owns — never in a form, never client-set.
OWNER_FIELDS = {"owner", "userId", "createdBy", "recordedBy", "receivedBy", "reviewedBy",
                "processedBy", "markedBy", "publishedBy", "collectedBy", "settledBy"}
# Timestamps / mongoose meta present on every doc.
META_FIELDS = {"_id", "__v", "createdAt", "updatedAt"}

_DISPLAY_ORDER = ("name", "title", "label", "fullName", "code", "email")


def _ts_type(f: dict) -> str:
    t = str(f.get("type", "String"))
    if f.get("enum"):
        # Client DTO uses `string`, NOT a strict literal union. LLM-generated components set enum
        # fields from `e.target.value` (a plain string), which never assigns to `'a' | 'b'` and caused
        # the dominant class of build errors (TS2322/TS2345 "string not assignable"). The Mongoose
        # `enum` + the Zod schema still enforce the valid set server-side, so validity is preserved;
        # only the compile-time literal narrowing (of little value on LLM output) is dropped. The exact
        # allowed values remain in the CONTRACT memory + the form `<Select>` options.
        return "string"
    if t.startswith("["):
        inner = t[1:-1]
        # Primitive arrays stay typed. A Mongoose `Mixed`/sub-document array is genuinely untyped and
        # LLM components use it every which way (rendered as a node, bound to an input, even set to a
        # joined string), so `any` is the honest type that lets all those usages compile — `unknown[]`
        # blocked every one.
        return {"String": "string[]", "ObjectId": "string[]", "Number": "number[]"}.get(inner, "any")
    return {"Number": "number", "Boolean": "boolean", "Date": "string",
            "ObjectId": "string", "Mixed": "any"}.get(t, "string")


def _control(f: dict) -> str:
    if f.get("ref"):
        return "ref-select"
    if f.get("enum"):
        return "enum-select"
    return {"Boolean": "checkbox", "Number": "number", "Date": "date"}.get(str(f.get("type")), "text")


def display_field(model: dict) -> str:
    """The human-readable field to show for a record in dropdowns/tables."""
    names = [f.get("name") for f in (model.get("fields") or []) if f.get("name")]
    for cand in _DISPLAY_ORDER:
        if cand in names:
            return cand
    # any `*Name` / `*No` / `*Code`
    for n in names:
        low = n.lower()
        if low.endswith(("name", "no", "code", "title")):
            return n
    return names[0] if names else "_id"


def entity_contract(model: dict, by_name: dict) -> dict:
    """The canonical contract for one entity: fields, form metadata, columns, display field, DTO."""
    name = pascal(model.get("name", "Item"))
    fields = [f for f in (model.get("fields") or []) if f.get("name")]
    form_meta = []
    for f in fields:
        if f["name"] in OWNER_FIELDS:
            continue
        ref = f.get("ref")
        rmodel = by_name.get(pascal(ref)) if ref else None
        form_meta.append({
            "name": f["name"],
            "control": _control(f),
            "required": bool(f.get("required")),
            "type": f.get("type", "String"),
            "enum": f.get("enum"),
            "ref": pascal(ref) if ref else None,
            "endpoint": f"/api/{route_name(ref)}" if ref else None,
            "displayField": display_field(rmodel) if rmodel else None,
        })
    columns = [f["name"] for f in fields if f["name"] not in OWNER_FIELDS][:5]
    return {
        "name": name,
        "segment": route_name(name),
        "fieldNames": [f["name"] for f in fields],
        "displayField": display_field(model),
        "form": form_meta,
        "columns": columns,
        "dto": _dto_ts(name, fields),
    }


def _dto_ts(name: str, fields: list) -> str:
    lines = [f"export interface {name} {{", "  _id: string"]
    for f in fields:
        if f["name"] in OWNER_FIELDS or f["name"] in META_FIELDS:
            continue
        # Every declared field is NON-optional in the read DTO. This DTO types records returned by the
        # API — the server stores + returns each declared field (mongoose defaults fill the rest), so a
        # read is never `undefined`. Measured on real LLM output this cuts build errors sharply: it kills
        # the whole `possibly undefined` (TS18048) class AND the `string | undefined not assignable to
        # string` assignments (optional field → a form's string state), which dominate otherwise. LLM
        # components read fields far more than they construct full typed entity literals, so non-optional
        # nets strongly positive.
        lines.append(f"  {f['name']}: {_ts_type(f)}")
    # Timestamps are required for the same reason, and they used to be the one exception — which
    # reintroduced exactly the class above: every model is built with `{ timestamps: true }`
    # (scaffold.model_file), so mongoose sets both on every document and a read always has them, yet
    # `createdAt?: string` made the obvious `new Date(row.createdAt)` a build error.
    lines += ["  createdAt: string", "  updatedAt: string", "}", ""]
    return "\n".join(lines)


def build_registry(spec: dict) -> dict:
    """{ EntityName: contract } for every model in the spec (User excluded — auth owns it)."""
    models = [m for m in (spec.get("data_model") or []) if pascal(m.get("name", "")) != "User"]
    by_name = {pascal(m.get("name", "")): m for m in models}
    return {pascal(m.get("name", "Item")): entity_contract(m, by_name) for m in models}


# Auth owns the User entity, so it is excluded from the data-model registry — but pages/forms still
# `import type { User } from '@/types'` (admin user list, current actor, etc.). Emit a client-safe User
# DTO here (never the passwordHash) so those imports resolve.
_USER_DTO = (
    "export interface User {\n"
    "  _id: string\n"
    "  email: string\n"
    "  name: string\n"
    "  role: string\n"
    "  createdAt: string\n"
    "  updatedAt: string\n"
    "}\n"
)


def types_files(registry: dict) -> dict[str, str]:
    """`types/<Entity>.ts` DTO per entity + a client-safe User DTO + a barrel `types/index.ts`."""
    files: dict[str, str] = {"types/User.ts": _USER_DTO}
    for name, c in registry.items():
        files[f"types/{name}.ts"] = c["dto"]
    names = ["User", *registry.keys()]
    files["types/index.ts"] = "".join(f"export * from './{n}'\n" for n in names)
    return files


def contract_md(registry: dict) -> str:
    """Human/agent-readable memory: exact field names per entity — agents must not invent others."""
    out = ["# CONTRACT — the ONLY valid field names per entity", "",
           "Use EXACTLY these field names in models, routes, forms, tables and pages. Type a row as",
           "the entity DTO from `@/types` so TypeScript catches wrong names. `_id` is the id (never `id`).",
           ""]
    for name, c in registry.items():
        out.append(f"## {name}  (`/api/{c['segment']}`, display: `{c['displayField']}`)")
        for fm in c["form"]:
            extra = (f" → dropdown `{fm['endpoint']}` (show `{fm['displayField']}`)" if fm["control"] == "ref-select"
                     else f" enum[{'|'.join(map(str, fm['enum'] or []))}]" if fm["control"] == "enum-select" else "")
            req = " required" if fm["required"] else ""
            out.append(f"- `{fm['name']}`: {fm['control']}{req}{extra}")
        out.append("")
    return "\n".join(out) + "\n"
