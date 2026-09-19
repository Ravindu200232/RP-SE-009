import mongoose from 'mongoose';

/**
 * One connection, cached across module re-evaluation.
 *
 * Next.js re-evaluates modules on every hot reload in development and across
 * route handlers in production. A plain module-level `let` therefore opens a
 * new connection each time until the pool is exhausted, and the symptom is
 * timeouts that look like slow queries. The cache lives on globalThis because
 * that is the one thing a reload does not reset.
 */
const cache = globalThis.__mongoose ?? (globalThis.__mongoose = { conn: null, promise: null });

export async function connectDb(uri = process.env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/sketch_next') {
  if (cache.conn) return cache.conn;
  cache.promise ??= mongoose.connect(uri, { bufferCommands: false });
  try {
    cache.conn = await cache.promise;
  } catch (error) {
    // A failed attempt must not be cached, or every later request replays it.
    cache.promise = null;
    throw error;
  }
  return cache.conn;
}

export async function disconnectDb() {
  if (mongoose.connection.readyState !== 0) await mongoose.disconnect();
  cache.conn = null;
  cache.promise = null;
}
