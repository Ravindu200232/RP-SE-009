"""Single, strict Gemma 4 runtime for every Locode LLM operation.

All callers use the installed local ``gemma4:12b`` model through Ollama.  The
runtime profile was measured on the target RTX 3060: a 98,304-token context and
two server-side slots remain fully GPU resident.  No caller may change the
model, context size, or introduce a cloud/local fallback.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from typing import Any, Iterable

import requests

log = logging.getLogger("llm")

OLLAMA_URL = "http://localhost:11434"
PROVIDER = "ollama"
LOCAL_MODEL = "gemma4:12b"
CLOUD_MODEL = "nemotron-3-super:cloud"

# Compatibility names used by older agents and request contracts. Planning is
# cloud-only; every source-writing, update, and repair call remains local-only.
ARCHITECT_MODEL = CLOUD_MODEL
GEN_MODEL = LOCAL_MODEL
FALLBACK_MODEL = LOCAL_MODEL
REPAIR_MODEL = LOCAL_MODEL
REMAINING_MODEL = LOCAL_MODEL

CONTEXT_TOKENS = 98_304
CLOUD_CONTEXT_TOKENS = 262_144
KEEP_ALIVE = "30m"
EXPECTED_FAMILY = "gemma4"
EXPECTED_QUANTIZATION = "Q4_K_M"

BASE_OPTS = {
    "num_ctx": CONTEXT_TOKENS,
    "temperature": 0.0,
    "top_p": 0.9,
}
ARCHITECT_OPTS = {"num_ctx": CONTEXT_TOKENS, "temperature": 0.1, "top_p": 0.9}
REPAIR_OPTS = {"num_ctx": CONTEXT_TOKENS, "temperature": 0.0, "top_p": 0.9}
REMAINING_OPTS = dict(REPAIR_OPTS)
THINK = False
REMAINING_THINK = False

_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_token_cb = None
_metrics_lock = threading.Lock()
_metrics = {"calls": 0, "promptTokens": 0, "outputTokens": 0,
            "evalDurationNs": 0, "loadDurationNs": 0}


class LLMError(RuntimeError):
    pass


class LLMTruncatedError(LLMError):
    pass


class RuntimeProfileError(LLMError):
    pass


def set_token_callback(fn):
    """Register ``callback(prompt_tokens, completion_tokens)`` for telemetry."""
    global _token_cb
    _token_cb = fn


def pinned_model(requested: str | None = None) -> str:
    """Return the only generation model and ignore legacy overrides."""
    if requested and requested != LOCAL_MODEL:
        log.warning("Ignoring model override %r; Locode is pinned to local %s",
                    requested, LOCAL_MODEL)
    return LOCAL_MODEL


def pinned_architect_model(requested: str | None = None) -> str:
    """Return the only planning model and ignore legacy overrides."""
    if requested and requested != CLOUD_MODEL:
        log.warning("Ignoring Architect model override %r; planning is pinned to %s",
                    requested, CLOUD_MODEL)
    return CLOUD_MODEL


def _resolve_model(requested: str | None, route: str) -> str:
    if route == "architect":
        return pinned_architect_model(requested)
    if route != "generation":
        raise LLMError(f"Unknown LLM route {route!r}")
    return pinned_model(requested)


def _track(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        return
    with _metrics_lock:
        _metrics["calls"] += 1
        _metrics["promptTokens"] += int(data.get("prompt_eval_count") or 0)
        _metrics["outputTokens"] += int(data.get("eval_count") or 0)
        _metrics["evalDurationNs"] += int(data.get("eval_duration") or 0)
        _metrics["loadDurationNs"] += int(data.get("load_duration") or 0)
    if not _token_cb:
        return
    try:
        _token_cb(int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0))
    except Exception:
        pass


def reset_metrics() -> None:
    with _metrics_lock:
        for key in _metrics:
            _metrics[key] = 0


def metrics_snapshot() -> dict[str, Any]:
    with _metrics_lock:
        value = dict(_metrics)
    seconds = value["evalDurationNs"] / 1_000_000_000
    value["tokensPerSecond"] = round(value["outputTokens"] / seconds, 2) if seconds else 0.0
    value["evalDurationSeconds"] = round(seconds, 3)
    value["loadDurationSeconds"] = round(value.pop("loadDurationNs") / 1_000_000_000, 3)
    value.pop("evalDurationNs", None)
    return value


def log_config(model: str | None = None) -> None:
    pinned_model(model)
    log.info("Locode routing -> architect=%s (%s ctx), generation=%s (%s ctx), think=%s",
             CLOUD_MODEL, CLOUD_CONTEXT_TOKENS, LOCAL_MODEL, CONTEXT_TOKENS, THINK)


def strip_think(text: str) -> str:
    return _THINK_TAG.sub("", text or "").strip()


def _request(method: str, path: str, *, timeout: int = 120, **kwargs):
    try:
        response = requests.request(method, f"{OLLAMA_URL}{path}", timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        detail = ""
        if response is not None:
            try:
                detail = str(response.text or "").strip()
            except Exception:
                detail = ""
        suffix = f" — {detail}" if detail else ""
        raise LLMError(f"Ollama request failed: {exc}{suffix}") from exc


def cloud_profile(*, prewarm: bool = True) -> dict[str, Any]:
    """Verify the pinned cloud planner tag and optionally make a tiny live call."""
    tags = _request("GET", "/api/tags", timeout=30).json().get("models") or []
    names = {str(item.get("name") or item.get("model") or "") for item in tags}
    if CLOUD_MODEL not in names:
        raise RuntimeProfileError(
            f"Required planning model {CLOUD_MODEL!r} is not installed. "
            f"Run `ollama pull {CLOUD_MODEL}`."
        )
    if prewarm:
        body = _payload(CLOUD_MODEL, [{"role": "user", "content": "Reply OK."}],
                        num_predict=4, think=False, extra_opts={"temperature": 0.0},
                        route="architect")
        body.update({"stream": False, "keep_alive": KEEP_ALIVE})
        checked = _request("POST", "/api/chat", json=body, timeout=120).json()
        _track(checked)
        if checked.get("error"):
            raise RuntimeProfileError(f"Cloud planner unavailable: {checked['error']}")
    return {"model": CLOUD_MODEL, "context": CLOUD_CONTEXT_TOKENS,
            "processor": "Ollama Cloud", "thinking": False}


def runtime_profile(*, prewarm: bool = True) -> dict[str, Any]:
    """Verify the exact model and its all-GPU 98K allocation.

    This is deliberately strict.  A missing model, different quantization, smaller
    context, or partial CPU offload aborts generation before project files change.
    """
    flash = str(os.environ.get("OLLAMA_FLASH_ATTENTION", "")).lower()
    kv_cache = str(os.environ.get("OLLAMA_KV_CACHE_TYPE", "")).lower()
    parallel = str(os.environ.get("OLLAMA_NUM_PARALLEL", ""))
    runtime_errors = []
    if flash not in {"1", "true"}:
        runtime_errors.append("OLLAMA_FLASH_ATTENTION must be 1")
    if kv_cache not in {"q8", "q8_0"}:
        runtime_errors.append("OLLAMA_KV_CACHE_TYPE must be q8_0")
    if parallel != "2":
        runtime_errors.append("OLLAMA_NUM_PARALLEL must be 2")
    if runtime_errors:
        raise RuntimeProfileError("Invalid Ollama runtime: " + "; ".join(runtime_errors))

    tags = _request("GET", "/api/tags", timeout=30).json().get("models") or []
    names = {str(item.get("name") or item.get("model") or "") for item in tags}
    if LOCAL_MODEL not in names:
        raise RuntimeProfileError(
            f"Required local model {LOCAL_MODEL!r} is not installed. Run `ollama pull {LOCAL_MODEL}`."
        )

    shown = _request("POST", "/api/show", json={"model": LOCAL_MODEL}, timeout=30).json()
    details = shown.get("details") or {}
    family = str(details.get("family") or "")
    quantization = str(details.get("quantization_level") or "")
    if family != EXPECTED_FAMILY or quantization.upper() != EXPECTED_QUANTIZATION:
        raise RuntimeProfileError(
            f"{LOCAL_MODEL} must be {EXPECTED_FAMILY} {EXPECTED_QUANTIZATION}; "
            f"Ollama reports family={family!r}, quantization={quantization!r}."
        )

    load_duration = 0
    if prewarm:
        body = _payload(
            LOCAL_MODEL,
            [{"role": "user", "content": "Reply with OK only."}],
            num_predict=2,
            think=False,
            extra_opts={"temperature": 0.0},
        )
        body.update({"stream": False, "keep_alive": KEEP_ALIVE})
        warmed = _request("POST", "/api/chat", json=body, timeout=300).json()
        load_duration = int(warmed.get("load_duration") or 0)
        _track(warmed)
        _reject_truncation(warmed, "runtime prewarm")

    running = _request("GET", "/api/ps", timeout=30).json().get("models") or []
    loaded = next((item for item in running
                   if str(item.get("name") or item.get("model")) == LOCAL_MODEL), None)
    if not loaded:
        raise RuntimeProfileError(f"{LOCAL_MODEL} did not remain loaded after prewarm")
    context = int(loaded.get("context_length") or 0)
    size = int(loaded.get("size") or 0)
    size_vram = int(loaded.get("size_vram") or 0)
    if context != CONTEXT_TOKENS:
        raise RuntimeProfileError(
            f"Gemma context allocation is {context:,}, expected exactly {CONTEXT_TOKENS:,}."
        )
    if not size or size_vram < size:
        cpu_pct = 100 if not size else round(max(0.0, 1.0 - size_vram / size) * 100)
        raise RuntimeProfileError(
            f"Gemma is partially CPU-offloaded ({cpu_pct}% CPU). Free VRAM and retry; "
            "Locode requires `ollama ps` to report 100% GPU before writing a project."
        )
    return {
        "model": LOCAL_MODEL,
        "family": family,
        "quantization": quantization,
        "context": context,
        "size": size,
        "sizeVram": size_vram,
        "processor": "100% GPU",
        "flashAttention": True,
        "kvCache": kv_cache,
        "parallel": 2,
        "prewarmLoadSeconds": round(load_duration / 1_000_000_000, 3),
        "warmStart": load_duration < 1_000_000_000,
    }


def ensure_loaded(model: str | None = None, extra_opts: dict | None = None):
    """Compatibility entrypoint; the profile is intentionally not caller-configurable."""
    pinned_model(model)
    if extra_opts and int(extra_opts.get("num_ctx", CONTEXT_TOKENS)) != CONTEXT_TOKENS:
        log.warning("Ignoring context override; Gemma runtime is pinned to %s", CONTEXT_TOKENS)
    return runtime_profile(prewarm=True)


def unload(model: str | None = None) -> None:
    """Compatibility no-op; Gemma stays resident for its configured keep-alive."""
    pinned_model(model)


def _payload(model: str, messages: Iterable[dict[str, Any]], num_predict: int,
              think: bool | None, extra_opts: dict | None,
              format_schema: dict | str | None = None,
              route: str = "generation") -> dict[str, Any]:
    opts = dict(BASE_OPTS)
    if extra_opts:
        opts.update(extra_opts)
    # Model/context/GPU policy is not overridable by agents.
    opts.pop("num_gpu", None)
    opts["num_ctx"] = (CLOUD_CONTEXT_TOKENS if route == "architect" else CONTEXT_TOKENS)
    opts["num_predict"] = int(num_predict)
    body: dict[str, Any] = {
        "model": _resolve_model(model, route),
        "messages": list(messages),
        "options": opts,
        "keep_alive": KEEP_ALIVE,
    }
    if think is not None:
        body["think"] = bool(think)
    if format_schema is not None:
        body["format"] = format_schema
    return body


def _messages(messages, system: str | None) -> list[dict[str, Any]]:
    # Gemma 4 supports a native system role and Ollama's renderer owns all model
    # control tokens.  Never hand-build tokenizer markers here.
    return ([{"role": "system", "content": system}] if system else []) + list(messages)


def _reject_truncation(data: dict[str, Any], label: str) -> None:
    reason = str(data.get("done_reason") or "")
    if reason == "length":
        message = data.get("message") or {}
        partial = str(message.get("content") or "")
        thinking = str(message.get("thinking") or "")
        tail_source = partial or thinking
        tail = " ".join(tail_source[-180:].split())
        raise LLMTruncatedError(
            f"{label} exhausted its {data.get('eval_count', '?')} output tokens; "
            f"partial content={len(partial)} chars, thinking={len(thinking)} chars, "
            f"stopped near {tail!r}; the incomplete result was rejected and will not be written."
        )


def chat(messages, *, model=None, num_predict=1024, think=THINK, system=None,
         extra_opts=None, timeout=300, format_schema: dict | str | None = None,
         route: str = "generation") -> str:
    """Non-streaming Gemma chat with optional Ollama JSON-schema output."""
    model = _resolve_model(model, route)
    body = _payload(model, _messages(messages, system), num_predict, think,
                    extra_opts, format_schema, route)
    body["stream"] = False
    data = _request("POST", "/api/chat", json=body, timeout=timeout).json()
    _track(data)
    label = "Nemotron Cloud response" if route == "architect" else "Gemma response"
    _reject_truncation(data, label)
    content = strip_think((data.get("message") or {}).get("content", ""))
    if not content:
        raise LLMError("Gemma returned no final content")
    return content


def stream_chat(messages, *, model=None, num_predict=4096, think=THINK,
                system=None, extra_opts=None, timeout=600,
                format_schema: dict | str | None = None,
                route: str = "generation"):
    """Yield final-answer tokens only and reject any length-stopped completion."""
    model = _resolve_model(model, route)
    body = _payload(model, _messages(messages, system), num_predict, think,
                    extra_opts, format_schema, route)
    body["stream"] = True
    response = _request("POST", "/api/chat", json=body, stream=True, timeout=timeout)
    usage: dict[str, Any] = {}
    for line in response.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        token = (chunk.get("message") or {}).get("content", "") or ""
        if token:
            yield token
        if chunk.get("done"):
            usage = chunk
            break
    _track(usage)
    label = "Nemotron Cloud streamed response" if route == "architect" else "Gemma streamed response"
    _reject_truncation(usage, label)


def stream_capture(messages, *, model=None, num_predict=4096, think=THINK,
                   system=None, extra_opts=None, timeout=600,
                   format_schema: dict | str | None = None,
                   route: str = "generation") -> tuple[str, str]:
    """Return ``(content, thinking)`` for the bounded hard-repair path."""
    model = _resolve_model(model, route)
    body = _payload(model, _messages(messages, system), num_predict, think,
                    extra_opts, format_schema, route)
    body["stream"] = True
    response = _request("POST", "/api/chat", json=body, stream=True, timeout=timeout)
    content, thinking, usage = "", "", {}
    for line in response.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        message = chunk.get("message") or {}
        content += message.get("content", "") or ""
        thinking += message.get("thinking", "") or ""
        if chunk.get("done"):
            usage = chunk
            break
    _track(usage)
    label = "Nemotron Cloud repair response" if route == "architect" else "Gemma repair response"
    _reject_truncation(usage, label)
    return strip_think(content), thinking
