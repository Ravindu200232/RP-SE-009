"""Saved reports survive interruption and never require another test run."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from qa_agent.evidence import Evidence
from qa_agent import artifacts, report


class ReportingArtifactsTests(unittest.TestCase):
    def test_recovers_file_outcomes_sources_routes_and_screenshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "node_modules/.vite/vitest/results.json": json.dumps({"results": [[":test/route.test.js", {"failed": False, "duration": 12}]]}),
                "test/route.test.js": "import {GET} from '../app/api/rooms/route.js';",
                "app/api/rooms/route.js": "export async function GET() {}",
                ".agent/knowledge.json": json.dumps([{"problem": "admin", "category": "E2E", "verification": "browserRunJourney passed: admin", "at": "2026-09-09T01:00:00Z"}]),
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            shot = root / ".agent/screenshots/home-360.png"
            shot.parent.mkdir(parents=True)
            shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 360, 800))
            data = report.read(root, "hotel")
            self.assertFalse(data["complete"])
            self.assertEqual(data["vitest"]["fileResults"][0]["status"], "passed")
            self.assertNotIn("numPassedTests", data["vitest"])
            self.assertEqual(data["contracts"][0]["tests"][0]["status"], "passed")
            self.assertEqual(data["screenshots"][0]["width"], 360)
            self.assertEqual(data["report"]["e2e"]["stage_total"], 0)
            self.assertEqual(len(data["report"]["e2e"]["recordedOutcomes"]), 1)
            self.assertEqual(len(data["timeline"]), 3)

    def test_live_result_saved_before_done_with_full_e2e_trace_and_retry_history(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, published, errors = Evidence(), [], []
            listener = report.LiveReport(directory, ledger, published.append, errors.append)
            trace = "\n".join(f"{i}. assert a long browser stage {'x' * 60}" for i in range(1, 41))
            ledger.record_external("e2e", "checkout", "browserRunJourney", [], "failed", trace, "Step 40 failed")
            listener("tool:end", {})
            ledger.record_external("e2e", "checkout", "browserRunJourney", [], "passed", trace)
            listener("tool:end", {})
            listener("tool:end", {})  # Reads do not publish duplicate snapshots.
            data = report.read(directory)
            self.assertFalse(data["complete"])
            self.assertEqual(data["report"]["e2e"]["stage_total"], 40)
            self.assertEqual([r["status"] for r in data["timeline"]], ["failed", "passed"])
            self.assertEqual(len(published), 2)
            self.assertEqual(errors, [])
            self.assertTrue(all(r["type"] == "test_report" for r in published))

    def test_screenshot_access_stays_in_project_image_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in ("../secret.png", ".env", "app/private.png", ".agent/screenshots/../../../secret.png"):
                with self.assertRaises(ValueError):
                    artifacts.screenshot_path(directory, path)

    def test_retry_does_not_reuse_previous_assertion_report(self):
        ledger = Evidence()
        row = ledger.start("unit", "all", "vitest", [], [])
        row["report"] = {"testResults": []}
        ledger.observe(row, {"exitCode": 0})
        fresh = ledger.start("unit", "all", "vitest", [], [])
        self.assertIsNone(fresh["report"])
        self.assertEqual([r["status"] for r in ledger.history], ["passed", "running"])
