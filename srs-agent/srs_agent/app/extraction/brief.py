"""Merge raw idea + all extracted sources into one normalized brief."""
from __future__ import annotations

import re
from typing import Any


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_brief(raw_idea: str, sources: list[dict[str, Any]]) -> str:
    """Combine the typed idea with text from PDF/image/voice sources."""
    parts: list[str] = []
    idea = _clean(raw_idea or "")
    if idea:
        parts.append(f"USER IDEA:\n{idea}")
    for src in sources:
        text = _clean(src.get("text", ""))
        if not text:
            continue
        mode = src.get("mode", "source").upper()
        fname = src.get("filename") or ""
        header = f"{mode} SOURCE" + (f" ({fname})" if fname else "")
        parts.append(f"{header}:\n{text}")
    return "\n\n---\n\n".join(parts).strip()
