"""Workflow / service layer generator.

Per entity it generates `src/lib/services/<Entity>Service.js` with
`create<Entity>`, `update<Entity>`, `delete<Entity>`, and any workflow methods
(`cancel<Entity>`, `pay<Entity>`, ...) implied by the model's side effects.

Workflow logic lives here, NOT in route handlers, so relationship side effects
run consistently:
* ref validation before insert/update,
* counter increment/decrement on related docs,
* stock adjustment by embedded line items (POS/ERP),
* child-record creation (invoice items, stock movements, progress, order items),
* status propagation to related docs (table reserved, vehicle sold, invoice paid),
* relation-guarded delete (block when referenced).
"""
from __future__ import annotations


def _camel(name):
    return name[:1].lower() + name[1:]


def _name_to_collection(model):
    out = {e["name"]: e["collection"] for e in model["entities"]}
    return out


def _guess_collection(name):
    base = name[:1].lower() + name[1:]
    if base.endswith("y") and base[-2:-1] not in "aeiou":
        return base[:-1] + "ies"
    if base.endswith(("s", "x", "z", "ch", "sh")):
        return base + "es"
    return base + "s"


def _ref_field_to(entity, target):
    for rel in entity["relationships"]:
        if rel["target"] == target:
            return rel["field"]
    return None


def _has_branch(entity):
    return any(rel["target"] == "Branch" for rel in entity["relationships"])


_STATUS_VALUE = {
    "RestaurantTable": "reserved", "Vehicle": "sold", "Invoice": "paid", "Bill": "paid",
}


def _status_value(entity_name, target):
    if entity_name == "Order" and target == "RestaurantTable":
        return "occupied"
    return _STATUS_VALUE.get(target, "confirmed")


def _effect_lines(entity, eff, n2c, indent="  "):
    target = eff["target"]
    field = eff.get("field")
    action = eff["action"]
    tcoll = n2c.get(target, _guess_collection(target))
    ref_field = _ref_field_to(entity, target)
    lines = []
    if action in ("increment", "decrement"):
        sign = "1" if action == "increment" else "-1"
        if ref_field:
            lines.append(f"{indent}if (rec.{ref_field}) await orm.incField('{tcoll}', rec.{ref_field}, '{field}', {sign});")
        elif entity.get("embeds"):
            branch = "rec.branchId" if _has_branch(entity) else "undefined"
            filt = "{ productId: it.productId" + (", branchId: rec.branchId" if branch != "undefined" else "") + " }"
            lines.append(f"{indent}for (const it of (rec.items || [])) {{")
            lines.append(f"{indent}  const stock = await orm.findOneBy('{tcoll}', {filt});")
            lines.append(f"{indent}  if (stock) await orm.incField('{tcoll}', stock.id, '{field}', {sign} * (Number(it.qty) || 0));")
            lines.append(f"{indent}}}")
    elif action == "append-history" and ref_field:
        lines.append(f"{indent}if (rec.{ref_field}) await orm.pushField('{tcoll}', rec.{ref_field}, '{field}', rec.id);")
    elif action == "set-status":
        value = _status_value(entity["name"], target)
        if target == entity["name"]:
            lines.append(f"{indent}await orm.setFields('{entity['collection']}', rec.id, {{ {field}: '{value}' }});")
        elif ref_field:
            lines.append(f"{indent}if (rec.{ref_field}) await orm.setFields('{tcoll}', rec.{ref_field}, {{ {field}: '{value}' }});")
    elif action == "notify":
        lines.append(f"{indent}/* side effect: notify {target} (a Notification record would be created here) */")
    elif action == "create-children":
        parent_field = _camel(entity["name"]) + "Id"
        if entity.get("embeds") and target == "StockMovement":
            mtype = "in" if entity["name"] == "GRN" else "out"
            lines.append(f"{indent}for (const it of (rec.items || [])) {{")
            lines.append(f"{indent}  await orm.createDoc('{tcoll}', {{ {parent_field}: rec.id, productId: it.productId, branchId: rec.branchId, type: '{mtype}', qty: Number(it.qty) || 0 }});")
            lines.append(f"{indent}}}")
        elif entity.get("embeds"):
            lines.append(f"{indent}for (const it of (rec.items || [])) {{")
            lines.append(f"{indent}  await orm.createDoc('{tcoll}', {{ {parent_field}: rec.id, ...it }});")
            lines.append(f"{indent}}}")
        else:
            lines.append(f"{indent}await orm.createDoc('{tcoll}', {{ {parent_field}: rec.id }});")
    return lines


