// Server-side database layer with TWO backends:
//  - MongoDB (when MONGODB_URI is set in .env.local; database = MONGODB_DB,
//    which the generator sets to the project id)
//  - local JSON file fallback (data/db.json) so the app always works offline.
// Used ONLY by API route handlers (Node runtime).
import fs from 'fs';
import path from 'path';

const DB_PATH = path.join(process.cwd(), 'data', 'db.json');
const MONGO_URI = process.env.MONGODB_URI || '';
const MONGO_DB = process.env.MONGODB_DB || 'app';

/* ------------------------------ Mongo client ----------------------------- */
let _clientPromise = null;

async function mongo() {
  if (!MONGO_URI) return null;
  try {
    if (!global.__mongoClientPromise) {
      // Some local resolvers refuse SRV lookups (mongodb+srv) - use public DNS
      // for this server process so Atlas always resolves.
      const dns = await import('dns');
      try { dns.setServers(['8.8.8.8', '1.1.1.1']); } catch (e) { /* keep system DNS */ }
      const { MongoClient } = await import('mongodb');
      const client = new MongoClient(MONGO_URI, { serverSelectionTimeoutMS: 4000 });
      global.__mongoClientPromise = client.connect();
    }
    _clientPromise = global.__mongoClientPromise;
    const client = await _clientPromise;
    return client.db(MONGO_DB);
  } catch (e) {
    console.error('Mongo unavailable, falling back to JSON db:', e.message);
    return null;
  }
}

/* ------------------------------ JSON fallback ----------------------------- */
function loadJson() {
  try {
    return JSON.parse(fs.readFileSync(DB_PATH, 'utf-8'));
  } catch (e) {
    return {};
  }
}

function saveJson(db) {
  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2), 'utf-8');
}

function newId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

const strip = (doc) => {
  if (!doc) return doc;
  const { _id, ...rest } = doc;
  return rest;
};

/* --------------------------------- API ----------------------------------- */
export async function listRecords(entity) {
  const db = await mongo();
  if (db) {
    const rows = await db.collection(entity).find({}).limit(500).toArray();
    return rows.map(strip);
  }
  const j = loadJson();
  return Array.isArray(j[entity]) ? j[entity] : [];
}

export async function getRecord(entity, id) {
  const db = await mongo();
  if (db) return strip(await db.collection(entity).findOne({ id: String(id) }));
  return (await listRecords(entity)).find((r) => String(r?.id) === String(id)) || null;
}

export async function createRecord(entity, data) {
  const rec = { id: newId(), createdAt: new Date().toISOString(), ...data };
  const db = await mongo();
  if (db) {
    await db.collection(entity).insertOne({ ...rec });
    return rec;
  }
  const j = loadJson();
  if (!Array.isArray(j[entity])) j[entity] = [];
  j[entity].push(rec);
  saveJson(j);
  return rec;
}

export async function updateRecord(entity, id, data) {
  const db = await mongo();
  if (db) {
    const { id: _ignore, _id, ...patch } = data || {};
    const res = await db.collection(entity).findOneAndUpdate(
      { id: String(id) }, { $set: patch }, { returnDocument: 'after' }
    );
    return strip(res && (res.value || res));
  }
  const j = loadJson();
  const rows = Array.isArray(j[entity]) ? j[entity] : [];
  const i = rows.findIndex((r) => String(r?.id) === String(id));
  if (i === -1) return null;
  rows[i] = { ...rows[i], ...data, id: rows[i].id };
  j[entity] = rows;
  saveJson(j);
  return rows[i];
}

export async function deleteRecord(entity, id) {
  const db = await mongo();
  if (db) {
    const res = await db.collection(entity).deleteOne({ id: String(id) });
    return res.deletedCount > 0;
  }
  const j = loadJson();
  const rows = Array.isArray(j[entity]) ? j[entity] : [];
  const next = rows.filter((r) => String(r?.id) !== String(id));
  j[entity] = next;
  saveJson(j);
  return rows.length !== next.length;
}

export async function findUser(email, password) {
  const users = await listRecords('users');
  return users.find((u) => u?.email === email && (!password || u?.password === password)) || null;
}

export async function addUser(user) {
  return createRecord('users', user);
}
