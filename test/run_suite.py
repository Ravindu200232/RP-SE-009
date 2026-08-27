"""Run all repository tests and persist a compact, reviewable result."""
from __future__ import annotations

import io
import platform
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
RESULT_PATH = TEST_ROOT / "results" / "latest.txt"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def discover(folder: str) -> unittest.TestSuite:
    return unittest.defaultTestLoader.discover(
        start_dir=str(TEST_ROOT / folder),
        pattern="test_*.py",
        top_level_dir=str(ROOT),
    )


def main() -> int:
    unit_suite = discover("unit")
    integration_suite = discover("integration")
    unit_count = unit_suite.countTestCases()
    integration_count = integration_suite.countTestCases()
    suite = unittest.TestSuite((unit_suite, integration_suite))

    detail = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=detail, verbosity=2).run(suite)
    duration = time.perf_counter() - started

    status = "PASS" if result.wasSuccessful() else "FAIL"
    summary = [
        "AgentForge repository test result",
        "=================================",
        f"Status: {status}",
        f"Run at (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Command: python test/run_suite.py",
        f"Python: {platform.python_version()}",
        f"Unit tests: {unit_count}",
        f"Integration tests: {integration_count}",
        f"Total tests run: {result.testsRun}",
        f"Failures: {len(result.failures)}",
        f"Errors: {len(result.errors)}",
        f"Skipped: {len(result.skipped)}",
        f"Duration: {duration:.3f}s",
        "",
        "Detailed results",
        "----------------",
        detail.getvalue().rstrip(),
        "",
    ]
    report = "\n".join(summary)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(report, encoding="utf-8")
    print(report)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
