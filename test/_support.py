"""Shared import setup for the repository-level tests."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

for source_root in (ROOT, ROOT / "srs-agent", ROOT / "deployment-agent"):
    value = str(source_root)
    if value not in sys.path:
        sys.path.insert(0, value)
