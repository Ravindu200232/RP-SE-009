from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from test import _support  # noqa: F401
from qa_agent.e2e.e2e_progress import (
    extend_round_budget,
    measure_progress,
    normalize_message,
    stop_after_no_progress,
)
from qa_agent.e2e.e2e_results import aggregate_e2e, stage_result
from qa_agent.e2e.e2e_semantics import (
    is_iso_date,
    is_relative_date,
    js_runtime_value,
    relative_date_token,
    resolve_runtime_value,
    semantic_words,
)


def failure(kind: str, message: str = "failed") -> SimpleNamespace:
    return SimpleNamespace(kind=kind, target="app/page.jsx", name="Submit", message=message)


class _Step:
    def __init__(self, label: str):
        self.label = label

    def describe(self) -> str:
        return self.label


class SemanticValueTests(unittest.TestCase):
    def test_semantic_words_normalize_camel_case_and_common_suffixes(self):
        words = semantic_words("BookingHistory buttons and booked rooms")

        self.assertIn("book", words)
        self.assertIn("history", words)
        self.assertIn("room", words)
        self.assertNotIn("button", words)

    def test_relative_date_token_is_clamped_to_the_supported_window(self):
        self.assertEqual(relative_date_token(99999), "{{date+3650}}")
        self.assertEqual(relative_date_token(-99999), "{{date-3650}}")

    def test_relative_date_resolves_against_the_runtime_day(self):
        self.assertEqual(
            resolve_runtime_value("{{date+3}}", today=date(2026, 8, 25)),
            "2026-08-28",
        )
        self.assertEqual(
            resolve_runtime_value("{{date-2}}", today=date(2026, 8, 25)),
            "2026-08-23",
        )

    def test_non_relative_runtime_value_is_not_changed(self):
        self.assertEqual(resolve_runtime_value("guest@example.test"), "guest@example.test")

    def test_date_validators_reject_impossible_calendar_dates(self):
        self.assertTrue(is_relative_date("{{date+10}}"))
        self.assertTrue(is_iso_date("2028-02-29"))
        self.assertFalse(is_iso_date("2027-02-29"))

    def test_javascript_runtime_expression_only_wraps_relative_dates(self):
        quote = lambda value: f'"{value}"'

        self.assertEqual(js_runtime_value("{{date-4}}", quote), "relativeDate(-4)")
        self.assertEqual(js_runtime_value("fixed", quote), '"fixed"')


class ConvergencePolicyTests(unittest.TestCase):
    def test_failure_messages_ignore_runtime_specific_ids_ports_and_timings(self):
        message = normalize_message(
            "Object 507f1f77bcf86cd799439011 at http://localhost:5173 took 1200ms code 999"
        )

        self.assertIn("<oid>", message)
        self.assertIn("<base>", message)
        self.assertIn("<time>", message)
        self.assertIn("<n>", message)

    def test_advancing_to_a_later_business_step_counts_as_progress(self):
        progressed, reason = measure_progress(
            [failure("SELECTOR")],
            [failure("ASSERTION")],
            set(),
            before_step=0,
            after_step=1,
        )

        self.assertTrue(progressed)
        self.assertIn("1→2", reason)

    def test_lower_severity_at_the_same_step_does_not_fake_progress(self):
        progressed, reason = measure_progress(
            [failure("CRASH")],
            [failure("SELECTOR", "different symptom")],
            set(),
            before_step=2,
            after_step=2,
        )

        self.assertFalse(progressed)
        self.assertIn("same scenario step", reason)

    def test_no_progress_stops_after_the_minimum_rounds(self):
        self.assertFalse(stop_after_no_progress(1, False, minimum_rounds=2))
        self.assertTrue(stop_after_no_progress(2, False, minimum_rounds=2))
        self.assertFalse(stop_after_no_progress(4, True, minimum_rounds=2))

    def test_evidence_exhaustion_can_stop_immediately(self):
        self.assertTrue(stop_after_no_progress(1, False, exhausted=True))

    def test_round_budget_grows_only_after_observed_progress(self):
        self.assertEqual(extend_round_budget(2, 2, 6, 2, True), 4)
        self.assertEqual(extend_round_budget(2, 2, 6, 2, False), 2)


class E2EResultAccountingTests(unittest.TestCase):
    def setUp(self):
        self.scenario = SimpleNamespace(steps=[_Step("Open page"), _Step("Submit form")])

    def test_successful_journey_counts_each_stage_once(self):
        result = stage_result(self.scenario)

        self.assertEqual(result["stage_total"], 2)
        self.assertEqual(result["stage_passed"], 2)
        self.assertEqual(result["stage_rate"], 100)

    def test_failed_stage_marks_later_work_as_not_reached(self):
        failed = SimpleNamespace(name="Open page")
        result = stage_result(self.scenario, [failed])

        self.assertEqual(result["stage_failed"], 1)
        self.assertEqual(result["stage_not_reached"], 1)
        self.assertEqual([row["status"] for row in result["stages"]], ["fail", "not_reached"])

    def test_postcondition_failure_is_an_explicit_proof_stage(self):
        failed = SimpleNamespace(name="Saved record is visible")
        result = stage_result(self.scenario, [failed], {"completed": True})

        self.assertEqual(result["stage_total"], 3)
        self.assertEqual(result["stage_passed"], 2)
        self.assertEqual(result["stage_failed"], 1)

    def test_global_integrity_proof_is_included_in_aggregate(self):
        output = {
            "flows": [{"stage_total": 2, "stage_passed": 2}],
            "global_integrity": {"ran": True, "passed": False},
        }

        aggregate_e2e(output)

        self.assertEqual(output["stage_total"], 3)
        self.assertEqual(output["stage_failed"], 1)
        self.assertEqual(output["stage_rate"], 67)


if __name__ == "__main__":
    unittest.main()
