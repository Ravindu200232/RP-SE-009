"""
agents/llm.py — Central Ollama access for every Locode agent.

WHY THIS EXISTS
    Previously each agent called Ollama's /api/chat directly and never set
    `num_ctx`, so generation ran at Ollama's ~2-4K default context. Once we
    inject codebase context (models, API contract, sibling components) the
    prompt silently truncates and the model produces broken code. Routing every
    call through here guarantees a ~98K context window and a consistent thinking
    level on all stages.

USAGE
    from agents import llm
    text = llm.chat([{"role": "user", "content": "..."}], system=SYS)
    for tok in llm.stream_chat(msgs, num_predict=6144):
        emit(tok)
"""
import json
import logging
import os
import re
import time

import requests

log = logging.getLogger("llm")

OLLAMA_URL = "http://localhost:11434"

# ── Provider selection ─────────────────────────────────────────────────────────
# The whole engine routes LLM calls through this module. `LOCODE_PROVIDER` picks the backend:
#   "ollama" (default) → local Ollama /api/chat (gemma etc.)
#   "gemini"           → Google Gemini free API (native generateContent, OpenAI-key-free)
# Everything else in the engine is provider-agnostic — only the three public functions below branch.
PROVIDER = os.environ.get("LOCODE_PROVIDER", "ollama").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# One model drives every stage. Configurable per-call, but the whole pipeline
# is tuned for Gemma 4 12B. `gemma3:12b` is the documented fallback if the
# gemma4 tag has not been pulled yet.
GEN_MODEL = "gemma4:12b"
FALLBACK_MODEL = "gemma3:12b"

# First-pass repair runs on gemma (same model as generation → no VRAM swap), full-GPU.
REPAIR_MODEL = "gemma4:12b"
REPAIR_OPTS = {"num_gpu": 999, "num_ctx": 16384}

# Stubborn / remaining bugs escalate to a powerful CLOUD model — nemotron-3-super:cloud — with maximum
# context and thinking enabled (cloud → no local VRAM/speed limit, so give it the whole file + reasoning).
REMAINING_MODEL = "nemotron-3-super:cloud"
REMAINING_OPTS = {"num_ctx": 65536}   # cloud: max context, no num_gpu
REMAINING_THINK = "high"

# When the Gemini provider is active, every stage uses a Gemini model by default (overridable by env).
# `gemini-flash-latest` = Gemini 2.5 Flash: 1M context, strong at code, generous free tier.
if PROVIDER == "gemini":
    GEN_MODEL = os.environ.get("LOCODE_MODEL", "gemini-flash-latest")
    FALLBACK_MODEL = GEN_MODEL
    REPAIR_MODEL = GEN_MODEL
    REMAINING_MODEL = os.environ.get("LOCODE_HARD_MODEL", GEN_MODEL)

# Options sent on EVERY call. num_ctx is the headline fix — 98K as requested.
# NOTE: 98K KV-cache on a 12B model is VRAM-heavy. num_gpu:999 forces max GPU offload; if the
# machine can't hold the cache it spills to CPU and generation gets slow — tune num_ctx down then.
BASE_OPTS = {
    "num_ctx": 98304,      # ~98K context window (long full-stack codebase context)
    "temperature": 0.12,   # low temp → predictable code, fewer hallucinations
    "top_p": 0.9,
    "num_gpu": 999,        # force max GPU offload → full speed, never spill to CPU
}

# Gemma 4 thinking level. Kept LOW for code generation: less latency, fewer
# wasted tokens, still enough reasoning to wire a component correctly.
THINK = "low"

_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Optional token accounting hook (wired by server for the savings calculator).
_token_cb = None


def set_token_callback(fn):
    """Register a callback(prompt_tokens, completion_tokens) for usage tracking."""
    global _token_cb
    _token_cb = fn


def _track(resp_json: dict):
    if _token_cb and isinstance(resp_json, dict):
        try:
            _token_cb(resp_json.get("prompt_eval_count", 0),
                      resp_json.get("eval_count", 0))
        except Exception:
            pass


def log_config(model: str = None):
    """Log the outgoing Ollama options once at the start of a pipeline run."""
    log.info(
        "🧠 Ollama config → model=%s num_ctx=%s temp=%s top_p=%s think=%s",
        model or GEN_MODEL, BASE_OPTS["num_ctx"], BASE_OPTS["temperature"],
        BASE_OPTS["top_p"], THINK,
    )


def strip_think(text: str) -> str:
    """Remove any <think>...</think> block a model may embed in its content."""
    return _THINK_TAG.sub("", text or "").strip()