def _allowed_keys(entity):
    keys = [fl["name"] for fl in entity["fields"]]
    keys += [rel["field"] for rel in entity["relationships"]]
    keys += [emb["name"] for emb in entity.get("embeds", [])]
    # de-dup
    out, seen = [], set()
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def generate_service_file(entity, model) -> str:
    name = entity["name"]
    coll = entity["collection"]
    n2c = _name_to_collection(model)

    by_on = {}
    for eff in entity["side_effects"]:
        by_on.setdefault(eff["on"], []).append(eff)

    create_lines = []
    for eff in by_on.get("create", []):
        create_lines += _effect_lines(entity, eff, n2c)
    create_block = ("\n  // --- relationship side effects ---\n" + "\n".join(create_lines)) if create_lines else ""

    allowed = ", ".join(f"'{k}'" for k in _allowed_keys(entity))

    parts = [
        f"// AUTO-GENERATED service for {name} (workflow + relationship side effects).",
        f"import {{ {name} }} from '@/lib/models/{name}';",
        "import * as orm from '@/lib/orm';",
        "",
        f"const ALLOWED = [{allowed}];",
        "function pick(data) { const out = {}; for (const k of ALLOWED) { if (data && data[k] !== undefined) out[k] = data[k]; } return out; }",
        "",
        f"export async function create{name}(data) {{",
        "  const clean = pick(data);",
        f"  const errors = await orm.validateRefs({name}.refs, clean);",
        "  if (errors.length) { const e = new Error(errors.join('; ')); e.status = 400; throw e; }",
        f"  const rec = await orm.createDoc('{coll}', clean);{create_block}",
        "  return rec;",
        "}",
        "",
        f"export async function update{name}(id, data) {{",
        "  const clean = pick(data);",
        "  const provided = Object.keys(clean);",
        f"  const errors = await orm.validateRefs({name}.refs, clean, provided);",
        "  if (errors.length) { const e = new Error(errors.join('; ')); e.status = 400; throw e; }",
        f"  return orm.updateDoc('{coll}', id, clean);",
        "}",
        "",
        f"export async function delete{name}(id) {{",
        f"  const refCount = await orm.countReferencing({name}.referencedBy, id);",
        "  if (refCount > 0) { const e = new Error('Cannot delete: ' + refCount + ' related record(s) still reference this'); e.status = 409; throw e; }",
    ]
    delete_lines = []
    for eff in by_on.get("delete", []):
        delete_lines += _effect_lines(entity, eff, n2c)
    if delete_lines:
        parts.append(f"  const rec = await orm.getDoc('{coll}', id);")
        parts.append("  if (rec) {")
        parts += [("  " + ln) for ln in delete_lines]
        parts.append("  }")
    parts.append(f"  return orm.removeDoc('{coll}', id);")
    parts.append("}")

    # Workflow methods for non-create/update/delete side-effect triggers (cancel, pay, ...).
    for on, effs in by_on.items():
        if on in ("create", "delete"):
            continue
        method = on[:1].upper() + on[1:]
        status_val = "cancelled" if on == "cancel" else ("paid" if on == "pay" else on)
        has_status = any(fl["name"] == "status" for fl in entity["fields"])
        set_status = f"  const rec = await orm.updateDoc('{coll}', id, {{ status: '{status_val}' }});" if has_status \
            else f"  const rec = await orm.getDoc('{coll}', id);"
        eff_lines = []
        for eff in effs:
            eff_lines += _effect_lines(entity, eff, n2c)
        parts += [
            "",
            f"export async function {on}{name}(id) {{",
            set_status,
            "  if (!rec) return null;",
        ]
        parts += eff_lines
        parts += ["  return rec;", "}"]

    return "\n".join(parts) + "\n"
