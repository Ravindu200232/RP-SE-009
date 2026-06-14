// Seed MongoDB from data/db.json (run by the generator: `node scripts/seed.mjs`).
// Reads MONGODB_URI / MONGODB_DB from .env.local; no-op when Mongo isn't configured.
import fs from 'fs';
import path from 'path';

function loadEnvLocal() {
  const p = path.join(process.cwd(), '.env.local');
  if (!fs.existsSync(p)) return;
  for (const line of fs.readFileSync(p, 'utf-8').split(/\r?\n/)) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
  }
}
loadEnvLocal();

const uri = process.env.MONGODB_URI;
const dbName = process.env.MONGODB_DB || 'app';
if (!uri) {
  console.log('SEED: no MONGODB_URI - JSON fallback mode, nothing to do.');
  process.exit(0);
}

const data = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'data', 'db.json'), 'utf-8'));

const dns = await import('dns');
try { dns.setServers(['8.8.8.8', '1.1.1.1']); } catch (e) { /* keep system DNS */ }
const { MongoClient } = await import('mongodb');
const client = new MongoClient(uri, { serverSelectionTimeoutMS: 8000 });
try {
  await client.connect();
  const db = client.db(dbName);
  let total = 0;
  for (const [coll, rows] of Object.entries(data)) {
    if (!Array.isArray(rows) || rows.length === 0) continue;
    await db.collection(coll).deleteMany({});
    await db.collection(coll).insertMany(rows.map((r) => ({ ...r })));
    total += rows.length;
  }
  console.log(`SEED: ok - ${total} records across ${Object.keys(data).length} collections into '${dbName}'.`);
} catch (e) {
  console.error('SEED: failed -', e.message, '(app will use the JSON fallback)');
} finally {
  await client.close().catch(() => {});
}
