"""Backward-compatible entrypoint for the input-driven Gemma Architect.

The historical RefinerAgent contained keyword classifiers, role presets, generic
entity fallbacks, and a fixed page formula. Those policies have intentionally
been removed; invalid architecture now fails instead of becoming a template.
"""
from __future__ import annotations

import json

from agents import llm
from agents.architect import ArchitectAgent


class RefinerAgent:
    """Compatibility wrapper used by the server and headless smoke harness."""

    def __init__(self, ollama_url=None, model=None):
        self.model = llm.pinned_architect_model(model or llm.ARCHITECT_MODEL)

    def refine(self, raw_idea: str) -> str:
        return json.dumps(ArchitectAgent(self.model).plan(raw_idea), ensure_ascii=False, indent=2)
