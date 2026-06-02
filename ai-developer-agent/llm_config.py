"""
Central LLM configuration for the multi-agent pipeline.

WHY THIS FILE EXISTS
--------------------
The #1 reason qwen2.5-coder:7b produced truncated / one-line JSON is that the
stock ChatOllama context window is tiny (~2048 tokens). Your SRS + backend
schemas + the system prompt easily blow past that, so the model silently runs
out of room and stops mid-generation.

`get_llm()` sets:
  - num_ctx     : a big enough context window for SRS + schemas + prompt
  - num_predict : -1 = keep generating until the JSON is fully closed (no cap)

Tune these in ONE place. If you hit RAM/VRAM limits, lower num_ctx to 8192.
qwen2.5-coder:7b supports up to 32768 if you need more for a huge SRS.
"""

import json
import re

from langchain_ollama import ChatOllama

MODEL_NAME = "qwen2.5-coder:7b"
DEFAULT_NUM_CTX = 16384      # room for SRS + backend schemas + system prompt
DEFAULT_NUM_PREDICT = -1     # -1 = generate until the model closes the JSON


def get_llm(temperature: float = 0.0,
            num_ctx: int = DEFAULT_NUM_CTX,
            num_predict: int = DEFAULT_NUM_PREDICT) -> ChatOllama:
    """Return a configured local model. format='json' constrains output to
    valid JSON so the stream stops cleanly when the object is complete."""
    return ChatOllama(
        model=MODEL_NAME,
        format="json",
        temperature=temperature,
        num_ctx=num_ctx,
        num_predict=num_predict,
    )


def extract_json(text: str):
    """Best-effort JSON loader.

    format='json' should already guarantee valid JSON, but this is a cheap
    safety net: it strips stray markdown fences and, if needed, falls back to
    the outermost {...} block so a tiny bit of extra text never crashes a run.
    """
    if not text:
        raise ValueError("empty model response")

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def stream_to_string(chain, payload: dict) -> str:
    """Stream a chain to stdout (so you keep your live console view) and also
    return the full accumulated string."""
    out = ""
    for chunk in chain.stream(payload):
        token = chunk.content
        print(token, end="", flush=True)
        out += token
    return out
