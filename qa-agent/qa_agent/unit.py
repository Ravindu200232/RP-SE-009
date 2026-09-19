"""The unit stage.

Redesigned around the engine rather than around a pile of bespoke authoring
code. The old stage hand-rolled target selection, test generation, mock
installation, repair heuristics and quarantine, and most of its bugs lived in
the seams between those. What actually matters is narrower:

1. Make the runner work. Deterministic, no model.
2. Have the model author tests for the targets that matter, at the deep
   profile, reading the source first.
3. Run Vitest for real and parse its own report. Never a model's summary.
4. Repair, bounded by the failure signature: the same failure twice with no
   edit in between ends the round instead of looping.

Coverage can be reported as diagnostic information. It does not cause repairs
or block a passing suite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import harness

MAX_ROUNDS = 4


@dataclass
class UnitResult:
    ran: bool = False
    report: dict | None = None
    coverage: dict | None = None
    rounds: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    suspects: list = field(default_factory=list)
    deleted: int = 0
    skipped: int = 0
    reason: str = ""

    @property
    def counts(self) -> dict:
        return counts_of(self.report)


def counts_of(report: dict | None) -> dict:
    """Vitest's assertion rows are authoritative.

    The summary fields go stale after a targeted repair run that only re-ran
    part of the suite, and a stale summary reported as the current result is
    how a red suite gets shown as green.
    """
    suites = (report or {}).get("testResults") or []
    cases = [case for suite in suites for case in (suite.get("assertionResults") or [])]
    passed = sum(1 for c in cases if c.get("status") == "passed")
    failed = sum(1 for c in cases if c.get("status") == "failed")
    skipped = sum(1 for c in cases if c.get("status") in ("skipped", "pending", "todo"))
    return {"passed": passed, "failed": failed, "skipped": skipped,
            "total": len(cases), "files": len(suites)}


def failures_of(report: dict | None) -> list[dict]:
    out = []
    for suite in (report or {}).get("testResults") or []:
        name = str(suite.get("name") or suite.get("testFilePath") or "").replace("\\", "/")
        for case in suite.get("assertionResults") or []:
            if case.get("status") != "failed":
                continue
            messages = case.get("failureMessages") or []
            out.append({"file": name, "case": case.get("fullName") or case.get("title") or "",
                        "message": (messages[0] if messages else "")[:1200]})
    return out


def signature(failures: list[dict]) -> str:
    """What "the same failure again" means, without the line noise."""
    parts = []
    for failure in sorted(failures, key=lambda f: (f["file"], f["case"]))[:20]:
        head = re.sub(r"\d+", "#", (failure["message"] or "").splitlines()[0] if failure["message"] else "")
        parts.append(f"{failure['file'].split('/')[-1]}::{failure['case']}::{head[:120]}")
    return "|".join(parts)


def classify(message: str) -> str:
    """Group failures so the round summary says something useful."""
    text = str(message or "").lower()
    for pattern, label in (
        (r"cannot find module|failed to resolve|module not found", "missing module"),
        (r"is not a function|is not defined", "missing export"),
        (r"econnrefused|mongo|connection", "database"),
        (r"timeout|timed out", "timeout"),
        (r"expected .* to (?:be|equal|contain)", "assertion"),
        (r"syntaxerror|unexpected token", "syntax"),
        (r"cannot read propert", "null access"),
    ):
        if re.search(pattern, text):
            return label
    return "other"


def top_classes(failures: list[dict], limit: int = 5) -> list[dict]:
    tally: dict[str, int] = {}
    for failure in failures:
        label = classify(failure.get("message"))
        tally[label] = tally.get(label, 0) + 1
    return [{"class": label, "count": count}
            for label, count in sorted(tally.items(), key=lambda kv: -kv[1])[:limit]]


AUTHOR_BRIEF = """Complete the unit verification for this application.

Work at the deepest level you can: read the source before you test it, and test
what the code actually does rather than what its name suggests.

The preceding build's reads, decisions and evidence remain in this conversation
when available. Continue from them. Inspect the recorded evidence and saved
test results first, then read source and existing tests for the missing or
changed behaviours. A transition into QA is not a reason to reread every file
or rewrite an existing suite. Reading another part of a saved report is not a
reason to execute the tests again.
Do not add or rerun tests solely to improve coverage percentages.

1. Read the vitest skill and use the project layout to locate the modules you
   need. Reuse current source already in context; read missing or changed context.
2. Reuse the existing verification scope and extend it for missing behaviours.
   If there is no scope, call defineVerificationScope for domain logic, route
   contracts, validation/error paths and model constraints, then seal it.
