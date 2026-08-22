from __future__ import annotations

from typing import Any

SESSIONS: dict[str, dict[str, Any]] = {}
TEMPLATE_CACHE: dict[str, Any] | None = None
DATASET_CACHE: list[dict[str, str]] | None = None
