"""
Unified Ollama client — local daemon + Ollama Cloud.

Cloud routing rules
-------------------
A model is treated as a cloud model when its name ends with ``-cloud`` or
``:cloud`` (e.g. ``qwen3-coder:480b-cloud``, ``glm-4.6:cloud``).

Two ways to reach cloud models, both supported here:

1. **Local proxy** — user ran ``ollama signin`` on a recent Ollama build.
   Cloud models then work through ``http://localhost:11434`` exactly like
   local ones; the daemon forwards to ollama.com. No key needed here.
2. **Direct API key** — user pasted an ollama.com API key into AgentForge.
   We then talk straight to ``https://ollama.com`` with a Bearer token,
   so no local Ollama install is required for cloud models at all.

If a key is configured it wins for cloud models; otherwise we fall back to
the local daemon and let it proxy.
"""
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
    "qwen3-coder:480b-cloud", "deepseek-v3.1:671b-cloud",
    "gpt-oss:120b-cloud", "kimi-k2:1t-cloud", "glm-4.6:cloud",
    "minimax-m2:cloud",
]


CLOUD_DEFAULT_CTX = 131072

LOCAL_DEFAULT_CTX = 16384

_ICONS = [
    ("coder", "⚛"), ("code", "⚛"), ("qwen", "⚛"), ("kimi", "🌙"),
    ("deepseek", "🔍"), ("gpt-oss", "🌀"), ("glm", "🧊"), ("minimax", "🎯"),
    ("nemotron", "🟩"), ("gemma", "💎"), ("llama", "🦙"), ("mistral", "⚡"),
    ("phi", "🔬"), ("vl", "👁"),
]


def _icon_for(model_id: str) -> str:
    m = model_id.lower()
    for key, icon in _ICONS:
        if key in m:
            return icon
    return "🧠"


def _pretty_label(model_id: str) -> str:
    """`qwen3.5:397b-cloud` → `Qwen3.5 397B`."""
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


def is_cloud_model(model: str) -> bool:
    """True when the model name marks it as an Ollama Cloud model."""
    if not model:
        return False
    m = model.strip().lower()
    if m.endswith("-cloud") or m.endswith(":cloud"):
        return True

    return model.strip() in _default_client().remote_names()


def max_context(model: str) -> int:
    """
    Context window to request for this model.

    Cloud models get their full published window — nothing runs on the user's
    GPU, so there is no reason to hold back. Local models are capped by a
    conservative default (overridable via settings ``local_num_ctx`` or the
    ``AGENTFORGE_NUM_CTX`` env var) and never asked for more than they support.
    """
    real = _default_client().model_context(model)

    if is_cloud_model(model):
        return real or CLOUD_DEFAULT_CTX

    override = (os.environ.get("AGENTFORGE_NUM_CTX", "").strip()
                or str(load_settings().get("local_num_ctx", "")).strip())
    want = max(4096, int(override)) if override.isdigit() else LOCAL_DEFAULT_CTX
    return min(want, real) if real else want


def load_settings() -> dict:
    """Read ~/.agentforge/settings.json. Never raises."""
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"settings read failed: {e}")
    return {}


