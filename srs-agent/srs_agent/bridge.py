"""
Every seam between the SRS agent and AgentForge lives here.

The `app/` tree below this file is a verbatim copy of the standalone
srs-generator, and it is meant to stay that way — a future re-sync should be a
directory copy, not a merge. So everything AgentForge-specific is collected in this
one module, and `app/config.py` is the only file in the copy that imports it.

That is also why this is a plain import rather than the environment-variable
dance you would normally use to configure pydantic-settings: an env var only
works if it is set before `app.config` is first imported, and there is no way
to enforce that ordering from inside a package that can be imported from a
server thread, a test, or a scratchpad script. An import has no ordering to get
wrong.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


LOCODE_ROOT = Path(__file__).resolve().parents[2]


if str(LOCODE_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCODE_ROOT))

PROD_DIR = LOCODE_ROOT / "production-ready"


SRS_STAGING = PROD_DIR / ".srs"


SRS_PORT = 7826


DEFAULT_SRS_MODEL = "gemma4:31b-cloud"


def agentforge_settings() -> dict:
    """
    Read ~/.agentforge/settings.json. Never raises.

    Prefers AgentForge's own reader so the two stay in step, but falls back to
    reading the file directly: this module is also imported by the standalone
    verification scripts, where a broken `agents` import should not be the
    thing that stops the SRS from starting.
    """
    try:
        from agents.ollama_client import load_settings
        return load_settings()
    except Exception:
        try:
            path = Path.home() / ".agentforge" / "settings.json"
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}


def srs_model() -> str:
    """
    The model the SRS should use when the caller did not name one.

    The sidebar's SRS picker writes `srs_model`. It falls back to the agent's
    model rather than to a hardcoded name, because a user who has chosen a
    model once has told us which models this machine can actually reach.
    """
    settings = agentforge_settings()
    for key in ("srs_model", "agent_model"):
        value = str(settings.get(key, "")).strip()
        if value:
            return value
    return DEFAULT_SRS_MODEL


def route(model: str) -> tuple[str, dict]:
    """
    (base_url, headers) for this model, using AgentForge's routing.

    This is the whole reason the SRS side does not talk to Ollama directly any
    more: `:cloud` models go to ollama.com with the bearer token AgentForge already
    has saved, where the copied adapter posted every model to localhost:11434
    and so only worked after a separate `ollama signin`.
    """
    try:
        from agents.ollama_client import _default_client
        return _default_client().route(model)
    except Exception:
        return "http://localhost:11434", {"Content-Type": "application/json"}


def num_ctx(model: str) -> int:
    """Context window to request — measured per model, not a fixed 8192."""
    try:
        from agents.ollama_client import max_context
        return int(max_context(model))
    except Exception:
        return 8192


SRS_DB = "agentforge_srs"


def mongo_uri() -> str:
    """AgentForge's mongod, on whatever port it settled on."""
    try:
        from agents.mongo import MONGO, get_uri_override
        override = get_uri_override()
        if override:
            return override
        return f"mongodb://127.0.0.1:{MONGO.port}/{SRS_DB}"
    except Exception:
        return f"mongodb://127.0.0.1:27017/{SRS_DB}"
