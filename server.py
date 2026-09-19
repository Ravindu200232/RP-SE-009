#!/usr/bin/env python3
"""Stable AgentForge backend entrypoint."""
from __future__ import annotations

import asyncio
import sys

import server_runtime as _runtime


if __name__ == "__main__":
    try:
        asyncio.run(_runtime.main())
    except KeyboardInterrupt:
        print("\n⛔ Stopped.")
        _runtime.RUNTIMES.close()
else:
    # Keep legacy imports pointed at the shared runtime.
    sys.modules[__name__] = _runtime
