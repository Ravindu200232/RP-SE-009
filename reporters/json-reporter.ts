import fs from "fs";
import path from "path";
import type {
  FinalReport,
  BugRecord,
  TraceabilityRecord,
  SecurityFinding,
  PerformanceFinding,
  RunRecord,
  ProjectInventory,
  SRSDocument,
  QualityScore,
  TestSuiteResult,
} from "@/types";
import type { TraceabilityReport } from "@/analyzers/traceability-analyzer";
import type { SecurityReport } from "@/analyzers/security-analyzer";
import type { PerformanceReport } from "@/analyzers/performance-analyzer";
import type { QualityReport } from "@/analyzers/quality-analyzer";

export class JSONReporter {
  private outputDir: string;

  constructor(outputDir: string) {
    this.outputDir = outputDir;
    fs.mkdirSync(path.join(outputDir, "reports"), { recursive: true });
    fs.mkdirSync(path.join(outputDir, "bugs"), { recursive: true });
  }

  saveInventory(inventory: ProjectInventory): void {
    this.write("inventory/project_inventory.json", inventory);
  }

  saveSRS(srs: SRSDocument): void {
    this.write("inventory/srs_normalized.json", srs);
  }

  saveTraceability(report: TraceabilityReport): void {
    this.write("reports/requirements_traceability.json", {
      summary: {
        total: report.records.length,
        implemented: report.implemented,
        partiallyImplemented: report.partiallyImplemented,
        missing: report.missing,
        unverifiable: report.unverifiable,
        coveragePercent: report.coveragePercent,
      },
      records: report.records,
    });

    const missing = report.records.filter(
      (r) => r.status === "missing" || r.status === "partially_implemented"
    );
    this.write("reports/missing_parts_report.json", {
      total: missing.length,
      items: missing,
    });
  }

  saveQuality(report: QualityReport): void {
    this.write("reports/quality_review.json", report);
    this.write("reports/quality_gate.json", {
      passed: report.score.passed,
      score: report.score.overall,
      breakdown: {
        functionalCorrectness: report.score.functionalCorrectness,
        codeQuality: report.score.codeQuality,
        security: report.score.security,
        performance: report.score.performance,
      },
      gate: report.score.passed ? "PASS" : "FAIL",
    });
  }

  saveSecurity(report: SecurityReport): void {
    this.write("reports/security_report.json", {
      summary: report.summary,
      toolsUsed: report.toolsUsed,
      llmAnalysis: report.llmAnalysis,
    });
    this.write("reports/security_findings.json", report.findings);
    if (report.bugs.length > 0) {
      this.write("bugs/security_bugs.json", report.bugs);
    }
  }

  savePerformance(report: PerformanceReport): void {
    this.write("reports/performance_report.json", {
      summary: report.summary,
      toolsUsed: report.toolsUsed,
      autocannon: report.autocannon,
      findings: report.findings,
    });
    if (report.bugs.length > 0) {
      this.write("bugs/performance_bugs.json", report.bugs);
    }
  }

  saveUnitTestBugs(bugs: BugRecord[]): void {
    this.write("bugs/unit_test_bugs.json", bugs);
  }

  saveIntegrationTestBugs(bugs: BugRecord[]): void {
    this.write("bugs/integration_test_bugs.json", bugs);
  }

  saveSRSGapBugs(bugs: BugRecord[]): void {
    this.write("bugs/srs_gap_bugs.json", bugs);
  }

  saveMergedBugs(allBugs: BugRecord[]): void {
    this.write("bugs/all_bugs_merged.json", allBugs);
  }

  saveFinalReport(report: FinalReport): void {
    this.write("reports/final_agent3_report.json", report);
  }

  buildFinalReport(params: {
    run: RunRecord;
    inventory: ProjectInventory;
    srs: SRSDocument;
    traceability: TraceabilityReport;
    unitTests: TestSuiteResult;
    integrationTests: TestSuiteResult;
    security: SecurityReport;
    performance: PerformanceReport;
    quality: QualityReport;
    allBugs: BugRecord[];
    artifacts: string[];
  }): FinalReport {
    const { run, inventory, srs, traceability, unitTests, integrationTests, security, performance, quality, artifacts } = params;

    const majorBlockers: string[] = [];
    if (unitTests.failed > 0) majorBlockers.push(`${unitTests.failed} unit tests failing`);
    if (security.summary.critical > 0) majorBlockers.push(`${security.summary.critical} critical security issues`);
    if (!quality.score.passed) majorBlockers.push(`Quality gate failed (score: ${quality.score.overall}/100)`);
    if (traceability.missing > 0) majorBlockers.push(`${traceability.missing} requirements not implemented`);

    const recommendations: string[] = [];
    if (inventory.testFiles.length === 0) recommendations.push("Add automated test suite to the project");
    if (security.summary.high > 0) recommendations.push("Address high-severity security findings before deployment");
    if (traceability.coveragePercent < 70) recommendations.push("Improve requirement coverage (currently below 70%)");
    recommendations.push("Review and integrate generated unit tests into the main project");
    if (quality.score.codeQuality < 70) recommendations.push("Resolve ESLint errors and TypeScript issues");

    return {
      runId: run.id,
      projectName: inventory.packageJson
        ? String((inventory.packageJson as { name?: string }).name || srs.projectName)
        : srs.projectName,
      projectPath: run.config.projectPath,
      srsPath: run.config.srsPath,
      analysisDate: new Date().toISOString(),
      projectSummary: {
        detectedStack: inventory.projectType,
        frameworks: inventory.frameworks,
        totalFiles: inventory.allFiles.length,
        hasTypeScript: inventory.hasTypeScript,
        hasPython: inventory.hasPython,
      },
      requirementsSummary: {
        total: traceability.records.length,
        implemented: traceability.implemented,
        partiallyImplemented: traceability.partiallyImplemented,
        missing: traceability.missing,
        unverifiable: traceability.unverifiable,
        coveragePercent: traceability.coveragePercent,
      },
      unitTestSummary: unitTests,
      integrationTestSummary: integrationTests,
      securitySummary: security.summary,
      performanceSummary: performance.summary,
      qualityScore: quality.score,
      majorBlockers,
      recommendations,
      artifacts,
    };
  }

  private write(relativePath: string, data: unknown): void {
    const fullPath = path.join(this.outputDir, relativePath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, JSON.stringify(data, null, 2), "utf-8");
  }
}
