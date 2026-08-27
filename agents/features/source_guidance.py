"""Shared feature prompts and small deterministic media-intent guard."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


PROMPT_FILE = Path(__file__).with_name("feature_prompt.md")


@lru_cache(maxsize=None)
def feature_prompt(name: str, *, foundation: bool = False) -> str:
    """Load one named contract; keep a safe fallback for packaged installs."""
    try:
        text = PROMPT_FILE.read_text("utf-8")
        marker = str(name or "").strip().upper()
        match = re.search(
            rf"<!--\s*{re.escape(marker)}\s*-->(.*?)<!--\s*/{re.escape(marker)}\s*-->",
            text, re.S)
        body = match.group(1).strip() if match else ""
        if foundation and marker != "FOUNDATION":
            base = feature_prompt("FOUNDATION")
            body = f"{base}\n\n{body}" if base else body
        if body:
            return body
    except OSError:
        pass
    return "Inspect current source and evidence before changing only the requested behavior."


def render_feature_prompt(name: str, **values) -> str:
    """Render explicit double-brace placeholders without template evaluation."""
    text = feature_prompt(name)
    for key, value in values.items():
        text = text.replace("{{" + key.upper() + "}}", str(value or ""))
    return text


HUMAN_COMMENT_POLICY = feature_prompt("HUMAN_COMMENT")
FEATURE_IMAGE_POLICY = feature_prompt("FEATURE_IMAGE")


_IMAGE_INTENT_RE = re.compile(
    r"\b(?:image|images|photo|photos|picture|pictures|photograph|photographs|"
    r"banner\s+image|hero\s+image|background\s+image|thumbnail|cover\s+image|"
    r"illustration|visual\s+asset)\b",
    re.I,
)
_IMAGE_NEGATION_RE = re.compile(
    r"\b(?:no|without|remove|delete|hide|disable)\b[^.!;\n]{0,40}"
    r"\b(?:image|images|photo|photos|picture|pictures|thumbnail|illustration)s?\b",
    re.I,
)
_IMAGE_ADD_RE = re.compile(
    r"\b(?:add|include|generate|create|draw|use|put|insert|replace)\b[^.!;\n]{0,40}"
    r"\b(?:image|images|photo|photos|picture|pictures|thumbnail|illustration)s?\b",
    re.I,
)


def feature_image_requested(text: str) -> bool:
    """True when a feature explicitly asks to add/use generated visual media."""
    value = " ".join(str(text or "").split())
    if not value:
        return False
    if _IMAGE_NEGATION_RE.search(value) and not _IMAGE_ADD_RE.search(value):
        return False
    return bool(_IMAGE_INTENT_RE.search(value))


def feature_image_prompt(text: str) -> str:
    """Return the extra feature contract only when visual generation was asked for."""
    return FEATURE_IMAGE_POLICY if feature_image_requested(text) else ""


__all__ = [
    "FEATURE_IMAGE_POLICY",
    "HUMAN_COMMENT_POLICY",
    "feature_prompt",
    "render_feature_prompt",
    "feature_image_prompt",
    "feature_image_requested",
]
