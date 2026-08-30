"""Turns a user's request into one complete, normalized product plan."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape, quoteattr

# Source: llm_client.py — imported helper(s) come from this file.
from agents.core.llm.llm_client import OllamaClient, max_context
# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import feature_image_requested

log = logging.getLogger("planner")
PROMPT_PATH = Path(__file__).with_name("planning_prompt.txt")

NEXT_STACK = """\
FIXED IMPLEMENTATION STACK
- Next.js 16 App Router, React 19, JavaScript only; no TypeScript.
- Tailwind utilities for styling; lucide-react icons; framer-motion only when motion helps.
- MongoDB official driver through the generated @/lib/mongodb module.
- Files live under app/, components/, and lib/. Pages use .jsx, route/lib modules use .js.
- Filesystem routing; no react-router-dom, Pages Router, Mongoose, Prisma, or external APIs.
- Better Auth is generated only when the product genuinely needs authentication.
- AgentForge already owns package/config/Mongo/auth defaults. Never put those in file_plan/tasks.
- Every product page, component, seed module, API route, loading/error/empty behavior, and E2E journey must be planned.
"""

# One account flow can be planned under any of these names. The planner must
# not append a second page for a flow the plan already serves, or the app ships
# duplicate half-built auth screens that compete for the same navigation.
SIGN_IN_PATHS = frozenset({"/sign-in", "/signin", "/login"})
SIGN_UP_PATHS = frozenset({"/sign-up", "/signup", "/register"})

# Better Auth owns these collections and reaches them through its own catch-all
# route, so no planned route reads or writes them. Asking the planner to "connect
# it to the user flow or remove it" is a gap it cannot close either way: removing
# the collection loses the identity model, and inventing a route for it competes
# with the auth provider. The round then repeats until the budget is spent.
AUTH_OWNED_COLLECTIONS = frozenset({"user", "account", "session", "verification"})

# How many times the planner is asked to close its own gaps before the build
# proceeds with what it has.
GAP_ROUNDS = 3

_PLAN_VOLUME_KEYS = ("requirements", "routes", "file_plan", "site_map",
                     "capabilities", "tasks")

# Plan volume in the format expected by the next pipeline steps.
def _plan_volume(plan: dict) -> dict:
    """Plan volume in the standard shape used by the rest of the pipeline."""
    return {key: len(_list(plan.get(key))) for key in _PLAN_VOLUME_KEYS}

_ROUTES_HEADING_RE = re.compile(r"^#+\s*Required Routes\s*$", re.M)
_ROUTE_LINE_RE = re.compile(r"^\s*[*-]\s*`(/[^`]*)`\s*$", re.M)


# The routes the approved SRS lists under Required Routes. The specification says which pages the customer signed
# off on, and the planner reads it as prose. On a large brief it quietly drops a few — three of twenty-seven on
# the first sports store — and nothing downstream notices, because a route that was never planned leaves no hole
# to find. Reading the list back out of the brief is what turns a silent omission into a gap the planner is asked
# to close.
def _promised_routes(requirements: str) -> list[str]:
    """The routes the approved SRS lists under Required Routes.

    The specification says which pages the customer signed off on, and the
    planner reads it as prose. On a large brief it quietly drops a few — three
    of twenty-seven on the first sports store — and nothing downstream notices,
    because a route that was never planned leaves no hole to find. Reading the
    list back out of the brief is what turns a silent omission into a gap the
    planner is asked to close.
    """
    # Not _text(): it collapses newlines, and every anchor below is a line one.
    text = str(requirements or "")
    match = _ROUTES_HEADING_RE.search(text)
    if not match:
        return []
    tail = text[match.end():]
    end = re.search(r"^#+\s+\S", tail, re.M)
    # From: agents/data/database_server.py
    return [route for route in _ROUTE_LINE_RE.findall(tail[:end.start()] if end else tail)]


# Every promised route the plan does not serve.
def _unplanned_routes(plan: dict, promised: list[str]) -> list[str]:
    """Every promised route the plan does not serve."""
    if not promised:
        return []
    served = {_url_shape(item.get("path")) for item in plan.get("routes") or []}
    served |= {_url_shape(item.get("path")) for item in plan.get("site_map") or []}
    missing = [route for route in promised if _url_shape(route) not in served]
    return [f"the approved specification requires {route}, but no route or "
            f"site_map entry serves it. Add the page, its file and its journey."
            for route in missing]


# True when a replanned answer carries less of the product than we hold.
def _plan_is_poorer(candidate: dict, current: dict) -> bool:
    """True when a replanned answer carries less of the product than we hold."""
    new, old = _plan_volume(candidate), _plan_volume(current)
    return any(new[key] < old[key] for key in _PLAN_VOLUME_KEYS)

# A plan with nothing to build is a failed plan, not a small product.
def _plan_is_empty(plan: dict) -> bool:
    """A plan with nothing to build is a failed plan, not a small product."""
    volume = _plan_volume(plan)
    return not (volume["routes"] or volume["file_plan"])

@dataclass
class PlanBundle:
    data: dict
    markdown: str
    architecture_markdown: str
    design_markdown: str
    raw: str
    sitemap_xml: str = ""

# Converts a flexible model value into one clean text value.
def _text(value: Any, limit: int = 0) -> str:
    """Convert a flexible model value into one clean text value."""
    result = " ".join(str(value or "").split())
    return result[:limit] if limit else result

# Converts a flexible model value into a predictable list.
def _list(value: Any) -> list:
    """Convert a flexible model value into a predictable list."""
    return value if isinstance(value, list) else []

# Converts a flexible model value into a predictable dictionary.
def _dict(value: Any) -> dict:
    """Convert a flexible model value into a predictable dictionary."""
    return value if isinstance(value, dict) else {}

# Converts a flexible model value into a clean list of strings.
def _strings(value: Any, limit: int = 0) -> list[str]:
    # A model that answers `"exports": "ensureSeeded"` means the one-item list.
    # Dropping the scalar threw the answer away, so a gap round that asked for
    # exactly that value could report the same gap forever and never close it.
    """Convert a flexible model value into a clean list of strings."""
    items = _list(value) or ([value] if isinstance(value, (str, int, float)) else [])
    out = []
    for item in items:
        text = _text(item, limit)
        if text and text not in out:
            out.append(text)
    return out

# Converts a flexible model value into a clean list of record dictionaries.
def _records(value: Any) -> list[dict]:
    """Convert a flexible model value into a clean list of record dictionaries."""
    return [dict(item) for item in _list(value) if isinstance(item, dict)]

# A URL with its dynamic segment spelled one way.
# Symbols removed/normalized:
# - Query parameters after '?' (e.g., '?search=1') -> stripped
# - URL anchors/hashes after '#' (e.g., '#section') -> stripped
# - Extra slashes '/' -> normalized
# - Dynamic segment symbols ':', '[', ']', '{', '}' (e.g., ':id', '[id]', '{id}') -> normalized to '[*]'
def _url_shape(value: Any) -> str:
    """A URL with its dynamic segment spelled one way.

    A site map writes /workshop/job/:id and the routes table writes
    /workshop/job/[id] for the same screen. Comparing the two as plain strings
    reported a gap the planner could not close — it kept rewriting a page that
    was already there, and burned every gap round on one phantom.
    """
    path = _text(value).split("?", 1)[0].split("#", 1)[0]
    parts = []
    for part in path.strip("/").split("/"):
        if not part:
            continue
        if part.startswith((":", "[")) or part.endswith("]") or part.startswith("{"):
            parts.append("[*]")
        else:
            parts.append(part.lower())
    return "/" + "/".join(parts)


# Converts a label into a safe URL/file slug.
# Symbols removed/replaced:
# - All non-alphanumeric characters [^a-z0-9]+ (spaces, punctuation: !, @, #, $, %, ^, &, *, (, ), _, +, =, {, }, |, \, :, ;, ", ', <, >, ,, ., ?, / etc.) -> replaced with '-'
# - Leading and trailing dashes '-' -> stripped
def _slug(value: str, fallback: str = "agentforge-app") -> str:
    """Convert a label into a safe URL/file slug."""
    result = re.sub(r"[^a-z0-9]+", "-", _text(value).lower()).strip("-")
    return result[:48].strip("-") or fallback

# Renders only the attributes that actually have a value.

# Match an access description to an exact role name.
# Symbols & prefixes removed:
# - Role prefixes: 'as role:', 'as role=', 'as role-', 'role:', 'role=', 'role-' -> stripped
def _canonical_actor(value: Any, fallback: str = "") -> str:
    """Match an access description to an exact role name."""
    actor = _text(value, 80)
    actor = re.sub(r"^(?:as\s+)?role\s*[:=-]?\s+", "", actor,
                   flags=re.I).strip()
    return actor or fallback

# Read the first complete JSON object in a model response.
def _json_object(raw: str) -> dict:
    """Read the first complete JSON object in a model response."""
    source = str(raw or "").strip()
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", source,
                        flags=re.I | re.S)
    candidates = list(reversed(fenced))
    candidates.append(source)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for match in re.finditer(r"\{", candidate):
            try:
                # From: agents/data/database_server.py
                value, _ = decoder.raw_decode(candidate[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    return {}

# Escape one value so it can be written safely inside a Markdown table cell.
# Symbols escaped/replaced:
# - Table column separator '|' -> escaped as '\|'
# - Line breaks '\n' -> replaced with a space ' '
def _md_cell(value: Any) -> str:
    """Escape one value so it can be written safely inside a Markdown table cell."""
    if isinstance(value, list):
        value = ", ".join(_text(item) for item in value)
    return _text(value).replace("|", "\\|").replace("\n", " ") or "—"

# Render a short list of values as readable Markdown bullets.
def _bullets(items: Any, empty: str = "None") -> list[str]:
    """Render a short list of values as readable Markdown bullets."""
    values = _list(items)
    if not values:
        return [f"- {empty}"]
    lines = []
    for item in values:
        if isinstance(item, dict):
            label = item.get("text") or item.get("name") or item.get("decision")
            tail = item.get("reason") or item.get("purpose") or item.get("tradeoff")
            line = _text(label)
            if tail:
                line += " — " + _text(tail)
        else:
            line = _text(item)
        if line:
            lines.append("- " + line)
    return lines or [f"- {empty}"]

__all__ = [name for name in globals() if not name.startswith('__')]
