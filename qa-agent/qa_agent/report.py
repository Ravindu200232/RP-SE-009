"""The QA record: what ran, what it proved, and what is still open.

One JSON file per project under `.agentforge/qa/`, in exactly the shape the
studio's Testing tab renders. It is written by the QA agent and read by the
server, so the report is the contract between them - not a second summary
generated for display.

The PDF is the same record, printable, for anyone who has to hand the evidence
to someone who will not open the studio.
"""
from __future__ import annotations

import json
import re
import time
import os
import tempfile
from pathlib import Path

QA_DIR = ".agentforge/qa"
RESULTS = "results.json"


def qa_path(project_dir: Path | str) -> Path:
    return Path(project_dir) / QA_DIR / RESULTS


def read(project_dir: Path | str, project: str = "") -> dict:
    from . import artifacts
    path = qa_path(project_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return artifacts.recover(Path(project_dir), project)
    data.setdefault("project", project)
    return artifacts.enrich(Path(project_dir), data)


def write(project_dir: Path | str, payload: dict) -> Path:
    path = qa_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Readers may fetch while a test finishes. Never expose half a JSON file.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            json.dump(payload, stream, indent=2, ensure_ascii=False, default=str)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return path


def _runner_counts(output: str) -> dict | None:
    """Read Vitest's printed totals without inventing individual test cases."""
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    cases = re.search(r"^\s*Tests\s+(.+)$", output, re.M)
    if not cases:
        return None
    values = {status: int(count) for count, status in re.findall(
        r"(\d+)\s+(passed|failed|skipped|todo)", cases.group(1))}
    if not values:
        return None
    total = re.search(r"\((\d+)\)", cases.group(1))
    files = re.search(r"^\s*Test Files\s+.*?\((\d+)\)", output, re.M)
    return {"source": "runner-summary", "numPassedTests": values.get("passed", 0),
            "numFailedTests": values.get("failed", 0),
            "numPendingTests": values.get("skipped", 0),
            "numTodoTests": values.get("todo", 0),
            "numTotalTests": int(total.group(1)) if total else sum(values.values()),
            "numTotalTestSuites": int(files.group(1)) if files else 0}


def from_evidence(*, project: str, project_dir: Path, evidence: dict,
                  security: dict, complete: bool) -> dict:
    """Publish checks the builder already ran; never start a model or a test."""
    from . import harness
    from .e2e import E2EResult, journeys_from_evidence
    from .unit import UnitResult, failures_of

    suites = [row for row in evidence.get("suites", [])
              if row.get("status") not in ("retired", "outdated")]
    unit_rows = sorted((row for row in suites if row.get("kind") == "unit"),
                       key=lambda row: row.get("sequence", 0))
    latest = unit_rows[-1] if unit_rows else {}
    unit_report = latest.get("report") or _runner_counts(latest.get("output", ""))
    unit = UnitResult(ran=bool(unit_rows), report=unit_report,
                      coverage=latest.get("coverage"))
    unit.unresolved = [{"case": row.get("suite", "unit"),
                        "message": row.get("reason") or row.get("output", ""),
                        "diagnosis": row.get("status", "unknown")}
                       for row in suites if row.get("status") == "failed"]
    unit.unresolved += [{"case": row.get("view", "Screenshot"), "diagnosis": "visual",
                         "message": row.get("findings", "Visual review failed")}
                        for row in evidence.get("visuals", []) if row.get("status") == "failed"]
    unit.unresolved += failures_of(unit_report)
    e2e = E2EResult(journeys=journeys_from_evidence({"suites": [row for row in suites if row.get("status") != "running"]}))
    e2e.failures = [{"case": row.get("suite"), "message": row.get("reason") or row.get("output", "")}
                    for row in suites if row.get("kind") == "e2e" and row.get("status") == "failed"]
    e2e.ran = bool(e2e.journeys)
    runtime = [row.get("reason") or row.get("output", "") for row in suites
               if row.get("kind") == "runtime" and row.get("status") == "failed"]
    stages = tuple(kind for kind in ("unit", "e2e", "runtime")
                   if any(row.get("kind") == kind and row.get("status") in ("passed", "failed") for row in suites))
    if security is not None:
        stages += ("security",)
    data = assemble(project=project, project_dir=project_dir, unit=unit, e2e=e2e,
                    security=security, evidence=evidence, runtime=runtime,
                    manifest={}, tests=harness.collect_test_sources(project_dir),
                    history=[], stages=stages, complete=complete)
    data["timeline"] = evidence.get("history", [])
    data["unitEvidenceStatus"] = latest.get("status")
    # Older results remain inspectable, but never become current test status.
    if not unit_report:
        older = sorted((r for r in evidence.get("suites", [])
                        if r.get("kind") == "unit" and r.get("status") == "outdated"),
                       key=lambda r: r.get("sequence", 0))
        if older:
            data["savedVitest"] = older[-1].get("report") or _runner_counts(older[-1].get("output", ""))
            data["unitEvidenceStatus"] = "outdated"
    from .artifacts import enrich
    return enrich(project_dir, data)


class LiveReport:
    """Persist changed evidence after tools finish, including interrupted builds."""

    def __init__(self, project_dir, evidence, publish, on_error):
        self.root, self.evidence = Path(project_dir), evidence
        self.publish, self.on_error = publish, on_error
        self.previous = None

    def __call__(self, event, payload):
        if event not in ("tool:end", "agent:done", "agent:error", "agent:abort"):
            return
        if not self.evidence.active:
            return
        signature = self.evidence.fingerprint()
        if signature == self.previous:
            return
        try:
            data = from_evidence(project=self.root.name, project_dir=self.root,
                                 evidence=self.evidence.summary(), security=None, complete=False)
            write(self.root, data)
            self.previous = signature
            self.publish({"type": "test_report", "project": self.root.name,
                          "generated": data["generated"], "complete": False})
        except Exception as error:
            self.on_error(error)


def assemble(*, project: str, project_dir: Path, unit, e2e, security: dict,
             evidence: dict, runtime: list, manifest: dict, tests: dict,
             history: list, performance: dict | None = None,
             stages: tuple = (), complete: bool = True) -> dict:
    """Build the studio-shaped record from the stage results.

    `stages` names what has actually run. A record written half way through a
    verification is real evidence about the stages it names and says nothing
    about the ones it does not - which is different from, and much more useful
    than, no record at all.
    """
    return {
        "project": project,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stages": list(stages),
        "complete": bool(complete),
        "vitest": unit.report,
        "manifest": manifest,
        "tests": tests,
        "history": history,
        "performance": performance or {"scores": {}, "metrics": {}},
        "report": {
            "unit": {"deleted": unit.deleted, "skipped": unit.skipped,
                     "coverage": unit.coverage, "reason": unit.reason},
            "suite": {"unresolved": unit.unresolved, "suspects": unit.suspects,
                      "quarantined": [], "failures": unit.unresolved},
            "e2e": e2e.as_report(),
            "runtime": runtime,
            "security": security,
            "evidence": evidence,
        },
    }


def append_history(existing: dict, rounds: list) -> list:
    """Round-one rates, kept across runs so a trend is visible.

    Only the first round of each run is recorded: later rounds measure repair,
    not what the generated tests did on their own, and mixing the two makes the
    trend meaningless.
    """
    history = list(existing.get("history") or [])
    if rounds:
        history.append(rounds[0])
    return history[-40:]


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def build_pdf(qa: dict, out: Path | str, project: str = "") -> Path:
    """Render the record as a printable report."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=20, spaceAfter=4)
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=9,
                         textColor=colors.HexColor("#64748B"), spaceAfter=14)
    head = ParagraphStyle("h", parent=styles["Heading2"], fontSize=12, spaceBefore=14,
                          spaceAfter=6, textColor=colors.HexColor("#0F172A"))
    body = ParagraphStyle("b", parent=styles["Normal"], fontSize=9, leading=13)
    mono = ParagraphStyle("m", parent=styles["Normal"], fontName="Courier", fontSize=7.5,
                          leading=10, textColor=colors.HexColor("#334155"))

    def table(rows, widths):
        t = Table(rows, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F8FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    report = qa.get("report") or {}
    unit_counts = _unit_counts(qa.get("vitest"))
    unit_label = "files" if (qa.get("vitest") or {}).get("fileResults") is not None else "cases"
    e2e = report.get("e2e") or {}
    security = report.get("security") or {}
    flow = [
        Paragraph(f"Test report — {qa.get('project') or project}", title),
        Paragraph(f"Generated {qa.get('generated', '')} · "
                  f"unit {unit_counts['passed']}/{unit_counts['total']} {unit_label} passing · "
                  f"end-to-end {e2e.get('stage_passed', 0)}/{e2e.get('stage_total', 0)} stages",
                  sub),
        Paragraph("Summary", head),
        table([["layer", "result", "detail"],
               ["Unit", _verdict(unit_counts["failed"] == 0 and unit_counts["total"] > 0),
                f"{unit_counts['passed']} {unit_label} passing, {unit_counts['failed']} failing, "
                f"{unit_counts['skipped']} skipped across {unit_counts['files']} file(s)"],
               ["End-to-end", _verdict(e2e.get("failed", 1) == 0 and e2e.get("total", 0) > 0),
                f"{e2e.get('passed', 0)}/{e2e.get('total', 0)} journeys, "
                f"{e2e.get('stage_passed', 0)}/{e2e.get('stage_total', 0)} stages"],
               ["Security", _verdict(not security.get("findings")) if report.get("security") else "UNRECORDED",
                f"{len(security.get('findings') or [])} finding(s)"]],
              [70 * mm, 25 * mm, 75 * mm]),
    ]
    if qa.get("provenance"):
        flow += [Paragraph(_escape(qa["provenance"]), body), Spacer(1, 5 * mm)]
    saved_files = (qa.get("vitest") or {}).get("fileResults") or []
    if saved_files:
        flow += [Paragraph("Saved unit file outcomes", head),
                 Paragraph(_escape(qa["vitest"].get("note", "")), body),
                 table([["file", "status", "duration (ms)"]] +
                       [[_short(row["file"]), row["status"], str(round(row.get("duration") or 0))]
                        for row in saved_files], [115 * mm, 25 * mm, 30 * mm])]

    suites = (qa.get("vitest") or {}).get("testResults") or []
    if suites:
        flow += [Paragraph("Unit suites", head),
                 table([["file", "passing", "failing"]] +
                       [[_short(s.get("name") or ""),
                         str(sum(1 for c in (s.get("assertionResults") or [])
                                 if c.get("status") == "passed")),
                         str(sum(1 for c in (s.get("assertionResults") or [])
                                 if c.get("status") == "failed"))]
                        for s in suites[:40]],
                       [120 * mm, 25 * mm, 25 * mm])]

    flows = e2e.get("flows") or []
    if flows:
        flow += [Paragraph("End-to-end journeys", head)]
        for journey in flows[:12]:
            flow.append(Paragraph(f"<b>{journey.get('title', '')}</b> — "
                                  f"{journey.get('stage_passed', 0)}/"
                                  f"{journey.get('stage_total', 0)} stages", body))
            for stage in (journey.get("stages") or [])[:20]:
                mark = {"passed": "PASS", "failed": "FAIL"}.get(stage["status"], "----")
                flow.append(Paragraph(f"{mark}  {_escape(stage['name'])}", mono))
            flow.append(Spacer(1, 6))

    unresolved = (report.get("suite") or {}).get("unresolved") or []
    if unresolved:
        flow += [PageBreak(), Paragraph("Left unresolved", head),
                 table([["case", "diagnosis", "message"]] +
                       [[_escape(u.get("case", ""))[:60], u.get("diagnosis", ""),
                         _escape(u.get("message", ""))[:120]] for u in unresolved[:30]],
                       [55 * mm, 25 * mm, 90 * mm])]

    findings = security.get("findings") or []
    if findings:
        flow += [Paragraph("Security findings", head),
                 table([["check", "file:line", "detail"]] +
                       [[f.get("code", ""), f"{f.get('file', '')}:{f.get('line', '')}",
                         _escape(f.get("detail", ""))[:110]] for f in findings[:40]],
                       [45 * mm, 55 * mm, 70 * mm])]

    flow.append(Paragraph(
        "Evidence in this report is the exit status of commands and browser journeys that "
        "actually ran. It is not a guarantee that the application is free of defects.", sub))

    SimpleDocTemplate(str(out), pagesize=A4, title=f"{qa.get('project', '')} test report",
                      leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(flow)
    return out


def _unit_counts(vitest: dict | None) -> dict:
    if isinstance((vitest or {}).get("fileResults"), list):
        rows = vitest["fileResults"]
        return {"passed": sum(r.get("status") == "passed" for r in rows),
                "failed": sum(r.get("status") == "failed" for r in rows),
                "skipped": 0, "total": len(rows), "files": len(rows)}
    if (vitest or {}).get("source") == "runner-summary":
        return {"passed": vitest["numPassedTests"], "failed": vitest["numFailedTests"],
                "skipped": vitest["numPendingTests"] + vitest["numTodoTests"],
                "total": vitest["numTotalTests"], "files": vitest["numTotalTestSuites"]}
    suites = (vitest or {}).get("testResults") or []
    cases = [c for s in suites for c in (s.get("assertionResults") or [])]
    return {"passed": sum(1 for c in cases if c.get("status") == "passed"),
            "failed": sum(1 for c in cases if c.get("status") == "failed"),
            "skipped": sum(1 for c in cases if c.get("status") in ("skipped", "pending", "todo")),
            "total": len(cases), "files": len(suites)}


def _verdict(ok: bool) -> str:
    return "PASS" if ok else "OPEN"


def _short(path: str) -> str:
    return str(path).replace("\\", "/").split("/test/")[-1][:80]


def _escape(text: str) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
