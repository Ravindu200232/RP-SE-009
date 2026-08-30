"""Provides runtime defaults created before product code is written.

Product-specific files still come from the approved plan.
"""
from __future__ import annotations

import json
import re
import secrets
import textwrap

# Source: base_templates.py — imported helper(s) come from this file.
from agents.planner.templates.base_templates import (
    AUTH_CLIENT, AUTH_ROUTE, HEALTH_ROUTE, KNOWN_DEPENDENCIES, MONGODB_MODULE,
    NEXT_CONFIG, NEXT_DEPENDENCIES, NEXT_DEV_DEPENDENCIES, NEXT_GLOBALS,
    NEXT_TAILWIND, SEED_MODULE, SEED_ROUTE,
)
# Source: auth_template.py — imported helper(s) come from this file.
from agents.planner.templates.auth_template import _auth_module, _signup_role


# Returns the dependency names declared in the generated package.json.
def _dependency_names(plan: dict) -> list[str]:
    """Return the dependency names declared in the generated package.json."""
    names = []
    for item in plan.get("dependencies") or []:
        name = item.get("name") if isinstance(item, dict) else item
        name = str(name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


# Checks whether the approved plan requires authentication.
def _auth_required(plan: dict) -> bool:
    """Return whether the approved plan requires authentication."""
    access = plan.get("roles_and_access") or {}
    return bool(access.get("authentication_required"))



# Builds the stable /api/seed route source used by generated applications.
def _seed_route(plan: dict) -> str:
    """Build the stable /api/seed route source used by generated applications."""
    required, auth = [], _auth_required(plan)
    for model in plan.get('data_model') or []:
        seed = model.get('seed') or {}; digits = re.sub(r'[^0-9]', '', str(seed.get('count') or ''))
        count = int(digits) if digits else 0
        name = str(model.get('collection') or '').strip()
        auth_owned = {'user', 'users', 'account', 'accounts', 'session', 'sessions', 'verification', 'verifications'}
        if name and count > 0 and (not auth or name.lower() not in auth_owned):
            required.append({'collection': name, 'count': count})
    accounts = [{'email': a.get('email'), 'role': a.get('role')} for a in
                (plan.get('roles_and_access') or {}).get('demo_accounts') or []]
    # From: agents/planner/templates/base_templates.py
    return (SEED_ROUTE
            .replace('__REQUIRED_SEEDS__', json.dumps(required, ensure_ascii=False))
            .replace('__DEMO_ACCOUNTS__', json.dumps(accounts if auth else [], ensure_ascii=False))
            .replace('__AUTH_IMPORT__', "import { ensureDemoAccounts } from '@/lib/auth'" if auth else '')
            .replace('__AUTH_ENSURE__', '    await ensureDemoAccounts()\n' if auth else ''))

# Builds the baseline package.json used by a new Next.js application.
def _next_package(plan: dict) -> str:
    """Build the baseline package.json used by a new Next.js application."""
    dependencies = dict(NEXT_DEPENDENCIES)
    for name in _dependency_names(plan):
        if name in KNOWN_DEPENDENCIES:
            dependencies[name] = KNOWN_DEPENDENCIES[name]
    project = plan.get("project") or {}
    # From: agents/planner/templates/base_templates.py
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



# Builds next templates in the format expected by the next pipeline steps.
def render_next_templates(plan: dict, *, mongo_uri: str, db_name: str,
                          dev_port: int, ui_port: int = 7824) -> dict[str, str]:
    """Build next templates in the standard shape used by the rest of the pipeline."""
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
        "components/ToastHost.jsx": "'use client'\nimport { Toaster } from 'react-hot-toast'\nexport default function ToastHost() { return <Toaster position=\"top-right\" toastOptions={{ duration: 3500 }} /> }\n",
        "app/layout.jsx": textwrap.dedent(f"""\
            import './globals.css'
            import ToastHost from '@/components/ToastHost'

            export const metadata = {{ title: {json.dumps(title)}, description: {json.dumps(summary)} }}

            export default function RootLayout({{ children }}) {{
              return (
                <html lang="en" suppressHydrationWarning>
                  <body suppressHydrationWarning><ToastHost />{{children}}</body>
                </html>
              )
            }}
            """),
        "app/page.jsx": "export default function Page() { return <main><p>Building…</p></main> }\n",
        "lib/mongodb.js": MONGODB_MODULE,
        "lib/seed.js": SEED_MODULE,
        "app/api/health/route.js": HEALTH_ROUTE,
        "app/api/seed/route.js": _seed_route(plan),
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
        # From: agents/planner/builder/project_memory.py
        # From: agents/planner/templates/auth_template.py
        files.update({
            "lib/auth.js": _auth_module(
                _signup_role(plan), origins,
                (plan.get("roles_and_access") or {}).get("demo_accounts") or [],
            ),
            "lib/auth-client.js": AUTH_CLIENT,
            "app/api/auth/[...all]/route.js": AUTH_ROUTE,
        })
    return files



# Builds templates in the format expected by the next pipeline steps.
def render_templates(stack: str, plan: dict, *, mongo_uri: str = "",
                     db_name: str = "", dev_port: int = 5173) -> dict[str, str]:
    """Build templates in the standard shape used by the rest of the pipeline."""
    return render_next_templates(plan, mongo_uri=mongo_uri, db_name=db_name,
                                 dev_port=dev_port)