def unload(model: str):
    """Evict a model from VRAM (keep_alive=0) so the next model gets full GPU. Best-effort."""
    if PROVIDER != "ollama":
        return
    try:
        requests.post(f"{OLLAMA_URL}/api/generate",
                      json={"model": model, "keep_alive": 0}, timeout=30)
    except Exception:
        pass


def ensure_loaded(model: str, extra_opts: dict | None = None):
    """Warm a model into VRAM with the given options (so the first real call isn't a cold load)."""
    if PROVIDER != "ollama":
        return
    try:
        opts = dict(BASE_OPTS)
        if extra_opts:
            opts.update(extra_opts)
        requests.post(f"{OLLAMA_URL}/api/chat",
                      json={"model": model, "messages": [{"role": "user", "content": "ok"}],
                            "options": opts, "stream": False, "keep_alive": "10m"}, timeout=120)
    except Exception:
        pass


# ── Internals ────────────────────────────────────────────────────────────────

def _payload(model, messages, num_predict, think, extra_opts):
    opts = dict(BASE_OPTS)
    opts["num_predict"] = num_predict
    if extra_opts:
        opts.update(extra_opts)
    body = {"model": model, "messages": messages, "options": opts}
    if think is not None:
        body["think"] = think
    return body


def _think_ladder(think):
    """
    Ordered `think` values to try, most-desired first. If the model or the
    installed Ollama version rejects a thinking level we degrade gracefully:
    requested level → disabled → omit the field entirely.
    """
    ladder = []
    for v in (think, False, None):
        if v not in ladder:
            ladder.append(v)
    return ladder


def _is_think_error(txt: str) -> bool:
    t = (txt or "").lower()
    return "think" in t or "thinking" in t


# ── Gemini provider (native generateContent / streamGenerateContent) ───────────

def _gemini_body(messages, system, num_predict):
    """Map role/content messages → Gemini `contents`; system → `systemInstruction`; thinking OFF."""
    contents = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": BASE_OPTS["temperature"],
            "topP": BASE_OPTS["top_p"],
            "maxOutputTokens": max(int(num_predict), 2048),
            "thinkingConfig": {"thinkingBudget": 0},   # code gen — no reasoning tokens
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


# Free-tier RPM throttle: keep at least this many seconds between Gemini calls (≈ under 15 RPM).
GEMINI_MIN_INTERVAL = float(os.environ.get("GEMINI_MIN_INTERVAL", "5.0"))
_gemini_last = [0.0]


def _gemini_retry_delay(resp) -> float:
    """Gemini returns the retry hint in the error body (details[].retryDelay: '30s'), not a header."""
    try:
        for d in (resp.json().get("error", {}).get("details", []) or []):
            rd = d.get("retryDelay")
            if rd:
                return float(str(rd).rstrip("s"))
    except Exception:
        pass
    return 0.0


def _gemini_post(url, body, timeout, stream):
    """POST with a min-interval throttle + retry/backoff on 429 (free-tier rate limit)."""
    headers = {"Content-Type": "application/json", "X-goog-api-key": GEMINI_API_KEY}
    last = None
    for attempt in range(8):
        gap = GEMINI_MIN_INTERVAL - (time.time() - _gemini_last[0])
        if gap > 0:
            time.sleep(gap)
        _gemini_last[0] = time.time()
        resp = requests.post(url, headers=headers, json=body, timeout=timeout, stream=stream)
        if resp.status_code == 429:
            wait = _gemini_retry_delay(resp) or float(resp.headers.get("Retry-After", 0)) or min(2 ** attempt, 30)
            wait = min(max(wait, 2), 65)   # free-tier RPM resets per minute → wait up to ~65s
            log.warning("   gemini 429 — backing off %.0fs (attempt %d)", wait, attempt + 1)
            time.sleep(wait)
            last = resp
            continue
        resp.raise_for_status()
        return resp
    if last is not None:
        last.raise_for_status()
    raise RuntimeError("gemini: exhausted retries")


def _gemini_track(data):
    if _token_cb and isinstance(data, dict):
        u = data.get("usageMetadata", {}) or {}
        try:
            _token_cb(u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0))
        except Exception:
            pass


def _gemini_chat(model, messages, system, num_predict, timeout=120) -> str:
    url = f"{GEMINI_BASE}/{model}:generateContent"
    resp = _gemini_post(url, _gemini_body(messages, system, num_predict), timeout, stream=False)
    data = resp.json()
    _gemini_track(data)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except Exception:
        return ""


