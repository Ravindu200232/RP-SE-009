from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Repository root must come first so `backend.agent4` resolves
# to <repository>/backend/agent4 instead of backend/backend.
for path in (str(BACKEND), str(ROOT)):
    if path in sys.path:
        sys.path.remove(path)

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))