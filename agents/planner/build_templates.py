"""Provides runtime defaults created before product code is written.

Product-specific files still come from the approved plan.
"""
from __future__ import annotations

import json
import re
import secrets
import textwrap


NEXT_DEPENDENCIES = {
    "next": "16.3.0",
    "react": "19.0.8",
    "react-dom": "19.0.8",
    "mongodb": "6.21.0",
    "lucide-react": "^0.441.0",
    "framer-motion": "^11.5.4",
    "better-auth": "1.6.26",
    "@better-auth/mongo-adapter": "1.6.26",
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
    "react-hot-toast": "^2.4.1",
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
    return Response.json({ ok: true, ran: false, reason: 'no seed export' })
  }
  try {
    await exported[name]()
    return Response.json({ ok: true, ran: true })
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




def _dependency_names(plan: dict) -> list[str]:
    names = []
    for item in plan.get("dependencies") or []:
        name = item.get("name") if isinstance(item, dict) else item
        name = str(name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _auth_required(plan: dict) -> bool:
    access = plan.get("roles_and_access") or {}
    return bool(access.get("authentication_required"))


def _signup_role(plan: dict) -> str:
    access = plan.get("roles_and_access") or {}
    return str(access.get("signup_role") or "user").strip() or "user"


def _auth_module(signup_role: str, origins: list[str], demo_accounts: list[dict]) -> str:
    accounts = [{
        "email": str(item.get("email") or "").strip(),
        "password": str(item.get("password") or ""),
        "name": str(item.get("name") or "Demo User").strip(),
        "role": str(item.get("role") or signup_role).strip() or signup_role,
    } for item in demo_accounts if isinstance(item, dict)
        and item.get("email") and item.get("password")]
    return textwrap.dedent(f"""\
        import {{ betterAuth }} from 'better-auth'
        import {{ mongodbAdapter }} from '@better-auth/mongo-adapter'
        import {{ nextCookies }} from 'better-auth/next-js'
        import {{ MongoClient }} from 'mongodb'

        const globalForAuth = globalThis

        function build() {{
          const client = new MongoClient(process.env.MONGODB_URI,
                                         {{ serverSelectionTimeoutMS: 8000 }})
          return {{ client, auth: betterAuth({{
            database: mongodbAdapter(client.db(process.env.MONGODB_DB)),
            emailAndPassword: {{ enabled: true }},
            user: {{
              additionalFields: {{
                role: {{ type: 'string', defaultValue: {json.dumps(signup_role)}, input: false }},
              }},
            }},
            secret: process.env.BETTER_AUTH_SECRET,
            baseURL: process.env.BETTER_AUTH_URL,
            trustedOrigins: {json.dumps(origins)},
            plugins: [nextCookies()],
          }}) }}
        }}

        let held = globalForAuth._authInstance ?? build()
        if (process.env.NODE_ENV !== 'production') globalForAuth._authInstance = held

        export let auth = held.auth

        // The driver closes a client whose first connection failed, so without
        // this every later request throws "Topology is closed" even once the
        // database is back. A dead instance is replaced instead.
        const UNUSABLE = /Topology is closed|MongoNotConnectedError|must be connected/i

        function renew() {{
          held.client.close().catch(() => {{}})
          held = build()
          if (process.env.NODE_ENV !== 'production') globalForAuth._authInstance = held
          globalForAuth._authDemoSeed = null
          auth = held.auth
          return held
        }}

        async function live(run) {{
          try {{
            return await run(held)
          }} catch (error) {{
            if (!UNUSABLE.test(String(error))) throw error
            return await run(renew())
          }}
        }}

        const demoAccounts = {json.dumps(accounts, ensure_ascii=False)}

        async function createDemoAccounts({{ client, auth }}) {{
          const db = client.db(process.env.MONGODB_DB)
          for (const account of demoAccounts) {{
            let user = await db.collection('user').findOne({{ email: account.email }})
            if (user) {{
              const credential = await db.collection('account').findOne({{
                userId: user._id.toString(), providerId: 'credential',
              }})
              // A plain orphan user blocks provider signup but can never sign in.
              if (!credential) {{
                await db.collection('user').deleteOne({{ _id: user._id }})
                user = null
              }}
            }}
            if (!user) {{
              await auth.api.signUpEmail({{
                body: {{ email: account.email, password: account.password, name: account.name }},
              }})
              user = await db.collection('user').findOne({{ email: account.email }})
            }}
            if (!user) throw new Error(`Better Auth did not create ${{account.email}}`)
            await db.collection('user').updateOne(
              {{ _id: user._id }}, {{ $set: {{ role: account.role, name: account.name }} }},
            )
          }}
        }}

        export function ensureDemoAccounts() {{
          if (!globalForAuth._authDemoSeed) {{
            globalForAuth._authDemoSeed = live(createDemoAccounts).catch((error) => {{
              globalForAuth._authDemoSeed = null
              throw error
            }})
          }}
          return globalForAuth._authDemoSeed
        }}

        export async function getSessionUser() {{
          const {{ headers }} = await import('next/headers')
          const list = await headers()
          const session = await live(({{ auth }}) => auth.api.getSession({{ headers: list }}))
          return session?.user ?? null
        }}
        """)


def _next_package(plan: dict) -> str:
    dependencies = dict(NEXT_DEPENDENCIES)
    for name in _dependency_names(plan):
        if name in KNOWN_DEPENDENCIES:
            dependencies[name] = KNOWN_DEPENDENCIES[name]
    project = plan.get("project") or {}
    data = {
        "name": project.get("name") or "agentforge-app",
        "private": True,
        "version": "0.1.0",
        "scripts": {
            "dev": "next dev --webpack",
            "build": "next build --webpack",
            "start": "next start",
        },
        "dependencies": dict(sorted(dependencies.items())),
        "devDependencies": dict(sorted(NEXT_DEV_DEPENDENCIES.items())),
    }
    return json.dumps(data, indent=2) + "\n"



def render_next_templates(plan: dict, *, mongo_uri: str, db_name: str,
                          dev_port: int, ui_port: int = 7824) -> dict[str, str]:
    project = plan.get("project") or {}
    title = str(project.get("title") or "AgentForge App")
    summary = str(project.get("summary") or title)
    slug = str(project.get("name") or "agentforge-app")
    database = db_name or "agentforge_" + re.sub(r"[^a-z0-9_]+", "_", slug.lower())
    uri = mongo_uri or f"mongodb://127.0.0.1:27017/{database}"
    files = {
        "package.json": _next_package(plan),
        "next.config.mjs": NEXT_CONFIG,
        "jsconfig.json": json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"]}}}, indent=2) + "\n",
        "tailwind.config.js": NEXT_TAILWIND,
        "postcss.config.js": "module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }\n",
        "app/globals.css": NEXT_GLOBALS,
        "app/layout.jsx": textwrap.dedent(f"""\
            import './globals.css'

            export const metadata = {{ title: {json.dumps(title)}, description: {json.dumps(summary)} }}

            export default function RootLayout({{ children }}) {{
              return (
                <html lang="en" suppressHydrationWarning>
                  <body suppressHydrationWarning>{{children}}</body>
                </html>
              )
            }}
            """),
        "app/page.jsx": "export default function Page() { return <main><p>Building…</p></main> }\n",
        "lib/mongodb.js": MONGODB_MODULE,
        "lib/seed.js": SEED_MODULE,
        "app/api/health/route.js": HEALTH_ROUTE,
        "app/api/seed/route.js": SEED_ROUTE,
        ".env.local": (
            f"MONGODB_URI={uri}\nMONGODB_DB={database}\n"
            f"BETTER_AUTH_SECRET={secrets.token_hex(32)}\n"
            f"BETTER_AUTH_URL=http://localhost:{dev_port}\nNEXT_TELEMETRY_DISABLED=1\n"
        ),
        ".gitignore": "node_modules/\n.next/\nout/\n.env*.local\n.agentforge/\n*.log\n",
    }
    if _auth_required(plan):
        origins = [
            "http://localhost:*", "http://127.0.0.1:*",
        ]
        files.update({
            "lib/auth.js": _auth_module(
                _signup_role(plan), origins,
                (plan.get("roles_and_access") or {}).get("demo_accounts") or [],
            ),
            "lib/auth-client.js": AUTH_CLIENT,
            "app/api/auth/[...all]/route.js": AUTH_ROUTE,
        })
    return files



def render_templates(stack: str, plan: dict, *, mongo_uri: str = "",
                     db_name: str = "", dev_port: int = 5173) -> dict[str, str]:
    return render_next_templates(plan, mongo_uri=mongo_uri, db_name=db_name,
                                 dev_port=dev_port)
