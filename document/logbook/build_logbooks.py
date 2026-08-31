"""Render the four RP-SE-009 periodic log books to HTML and PDF.

    python document/logbook/build_logbooks.py

Each student gets one A4 document in the departmental log entry format: project
and student details, a period summary, the date-wise work table grouped by
month, the plan for the next evaluation period, and a single declaration and
signature block at the end.

The document is plain black and white throughout - no fills, no tints, no
colour - so it prints identically on any printer and photocopies cleanly.
Structure is carried by rule weight and type weight instead of shading.

PDFs are printed with the Chromium that ships with this environment, so the
output needs no external service. Set CHROME to override the binary.
"""
from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from logbook_data import MONTH_NAMES, MONTH_ORDER, PROJECT, STUDENTS  # noqa: E402

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    shutil.which("google-chrome") or "",
]

CSS = """
@page {
  size: A4;
  margin: 16mm 14mm 15mm 14mm;
}

* { box-sizing: border-box; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  margin: 0;
  font-family: "Liberation Serif", "Times New Roman", Times, serif;
  font-size: 10.5pt;
  line-height: 1.45;
  color: #000;
  background: #fff;
}

.sheet { max-width: 182mm; margin: 0 auto; }

/* ---------- masthead ---------- */
.masthead {
  text-align: center;
  border-bottom: 2pt solid #000;
  padding-bottom: 7pt;
  margin-bottom: 12pt;
}
.masthead .inst {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 12.5pt;
  font-weight: 700;
  letter-spacing: .35pt;
  text-transform: uppercase;
}
.masthead .fac {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 8.8pt;
  margin-top: 2pt;
  letter-spacing: .2pt;
}
.masthead h1 {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 13.5pt;
  font-weight: 700;
  margin: 9pt 0 3pt;
  letter-spacing: .2pt;
}
.masthead .sub { font-size: 10pt; }

/* ---------- section headings ---------- */
/* No tint behind a heading - a rule above and below separates it just as well
   and survives a photocopier. */
h2 {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 10.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .5pt;
  margin: 15pt 0 6pt;
  padding: 3pt 0 2.5pt;
  border-top: 1.4pt solid #000;
  border-bottom: .7pt solid #000;
  break-after: avoid;
}
h2 .n { margin-right: 6pt; }

/* ---------- tables ---------- */
table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 4pt;
}
th, td {
  border: .7pt solid #000;
  padding: 4pt 6pt;
  text-align: left;
  vertical-align: top;
}
thead th {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 9pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .3pt;
  border-bottom: 1.4pt solid #000;
}
thead { display: table-header-group; }
tr { break-inside: avoid; }

table.details th { width: 33%; font-weight: 700; }

table.work col.c-date { width: 20mm; }
table.work col.c-no { width: 11mm; }
table.work td.date { white-space: nowrap; font-variant-numeric: tabular-nums; }
table.work td.no { text-align: center; }

/* ---------- month grouping ---------- */
/* A month may flow across a page break - holding one together pushes whole
   blocks onto fresh pages and leaves half-empty sheets. The header row repeats
   on the continuation and the title never ends a page on its own. */
.month { margin-top: 11pt; }
.month-title {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 9.6pt;
  font-weight: 700;
  letter-spacing: .4pt;
  text-transform: uppercase;
  border-bottom: 1.4pt solid #000;
  padding: 0 1pt 2.5pt;
  margin-bottom: 3pt;
  break-after: avoid;
}
.month-title .count {
  float: right;
  font-weight: 400;
  font-size: 8.6pt;
}

/* ---------- prose and lists ---------- */
p.summary { text-align: justify; margin: 0 0 6pt; }
ol.plan { margin: 4pt 0 4pt 16pt; padding: 0; }
ol.plan li { margin-bottom: 3.5pt; text-align: justify; }

/* ---------- declaration and the single closing signature block ---------- */
.declaration {
  border: .7pt solid #000;
  padding: 7pt 9pt;
  font-size: 9.6pt;
  text-align: justify;
}
.comments-label {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 8.6pt;
  font-weight: 700;
  letter-spacing: .3pt;
  text-transform: uppercase;
  border: .7pt solid #000;
  border-bottom: none;
  padding: 3pt 7pt;
  margin-top: 9pt;
  break-after: avoid;
}
.comments-box {
  border: .7pt solid #000;
  height: 30mm;
  break-inside: avoid;
}
table.finalsign { margin-top: 10pt; break-inside: avoid; }
table.finalsign td {
  height: 26mm;
  vertical-align: bottom;
  padding: 4pt 7pt 5pt;
  text-align: center;
}
table.finalsign .line {
  border-top: .7pt solid #000;
  padding-top: 3pt;
  font-size: 9pt;
  font-weight: 700;
}
table.finalsign .role {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 8.2pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .3pt;
  margin-top: 1.5pt;
}
table.finalsign .datel { font-size: 8.4pt; margin-top: 5pt; }

.footer-id {
  margin-top: 11pt;
  font-size: 8pt;
  text-align: center;
  border-top: .7pt solid #000;
  padding-top: 4pt;
}
"""

E = html.escape


def month_key(ddmmyyyy: str) -> str:
    """'24.08.2026' -> '08.2026'."""
    _, mm, yyyy = ddmmyyyy.split(".")
    return f"{mm}.{yyyy}"


def group_by_month(entries):
    buckets = {k: [] for k in MONTH_ORDER}
    for date, work in entries:
        buckets.setdefault(month_key(date), []).append((date, work))
    return [(k, buckets[k]) for k in MONTH_ORDER if buckets.get(k)]