def _gemini_stream(model, messages, system, num_predict, timeout=300):
    url = f"{GEMINI_BASE}/{model}:streamGenerateContent?alt=sse"
    resp = _gemini_post(url, _gemini_body(messages, system, num_predict), timeout, stream=True)
    for raw in resp.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except Exception:
            continue
        for cand in chunk.get("candidates", []) or []:
            for p in (cand.get("content", {}) or {}).get("parts", []) or []:
                t = p.get("text", "")
                if t:
                    yield t
        if chunk.get("usageMetadata"):
            _gemini_track(chunk)


# ── Public API ───────────────────────────────────────────────────────────────

def chat(messages, *, model=None, num_predict=1024, think=THINK,
         system=None, extra_opts=None, timeout=120) -> str:
    """Non-streaming chat. Returns the assistant message content (think stripped)."""
    model = model or GEN_MODEL
    if PROVIDER == "gemini":
        return strip_think(_gemini_chat(model, list(messages), system, num_predict, timeout))
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    last_err = None
    for tv in _think_ladder(think):
        body = _payload(model, msgs, num_predict, tv, extra_opts)
        body["stream"] = False
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=timeout)
            if resp.status_code >= 400:
                if tv is not None and _is_think_error(resp.text):
                    last_err = resp.text[:200]
                    continue
                resp.raise_for_status()
            data = resp.json()
            _track(data)
            content = strip_think(data.get("message", {}).get("content", ""))
            # gemma4:12b in thinking mode spends the whole num_predict budget in the (separate)
            # thinking channel and answers with an EMPTY content — a 200 OK carrying nothing. The
            # ladder below only caught models that REJECT thinking, so the empty string flowed
            # straight through: the architect's spec "failed to parse" and every app silently fell
            # back to the generic `Entry` placeholder. An empty answer is a thinking failure too.
            if content.strip():
                return content
            if tv is None:
                return content          # last rung — nothing left to try
            last_err = f"empty content with think={tv!r}"
            log.warning("   chat returned empty content with think=%r — retrying without it", tv)
            continue
        except requests.RequestException as e:
            last_err = str(e)
            log.error("   chat error: %s", e)
            break
    raise RuntimeError(f"llm.chat failed: {last_err}")


def stream_chat(messages, *, model=None, num_predict=4096, think=THINK,
                system=None, extra_opts=None, timeout=300):
    """
    Streaming chat generator. Yields content token strings as they arrive.
    Thinking tokens (message.thinking) are never yielded — only the final answer.
    Retries with reduced `think` settings if the level is rejected.
    """
    model = model or GEN_MODEL
    if PROVIDER == "gemini":
        yield from _gemini_stream(model, list(messages), system, num_predict, timeout)
        return
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    last_err = None
    for tv in _think_ladder(think):
        body = _payload(model, msgs, num_predict, tv, extra_opts)
        body["stream"] = True
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=body,
                                 stream=True, timeout=timeout)
            if resp.status_code >= 400:
                txt = resp.text[:200]
                if tv is not None and _is_think_error(txt):
                    last_err = txt
                    log.warning("   think=%s rejected — retrying lower", tv)
                    continue
                resp.raise_for_status()
            usage = {}
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                tok = chunk.get("message", {}).get("content", "")
                if tok:
                    yield tok
                if chunk.get("done"):
                    usage = chunk
                    break
            _track(usage)
            return
        except requests.RequestException as e:
            last_err = str(e)
            log.error("   stream_chat error: %s", e)
            break
    raise RuntimeError(f"llm.stream_chat failed: {last_err}")


def stream_capture(messages, *, model=None, num_predict=4096, think=THINK,
                   system=None, extra_opts=None, timeout=600) -> tuple[str, str]:
    """Like stream_chat but RETURNS `(content, thinking)` — captures BOTH channels. For a repair with a
    thinking model (nemotron) whose real answer may land in `message.thinking` instead of `content`."""
    model = model or GEN_MODEL
    if PROVIDER == "gemini":
        text = "".join(_gemini_stream(model, list(messages), system, num_predict, timeout))
        return text, ""
    msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
    last_err = None
    for tv in _think_ladder(think):
        body = _payload(model, msgs, num_predict, tv, extra_opts)
        body["stream"] = True
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=body, stream=True, timeout=timeout)
            if resp.status_code >= 400:
                if tv is not None and _is_think_error(resp.text[:200]):
                    last_err = resp.text[:200]
                    continue
                resp.raise_for_status()
            content, thinking, usage = "", "", {}
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                m = chunk.get("message", {})
                content += m.get("content", "") or ""
                thinking += m.get("thinking", "") or ""
                if chunk.get("done"):
                    usage = chunk
                    break
            _track(usage)
            return content, thinking
        except requests.RequestException as e:
            last_err = str(e)
            log.error("   stream_capture error: %s", e)
            break
    raise RuntimeError(f"llm.stream_capture failed: {last_err}")
