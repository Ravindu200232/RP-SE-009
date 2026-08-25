"""Pre-E2E comparison of the approved plan and generated source."""
from __future__ import annotations

from agents.analysis.analyzer import AnalyzerReport


def run_plan_code_preflight(analyzer, *, repairable_major, elog, log) -> int:
    """Repair deterministic and semantic plan/code gaps before browser authoring."""
    try:
        scanned = analyzer.scan()
    except Exception as e:  # noqa: BLE001
        log.debug(f"pre-journey analysis scan: {e}")
        return 0

    findings = [
        f for f in (getattr(scanned, "findings", None) or [])
        if f.severity == "blocker" or f.code in repairable_major
    ]

    # One bounded semantic audit catches requirements that exist in the plan
    # but were never connected across the generated source.
    try:
        semantic = analyzer.unbuilt_promises(max_reads=5) or []
    except Exception as e:  # noqa: BLE001
        log.debug(f"pre-journey plan/code semantic audit: {e}")
        semantic = []

    seen = {(getattr(f, "code", ""), getattr(f, "path", ""),
             getattr(f, "message", "")) for f in findings}
    for finding in semantic:
        key = (getattr(finding, "code", ""), getattr(finding, "path", ""),
               getattr(finding, "message", ""))
        if key not in seen:
            findings.append(finding)
            seen.add(key)

    if not findings:
        elog("INFO", "   🔎 plan ↔ built-code preflight — requirements and source agree")
        return 0

    codes = ", ".join(sorted({getattr(f, "code", "") for f in findings
                              if getattr(f, "code", "")}))
    elog("INFO", f"   🔎 plan ↔ built-code preflight found {len(findings)} "
                 f"issue(s) before E2E authoring — {codes}")

    report = AnalyzerReport()
    report.findings = findings[:16]
    report.missing = []
    try:
        written = analyzer.repair(report) or 0
    except Exception as e:  # noqa: BLE001
        elog("WARN", f"   ⚠ pre-E2E plan/code repair failed: {e}")
        log.exception("pre-e2e plan/code repair")
        return 0


    if written:
        elog("INFO", f"   🔧 repaired {written} file(s) from plan/code evidence before journeys")
    return written
