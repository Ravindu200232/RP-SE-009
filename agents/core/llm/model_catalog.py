"""Discover, inspect, pull, and unload Ollama models."""
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
# Source: llm_settings.py — imported helper(s) come from this file.
from agents.core.llm.llm_settings import (
    CLOUD_DEFAULT_CTX, CLOUD_HOST, FALLBACK_CLOUD, LOCAL_DEFAULT_CTX,
    _icon_for, _pretty_label, is_cloud_model, max_context,
)
log = logging.getLogger("ollama")

# Use the public client module so tests and callers can replace HTTP transport.
def _http():
    """Use the public client module so tests and callers can replace HTTP transport."""
    # Source: llm.py — imported helper(s) come from this file.
    from agents.core.llm import llm_client
    return llm_client.requests


class OllamaCatalogMixin:
    # List models known by the local service.
    def tags(self, refresh: bool = False) -> list:
        """List models known by the local service."""
        if self._tags_cache is not None and not refresh:
            return self._tags_cache
        try:
            r = _http().get(f"{self.host}/api/tags", timeout=6)
            self._tags_cache = r.json().get("models", []) or []
            self._tags_ok = r.status_code < 400
        except Exception:
            self._tags_cache = []
            self._tags_ok = False
        return self._tags_cache

    # Check whether the local service answered its latest request.
    def daemon_ready(self) -> bool:
        """Check whether the local service answered its latest request."""
        if self._tags_cache is None:
            self.tags()
        return self._tags_ok

    # List cloud models available to the configured API key.
    def cloud_tags(self, refresh: bool = False) -> list:
        """List cloud models available to the configured API key."""
        if not self.api_key:
            return []
        if self._cloud_tags_cache is not None and not refresh:
            return self._cloud_tags_cache
        try:
            r = _http().get(f"{CLOUD_HOST}/api/tags",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=10)
            self._cloud_tags_cache = r.json().get("models", []) or []
        except Exception:
            self._cloud_tags_cache = []
        return self._cloud_tags_cache

    # List the model names known by the local service.
    def list_local(self) -> list:
        """List the model names known by the local service."""
        return [m.get("name") for m in self.tags() if m.get("name")]

    # List cloud model names registered with the local service.
    def remote_names(self) -> set:
        """List cloud model names registered with the local service."""
        return {m["name"] for m in self.tags()
                if "ollama.com" in str(m.get("remote_host") or "")
                and m.get("name")}

    # Returns the cloud account signed in through the local service.
    def account(self, refresh: bool = False) -> dict:
        """Return the cloud account signed in through the local service."""
        if self._me_cache is not None and not refresh:
            return self._me_cache
        me = {}
        try:
            r = _http().post(f"{self.host}/api/me", json={}, timeout=6)
            if r.status_code < 400:
                data = r.json() or {}
                if data.get("email") or data.get("name") or data.get("id"):
                    me = data
        except Exception:
            pass
        self._me_cache = me
        return me

    # Check whether the local service is signed in to Ollama Cloud.
    def signed_in(self) -> bool:
        """Check whether the local service is signed in to Ollama Cloud."""
        return bool(self.account()) or bool(self.remote_names())

    # Check whether cloud models can be used.
    def cloud_ready(self) -> bool:
        """Check whether cloud models can be used."""
        return bool(self.api_key) or self.signed_in()

    # Returns a clean display value for the current model entry in the model list.
    def show(self, model: str) -> dict:
        """Return cached details about one model."""
        if model in self._show_cache:
            return self._show_cache[model]
        # From: agents/core/llm/llm_client.py
        base, headers = self.route(model)
        info = {}
        try:
            r = _http().post(f"{base}/api/show", json={"model": model},
                              headers=headers, timeout=15)
            if r.status_code < 400:
                info = r.json() or {}
        except Exception:
            pass
        self._show_cache[model] = info
        return info

    # Check whether this model can accept image input.
    def supports_vision(self, model: str) -> bool:
        """Check whether the model accepts images."""
        caps = (self.show(model) or {}).get("capabilities") or []
        return any(str(c).lower() == "vision" for c in caps)

    # Returns the model's maximum context size, or zero when unknown.
    def model_context(self, model: str) -> int:
        """Return the model's maximum context size, or zero when unknown."""
        mi = (self.show(model) or {}).get("model_info") or {}
        for k, v in mi.items():
            if k.endswith("context_length") and isinstance(v, int):
                return v
        return 0

    # Normalize one discovered model into the catalogue shape used by the Studio.
    def _entry(self, model_id: str, cloud: bool, probe: bool = True) -> dict:
        """Normalize one discovered model into the catalogue shape used by the Studio."""
        ctx = self.model_context(model_id) if probe else 0
        if cloud:

            # Report the same cloud window this client will request.
            ctx = max(ctx, CLOUD_DEFAULT_CTX)
        elif ctx:
            # From: agents/core/llm/llm_settings.py
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
        # From: agents/core/llm/llm_settings.py
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

    # Builds the local and cloud model lists used by the interface.
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

    # Check whether the configured API key can reach Ollama Cloud.
    def cloud_reachable(self) -> bool:
        """Check whether the configured API key can reach Ollama Cloud."""
        if not self.api_key:
            return False
        try:
            r = _http().get(f"{CLOUD_HOST}/api/tags",
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=8)
            return r.status_code < 400
        except Exception:
            return False

    # Check whether the selected model is ready to use.
    def has_model(self, model: str) -> bool:
        """Check whether the selected model is ready to use."""
        # From: agents/core/llm/llm_settings.py
        if is_cloud_model(model):

            if self.api_key:
                return True
            return any(model == n for n in self.list_local())
        names = self.list_local()
        return any(model == n or model.split(":")[0] == n.split(":")[0]
                   for n in names)

    # Prepare a local model or register a cloud model for use.
    def pull(self, model: str, on_progress=None) -> bool:
        """Prepare a local model or register a cloud model for use."""
        # From: agents/core/llm/llm_settings.py
        cloud = is_cloud_model(model)

        # Cloud registration should fail quickly when sign-in is unavailable.
        budget = 120 if cloud else 1800
        try:
            r = _http().post(f"{self.host}/api/pull", json={"name": model},
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

    # Release a locally loaded model when it is no longer needed.
    def unload(self, model: str):
        """Unload a local model from memory."""
        # From: agents/core/llm/llm_settings.py
        if is_cloud_model(model):
            return
        try:
            _http().post(f"{self.host}/api/generate",
                          json={"model": model, "keep_alive": 0}, timeout=8)
        except Exception:
            pass

    # Returns the model information needed by the interface.
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

