"""The providers a person has an account with, kept once and reused by every app.

Before this, a Supabase key was asked for in the middle of a build, used by
that one project, and asked for again by the next. That is the wrong shape for
a credential: the account belongs to the person, not to the application, and
the second app has the same bucket as the first.

So a plugin is a provider - Stripe, Resend, Supabase, Google - and it has three
parts kept deliberately apart:

* **What it asks for** is the skill's own `setup.json`, which is also what the
  build's setup question reads. Nothing is copied here, so the card and the
  question can never drift apart.
* **What the person typed** lives with their account, sealed, in the same
  `user_credentials` document the deployment accounts use. It is never returned
  to a browser and never reaches a model: the read side hands back which keys
  are set and the last four characters, and nothing else.
* **Which apps use it** is a list of plugin ids in the project's own
  `.agentforge/plugins.json`. Ticking one there is what puts its values into
  that project's `.env.local`, and unticking it is what stops.

Several choices that ask for the same keys are modes of one plugin rather than
plugins of their own - Stripe test and Stripe live both write
`STRIPE_SECRET_KEY`, so as two cards they would quietly overwrite each other.

This module is deliberately not one of `server_runtime`'s parts: it needs none
of that shared namespace, so it is imported normally, the way `cli_signin` and
`github_device` are.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from server_modules.services import auth_db, secret_box

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "builder-agent" / "builder_agent" / "assets" / "skills"
CATALOG = SKILL_ROOT / "plugins.json"

# The same name an environment variable has to be, checked again here because
# this side writes into a real .env and a declaration is only as good as the
# file it was read from.
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
MAX_VALUE = 8192

# Where a project records which plugins it uses.
PROJECT_FILE = Path(".agentforge") / "plugins.json"


def _read_json(path: Path) -> dict:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        return body if isinstance(body, dict) else {}
    except (OSError, ValueError):
        return {}


def _declaration(skill: str) -> dict:
    return _read_json(SKILL_ROOT / skill / "setup.json")


def _fields_for(skill: str, choice_id: str) -> list[dict]:
    """Everything one mode asks for: the skill's own fields, then the choice's.

    Read rather than restated. Stripe asks for three keys because
    `payments/setup.json` says so, and if that file gains a fourth this gains
    it too without anyone remembering to come here.
    """
    declaration = _declaration(skill)
    choice = next((c for c in (declaration.get("choices") or [])
                   if isinstance(c, dict) and c.get("id") == choice_id), None)
    if not choice:
        return []
    out = []
    for field in list(declaration.get("fields") or []) + list(choice.get("fields") or []):
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "").strip().upper()
        if not ENV_NAME.fullmatch(key):
            continue
        out.append({
            "key": key,
            "label": str(field.get("label") or key)[:80],
            "hint": str(field.get("hint") or "")[:240],
            "example": str(field.get("example") or "")[:120],
            "secret": bool(field.get("secret", True)),
            "required": bool(field.get("required", True)),
        })
    return out


def catalog() -> list[dict]:
    """Every plugin that ships, with what each of its modes asks for."""
    body = _read_json(CATALOG)
    out = []
    for plugin in (body.get("plugins") or []):
        if not isinstance(plugin, dict) or not plugin.get("id"):
            continue
        skill = str(plugin.get("skill") or "")
        modes = []
        for mode in (plugin.get("modes") or []):
            if not isinstance(mode, dict):
                continue
            fields = _fields_for(skill, str(mode.get("choice") or ""))
            if not fields:
                continue
            modes.append({"choice": str(mode.get("choice")),
                          "label": str(mode.get("label") or ""),
                          "hint": str(mode.get("hint") or ""), "fields": fields})
        if not modes:
            continue
        out.append({
            "id": str(plugin["id"]), "name": str(plugin.get("name") or plugin["id"]),
            "group": str(plugin.get("group") or "Other"),
            "icon": str(plugin.get("icon") or ""),
            "site": str(plugin.get("site") or ""), "what": str(plugin.get("what") or ""),
            "skill": skill, "signin": str(plugin.get("signin") or ""), "modes": modes,
        })
    return out


def _by_id() -> dict:
    return {plugin["id"]: plugin for plugin in catalog()}


def groups() -> list[str]:
    return [str(group) for group in (_read_json(CATALOG).get("groups") or [])]


# -- what the person has set, without ever saying what it is -------------------
def _stored(user_id: str) -> dict:
    document = auth_db.get_db().user_credentials.find_one({"user_id": str(user_id)}) or {}
    stored = document.get("plugins")
    return stored if isinstance(stored, dict) else {}


def summary_for(user_id: str) -> list[dict]:
    """Which plugins are configured, which keys are set, and a four-character hint.

    Never a value. The same rule the deployment accounts follow: a browser that
    can read back a secret is a browser that can leak one, and the person who
    typed it already knows what they typed.
    """
    saved = _stored(user_id) if user_id else {}
    out = []
    for plugin in catalog():
        entry = saved.get(plugin["id"]) or {}
        values = entry.get("values") if isinstance(entry.get("values"), dict) else {}
        mode = str(entry.get("mode") or plugin["modes"][0]["choice"])
        declared = {field["key"] for m in plugin["modes"] for field in m["fields"]}
        hints, blank = {}, []
        for key in sorted(declared):
            raw = secret_box.unseal(values.get(key) or "")
            if raw:
                hints[key] = f"...{raw[-4:]}" if len(raw) > 4 else "set"
            else:
                blank.append(key)
        required = {field["key"] for m in plugin["modes"] if m["choice"] == mode
                    for field in m["fields"] if field["required"]}
        out.append({"id": plugin["id"], "mode": mode, "set": sorted(hints), "hints": hints,
                    "missing": [key for key in blank if key in required],
                    "configured": bool(required) and required.issubset(set(hints))})
    return out


def save(user_id: str, plugin_id: str, mode: str, values: dict) -> list[dict]:
    """Keep what they typed, sealed, against their account.

    A lone `-` clears one setting, the convention the deployment accounts
    already use. An empty box means "leave it alone", because a form that wipes
    a key you did not retype is a form that loses your key.
    """
    if not user_id:
        raise ValueError("Sign in before saving a plugin")
    plugin = _by_id().get(str(plugin_id))
    if not plugin:
        raise ValueError("Unknown plugin")
    chosen = next((m for m in plugin["modes"] if m["choice"] == str(mode)), plugin["modes"][0])
    declared = {field["key"] for field in chosen["fields"]}

    saved = _stored(user_id)
    entry = saved.get(plugin["id"]) if isinstance(saved.get(plugin["id"]), dict) else {}
    kept = dict(entry.get("values") or {})
    for key, value in (values or {}).items():
        key = str(key or "").strip().upper()
        if key not in declared:
            continue
        value = str(value if value is not None else "")
        if value == "-":
            kept.pop(key, None)
            continue
        if not value:
            continue
        if any(ch in value for ch in ("\r", "\n", "\0")) or len(value) > MAX_VALUE:
            raise ValueError(f"{key} contains a line break or is too long")
        kept[key] = secret_box.seal(value)

    saved[plugin["id"]] = {"mode": chosen["choice"], "values": kept}
    auth_db.get_db().user_credentials.update_one(
        {"user_id": str(user_id)},
        {"$set": {"plugins": saved, "updated_at": auth_db._now()}}, upsert=True)
    return summary_for(user_id)


def forget(user_id: str, plugin_id: str) -> list[dict]:
    saved = _stored(user_id)
    saved.pop(str(plugin_id), None)
    auth_db.get_db().user_credentials.update_one(
        {"user_id": str(user_id)},
        {"$set": {"plugins": saved, "updated_at": auth_db._now()}}, upsert=True)
    return summary_for(user_id)


# -- which apps use which ------------------------------------------------------
def enabled_for(project_dir) -> list[str]:
    known = set(_by_id())
    body = _read_json(Path(project_dir) / PROJECT_FILE)
    return [str(p) for p in (body.get("enabled") or []) if str(p) in known]


def set_enabled(project_dir, plugin_ids) -> list[str]:
    """Record which plugins this project uses, and which skills that entitles.

    Both are written, because the two readers are on opposite sides of a wall.
    The server reads `enabled` to know whose credentials to merge into the env;
    the builder-agent reads `skills` to know which pages the model may read,
    and it cannot import this module to work that out for itself - so the
    mapping is resolved once, here, by the side that owns the catalogue.
    """
    by_id = _by_id()
    chosen = [str(p) for p in (plugin_ids or []) if str(p) in by_id]
    skills = sorted({by_id[p]["skill"] for p in chosen if by_id[p].get("skill")})
    target = Path(project_dir) / PROJECT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"enabled": chosen, "skills": skills}, indent=2),
                      encoding="utf-8")
    return chosen


def skills_for(project_dir) -> list[str]:
    """The skills a project's plugins need the model to be able to read."""
    by_id = _by_id()
    return sorted({by_id[p]["skill"] for p in enabled_for(project_dir)
                   if by_id.get(p, {}).get("skill")})


def env_for(user_id: str, project_dir) -> dict:
    """The settings this project's plugins contribute, unsealed, ready to merge.

    This is the only function that returns a value, and it returns it to the
    server writing `.env.local` - not to a browser, not to a transcript and not
    to a model, which reads them back out of `process.env` at run time.
    """
    if not user_id:
        return {}
    saved, by_id, out = _stored(user_id), _by_id(), {}
    for plugin_id in enabled_for(project_dir):
        plugin, entry = by_id.get(plugin_id), saved.get(plugin_id)
        if not plugin or not isinstance(entry, dict):
            continue
        mode = str(entry.get("mode") or "")
        chosen = next((m for m in plugin["modes"] if m["choice"] == mode), plugin["modes"][0])
        declared = {field["key"] for field in chosen["fields"]}
        for key, sealed in (entry.get("values") or {}).items():
            if key in declared:
                value = secret_box.unseal(sealed or "")
                if value:
                    out[key] = value
    return out
