"""Test fixtures: force offline LLM + in-memory store before importing app."""
import os

# Must be set BEFORE any app import (settings are cached at import time).
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:9")   # unreachable -> offline
os.environ.setdefault("MONGODB_URI", "mongodb://127.0.0.1:9/agentforge_test")
os.environ.setdefault("MONGODB_ALLOW_MEMORY_FALLBACK", "true")
os.environ.setdefault("LLM_ALLOW_OFFLINE_FALLBACK", "true")
os.environ.setdefault("MERMAID_CLI", "__none__")  # skip image rendering in tests

import pytest  # noqa: E402

from app.db import connect_store  # noqa: E402


@pytest.fixture(autouse=True)
async def _store():
    """Ensure the (in-memory) store is connected for every test."""
    await connect_store()
    yield