def save_settings(data: dict) -> bool:
    """Merge-write ~/.agentforge/settings.json. Never raises."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        current = load_settings()
        current.update(data)
        SETTINGS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log.warning(f"settings write failed: {e}")
        return False


def get_api_key() -> str:
    """API key from env first, then the settings file."""
    return (os.environ.get("OLLAMA_API_KEY", "").strip()
            or str(load_settings().get("ollama_api_key", "")).strip())


def get_local_host() -> str:
    """Local daemon URL — env override wins, then settings, then default."""
    host = (os.environ.get("OLLAMA_HOST", "").strip()
            or str(load_settings().get("ollama_host", "")).strip()
            or DEFAULT_LOCAL_HOST)
    if not host.startswith("http"):
        host = f"http://{host}"
    return host.rstrip("/")


class OllamaClient:
    """Thin requests wrapper that transparently routes local vs cloud."""

    def __init__(self, host: str = None, api_key: str = None):
        self.host = (host or get_local_host()).rstrip("/")
        self._api_key = api_key
        self._tags_cache = None
        self._cloud_tags_cache = None
        self._show_cache = {}

    @property
    def api_key(self) -> str:

        return self._api_key if self._api_key is not None else get_api_key()

    def route(self, model: str):
        """Return (base_url, headers) for this model."""
        headers = {"Content-Type": "application/json"}
        if is_cloud_model(model) and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            return CLOUD_HOST, headers
        return self.host, headers

    def describes_cloud(self, model: str) -> bool:
        return is_cloud_model(model)

    @staticmethod
    def _rejected_think(status: int, text: str) -> bool:
        """Whether this 4xx is the daemon saying the model cannot think."""
        return status == 400 and "think" in (text or "").lower()

    def chat_stream(self, model: str, messages: list, tools: list = None,
                    options: dict = None, keep_alive=None, timeout: int = 1800,
                    think: bool = None, stall: int = 300):
        """
        Yield decoded chunks from /api/chat with stream=True.

        Each yielded item is the raw Ollama chunk dict, so callers can read
        ``chunk["message"]["content"]`` and ``chunk["message"]["tool_calls"]``.

        `think` maps to Ollama's own field: True asks a reasoning model to
        think first, False suppresses it, None leaves the model's default
        alone. A model with no thinking mode answers a request carrying the
        field with a 400, so that one case is retried without it rather than
        failing a build over a toggle.

        TWO deadlines, because they catch opposite failures and neither
        catches the other.

        `stall` is the longest silence tolerated — requests' own read timeout,
        which fires when NOTHING arrives. Without it a model that accepts the
        request and then says nothing is bounded only by `timeout`, and the
        total budget below is checked inside the chunk loop, so a stream with
        no first chunk never reaches it. Measured: a QA repair round sat at
        "still working — 210s, 0 tokens" against a remote model, and its real
        ceiling was the 1800s default — half an hour of silence with nothing on
        screen and no error.

        `timeout` is enforced as a TOTAL budget for the whole stream, not only
        as the gap between chunks. requests' own timeout is the second of
        those, and on a stream it is nearly useless: measured on one page edit,
        3045 chunks arrived in 18 seconds — 1991 of them reasoning tokens — with
        the longest silence at 0.5s. A model that keeps generating therefore
        never trips a 150s read timeout, and a runaway turn hung a page update
        for over seven minutes with nothing on screen and no error. Whatever
        arrived before the budget ran out is kept; the caller sees a truncated
        answer instead of waiting forever.
        """
        base, headers = self.route(model)
        payload = {"model": model, "messages": messages, "stream": True}
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        if think is not None:
            payload["think"] = bool(think)

        r = requests.post(f"{base}/api/chat", json=payload, headers=headers,
                          stream=True, timeout=(15, stall))

        if r.status_code >= 400:
            body = r.text
            if self._rejected_think(r.status_code, body) and "think" in payload:
                log.info(f"{model} has no thinking mode — retrying without it")
                payload.pop("think")
                r = requests.post(f"{base}/api/chat", json=payload,
                                  headers=headers, stream=True,
                                  timeout=(15, stall))
                body = r.text if r.status_code >= 400 else ""
            if r.status_code >= 400:
                raise RuntimeError(
                    f"Ollama {r.status_code} @ {base}: {body[:300]}")

        deadline = time.time() + timeout
        chunks = 0
        try:
            for line in r.iter_lines():
                if time.time() > deadline:
                    log.warning(f"{model}: stopping the stream after {timeout}s "
                                f"and {chunks} chunk(s) — the total budget is "
                                f"spent")
                    break
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunks += 1
                yield chunk
        except requests.exceptions.ReadTimeout:

            log.warning(f"{model}: no output for {stall}s after {chunks} "
                        f"chunk(s) — giving up on this call")
            raise RuntimeError(
                f"{model} sent nothing for {stall}s. The model may be "
                f"overloaded or the prompt too large for it."
            ) from None
        finally:

            r.close()

    def chat(self, model: str, messages: list, tools: list = None,
             options: dict = None, keep_alive=None, timeout: int = 600,
             think: bool = None) -> dict:
        """Non-streaming chat. Returns the full response dict."""
        base, headers = self.route(model)
        payload = {"model": model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        if think is not None:
            payload["think"] = bool(think)

        r = requests.post(f"{base}/api/chat", json=payload, headers=headers,
                          timeout=timeout)
        if self._rejected_think(r.status_code, r.text) and "think" in payload:
            log.info(f"{model} has no thinking mode — retrying without it")
            payload.pop("think")
            r = requests.post(f"{base}/api/chat", json=payload, headers=headers,
                              timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(
                f"Ollama {r.status_code} @ {base}: {r.text[:300]}")
        return r.json()

    def tags(self, refresh: bool = False) -> list:
        """Raw /api/tags entries from the local daemon. [] if unreachable."""
        if self._tags_cache is not None and not refresh:
            return self._tags_cache
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=6)
            self._tags_cache = r.json().get("models", []) or []
        except Exception:
            self._tags_cache = []
        return self._tags_cache

    def cloud_tags(self, refresh: bool = False) -> list:
        """Models ollama.com exposes to this API key. [] without a key."""
        if not self.api_key:
            return []
        if self._cloud_tags_cache is not None and not refresh:
            return self._cloud_tags_cache
        try:
            r = requests.get(f"{CLOUD_HOST}/api/tags",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=10)
            self._cloud_tags_cache = r.json().get("models", []) or []
        except Exception:
            self._cloud_tags_cache = []
        return self._cloud_tags_cache

    def list_local(self) -> list:
        """Every model name the daemon knows about."""
        return [m.get("name") for m in self.tags() if m.get("name")]

    def remote_names(self) -> set:
        """Names the daemon proxies to ollama.com — i.e. cloud models."""
        return {m["name"] for m in self.tags()
                if "ollama.com" in str(m.get("remote_host") or "")
                and m.get("name")}

    def signed_in(self) -> bool:
        """
        True when the local daemon is signed in to ollama.com.

        A signed-in daemon proxies cloud models itself, so no API key is
        needed here — it reports them with a ``remote_host`` on ollama.com.
        """
        return bool(self.remote_names())

    def cloud_ready(self) -> bool:
        """Cloud models are usable via an API key or a signed-in daemon."""
        return bool(self.api_key) or self.signed_in()

    def show(self, model: str) -> dict:
        """Cached /api/show — real context length, family and capabilities."""
        if model in self._show_cache:
            return self._show_cache[model]
        base, headers = self.route(model)
        info = {}
        try:
            r = requests.post(f"{base}/api/show", json={"model": model},
                              headers=headers, timeout=15)
            if r.status_code < 400:
                info = r.json() or {}
        except Exception:
            pass
        self._show_cache[model] = info
        return info

    def supports_vision(self, model: str) -> bool:
        """
        Whether the model accepts images.

        `show()` already returns this and its result is cached, so asking costs
        nothing beyond the probe the catalogue already makes. `or []` is load
        bearing: at least one installed model reports `capabilities: null`.
        """
        caps = (self.show(model) or {}).get("capabilities") or []
        return any(str(c).lower() == "vision" for c in caps)

    def model_context(self, model: str) -> int:
        """The model's real maximum context length, or 0 if unknown."""
        mi = (self.show(model) or {}).get("model_info") or {}
        for k, v in mi.items():
            if k.endswith("context_length") and isinstance(v, int):
                return v
        return 0

    def supports_tools(self, model: str) -> bool:
        return "tools" in ((self.show(model) or {}).get("capabilities") or [])

    def _entry(self, model_id: str, cloud: bool, probe: bool = True) -> dict:
        ctx = self.model_context(model_id) if probe else 0
        if not cloud and ctx:

            ctx = max_context(model_id)
        low = model_id.lower()
        if cloud:
            tag = "cloud"
        elif "coder" in low or "code" in low:
            tag = "code"
        elif re.search(r":(\d{2,3})b", low):
            tag = "big"
        else:
            tag = "quality"
        return {
            "id": model_id,
            "label": _pretty_label(model_id),
            "icon": _icon_for(model_id),
            "tag": tag,
            "role": "build" if "cod" in low else "both",
            "ctx": ctx or (CLOUD_DEFAULT_CTX if cloud else 0),
            "installed": True,

            "vision": self.supports_vision(model_id) if probe else False,
            "desc": (f"Cloud · {(ctx or CLOUD_DEFAULT_CTX) // 1024}k context · no VRAM"
                     if cloud else
                     f"Local · {ctx // 1024}k context" if ctx else "Local model"),
        }

    def discover(self, refresh: bool = False) -> dict:
        """
        Ask the daemon (and ollama.com, if a key is set) what actually exists.

        Returns ``{"cloud": [...], "local": [...]}`` of UI-ready entries.
        Falls back to a small static cloud list only when nothing is reachable.
        """
        if refresh:
            self._tags_cache = None
            self._cloud_tags_cache = None

        tags = self.tags(refresh=refresh)
        remote = self.remote_names()

        cloud_ids, local_ids = [], []
        for m in tags:
            name = m.get("name")
            if not name:
                continue
            (cloud_ids if name in remote else local_ids).append(name)

        for m in self.cloud_tags(refresh=refresh):
            name = m.get("name")
            if name and name not in cloud_ids:
                cloud_ids.append(name)

        with ThreadPoolExecutor(max_workers=8) as pool:
            cloud = list(pool.map(lambda i: self._entry(i, True), cloud_ids))
            local = list(pool.map(lambda i: self._entry(i, False), local_ids))

        if not cloud:

            cloud = [{**self._entry(i, True, probe=False), "installed": False}
                     for i in FALLBACK_CLOUD]

        cloud.sort(key=lambda e: -e["ctx"])
        local.sort(key=lambda e: (e["tag"] != "code", e["id"]))
        return {"cloud": cloud, "local": local}

    def cloud_reachable(self) -> bool:
        """True if a configured API key actually authenticates."""
        if not self.api_key:
            return False
        try:
            r = requests.get(f"{CLOUD_HOST}/api/tags",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=8)
            return r.status_code < 400
        except Exception:
            return False

    def has_model(self, model: str) -> bool:
        """Cloud models need no local install; local ones are matched by tag."""
        if is_cloud_model(model):

            if self.api_key:
                return True
            return any(model == n for n in self.list_local())
        names = self.list_local()
        return any(model == n or model.split(":")[0] == n.split(":")[0]
                   for n in names)

    def pull(self, model: str, on_progress=None) -> bool:
        """Pull a model into the local daemon. Cloud models are never pulled —
        they have no weights to download."""
        if is_cloud_model(model):
            return True
        try:
            r = requests.post(f"{self.host}/api/pull", json={"name": model},
                              stream=True, timeout=1800)
            last = -1
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("total") and on_progress:
                    pct = int(chunk.get("completed", 0) / chunk["total"] * 100)
                    if pct != last and pct % 10 == 0:
                        on_progress(pct)
                        last = pct
                if "success" in chunk.get("status", ""):
                    return True
            return True
        except Exception as e:
            log.error(f"pull failed: {e}")
            return False

    def unload(self, model: str):
        """Free VRAM. No-op for cloud models — nothing is resident locally."""
        if is_cloud_model(model):
            return
        try:
            requests.post(f"{self.host}/api/generate",
                          json={"model": model, "keep_alive": 0}, timeout=8)
        except Exception:
            pass

    def catalog(self, refresh: bool = True) -> dict:
        """Everything the UI needs to render its model pickers."""
        found = self.discover(refresh=refresh)
        return {
            "cloud": found["cloud"],
            "local_models": found["local"],

            "local": [e["id"] for e in found["local"]] + [e["id"] for e in found["cloud"]
                                                          if e.get("installed")],
            "cloud_enabled": self.cloud_ready(),
            "cloud_via": ("api-key" if self.api_key
                          else "signed-in" if self.signed_in() else "none"),
            "host": self.host,
            "local_ctx": LOCAL_DEFAULT_CTX,
        }


_CLIENT = None


def _default_client() -> "OllamaClient":
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OllamaClient()
    return _CLIENT


def set_default_client(client: "OllamaClient"):
    """Let the server share its configured client with the helpers above."""
    global _CLIENT
    _CLIENT = client
