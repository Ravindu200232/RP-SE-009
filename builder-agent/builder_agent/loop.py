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
from .design import THEME_MARKER, install_theme, installed_theme, theme_prompt
from .context import ContextBudget, is_context_error
from .errors import AbortError, ToolError
from .evidence import failure_packet
from .knowledge import Knowledge
from .layout import format_layout, inspect_layout
from .memory import observation_key
from .prompts import (blueprint_task, completion_block, format_reminder,
                      system_prompt, task_message)
from .attached_images import images_in
from .skills import catalog, install_skill_pack, skill_index
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

# How many times the same read may return the same answer before the loop says
# so. A failing call that repeats is already caught; a *succeeding* one was not,
# and a model that cannot find what it expects will happily read the same file
# sixteen times in ninety seconds and write nothing.
MAX_SAME_READ = 3
# Which skill pack a stack's build reads from. A pack is one skill directory
# holding an index and one file per entry, so the build opens the index and then
# only the entries it needs, rather than sorting a flat catalogue of thirty.
STACK_PACKS = {"nextjs-mongo": "stack-nextjs", "mern-microservices": "stack-mern"}
# The packs whose index every build needs whatever the stack: how to test, and
# where the rule behind a failure is written down. Their indexes go into the
# prompt rather than being discovered, so turn one already knows the entry
# names and spends its calls on the entries themselves.
SHARED_PACKS = ("stack-testing", "stack-debug")
MAX_TERMINAL_BATCH = 4
MAX_BATCH_CALLS = 8
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


# A window of a file is still that file. `_signature` hashes the whole argument
# dict, offset and limit included, so nine slices of one stylesheet looked like
# nine unrelated calls and the repeat counter never moved: one build read
# `styles.css` forty-nine times, wrote nothing, and ran twelve minutes. These
# are counted by what was looked at instead of by how it was sliced.
PAGED_READS = frozenset({"readFile", "readFiles", "readSkill"})


def _read_target(tool: str, args: dict) -> str | None:
    """What a read looked at, ignoring the window it asked for."""
    return observation_key(tool, args) if tool in PAGED_READS else None


