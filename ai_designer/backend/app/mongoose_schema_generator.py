"""MongoDB schema + runtime generator.

Generates, from a planned data model:
* `src/lib/orm.js` — a relationship-aware data-access runtime over the native
  `mongodb` driver (already a scaffold dependency) with a local-JSON fallback so
  generated apps run offline. Provides CRUD + ref validation + populate +
  counter/array side-effect helpers. (Mongoose itself is NOT a scaffold
  dependency, so we target the installed native driver to keep `next build`
  green while still modelling refs, indexes, enums, validation, and virtuals.)
* `src/lib/models/<Entity>.js` — one declarative schema descriptor per entity
  (fields, typed, enums, unique, indexes, refs with collection + cardinality).
* `src/lib/models/index.js` — the model registry keyed by name and collection.

These descriptors are consumed by the API-route, service, and CRUD-UI
generators so every entity gets real, relationship-aware code (not renamed
generic CRUD).
"""
from __future__ import annotations

import json


# --------------------------------------------------------------------------- #
# Fixed runtime (lib/orm.js) — relationship-aware data access, server-only.
# --------------------------------------------------------------------------- #

ORM_RUNTIME = r"""// AUTO-GENERATED relationship-aware data runtime (server-only).
// Backends: MongoDB (native driver) when MONGODB_URI is set, else local JSON.
import fs from 'fs';
import path from 'path';

const DB_PATH = path.join(process.cwd(), 'data', 'db.json');
const MONGO_URI = process.env.MONGODB_URI || '';
const MONGO_DB = process.env.MONGODB_DB || 'app';

async function db() {
  if (!MONGO_URI) return null;
  try {
    if (!global.__ormClientPromise) {
      const { MongoClient } = await import('mongodb');
      global.__ormClientPromise = new MongoClient(MONGO_URI, { serverSelectionTimeoutMS: 4000 }).connect();
    }
    const client = await global.__ormClientPromise;
    return client.db(MONGO_DB);
  } catch (e) {
    console.error('orm: mongo unavailable, using JSON fallback:', e.message);
    return null;
  }
}

function loadJson() { try { return JSON.parse(fs.readFileSync(DB_PATH, 'utf-8')); } catch (e) { return {}; } }
function saveJson(o) { fs.mkdirSync(path.dirname(DB_PATH), { recursive: true }); fs.writeFileSync(DB_PATH, JSON.stringify(o, null, 2)); }
function newId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
const strip = (d) => { if (!d) return d; const { _id, ...rest } = d; return rest; };

export async function listDocs(collection, opts = {}) {
  const { search = '', filter = {}, page = 1, limit = 50 } = opts;
  const conn = await db();
  let rows;
  if (conn) rows = (await conn.collection(collection).find({}).limit(2000).toArray()).map(strip);
  else { const j = loadJson(); rows = Array.isArray(j[collection]) ? j[collection] : []; }
  rows = rows.filter((row) => {
    for (const [k, v] of Object.entries(filter || {})) {
      if (v !== undefined && v !== '' && String(row?.[k]) !== String(v)) return false;
    }
    if (search) { if (!JSON.stringify(row).toLowerCase().includes(String(search).toLowerCase())) return false; }
    return true;
  });
  const total = rows.length;
  const p = Math.max(1, Number(page) || 1);
  const start = (p - 1) * limit;
  return { rows: rows.slice(start, start + limit), total, page: p, limit };
}

export async function getDoc(collection, id) {
  if (!id) return null;
  const conn = await db();
  if (conn) return strip(await conn.collection(collection).findOne({ id: String(id) }));
  const j = loadJson();
  return (j[collection] || []).find((r) => String(r?.id) === String(id)) || null;
}

export async function createDoc(collection, data) {
  const rec = { id: newId(), createdAt: new Date().toISOString(), ...(data || {}) };
  const conn = await db();
  if (conn) { await conn.collection(collection).insertOne({ ...rec }); return rec; }
  const j = loadJson(); if (!Array.isArray(j[collection])) j[collection] = []; j[collection].push(rec); saveJson(j); return rec;
}

export async function updateDoc(collection, id, patch) {
  const conn = await db();
  if (conn) {
    const { id: _i, _id, ...p } = patch || {};
    const res = await conn.collection(collection).findOneAndUpdate({ id: String(id) }, { $set: p }, { returnDocument: 'after' });
    return strip(res && (res.value || res));
  }
  const j = loadJson(); const rows = j[collection] || [];
  const i = rows.findIndex((r) => String(r?.id) === String(id));
  if (i === -1) return null;
  rows[i] = { ...rows[i], ...(patch || {}), id: rows[i].id }; j[collection] = rows; saveJson(j); return rows[i];
}

export async function removeDoc(collection, id) {
  const conn = await db();
  if (conn) return (await conn.collection(collection).deleteOne({ id: String(id) })).deletedCount > 0;
  const j = loadJson(); const rows = j[collection] || [];
  const next = rows.filter((r) => String(r?.id) !== String(id)); j[collection] = next; saveJson(j);
  return rows.length !== next.length;
}

/* ---- relationship helpers ---- */

// Validate required refs point to existing documents. `provided` limits checks
// to fields present in the payload (for PATCH).
export async function validateRefs(refs, data, provided) {
  const errors = [];
  for (const ref of refs || []) {
    const has = !provided || provided.includes(ref.field);
    const val = data?.[ref.field];
    if (!val) { if (ref.required && !provided) errors.push(ref.label + ' is required'); continue; }
    if (!has) continue;
    const exists = await getDoc(ref.collection, val);
    if (!exists) errors.push(ref.label + ' references a missing ' + ref.target);
  }
  return errors;
}

export async function populateDoc(doc, refs) {
  if (!doc) return doc;
  const out = { ...doc };
  for (const ref of refs || []) {
    const val = doc[ref.field];
    if (!val) continue;
    const rel = await getDoc(ref.collection, val);
    if (rel) out['_' + ref.field] = { id: rel.id, label: rel.name || rel.title || rel.email || rel.number || rel.id };
  }
  return out;
}

export async function populateMany(docs, refs) {
  const out = [];
  for (const d of docs || []) out.push(await populateDoc(d, refs));
  return out;
}

// Documents that reference this one (block/cascade decisions).
export async function countReferencing(referencedBy, id) {
  let total = 0;
  for (const link of referencedBy || []) {
    const { rows } = await listDocs(link.collection, { filter: { [link.field]: String(id) }, limit: 1 });
    total += rows.length;
  }
  return total;
}

/* ---- side-effect helpers ---- */
export async function incField(collection, id, field, by = 1) {
  const cur = await getDoc(collection, id); if (!cur) return null;
  return updateDoc(collection, id, { [field]: (Number(cur[field]) || 0) + by });
}
export async function pushField(collection, id, field, value) {
  const cur = await getDoc(collection, id); if (!cur) return null;
  const arr = Array.isArray(cur[field]) ? cur[field] : [];
  return updateDoc(collection, id, { [field]: [...arr, value] });
}
export async function setFields(collection, id, patch) { return updateDoc(collection, id, patch || {}); }

// Find one matching doc by an equality filter (used for stock-by-product, etc.).
export async function findOneBy(collection, filter) {
  const { rows } = await listDocs(collection, { filter, limit: 1 });
  return rows[0] || null;
}
"""


