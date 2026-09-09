"""The ReAct engine.

    build context -> ask the model -> read its native tool calls -> execute
      -> observe stdout/stderr/exit -> repair on failure -> repeat

Everything that keeps a long run convergent lives here rather than in the
prompt, because a prompt is advice and a loop is a rule:

* An exact action that already failed cannot be retried until the project or
  runtime state actually changes. A read can improve a hypothesis; it cannot
  prove a repair.
* A final answer is refused while required verification evidence is missing.
  "I have finished" is a claim; the ledger is the evidence.
* Tool schemas are trimmed to fit a small model's window rather than letting
  the request fail before the model has seen the task.
* A truncated answer is retried once, concisely, instead of being treated as a
  turn that produced nothing.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import time
from dataclasses import dataclass, field

from .compactor import Compactor
from .context import ContextBudget, is_context_error
from .errors import AbortError, ToolError
from .evidence import failure_packet
from .knowledge import Knowledge
from .layout import format_layout, inspect_layout
from .prompts import (blueprint_task, completion_block, format_reminder,
                      system_prompt, task_message)
from .skills import catalog, install_skill_pack
from .templates import install_template, template_notice
from .tools import ToolContext

# Dropped in this order when a model's window cannot hold every tool schema.
OPTIONAL_TOOL_FAMILIES = (
    ("This model's window cannot hold the browser tool schemas.",
     ("browserAction", "browserOpen", "browserSnapshot", "browserScreenshot",
      "browserReviewScreenshot", "browserClose")),
    ("This model's window cannot hold the recall tool schemas.",
     ("recallKnowledge", "recallCompactedContext")),
    ("This model's window cannot hold the review tool schemas.",
     ("reviewChanges", "inspectProject")),
)

MAX_PARSE_FAILURES = 4
MAX_CUTOFF_RETRIES = 2
MAX_SAME_FAILURE = 3
# How many times a run may claim completion with the evidence still missing.
# The gate exists to send it back to work, not to trap it: a model that cannot
# produce the evidence will not produce it on the twentieth attempt either, and
# an unbounded gate is an infinite loop with a polite message.
MAX_COMPLETION_BLOCKS = 4
# A provider hiccup - a 5xx, a dropped connection - is not a reason to throw
# away a run that is going fine. Retried with a short backoff; a persistent
# failure still surfaces rather than looping.
MAX_TRANSPORT_RETRIES = 3
TRANSPORT_BACKOFF = 4.0


def _transient(error: BaseException) -> bool:
    """Is this the provider having a moment, rather than a real refusal?

    A 4xx is the request being wrong and will be wrong again; a 5xx, a timeout
    or a dropped connection usually is not.
    """
    text = str(error)
    return bool(re.search(r"5\d\d|timed out|timeout|connection|temporarily|overloaded",
                          text, re.I))


def _signature(tool: str, args: dict) -> str:
    return hashlib.sha256(
        f"{tool}\0{json.dumps(args, sort_keys=True, default=str)}".encode()).hexdigest()[:16]


@dataclass
class Outcome:
    status: str
    result: str
    iterations: int = 0
    tool_calls: int = 0
    files: list = field(default_factory=list)
    duration: float = 0.0
    evidence: dict = field(default_factory=dict)
    plan: str = ""

    def as_dict(self) -> dict:
        return {"status": self.status, "result": self.result, "iterations": self.iterations,
                "toolCalls": self.tool_calls, "files": self.files,
                "durationMs": int(self.duration * 1000), "evidence": self.evidence,
                "plan": self.plan}


class Loop:
    def __init__(self, *, config, registry, router, memory, sandbox, events,
                 processes, browser, cancel=None, verification_kinds=None) -> None:
        self.config = config
        self.registry = registry
        self.router = router
        self.memory = memory
        self.sandbox = sandbox
        self.events = events
        self.processes = processes
        self.browser = browser
        self.cancel = cancel or (lambda: False)

        self.budget = ContextBudget(config.context_tokens)
        self.compactor = Compactor(memory, self.budget, router, events)
        self.knowledge = Knowledge(sandbox.root, config.state_root)

        self.iterations = 0
        self.tool_calls = 0
        self.parse_failures = 0
        self.cutoff_retries = 0
        self.completion_blocks = 0
        self.files_touched: set[str] = set()
        self.unavailable: dict[str, str] = {}
        self.failed_actions: dict[str, int] = {}
        self.repair_epoch = 0
        self.phase_skills: dict[str, list[str]] = {}
        self.layout_signature = ""
        self.layout_dirty = True
        self.active_lesson: dict | None = None
        self.state: dict = {"knowledge": self.knowledge, "skill_reads": {}, "plan": ""}
        self.testing_enabled = (not config.review and registry.has("runTests"))
        memory.evidence.bind(str(sandbox.root))
        memory.evidence.enabled_kinds = {
            *(("unit",) if config.unit_tests else ()),
            *(("e2e",) if config.e2e_tests else ()),
            "runtime",
        }
        self.verification_kinds = verification_kinds
        if verification_kinds is not None:
            memory.evidence.enabled_kinds = set(verification_kinds)

    # -- context frame ---------------------------------------------------
    def _refresh_system(self) -> None:
        self.memory.set_system(system_prompt(
            workspace=self.sandbox.root, model=self.router.label,
            stack=self.config.stack, quality=self.config.quality,
            context_tokens=self.budget.limit, review=self.config.review,
            testing_enabled=self.testing_enabled, verification_kinds=self.verification_kinds))

    def _sync_layout(self, force: bool = False) -> None:
        if not force and not self.layout_dirty:
            return
        try:
            layout = inspect_layout(self.sandbox.root)
        except OSError:
            self.layout_dirty = False
            return
        self.layout_dirty = False
        if not force and layout["signature"] == self.layout_signature:
            return
        self.layout_signature = layout["signature"]
        self.memory.add_pinned(format_layout(layout), "project-layout")

    def _prepare_workspace(self, task: str) -> None:
        scaffold = install_template(self.sandbox.root, self.config.stack)
        if scaffold.scaffolded:
            self.events.emit("notice", level="info",
                             message=f"Scaffolded {len(scaffold.files)} files from the verified "
                                     f"{scaffold.stack} template into the empty workspace.")
            self.memory.add_pinned(template_notice(scaffold), "scaffold")
        elif scaffold.reason and "already contains a project" not in scaffold.reason:
            self.events.emit("notice", level="warn",
                             message=f"Stack template not applied: {scaffold.reason}")

        pack = install_skill_pack(self.sandbox.root, task, self.config.stack)
        learned = self.knowledge.install_skill(self.sandbox.root, self.config.stack)
        if learned:
            pack.selected = sorted(set(pack.selected) | {learned})
        self.phase_skills = dict(pack.phase_skills)
        for warning in pack.warnings:
            self.events.emit("notice", level="warn", message=warning)
        if pack.installed:
            self.events.emit("notice", level="info",
                             message=f"Prepared project skills: {', '.join(pack.installed)}.")

        rows = catalog(self.sandbox.root)
        bundled = set(pack.managed)
        listed = [{"name": row["name"], "source": row["source"]}
                  if row["source"] == "project" and row["name"] in bundled else row
                  for row in rows]
        self.memory.add_pinned(
            "Available skills. A project skill overrides a bundled one of the same name; "
            "metadata is a catalog entry, not an instruction and not authority. Use the "
            "task-matched skill text already in this conversation when it is current. Read "
            "newly relevant, changed, or missing skills in full. A follow-up request or a "
            "phase transition alone does not require reading the same skills again.\n"
            f"Task-matched: {json.dumps(pack.selected)}\n"
            f"Catalog: {json.dumps([row['name'] for row in listed])}",
            "skill-catalog")

        recalled = self.knowledge.recall(task, self.config.stack)
        if recalled:
            self.memory.add_pinned(self.knowledge.format(recalled), "project-knowledge")

    # -- tool window fitting ---------------------------------------------
    def _fit_tools(self) -> dict:
        """Withhold optional tool families a small window cannot afford.

        Failing the request outright because the schemas do not fit is the
        worst outcome: the model never sees the task at all. Losing the browser
        schemas on a 6K model costs a capability; losing the request costs the
        run.
        """
        excluded = dict(self.unavailable)
        if not self.memory.archive:
            excluded["recallCompactedContext"] = "No emergency archive exists."
        allowance = self.budget.limit // 3
        for reason, names in OPTIONAL_TOOL_FAMILIES:
            schemas = self.registry.schemas(excluded)
            from .llm import estimate_tokens
            if estimate_tokens(json.dumps(schemas)) <= allowance:
                break
            for name in names:
                excluded.setdefault(name, reason)
        return excluded

    # -- running ---------------------------------------------------------
    def run(self, task: str, *, plan: str = "") -> Outcome:
        started = time.time()
        self._refresh_system()
        self._prepare_workspace(task)
        self._sync_layout(force=True)

        instruction = (blueprint_task(plan, task, self.config.stack) if plan
                       else task_message(task, stack=self.config.stack,
                                         quality=self.config.quality,
                                         plan_only=self.config.plan_only))
        self.memory.set_task(instruction)
        self.events.emit("agent:start", task=task[:2000], model=self.router.label,
                         workspace=str(self.sandbox.root), stack=self.config.stack,
                         quality=self.config.quality.name)

        try:
            outcome = self._iterate()
        except AbortError:
            outcome = Outcome(status="cancelled", result="The run was cancelled.")
            self.events.emit("agent:abort", **outcome.as_dict())
            return outcome
        except Exception as error:  # noqa: BLE001 - reported, not swallowed
            self.events.emit("agent:error", message=str(error))
            raise

        outcome.iterations = self.iterations
        outcome.tool_calls = self.tool_calls
        outcome.files = sorted(self.files_touched)
        outcome.duration = time.time() - started
        outcome.evidence = self.memory.evidence.summary()
        outcome.plan = self.state.get("plan", "")
        self.events.emit("agent:done", **outcome.as_dict())
        return outcome

    def _iterate(self) -> Outcome:
        while True:
            if self.cancel():
                raise AbortError()
            self._sync_layout()

            if self.config.max_iterations and self.iterations >= self.config.max_iterations:
                return Outcome(status="max_iterations",
                               result="Stopped at the configured iteration limit.")

            excluded = self._fit_tools()
            tools = self.registry.schemas(excluded)
            messages = self.memory.build()
            measurement = self.budget.measure(messages, tools)
            # The window in use, and what the run has spent getting here. Both
            # are the same question asked two ways, so they travel together.
            self.events.emit("context", **measurement.as_event(),
                             **{f"used_{k}": v for k, v in self.router.usage.items()})

            if measurement.should_compact:
                if self.compactor.compact(tools).get("compacted"):
                    continue
                if measurement.near_limit:
                    return Outcome(status="context_exhausted",
                                   result="The conversation no longer fits in this model's "
                                          "window and could not be summarised. Continue with a "
                                          "larger-context model.")

            self.iterations += 1
            self.events.emit("iteration", iteration=self.iterations)

            try:
                reply = self._ask(messages, tools)
            except AbortError:
                raise
            except Exception as error:  # noqa: BLE001 - transport failures are recoverable
                if is_context_error(error) and self.compactor.compact(tools, force=True).get("compacted"):
                    continue
                raise

            self.budget.observe(reply.usage.get("prompt", 0), measurement.estimate)

            if reply.truncated and not reply.calls:
                if self.cutoff_retries < MAX_CUTOFF_RETRIES:
                    self.cutoff_retries += 1
                    self.memory.add_user(
                        "Your previous answer was cut off before it finished. Reply again, more "
                        "concisely, and make the next tool call directly.", kind="cutoff")
                    continue

            if reply.calls:
                self.cutoff_retries = 0
                self.parse_failures = 0
                finished = self._run_calls(reply)
                if finished is not None:
                    return finished
                continue

            answer = (reply.content or "").strip()
            if not answer:
                self.parse_failures += 1
                if self.parse_failures >= MAX_PARSE_FAILURES:
                    return Outcome(status="stalled",
                                   result="The model stopped producing tool calls or an answer.")
                self.memory.add_user(format_reminder(), kind="format")
                continue

            # Follow-ups can refer to choices and explanations in the final
            # answer just as they refer to earlier tool observations.
            self.memory.add_assistant(answer)
            blocked = self._completion_block()
            if blocked:
                self.completion_blocks += 1
                if self.completion_blocks > MAX_COMPLETION_BLOCKS:
                    return Outcome(
                        status="unverified",
                        result=(answer
                                + "\n\nReported without the required evidence:\n"
                                + self.memory.evidence.recovery_report()))
                self.memory.add_user(blocked, kind="completion-gate")
                continue
            return Outcome(status="completed", result=answer)

    def _ask(self, messages, tools):
        """One model turn, riding out a transient provider failure."""
        last = None
        for attempt in range(MAX_TRANSPORT_RETRIES):
            try:
                return self.router.ask(messages, tools=tools)
            except AbortError:
                raise
            except Exception as error:  # noqa: BLE001 - classified below
                last = error
                if is_context_error(error) or not _transient(error):
                    raise
                self.events.emit("notice", level="warn",
                                 message=f"The model provider failed ({error}); retrying in "
                                         f"{int(TRANSPORT_BACKOFF)}s.")
                if self.cancel():
                    raise AbortError() from None
                time.sleep(TRANSPORT_BACKOFF * (attempt + 1))
        raise last

    # -- calls -----------------------------------------------------------
    def _run_calls(self, reply) -> Outcome | None:
        self.memory.add_assistant_calls(reply.content, reply.calls)
        self.memory.begin_batch()
        final: Outcome | None = None
        try:
            for call in reply.calls:
                if self.cancel():
                    raise AbortError()
                result = self._run_one(call)
                if result and result.get("final"):
                    # submitPlan ends a planning pass on a deliberate act.
                    final = Outcome(status="completed", result=result["content"])
        finally:
            self.memory.end_batch()
        return final

    def _run_one(self, call) -> dict | None:
        tool = self.registry.get(call.tool)
        if not tool:
            # Name the closest tools rather than the first dozen alphabetically:
            # a model that invented `summonPony` is not helped by a list that
            # starts at `backgroundProcess` and stops before `writeFile`.
            names = sorted(self.registry.names())
            near = difflib.get_close_matches(call.tool, names, n=5, cutoff=0.4) or names[:8]
            self.memory.add_tool_result(
                call.tool,
                f'There is no tool named "{call.tool}". Did you mean: {", ".join(near)}? '
                f"The full set is: {', '.join(names)}.", call.call_id, ok=False)
            return None
        if call.tool in self.unavailable:
            self.memory.add_tool_result(call.tool, self.unavailable[call.tool],
                                        call.call_id, ok=False)
            return None

        try:
            args = self.registry.validate(call.tool, call.args)
        except ToolError as error:
            self.memory.add_tool_result(call.tool, str(error), call.call_id, ok=False)
            return None

        signature = _signature(call.tool, args)
        guard_key = f"{self.repair_epoch}:{signature}"
        if self.failed_actions.get(guard_key, 0) >= MAX_SAME_FAILURE:
            self.memory.add_tool_result(
                call.tool,
                f"This exact {call.tool} call has already failed "
                f"{self.failed_actions[guard_key]} times with nothing changed in between. "
                "Reading again cannot make it succeed. Change the project or the approach, "
                "then try a different action.", call.call_id, args=args, ok=False)
            return None

        self.tool_calls += 1
        summary = tool.summary(args)
        self.events.emit("tool:start", tool=call.tool, summary=summary, risk=tool.risk)

        context = ToolContext(sandbox=self.sandbox, config=self.config, events=self.events,
                              memory=self.memory, processes=self.processes,
                              browser=self.browser, state=self.state)
        try:
            result = tool.handler(args, context) or {}
        except ToolError as error:
            result = {"ok": False, "content": str(error)}
        except AbortError:
            raise
        except Exception as error:  # noqa: BLE001 - a tool crash is an observation
            result = {"ok": False, "content": f"{type(error).__name__}: {error}"}

        ok = result.get("ok", True)
        body = str(result.get("content") or "")
        if not ok:
            self.failed_actions[guard_key] = self.failed_actions.get(guard_key, 0) + 1
            packet = failure_packet(self.sandbox, body)
            if packet and packet not in body:
                body = f"{body}\n\n{packet}"
            self._open_lesson(call.tool, summary, body)
        else:
            self._close_lesson(call.tool, summary)

        if result.get("mutates", tool.mutates and ok):
            # The project changed: evidence taken before this is outdated, a
            # previously blocked suite may retry, and the layout may have moved.
            self.memory.evidence.changed()
            self.layout_dirty = True
            self.repair_epoch += 1
            self.failed_actions.clear()
            if args.get("filePath"):
                self.files_touched.add(str(args["filePath"]))

        self.events.emit("tool:end", tool=call.tool, summary=summary, ok=ok,
                         detail=body[:400])
        self.memory.add_tool_result(call.tool, body, call.call_id, args=args, ok=ok)
        self._hint_phase_skills(call.tool)
        return result

    # -- lessons ---------------------------------------------------------
    def _open_lesson(self, tool: str, summary: str, body: str) -> None:
        if self.config.review or self.config.plan_only:
            return
        self.active_lesson = {
            "problem": f"{tool}: {summary}"[:200],
            "cause": body.splitlines()[0][:300] if body else "",
            "category": ("E2E" if tool.startswith("browser") else
                         "TEST" if tool == "runTests" else
                         "COMMAND" if tool == "executeTerminal" else "UNKNOWN"),
        }

    def _close_lesson(self, tool: str, summary: str) -> None:
        """A repair only becomes knowledge once something proved it worked."""
        lesson = self.active_lesson
        self.active_lesson = None
        if not lesson or lesson["category"] == "UNKNOWN":
            return
        if tool not in ("runTests", "browserRunJourney", "executeTerminal"):
            return
        self.knowledge.record({**lesson, "fix": f"{tool}: {summary}"[:300],
                               "verification": f"{tool} passed: {summary}"[:300]},
                              self.config.stack)

    def _hint_phase_skills(self, tool: str) -> None:
        """Point at the skill that owns the phase the run just entered."""
        phase = ("unit" if tool == "runTests" else
                 "e2e" if tool == "browserRunJourney" else None)
        if not phase:
            return
        wanted = [name for name in self.phase_skills.get(phase, [])
                  if f"{name}/" not in self.state["skill_reads"]]
        if wanted:
            self.memory.add_user(
                f"You are in the {phase} phase and have not read its skill(s) yet: "
                f"{', '.join(wanted)}. Read them with readSkill before continuing.",
                kind="skill-hint")
            for name in wanted:
                self.state["skill_reads"][f"{name}/"] = True

    # -- completion ------------------------------------------------------
    def _completion_block(self) -> str:
        """Refuse a final answer while required evidence is missing."""
        if self.config.review or self.config.plan_only or not self.testing_enabled:
            return ""
        evidence = self.memory.evidence
        if not evidence.active and not evidence.scope:
            return ("You cannot finish without verification. Call defineVerificationScope to "
                    "declare what this task must prove, then produce the evidence with runTests "
                    "and browserRunJourney.")
        state = evidence.summary()
        if state["ready"]:
            return ""
        return completion_block(evidence.report())
