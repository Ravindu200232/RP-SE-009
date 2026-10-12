"""The studio's shared backend runtime."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The engine, and each agent, on the import path — so `from srs_agent import …` works however the server was started.
for folder in ("src", "srs-agent", "prototype-agent", "builder-agent",
               "qa-agent", "deploy-agent"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
