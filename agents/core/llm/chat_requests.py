"""Send chat requests to local or cloud Ollama."""
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


class OllamaChatMixin:
    # Check whether the model rejected the thinking option.
    @staticmethod
    def _rejected_think(status: int, text: str) -> bool:
        """Check whether the model rejected the thinking option."""
        return status == 400 and "think" in (text or "").lower()

    # Sends one JSON request to the configured Ollama-compatible endpoint.
    def _post(self, url: str, **kwargs):
        """Send one JSON request to the configured Ollama-compatible endpoint."""
        last = None
        for attempt in range(4):
            try:
                r = _http().post(url, **kwargs)
                if r.status_code not in {429, 500, 502, 503, 504}:
                    return r
                last = RuntimeError(f"HTTP {r.status_code}: {r.text[:220]}")
                # From: agents/planner/builder/write_stream.py
                r.close()
            except _http().RequestException as exc:
                last = exc
            if attempt < 3:
                log.warning("Ollama transport/upstream failure — retry %s/3", attempt + 1)
                time.sleep((1, 2, 4)[attempt])
        raise RuntimeError(f"Ollama request failed after retries: {last}")

    # Yield chat updates as they arrive. Unsupported thinking options are retried without that option. ``stall``
    # limits silence, while ``timeout`` limits the whole response.
    def chat_stream(self, model: str, messages: list, tools: list = None,
                    options: dict = None, keep_alive=None, timeout: int = 1800,
                    think: bool = None, stall: int = 300):
        """Yield chat updates as they arrive.

        Unsupported thinking options are retried without that option. ``stall``
        limits silence, while ``timeout`` limits the whole response.
        """
        # From: agents/core/llm/llm_client.py
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
        except _http().exceptions.ReadTimeout:

            log.warning(f"{model}: no output for {stall}s after {chunks} "
                        f"chunk(s) — giving up on this call")
            raise RuntimeError(
                f"{model} sent nothing for {stall}s. The model may be "
                f"overloaded or the prompt too large for it."
            ) from None
        finally:

            # From: agents/planner/builder/write_stream.py
            r.close()

    # Sends one chat request to the selected model and return its response.
    def chat(self, model: str, messages: list, tools: list = None,
             options: dict = None, keep_alive=None, timeout: int = 600,
             think: bool = None) -> dict:
        """Return one complete chat response."""
        # From: agents/core/llm/llm_client.py
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

