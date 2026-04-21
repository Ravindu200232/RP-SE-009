import fs from "fs";
import path from "path";
import type { FinalReport } from "@/types";

export class HTMLReporter {
  generateHTML(report: FinalReport, outputDir: string): string {
    const html = this.buildHTML(report);
    const htmlPath = path.join(outputDir, "html", "report.html");
    fs.mkdirSync(path.dirname(htmlPath), { recursive: true });
    fs.writeFileSync(htmlPath, html, "utf-8");
    return htmlPath;
  }

  private buildHTML(report: FinalReport): string {
    const passText = report.qualityScore.passed ? "QUALITY GATE PASS" : "QUALITY GATE FAIL";
    const gateClass = report.qualityScore.passed ? "gate-pass" : "gate-fail";
    const blockers = report.majorBlockers.length > 0
      ? report.majorBlockers
      : ["No major blockers were recorded for this run."];
    const recommendations = report.recommendations.length > 0
      ? report.recommendations
      : ["No recommendations were generated for this run."];

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent 3 QA Report - ${esc(report.projectName)}</title>
<style>
  :root {
    --ink: #0f172a;
    --muted: #475569;
    --soft: #64748b;
    --line: #d7e3f4;
    --panel: #ffffff;
    --paper: #f4f7fb;
    --navy: #0f172a;
    --blue: #2563eb;
    --sky: #dbeafe;
    --violet: #7c3aed;
    --green: #16a34a;
    --amber: #d97706;
    --red: #dc2626;
    --shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", Arial, sans-serif;
    color: var(--ink);
    background:
      radial-gradient(circle at top left, rgba(37, 99, 235, 0.14), transparent 34%),
      radial-gradient(circle at top right, rgba(124, 58, 237, 0.10), transparent 26%),
      linear-gradient(180deg, #eaf1fb 0%, #f8fbff 55%, #eef4fb 100%);
    line-height: 1.55;
  }

  .shell {
    max-width: 1120px;
    margin: 0 auto;
    padding: 36px 20px 56px;
  }

  .paper {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 28px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .cover {
    position: relative;
    padding: 48px 48px 36px;
    background:
      linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 64, 175, 0.94)),
      linear-gradient(135deg, #0f172a, #1d4ed8);
    color: #fff;
  }

  .cover::after {
    content: "";
    position: absolute;
    inset: auto 0 0;
    height: 16px;
    background: linear-gradient(90deg, #38bdf8, #2563eb, #7c3aed, #ec4899);
  }

  .eyebrow {
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: rgba(219, 234, 254, 0.88);
  }

  .cover h1 {
    margin: 18px 0 10px;
    font-size: clamp(2rem, 3vw, 3rem);
    line-height: 1.08;
    letter-spacing: -0.03em;
  }

  .subtitle {
    max-width: 720px;
    font-size: 1rem;
    color: rgba(226, 232, 240, 0.92);
  }

  .meta-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-top: 28px;
  }

  .meta-card {
    background: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    padding: 16px;
    backdrop-filter: blur(10px);
  }

  .meta-card .label {
    font-size: 0.72rem;
    color: rgba(191, 219, 254, 0.82);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .meta-card .value {
    margin-top: 8px;
    font-size: 1rem;
    font-weight: 700;
    color: #fff;
    word-break: break-word;
  }

  .gate {
    display: inline-flex;
    margin-top: 24px;
    padding: 10px 18px;
    border-radius: 999px;
    font-size: 0.9rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .gate-pass {
    background: rgba(34, 197, 94, 0.16);
    border: 1px solid rgba(34, 197, 94, 0.32);
    color: #dcfce7;
  }

  .gate-fail {
    background: rgba(239, 68, 68, 0.16);
    border: 1px solid rgba(239, 68, 68, 0.30);
    color: #fee2e2;
  }

  .content {
    padding: 36px 48px 48px;
    background:
      linear-gradient(180deg, rgba(219, 234, 254, 0.20), transparent 28%),
      var(--panel);
  }

  .section {
    margin-top: 28px;
    padding-top: 4px;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
    font-size: 1.2rem;
    font-weight: 800;
    letter-spacing: -0.01em;
    color: var(--ink);
  }

  .section-title::before {
    content: "";
    width: 12px;
    height: 32px;
    border-radius: 999px;
    background: linear-gradient(180deg, #2563eb, #7c3aed);
  }

  .abstract-box,
  .note,
  .list-panel,
  .table-wrap {
    background: linear-gradient(180deg, #ffffff, #f9fbff);
    border: 1px solid var(--line);
    border-radius: 22px;
    box-shadow: 0 14px 32px rgba(37, 99, 235, 0.08);
  }

  .abstract-box {
    padding: 24px 26px;
  }

  .abstract-box p {
    margin: 0;
    color: var(--muted);
  }

  .index-terms {
    margin-top: 16px;
    padding: 16px 18px;
    border-left: 6px solid var(--blue);
    background: var(--sky);
    border-radius: 16px;
    color: #1e3a8a;
    font-size: 0.95rem;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
  }

  .card {
    position: relative;
    padding: 18px 18px 18px 20px;
    border: 1px solid var(--line);
    border-radius: 20px;
    background: linear-gradient(180deg, #ffffff, #f8fbff);
    overflow: hidden;
  }

  .card::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 8px;
    background: var(--card-accent, var(--blue));
  }

  .card .label {
    font-size: 0.72rem;
    color: var(--soft);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .card .value {
    margin-top: 10px;
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }

  .card .sub {
    margin-top: 8px;
    color: var(--muted);
    font-size: 0.9rem;
  }

  .facts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px 18px;
    margin-top: 18px;
  }

  .fact {
    padding: 14px 16px;
    border: 1px solid var(--line);
    border-radius: 16px;
    background: #f8fbff;
  }

  .fact .name {
    font-size: 0.74rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--soft);
  }

  .fact .desc {
    margin-top: 6px;
    color: var(--ink);
    font-size: 0.95rem;
  }

  .score-list {
    display: grid;
    gap: 14px;
  }

  .score-row {
    display: grid;
    grid-template-columns: 220px 1fr 48px;
    align-items: center;
    gap: 16px;
  }

  .score-row .name {
    font-weight: 700;
    color: var(--ink);
    font-size: 0.95rem;
  }

  .bar {
    height: 12px;
    border-radius: 999px;
    background: #dbe6f4;
    overflow: hidden;
  }

  .fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--bar-color, #2563eb), color-mix(in srgb, var(--bar-color, #2563eb) 56%, white));
  }

  .score-value {
    text-align: right;
    font-weight: 800;
    color: var(--bar-color, var(--blue));
  }

  .table-wrap {
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: #fff;
    font-size: 0.74rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    text-align: left;
    padding: 14px 16px;
  }

  td {
    padding: 14px 16px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.95rem;
    vertical-align: top;
  }

  tbody tr:nth-child(even) td {
    background: #f8fbff;
  }

  .list-panel {
    padding: 18px 22px;
  }

  .list-panel h3 {
    margin: 0 0 12px;
    font-size: 0.98rem;
    color: var(--ink);
  }

  .list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .list li {
    position: relative;
    padding: 10px 0 10px 22px;
    border-top: 1px solid var(--line);
    color: var(--muted);
  }

  .list li:first-child {
    border-top: 0;
  }

  .list li::before {
    content: "";
    position: absolute;
    left: 2px;
    top: 17px;
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: linear-gradient(180deg, #2563eb, #7c3aed);
  }

  .note {
    padding: 16px 18px;
    background: linear-gradient(180deg, #fff9e8, #fff4cf);
    color: #92400e;
  }

  .footer {
    margin-top: 34px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
    color: var(--soft);
    font-size: 0.86rem;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  @media (max-width: 900px) {
    .meta-grid,
    .cards,
    .facts {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .score-row {
      grid-template-columns: 1fr;
      gap: 8px;
    }

    .score-value {
      text-align: left;
    }
  }

  @media (max-width: 640px) {
    .shell {
      padding: 16px 12px 36px;
    }

    .cover,
    .content {
      padding-left: 20px;
      padding-right: 20px;
    }

    .meta-grid,
    .cards,
    .facts {
      grid-template-columns: 1fr;
    }
  }

  @media print {
    body {
      background: #fff;
    }

    .shell {
      max-width: none;
      padding: 0;
    }

    .paper {
      border: 0;
      box-shadow: none;
      border-radius: 0;
    }
  }
</style>
</head>
<body>
  <div class="shell">
    <article class="paper">
      <section class="cover">
        <div class="eyebrow">Agent 3 QA Platform</div>
        <h1>Quality Assurance Report</h1>
        <p class="subtitle">Colorful IEEE-style assessment designed for traceability review, engineering handoff, and release decision support.</p>
        <div class="gate ${gateClass}">${passText}</div>
        <div class="meta-grid">
          <div class="meta-card">
            <div class="label">Project</div>
            <div class="value">${esc(report.projectName)}</div>
          </div>
          <div class="meta-card">
            <div class="label">Detected Stack</div>
            <div class="value">${esc(report.projectSummary.detectedStack)}</div>
          </div>
          <div class="meta-card">
            <div class="label">Analysis Date</div>
            <div class="value">${esc(this.formatDate(report.analysisDate))}</div>
          </div>
          <div class="meta-card">
            <div class="label">Run ID</div>
            <div class="value">${esc(report.runId)}</div>
          </div>
        </div>
      </section>

      <section class="content">
        <section class="section">
          <div class="section-title">Abstract</div>
          <div class="abstract-box">
            <p>${esc(this.abstractText(report))}</p>
            <div class="index-terms"><strong>Index Terms:</strong> quality assurance, traceability, unit testing, integration testing, security findings, release readiness</div>
          </div>
        </section>

        <section class="section">
          <div class="section-title">1. Executive Overview</div>
          <div class="cards">
            ${this.metricCard("Overall QA Score", `${report.qualityScore.overall}/100`, report.qualityScore.passed ? "Quality gate passed" : "Quality gate failed", report.qualityScore.passed ? "#16a34a" : "#dc2626")}
            ${this.metricCard("Requirement Coverage", `${report.requirementsSummary.coveragePercent}%`, `${report.requirementsSummary.implemented} implemented`, "#2563eb")}
            ${this.metricCard("Security Findings", `${report.securitySummary.total}`, `${report.securitySummary.critical} critical`, report.securitySummary.critical > 0 ? "#dc2626" : "#0f766e")}
            ${this.metricCard("Files Analyzed", `${report.projectSummary.totalFiles}`, report.projectSummary.frameworks.join(", ") || "No frameworks detected", "#7c3aed")}
          </div>
          <div class="facts">
            ${this.factItem("Frameworks", report.projectSummary.frameworks.join(", ") || "None detected")}
            ${this.factItem("TypeScript", report.projectSummary.hasTypeScript ? "Yes" : "No")}
            ${this.factItem("Python", report.projectSummary.hasPython ? "Yes" : "No")}
            ${this.factItem("Project Path", report.projectPath)}
          </div>
        </section>

        <section class="section">
          <div class="section-title">2. Requirements and Traceability</div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Interpretation</th>
                </tr>
              </thead>
              <tbody>
                ${this.tableRow("Total Requirements", String(report.requirementsSummary.total), "All parsed functional and non-functional requirements")}
                ${this.tableRow("Implemented", String(report.requirementsSummary.implemented), "Requirements with direct implementation evidence")}
                ${this.tableRow("Partially Implemented", String(report.requirementsSummary.partiallyImplemented), "Requirements with incomplete validation")}
                ${this.tableRow("Missing", String(report.requirementsSummary.missing), "Requirements with no mapped implementation evidence")}
                ${this.tableRow("Unverifiable", String(report.requirementsSummary.unverifiable), "Requirements needing stronger traceability")}
                ${this.tableRow("Coverage", `${report.requirementsSummary.coveragePercent}%`, "Overall mapped requirement coverage")}
              </tbody>
            </table>
          </div>
        </section>

        <section class="section">
          <div class="section-title">3. Verification Results</div>
          <div class="cards">
            ${this.metricCard("Unit Tests", String(report.unitTestSummary.total), `${report.unitTestSummary.passed} passed / ${report.unitTestSummary.failed} failed`, report.unitTestSummary.failed > 0 ? "#d97706" : "#16a34a")}
            ${this.metricCard("Integration Tests", String(report.integrationTestSummary.total), `${report.integrationTestSummary.passed} passed / ${report.integrationTestSummary.failed} failed`, report.integrationTestSummary.failed > 0 ? "#dc2626" : "#0f766e")}
            ${this.metricCard("Performance Alerts", String(report.performanceSummary.alerts), `${report.performanceSummary.total} findings recorded`, report.performanceSummary.alerts > 0 ? "#d97706" : "#2563eb")}
            ${this.metricCard("Major Blockers", String(report.majorBlockers.length), report.majorBlockers.length > 0 ? "Needs engineering triage" : "No blockers recorded", report.majorBlockers.length > 0 ? "#dc2626" : "#16a34a")}
          </div>
        </section>

        <section class="section">
          <div class="section-title">4. Quality Score Breakdown</div>
          <div class="abstract-box score-list">
            ${this.scoreRow("Functional Correctness (40%)", report.qualityScore.functionalCorrectness)}
            ${this.scoreRow("Code Quality (25%)", report.qualityScore.codeQuality)}
            ${this.scoreRow("Security (20%)", report.qualityScore.security)}
            ${this.scoreRow("Performance (15%)", report.qualityScore.performance)}
            ${this.scoreRow("Overall Score", report.qualityScore.overall)}
          </div>
        </section>

        <section class="section">
          <div class="section-title">5. Security and Operational Risk</div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Count</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${this.tableRow("Critical", String(report.securitySummary.critical), report.securitySummary.critical > 0 ? "Immediate remediation required" : "No critical items")}
                ${this.tableRow("High", String(report.securitySummary.high), report.securitySummary.high > 0 ? "Prioritize before release" : "No high-severity items")}
                ${this.tableRow("Medium", String(report.securitySummary.medium), report.securitySummary.medium > 0 ? "Plan near-term fixes" : "No medium-severity items")}
                ${this.tableRow("Low", String(report.securitySummary.low), report.securitySummary.low > 0 ? "Track as backlog improvements" : "No low-severity items")}
                ${this.tableRow("Performance Alerts", String(report.performanceSummary.alerts), report.performanceSummary.alerts > 0 ? "Investigate throughput and latency impact" : "No active alerts")}
              </tbody>
            </table>
          </div>
        </section>

        <section class="section">
          <div class="section-title">6. Major Blockers</div>
          <div class="list-panel">
            <h3>Release Readiness Issues</h3>
            <ul class="list">
              ${blockers.map((item) => `<li>${esc(item)}</li>`).join("")}
            </ul>
          </div>
        </section>

        <section class="section">
          <div class="section-title">7. Recommendations</div>
          <div class="list-panel">
            <h3>Recommended Next Actions</h3>
            <ul class="list">
              ${recommendations.map((item) => `<li>${esc(item)}</li>`).join("")}
            </ul>
          </div>
        </section>

        <section class="section">
          <div class="section-title">8. Artifact Register</div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Artifact</th>
                  <th>Type</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                ${report.artifacts.slice(0, 18).map((artifact) => this.tableRow(artifact, artifact.split("/")[0] || "file", "Generated by the Agent 3 pipeline")).join("")}
              </tbody>
            </table>
          </div>
          ${report.artifacts.length > 18 ? `<div class="note" style="margin-top:16px;">${esc(String(report.artifacts.length - 18))} additional artifacts are available in the run output directory.</div>` : ""}
        </section>

        <footer class="footer">
          <div>Generated by Agent 3 QA Platform</div>
          <div>${esc(this.formatDate(report.analysisDate))}</div>
          <div>Run: ${esc(report.runId)}</div>
        </footer>
      </section>
    </article>
  </div>
</body>
</html>`;
  }

  private abstractText(report: FinalReport): string {
    return `${report.projectName} was analyzed across requirements coverage, automated verification, code quality, security posture, and performance indicators. The project achieved an overall QA score of ${report.qualityScore.overall}/100 with ${report.requirementsSummary.coveragePercent}% mapped requirement coverage. This IEEE-style layout is intended to make blocker review, remediation planning, and engineering sign-off faster.`;
  }

  private metricCard(label: string, value: string, sub: string, color: string): string {
    return `<article class="card" style="--card-accent:${esc(color)}">
      <div class="label">${esc(label)}</div>
      <div class="value">${esc(value)}</div>
      <div class="sub">${esc(sub)}</div>
    </article>`;
  }

  private factItem(name: string, description: string): string {
    return `<div class="fact">
      <div class="name">${esc(name)}</div>
      <div class="desc">${esc(description)}</div>
    </div>`;
  }

  private tableRow(name: string, value: string, interpretation: string): string {
    return `<tr>
      <td>${esc(name)}</td>
      <td>${esc(value)}</td>
      <td>${esc(interpretation)}</td>
    </tr>`;
  }

  private scoreRow(name: string, value: number): string {
    const color = value >= 80 ? "#16a34a" : value >= 60 ? "#d97706" : "#dc2626";
    return `<div class="score-row" style="--bar-color:${esc(color)}">
      <div class="name">${esc(name)}</div>
      <div class="bar"><div class="fill" style="width:${Math.max(6, value)}%"></div></div>
      <div class="score-value">${esc(String(value))}</div>
    </div>`;
  }

  private formatDate(input: string): string {
    return new Date(input).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }
}

function esc(value: string | number | undefined): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
