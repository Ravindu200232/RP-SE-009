import mongoose from 'mongoose';
import dns from 'dns';

/**
 * Cached MongoDB connection helper.
 *
 * Atlas mongodb+srv needs DNS SRV lookups. Some Windows/Ollama dev machines
 * resolve through the system resolver correctly, while direct public DNS can be
 * blocked; others need public DNS. So we try the system resolver first, then
 * retry once with public DNS only for DNS-like failures. Set DNS_SERVERS to a
 * comma-separated list to force specific servers, or "off" to disable fallback.
 */

const MONGODB_URI = process.env.MONGODB_URI;
const PUBLIC_DNS_SERVERS = ['8.8.8.8', '1.1.1.1'];

interface MongooseCache {
  conn: typeof mongoose | null;
  promise: Promise<typeof mongoose> | null;
}

declare global {
  // eslint-disable-next-line no-var
  var _mongoose: MongooseCache | undefined;
}

const cached: MongooseCache = global._mongoose ?? { conn: null, promise: null };
global._mongoose = cached;

function configuredDnsServers(): string[] {
  const value = process.env.DNS_SERVERS?.trim();
  if (!value || value.toLowerCase() === 'auto') return [];
  if (value.toLowerCase() === 'off') return [];
  return value.split(',').map((s) => s.trim()).filter(Boolean);
}

async function connectOnce(): Promise<typeof mongoose> {
  return mongoose
    .connect(MONGODB_URI as string, {
      bufferCommands: false,
      serverSelectionTimeoutMS: 8000,
    })
    .then((m) => m);
}

function shouldRetryWithPublicDns(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /querySrv|ENOTFOUND|ETIMEOUT|ECONNREFUSED/i.test(msg);
}

export async function connectDB(): Promise<typeof mongoose> {
  if (!MONGODB_URI) {
    throw new Error('MONGODB_URI is not set. Add it to .env.local');
  }

  if (cached.conn) {
    return cached.conn;
  }

  if (!cached.promise) {
    cached.promise = (async () => {
      const explicitServers = configuredDnsServers();
      if (explicitServers.length) {
        try {
          dns.setServers(explicitServers);
        } catch {
          /* use the system resolver */
        }
      }

      try {
        return await connectOnce();
      } catch (err) {
        if (explicitServers.length || !shouldRetryWithPublicDns(err)) throw err;
        try {
          dns.setServers(PUBLIC_DNS_SERVERS);
        } catch {
          throw err;
        }
        return connectOnce();
      }
    })();
  }

  try {
    cached.conn = await cached.promise;
  } catch (err) {
    cached.promise = null;
    throw err;
  }

  return cached.conn;
}
