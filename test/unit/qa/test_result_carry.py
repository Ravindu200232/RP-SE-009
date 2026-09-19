"""What a project has proved, across every run that proved part of it.

One request tests one thing. The report written after it used to be the whole
project's test status, so adding a page turned a hundred passing tests into
three and every earlier result read as work undone.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from qa_agent import report


def case(name, status="passed"):
    return {"fullName": name, "title": name, "status": status, "failureMessages": []}


def suite(path, *cases, status="passed"):
    return {"name": str(path), "status": status, "assertionResults": list(cases)}


class CarryUnitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "tests").mkdir()
        for name in ("home", "cart", "menu"):
            (self.root / "tests" / f"{name}.test.js").write_text("//", encoding="utf-8")

    def path(self, name):
        return self.root / "tests" / f"{name}.test.js"

    def saved(self):
        return {"testResults": [suite(self.path("home"), case("a"), case("b")),
                                suite(self.path("cart"), case("c"))],
                "numTotalTests": 3}

    def test_a_run_that_tested_one_file_keeps_the_rest_of_the_suite(self):
        merged = report.carry_unit(
            self.saved(), {"testResults": [suite(self.path("menu"), case("d"))]}, self.root)
        self.assertEqual([Path(row["name"]).stem for row in merged["testResults"]],
                         ["home.test", "cart.test", "menu.test"])
        self.assertEqual(merged["numTotalTests"], 4)
        self.assertEqual(merged["numPassedTests"], 4)
        self.assertEqual(merged["carriedForward"], 2)

    def test_the_new_result_for_a_file_replaces_the_old_one(self):
        """A test that has started failing is never answered with its last pass."""
        merged = report.carry_unit(
            self.saved(),
            {"testResults": [suite(self.path("home"), case("a", "failed"), case("b"),
                                   status="failed")]},
            self.root)
        rows = {Path(row["name"]).stem: row["status"] for row in merged["testResults"]}
        self.assertEqual(rows["home.test"], "failed")
        self.assertEqual(merged["numFailedTests"], 1)
        self.assertFalse(merged["success"])

    def test_a_deleted_test_file_stops_counting(self):
        saved = self.saved()
        saved["testResults"].append(suite(self.path("gone"), case("z")))
        merged = report.carry_unit(saved, {"testResults": [suite(self.path("menu"), case("d"))]},
                                   self.root)
        self.assertNotIn("gone.test", [Path(row["name"]).stem for row in merged["testResults"]])

    def test_a_run_with_no_unit_tests_leaves_the_suite_as_it_was(self):
        merged = report.carry_unit(self.saved(), None, self.root)
        self.assertEqual(merged["numTotalTests"], 3)

    def test_a_project_with_nothing_saved_reports_only_this_run(self):
        current = {"testResults": [suite(self.path("menu"), case("d"))]}
        self.assertIs(report.carry_unit(None, current, self.root), current)
        self.assertIsNone(report.carry_unit(None, None, self.root))

    def test_totals_only_printed_never_erase_a_detailed_suite(self):
        """"Tests 3 passed" says less than per-case rows, so it does not win."""
        merged = report.carry_unit(self.saved(), {"numTotalTests": 3, "numPassedTests": 3},
                                   self.root)
        self.assertEqual(len(merged["testResults"]), 2)


class CarryJourneyTests(unittest.TestCase):
    def saved(self):
        return {"report": {"e2e": {"flows": [
            {"title": "Member books a bench", "role": "member", "flow": "direct-CDP journey",
             "stages": [{"index": 1, "name": "sign in", "label": "sign in", "status": "passed"}]},
            {"title": "Manager sees the money", "role": "manager", "flow": "", "stages": []},
        ]}}}

    def test_a_journey_nobody_reran_is_still_known(self):
        from qa_agent.e2e import Journey
        merged = report.carry_journeys(self.saved(), [Journey(title="Guest browses the menu")])
        self.assertEqual([journey.title for journey in merged],
                         ["Member books a bench", "Manager sees the money",
                          "Guest browses the menu"])
        self.assertEqual(merged[0].role, "member")
        self.assertEqual(merged[0].stages[0]["status"], "passed")

    def test_a_journey_that_ran_again_is_not_listed_twice(self):
        from qa_agent.e2e import Journey
        merged = report.carry_journeys(
            self.saved(), [Journey(title="member books a bench", stages=[])])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[-1].title, "member books a bench")


class ReportCarryTests(unittest.TestCase):
    """The whole record, written by a run that only re-proved part of it."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "tests").mkdir()
        (self.root / "tests" / "home.test.js").write_text("//", encoding="utf-8")
        (self.root / "tests" / "menu.test.js").write_text("//", encoding="utf-8")

        first = {
            "project": "cafe", "stages": ["unit", "e2e", "security"], "complete": True,
            "vitest": {"testResults": [suite(self.root / "tests/home.test.js",
                                             case("shows the counter"))]},
            "report": {"e2e": {"flows": [{"title": "Guest orders lunch", "stages": []}]},
                       "security": {"findings": [], "audit": {}},
                       "unit": {"coverage": {"lines": 91}}},
        }
        report.write(self.root, first)

    def evidence(self, path):
        return {"suites": [{"kind": "unit", "suite": "menu", "status": "passed", "sequence": 1,
                            "revision": 2,
                            "report": {"testResults": [suite(path, case("lists dishes"))]}}],
                "visuals": [], "history": [], "ready": True}

    def test_an_edit_adds_to_the_suite_rather_than_replacing_it(self):
        data = report.from_evidence(
            project="cafe", project_dir=self.root,
            evidence=self.evidence(self.root / "tests/menu.test.js"),
            security=None, complete=True)
        files = [Path(row["name"]).name for row in data["vitest"]["testResults"]]
        self.assertEqual(sorted(files), ["home.test.js", "menu.test.js"])
        self.assertEqual(data["vitest"]["numTotalTests"], 2)

    def test_the_stages_and_the_scan_a_project_already_had_survive(self):
        data = report.from_evidence(
            project="cafe", project_dir=self.root,
            evidence=self.evidence(self.root / "tests/menu.test.js"),
            security=None, complete=True)
        self.assertEqual(data["stages"], ["unit", "e2e", "security"])
        self.assertEqual(data["report"]["security"], {"findings": [], "audit": {}})
        self.assertEqual([flow["title"] for flow in data["report"]["e2e"]["flows"]],
                         ["Guest orders lunch"])
        self.assertEqual(data["report"]["unit"]["coverage"], {"lines": 91})

    def test_a_fresh_project_carries_nothing_it_never_had(self):
        empty = Path(tempfile.mkdtemp())
        data = report.from_evidence(project="new", project_dir=empty,
                                    evidence={"suites": [], "visuals": [], "history": []},
                                    security=None, complete=False)
        self.assertEqual(data["stages"], [])
        self.assertIsNone(data["vitest"])


if __name__ == "__main__":
    unittest.main()
