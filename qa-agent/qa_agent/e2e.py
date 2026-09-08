"""The end-to-end stage.

A journey is a user's whole path through the product - sign in, search, book,
pay, see it in their bookings - not a click. Scoring is per stage, because
"checkout failed" tells nobody anything, while "3 of 7 stages passed, it broke
at payment" is a bug report.

Stages after a failure are recorded as *not reached* rather than failed. They
were never executed, and marking them failed both overstates the damage and
hides where the break actually is.

Only the final accepted run of each journey counts toward the score. Repair
retries never inflate it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_ROUNDS = 3

AUTHOR_BRIEF = """Prove this application works end to end, in a real browser.

The app must already be running. Start it as a managed service with
executeTerminal(service:true) if it is not, and confirm readiness by reaching
its URL before you test anything.

1. Discover the real routes and controls: read the project layout, open the
   app with browserOpen and read the accessible tree with browserSnapshot.
   Never guess a selector.
2. Call defineVerificationScope with the critical user journeys this product
   has - each one a complete path a real user takes, end to end. Seal it.
3. Run each journey with browserRunJourney, giving it a stable suite name, a
   startUrl, the requirement ids in covers, and steps that assert real
   outcomes: the text that proves the action worked, the URL it lands on, the
   count of what is now listed.
4. Every journey ends with an automatic diagnostics check, so a page that
   renders while throwing in the console or answering 500 fails. That is
   deliberate - fix the app, not the assertion.

Route each failure by its owner:
- E2E_SELECTOR_AMBIGUOUS: the page has several of that control, which on a list
  page is correct and expected. Add index:0 to take the first (index:-1 the
  last), or use a more specific name or CSS selector. Do not change the product
  to make a list stop repeating itself.
- E2E_SELECTOR_MISMATCH: your locator names something that is not there. Read
  the snapshot again and use the accessible name that really exists.
- E2E_UI_TARGET_MISSING: the product is missing the control the journey needs.
  Build it, or fix the route or state that should have produced it.
- An assertion, console, network or 5xx failure: the product is broken. Fix it.

Use isolated test accounts and data. Never weaken a journey to make it pass."""


REPAIR_BRIEF = """These journeys are failing:

{failures}

Repair the owner each failure names, then rerun only the affected journey.
Do not take another snapshot of a page that has not changed, and do not rerun
a journey unchanged."""


@dataclass
class Journey:
    title: str
    role: str = "user"
    flow: str = ""
    stages: list = field(default_factory=list)
    blocked_upstream: bool = False

    def score(self) -> dict:
        passed = sum(1 for s in self.stages if s["status"] == "passed")
        failed = sum(1 for s in self.stages if s["status"] == "failed")
        not_reached = sum(1 for s in self.stages if s["status"] == "not_reached")
        return {"stage_total": len(self.stages), "stage_passed": passed,
                "stage_failed": failed, "stage_not_reached": not_reached}

    def as_dict(self) -> dict:
        return {"title": self.title, "role": self.role, "flow": self.flow,
                "stages": self.stages, "blocked_upstream": self.blocked_upstream,
                **self.score()}


@dataclass
class E2EResult:
    ran: bool = False
    journeys: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    fixed: int = 0
    reason: str = ""

    def as_report(self) -> dict:
        totals = {"stage_total": 0, "stage_passed": 0, "stage_failed": 0, "stage_not_reached": 0}
        for journey in self.journeys:
            for key, value in journey.score().items():
                totals[key] += value
        passed = sum(1 for j in self.journeys if j.score()["stage_failed"] == 0
                     and j.score()["stage_total"] > 0)
        total = len(self.journeys)
        return {
            "ran": self.ran, "total": total, "passed": passed, "failed": total - passed,
            "rate": round(passed * 100 / total) if total else 0,
            **totals,
            "flows": [journey.as_dict() for journey in self.journeys],
            "failures": self.failures, "fixed": self.fixed,
            "reason": self.reason,
        }


_STEP_LABEL = re.compile(r"^(\d+)\.\s+(.*)$")


def journeys_from_evidence(evidence: dict) -> list[Journey]:
    """Turn recorded E2E suites into per-stage journeys the studio can render.

    The engine already stored each journey's step trace as the suite's output,
    so the stages come from what ran, not from a second description of it.
    """
    journeys = []
    for record in evidence.get("suites", []):
        if record.get("kind") != "e2e":
            continue
        stages, hit_failure = [], False
        for line in str(record.get("output") or "").splitlines():
            match = _STEP_LABEL.match(line.strip())
            if not match:
                continue
            number, label = match.group(1), match.group(2)
            if hit_failure:
                # Never executed. Marking these failed would both overstate the
                # damage and hide where the journey actually broke.
                status = "not_reached"
            elif record.get("status") == "failed" and _is_failed(number, label, record):
                status = "failed"
                hit_failure = True
            else:
                status = "passed"
            stages.append({"name": label[:180], "status": status})
        if record.get("status") == "failed" and not hit_failure and stages:
            stages[-1]["status"] = "failed"
        journeys.append(Journey(title=record.get("suite", "journey"),
                                flow=record.get("source", "direct-CDP journey"),
                                stages=stages,
                                blocked_upstream=record.get("status") == "interrupted"))
    return journeys


def _is_failed(number: str, label: str, record: dict) -> bool:
    """Is this the step the recorded reason blames?

    The reason names the step by number ("Step 3 failed: ..."), so that is the
    match. The label is a fallback for a failure recorded without one.
    """
    reason = str(record.get("reason") or "")
    if not reason:
        return False
    return f"Step {number} " in reason or (len(label) > 8 and label[:40] in reason)


def run_stage(*, agent, workspace: Path, events=None) -> E2EResult:
    """Author, run and repair the browser journeys."""
    result = E2EResult()
    agent.build(AUTHOR_BRIEF)
    result.ran = True

    for _ in range(MAX_ROUNDS):
        evidence = agent.memory.evidence.summary()
        result.journeys = journeys_from_evidence(evidence)
        failing = [record for record in evidence.get("suites", [])
                   if record.get("kind") == "e2e" and record.get("status") not in ("passed", "outdated")]
        result.failures = [{"suite": record.get("suite"),
                            "reason": str(record.get("reason") or "")[:600]}
                           for record in failing]
        if not failing:
            break
        listing = "\n".join(f"- {item['suite']}: {item['reason']}" for item in result.failures[:8])
        before = len(agent.memory.digest["files"])
        agent.build(REPAIR_BRIEF.format(failures=listing))
        result.fixed += max(0, len(agent.memory.digest["files"]) - before)

    evidence = agent.memory.evidence.summary()
    result.journeys = journeys_from_evidence(evidence)
    if not result.journeys:
        result.reason = "No browser journeys were recorded."
    if events:
        report = result.as_report()
        events.emit("test", state="result", kind="e2e", suite="journeys",
                    status="passed" if not result.failures else "failed",
                    detail=f"{report['stage_passed']}/{report['stage_total']} stages")
    return result