# --------------------------------------------------------------------------- #
# Per-entity model descriptors
# --------------------------------------------------------------------------- #

def _collection_of(name, model):
    for e in model["entities"]:
        if e["name"] == name:
            return e["collection"]
    # User is always present when referenced
    return _guess_collection(name)


def _guess_collection(name):
    base = name[:1].lower() + name[1:]
    if base.endswith("y") and base[-2:-1] not in "aeiou":
        return base[:-1] + "ies"
    if base.endswith(("s", "x", "z", "ch", "sh")):
        return base + "es"
    return base + "s"


def model_descriptor(entity, model):
    """Build the plain-data descriptor embedded into the generated model file."""
    refs = []
    for rel in entity["relationships"]:
        refs.append({
            "field": rel["field"],
            "target": rel["target"],
            "collection": _collection_of(rel["target"], model),
            "required": rel["required"],
            "cardinality": rel["cardinality"],
            "owner": rel.get("owner", False),
        })
    enums = {fl["name"]: fl["enum"] for fl in entity["fields"] if fl.get("enum")}
    return {
        "name": entity["name"],
        "collection": entity["collection"],
        "label": entity["label"],
        "fields": entity["fields"],
        "refs": refs,
        "indexes": entity["indexes"],
        "unique": entity["unique"],
        "enums": enums,
        "embeds": entity.get("embeds", []),
        "referencedBy": [
            {"entity": rb["entity"], "field": rb["field"], "collection": _collection_of(rb["entity"], model)}
            for rb in entity.get("referenced_by", [])
        ],
        "access": entity.get("access", {}),
    }


def generate_model_file(entity, model) -> str:
    desc = model_descriptor(entity, model)
    body = json.dumps(desc, indent=2)
    return (
        f"// AUTO-GENERATED model descriptor for {entity['name']}.\n"
        f"export const {entity['name']} = {body};\n\n"
        f"export default {entity['name']};\n"
    )


def generate_models_index(model) -> str:
    names = [e["name"] for e in model["entities"]]
    imports = "\n".join(f"import {{ {n} }} from './{n}';" for n in names)
    registry = ", ".join(names)
    by_coll = ",\n  ".join(f"'{e['collection']}': {e['name']}" for e in model["entities"])
    return (
        "// AUTO-GENERATED model registry.\n"
        f"{imports}\n\n"
        f"export const Models = {{ {registry} }};\n\n"
        f"export const byCollection = {{\n  {by_coll}\n}};\n\n"
        "export function modelFor(collection) { return byCollection[collection] || null; }\n"
    )


def field_js_type(ftype: str) -> str:
    return {
        "number": "Number", "currency": "Number", "boolean": "Boolean",
        "date": "Date", "datetime": "Date",
    }.get(ftype, "String")
