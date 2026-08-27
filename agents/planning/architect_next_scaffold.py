"""Next.js scaffold, generated context snapshot and file planning helpers."""
from agents.planning.architect_core import *
from agents.planning.architect_core import _fix_doubled_tags, _strip_fence, _safe_flush_len, _RefusalLoop
from agents.planning.architect_prompts import *


class ArchitectNextScaffoldMixin:
    def _scaffold_next(self):
        """
        Next.js 16 App Router + MongoDB.

        Versions are pinned exactly.

        **Next 16.3**, moved up from 15.5 so the model can read the framework's
        own documentation: 16.2+ ships the full docs inside the package at
        `node_modules/next/dist/docs/` (measured: 444 files, 3.9 MB, matched to
        the installed version), and `next dev` writes an `AGENTS.md` pointing
        at them. The trade is real — 16 hard-errors where 15 only warned, most
        notably on sync `params` access, which mid-size models still write —
        and the docs are the mitigation for exactly that.

        AgentForge runs 16 on **webpack**, not its new default Turbopack, because
        `Failed to compile` / `Module not found` / `Can't resolve` are the
        strings the build fix loop parses; all three were verified present with
        `--webpack` on 16.3.

        mongodb 6 because 7 requires Node >= 20.19 and the vendored Node is
        20.18.1 — 16.3 itself needs only >= 20.9.0, so no Node bump. Tailwind 3
        because v4's CSS-first config is not what models emit.
        """
        self._log("INFO", "🧱 Scaffolding Next.js + Tailwind + MongoDB")
        title = self.plan.get("title", "AgentForge App")
        slug = self.plan.get("project_name", "agentforge-app")
        db = self.db_name or f"agentforge_{re.sub(r'[^a-z0-9_]+', '_', slug.lower())}"

        deps = {"next": "16.3.0", "react": "19.0.8", "react-dom": "19.0.8",
                "mongodb": "6.21.0", "lucide-react": "^0.441.0",

                "better-auth": "1.6.26",
                "@better-auth/mongo-adapter": "1.6.26"}
        for d in self.plan.get("dependencies", []):
            key = d.strip().split("@")[0]
            if key in self.NEXT_EXTRA_DEPS and key not in self.BANNED_DEPS:
                deps[key] = self.NEXT_EXTRA_DEPS[key]
        deps.setdefault("framer-motion", self.NEXT_EXTRA_DEPS["framer-motion"])

        pkg = {
            "name": slug,
            "private": True,
            "version": "0.1.0",

            "scripts": dict(self.NEXT_PINNED["scripts"]),
            "dependencies": dict(sorted(deps.items())),
            "devDependencies": dict(self.NEXT_PINNED["devDependencies"]),
        }
        self._keep_installed_deps(pkg)
        self.write_file("package.json", json.dumps(pkg, indent=2))

        self.write_file("next.config.mjs", textwrap.dedent("""\
            /** @type {import('next').NextConfig} */
            const nextConfig = {
              // StrictMode double-invokes effects, which double-inserts seed rows.
              reactStrictMode: false,
              typescript: { ignoreBuildErrors: true },
              outputFileTracingRoot: process.cwd(),
              // Forward browser console warnings and errors to the dev server's
              // terminal, WITH their source location:
              //   [browser] ShoppingCart is not defined (app/checkout/page.js:164:11)
              // AgentForge captures that stream, so a client-side crash arrives with
              // a file and a line instead of a bare message. Added in 16.2.
              logging: { browserToTerminal: 'warn' },
              // Next 16 refuses dev requests whose origin it does not recognise,
              // and answers 403 for every file under /_next/static. The page
              // still returns 200, so it looks fine and runs no JavaScript —
              // which is indistinguishable, from the outside, from an app whose
              // buttons do nothing. Both the preview and the bug reproduction
              // reach this app on 127.0.0.1, so both must be named here.
              allowedDevOrigins: ['127.0.0.1', 'localhost'],
            }

            export default nextConfig
            """))

        self.write_file("jsconfig.json", json.dumps({
            "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"]}}
        }, indent=2))

        self.write_file("tailwind.config.js", textwrap.dedent("""\
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
            """))

        self.write_file("postcss.config.js", textwrap.dedent("""\
            module.exports = {
              plugins: { tailwindcss: {}, autoprefixer: {} },
            }
            """))

        self.write_file("app/globals.css", textwrap.dedent("""\
            @tailwind base;
            @tailwind components;
            @tailwind utilities;

            * { -webkit-font-smoothing: antialiased; }
            html, body { height: 100%; }
            body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; }
            ::-webkit-scrollbar { width: 10px; height: 10px; }
            ::-webkit-scrollbar-thumb { background: rgba(120,120,140,.35); border-radius: 8px; }
            ::-webkit-scrollbar-track { background: transparent; }
            """))

        self.write_file("app/layout.jsx", textwrap.dedent(f"""\
            import './globals.css'

            export const metadata = {{
              title: {json.dumps(title)},
              description: {json.dumps(self.plan.get('description', title))},
            }}

            export default function RootLayout({{ children }}) {{
              // suppressHydrationWarning is on <html> and <body> because
              // extensions — Grammarly (data-gr-ext-installed), QuillBot
              // (data-qb-installed), password managers — inject attributes
              // into exactly these two elements before React hydrates. That
              // produces a red "tree hydrated but some attributes … didn't
              // match" overlay on every page for anyone running one, and it
              // is not a fault in the app. The suppression is one level deep:
              // real mismatches inside the tree are still reported.
              return (
                <html lang="en" suppressHydrationWarning>
                  <body className="min-h-screen antialiased" suppressHydrationWarning>
                    {{children}}
                  </body>
                </html>
              )
            }}
            """))

        self.write_file("app/page.jsx", textwrap.dedent("""\
            export default function Page() {
              return (
                <main className="min-h-screen flex items-center justify-center">
                  <p className="text-lg text-gray-500">Building…</p>
                </main>
              )
            }
            """))

        # Snapshot only after the initial application shell exists.
        for _rel in self.NEXT_SCAFFOLD:
            if _rel in self.files:
                self._scaffold_baseline[_rel] = self.files[_rel]

        self.write_file("lib/mongodb.js", textwrap.dedent("""\
            import { MongoClient, ObjectId } from 'mongodb'

            const uri = process.env.MONGODB_URI
            const dbName = process.env.MONGODB_DB

            // Connected on FIRST USE, never when this file is imported.
            //
            // `new MongoClient(uri).connect()` at module scope opens a socket
            // the moment anything imports this module — and `next build`
            // imports every page and route during its "Collecting page data"
            // pass. That made a running database a requirement to COMPILE the
            // app, which is not a requirement it should have. It worked on a
            // machine with mongod running and failed in CI, where the build
            // died with `MongoServerSelectionError: connect ECONNREFUSED
            // 127.0.0.1:27017`, blaming whichever route the collection worker
            // happened to reach first.
            let clientPromise

            // Reuse across HMR reloads so dev doesn't leak a connection per edit.
            if (process.env.NODE_ENV === 'development' && global._mongoClientPromise) {
              clientPromise = global._mongoClientPromise
            }

            function connection() {
              if (!clientPromise) {
                if (!uri) throw new Error('MONGODB_URI is not set — check .env.local')
                clientPromise = new MongoClient(uri).connect()
                if (process.env.NODE_ENV === 'development') {
                  global._mongoClientPromise = clientPromise
                }
              }
              return clientPromise
            }

            /** Awaitable exactly like the promise this replaced — it just does
             *  not exist until something awaits it. */
            export default { then: (ok, no) => connection().then(ok, no) }

            export async function getDb() {
              const client = await connection()
              return client.db(dbName)
            }

            export async function getCollection(name) {
              const db = await getDb()
              return db.collection(name)
            }

            /** ObjectId -> string, Date -> ISO string, so it can cross to a
             *  Client Component without React complaining. */
            export function serialize(doc) {
              return doc == null ? doc : JSON.parse(JSON.stringify(doc))
            }

            export { ObjectId }
            """))

        self.write_file("app/api/health/route.js", textwrap.dedent("""\
            import { getDb } from '@/lib/mongodb'

            export const dynamic = 'force-dynamic'

            export async function GET() {
              try {
                const db = await getDb()
                await db.command({ ping: 1 })
                return Response.json({ ok: true, db: db.databaseName })
              } catch (e) {
                return Response.json({ ok: false, error: String(e) }, { status: 500 })
              }
            }
            """))

        uri = self.mongo_uri or f"mongodb://127.0.0.1:27017/{db}"
        self.write_file(".env.local", textwrap.dedent(f"""\
            MONGODB_URI={uri}
            MONGODB_DB={db}
            BETTER_AUTH_SECRET={secrets.token_hex(32)}
            BETTER_AUTH_URL=http://localhost:{self.dev_port}
            NEXT_TELEMETRY_DISABLED=1
            """))

        signup_role = self._signup_role()

        auth_src = textwrap.dedent("""\
            import { betterAuth } from 'better-auth'
            import { mongodbAdapter } from '@better-auth/mongo-adapter'
            import { nextCookies } from 'better-auth/next-js'
            import { MongoClient } from 'mongodb'

            const uri = process.env.MONGODB_URI
            const globalForAuth = globalThis
            const client =
              globalForAuth._authMongoClient ?? new MongoClient(uri)
            if (process.env.NODE_ENV !== 'production') {
              globalForAuth._authMongoClient = client
            }

            export const auth = betterAuth({
              // No `client` here — that would enable transactions, which need
              // a replica set. AgentForge's mongod is standalone.
              database: mongodbAdapter(client.db(process.env.MONGODB_DB)),
              emailAndPassword: { enabled: true },
              user: {
                additionalFields: {
                  role: { type: 'string', defaultValue: 'user', input: false },
                },
              },
              secret: process.env.BETTER_AUTH_SECRET,
              baseURL: process.env.BETTER_AUTH_URL,
              // Better Auth answers "Invalid origin" — visible on the form,
              // with no account created — for any Origin not matched here.
              // This app is reachable several ways: the dev server directly,
              // AgentForge's preview proxy on another port, each under both
              // `localhost` and `127.0.0.1` (different origins to a browser;
              // Electron uses one and a normal tab the other), and the port
              // moves when one is busy.
              //
              // Enumerating them is how this broke the first time, so match on
              // the pattern instead — `*` is supported and only widens to
              // loopback. A remote origin is still refused with 403, verified.
              trustedOrigins: {TRUSTED_ORIGINS},
              // Must be last: it is what lets a Server Action or route handler
              // set the session cookie on the response.
              plugins: [nextCookies()],
            })

            /** The signed-in user, or null. Safe in any server file. */
            export async function getSessionUser() {
              const { headers } = await import('next/headers')
              const session = await auth.api.getSession({ headers: await headers() })
              return session?.user ?? null
            }
            """).replace("{TRUSTED_ORIGINS}", self.TRUSTED_ORIGINS)
        auth_src = auth_src.replace("defaultValue: 'user'",
                                    f"defaultValue: {json.dumps(signup_role)}")
        self._log("INFO", f"   🔐 signing up creates a `{signup_role}` — "
                          f"never an administrator, whatever order the plan "
                          f"lists its accounts in")

        if self._needs_auth():
            self.write_own("lib/auth.js", auth_src)

            self.write_own("app/api/auth/[...all]/route.js", textwrap.dedent("""\
                import { toNextJsHandler } from 'better-auth/next-js'

                // Serves every auth endpoint: /api/auth/sign-in/email,
                // /api/auth/sign-up/email, /api/auth/sign-out,
                // /api/auth/get-session.

                // Never at module scope: importing `@/lib/auth` builds the
                // Better Auth instance, which connects to MongoDB, and
                // `next build` imports this file while collecting page data.
                // Built once and reused, on the first request.
                let handlers
                async function ready() {
                  if (!handlers) {
                    const { auth } = await import('@/lib/auth')
                    handlers = toNextJsHandler(auth.handler)
                  }
                  return handlers
                }

                export const dynamic = 'force-dynamic'

                export async function GET(request) {
                  return (await ready()).GET(request)
                }

                export async function POST(request) {
                  return (await ready()).POST(request)
                }
                """))

            self.write_own("lib/auth-client.js", textwrap.dedent("""\
                'use client'
                import { createAuthClient } from 'better-auth/react'

                export const authClient = createAuthClient()
                export const { signIn, signUp, signOut, useSession } = authClient
                """))
        else:
            self._log("INFO", "   🔓 Nothing in the brief signs in — building "
                              "without authentication")

        self.write_file(".gitignore", textwrap.dedent("""\
            node_modules/
            .next/
            out/
            .env*.local
            .agentforge/
            *.log
            """))

        self.write_agent_files()

    def _context_snapshot(self, max_files: int = 14, per_file: int = 1400,
                          wanted: list = None) -> str:
        """Existing source, trimmed — so later files can import correctly.

        `wanted` is the files about to be written. Ranking by what they will
        need beats ranking alphabetically, which is what this did: with a
        fourteen-file cap, `components/AdminTable.jsx` was included over
        `components/StockAdjustmentForm.jsx` because of the letter A, whatever
        the next task happened to be about.

        Two things earn a place near the top: living in the same folder as
        something about to be written, and already being imported by one of
        them. The three fixed entries stay first — the database helper and the
        layout are the shape everything else is written against.
        """
        src = [(p, c) for p, c in self.files.items() if self.is_source(p)]
        if not src:
            return "(no source files yet)"
        priority = ({"src/App.jsx": 0} if self.stack == "vite"
                    else {"lib/mongodb.js": 0, "app/layout.jsx": 1, "app/page.jsx": 2})

        # Start with files connected by an explicit cross-task contract.
        near = set(self._related_context_files(wanted or []))
        for target in (wanted or []):
            path = target if isinstance(target, str) else (target or {}).get("path", "")
            if not path:
                continue
            folder = path.rsplit("/", 1)[0] if "/" in path else ""
            for other, _ in src:
                if folder and other.startswith(folder + "/"):
                    near.add(other)
            body = self.files.get(path, "")
            specs = (self.ALIAS_IMPORT_RE.findall(body)
                     + self.LOCAL_IMPORT_RE.findall(body))
            for spec in specs:
                spec = spec.lstrip("./")
                for cand in (spec, f"{spec}.js", f"{spec}.jsx",
                             f"{spec}/index.js", f"{spec}/index.jsx"):
                    if cand in self.files:
                        near.add(cand)

        src.sort(key=lambda x: (priority.get(x[0], 99),
                                0 if x[0] in near else 1,
                                x[0]))
        out = []
        for path, content in src[:max_files]:
            body = content if len(content) <= per_file else \
                content[:per_file] + "\n// …truncated…\n"
            out.append(f"--- {path} ---\n{body}")
        return "\n\n".join(out)
