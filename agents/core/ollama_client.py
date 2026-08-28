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


def _icon_for(model_id: str) -> str:
    m = model_id.lower()
    for key, icon in _ICONS:
        if key in m:
            return icon
    return "🧠"


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


def is_cloud_model(model: str) -> bool:
    """Check whether a model runs through Ollama Cloud."""
    if not model:
        return False
    m = model.strip().lower()
    if m.endswith("-cloud") or m.endswith(":cloud") or m in _KNOWN_CLOUD:
        return True

    return model.strip() in _default_client().remote_names()


def max_context(model: str) -> int:
    """Choose a safe context size for the model.

    Cloud models use their full window. Local models use the configured limit.
    """
    real = _default_client().model_context(model)

    if is_cloud_model(model):
        return max(real, CLOUD_DEFAULT_CTX)

    override = (os.environ.get("AGENTFORGE_NUM_CTX", "").strip()
                or str(load_settings().get("local_num_ctx", "")).strip())
    want = max(4096, int(override)) if override.isdigit() else LOCAL_DEFAULT_CTX
    return min(want, real) if real else want


def load_settings() -> dict:
    """Read AgentForge settings, or return an empty result on failure."""
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"settings read failed: {e}")
    return {}


def save_settings(data: dict) -> bool:
    """Update AgentForge settings and report whether the save worked."""
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
    """Read the API key from the environment or saved settings."""
    return (os.environ.get("OLLAMA_API_KEY", "").strip()
            or str(load_settings().get("ollama_api_key", "")).strip())


def get_local_host() -> str:
    """Return the configured address of the local Ollama service."""
    host = (os.environ.get("OLLAMA_HOST", "").strip()
            or str(load_settings().get("ollama_host", "")).strip()
            or DEFAULT_LOCAL_HOST)
    if not host.startswith("http"):
        host = f"http://{host}"
    return host.rstrip("/")


