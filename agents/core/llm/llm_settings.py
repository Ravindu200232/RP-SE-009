"""Routes Ollama requests to a local service or Ollama Cloud."""
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

log = logging.getLogger("ollama")

DEFAULT_LOCAL_HOST = "http://localhost:11434"
CLOUD_HOST = "https://ollama.com"

SETTINGS_PATH = Path.home() / ".agentforge" / "settings.json"


FALLBACK_CLOUD = [
    "gemma4:31b-cloud", "bjoernb/gemma4-31b-fast:latest",
    "qwen3-coder:480b-cloud", "deepseek-v3.1:671b-cloud",
    "gpt-oss:120b-cloud", "kimi-k2:1t-cloud", "glm-4.6:cloud",
    "minimax-m2:cloud",
]


# Use the full cloud window when Ollama reports a smaller placeholder value.
CLOUD_DEFAULT_CTX = 262144

# Some cloud wrappers do not include "cloud" in their names.
_KNOWN_CLOUD = {m.lower() for m in FALLBACK_CLOUD}

# Treat names with and without the optional "latest" tag as the same model.
_KNOWN_CLOUD |= {m[: -len(":latest")] for m in _KNOWN_CLOUD
                 if m.endswith(":latest")}

LOCAL_DEFAULT_CTX = 16384

_ICONS = [
    ("coder", "⚛"), ("code", "⚛"), ("qwen", "⚛"), ("kimi", "🌙"),
    ("deepseek", "🔍"), ("gpt-oss", "🌀"), ("glm", "🧊"), ("minimax", "🎯"),
    ("nemotron", "🟩"), ("gemma", "💎"), ("llama", "🦙"), ("mistral", "⚡"),
    ("phi", "🔬"), ("vl", "👁"),
]


# Choose the small UI icon used to describe a model entry.
def _icon_for(model_id: str) -> str:
    """Choose the small UI icon used to describe a model entry."""
    m = model_id.lower()
    for key, icon in _ICONS:
        if key in m:
            return icon
    return "🧠"


# Turn a model ID into a readable label.
def _pretty_label(model_id: str) -> str:
    """Turn a model ID into a readable label."""
    base = re.sub(r"[-:]cloud$", "", model_id.strip())
    base = base.split("/")[-1]
    parts = re.split(r"[:\-]", base)
    out = []
    for p in parts:
        if not p or p == "latest":
            continue
        if re.fullmatch(r"\d+(\.\d+)?[bmt]", p, re.I):
            out.append(p.upper())
        elif p.lower() in ("vl", "moe", "gpt", "oss", "glm"):
            out.append(p.upper())
        else:
            out.append(p[:1].upper() + p[1:])
    return " ".join(out) or model_id


# Check whether a model runs through Ollama Cloud.
def is_cloud_model(model: str) -> bool:
    """Check whether a model runs through Ollama Cloud."""
    if not model:
        return False
    m = model.strip().lower()
    if m.endswith("-cloud") or m.endswith(":cloud") or m in _KNOWN_CLOUD:
        return True

    # Source: llm_client.py — imported helper(s) come from this file.
    from agents.core.llm.llm_client import _default_client
    # From: agents/core/llm/llm_client.py
    return model.strip() in _default_client().remote_names()


# Choose a safe context size for the model. Cloud models use their full window. Local models use the configured
# limit.
def max_context(model: str) -> int:
    """Choose a safe context size for the model.

    Cloud models use their full window. Local models use the configured limit.
    """
    # Source: llm_client.py — imported helper(s) come from this file.
    from agents.core.llm.llm_client import _default_client
    # From: agents/core/llm/llm_client.py
    real = _default_client().model_context(model)

    if is_cloud_model(model):
        return max(real, CLOUD_DEFAULT_CTX)

    override = (os.environ.get("AGENTFORGE_NUM_CTX", "").strip()
                or str(load_settings().get("local_num_ctx", "")).strip())
    want = max(4096, int(override)) if override.isdigit() else LOCAL_DEFAULT_CTX
    return min(want, real) if real else want


# Read AgentForge settings, or return an empty result on failure.
def load_settings() -> dict:
    """Read AgentForge settings, or return an empty result on failure."""
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"settings read failed: {e}")
    return {}


# Update AgentForge settings and report whether the save worked.
def save_settings(data: dict) -> bool:
    """Update AgentForge settings and report whether the save worked."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        current = load_settings()
        # From: agents/planner/builder/project_memory.py
        current.update(data)
        SETTINGS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log.warning(f"settings write failed: {e}")
        return False


# Read the API key from the environment or saved settings.
def get_api_key() -> str:
    """Read the API key from the environment or saved settings."""
    return (os.environ.get("OLLAMA_API_KEY", "").strip()
            or str(load_settings().get("ollama_api_key", "")).strip())


# Returns the configured address of the local Ollama service.
def get_local_host() -> str:
    """Return the configured address of the local Ollama service."""
    host = (os.environ.get("OLLAMA_HOST", "").strip()
            or str(load_settings().get("ollama_host", "")).strip()
            or DEFAULT_LOCAL_HOST)
    if not host.startswith("http"):
        host = f"http://{host}"
    return host.rstrip("/")


