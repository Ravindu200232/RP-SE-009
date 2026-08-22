from __future__ import annotations

import csv
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from .config import DATASET_CANDIDATES, DOMAIN_KEYWORDS, PdfReader, QUESTION_DEFAULTS, TEMPLATE_CANDIDATES
from . import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def truncate(text: str, limit: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def has_answer_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(str(item or "").strip() for item in value)
    if isinstance(value, dict):
        return any(has_answer_value(item) for item in value.values())
    return bool(str(value or "").strip())


def normalize_project_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:80] if text else "Untitled App"


def guess_project_name(text: str) -> str:
    sentence = re.split(r"[.!?\n]", normalize_project_name(text), maxsplit=1)[0].strip()
    return sentence or "Untitled App"


def resolve_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if str(path).strip() and path.exists():
            return path
    return None


def load_template() -> dict[str, Any]:
    if state.TEMPLATE_CACHE is not None:
        return deepcopy(state.TEMPLATE_CACHE)
    path = resolve_existing(TEMPLATE_CANDIDATES)
    if path:
        try:
            state.TEMPLATE_CACHE = json.loads(path.read_text(encoding="utf-8"))
            return deepcopy(state.TEMPLATE_CACHE)
        except Exception:
            pass
    state.TEMPLATE_CACHE = {
        "document_type": "Software Requirements Specification",
        "standard": "IEEE SRS",
        "metadata": {},
        "sections": {},
        "appendices": {},
        "services": [],
    }
    return deepcopy(state.TEMPLATE_CACHE)


def load_dataset() -> list[dict[str, str]]:
    if state.DATASET_CACHE is not None:
        return state.DATASET_CACHE
    path = resolve_existing(DATASET_CANDIDATES)
    if not path:
        state.DATASET_CACHE = []
        return state.DATASET_CACHE
    rows: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                rows.append({key: str(value or "") for key, value in row.items()})
                if index >= 999:
                    break
    except Exception:
        rows = []
    state.DATASET_CACHE = rows
    return state.DATASET_CACHE


def infer_domain(text: str) -> str:
    text = str(text or "").lower()
    best_domain, best_score = "General", 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_domain, best_score = domain, score
    return best_domain


def get_dataset_examples(domain: str) -> list[dict[str, str]]:
    rows = load_dataset()
    matches = [row for row in rows if (row.get("domain") or "").lower() == domain.lower()]
    pool = matches or rows
    return [{"domain": row.get("domain", domain), "summary": truncate(row.get("summary") or row.get("training_text") or "", 220)} for row in pool[:2]]


def strip_json_fence(text: str) -> str:
    return re.sub(r"^```(?:json)?|```$", "", str(text or "").strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = strip_json_fence(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start < 0 or end <= start:
        return {}
    payload = json.loads(cleaned[start:end])
    return payload if isinstance(payload, dict) else {}


def safe_decode(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return payload.decode(encoding)
        except Exception:
            continue
    return ""


def answer_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def extract_pdf_text(payload: bytes) -> str:
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(BytesIO(payload))
        return truncate("\n".join((page.extract_text() or "") for page in reader.pages[:6]), 1800)
    except Exception:
        return ""


def summarize_upload(file: UploadFile, payload: bytes) -> dict[str, Any]:
    name = file.filename or "unknown"
    suffix = Path(name).suffix.lower()
    kind = "file"
    excerpt = ""
    summary = f"Registered file '{name}'."
    if (file.content_type or "").startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        try:
            with Image.open(BytesIO(payload)) as image:
                kind = "image"
                summary = f"Uploaded image '{name}' ({image.width}x{image.height})."
                excerpt = f"Image dimensions: {image.width}x{image.height}"
        except Exception:
            pass
    elif suffix == ".pdf" or file.content_type == "application/pdf":
        kind = "pdf"
        excerpt = extract_pdf_text(payload)
        summary = f"Uploaded PDF '{name}' for requirements context."
    elif (file.content_type or "").startswith("audio/") or suffix in {".mp3", ".wav", ".m4a", ".ogg", ".webm"}:
        kind = "audio"
        summary = f"Uploaded voice note '{name}'."
    elif suffix in {".txt", ".md", ".json", ".csv"} or (file.content_type or "").startswith("text/"):
        kind = "text"
        excerpt = truncate(safe_decode(payload), 1800)
        summary = f"Uploaded text document '{name}'."
    return {"asset_id": str(uuid4()), "filename": name, "kind": kind, "summary": summary, "excerpt": excerpt}


def to_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or list(fallback or [])
    text = str(value or "").strip()
    if not text:
        return list(fallback or [])
    return [part.strip(" -*\t") for part in re.split(r"\r?\n+|[,;]+", text) if part.strip(" -*\t")]


def build_template_outline(node: Any, path: str = "root", depth: int = 0, max_depth: int = 3) -> list[str]:
    if depth > max_depth:
        return []
    if isinstance(node, dict):
        lines = [path]
        for key, value in node.items():
            lines.extend(build_template_outline(value, f"{path}.{key}", depth + 1, max_depth))
        return lines
    if isinstance(node, list):
        if not node:
            return [f"{path}[]"]
        return [f"{path}[]", *build_template_outline(node[0], f"{path}[0]", depth + 1, max_depth)]
    return [f"{path}: {str(node)}"]


def template_excerpt(limit: int = 5000) -> str:
    outline = "\n".join(build_template_outline(load_template(), "template", 0, 4))
    return outline if len(outline) <= limit else outline[: limit - 3] + "..."
