"""Validated deployment interview answers; credentials never belong here."""
from __future__ import annotations

import re

FIELDS = {
    "project_name", "repository_name", "repository_visibility", "readme", "commit_message",
    "vercel_scope", "netlify_team", "netlify_site_id", "aws_instance_type",
    "azure_resource_group", "azure_location", "azure_sku", "azure_plan",
}
IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")


def validate_answers(raw: dict | None) -> dict:
    if raw is not None and not isinstance(raw, dict):
        raise ValueError("Deployment answers must be an object")
    answers = {key: str(value).strip() for key, value in (raw or {}).items() if key in FIELDS and value != ""}
    for key, value in answers.items():
        limit = 20000 if key == "readme" else 300 if key == "commit_message" else 100
        if len(value) > limit or "\x00" in value:
            raise ValueError(f"Invalid deployment answer: {key}")
        if key not in {"readme", "commit_message"} and not IDENTIFIER.fullmatch(value):
            raise ValueError(f"Use letters, digits, dots, underscores or hyphens for {key}")
    if answers.get("repository_visibility", "private") not in {"private", "public"}:
        raise ValueError("Repository visibility must be private or public")
    if answers.get("aws_instance_type", "t3.micro") not in {"t3.micro", "t3.small", "t3.medium", "t4g.micro", "t4g.small"}:
        raise ValueError("Unsupported AWS instance size")
    if answers.get("azure_sku", "B1") not in {"F1", "B1", "B2", "B3", "S1", "P1v3"}:
        raise ValueError("Unsupported Azure plan size")
    return answers
