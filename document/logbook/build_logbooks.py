"""Render the four RP-SE-009 periodic log books to HTML and PDF.

    python document/logbook/build_logbooks.py

Each student gets one A4 document in the departmental log entry format: project
and student details, a period summary, the date-wise work table split by month
with a supervisor signature block after every month, a consolidated monthly
verification table, the plan for the next evaluation period, and the closing
declaration and signatures.

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
  color: #111;
  background: #fff;
}

.sheet { max-width: 182mm; margin: 0 auto; }

/* ---------- masthead ---------- */
.masthead {
  text-align: center;
  border-bottom: 2.2pt solid #111;
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
  color: #333;
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
.masthead .sub {
  font-size: 10pt;
  color: #222;
}
.masthead .sub strong { font-weight: 700; }

/* ---------- section headings ---------- */
h2 {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 10.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .5pt;
  margin: 16pt 0 6pt;
  padding: 3.5pt 6pt;
  background: #ececec;
  border-left: 3.5pt solid #111;
  break-after: avoid;
}
h2 .n { color: #444; margin-right: 5pt; }

/* ---------- tables ---------- */
table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 4pt;
}
th, td {
  border: .7pt solid #555;
  padding: 4pt 6pt;
  text-align: left;
  vertical-align: top;
}
thead th {
  background: #ddd;
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 9pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .3pt;
}
thead { display: table-header-group; }
tr { break-inside: avoid; }

/* details block */
table.details th {
  width: 33%;
  background: #f3f3f3;
  font-weight: 700;
}

/* work log */
table.work col.c-date { width: 20mm; }
table.work col.c-no { width: 11mm; }
table.work td.date { white-space: nowrap; font-variant-numeric: tabular-nums; }
table.work td.no { text-align: center; color: #333; }
table.work tbody tr:nth-child(even) td { background: #fafafa; }

/* month grouping */
/* A month is allowed to flow across a page break - holding one together pushes
   whole blocks onto fresh pages and leaves half-empty sheets. The header row
   repeats on the continuation, the title never ends a page on its own, and the
   signature block below is what stays unbroken. */
.month {
  margin-top: 11pt;
}
.month-title {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 9.6pt;
  font-weight: 700;
  letter-spacing: .35pt;
  text-transform: uppercase;
  background: #111;
  color: #fff;
  padding: 3pt 7pt;
  break-after: avoid;
}
.month-title .count {
  float: right;
  font-weight: 400;
  font-size: 8.6pt;
  opacity: .85;
}

/* monthly supervisor sign-off */
table.signoff {
  margin-top: 0;
  margin-bottom: 2pt;
  break-inside: avoid;
}
table.signoff th {
  background: #f3f3f3;
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 8.4pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .25pt;
  text-align: center;
  padding: 3pt 4pt;
}
table.signoff td {
  height: 15mm;
  font-size: 9pt;
}
/* the consolidated roll-up repeats months already signed above, so it needs
   only enough room for an initial and a date */
table.signoff.compact td { height: 9.5mm; }
table.signoff td.rule {
  vertical-align: bottom;
  text-align: center;
  color: #777;
  font-size: 8pt;
  padding-bottom: 3pt;
}
.signoff-label {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 8.4pt;
  font-weight: 700;
  letter-spacing: .3pt;
  text-transform: uppercase;
  color: #111;
  background: #ececec;
  border: .7pt solid #555;
  border-bottom: none;
  padding: 3pt 7pt;
  break-after: avoid;
}

/* prose + lists */
p.summary { text-align: justify; margin: 0 0 6pt; }
ol.plan, ul.plan { margin: 4pt 0 4pt 16pt; padding: 0; }
ol.plan li, ul.plan li { margin-bottom: 3.5pt; text-align: justify; }

/* declaration + final signatures */
.declaration {
  border: .7pt solid #555;
  padding: 7pt 9pt;
  font-size: 9.6pt;
  text-align: justify;
  background: #fafafa;
}
table.finalsign { margin-top: 8pt; break-inside: avoid; }
table.finalsign td { height: 22mm; vertical-align: bottom; padding-bottom: 4pt; }
table.finalsign .role {
  font-family: "Liberation Sans", Arial, sans-serif;
  font-size: 8.4pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .3pt;
}
table.finalsign .line { border-top: .7pt solid #111; margin-top: 12pt; padding-top: 2.5pt; font-size: 8.6pt; color: #333; }

.note {
  margin-top: 9pt;
  font-size: 8.4pt;
  color: #444;
  border-top: .7pt dashed #999;
  padding-top: 5pt;
}
.footer-id {
  margin-top: 10pt;
  font-size: 8pt;
  color: #666;
  text-align: center;
  border-top: .7pt solid #bbb;
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
      <div class="signoff-label">Monthly Verification — {E(name)}</div>
      <table class="signoff">
        <thead>
          <tr>
            <th style="width:44%">Supervisor's Comments for {E(name)}</th>
            <th style="width:28%">Supervisor's Signature</th>
            <th style="width:28%">Co-Supervisor's Signature</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td></td>
            <td class="rule">Signature &amp; Date</td>
            <td class="rule">Signature &amp; Date</td>
          </tr>
        </tbody>
      </table>
    </div>"""


