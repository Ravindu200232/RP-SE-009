"""Tests for in-flight E2E performance metrics collection and QA reporting."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from test import _support  # noqa: F401
from qa_agent.evidence import Evidence, compute_performance_from_samples
from qa_agent.journeys import capture_page_performance
from qa_agent import report, artifacts


class PerformanceMetricsTests(unittest.TestCase):
    def test_capture_page_performance_extracts_metrics_safely(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "ttfb": 42,
            "dcl": 180,
            "load": 250,
            "fcp": 120,
            "fp": 80,
            "apiCount": 3,
            "avgApi": 45,
            "url": "http://localhost:3000/dashboard",
        }
        result = capture_page_performance(page)
        self.assertIsNotNone(result)
        self.assertEqual(result["ttfb"], 42)
        self.assertEqual(result["fcp"], 120)
        self.assertEqual(result["apiCount"], 3)

    def test_capture_page_performance_handles_exceptions_gracefully(self):
        page = MagicMock()
        page.evaluate.side_effect = Exception("CDP connection broken")
        result = capture_page_performance(page)
        self.assertIsNone(result)

        self.assertIsNone(capture_page_performance(None))

    def test_compute_performance_from_samples_calculates_scores_and_metrics(self):
        samples = [
            {"ttfb": 50, "dcl": 220, "load": 350, "fcp": 140, "apiCount": 2, "avgApi": 60, "url": "http://localhost:3000/"},
            {"ttfb": 40, "dcl": 200, "load": 310, "fcp": 130, "apiCount": 4, "avgApi": 50, "url": "http://localhost:3000/items"},
        ]
        perf = compute_performance_from_samples(samples)
        scores = perf["scores"]
        metrics = perf["metrics"]

        self.assertIn("performance", scores)
        self.assertIn("speed-index", scores)
        self.assertIn("responsiveness", scores)
        self.assertIn("navigation", scores)
        self.assertGreaterEqual(scores["performance"], 90)

        self.assertIn("time-to-first-byte", metrics)
        self.assertIn("first-contentful-paint", metrics)
        self.assertIn("dom-content-loaded", metrics)
        self.assertIn("page-load-time", metrics)
        self.assertIn("api-response-avg", metrics)
        self.assertEqual(metrics["api-requests-measured"], "6 calls")
        self.assertEqual(metrics["journeys-measured"], "2 flow(s)")

    def test_evidence_ledger_records_and_computes_performance(self):
        evidence = Evidence()
        self.assertEqual(evidence.compute_performance(), {"scores": {}, "metrics": {}})

        evidence.record_performance_sample(
            suite="guest-flow",
            ttfb=35,
            dcl=190,
            load=280,
            fcp=110,
            apiCount=3,
            avgApi=40,
            url="http://localhost:3000/",
        )
        summary = evidence.summary()
        self.assertIn("performance", summary)
        perf = summary["performance"]
        self.assertIn("performance", perf["scores"])
        self.assertIn("time-to-first-byte", perf["metrics"])

    def test_report_from_evidence_and_assemble_carries_performance(self):
        evidence_dict = {
            "ready": True,
            "suites": [
                {"kind": "e2e", "suite": "order", "status": "passed",
                 "output": "1. navigate -> /\n2. assert textIncludes -> Done"}
            ],
            "visuals": [],
            "history": [],
            "performance": {
                "scores": {"performance": 96, "speed-index": 98},
                "metrics": {"time-to-first-byte": "35 ms", "page-load-time": "280 ms"},
                "measured_on": "in-flight e2e browser session",
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            data = report.from_evidence(
                project="shop",
                project_dir=Path(directory),
                evidence=evidence_dict,
                security=None,
                complete=True,
            )
            self.assertIn("performance", data)
            self.assertEqual(data["performance"]["scores"]["performance"], 96)
            self.assertEqual(data["performance"]["metrics"]["page-load-time"], "280 ms")


if __name__ == "__main__":
    unittest.main()
