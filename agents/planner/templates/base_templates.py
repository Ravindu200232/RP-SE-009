"""Static source templates used to bootstrap generated Next.js applications."""

NEXT_DEPENDENCIES = {
    "next": "16.3.0",
    "react": "19.0.8",
    "react-dom": "19.0.8",
    "mongodb": "6.21.0",
    "lucide-react": "^0.441.0",
    "framer-motion": "^11.5.4",
    "better-auth": "1.6.26",
    "@better-auth/mongo-adapter": "1.6.26",
    "react-hot-toast": "^2.4.1",
}

NEXT_DEV_DEPENDENCIES = {
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "3.4.19",
    "vitest": "^3.0.0",
    "jsdom": "^25.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/user-event": "^14.0.0",
}



KNOWN_DEPENDENCIES = {
    "bcryptjs": "^3.0.3",
    "react-icons": "^5.3.0",
    "recharts": "^2.12.7",
    "date-fns": "^3.6.0",
    "dayjs": "^1.11.13",
    "clsx": "^2.1.1",
    "uuid": "^10.0.0",
    "nanoid": "^5.0.7",
    "slugify": "^1.6.6",
    "zod": "^3.23.8",
    "swr": "^2.2.5",
    "react-hook-form": "^7.53.0",
    "zustand": "^4.5.5",
}

NEXT_CONFIG = """\
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  typescript: { ignoreBuildErrors: true },
  outputFileTracingRoot: process.cwd(),
  logging: { browserToTerminal: 'warn' },
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
}

export default nextConfig
"""

NEXT_TAILWIND = """\
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
    './lib/**/*.{js,jsx}',
  ],
  theme: { extend: {} },
  plugins: [],
}
"""

NEXT_GLOBALS = """\
@tailwind base;
@tailwind components;
@tailwind utilities;

* { -webkit-font-smoothing: antialiased; }
html, body { min-height: 100%; }
body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: rgba(120, 120, 140, .35); border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }
"""

MONGODB_MODULE = """\
import { MongoClient, ObjectId } from 'mongodb'

const uri = process.env.MONGODB_URI
const dbName = process.env.MONGODB_DB
let clientPromise

if (process.env.NODE_ENV === 'development' && global._mongoClientPromise) {
  clientPromise = global._mongoClientPromise
}

function cache(value) {
  clientPromise = value
  if (process.env.NODE_ENV === 'development') global._mongoClientPromise = value
}

function connection() {
  if (!clientPromise) {
    if (!uri) throw new Error('MONGODB_URI is not set')
    const client = new MongoClient(uri, { serverSelectionTimeoutMS: 5000 })
    // A client whose first connection failed keeps a closed topology, so the
    // dead one is dropped and the next call connects to a live server.
    cache(client.connect().catch((error) => {
      cache(undefined)
      client.close().catch(() => {})
      throw error
    }))
  }
  return clientPromise
}

export default { then: (resolve, reject) => connection().then(resolve, reject) }

export async function getDb() {
  const client = await connection()
  return client.db(dbName)
}

export async function getCollection(name) {
  return (await getDb()).collection(name)
}

export function serialize(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

export { ObjectId }
"""

HEALTH_ROUTE = """\
import { getDb } from '@/lib/mongodb'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const db = await getDb()
    await db.command({ ping: 1 })
    return Response.json({ ok: true, db: db.databaseName })
  } catch (error) {
    return Response.json({ ok: false, error: String(error) }, { status: 500 })
  }
}
"""

SEED_MODULE = """\
// Replaced by the planned seed. The no-op keeps `@/lib/seed` importable so the
// seed endpoint always resolves, even for an app that stores nothing.
export async function ensureSeeded() {
  return { seeded: false }
}
"""

SEED_ROUTE = """\
import * as seedModule from '@/lib/seed'
import { getDb } from '@/lib/mongodb'
__AUTH_IMPORT__

const REQUIRED_SEEDS = __REQUIRED_SEEDS__
const DEMO_ACCOUNTS = __DEMO_ACCOUNTS__

export const dynamic = 'force-dynamic'

// The planned seed owns its export name, so this route accepts any of them.
// The lookup is deliberately by computed key. Reading the names straight off
// the namespace makes webpack emit "Attempted import error" for every name the
// planned seed does not happen to export, and this route is scaffold-owned, so
// no repair pass is allowed to rewrite the warning away.
const SEED_EXPORTS = ['ensureSeeded', 'seedDatabase', 'seed', 'default']

// AgentForge calls this once the app is serving, so the planned rows exist even
// when no page happened to run the seed itself.
export async function GET() {
  const exported = { ...seedModule }
  const name = SEED_EXPORTS.find((key) => typeof exported[key] === 'function')
  if (!name) {
    const ok = REQUIRED_SEEDS.length === 0
    return Response.json({ ok, ran: false, reason: 'no seed export' }, { status: ok ? 200 : 500 })
  }
  try {
__AUTH_ENSURE__    await exported[name]()
    const db = await getDb()
    for (const row of REQUIRED_SEEDS) {
      const count = await db.collection(row.collection).countDocuments({})
      if (count < row.count) throw new Error(`Seed incomplete: ${row.collection} has ${count}/${row.count} rows`)
    }
    for (const account of DEMO_ACCOUNTS) {
      const user = await db.collection('user').findOne({ email: account.email })
      const credential = user && await db.collection('account').findOne({ userId: { $in: [user._id, user._id.toString()] }, providerId: 'credential' })
      if (!user || !credential || String(user.role || '') !== String(account.role || ''))
        throw new Error(`Demo account not persisted with role: ${account.email}`)
    }
    return Response.json({ ok: true, ran: true, accounts: DEMO_ACCOUNTS.length, collections: REQUIRED_SEEDS.length })
  } catch (error) {
    return Response.json({ ok: false, error: String(error) }, { status: 500 })
  }
}
"""

AUTH_CLIENT = """\
'use client'
import { createAuthClient } from 'better-auth/react'

export const authClient = createAuthClient()
export const { signIn, signUp, signOut, useSession } = authClient
"""

AUTH_ROUTE = """\
import { toNextJsHandler } from 'better-auth/next-js'

async function ready() {
  const { auth, ensureDemoAccounts } = await import('@/lib/auth')
  // Seeding retries on the next request; a database that is not up yet must
  // not take every auth endpoint down with it.
  await ensureDemoAccounts().catch(() => {})
  return toNextJsHandler(auth.handler)
}

export const dynamic = 'force-dynamic'
export async function GET(request) { return (await ready()).GET(request) }
export async function POST(request) { return (await ready()).POST(request) }
"""