def monthly_summary_table(groups) -> str:
    rows = []
    for mkey, entries in groups:
        rows.append(
            f'        <tr><td>{E(MONTH_NAMES[mkey])}</td>'
            f'<td style="text-align:center">{len(entries)}</td>'
            f'<td></td><td></td></tr>'
        )
    total = sum(len(e) for _, e in groups)
    rows.append(
        f'        <tr><td><strong>Total</strong></td>'
        f'<td style="text-align:center"><strong>{total}</strong></td>'
        f'<td></td><td></td></tr>'
    )
    return f"""    <table class="signoff compact">
      <thead>
        <tr>
          <th style="width:26%;text-align:left">Month</th>
          <th style="width:14%">Entries Logged</th>
          <th style="width:30%">Supervisor's Signature</th>
          <th style="width:30%">Date</th>
        </tr>
      </thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>"""


def render(s) -> str:
    groups = group_by_month(s["entries"])

    blocks = []
    n = 1
    for mkey, rows in groups:
        blocks.append(month_block(mkey, rows, n))
        n += len(rows)

    plan = "\n".join(f"      <li>{E(item)}</li>" for item in s["next"])
    total = sum(len(e) for _, e in groups)

    title = (
        f"RP-SE-009 Periodic Log Book — {s['agent']} — {s['student']}"
    )

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

  <h2><span class="n">3.</span>Date-wise RP Work ({total} entries, verified monthly)</h2>
{"".join(blocks)}

  <h2><span class="n">4.</span>Consolidated Monthly Verification</h2>
{monthly_summary_table(groups)}

  <h2><span class="n">5.</span>Project Work Planned Before the Next Evaluation Period</h2>
  <ol class="plan">
{plan}
  </ol>

  <h2><span class="n">6.</span>Declaration and Signatures</h2>
  <div class="declaration">
    I certify that the work recorded in this log book for the period
    {E(PROJECT['period_label'])} was carried out by me as the individual component
    contribution to research project {E(PROJECT['project_id'])}, and that the group-level
    contributions recorded here were made jointly with the other project members.
  </div>

  <table class="finalsign">
    <tbody>
      <tr>
        <td style="width:50%">
          <span class="role">Student</span>
          <div class="line">{E(s['student'])} ({E(s['student_id'])}) — Signature &amp; Date</div>
        </td>
        <td style="width:50%">
          <span class="role">Supervisor</span>
          <div class="line">{E(PROJECT['supervisor'])} — Signature &amp; Date</div>
        </td>
      </tr>
      <tr>
        <td>
          <span class="role">Co-Supervisor</span>
          <div class="line">{E(PROJECT['co_supervisor'])} — Signature &amp; Date</div>
        </td>
        <td>
          <span class="role">Overall Supervisor Comments</span>
          <div class="line">Comments</div>
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
