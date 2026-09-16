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
    """Read Vitest's printed totals without inventing individual test cases.

    `npm test --workspaces` runs the runner once per workspace and prints a
    summary for each, so a microservices project prints four. Reading only the
    first reported one service's tests as the whole project's: eight passing
    across one file, for a repository with four services and a client.
    """
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    lines = re.findall(r"^\s*Tests\s+(.+)$", output, re.M)
    if not lines:
        return None

    totals = {"passed": 0, "failed": 0, "skipped": 0, "todo": 0}
    counted = 0
    seen = False
    for line in lines:
        values = {status: int(count) for count, status in re.findall(
            r"(\d+)\s+(passed|failed|skipped|todo)", line)}
        if not values:
            continue
        seen = True
        for status, count in values.items():
            totals[status] += count
        total = re.search(r"\((\d+)\)", line)
        counted += int(total.group(1)) if total else sum(values.values())
    if not seen:
        return None

    files = sum(int(match) for match in
                re.findall(r"^\s*Test Files\s+.*?\((\d+)\)", output, re.M))
    return {"source": "runner-summary", "numPassedTests": totals["passed"],
            "numFailedTests": totals["failed"],
            "numPendingTests": totals["skipped"],
            "numTodoTests": totals["todo"],
            "numTotalTests": counted,
            "numTotalTestSuites": files}


def _size(report: dict | None) -> tuple:
    """How much of the project one unit report actually covers.

    A run that wrote a machine-readable report beats one that only printed
    totals, because only the first carries the individual cases; after that,
    more tests is a wider run.
    """
    report = report or {}
    return (bool(report.get("testResults")), int(report.get("numTotalTests") or 0))


def _report_size(row: dict) -> tuple:
    return _size(row.get("report") or _runner_counts(row.get("output", "")))


def _unit_file(row: dict) -> str:
    """One test file, however whoever wrote the row spelled its path."""
    return str(row.get("name") or row.get("testFilePath") or "").replace("\\", "/").lower()


def _unit_totals(rows: list) -> dict:
    """Vitest's summary fields, recomputed from the rows they describe."""
    from .unit import counts_of
    counts = counts_of({"testResults": rows})
    failed_files = sum(1 for row in rows if row.get("status") == "failed")
    return {
        "numTotalTests": counts["total"], "numPassedTests": counts["passed"],
        "numFailedTests": counts["failed"], "numPendingTests": counts["skipped"],
        "numTodoTests": 0,
        "numTotalTestSuites": len(rows), "numFailedTestSuites": failed_files,
        "numPassedTestSuites": len(rows) - failed_files,
        "success": counts["failed"] == 0 and failed_files == 0,
    }


def _still_on_disk(project_dir: Path | str, name: str) -> bool:
    """Is the file this result describes still part of the project?

    A test that was deleted stops being evidence of anything. Where the path
    cannot be resolved at all the row is kept: an unreadable name is not proof
    the file is gone.
    """
    if not name:
        return False
    path = Path(name)
    try:
        if not path.is_absolute():
            path = Path(project_dir) / name
        return path.exists()
    except OSError:
        return True


def carry_unit(saved: dict | None, current: dict | None,
               project_dir: Path | str | None = None) -> dict | None:
    """A suite is everything proved so far, not whatever this run re-ran.

    Adding one page runs that page's tests, and the report written afterwards
    became the project's whole test status: a hundred passing tests turned into
    three, and every earlier result read as work undone.

    A file this run did not touch keeps the result it last had. A file it did
    run is replaced by what just happened, because that is now what is true
    about it - a test that has started failing must never be answered with the
    last time it passed.
    """
    old = (saved or {}).get("testResults")
    new = (current or {}).get("testResults")
    if not isinstance(old, list) or not old:
        return current or saved or None
    if not isinstance(new, list) or not new:
        # Nothing at file granularity to merge into; keep whichever says more.
        return max(current or {}, saved, key=_size) or None

    ran = {_unit_file(row) for row in new if _unit_file(row)}
    rows = [row for row in old
            if _unit_file(row) and _unit_file(row) not in ran
            and (project_dir is None
                 or _still_on_disk(project_dir, row.get("name") or row.get("testFilePath")))]
    kept = len(rows)
    rows += new

    merged = {key: value for key, value in current.items() if key != "testResults"}
    merged["testResults"] = rows
    merged.update(_unit_totals(rows))
    if kept:
        merged["carriedForward"] = kept
    return merged


