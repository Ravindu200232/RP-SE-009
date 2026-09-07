"""One build, start to finish.

The session owns the durable pieces - workspace, memory, model, processes,
browser - across the passes a build is made of:

    plan  ->  design  ->  build  ->  verify

There is no approval between them. The engine used to stop twice: once for the
plan and once for a design questionnaire, each waiting on a human who, in a
studio build, is not there. Both are now decided and applied automatically, and
what the user gets instead of two dialogs is a plan and a design contract
written into the project where they can read and edit them.

What is deliberately kept is the refusal to *finish* without evidence. Skipping
an approval prompt is a convenience; skipping verification would be a lie.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from .browser import Browser
from .config import Config
from .design import choose as choose_design
from .design import design_contract_message, write_design_skill
from .errors import AbortError, ConfigError
from .events import Events
from .llm import OllamaClient, Router
from .loop import Loop, Outcome
from .memory import Memory
from .processes import Processes
from .prompts import task_message
from .sandbox import Sandbox
from .tools import build_registry, review_registry

# Work with no user interface: a design contract for a cron job is noise.
NON_UI_TERMS = ("cli", "command line", "cron", "worker", "script", "library",
                "migration", "seed script", "api only", "headless")
UI_TERMS = ("page", "pages", "screen", "ui", "ux", "component", "layout", "design",
            "dashboard", "form", "site", "website", "app", "application", "portal",
            "landing", "theme", "style", "styling", "responsive")


def wants_design(task: str) -> bool:
    text = f" {str(task or '').lower()} "
    if any(f" {term} " in text for term in NON_UI_TERMS):
        return False
    return any(f" {term} " in text for term in UI_TERMS)


class BuilderAgent:
    """The builder agent: plans, designs, builds and proves one application."""

    def __init__(self, config: Config, *, client=None, events: Events | None = None,
                 cancel=None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.config = config
        self.events = events or Events()
        self.cancel = cancel or (lambda: False)
        self.sandbox = Sandbox(config.workspace)
        self.memory = Memory(budget_tokens=config.context_tokens)
        self.processes = Processes(events=self.events)
        self.browser = Browser(events=self.events)
        self.client = client or OllamaClient(config.host or None)
        self.router = Router(self.client, config.model, config=config, events=self.events)
        self.registry = build_registry()
        self.plan_text = ""
        self.design: dict | None = None

        detected = self.router.context_window()
        if detected:
            self.config.context_tokens = detected
            self.memory.budget_tokens = detected

    # -- passes ----------------------------------------------------------
    def plan(self, task: str) -> Outcome:
        """Investigate the project, then write the plan the build executes."""
        self.events.emit("phase", phase="plan", title="Planning", status="active")
        loop = self._loop(self.registry.subset(
            [name for name, tool in self.registry.tools.items()
             if tool.review_safe or name in ("executeTerminal",)]),
            plan_only=True)
        outcome = loop.run(task)
        self.plan_text = loop.state.get("plan") or outcome.result
        self.events.emit("phase", phase="plan", title="Planning", status="done")
        return outcome

    def apply_design(self, task: str) -> dict | None:
        """Decide the look, and write it into the project as a contract."""
        if not wants_design(task):
            return None
        selection = choose_design(task)
        written = write_design_skill(self.sandbox.root, selection, goal=task[:300])
        self.design = written
        self.events.emit("phase", phase="design", title="Design system", status="done",
                         palette=selection["paletteName"], theme=selection["themeMode"])
        self.events.emit("notice", level="info",
                         message=f"Design contract: {selection['paletteName']} "
                                 f"({selection['themeMode']} default) written to {written['path']}.")
        return written

    def build(self, task: str, *, plan: str = "") -> Outcome:
        """Implement the plan and prove it works."""
        self.events.emit("phase", phase="build", title="Building", status="active")
        instruction = task
        if self.design:
            instruction = design_contract_message(self.design["selection"]) + "\n\n" + task
        loop = self._loop(self.registry)
        outcome = loop.run(instruction, plan=plan)
        self.events.emit("phase", phase="build", title="Building",
                         status="done" if outcome.status == "completed" else "error")
        return outcome

    def review(self, focus: str = "Review the current change set.") -> Outcome:
        """A read-only pass that reports defects and changes nothing."""
        loop = self._loop(review_registry(self.registry), review=True)
        return loop.run(focus)

    def run(self, task: str) -> Outcome:
        """The whole build: plan, design, implement, verify."""
        if not str(task or "").strip():
            raise ConfigError("A task description is required.")
        try:
            plan_outcome = self.plan(task)
            if plan_outcome.status not in ("completed",):
                # A planning pass that could not finish is not fatal: the build
                # can still proceed from the request itself, and saying so is
                # more useful than refusing to start.
                self.events.emit("notice", level="warn",
                                 message="Planning did not complete; building from the request "
                                         "directly.")
                self.plan_text = ""
            self.apply_design(task)
            return self.build(task, plan=self.plan_text)
        finally:
            self._finish()

    # -- plumbing --------------------------------------------------------
    def _loop(self, registry, *, plan_only: bool = False, review: bool = False) -> Loop:
        config = self.config
        if plan_only or review:
            from dataclasses import replace
            config = replace(config, plan_only=plan_only, review=review)
        return Loop(config=config, registry=registry, router=self.router, memory=self.memory,
                    sandbox=self.sandbox, events=self.events, processes=self.processes,
                    browser=self.browser, cancel=self.cancel)

    def _finish(self) -> None:
        """Leave services running for the preview; take everything else down."""
        self.memory.close_pending_tools(
            "The run ended before this tool reported a result. Verify the current state before "
            "retrying it.")
        self.processes.release_services()
        self.processes.stop_all(keep_services=True)
        self.browser.close()

    def dispose(self) -> None:
        self.processes.stop_all()
        self.browser.close()

    def snapshot(self) -> dict:
        return {
            "id": self.id, "model": self.router.label, "workspace": str(self.sandbox.root),
            "stack": self.config.stack, "quality": self.config.quality.name,
            "messages": len(self.memory), "compactions": self.memory.compactions,
            "usage": self.router.usage,
            "processes": [job.summary() for job in self.processes.list()],
            "evidence": self.memory.evidence.summary(),
            "plan": self.plan_text, "design": self.design,
        }
