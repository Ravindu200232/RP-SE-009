"""
AgentForge's QA layer: tests written while the app generates, then run and fixed.

The build pipeline is untouched. `QASession` wraps one callback the architect
already fires, so the phase loop in `agents/architect.py` needs no edit at all,
and the test author runs on a second model call that never reads or writes the
build conversation.

The repair half lives in `agents/bugfixer.py`, not here, because it is a
bug-fixing agent like the others and shares their shape — the user asked for
exactly that split.
"""
from .author import UnitTestAuthor
from .e2e import E2EAgent
from .debugger import AgenticE2EDebugger, DebugNotebook
from .flows import (Scenario, Selector, Step, parse_scenario, parse_selector,
                    to_playwright_js)
from .harness import CONFIG, DEV_DEPS, TestHarness
from .runner import VitestRunner, classify
from .session import QASession
from .snapshot import FileSnapshot
from .spec import (MAX_PER_PHASE, MAX_PER_PROJECT, QAReport, TestFailure,
                   TestTarget, select_targets, test_path_for)

__all__ = [
    "QASession", "UnitTestAuthor", "TestHarness", "VitestRunner", "FileSnapshot",
    "E2EAgent", "AgenticE2EDebugger", "DebugNotebook", "Scenario", "Selector", "Step",
    "TestTarget", "TestFailure", "QAReport",
    "select_targets", "test_path_for", "classify",
    "parse_scenario", "parse_selector", "to_playwright_js",
    "MAX_PER_PHASE", "MAX_PER_PROJECT", "CONFIG", "DEV_DEPS",
]
