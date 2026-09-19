"""Failure kinds the engine distinguishes when it decides what to do next.

The loop reacts differently to each: a `ToolError` is an observation the model
can repair from, a `SecurityError` is a refusal it must plan around, and an
`AbortError` ends the run. Collapsing them into one exception type would make
"the model wrote a bad path" indistinguishable from "the user pressed stop".
"""
from __future__ import annotations


class AgentError(Exception):
    """Base class so a caller can catch everything the engine raises."""


class ConfigError(AgentError):
    """The run was asked for something it cannot be configured to do."""


class ToolError(AgentError):
    """A tool refused or failed. Returned to the model as an observation."""


class SecurityError(AgentError):
    """A path or command crossed a boundary the engine will not cross."""

    def __init__(self, message: str, **detail):
        super().__init__(message)
        self.detail = detail


class AbortError(AgentError):
    """The run was cancelled. Never reported as a failure of the work."""
