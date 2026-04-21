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

  private buildHTML(r: FinalReport): string {
    const passColor = r.qualityScore.passed ? "#22c55e" : "#ef4444";
    const passText = r.qualityScore.passed ? "PASS" : "FAIL";
    const gateStyle = r.qualityScore.passed
      ? "background:#166534;color:#dcfce7"
      : "background:#7f1d1d;color:#fee2e2";

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent 3 QA Report - ${r.projectName}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a0a; color: #e5e5e5; line-height: 1.6; }
  .container { max-width: 1100px; margin: 0 auto; padding: 40px 24px; }
  .cover { text-align: center; padding: 80px 40px; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); border-radius: 16px; margin-bottom: 40px; border: 1px solid #334155; }
  .cover h1 { font-size: 2.5rem; font-weight: 800; background: linear-gradient(to right, #60a5fa, #a78bfa, #f472b6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
  .cover .subtitle { color: #94a3b8; margin-top: 12px; font-size: 1rem; }
  .cover .meta { display: flex; justify-content: center; gap: 32px; margin-top: 32px; flex-wrap: wrap; }
  .cover .meta-item { text-align: center; }
  .cover .meta-item .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .cover .meta-item .value { font-size: 0.95rem; color: #cbd5e1; margin-top: 4px; }
  .gate { display: inline-block; padding: 8px 24px; border-radius: 9999px; font-weight: 700; font-size: 1.1rem; margin-top: 24px; ${gateStyle}; }
  .section { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 28px; margin-bottom: 24px; }
  .section h2 { font-size: 1.25rem; font-weight: 700; color: #f1f5f9; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #1f2937; display: flex; align-items: center; gap: 8px; }
  .section h2::before { content: ''; display: inline-block; width: 4px; height: 20px; background: linear-gradient(to bottom, #3b82f6, #8b5cf6); border-radius: 2px; }
  .grid { display: grid; gap: 16px; }
  .grid-2 { grid-template-columns: 1fr 1fr; }
  .grid-3 { grid-template-columns: 1fr 1fr 1fr; }
  .grid-4 { grid-template-columns: 1fr 1fr 1fr 1fr; }
  .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; }
  .card .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.75rem; font-weight: 700; color: #f1f5f9; margin-top: 4px; }
  .card .sub { font-size: 0.8rem; color: #475569; margin-top: 2px; }
  .score-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .score-bar .name { width: 180px; font-size: 0.85rem; color: #94a3b8; }
  .score-bar .bar { flex: 1; height: 8px; background: #1e293b; border-radius: 4px; overflow: hidden; }
  .score-bar .fill { height: 100%; border-radius: 4px; background: linear-gradient(to right, #3b82f6, #8b5cf6); }
  .score-bar .pct { width: 40px; text-align: right; font-size: 0.85rem; color: #e2e8f0; font-weight: 600; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
  .badge-critical { background: #450a0a; color: #fca5a5; }
  .badge-high { background: #431407; color: #fdba74; }
  .badge-medium { background: #422006; color: #fcd34d; }
  .badge-low { background: #1a2e05; color: #86efac; }
  .badge-pass { background: #052e16; color: #86efac; }
  .badge-fail { background: #450a0a; color: #fca5a5; }
  .list { list-style: none; }
  .list li { padding: 8px 0; border-bottom: 1px solid #1e293b; font-size: 0.9rem; color: #94a3b8; display: flex; align-items: flex-start; gap: 8px; }
  .list li:last-child { border-bottom: none; }
  .list li::before { content: '→'; color: #3b82f6; flex-shrink: 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { text-align: left; padding: 10px 12px; background: #0f172a; color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.05em; }
  td { padding: 10px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  tr:last-child td { border-bottom: none; }
  .footer { text-align: center; padding: 32px; color: #334155; font-size: 0.8rem; }
  @media (max-width: 768px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container">

  <!-- Cover -->
  <div class="cover">
    <h1>QA Analysis Report</h1>
    <p class="subtitle">Agent 3 — Automated Quality Analysis Platform</p>
    <div class="meta">
      <div class="meta-item"><div class="label">Project</div><div class="value">${esc(r.projectName)}</div></div>
      <div class="meta-item"><div class="label">Stack</div><div class="value">${esc(r.projectSummary.detectedStack)}</div></div>
      <div class="meta-item"><div class="label">Analysis Date</div><div class="value">${new Date(r.analysisDate).toLocaleDateString()}</div></div>
      <div class="meta-item"><div class="label">Run ID</div><div class="value" style="font-size:0.8rem">${esc(r.runId.substring(0, 8))}...</div></div>
    </div>
    <div class="gate">Quality Gate: ${passText}</div>
  </div>

  <!-- Executive Summary -->
  <div class="section">
    <h2>Executive Summary</h2>
    <div class="grid grid-4">
      <div class="card"><div class="label">Total Files</div><div class="value">${r.projectSummary.totalFiles}</div></div>
      <div class="card"><div class="label">Requirements</div><div class="value">${r.requirementsSummary.total}</div><div class="sub">${r.requirementsSummary.coveragePercent}% coverage</div></div>
      <div class="card"><div class="label">Quality Score</div><div class="value" style="color:${passColor}">${r.qualityScore.overall}</div><div class="sub">out of 100</div></div>
      <div class="card"><div class="label">Security Issues</div><div class="value" style="color:${r.securitySummary.critical > 0 ? '#ef4444' : '#22c55e'}">${r.securitySummary.total}</div><div class="sub">${r.securitySummary.critical} critical</div></div>
    </div>
  </div>

  <!-- Quality Score Breakdown -->
  <div class="section">
    <h2>Quality Score Breakdown</h2>
    ${this.scoreBar("Functional Correctness (40%)", r.qualityScore.functionalCorrectness)}
    ${this.scoreBar("Code Quality (25%)", r.qualityScore.codeQuality)}
    ${this.scoreBar("Security (20%)", r.qualityScore.security)}
    ${this.scoreBar("Performance (15%)", r.qualityScore.performance)}
    ${this.scoreBar("Overall Score", r.qualityScore.overall)}
  </div>

  <!-- Requirements Traceability -->
  <div class="section">
    <h2>Requirements Traceability</h2>
    <div class="grid grid-4">
      <div class="card"><div class="label">Implemented</div><div class="value" style="color:#22c55e">${r.requirementsSummary.implemented}</div></div>
      <div class="card"><div class="label">Partial</div><div class="value" style="color:#f59e0b">${r.requirementsSummary.partiallyImplemented}</div></div>
      <div class="card"><div class="label">Missing</div><div class="value" style="color:#ef4444">${r.requirementsSummary.missing}</div></div>
      <div class="card"><div class="label">Coverage</div><div class="value">${r.requirementsSummary.coveragePercent}%</div></div>
    </div>
  </div>

  <!-- Testing -->
  <div class="section">
    <h2>Test Results</h2>
    <div class="grid grid-2">
      <div class="card">
        <div class="label">Unit Tests</div>
        <div class="value">${r.unitTestSummary.total}</div>
        <div class="sub" style="color:#22c55e">${r.unitTestSummary.passed} passed</div>
        <div class="sub" style="color:#ef4444">${r.unitTestSummary.failed} failed</div>
      </div>
      <div class="card">
        <div class="label">Integration Tests</div>
        <div class="value">${r.integrationTestSummary.total}</div>
        <div class="sub" style="color:#22c55e">${r.integrationTestSummary.passed} passed</div>
        <div class="sub" style="color:#ef4444">${r.integrationTestSummary.failed} failed</div>
      </div>
    </div>
  </div>

  <!-- Security -->
  <div class="section">
    <h2>Security Findings</h2>
    <div class="grid grid-4">
      <div class="card"><div class="label">Critical</div><div class="value" style="color:#ef4444">${r.securitySummary.critical}</div></div>
      <div class="card"><div class="label">High</div><div class="value" style="color:#f97316">${r.securitySummary.high}</div></div>
      <div class="card"><div class="label">Medium</div><div class="value" style="color:#eab308">${r.securitySummary.medium}</div></div>
      <div class="card"><div class="label">Low</div><div class="value" style="color:#22c55e">${r.securitySummary.low}</div></div>
    </div>
  </div>

  <!-- Major Blockers -->
  ${r.majorBlockers.length > 0 ? `
  <div class="section">
    <h2>Major Blockers</h2>
    <ul class="list">
      ${r.majorBlockers.map((b) => `<li>${esc(b)}</li>`).join("")}
    </ul>
  </div>` : ""}

  <!-- Recommendations -->
  <div class="section">
    <h2>Recommendations</h2>
    <ul class="list">
      ${r.recommendations.map((rec) => `<li>${esc(rec)}</li>`).join("")}
    </ul>
  </div>

  <!-- Artifacts -->
  <div class="section">
    <h2>Generated Artifacts</h2>
    <ul class="list">
      ${r.artifacts.map((a) => `<li style="font-family:monospace;font-size:0.8rem">${esc(a)}</li>`).join("")}
    </ul>
  </div>

  <div class="footer">
    Generated by Agent 3 QA Platform &mdash; ${new Date(r.analysisDate).toLocaleString()} &mdash; Run ID: ${esc(r.runId)}
  </div>
</div>
</body>
</html>`;
  }

  private scoreBar(name: string, value: number): string {
    const color =
      value >= 80 ? "#22c55e" : value >= 60 ? "#eab308" : "#ef4444";
    return `<div class="score-bar">
      <div class="name">${esc(name)}</div>
      <div class="bar"><div class="fill" style="width:${value}%;background:${color}"></div></div>
      <div class="pct">${value}</div>
    </div>`;
  }
}

function esc(s: string | number | undefined): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
