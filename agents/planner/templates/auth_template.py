"""Build the Better Auth source module from the approved role plan."""
import json
import textwrap

# Returns the public-registration role allowed by the approved access plan.
def _signup_role(plan: dict) -> str:
    """Return the public-registration role allowed by the approved access plan."""
    access = plan.get("roles_and_access") or {}
    return str(access.get("signup_role") or "user").strip() or "user"


# Builds the stable Better Auth helper used by generated applications.
def _auth_module(signup_role: str, origins: list[str], demo_accounts: list[dict]) -> str:
    """Build the stable Better Auth helper used by generated applications."""
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
              const ids = [user._id, user._id.toString()]
              const credential = await db.collection('account').findOne({{ userId: {{ $in: ids }}, providerId: 'credential' }})
              let valid = Boolean(credential)
              if (valid) try {{ await auth.api.signInEmail({{ body: {{ email: account.email, password: account.password }} }}) }} catch {{ valid = false }}
              // Seed owns demo credentials: repair stale/orphan identities through Better Auth.
              if (!valid) {{
                await db.collection('session').deleteMany({{ userId: {{ $in: ids }} }})
                await db.collection('account').deleteMany({{ userId: {{ $in: ids }} }})
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
            globalForAuth._authDemoSeed = live(createDemoAccounts).finally(() => {{ globalForAuth._authDemoSeed = null }})
          }}
          return globalForAuth._authDemoSeed
        }}

        export async function provisionUser({{ email, password, name, role }}) {{
          return live(async ({{ client, auth }}) => {{
            const db = client.db(process.env.MONGODB_DB)
            if (await db.collection('user').findOne({{ email }})) throw new Error('Email already registered')
            await auth.api.signUpEmail({{ body: {{ email, password, name }} }})
            const user = await db.collection('user').findOne({{ email }})
            if (!user) throw new Error(`Better Auth did not create ${{email}}`)
            await db.collection('user').updateOne({{ _id: user._id }}, {{ $set: {{ role, name }} }})
            return {{ id: user._id.toString(), email, name, role }}
          }})
        }}

        export async function getSessionUser() {{
          const {{ headers }} = await import('next/headers')
          const list = await headers()
          const session = await live(({{ auth }}) => auth.api.getSession({{ headers: list }}))
          return session?.user ?? null
        }}
        """)
