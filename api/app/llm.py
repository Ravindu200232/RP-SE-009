from __future__ import annotations

import os
from typing import Any

try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except Exception:
    ChatOllama = None
    OLLAMA_AVAILABLE = False

DEFAULT_MODEL = os.environ.get("AGENT2_MODEL", "qwen2.5:14b")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def build_llm(model: str | None = None, temperature: float = 0.3, **kwargs: Any):
    if not OLLAMA_AVAILABLE:
        raise RuntimeError(
            "langchain-ollama is not installed. Install with: pip install langchain-ollama"
        )
    return ChatOllama(
        model=model or DEFAULT_MODEL,
        base_url=DEFAULT_HOST,
        temperature=temperature,
        num_ctx=8192,
        **kwargs,
    )


def llm_invoke(llm, messages) -> str:
    result = llm.invoke(messages)
    content = getattr(result, "content", result)
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
