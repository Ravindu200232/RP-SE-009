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

from .approvals import Approvals
from .browser import Browser
from .config import Config
from .design import apply_answer as apply_design_answer
from .design import choose as choose_design
from .design import design_contract_message, form_payload, write_design_skill
from .design import tokens as design_tokens
from .errors import AbortError, ConfigError
from .events import Events
from .llm import OllamaClient, Router
from .loop import Loop, Outcome
from .memory import Memory
from .processes import Processes
from .prompts import task_message
from .sandbox import Sandbox
from .tools import build_registry, review_registry

# How many times a rejected plan may be sent back before the build proceeds
# anyway. A plan nobody accepts after this many tries is not going to be
# accepted, and the alternative is a build that never starts.
MAX_PLAN_REVISIONS = 3

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
        # Only a surface that can actually answer turns these on; everywhere
        # else they resolve to the default immediately.
        self.approvals = Approvals(self.events, enabled=bool(config.extra.get("gates")),
                                   timeout=float(config.extra.get("gate_timeout", 300)))
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
        """Investigate the project, then write the plan the build executes.

        The plan is offered for review before anything is built. Nobody has to
        answer: the gate expires into "accept", because a plan is cheap to
        change now and the alternative is a build that never starts.
        """
        self.events.emit("phase", phase="plan", title="Planning", status="active")
        request = task

        for revision in range(MAX_PLAN_REVISIONS + 1):
            loop = self._loop(self.registry.subset(
                [name for name, tool in self.registry.tools.items()
                 if tool.review_safe or name in ("executeTerminal",)]),
                plan_only=True)
            outcome = loop.run(request)
            self.plan_text = loop.state.get("plan") or outcome.result

            answer = self.approvals.ask(
                "plan", {"plan": self.plan_text, "goal": task[:400],
                         "revision": revision, "maxRevisions": MAX_PLAN_REVISIONS},
                default={"decision": "accept"}, cancel=self.cancel)
            if answer.get("decision") != "revise" or revision >= MAX_PLAN_REVISIONS:
                break

            feedback = str(answer.get("feedback") or "").strip()
            self.events.emit("notice", level="info",
                             message=f"Revising the plan (round {revision + 2})"
                                     + (f": {feedback[:160]}" if feedback else "."))
            request = "\n".join([
                f"Revise the plan for this request:\n\n{task}", "",
                "The previous plan was sent back. What was asked for:",
                feedback or "(nothing specific - reconsider the approach yourself)", "",
                "Previous plan:", self.plan_text[:6000], "",
                "Produce a new plan that addresses this. Do not simply restate the old one.",
            ])

        self.events.emit("phase", phase="plan", title="Planning", status="done")
        return outcome

    def apply_design(self, task: str) -> dict | None:
        """Decide the look, offer it for adjustment, and write it as a contract."""
        if not wants_design(task):
            return None
        form = form_payload(task)
        answer = self.approvals.ask(
            "design", form, default={"decision": "apply"}, cancel=self.cancel)
        if answer.get("decision") == "skip":
            self.events.emit("notice", level="info",
                             message="Design contract skipped; the build will choose its own look.")
            return None

        selection = apply_design_answer(form["chosen"], answer.get("selection"))
        written = write_design_skill(self.sandbox.root, selection, goal=task[:300])
        self.design = written
        self.events.emit("phase", phase="design", title="Design system", status="done",
                         palette=selection["paletteName"], theme=selection["themeMode"])
        self.events.emit("design", **{
            "palette": selection["paletteName"], "mood": selection["mood"],
            "theme": selection["themeMode"], "font": selection["font"],
            "radius": selection["radius"], "density": selection["density"],
            "typeScale": selection["typeScale"], "path": written["path"],
            "tokens": design_tokens(selection["palette"], selection["themeMode"]),
            "summary": (f"{selection['paletteName']} - {selection['mood']} "
                        f"Default theme {selection['themeMode']}; {selection['font']} type, "
                        f"{selection['radius']} corners, {selection['density']} spacing."),
        })
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
        self.approvals.cancel_all()
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
