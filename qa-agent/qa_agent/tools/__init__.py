"""QA-only tool families composed with Builder's code-authoring tools."""
from builder_agent.tools import build_registry as build_code_registry

from . import browser, verify


def build_registry():
    """Return code-authoring tools extended only for a QA run."""
    registry = build_code_registry()
    verify.register(registry)
    browser.register(registry)
    return registry


__all__ = ["build_registry"]
