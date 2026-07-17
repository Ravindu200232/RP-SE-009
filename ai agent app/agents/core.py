"""agents/core.py — the FIXED permanent core of every generated app (v2 engine).

Everything here is identical across apps and written verbatim (NO LLM): the create-next-app
base, the DB connection + API helpers, the full auth stack, and the pinned shadcn primitive
registry. The rule-based generation agents produce everything else (models, routes, pages,
sections, components, business logic).

This is the ONLY deterministic file emission in the v2 engine — the "permanent files for very
common things" the user approved. See agents/rules/*.md for the rules the agents follow.
"""
from __future__ import annotations

from agents import scaffold
from agents.component_registry import registry_files


def core_files(spec: dict) -> dict:
    """Return the fixed permanent files for a multipage-app spec."""
    files: dict[str, str] = {}

    # 1. create-next-app base: package.json, next.config, tsconfig, tailwind, globals, root layout
    files.update(scaffold.base_files(spec))

    # 2. fixed DB connection + response helpers
    files["lib/mongodb.ts"] = scaffold._DB_LIB
    files["lib/api.ts"] = scaffold._API_LIB

    # 2b. deterministic summary endpoint every dashboard fetches (`/api/reports?type=summary`).
    #     Always present so a dashboard's KPI fetch never 404s → never returns HTML → never crashes
    #     `res.json()`. Compiled from the data model, so counts always match real collections.
    _reports = scaffold.reports_route(spec)
    if _reports:
        files["app/api/reports/route.ts"] = _reports

    # 3. fixed shadcn primitive registry (components/ui/*, lib/utils.ts, components.json)
    files.update(registry_files(spec))

    # 4. fixed full auth stack (User model, lib/session, lib/auth, lib/seed, auth API routes,
    #    edge middleware, login/signup, dashboard shell + sidebar, admin manage-users, .env.local).
    #    Emitted through the GUARDED wrapper — `scaffold.auth_files` returns {} when the app doesn't
    #    need auth (`scaffold.auth_enabled(spec)` is false), so a simple utility app never gets a login
    #    stack / seeded users leaked into it. A multi-role app (DineFlow) still gets the full stack.
    files.update(scaffold.auth_files(spec))

    return files
