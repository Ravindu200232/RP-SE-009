"""Tool definitions and the registry the model is offered.

A tool declares its own JSON Schema, its risk level and its handler. The
registry serialises those to the provider's native `tools[]` and validates
arguments before a handler ever runs, so a hallucinated parameter becomes an
observation the model can correct rather than a Python traceback.

The validator is deliberately small. Only required/type/enum matter here, and
pulling in a full JSON Schema library to check three things would be a
dependency nobody asked for.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from ..errors import ToolError
from ..policy import MODERATE


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    risk: str = MODERATE
    summarize: Callable | None = None
    # Whether running this tool can change the project, and so invalidates
    # evidence recorded at an earlier revision.
    mutates: bool = False
    # Offered during a read-only review pass.
    review_safe: bool = False

    def summary(self, args: dict) -> str:
        if self.summarize:
            try:
                return str(self.summarize(args))
            except Exception:  # noqa: BLE001 - a display helper cannot fail a call
                pass
        first = next(iter((args or {}).values()), "")
        text = " ".join(str(first).split())
        return text[:60] + "…" if len(text) > 60 else text


class Registry:
    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}

    def add(self, tool: Tool) -> "Registry":
        if tool.name in self.tools:
            raise ToolError(f"Duplicate tool: {tool.name}")
        self.tools[tool.name] = tool
        return self

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def has(self, name: str) -> bool:
        return name in self.tools

    def names(self) -> list[str]:
        return list(self.tools)

    def subset(self, keep) -> "Registry":
        out = Registry()
        for name in keep:
            if name in self.tools:
                out.tools[name] = self.tools[name]
        return out

    def schemas(self, excluded: dict | None = None) -> list[dict]:
        """Native `tools[]` for the provider, minus anything currently withheld."""
        excluded = excluded or {}
        return [{
            "type": "function",
            "function": {"name": tool.name, "description": tool.description,
                         "parameters": tool.parameters},
        } for tool in self.tools.values() if tool.name not in excluded]

    def validate(self, name: str, args: dict) -> dict:
        """Coerce and check arguments, or raise with a usable correction."""
        tool = self.get(name)
        if not tool:
            raise ToolError(f'Unknown tool "{name}".')
        schema = tool.parameters or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        args = args if isinstance(args, dict) else {}
        out, errors = {}, []

        for key in required:
            value = args.get(key)
            if value is None or (isinstance(value, str) and not value.strip() and key != "content"):
                errors.append(f'missing required parameter "{key}"')

        for key, value in args.items():
            spec = properties.get(key)
            if not spec:
                out[key] = value      # tolerate extras rather than failing the step
                continue
            coerced = _coerce(value, spec.get("type"))
            if coerced is _MISSING:
                errors.append(f'parameter "{key}" should be {spec.get("type")}, '
                              f"got {_type_name(value)}")
                continue
            if spec.get("enum") and coerced not in spec["enum"]:
                errors.append(f'parameter "{key}" must be one of: {", ".join(map(str, spec["enum"]))}')
                continue
            out[key] = coerced

        if errors:
            usage = f' Expected: {name}({", ".join(properties)}).' if properties else ""
            raise ToolError("; ".join(errors) + "." + usage)

        for key, spec in properties.items():
            if key not in out and "default" in spec:
                out[key] = spec["default"]
        return out


class _Missing:
    pass


_MISSING = _Missing()


def _coerce(value, kind):
    if not kind or kind == "any":
        return value
    if kind == "string":
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return _MISSING
    if kind in ("number", "integer"):
        if value is None or isinstance(value, bool):
            return _MISSING
        try:
            number = float(value)
        except (TypeError, ValueError):
            return _MISSING
        if kind == "integer":
            return int(number) if number.is_integer() else _MISSING
        return number
    if kind == "boolean":
        if isinstance(value, bool):
            return value
        if value in ("true", "True", 1):
            return True
        if value in ("false", "False", 0):
            return False
        return _MISSING
    if kind == "array":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Small models sometimes send a JSON array as a string.
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (TypeError, ValueError):
                pass
            return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
        return _MISSING
    if kind == "object":
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except (TypeError, ValueError):
                pass
        return _MISSING
    return value


def _type_name(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


@dataclass
class ToolContext:
    """Everything a handler is allowed to reach."""

    sandbox: object
    config: object
    events: object
    memory: object
    processes: object
    browser: object = None
    # Asking the person watching, and knowing when the run has been called off
    # while a question is still on screen.
    approvals: object = None
    cancel: object = None
    state: dict = field(default_factory=dict)
