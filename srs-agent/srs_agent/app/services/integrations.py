"""Interview integration choices. Credentials never enter prompts or transcripts."""
from __future__ import annotations

import json
import re

from ..config import REPO_ROOT
from . import storage

KINDS = ("notifications", "payments", "image-uploads")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


def questions() -> list:
    root = REPO_ROOT / "builder-agent" / "builder_agent" / "assets" / "skills"
    backup = REPO_ROOT / "builder-agent" / "builder_agent" / "assets" / "_skills-backup"
    rows = []
    for name in KINDS:
        target = root / name / "setup.json"
        if not target.is_file():
            target = backup / name / "setup.json"
        if target.is_file():
            try:
                body = json.loads(target.read_text(encoding="utf-8"))
                rows.append({**body, "id": name})
            except Exception:
                pass
    return rows


def save(project_id: str, answers: list) -> list:
    catalog = {item["id"]: item for item in questions()}
    root = storage.project_dir(project_id)
    path = root / ".env.local"
    existing = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                existing[key] = value
    metadata, values = [], {}
    for answer in answers:
        question = catalog.get(answer.get("id"))
        if not question:
            raise ValueError("Unknown integration")
        choice = next((item for item in question.get("choices", []) if item["id"] == answer.get("choice")), None)
        if not choice:
            raise ValueError("Choose an available integration provider")
        fields = (question.get("fields") or []) + (choice.get("fields") or [])
        supplied = answer.get("values") or {}
        configured = []
        for field in fields:
            key = field["key"]
            if not ENV_NAME.fullmatch(key):
                raise ValueError("Invalid credential field declaration")
            value = str(supplied.get(key) or "")
            if value:
                if any(char in value for char in ("\r", "\n", "\0")) or len(value) > 8192:
                    raise ValueError("Credential value contains invalid characters or is too long")
                values[key] = value
            if value or existing.get(key):
                configured.append(key)
        metadata.append({"id": question["id"], "provider": choice["id"], "label": choice["label"],
                         "configured": configured, "required": [field["key"] for field in fields if field.get("required", True)]})
    # Whatever was answered is saved; nothing is required. The specification's
    # business is whether the product needs to take money or send mail, not
    # which company does it - the provider is settled at build time, by the
    # plugin the user picked, and an interview that insisted on all three was
    # asking two questions it had no way to act on.
    if len(set(item["id"] for item in metadata)) != len(metadata):
        raise ValueError("Each integration may only be answered once")
    # JSON quoting is compatible with dotenv and preserves # and whitespace in keys.
    existing.update({key: json.dumps(value, ensure_ascii=False) for key, value in values.items()})
    storage.write_text(path, "".join(f"{key}={value}\n" for key, value in existing.items()))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    storage.write_text(root / ".gitignore", ".env*\n!.env.example\n")
    return metadata
