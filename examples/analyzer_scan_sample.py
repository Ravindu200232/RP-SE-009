"""Read-only example for running AgentForge's AnalyzerAgent.

Usage:
    python examples/analyzer_scan_sample.py path/to/generated-next-app

Add ``--probe`` only when that app is already running.  The probe performs
HTTP requests against ``--base-url``; it does not start the development server.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow this file to be launched directly from the repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from agents.analysis import AnalyzerAgent  # noqa: E402


class ReadOnlyArchitecture:
    """Small adapter exposing the state AnalyzerAgent needs for ``scan()``."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.write_seq = 0
        self.files: dict[str, str] = {}

        plan_file = project_dir / "plan.md"
        self.plan_md = (
            plan_file.read_text(encoding="utf-8", errors="replace")
            if plan_file.is_file()
            else ""
        )

        json_plan = project_dir / "plan.json"
        try:
            self.plan = json.loads(json_plan.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.plan = {}

    def lint_generated(self) -> list[str]:
        """The full ArchitectAgent supplies lint output; this demo supplies none."""
        return []


def print_report(report) -> None:
    print(f"Summary: {report.summary()}")
    print(f"Clean (no blockers): {report.is_clean()}")
    print(f"Routes discovered: {len(report.routes)}")
    print(f"Planned files: {len(report.planned)}")

    if report.findings:
        print("\nFindings:")
        for finding in report.findings:
            print(f"- {finding.line()}")
            if finding.fix:
                print(f"  Fix: {finding.fix}")
    else:
        print("\nNo findings.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AgentForge's deterministic analyzer without repairs."
    )
    parser.add_argument("project", type=Path, help="Generated Next.js project")
    parser.add_argument(
        "--probe", action="store_true", help="Also send HTTP requests to live routes"
    )
    parser.add_argument("--base-url", default="http://localhost:5173")
    args = parser.parse_args()

    project_dir = args.project.resolve()
    if not project_dir.is_dir():
        parser.error(f"project directory does not exist: {project_dir}")

    architecture = ReadOnlyArchitecture(project_dir)
    analyzer = AnalyzerAgent(
        architecture,
        project_dir,
        base_url=args.base_url,
        callbacks={
            "on_test": lambda status, name, detail: print(
                f"[runtime:{status}] {name} - {detail}"
            )
        },
    )

    # scan() only observes files. Unlike run(), it neither installs packages nor
    # asks the model to rewrite files.
    report = analyzer.scan()
    if args.probe:
        analyzer.probe_routes(report)

    print_report(report)
    return 1 if report.blockers() else 0


if __name__ == "__main__":
    raise SystemExit(main())
