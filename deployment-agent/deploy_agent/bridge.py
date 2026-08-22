"""
Every seam between the deployment agent and AgentForge lives here.

`deployment_agent/`, `dfagents/` and `dfserver.py` beside this file are a copy
of the standalone DeployForge, and they are meant to stay that way — a future
re-sync should be a directory copy, not a merge. So everything AgentForge-specific
is collected in this one module, and only three files in the copy import it:

    deployment_agent/config.py        where the data directory comes from
    deployment_agent/tools.py         which Ollama the readiness probe asks
    deployment_agent/orchestrator.py  which model writes the deployment plan

Two things in the copy were renamed rather than left alone, because AgentForge has
its own module of each name at the root of sys.path and one of the pair would
have shadowed the other:

    agents/    → dfagents/     (AgentForge's `agents.ollama_client`, `agents.mongo`)
    server.py  → dfserver.py   (AgentForge's own server.py)

Same reasoning as `srs_agent/bridge.py`: this is a plain import rather than an
environment-variable dance because an env var only works if it is set before
the module that reads it is first imported, and there is no way to enforce that
ordering from a package that can be imported from a server thread, a test, or a
scratchpad script. An import has no ordering to get wrong.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parent
PKG_ROOT = AGENT_ROOT.parent
LOCODE_ROOT = PKG_ROOT.parent

for _root in (AGENT_ROOT, PKG_ROOT, LOCODE_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

PROD_DIR = LOCODE_ROOT / "production-ready"


DEPLOY_DATA = PROD_DIR / ".deploy"


DEPLOY_PORT = 7834


DEFAULT_DEPLOY_MODEL = "gemma4:31b-cloud"


def agentforge_settings() -> dict:
    """
    Read ~/.agentforge/settings.json. Never raises.

    Prefers AgentForge's own reader so the two stay in step, but falls back to
    reading the file directly: this module is also imported by the standalone
    verification scripts, where a broken `agents` import should not be the thing
    that stops the deployment agent from starting.
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


def deploy_model() -> str:
    """
    The model that writes the deployment plan.

    Falls back to the agent's model rather than to a hardcoded name, because a
    user who has chosen a model once has told us which models this machine can
    actually reach.
    """
    settings = agentforge_settings()
    for key in ("deploy_model", "agent_model"):
        value = str(settings.get(key, "")).strip()
        if value:
            return value
    return DEFAULT_DEPLOY_MODEL


def route(model: str) -> tuple[str, dict]:
    """
    (base_url, headers) for this model, using AgentForge's routing.

    This is the whole reason the copy does not talk to Ollama directly any more:
    `:cloud` models go to ollama.com with the bearer token AgentForge already has
    saved, where the copied client posts every model to localhost:11434 and so
    only works after a separate `ollama signin`.
    """
    try:
        from agents.ollama_client import _default_client
        return _default_client().route(model)
    except Exception:
        return "http://localhost:11434", {"Content-Type": "application/json"}


def ollama_client(model: str = ""):
    """
    A planner client pointed at whichever Ollama can serve the chosen model.

    Read fresh on every call rather than captured at import: the model comes
    from a settings file the user can change while AgentForge is running, and the
    copied module constants were resolved the first time anything imported
    `deployment_agent.config`.
    """
    from dfagents.planner import OllamaClient

    tag = model or deploy_model()
    base, headers = route(tag)
    return OllamaClient(base_url=base.rstrip("/"), model=tag, headers=headers)


def ollama_probe() -> dict:
    """
    Is the chosen model reachable? For the readiness panel.

    The copy asked `http://127.0.0.1:11434/api/tags` and looked for the model by
    name, which reports every cloud tag as missing — the tag is not installed
    locally and never will be.
    """
    import requests

    tag = deploy_model()
    base, headers = route(tag)
    try:
        r = requests.get(f"{base.rstrip('/')}/api/tags", headers=headers, timeout=6)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception as e:                                      # noqa: BLE001
        return {"ready": False, "model_ready": False, "model": tag,
                "error": f"{type(e).__name__}: {e}"}

    cloud = tag.endswith(":cloud") or tag.endswith("-cloud")
    return {"ready": True, "model_ready": cloud or tag in names, "model": tag}


def project_dir(project: str) -> Path:
    """The absolute path AgentForge would hand to /api/runs/analyze."""
    return PROD_DIR / project


def free_tier_only() -> bool:
    """
    Keep the EC2 instance inside AWS's free tier.

    Defaults to True, which is the opposite of the copy's behaviour and
    deliberate: AgentForge deploys demo apps somebody is trying out, and the
    planning model chose t3.small on its own — about $15 a month, decided by a
    model, on an account whose owner asked for the free option. Set
    `aws_free_tier: false` in ~/.agentforge/settings.json to let the plan size the
    instance itself.
    """
    value = agentforge_settings().get("aws_free_tier", True)
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)