def carry_journeys(saved: dict | None, current: list) -> list:
    """A journey nobody reran is still the last thing known about it."""
    from .e2e import Journey
    flows = (((saved or {}).get("report") or {}).get("e2e") or {}).get("flows") or []
    ran = {str(journey.title).strip().lower() for journey in current}
    kept = []
    for flow in flows:
        title = str(flow.get("title") or "").strip()
        if not title or title.lower() in ran:
            continue
        kept.append(Journey(title=title, role=flow.get("role") or "user",
                            flow=flow.get("flow") or "",
                            stages=list(flow.get("stages") or []),
                            blocked_upstream=bool(flow.get("blocked_upstream"))))
    return kept + list(current)


def _saved(project_dir: Path | str) -> dict:
    """The report this project already had, exactly as it was written."""
    try:
        data = json.loads(qa_path(project_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _widest_unit_run(rows: list) -> dict:
    """The run that says the most about the project, not the last one taken.

    A verification runs several unit suites - the scaffold baseline, the whole
    workspace, then one service on its own while it is repaired - and every one
    of them is current at this revision. Reading the last of those published
    whichever narrow suite happened to be repaired last as the project's whole
    result.
    """
    return max(rows, key=_report_size, default={})


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
    latest = _widest_unit_run(unit_rows)
    # What this run proved, over what the project had already proved. One run
    # is not the project's test status; every run so far is.
    saved = _saved(project_dir)
    unit_report = carry_unit(saved.get("vitest"),
                             latest.get("report") or _runner_counts(latest.get("output", "")),
                             project_dir)
    unit = UnitResult(ran=bool(unit_rows) or bool(unit_report), report=unit_report,
                      coverage=latest.get("coverage")
                              or ((saved.get("report") or {}).get("unit") or {}).get("coverage"))
    unit.unresolved = [{"case": row.get("suite", "unit"),
                        "message": row.get("reason") or row.get("output", ""),
                        "diagnosis": row.get("status", "unknown")}
                       for row in suites if row.get("status") == "failed"]
    unit.unresolved += [{"case": row.get("view", "Screenshot"), "diagnosis": "visual",
                         "message": row.get("findings", "Visual review failed")}
                        for row in evidence.get("visuals", []) if row.get("status") == "failed"]
    unit.unresolved += failures_of(unit_report)
    e2e = E2EResult(journeys=carry_journeys(
        saved, journeys_from_evidence({"suites": [row for row in suites if row.get("status") != "running"]})))
    e2e.failures = [{"case": row.get("suite"), "message": row.get("reason") or row.get("output", "")}
                    for row in suites if row.get("kind") == "e2e" and row.get("status") == "failed"]
    e2e.ran = bool(e2e.journeys)
    runtime = [row.get("reason") or row.get("output", "") for row in suites
               if row.get("kind") == "runtime" and row.get("status") == "failed"]
    if security is None:
        # A scan the project has already had is not undone by a run that did
        # not repeat it.
        security = ((saved.get("report") or {}).get("security")) or None
    # What this run proved, plus what earlier runs already had. A stage the
    # project has been through is real evidence even when today's edit did not
    # repeat it.
    proved = {row.get("kind") for row in suites
              if row.get("status") in ("passed", "failed")}
    proved |= set(saved.get("stages") or [])
    stages = tuple(kind for kind in ("unit", "e2e", "runtime") if kind in proved)
    if security is not None:
        stages += ("security",)
    perf = evidence.get("performance") if (evidence.get("performance") and evidence.get("performance", {}).get("scores")) else saved.get("performance")
    data = assemble(project=project, project_dir=project_dir, unit=unit, e2e=e2e,
                    security=security, evidence=evidence, runtime=runtime,
                    manifest={}, tests=harness.collect_test_sources(project_dir),
                    history=[], performance=perf, stages=stages, complete=complete)
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
