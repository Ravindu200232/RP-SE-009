"""The builder agent: plans, designs, builds and verifies one application.

A Python port of the AgentX engine, with the interaction modes removed and its
deep verification profile moved to where it pays - the unit and end-to-end
suites - rather than being a picker on the build itself.

    from builder_agent import BuilderAgent, Config
    agent = BuilderAgent(Config(workspace="./app", model="qwen2.5-coder:14b"))
    outcome = agent.run("build a hotel booking site")
"""
from .agent import BuilderAgent
from .config import (BUILD_QUALITY, VERIFY_QUALITY, Config, Quality, Stack,
                     detect_stack, stack_for, STACKS)
from .errors import AbortError, AgentError, ConfigError, SecurityError, ToolError
from .events import Events
from .evidence import Evidence
from .llm import OllamaClient, Router, load_settings, save_settings

__all__ = [
    "BuilderAgent", "Config", "Quality", "Stack", "STACKS", "Events", "Evidence",
    "OllamaClient", "Router", "BUILD_QUALITY", "VERIFY_QUALITY",
    "detect_stack", "stack_for", "load_settings", "save_settings",
    "AgentError", "ConfigError", "ToolError", "SecurityError", "AbortError",
]

__version__ = "1.0.0"
