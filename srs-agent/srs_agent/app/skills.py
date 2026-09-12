"""SRS Agent Skills System — modular guidance for specification and visual modeling."""
from __future__ import annotations

import json
import re
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"
SKILL_ROOT = ASSET_ROOT / "skills"
MANIFEST_PATH = SKILL_ROOT / "skill-pack.json"


def _normalise(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def read_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.is_file():
        return {}
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        entries = {}
        for s in data.get("skills", []):
            name = s.get("name")
            if name:
                entries[name] = s
        return entries
    except Exception:
        return {}


def select_srs_skills(task_text: str = "") -> list[str]:
    manifest = read_manifest()
    if not manifest:
        return []

    norm_text = _normalise(task_text)
    selected: set[str] = set()

    # Core and visualization skills are always selected by default
    for name, meta in manifest.items():
        if meta.get("category") in ("core", "visualization", "synchronization"):
            selected.add(name)

    # Contextual matching
    for name, meta in manifest.items():
        matches = meta.get("match", [])
        for kw in matches:
            if _normalise(kw) in norm_text:
                selected.add(name)
                for req in meta.get("requires", []):
                    if req in manifest:
                        selected.add(req)
                break

    return sorted(selected)


def get_srs_skill_text(name: str) -> str:
    skill_file = SKILL_ROOT / name / "SKILL.md"
    if not skill_file.is_file():
        return ""
    try:
        raw = skill_file.read_text(encoding="utf-8")
        # Strip frontmatter if present
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return raw.strip()
    except Exception:
        return ""


def get_active_skills_guidance(task_text: str = "") -> str:
    selected = select_srs_skills(task_text)
    if not selected:
        return ""

    blocks = []
    for s_name in selected:
        content = get_srs_skill_text(s_name)
        if content:
            blocks.append(f"### Skill: {s_name}\n{content}")

    if not blocks:
        return ""

    return "\n\n---\n## ACTIVE SRS SKILLS GUIDANCE\n" + "\n\n".join(blocks) + "\n---\n"