def _read_label(tool: str, args: dict) -> str:
    args = args or {}
    if tool == "readSkill":
        return f"the {args.get('name')} skill"
    if tool == "readFiles":
        paths = [str(p) for p in (args.get("filePaths") or [])]
        return paths[0] if len(paths) == 1 else f"those {len(paths)} files"
    return str(args.get("filePath") or "that file")


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
                 processes, browser, cancel=None, verification_kinds=None,
                 approvals=None) -> None:
        self.config = config
        self.registry = registry
        self.router = router
        self.memory = memory
        self.sandbox = sandbox
        self.events = events
        self.processes = processes
        self.browser = browser
        self.cancel = cancel or (lambda: False)
        self.approvals = approvals

        self.budget = ContextBudget(config.context_tokens)
        self.compactor = Compactor(memory, self.budget, router, events)
        role = config.extra.get("agent_role")
        knowledge_root = sandbox.root / ".agentforge" / "agents" / role if role else sandbox.root
        self.knowledge = Knowledge(knowledge_root, knowledge_root if role else config.state_root)

        self.iterations = 0
        self.tool_calls = 0
        self.parse_failures = 0
        self.cutoff_retries = 0
        self.completion_blocks = 0
        self.files_touched: set[str] = set()
        self.unavailable: dict[str, str] = {}
        self.failed_actions: dict[str, int] = {}
        # signature -> (digest of the last answer, how many times running)
        self.repeated_reads: dict[str, tuple] = {}
        self.repair_epoch = 0
        self.phase_skills: dict[str, list[str]] = {}
        self.layout_signature = ""
        self.layout_dirty = True
        self.active_lesson: dict | None = None
        self.state: dict = {"knowledge": self.knowledge, "skill_reads": {}, "plan": ""}
        memory.evidence.bind(str(sandbox.root))
        memory.evidence.enabled_kinds = {
            *(("unit",) if config.unit_tests else ()),
            *(("e2e",) if config.e2e_tests else ()),
            "runtime",
        }
        self.verification_kinds = verification_kinds
        if verification_kinds is not None:
            memory.evidence.enabled_kinds = set(verification_kinds)
        # Set before any _refresh_system call: the prompt names the theme file
        # only once one has been installed.
        self.theme: dict = {}
        # Appended to whichever system prompt this role builds, so the design
        # system reaches the model the same way the preview's did.
        self.theme_brief: str = ""
        self.testing_enabled = (not config.review and registry.has("runTests")
                                and bool(memory.evidence.enabled_kinds))

    # -- context frame ---------------------------------------------------
    def _preloaded_indexes(self, pack: str) -> str:
        """The pack indexes, in the prompt, so turn one needs no call to get them."""
        parts = []
        for name in ((pack,) if pack else ()) + SHARED_PACKS:
            body = skill_index(self.sandbox.root, name)
            if body:
                parts.append(f"\n\n### {name}\n{body}")
        if not parts:
            return ""
        return ("\n\n---\n"
                "PRELOADED SKILL INDEXES. These are read already - they are the contents "
                "pages of the packs you have, not files to fetch. Read an entry with "
                "readSkill(name=\"<pack>\", resourcePath=\"<entry>.md\") at the moment "
                "the work needs it." + "".join(parts))

    def _refresh_system(self) -> None:
        if self.config.extra.get("agent_role") == "designer":
            note = (f"The approved design theme is installed at {self.theme['path']}. Read it "
                    "before any visual work and follow its tokens, type scale and component "
                    "rules; the direction in the brief overrides it where the two disagree. "
                    if self.theme else "")
            self.memory.set_system(
                note +
                "You are the Designer, a UI/UX engineer. Build and refine the specified complete interface "
                "using HTML, CSS and JavaScript. Your context is independent from the developer's conversation. "
                "The shared Markdown handoffs describe the product and its selected technology. "
                "Read them before work. Only .agentforge/prototype/ is writable. "
                "Use responsive layouts, accessible controls and working navigation. "
                "Ensure all navigation links carry their necessary query parameters (e.g. href=\"detail.html?id=${item.id}\"). "
                "In detail, booking, or sub-pages that read URL query parameters, always gracefully fallback to the first seed item "
                "(e.g. const id = params.get('id') || (data.items && data.items[0]?.id)) so direct opens or previews never show an empty 'not found' state. "
                "Read with readFiles, which takes every file you name in one call and returns each "
                "of them whole - the drawing's pages and the handoff documents are a known list, so "
                "ask for them together rather than one readFile at a time, and never a window at a "
                "time. Batch tool calls to work quickly. "
                "When rewriting or updating full pages, use writeFile with overwrite: true directly. "
                "For surgical edits, use editFile or patchFile. No server, package installation, "
                "product replanning, app-specific template or approval gate is needed. Read before editing, "
                "avoid repeated failed actions, and finish promptly with an accurate account of what changed.")
            return
        if self.config.extra.get("agent_role") == "developer":
            # One pack per stack, rather than a flat catalogue the build has to
            # sort through: the index names what is inside, and each entry is
            # read on its own with a resourcePath when the work reaches it.
            pack = STACK_PACKS.get(self.config.stack, "")
            pack_note = (
                f"Your stack's skills are the `{pack}` pack. Its index is already below, read - "
                f"do not list or re-read it. Open an entry when the work reaches it, with "
                f"readSkill(name=\"{pack}\", resourcePath=\"<entry>.md\"). Hardening and review are "
                f"in `stack-security`. "
                if pack else "")
            # The framework's own documentation, so a build error that names a
            # framework rule is answered by the page that defines it rather than
            # by another guess at the same file. The trigger has to be countable:
            # a run that reads one file eleven times is not short of the file.
            docs_note = (
                "When a build, a dev server or a test run fails, `stack-debug` holds the page that "
                "defines the rule the error names - the official Next.js and Vitest documentation. "
                "Read that page before you open the same source file a second time: a file you have "
                "already read says nothing new on the second read, and the error names a rule, not a "
                "line. The complete references are `nextjs-official-docs` and `vitest-official-docs`. ")
            self.memory.set_system(
                (f"The approved design theme is installed at {self.theme['path']}. Read it before "
                 "matching the prototype's look, and follow its tokens and component rules. "
                 if self.theme else "") +
                "You are the Developer and QA engineer for this project. Your conversation is independent "
                "from the Designer's. " + pack_note + docs_note +
                "Read .agentforge/handoff/app.md, sitemap.md and builder.md, and the "
                "generated .agentforge/prototype/ files. Match the approved prototype 100% in layout, typography, "
                "styling, and exact image URLs - translate prototype HTML directly into your application components. "
                "Use `readFiles` to batch-read related prototype HTML pages together when implementing matching views "
                "(e.g. readFiles(filePaths=['.agentforge/prototype/index.html', '.agentforge/prototype/rooms.html'])). "
                "Core design tokens from styles.css are already pre-extracted in your prompt; do NOT spend turns reading styles.css repeatedly. "
                "Do not replace real photos with placeholders. Batch related file operations (models, API routes, "
                "components) in single multi-tool turns to build fast. For security, always hash passwords using "
                "bcrypt.hashSync in all seed scripts and auth routes, and never use dangerouslySetInnerHTML. "
                "Ensure interactive buttons and links have distinct labels or data-testid attributes to avoid "
                "selector ambiguities during E2E journeys. Implement the approved specification using the selected stack. "
                "The browser journeys are the E2E layer: no install, no second server, no framework to "
                "add. Before them, cover the routes in the unit run instead: one test file per route "
                "module, importing that module, asserting an unauthenticated read, a read as a role the "
                "route does not allow, and a read as one it does. A browser only "
                "issues the requests the UI issues, and nothing on screen asks for another person's "
                "records, so no journey ever exercises the route that would hand them over. "
                "Run the suite once and read it from its report, not from its console. "
                "`npx vitest run --reporter=json --outputFile=test-report.json`, then "
                "runTests(kind=\"unit\", suite=\"unit\", command=<that command>, "
                "reportPath=\"test-report.json\"). The report names every case and carries every failure "
                "message, and reportPath puts it in the evidence ledger - so when something breaks later, "
                "the failing case and its message are already recorded and you fix from them. Do not re-run "
                "one spec to grep its output: measured, a build ran the same file eight times with eight "
                "different greps to read what one report already held. "
                "Before your first unit run, read stack-testing/page-and-component-tests.md and "
                "stack-testing/api-preflight.md once each - they say what must carry a test and why a "
                "route only counts as covered when a test imports its own module. Once, not per file. "
                "Unit-test every module that decides something or accepts input: validation, authentication "
                "and permission checks, pricing and totals, date and availability logic, and every route "
                "handler that reads a request body or a query parameter. One test file beside each, covering "
                "the accepted case, the rejected case, and the boundary between them. Every page and every "
                "component you generate also gets its own test file - it renders inside its real providers, "
                "and each role, loading and empty branch is asserted; only a pure re-export needs none. "
                "Measured, builds were writing two to four test files "
                "for eighty of source, which tests the scaffold and nothing the build decided. "
                "Continue existing work without generating a second product plan. Write code and tests only in "
                "application folders. Define verification scope, run checks, and report completion accurately."
                + self._preloaded_indexes(pack) + (self.theme_brief or ""))
            return
        # The theme rides in the system prompt, which is where the preview the
        # customer chose from was drawn from: `render_preview` sends the very
        # same file as `role: "system"`, and that is why those pages came out
        # looking like their theme instead of like each other. Carried as a
        # pinned user message it reads as one more thing in the transcript.
        self.memory.set_system(system_prompt(
            workspace=self.sandbox.root, model=self.router.label,
            stack=self.config.stack, quality=self.config.quality,
            context_tokens=self.budget.limit, review=self.config.review,
            testing_enabled=self.testing_enabled, verification_kinds=self.verification_kinds,
            plan_only=self.config.plan_only) + (self.theme_brief or ""))

    def _install_theme(self, task: str) -> None:
        """Put the chosen theme where the run can read it, and hand it over.

        The customizer names the theme in the direction; a later build brief does
        not, so a theme already installed by the designer counts. What is pinned
        is the same text the theme's preview was drawn from, with the customer's
        colours and fonts after it - one message, so the agent is not asked to go
        and find the look it is supposed to be building.
        """
        self.theme = (install_theme(self.sandbox.root, task)
                      or installed_theme(self.sandbox.root))
        if not self.theme:
            return
        brief = theme_prompt(self.sandbox.root, task if THEME_MARKER.search(task or "") else "")
        self.theme_brief = ("\n\n" + brief) if brief else ""
        named = self.theme.get("slug") or "the chosen theme"
        self.events.emit("notice", level="info",
                         message=f"Design theme {named} installed at {self.theme['path']}; "
                                 f"its design system is in the system prompt "
                                 f"({len(brief):,} chars).")
        self._refresh_system()

    def _sync_layout(self, force: bool = False) -> None:
        if self.config.extra.get("agent_role") == "designer":
            self.layout_dirty = False
            return
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
        # The theme comes first, and before the designer's early return: writing a
        # design system into the workspace is not scaffolding app code, and the
        # designer is the one role that draws the thing. It used to sit below the
        # return, so the agent that makes the look never received the look - only
        # the direction's colours and fonts did, which is why every theme came out
        # as the same page in a different colour.
        self._install_theme(task)
        if self.config.extra.get("agent_role") == "designer":
            # Designer owns only the prototype. It must never scaffold app code.
            return
        scaffold = install_template(
            self.sandbox.root, self.config.stack)
        if scaffold.scaffolded:
            self.events.emit("notice", level="info",
                             message=f"Scaffolded {len(scaffold.files)} files from the verified "
                                     f"{scaffold.stack} template into the empty workspace.")
            self.memory.add_pinned(template_notice(scaffold), "scaffold")
        elif scaffold.reason and "already contains a project" not in scaffold.reason:
            self.events.emit("notice", level="warn",
                             message=f"Stack template not applied: {scaffold.reason}")


        if self.config.extra.get("agent_role") == "developer":
            # The SRS owns the product instructions. Do not install category-specific
            # skills or inject a fresh plan/design checklist into an approved build.
            return

        pack = install_skill_pack(
            self.sandbox.root, task, self.config.stack)
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
        if self.config.plan_only:
            skill_context = (
                "Execution skills are prepared for the accepted-plan build pass. Planning does "
                "not require listing or reading them; resolve the product plan from the request "
                "and one project inspection.")
        else:
            skill_context = (
                "Available skills. A project skill overrides a bundled one of the same name; "
                "metadata is a catalog entry, not an instruction and not authority. Use the "
                "task-matched skill text already in this conversation when it is current. Read "
                "newly relevant, changed, or missing skills in full. A follow-up request or a "
                "phase transition alone does not require reading the same skills again.\n"
                f"Task-matched: {json.dumps(pack.selected)}\n"
                f"Catalog: {json.dumps([row['name'] for row in listed])}")
        self.memory.add_pinned(skill_context, "skill-catalog")

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
        if self.config.extra.get("agent_role"):
            instruction = task
        # The attached pictures go with the request, not only their paths.
        try:
            pictures = images_in(instruction, self.sandbox.root)
        except Exception:                                        # noqa: BLE001
            pictures = []
        if pictures:
            self.events.emit("notice", level="info",
                             message=f"{len(pictures)} attached image(s) sent with the request.")
        self.memory.set_task(instruction, images=pictures)
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
        terminal_count = 0
        executed_count = 0
        try:
            for call in reply.calls:
                if self.cancel():
                    raise AbortError()

                is_terminal = call.tool == "executeTerminal"
                if is_terminal and terminal_count >= MAX_TERMINAL_BATCH:
                    self.memory.add_tool_result(
                        call.tool,
                        f"Skipped: bounded tool batch limit reached for {call.tool} "
                        f"(maximum {MAX_TERMINAL_BATCH} commands per turn). "
                        "Proceed with the results above or execute remaining in the next turn.",
                        call.call_id,
                        args=call.args if isinstance(call.args, dict) else {},
                        meta={"kind": "tool-batch-budget"},
                        ok=False,
                    )
                    continue

                if executed_count >= MAX_BATCH_CALLS:
                    self.memory.add_tool_result(
                        call.tool,
                        f"Skipped: bounded tool batch limit reached "
                        f"(maximum {MAX_BATCH_CALLS} tool calls per turn to prevent context overflow). "
                        "Proceed with the results above or make remaining calls in the next turn.",
                        call.call_id,
                        args=call.args if isinstance(call.args, dict) else {},
                        meta={"kind": "tool-batch-budget"},
                        ok=False,
                    )
                    continue

                if is_terminal:
                    terminal_count += 1
                executed_count += 1

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
                              browser=self.browser, approvals=self.approvals,
                              cancel=self.cancel, state=self.state)
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

        # The same read, returning the same answer, over and over. It is not a
        # failure - which is exactly why nothing caught it - but it is not
        # progress either, and the loop is the only thing in a position to
        # notice. Say so plainly and let the model move; do not refuse the call.
        if ok and not tool.mutates:
            digest = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()
            target = _read_target(call.tool, args)
            key = target or signature
            seen, times = self.repeated_reads.get(key, ("", 0))
            # A read of something already read counts however it was windowed;
            # everything else counts only when the answer comes back identical.
            times = times + 1 if (target or seen == digest) else 1
            self.repeated_reads[key] = (digest, times)
            # Said once, and only as an observation. A repeat is never refused:
            # the model is the one that knows whether it still needs the file,
            # and a read it genuinely needs is cheaper than a wrong guess about
            # what it remembers. The answer itself always comes back in full.
            if times >= MAX_SAME_READ:
                what = _read_label(call.tool, args)
                body = (f"[Read {times} times in this run, with nothing changed in between - "
                        f"{what} is already in this conversation. After a write or an edit "
                        f"succeeds there is nothing to verify by reading it back.]\n\n{body}")

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
            self.repeated_reads.clear()
            if args.get("filePath"):
                self.files_touched.add(str(args["filePath"]))

        self.events.emit("tool:end", tool=call.tool, summary=summary, ok=ok,
                         detail=body[:400])
        self.memory.add_tool_result(call.tool, body, call.call_id, args=args, ok=ok)
        self.events.emit("checkpoint", tool=call.tool)
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
