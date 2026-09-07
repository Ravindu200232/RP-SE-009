"""The QA stages, driven by a scripted agent and a scripted runner.

The stage functions are the part that decides whether a suite is repaired
again or reported as it stands, and that decision is made from the runner's
report rather than from anything a model said. Both are replaced here so the
decision itself is what is under test.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from qa_agent import e2e as e2e_stage
from qa_agent import harness, unit as unit_stage


def vitest(cases):
    suites = {}
    for path, name, status in cases:
        suites.setdefault(path, []).append(
            {"fullName": name, "status": status,
             "failureMessages": ["AssertionError: expected 1 to be 2"]
             if status == "failed" else []})
    return {"testResults": [{"name": path, "assertionResults": rows}
                            for path, rows in suites.items()]}


class FakeAgent:
    """Stands in for the builder agent: records briefs, edits on demand."""

    def __init__(self, on_build=None):
        self.briefs = []
        self.on_build = on_build
        self.memory = type("M", (), {"evidence": None, "digest": {"files": set()}})()

    def build(self, brief, **kwargs):
        self.briefs.append(brief)
        if self.on_build:
            self.on_build(len(self.briefs))
        return type("O", (), {"status": "completed", "result": ""})()


class UnitStageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "package.json").write_text(
            json.dumps({"name": "app", "scripts": {}}), encoding="utf-8")
        (self.root / "node_modules" / "vitest").mkdir(parents=True)
        self.reports = []

    def write_report(self, report, coverage=None):
        target = self.root / ".agentforge" / "qa"
        target.mkdir(parents=True, exist_ok=True)
        (target / "vitest.json").write_text(json.dumps(report), encoding="utf-8")
        if coverage is not None:
            (self.root / "coverage").mkdir(exist_ok=True)
            (self.root / "coverage" / "coverage-summary.json").write_text(
                json.dumps({"total": coverage}), encoding="utf-8")

    def runner(self, script):
        """Each vitest invocation writes the next report in `script`."""
        state = {"n": 0}

        def run(command, timeout=900):
            self.reports.append(command)
            if "vitest" in command:
                report = script[min(state["n"], len(script) - 1)]
                state["n"] += 1
                self.write_report(report)
                return {"exitCode": 0 if not _failing(report) else 1,
                        "stdout": "", "stderr": ""}
            return {"exitCode": 0, "stdout": "", "stderr": ""}
        return run

    def test_a_green_suite_is_reported_after_one_round(self):
        green = vitest([("test/a.test.js", "one", "passed")])
        result = unit_stage.run_stage(agent=FakeAgent(), workspace=self.root,
                                      run_command=self.runner([green]))

        self.assertTrue(result.ran)
        self.assertEqual(len(result.rounds), 1)
        self.assertEqual(result.rounds[0]["rate"], 100)
        self.assertEqual(result.unresolved, [])

    def test_a_failure_that_changes_is_repaired_again(self):
        first = vitest([("test/a.test.js", "one", "failed")])
        second = vitest([("test/a.test.js", "two", "failed")])
        third = vitest([("test/a.test.js", "two", "passed")])
        agent = FakeAgent()

        result = unit_stage.run_stage(agent=agent, workspace=self.root,
                                      run_command=self.runner([first, second, third]))

        self.assertEqual(len(result.rounds), 3)
        self.assertEqual(result.rounds[-1]["rate"], 100)
        # One authoring brief, then one repair brief per changed failure.
        self.assertEqual(len(agent.briefs), 3)
        self.assertIn("Repair it", agent.briefs[1])

    def test_the_same_failure_twice_ends_the_round_rather_than_looping(self):
        same = vitest([("test/a.test.js", "one", "failed")])
        agent = FakeAgent()

        result = unit_stage.run_stage(agent=agent, workspace=self.root,
                                      run_command=self.runner([same, same, same, same]))

        self.assertLess(len(result.rounds), unit_stage.MAX_ROUNDS + 1)
        self.assertIn("same failures repeated", result.reason)
        self.assertEqual(len(result.unresolved), 1)
        self.assertEqual(result.unresolved[0]["diagnosis"], "assertion")

    def test_a_runner_that_collects_nothing_is_a_problem_not_a_pass(self):
        result = unit_stage.run_stage(agent=FakeAgent(), workspace=self.root,
                                      run_command=self.runner([{"testResults": []}]))

        self.assertIn("no test cases", result.reason)
        self.assertEqual(result.counts["total"], 0)

    def test_a_broken_harness_stops_before_anything_is_authored(self):
        agent = FakeAgent()
        result = unit_stage.run_stage(
            agent=agent, workspace=self.root,
            run_command=lambda command, timeout=900: {"exitCode": 1, "stderr": "ENOENT"})

        self.assertFalse(result.ran)
        self.assertIn("install failed", result.reason)
        self.assertEqual(agent.briefs, [])   # nothing authored into a broken project


class E2EStageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def agent_with(self, evidence_by_round):
        """An agent whose evidence changes as the stage repairs it.

        The first brief authors the journeys, so the evidence it produces is
        round zero. Only a repair brief after that advances it.
        """
        state = {"n": 0}

        class Evidence:
            @staticmethod
            def summary():
                return evidence_by_round[min(state["n"], len(evidence_by_round) - 1)]

        agent = FakeAgent(on_build=lambda count: state.__setitem__("n", max(0, count - 1)))
        agent.memory.evidence = Evidence()
        return agent

    def test_passing_journeys_end_the_stage_without_repair(self):
        passing = {"suites": [{"kind": "e2e", "suite": "login", "status": "passed",
                               "output": "1. navigate -> /login\n2. assert urlIncludes"}]}
        agent = self.agent_with([passing])

        result = e2e_stage.run_stage(agent=agent, workspace=self.root)

        self.assertTrue(result.ran)
        self.assertEqual(result.failures, [])
        self.assertEqual(len(agent.briefs), 1)          # authoring only
        self.assertEqual(result.as_report()["stage_passed"], 2)

    def test_a_failing_journey_is_repaired_and_the_owner_is_named(self):
        failing = {"suites": [{"kind": "e2e", "suite": "checkout", "status": "failed",
                               "reason": "E2E_UI_TARGET_MISSING: no Pay button",
                               "output": "1. navigate -> /cart\n2. click Pay"}]}
        fixed = {"suites": [{"kind": "e2e", "suite": "checkout", "status": "passed",
                             "output": "1. navigate -> /cart\n2. click Pay"}]}
        agent = self.agent_with([failing, fixed])

        result = e2e_stage.run_stage(agent=agent, workspace=self.root)

        self.assertEqual(result.failures, [])
        self.assertGreaterEqual(len(agent.briefs), 2)
        self.assertIn("E2E_UI_TARGET_MISSING", agent.briefs[1])

    def test_a_journey_that_never_passes_is_reported_not_retried_forever(self):
        failing = {"suites": [{"kind": "e2e", "suite": "checkout", "status": "failed",
                               "reason": "Step 2 failed: still no Pay button",
                               "output": "1. navigate -> /cart\n2. click Pay"}]}
        agent = self.agent_with([failing])

        result = e2e_stage.run_stage(agent=agent, workspace=self.root)

        self.assertEqual(len(result.failures), 1)
        self.assertLessEqual(len(agent.briefs), e2e_stage.MAX_ROUNDS + 1)
        report = result.as_report()
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["stage_not_reached"], 0)

    def test_a_stage_with_no_journeys_says_so(self):
        agent = self.agent_with([{"suites": []}])

        result = e2e_stage.run_stage(agent=agent, workspace=self.root)

        self.assertEqual(result.journeys, [])
        self.assertIn("No browser journeys", result.reason)


def _failing(report):
    return any(case["status"] == "failed"
               for suite in report.get("testResults", [])
               for case in suite.get("assertionResults", []))


if __name__ == "__main__":
    unittest.main()
