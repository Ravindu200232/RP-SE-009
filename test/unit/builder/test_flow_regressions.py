"""Regressions observed while building Reading Desk through the Studio."""
import os
import unittest
from unittest.mock import patch

from test import _support  # noqa: F401
from builder_agent import design
from builder_agent.processes import shell_info
from qa_agent.evidence import Evidence


class CoverageCompletionTests(unittest.TestCase):
    def test_green_checks_finish_without_chasing_a_coverage_percentage(self):
        for coverage in (None, {"lines": {"pct": 40}, "branches": {"pct": 20}}):
            with self.subTest(coverage=coverage):
                evidence = Evidence()
                evidence.enabled_kinds = {"unit"}
                evidence.define_scope("web", "nextjs", [
                    {"id": "books", "description": "Add books", "evidence": ["unit"]}
                ], unit_target=95)
                record = evidence.start("unit", "books", "vitest run", [], ["books"])
                evidence.observe(record, {"exitCode": 0, "coverage": coverage})
                self.assertEqual(record["status"], "passed")
                self.assertTrue(evidence.summary()["ready"])

    def test_real_test_failures_still_need_repair(self):
        evidence = Evidence()
        evidence.enabled_kinds = {"unit"}
        evidence.define_scope("web", "nextjs", [
            {"id": "books", "description": "Add books", "evidence": ["unit"]}
        ])
        record = evidence.start("unit", "books", "vitest run", [], ["books"])
        evidence.observe(record, {"exitCode": 1, "stdout": "AssertionError"})
        self.assertEqual(record["status"], "failed")
        self.assertFalse(evidence.summary()["ready"])


class DesignScopeTests(unittest.TestCase):
    def test_design_does_not_invent_screens_from_request_or_plan_words(self):
        """A screen is a route the plan writes down, never a word it mentions.

        "no login or payments" names two screens the product does not have, and
        prose about an admin signing in is not an admin route. Only text that
        actually writes a path has decided a screen exists.
        """
        for request, expected in (
            ("Reading Desk: one page to add a book and filter read books. No login or payments.", []),
            ("A shop where an admin signs in to see orders", []),
            ("Plan: / renders the reading list; no detail, login, or checkout routes.", ["/"]),
        ):
            with self.subTest(request=request):
                self.assertEqual(design.form_payload(request)["chosen"]["pages"], expected)

    def test_explicit_screen_selection_still_reaches_the_contract(self):
        selection = design.apply_answer(design.choose("one page"), {"pages": ["login", "dashboard"]})
        self.assertEqual(selection["pages"], ["dashboard", "login"])


class ShellContextTests(unittest.TestCase):
    def test_windows_metadata_names_the_command_processor_that_executes_commands(self):
        with patch("builder_agent.processes.IS_WINDOWS", True), patch.dict(
            os.environ, {"COMSPEC": "C:\\Windows\\System32\\cmd.exe"}
        ):
            self.assertEqual(shell_info()["shell"], os.environ["COMSPEC"])


if __name__ == "__main__":
    unittest.main()