class OllamaClient:
    """Send Ollama requests to the correct local or cloud service."""

    def __init__(self, host: str = None, api_key: str = None):
        self.host = (host or get_local_host()).rstrip("/")
        self._api_key = api_key
        self._tags_cache = None
        self._tags_ok = False
        self._me_cache = None
        self._cloud_tags_cache = None
        self._show_cache = {}

    @property
    def api_key(self) -> str:

        return self._api_key if self._api_key is not None else get_api_key()

    def route(self, model: str):
        """Return the address and headers needed for this model."""
        headers = {"Content-Type": "application/json"}
        if is_cloud_model(model) and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            return CLOUD_HOST, headers
        return self.host, headers

    @staticmethod
    def _rejected_think(status: int, text: str) -> bool:
        """Check whether the model rejected the thinking option."""
        return status == 400 and "think" in (text or "").lower()

    def _post(self, url: str, **kwargs):
        last = None
        for attempt in range(4):
            try:
                r = requests.post(url, **kwargs)
                if r.status_code not in {429, 500, 502, 503, 504}:
                    return r
                last = RuntimeError(f"HTTP {r.status_code}: {r.text[:220]}")
                r.close()
            except requests.RequestException as exc:
                last = exc
            if attempt < 3:
                log.warning("Ollama transport/upstream failure — retry %s/3", attempt + 1)
                time.sleep((1, 2, 4)[attempt])
        raise RuntimeError(f"Ollama request failed after retries: {last}")

    def chat_stream(self, model: str, messages: list, tools: list = None,
                    options: dict = None, keep_alive=None, timeout: int = 1800,
                    think: bool = None, stall: int = 300):
        """Yield chat updates as they arrive.

        Unsupported thinking options are retried without that option. ``stall``
        limits silence, while ``timeout`` limits the whole response.
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

        r = self._post(f"{base}/api/chat", json=payload, headers=headers,
                       stream=True, timeout=(15, stall))

        if r.status_code >= 400:
            body = r.text
            if self._rejected_think(r.status_code, body) and "think" in payload:
                log.info(f"{model} has no thinking mode — retrying without it")
                payload.pop("think")
                r = self._post(f"{base}/api/chat", json=payload,
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
        """Return one complete chat response."""
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

        r = self._post(f"{base}/api/chat", json=payload, headers=headers,
                       timeout=timeout)
        if self._rejected_think(r.status_code, r.text) and "think" in payload:
            log.info(f"{model} has no thinking mode — retrying without it")
            payload.pop("think")
            r = self._post(f"{base}/api/chat", json=payload, headers=headers,
                           timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(
                f"Ollama {r.status_code} @ {base}: {r.text[:300]}")
        return r.json()

    def tags(self, refresh: bool = False) -> list:
        """List models known by the local service."""
        if self._tags_cache is not None and not refresh:
            return self._tags_cache
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=6)
            self._tags_cache = r.json().get("models", []) or []
            self._tags_ok = r.status_code < 400
        except Exception:
            self._tags_cache = []
            self._tags_ok = False
        return self._tags_cache

    def daemon_ready(self) -> bool:
        """Check whether the local service answered its latest request."""
        if self._tags_cache is None:
            self.tags()
        return self._tags_ok

    def cloud_tags(self, refresh: bool = False) -> list:
        """List cloud models available to the configured API key."""
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
        """List the model names known by the local service."""
        return [m.get("name") for m in self.tags() if m.get("name")]

    def remote_names(self) -> set:
        """List cloud model names registered with the local service."""
        return {m["name"] for m in self.tags()
                if "ollama.com" in str(m.get("remote_host") or "")
                and m.get("name")}

    def account(self, refresh: bool = False) -> dict:
        """Return the cloud account signed in through the local service."""
        if self._me_cache is not None and not refresh:
            return self._me_cache
        me = {}
        try:
            r = requests.post(f"{self.host}/api/me", json={}, timeout=6)
            if r.status_code < 400:
                data = r.json() or {}
                if data.get("email") or data.get("name") or data.get("id"):
                    me = data
        except Exception:
            pass
        self._me_cache = me
        return me

    def signed_in(self) -> bool:
        """Check whether the local service is signed in to Ollama Cloud."""
        return bool(self.account()) or bool(self.remote_names())

    def cloud_ready(self) -> bool:
        """Check whether cloud models can be used."""
        return bool(self.api_key) or self.signed_in()

    def show(self, model: str) -> dict:
        """Return cached details about one model."""
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
        """Check whether the model accepts images."""
        caps = (self.show(model) or {}).get("capabilities") or []
        return any(str(c).lower() == "vision" for c in caps)

    def model_context(self, model: str) -> int:
        """Return the model's maximum context size, or zero when unknown."""
        mi = (self.show(model) or {}).get("model_info") or {}
        for k, v in mi.items():
            if k.endswith("context_length") and isinstance(v, int):
                return v
        return 0

    def _entry(self, model_id: str, cloud: bool, probe: bool = True) -> dict:
        ctx = self.model_context(model_id) if probe else 0
        if cloud:

            # Report the same cloud window this client will request.
            ctx = max(ctx, CLOUD_DEFAULT_CTX)
        elif ctx:
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
            "ctx": ctx,
            "installed": True,

            "vision": self.supports_vision(model_id) if probe else False,
            "desc": (f"Cloud · {ctx // 1024}k context · no VRAM"
                     if cloud else
                     f"Local · {ctx // 1024}k context" if ctx else "Local model"),
        }

    def discover(self, refresh: bool = False) -> dict:
        """Build the local and cloud model lists used by the interface."""
        if refresh:
            self._tags_cache = None
            self._cloud_tags_cache = None
            self._me_cache = None

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
        """Check whether the configured API key can reach Ollama Cloud."""
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
        """Check whether the selected model is ready to use."""
        if is_cloud_model(model):

            if self.api_key:
                return True
            return any(model == n for n in self.list_local())
        names = self.list_local()
        return any(model == n or model.split(":")[0] == n.split(":")[0]
                   for n in names)

    def pull(self, model: str, on_progress=None) -> bool:
        """Prepare a local model or register a cloud model for use."""
        cloud = is_cloud_model(model)

        # Cloud registration should fail quickly when sign-in is unavailable.
        budget = 120 if cloud else 1800
        try:
            r = requests.post(f"{self.host}/api/pull", json={"name": model},
                              stream=True, timeout=budget)
            last = -1
            ok = True
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    log.error(f"pull {model}: {chunk['error']}")
                    ok = False
                    break
                if chunk.get("total") and on_progress:
                    pct = int(chunk.get("completed", 0) / chunk["total"] * 100)
                    if pct != last and pct % 10 == 0:
                        on_progress(pct)
                        last = pct
                if "success" in chunk.get("status", ""):
                    break
            if ok:

                # Refresh cached model lists after registration.
                self._tags_cache = None
                self._show_cache.pop(model, None)
            return ok or (cloud and bool(self.api_key))
        except Exception as e:
            if cloud and self.api_key:
                log.info(f"{model}: daemon unreachable for the cloud "
                         f"registration — the API key reaches it directly")
                return True
            log.error(f"pull failed: {e}")
            return False

    def unload(self, model: str):
        """Unload a local model from memory."""
        if is_cloud_model(model):
            return
        try:
            requests.post(f"{self.host}/api/generate",
                          json={"model": model, "keep_alive": 0}, timeout=8)
        except Exception:
            pass

    def catalog(self, refresh: bool = True) -> dict:
        """Return the model information needed by the interface."""
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
            "cloud_ctx": CLOUD_DEFAULT_CTX,
            "ollama_ready": self.daemon_ready(),
            "cloud_account": str(self.account().get("name") or ""),
        }


_CLIENT = None


def _default_client() -> "OllamaClient":
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OllamaClient()
    return _CLIENT


def set_default_client(client: "OllamaClient"):
    """Share the server's configured client with module helpers."""
    global _CLIENT
    _CLIENT = client
