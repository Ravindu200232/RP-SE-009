"""The QA agent.

It drives the same engine the builder does, at the deep profile - the one place
that profile is spent, because the unit and end-to-end suites are the evidence
anyone actually reads.

Four stages, in the order that makes each one cheaper than the last would be
without it:

    harness -> unit -> end-to-end -> security

The unit suite runs before the browser because a broken import found in three
seconds by Vitest is a browser journey you never had to debug. Security runs
last because it reads the finished tree.

The record it writes is the studio's Testing tab, byte for byte - there is no
second summary generated for display, so what the user sees is what ran.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "builder-agent") not in sys.path:
    sys.path.insert(0, str(_ROOT / "builder-agent"))

from builder_agent import BuilderAgent, Config, Events, VERIFY_QUALITY  # noqa: E402
from builder_agent.layout import inspect_layout  # noqa: E402
from builder_agent.memory import Memory  # noqa: E402

from . import e2e as e2e_stage  # noqa: E402
from . import harness, report, security, unit as unit_stage  # noqa: E402


@dataclass
class QAOutcome:
    project: str
    ok: bool = False
    record: dict = field(default_factory=dict)
    path: str = ""
    reason: str = ""


class QAAgent:
    """Proves a generated application, and writes down what it proved."""

    def __init__(self, *, project: str, project_dir: Path | str, model: str,
                 host: str = "", stack: str = "", events: Events | None = None,
                 think: bool = False, cancel=None, unit: bool = True, e2e: bool = True,
                 memory: Memory | None = None) -> None:
        self.project = project
        self.project_dir = Path(project_dir)
        self.events = events or Events()
        self.run_unit = unit
        self.run_e2e = e2e
        # The deep profile, and the only place it is used. Building runs at the
        # default profile; the suites are held to the higher bar.
        self.config = Config(workspace=self.project_dir, model=model, host=host,
                             stack=stack or "", quality=VERIFY_QUALITY, think=think,
                             unit_tests=unit, e2e_tests=e2e)
        # Continue the completed build's transcript and evidence. QA can use a
        # different model/profile without relearning the whole application.
        self.agent = BuilderAgent(self.config, events=self.events, cancel=cancel, memory=memory)

    # -- helpers ---------------------------------------------------------
    def _run(self, command: str, timeout: int = 900) -> dict:
        """Run a shell command in the project, through the engine's manager."""
        return self.agent.processes.run(command, self.project_dir, timeout=timeout,
                                        yield_after=timeout)

    def _manifest(self) -> dict:
        """Which test file covers which source file, from the imports they make."""
        import re
        found = {}
        base = self.project_dir / "test"
        if not base.is_dir():
            return found
        pattern = re.compile(r"""from\s+['"]@/([^'"]+)['"]""")
        for path in sorted(base.rglob("*.test.*")):
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            targets = pattern.findall(body)
            found[path.relative_to(self.project_dir).as_posix()] = {
                "target": targets[0] if targets else "", "targets": targets[:8]}
        return found

    def _runtime_notes(self) -> list[str]:
        """Runtime problems the engine observed, as plain lines for the report."""
        notes = []
        for record in self.agent.memory.evidence.summary().get("suites", []):
            if record.get("kind") == "runtime" and record.get("status") != "passed":
                notes.append(f"{record.get('suite')}: {record.get('reason') or record.get('output', '')[:300]}")
        for job in self.agent.processes.list():
            tail = (job.stderr or "").strip().splitlines()[-3:]
            if job.exit_code not in (0, None) and tail:
                notes.append(f"{job.command[:80]}: " + " ".join(tail))
        return notes[:40]

    # -- the run ---------------------------------------------------------
    def run(self) -> QAOutcome:
        outcome = QAOutcome(project=self.project)
        if not (self.project_dir / "package.json").is_file():
            outcome.reason = "This project has no package.json, so there is nothing to test."
            return outcome

        self.events.emit("test", state="start", project=self.project)
        existing = report.read(self.project_dir, self.project)

        try:
            unit_result = unit_stage.UnitResult()
            e2e_result = e2e_stage.E2EResult()
            findings = {"findings": [], "audit": {}}
            done: list = []
            record = {}
            path = None

            def save(complete: bool = False):
                """Put on disk what has been established so far.

                A verification that is cancelled, killed or still repairing
                used to leave nothing behind at all: the Testing panel said
                "nothing has been recorded for this project" after twelve
                rounds of real unit runs. Every stage now lands as it finishes,
                so what was proved survives whatever happens next.
                """
                nonlocal record, path
                record = report.assemble(
                    project=self.project, project_dir=self.project_dir,
                    unit=unit_result, e2e=e2e_result, security=findings,
                    evidence=self.agent.memory.evidence.summary(),
                    runtime=self._runtime_notes(), manifest=self._manifest(),
                    tests=harness.collect_test_sources(self.project_dir),
                    history=report.append_history(existing, unit_result.rounds),
                    performance=existing.get("performance"),
                    stages=tuple(done), complete=complete)
                path = report.write(self.project_dir, record)
                self.events.emit("test", state="report", project=self.project,
                                 stages=list(done), complete=complete)

            def _round_saved(partial):
                """Each repair round is worth keeping on its own."""
                nonlocal unit_result
                unit_result = partial
                save()

            if self.run_unit:
                self.events.emit("phase", phase="unit", title="Unit tests", status="active")
                unit_result = unit_stage.run_stage(
                    agent=self.agent, workspace=self.project_dir, run_command=self._run,
                    events=self.events, floor=int(VERIFY_QUALITY.unit_floor),
                    on_round=_round_saved)
                self.events.emit("phase", phase="unit", title="Unit tests", status="done")
                done.append("unit")
                save()

            if self.run_e2e:
                self.events.emit("phase", phase="e2e", title="End-to-end", status="active")
                e2e_result = e2e_stage.run_stage(
                    agent=self.agent, workspace=self.project_dir, events=self.events)
                self.events.emit("phase", phase="e2e", title="End-to-end", status="done")
                done.append("e2e")
                save()

            self.events.emit("phase", phase="security", title="Security review", status="active")
            findings = security.review(self.project_dir, self._run)
            self.events.emit("phase", phase="security", title="Security review", status="done")
            done.append("security")
            save(complete=True)

            counts = unit_result.counts
            e2e_report = e2e_result.as_report()
            outcome.record = record
            outcome.path = str(path)
            outcome.ok = (counts["failed"] == 0 and e2e_report.get("failed", 0) == 0
                          and not findings["findings"])
            outcome.reason = "" if outcome.ok else _open_items(counts, e2e_report, findings)
            self.events.emit("test", state="done", project=self.project, ok=outcome.ok,
                             unit=counts, e2e=e2e_report)
            return outcome
        finally:
            self.agent.dispose()

    def dispose(self) -> None:
        self.agent.dispose()


def _open_items(counts: dict, e2e_report: dict, findings: dict) -> str:
    parts = []
    if counts["failed"]:
        parts.append(f"{counts['failed']} unit case(s) failing")
    if e2e_report.get("failed"):
        parts.append(f"{e2e_report['failed']} journey(s) failing")
    if findings["findings"]:
        parts.append(f"{len(findings['findings'])} security finding(s)")
    return "; ".join(parts) or "verification incomplete"
