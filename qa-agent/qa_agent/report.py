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
import time
from pathlib import Path

QA_DIR = ".agentforge/qa"
RESULTS = "results.json"


def qa_path(project_dir: Path | str) -> Path:
    return Path(project_dir) / QA_DIR / RESULTS


def read(project_dir: Path | str, project: str = "") -> dict:
    path = qa_path(project_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"error": "no test results for this project", "project": project}
    data.setdefault("project", project)
    return data


def write(project_dir: Path | str, payload: dict) -> Path:
    path = qa_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")
    return path


def assemble(*, project: str, project_dir: Path, unit, e2e, security: dict,
             evidence: dict, runtime: list, manifest: dict, tests: dict,
             history: list, performance: dict | None = None) -> dict:
    """Build the studio-shaped record from the stage results."""
    return {
        "project": project,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
    e2e = report.get("e2e") or {}
    security = report.get("security") or {}
    flow = [
        Paragraph(f"Test report — {qa.get('project') or project}", title),
        Paragraph(f"Generated {qa.get('generated', '')} · "
                  f"unit {unit_counts['passed']}/{unit_counts['total']} passing · "
                  f"end-to-end {e2e.get('stage_passed', 0)}/{e2e.get('stage_total', 0)} stages",
                  sub),
        Paragraph("Summary", head),
        table([["layer", "result", "detail"],
               ["Unit", _verdict(unit_counts["failed"] == 0 and unit_counts["total"] > 0),
                f"{unit_counts['passed']} passing, {unit_counts['failed']} failing, "
                f"{unit_counts['skipped']} skipped across {unit_counts['files']} file(s)"],
               ["End-to-end", _verdict(e2e.get("failed", 1) == 0 and e2e.get("total", 0) > 0),
                f"{e2e.get('passed', 0)}/{e2e.get('total', 0)} journeys, "
                f"{e2e.get('stage_passed', 0)}/{e2e.get('stage_total', 0)} stages"],
               ["Security", _verdict(not security.get("findings")),
                f"{len(security.get('findings') or [])} finding(s)"]],
              [70 * mm, 25 * mm, 75 * mm]),
    ]

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
