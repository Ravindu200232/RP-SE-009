"""The tool set the model is offered.

One registry, assembled once. A review pass gets a strict read-only subset:
review reads a change and says what is wrong with it, and a tool that can write
or reach the network has no business in a pass nobody approved changes for.
"""
from __future__ import annotations

from .base import Registry, Tool, ToolContext
from . import files, knowledge, plan, search, setup, terminal

__all__ = ["Registry", "Tool", "ToolContext", "build_registry", "review_registry"]


def build_registry() -> Registry:
    registry = Registry()
    # Builder gets code and project tools only. QA composes its own test and
    # browser tool families on top of this registry.
    for module in (files, search, terminal, knowledge, plan, setup):
        module.register(registry)
    return registry


def review_registry(registry: Registry) -> Registry:
    return registry.subset([name for name, tool in registry.tools.items() if tool.review_safe])