3. Add or repair tests under test/ as `<name>.test.js`, importing through the `@/`
   alias. Use the helpers in test/helpers/ for anything touching MongoDB, and
   isolated fixtures - never production data.
4. Run the suite with runTests(kind:"unit") and the requirement ids in covers.
   Capture a JSON report in the same execution; coverage collection is optional.
5. When something fails, read the failure and its source context, then fix the
   real cause. If the product is wrong, fix the product. If the test is wrong,
   fix the test.

Never weaken an assertion, delete a case or add a skip to make the suite pass.
A test that asserts nothing is worse than no test, because it reports green.
If a behaviour genuinely cannot be tested here, record it with recordLimitation
and say exactly why."""


REPAIR_BRIEF = """The unit suite is failing. Repair it.

{summary}

Failures:
{failures}

Read the source each failure points at before editing anything. Cluster related
failures: many import or resolution errors usually share one cause, and fixing
that once beats patching each symptom. Then rerun only the affected files with
runTests before the whole suite."""


def run_stage(*, agent, workspace: Path, run_command, events=None, floor: int = 95,
              on_round=None) -> UnitResult:
    """Author, run and repair the unit suite. Returns what the runner reported.

    `on_round` is called after every round with the result so far. Repair can
    take a dozen rounds, and a run that is stopped during them should still
    leave behind the rounds it did.
    """
    workspace = Path(workspace)
    result = UnitResult()

    setup = harness.prepare(workspace, run_command)
    if not setup["ok"]:
        result.reason = setup["reason"]
        return result
    if events and setup["actions"]:
        events.emit("notice", level="info",
                    message="Test harness: " + "; ".join(setup["actions"]))

    agent.build(AUTHOR_BRIEF, verification_kinds=("unit",))
    last_signature = ""

    for round_index in range(MAX_ROUNDS):
        outcome = run_command(harness.run_command(workspace))
        result.ran = True
        report = harness.read_report(workspace)
        coverage = harness.read_coverage(workspace)
        result.report = report or result.report
        result.coverage = coverage or result.coverage

        counts = counts_of(result.report)
        failures = failures_of(result.report)
        rate = round(counts["passed"] * 100 / counts["total"]) if counts["total"] else 0
        result.rounds.append({"round": round_index + 1, "rate": rate, "floor": floor,
                              "passed": counts["passed"], "cases": counts["total"],
                              "top": top_classes(failures)})
        if events:
            events.emit("test", state="result", kind="unit", suite="vitest",
                        status="passed" if not failures else "failed",
                        detail=f"{counts['passed']}/{counts['total']} passing")
        if on_round:
            on_round(result)

        result.skipped = counts["skipped"]
        if not failures and counts["total"]:
            break
        if not counts["total"]:
            result.reason = ("The runner produced no test cases. "
                             + (outcome.get("stderr") or outcome.get("stdout") or "")[-600:])
            break

        current = signature(failures)
        if current == last_signature:
            # The same failures with nothing changed in between will not pass
            # on a third identical run; the round ends and the report says so.
            result.reason = "Repair stopped: the same failures repeated with no change between runs."
            break
        last_signature = current

        listing = "\n".join(f"- {f['file']} :: {f['case']}\n  {f['message'].splitlines()[0][:220]}"
                            for f in failures[:12])
        agent.build(REPAIR_BRIEF.format(
            summary=f"{counts['failed']} of {counts['total']} cases failing ({rate}% passing).",
            failures=listing), verification_kinds=("unit",))

    result.unresolved = [
        {"file": failure["file"], "case": failure["case"], "message": failure["message"][:400],
         "diagnosis": classify(failure["message"])}
        for failure in failures_of(result.report)
    ]
    result.suspects = _suspects(workspace)
    return result


_SUSPECT = re.compile(r"^\s*//\s*SUSPECT:\s*(.+)$", re.M)


def _suspects(workspace: Path) -> list[dict]:
    """Notes the author left where the code looked wrong but the test must not lie.

    A test describes what the code does. When the author believes the code is
    wrong, the honest move is a note, not a test asserting the bug is correct.
    """
    found = []
    base = Path(workspace) / "test"
    if not base.is_dir():
        return found
    for path in sorted(base.rglob("*.test.*")):
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for note in _SUSPECT.findall(body):
            found.append({"test": path.relative_to(workspace).as_posix(), "note": note.strip()[:300]})
            if len(found) >= 40:
                return found
    return found
