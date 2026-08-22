from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .common import truncate
from .config import (
    ChatOllama,
    ChatPromptTemplate,
    DEEPSEEK_MODEL,
    LANGCHAIN_AVAILABLE,
    LANGCHAIN_OLLAMA_AVAILABLE,
    LANGGRAPH_AVAILABLE,
    OLLAMA_CHAT_TIMEOUT_SECONDS,
    OLLAMA_URL,
    StrOutputParser,
)


def ollama_probe() -> dict[str, Any]:
    request = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "available": True,
            "url": OLLAMA_URL,
            "models": [item.get("name") for item in payload.get("models", []) if item.get("name")],
        }
    except Exception:
        return {"available": False, "url": OLLAMA_URL, "models": []}


def model_config() -> dict[str, Any]:
    return {
        "provider": "ollama",
        "ollama_url": OLLAMA_URL,
        "deepseek_model": DEEPSEEK_MODEL,
        "langchain_enabled": LANGCHAIN_AVAILABLE,
        "langchain_ollama_enabled": LANGCHAIN_OLLAMA_AVAILABLE,
        "langgraph_enabled": LANGGRAPH_AVAILABLE,
        "ollama": ollama_probe(),
    }


def call_ollama_text(prompt: str, *, system_prompt: str, temperature: float = 0.1) -> str:
    if LANGCHAIN_AVAILABLE and LANGCHAIN_OLLAMA_AVAILABLE:
        try:
            llm = ChatOllama(
                model=DEEPSEEK_MODEL,
                base_url=OLLAMA_URL,
                temperature=temperature,
                sync_client_kwargs={"timeout": OLLAMA_CHAT_TIMEOUT_SECONDS},
                async_client_kwargs={"timeout": OLLAMA_CHAT_TIMEOUT_SECONDS},
            )
            chain = (
                ChatPromptTemplate.from_messages(
                    [
                        ("system", system_prompt),
                        ("human", "{prompt}"),
                    ]
                )
                | llm
                | StrOutputParser()
            )
            return str(chain.invoke({"prompt": prompt})).strip()
        except Exception:
            pass

    payload = json.dumps(
        {
            "model": DEEPSEEK_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": temperature},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_CHAT_TIMEOUT_SECONDS) as response:
            content = json.loads(response.read().decode("utf-8"))
        return str(content.get("message", {}).get("content", "")).strip()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, Exception):
        return ""


def planner_name() -> str:
    if model_config()["ollama"]["available"]:
        return f"DeepSeek via Ollama ({DEEPSEEK_MODEL})"
    return "Heuristic IEEE planner"


def build_agent_message(session: dict[str, Any], mode: str) -> str:
    question_plan = session.get("question_plan") or {}
    question_count = len(question_plan.get("questions", []))
    fallback_messages = {
        "intake": (
            f"I mapped your idea against the IEEE SRS structure and prepared {question_count} short, user-friendly questions "
            "to fill the missing details."
        ),
        "update": "I refreshed the draft with your latest note and kept the remaining SRS questions simple and user-friendly.",
    }
    prompt = f"""Write a short assistant reply for an SRS intake workflow.

MODE: {mode}
PROJECT NAME: {session.get("project_name")}
ANALYSIS SUMMARY: {question_plan.get("summary") or session.get("analysis_summary") or ""}
QUESTION COUNT: {question_count}
LATEST USER MESSAGE: {truncate((session.get("messages") or [{}])[-1].get("content", ""), 400)}

RULES:
- Keep it to 1 or 2 sentences.
- Sound like an SRS analyst guiding the user.
- Mention IEEE-style requirement gathering naturally.
- Tell the user that no technical knowledge is needed.
- Do not use markdown.
- Do not mention internal tools unless you naturally say DeepSeek or Ollama once.
"""
    response = call_ollama_text(
        prompt,
        system_prompt="You are a concise product analyst helping a user complete an IEEE SRS interview.",
        temperature=0.25,
    )
    return response or fallback_messages.get(mode, fallback_messages["update"])
