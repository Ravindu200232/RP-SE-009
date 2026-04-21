import fs from "fs";
import path from "path";
import type { FinalReport } from "@/types";

export class PDFReporter {
  async generatePDF(report: FinalReport, htmlPath: string, outputDir: string): Promise<string> {
    const pdfPath = path.join(outputDir, "pdf", "agent3_report.pdf");
    fs.mkdirSync(path.dirname(pdfPath), { recursive: true });

    try {
      const PDFKit = require("pdfkit") as typeof import("pdfkit");
      return this.generateWithPDFKit(report, pdfPath, PDFKit);
    } catch (err) {
      console.warn("[PDFReporter] PDFKit generation failed:", err);
      const fallback = path.join(outputDir, "pdf", "report_fallback.txt");
      fs.writeFileSync(fallback, this.generateTextFallback(report), "utf-8");
      return fallback;
    }
  }

  private generateWithPDFKit(
    r: FinalReport,
    outputPath: string,
    PDFKit: typeof import("pdfkit")
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const doc = new PDFKit({ size: "A4", margin: 50 });
      const stream = fs.createWriteStream(outputPath);
      doc.pipe(stream);

      // Cover Page
      doc.rect(0, 0, doc.page.width, doc.page.height).fill("#0a0a0a");
      doc.fill("#ffffff");
      doc.fontSize(28).font("Helvetica-Bold");
      doc.text("QA Analysis Report", 50, 150, { align: "center" });
      doc.fontSize(14).font("Helvetica");
      doc.fill("#94a3b8");
      doc.text("Agent 3 — Automated Quality Analysis Platform", { align: "center" });
      doc.moveDown(3);
      doc.fill("#e2e8f0");
      doc.fontSize(12);
      doc.text(`Project: ${r.projectName}`, { align: "center" });
      doc.text(`Stack: ${r.projectSummary.detectedStack}`, { align: "center" });
      doc.text(`Date: ${new Date(r.analysisDate).toLocaleDateString()}`, { align: "center" });
      doc.text(`Run ID: ${r.runId.substring(0, 16)}...`, { align: "center" });
      doc.moveDown(2);
      const gateColor = r.qualityScore.passed ? "#22c55e" : "#ef4444";
      doc.fill(gateColor).fontSize(16).font("Helvetica-Bold");
      doc.text(`Quality Gate: ${r.qualityScore.passed ? "PASS" : "FAIL"}`, { align: "center" });

      doc.addPage();
      doc.rect(0, 0, doc.page.width, doc.page.height).fill("#0a0a0a");
      doc.fill("#ffffff");

      // Executive Summary
      this.sectionHeader(doc, "1. Executive Summary");
      this.keyValue(doc, "Total Files Analyzed", String(r.projectSummary.totalFiles));
      this.keyValue(doc, "Frameworks", r.projectSummary.frameworks.join(", "));
      this.keyValue(doc, "TypeScript", r.projectSummary.hasTypeScript ? "Yes" : "No");
      this.keyValue(doc, "Overall Quality Score", `${r.qualityScore.overall}/100`);
      doc.moveDown();

      // Requirement Traceability
      this.sectionHeader(doc, "2. Requirement Traceability");
      this.keyValue(doc, "Total Requirements", String(r.requirementsSummary.total));
      this.keyValue(doc, "Implemented", String(r.requirementsSummary.implemented));
      this.keyValue(doc, "Partially Implemented", String(r.requirementsSummary.partiallyImplemented));
      this.keyValue(doc, "Missing", String(r.requirementsSummary.missing));
      this.keyValue(doc, "Coverage", `${r.requirementsSummary.coveragePercent}%`);
      doc.moveDown();

      // Quality Score
      this.sectionHeader(doc, "3. Quality Score Breakdown");
      this.keyValue(doc, "Functional Correctness (40%)", `${r.qualityScore.functionalCorrectness}/100`);
      this.keyValue(doc, "Code Quality (25%)", `${r.qualityScore.codeQuality}/100`);
      this.keyValue(doc, "Security (20%)", `${r.qualityScore.security}/100`);
      this.keyValue(doc, "Performance (15%)", `${r.qualityScore.performance}/100`);
      this.keyValue(doc, "Overall", `${r.qualityScore.overall}/100`);
      doc.moveDown();

      // Testing
      this.sectionHeader(doc, "4. Test Results");
      doc.fill("#94a3b8").fontSize(10).font("Helvetica-Bold").text("Unit Tests:");
      doc.fill("#e2e8f0").font("Helvetica").fontSize(10);
      this.keyValue(doc, "  Total", String(r.unitTestSummary.total));
      this.keyValue(doc, "  Passed", String(r.unitTestSummary.passed));
      this.keyValue(doc, "  Failed", String(r.unitTestSummary.failed));
      doc.moveDown(0.5);
      doc.fill("#94a3b8").fontSize(10).font("Helvetica-Bold").text("Integration Tests:");
      doc.fill("#e2e8f0").font("Helvetica").fontSize(10);
      this.keyValue(doc, "  Total", String(r.integrationTestSummary.total));
      this.keyValue(doc, "  Passed", String(r.integrationTestSummary.passed));
      this.keyValue(doc, "  Failed", String(r.integrationTestSummary.failed));
      doc.moveDown();

      // Security
      this.sectionHeader(doc, "5. Security Findings");
      this.keyValue(doc, "Critical", String(r.securitySummary.critical));
      this.keyValue(doc, "High", String(r.securitySummary.high));
      this.keyValue(doc, "Medium", String(r.securitySummary.medium));
      this.keyValue(doc, "Low", String(r.securitySummary.low));
      this.keyValue(doc, "Total", String(r.securitySummary.total));
      doc.moveDown();

      // Major Blockers
      if (r.majorBlockers.length > 0) {
        this.sectionHeader(doc, "6. Major Blockers");
        for (const b of r.majorBlockers) {
          doc.fill("#ef4444").fontSize(10).text(`• ${b}`);
        }
        doc.moveDown();
      }

      // Recommendations
      this.sectionHeader(doc, "7. Recommendations");
      doc.fill("#e2e8f0").font("Helvetica").fontSize(10);
      for (const rec of r.recommendations) {
        doc.text(`• ${rec}`);
        doc.moveDown(0.3);
      }
      doc.moveDown();

      // Artifacts
      this.sectionHeader(doc, "8. Generated Artifacts");
      doc.fill("#94a3b8").fontSize(9).font("Courier");
      for (const a of r.artifacts.slice(0, 20)) {
        doc.text(a);
      }

      // Footer
      doc.fontSize(8).fill("#334155").font("Helvetica");
      doc.text(
        `Generated by Agent 3 QA Platform | ${new Date().toISOString()} | Run: ${r.runId}`,
        50,
        doc.page.height - 50,
        { align: "center" }
      );

      doc.end();
      stream.on("finish", () => resolve(outputPath));
      stream.on("error", reject);
    });
  }

  private sectionHeader(doc: PDFKit.PDFDocument, title: string): void {
    doc.moveDown(0.5);
    doc.fill("#3b82f6").fontSize(13).font("Helvetica-Bold").text(title);
    doc.fill("#1e293b")
      .rect(50, doc.y, doc.page.width - 100, 1)
      .fill("#1e3a5f");
    doc.moveDown(0.5);
    doc.fill("#e2e8f0").font("Helvetica").fontSize(10);
  }

  private keyValue(doc: PDFKit.PDFDocument, key: string, value: string): void {
    doc.fill("#94a3b8").font("Helvetica-Bold").fontSize(10).text(`${key}: `, { continued: true });
    doc.fill("#e2e8f0").font("Helvetica").text(value);
  }

  private generateTextFallback(r: FinalReport): string {
    return [
      "=== AGENT 3 QA REPORT ===",
      `Project: ${r.projectName}`,
      `Date: ${r.analysisDate}`,
      `Quality Gate: ${r.qualityScore.passed ? "PASS" : "FAIL"}`,
      `Overall Score: ${r.qualityScore.overall}/100`,
      "",
      "=== REQUIREMENTS ===",
      `Total: ${r.requirementsSummary.total}`,
      `Coverage: ${r.requirementsSummary.coveragePercent}%`,
      `Missing: ${r.requirementsSummary.missing}`,
      "",
      "=== SECURITY ===",
      `Critical: ${r.securitySummary.critical}`,
      `High: ${r.securitySummary.high}`,
      `Total: ${r.securitySummary.total}`,
      "",
      "=== MAJOR BLOCKERS ===",
      ...r.majorBlockers.map((b) => `- ${b}`),
      "",
      "=== RECOMMENDATIONS ===",
      ...r.recommendations.map((rec) => `- ${rec}`),
    ].join("\n");
  }
}
