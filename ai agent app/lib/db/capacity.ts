import dns from 'dns';
import mongoose from 'mongoose';
import { connectDB } from './mongoose';

const SYSTEM_DATABASES = new Set(['admin', 'local', 'config']);
const PUBLIC_DNS_SERVERS = ['8.8.8.8', '1.1.1.1'];

export interface MongoDatabaseUsage {
  name: string;
  collections: number;
}

export interface MongoCollectionUsage {
  totalCollections: number;
  databases: MongoDatabaseUsage[];
  limit: number;
  reserve: number;
  remaining: number;
}

function numberEnv(name: string, fallback: number): number {
  const n = Number(process.env[name]);
  return Number.isFinite(n) ? n : fallback;
}

function shouldRetryWithPublicDns(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /querySrv|ENOTFOUND|ETIMEOUT|ECONNREFUSED/i.test(msg);
}

function configuredDnsServers(): string[] {
  const value = process.env.DNS_SERVERS?.trim();
  if (!value || value.toLowerCase() === 'auto' || value.toLowerCase() === 'off') return [];
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

async function createConnectionWithDnsFallback(uri: string): Promise<mongoose.Connection> {
  const explicitServers = configuredDnsServers();
  if (explicitServers.length) {
    try {
      dns.setServers(explicitServers);
    } catch {
      /* keep system resolver */
    }
  }

  try {
    return await mongoose
      .createConnection(uri, {
        bufferCommands: false,
        serverSelectionTimeoutMS: 10000,
      })
      .asPromise();
  } catch (err) {
    const dnsMode = process.env.DNS_SERVERS?.trim().toLowerCase();
    if (explicitServers.length || dnsMode === 'off') throw err;
    if (!shouldRetryWithPublicDns(err)) throw err;
    try {
      dns.setServers(PUBLIC_DNS_SERVERS);
    } catch {
      throw err;
    }
    return mongoose
      .createConnection(uri, {
        bufferCommands: false,
        serverSelectionTimeoutMS: 10000,
      })
      .asPromise();
  }
}

export async function dropDatabaseByUri(uri: string): Promise<void> {
  const conn = await createConnectionWithDnsFallback(uri);
  try {
    await conn.dropDatabase();
  } finally {
    await conn.close().catch(() => {});
  }
}

export async function getMongoCollectionUsage(): Promise<MongoCollectionUsage> {
  const limit = numberEnv('MONGODB_COLLECTION_LIMIT', 500);
  const reserve = numberEnv('MONGODB_COLLECTION_RESERVE', 40);

  const m = await connectDB();
  if (!m.connection.db) {
    throw new Error('MongoDB connection is not ready');
  }

  const client = m.connection.getClient();
  const listed = await m.connection.db.admin().listDatabases();
  const databases: MongoDatabaseUsage[] = [];

  for (const db of listed.databases ?? []) {
    const name = db.name;
    if (!name || SYSTEM_DATABASES.has(name)) continue;
    const collections = await client
      .db(name)
      .listCollections({}, { nameOnly: true })
      .toArray();
    databases.push({ name, collections: collections.length });
  }

  databases.sort((a, b) => b.collections - a.collections || a.name.localeCompare(b.name));
  const totalCollections = databases.reduce((sum, db) => sum + db.collections, 0);
  return {
    totalCollections,
    databases,
    limit,
    reserve,
    remaining: Math.max(0, limit - totalCollections),
  };
}

export async function assertMongoCollectionCapacity(): Promise<MongoCollectionUsage> {
  const usage = await getMongoCollectionUsage();
  if (usage.limit <= 0) return usage;
  const safeThreshold = Math.max(0, usage.limit - usage.reserve);
  if (usage.totalCollections >= safeThreshold) {
    const top = usage.databases
      .slice(0, 8)
      .map((db) => `${db.name} (${db.collections})`)
      .join(', ');
    throw new Error(
      `MongoDB collection capacity is too low for a new backend app: ${usage.totalCollections}/${usage.limit} collections in use, reserve ${usage.reserve}. Delete old generated projects/databases first. Largest databases: ${top || 'none'}.`,
    );
  }
  return usage;
}