def details_table(s) -> str:
    rows = [
        ("Project ID", PROJECT["project_id"]),
        ("Research Topic", PROJECT["topic"]),
        ("Supervisor", PROJECT["supervisor"]),
        ("Co-Supervisor", PROJECT["co_supervisor"]),
        ("Student Name", s["student"]),
        ("Student Registration No.", s["student_id"]),
        ("Individual Component", s["component"]),
        ("Reporting Period", PROJECT["period_label"]),
        ("Phase Covered", PROJECT["phase"]),
    ]
    body = "\n".join(
        f'      <tr><th>{E(k)}</th><td>{E(v)}</td></tr>' for k, v in rows
    )
    return f'    <table class="details">\n{body}\n    </table>'


def month_block(mkey: str, rows, start_no: int) -> str:
    name = MONTH_NAMES[mkey]
    body = []
    for i, (date, work) in enumerate(rows, start=start_no):
        body.append(
            f'        <tr><td class="no">{i}</td>'
            f'<td class="date">{E(date)}</td>'
            f'<td>{E(work)}</td></tr>'
        )
    entries_word = "entry" if len(rows) == 1 else "entries"
    return f"""
    <div class="month">
      <div class="month-title">{E(name)}<span class="count">{len(rows)} {entries_word}</span></div>
      <table class="work">
        <colgroup><col class="c-no" /><col class="c-date" /><col /></colgroup>
        <thead>
          <tr><th>No.</th><th>Date</th><th>RP Work Carried Out</th></tr>
        </thead>
        <tbody>
{chr(10).join(body)}
        </tbody>
      </table>
    </div>"""


def render(s) -> str:
    groups = group_by_month(s["entries"])

    blocks = []
    n = 1
    for mkey, rows in groups:
        blocks.append(month_block(mkey, rows, n))
        n += len(rows)

    plan = "\n".join(f"      <li>{E(item)}</li>" for item in s["next"])
    total = sum(len(e) for _, e in groups)

    title = f"RP-SE-009 Periodic Log Book — {s['agent']} — {s['student']}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{E(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="sheet">

  <div class="masthead">
    <div class="inst">{E(PROJECT['institution'])}</div>
    <div class="fac">{E(PROJECT['faculty'])}</div>
    <h1>Research Project — Periodic Log Entry Form</h1>
    <div class="sub">
      Project <strong>{E(PROJECT['project_id'])}</strong>
      &nbsp;|&nbsp; {E(s['agent'])}
      &nbsp;|&nbsp; <strong>{E(s['student'])}</strong> ({E(s['student_id'])})
      &nbsp;|&nbsp; Reporting period <strong>{E(PROJECT['period_short'])}</strong>
    </div>
  </div>

  <h2><span class="n">1.</span>Project and Student Details</h2>
{details_table(s)}

  <h2><span class="n">2.</span>Summary of RP Work Carried Out During the Reporting Period</h2>
  <p class="summary">{E(s['summary'])}</p>

  <h2><span class="n">3.</span>Date-wise RP Work ({total} entries)</h2>
{"".join(blocks)}

  <h2><span class="n">4.</span>Project Work Planned Before the Next Evaluation Period</h2>
  <ol class="plan">
{plan}
  </ol>

  <h2><span class="n">5.</span>Declaration and Signatures</h2>
  <div class="declaration">
    I certify that the work recorded in this log book for the period
    {E(PROJECT['period_label'])} was carried out by me as the individual component
    contribution to research project {E(PROJECT['project_id'])}, and that the group-level
    contributions recorded here were made jointly with the other project members.
  </div>

  <div class="comments-label">Supervisor's Comments</div>
  <div class="comments-box"></div>

  <table class="finalsign">
    <tbody>
      <tr>
        <td style="width:34%">
          <div class="line">{E(s['student'])}</div>
          <div class="role">Student — {E(s['student_id'])}</div>
          <div class="datel">Date: ______________</div>
        </td>
        <td style="width:33%">
          <div class="line">{E(PROJECT['supervisor'])}</div>
          <div class="role">Supervisor</div>
          <div class="datel">Date: ______________</div>
        </td>
        <td style="width:33%">
          <div class="line">{E(PROJECT['co_supervisor'])}</div>
          <div class="role">Co-Supervisor</div>
          <div class="datel">Date: ______________</div>
        </td>
      </tr>
    </tbody>
  </table>

  <div class="footer-id">
    {E(PROJECT['project_id'])} &nbsp;·&nbsp; {E(PROJECT['topic'])} &nbsp;·&nbsp;
    {E(s['agent'])} &nbsp;·&nbsp; {E(s['student'])} &nbsp;·&nbsp; {E(PROJECT['period_short'])}
  </div>

</div>
</body>
</html>
"""


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    raise SystemExit("No Chromium/Chrome binary found; set CHROME=/path/to/chrome")


def to_pdf(chrome: str, html_path: Path, pdf_path: Path) -> None:
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise SystemExit(
            f"PDF generation failed for {html_path.name}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def main() -> None:
    chrome = find_chrome()
    for s in STUDENTS:
        base = f"RP-SE-009_LogBook_{s['slug']}_23Mar-25Aug2026"
        html_path = HERE / f"{base}.html"
        pdf_path = HERE / f"{base}.pdf"
        html_path.write_text(render(s), encoding="utf-8")
        to_pdf(chrome, html_path, pdf_path)
        kb = pdf_path.stat().st_size / 1024
        print(f"  {pdf_path.name}  ({len(s['entries'])} entries, {kb:.0f} KB)")


if __name__ == "__main__":
    main()
