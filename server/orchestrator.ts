import fs from "fs";
import path from "path";
import type {
  RunConfig,
  BugRecord,
  TestSuiteResult,
} from "@/types";
import {
  getRun,
  updateRunStatus,
  updateRunPhase,
  updateRunMetrics,
} from "@/store/run-store";
import { emitProgress, buildEvent } from "./event-bus";
import { LLMRouter } from "@/providers/llm-router";
import { ProjectParser } from "@/parsers/project-parser";
import { SRSParser } from "@/parsers/srs-parser";
import { DiscoveryAnalyzer } from "@/analyzers/discovery-analyzer";
import { TraceabilityAnalyzer } from "@/analyzers/traceability-analyzer";
import { QualityAnalyzer } from "@/analyzers/quality-analyzer";
import { SecurityAnalyzer } from "@/analyzers/security-analyzer";
import { PerformanceAnalyzer } from "@/analyzers/performance-analyzer";
import { UnitTestGenerator } from "@/generators/unit-test-generator";
import { IntegrationTestGenerator } from "@/generators/integration-test-generator";
import { runVitest } from "@/executors/vitest-executor";
import { JSONReporter } from "@/reporters/json-reporter";
import { HTMLReporter } from "@/reporters/html-reporter.next";
import { PDFReporter } from "@/reporters/pdf-reporter.next";
import { v4 as uuidv4 } from "uuid";

function emit(runId: string, phase: string, msg: string, progress?: number) {
  emitProgress(
    runId,
    buildEvent("log", { phase, message: msg, progress })
  );
}

function phaseStart(runId: string, phaseId: string, name: string) {
  updateRunPhase(runId, phaseId, {
    status: "running",
    startedAt: new Date().toISOString(),
    progress: 0,
  });
  emitProgress(runId, buildEvent("phase_start", { phase: phaseId, message: name }));
}

function phaseProgress(runId: string, phaseId: string, progress: number, detail?: string) {
  updateRunPhase(runId, phaseId, { progress, detail });
  emitProgress(
    runId,
    buildEvent("phase_progress", { phase: phaseId, progress, message: detail })
  );
}

function phaseComplete(runId: string, phaseId: string) {
  updateRunPhase(runId, phaseId, {
    status: "completed",
    completedAt: new Date().toISOString(),
    progress: 100,
  });
  emitProgress(runId, buildEvent("phase_complete", { phase: phaseId, progress: 100 }));
}

function phaseError(runId: string, phaseId: string, error: string) {
  updateRunPhase(runId, phaseId, {
    status: "failed",
    error,
    completedAt: new Date().toISOString(),
  });
  emitProgress(runId, buildEvent("phase_error", { phase: phaseId, message: error }));
}

function phaseSkip(runId: string, phaseId: string, detail?: string) {
  updateRunPhase(runId, phaseId, {
    status: "skipped",
    progress: 100,
    detail,
    completedAt: new Date().toISOString(),
  });
  emitProgress(runId, buildEvent("phase_complete", {
    phase: phaseId,
    progress: 100,
    message: detail || "skipped",
  }));
}

const emptyTestSuite = (): TestSuiteResult => ({
  total: 0, passed: 0, failed: 0, skipped: 0, duration: 0, tests: [],
});

function ensureProjectTestHarness(projectPath: string): void {
  const testsRoot = path.join(projectPath, "__tests__");
  const workspaceNodeModules = path.join(process.cwd(), "node_modules");
  const bridgedNodeModules = path.join(testsRoot, "node_modules");

  fs.mkdirSync(testsRoot, { recursive: true });

  if (!fs.existsSync(workspaceNodeModules) || fs.existsSync(bridgedNodeModules)) {
    return;
  }

  try {
    fs.symlinkSync(workspaceNodeModules, bridgedNodeModules, "junction");
  } catch (err) {
    console.warn("[Agent3] Failed to create __tests__/node_modules bridge:", err);
  }
}

function getUnitTestTargetCount(inventory: RunConfig["projectPath"] extends string ? {
  services: Array<{ path: string }>;
  controllers: Array<{ path: string }>;
  models: Array<{ path: string }>;
  middleware: Array<{ path: string }>;
  routes: Array<{ file: string }>;
  entryPoints: string[];
} : never): number {
  const targets = new Set<string>();
  inventory.services.slice(0, 5).forEach((file) => targets.add(file.path));
  inventory.controllers.slice(0, 5).forEach((file) => targets.add(file.path));
  inventory.models.slice(0, 4).forEach((file) => targets.add(file.path));
  inventory.middleware.slice(0, 4).forEach((file) => targets.add(file.path));
  inventory.routes.slice(0, 5).forEach((route) => targets.add(route.file));
  inventory.entryPoints.slice(0, 3).forEach((file) => targets.add(file));
  return targets.size;
}

function getExecutionError(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  const firstUsefulLine = trimmed
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);

  if (!firstUsefulLine) return null;
  return firstUsefulLine.slice(0, 300);
}

export async function runAnalysis(runId: string): Promise<void> {
  const run = getRun(runId);
  if (!run) throw new Error(`Run ${runId} not found`);

  const config = run.config;
  const outputPath = run.outputPath;

  // Setup output directory structure
  const dirs = [
    "inventory", "generated-tests/unit", "generated-tests/integration",
    "raw-logs", "reports", "bugs", "artifacts", "pdf", "html", "temp",
  ];
  for (const d of dirs) {
    fs.mkdirSync(path.join(outputPath, d), { recursive: true });
  }

  updateRunStatus(runId, "running");
  emit(runId, "init", `Analysis started for ${config.projectPath}`);
  ensureProjectTestHarness(config.projectPath);

  const llm = new LLMRouter({
    ollamaBaseUrl: config.ollamaBaseUrl,
    ollamaModel: config.ollamaModel,
    glmApiKey: config.glmApiKey,
    glmModel: config.glmModel,
  });

  const jsonReporter = new JSONReporter(outputPath);
  const allBugs: BugRecord[] = [];
  let unitTestSuite = emptyTestSuite();
  let integrationTestSuite = emptyTestSuite();

  // =============================================================
  // PHASE 1: Project Intake & Discovery
  // =============================================================
  phaseStart(runId, "intake", "Project Intake & Discovery");
  try {
    emit(runId, "intake", `Reading project at: ${config.projectPath}`);
    if (!fs.existsSync(config.projectPath)) {
      throw new Error(`Project path does not exist: ${config.projectPath}`);
    }
    phaseProgress(runId, "intake", 50, "Scanning files...");
    emit(runId, "intake", "Project path validated");
    phaseComplete(runId, "intake");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "intake", msg);
    updateRunStatus(runId, "failed");
    emitProgress(runId, buildEvent("error", { message: msg }));
    return;
  }

  // =============================================================
  // PHASE 2: Build Inventory
  // =============================================================
  phaseStart(runId, "inventory", "Building Project Inventory");
  let inventory;
  try {
    const parser = new ProjectParser();
    emit(runId, "inventory", "Scanning project structure...");
    inventory = await parser.parse(config.projectPath);
    phaseProgress(runId, "inventory", 60, `Found ${inventory.allFiles.length} files`);

    jsonReporter.saveInventory(inventory);
    updateRunMetrics(runId, { totalFiles: inventory.allFiles.length });
    emit(runId, "inventory", `Detected: ${inventory.projectType} | ${inventory.frameworks.join(", ")}`);
    emit(runId, "inventory", `Models: ${inventory.models.length} | Controllers: ${inventory.controllers.length} | Services: ${inventory.services.length}`);
    emit(runId, "inventory", `Routes: ${inventory.routes.length} | Components: ${inventory.components.length}`);

    phaseComplete(runId, "inventory");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "inventory", msg);
    emit(runId, "inventory", `Warning: inventory failed - ${msg}`);
    // Use a minimal inventory and continue
    inventory = {
      projectType: "unknown" as const, packageManager: "npm" as const,
      hasTypeScript: false, hasPython: false, frameworks: [], rootPath: config.projectPath,
      entryPoints: [], routes: [], models: [], controllers: [], services: [],
      middleware: [], schemas: [], components: [], apiHandlers: [], configFiles: [],
      envFiles: [], testFiles: [], allFiles: [], scripts: {}, dependencies: {}, devDependencies: {},
    };
  }

  // =============================================================
  // PHASE 3: SRS Parsing
  // =============================================================
  phaseStart(runId, "srs_parse", "Parsing Agent 1 SRS");
  let srs;
  try {
    if (!fs.existsSync(config.srsPath)) {
      throw new Error(`SRS file not found: ${config.srsPath}`);
    }
    const srsParser = new SRSParser();
    srs = srsParser.parse(config.srsPath);
    phaseProgress(runId, "srs_parse", 80);
    jsonReporter.saveSRS(srs);
    const totalReqs = srs.functionalRequirements.length + srs.nonFunctionalRequirements.length;
    emit(runId, "srs_parse", `Project: ${srs.projectName} | FRs: ${srs.functionalRequirements.length} | NFRs: ${srs.nonFunctionalRequirements.length}`);
    updateRunMetrics(runId, { totalRequirements: totalReqs });
    phaseComplete(runId, "srs_parse");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "srs_parse", msg);
    emit(runId, "srs_parse", `SRS parse failed: ${msg} - continuing with empty SRS`);
    srs = {
      projectName: path.basename(config.projectPath),
      functionalRequirements: [], nonFunctionalRequirements: [],
      raw: {},
    };
  }

  // =============================================================
  // PHASE 4: Requirement Traceability
  // =============================================================
  phaseStart(runId, "traceability", "Requirement Traceability Analysis");
  let traceabilityReport;
  try {
    const tracer = new TraceabilityAnalyzer(llm);
    emit(runId, "traceability", "Analyzing requirement coverage...");
    phaseProgress(runId, "traceability", 20);
    traceabilityReport = await tracer.analyze(srs, inventory, config.projectPath);
    phaseProgress(runId, "traceability", 80);
    jsonReporter.saveTraceability(traceabilityReport);

    const missingReqs = traceabilityReport.records.filter((r) => r.status === "missing");
    const srsGapBugs: BugRecord[] = missingReqs.map((req) => ({
      bugId: `SRS-${uuidv4().substring(0, 8)}`,
      phase: "traceability",
      severity: "high" as const,
      category: "srs_gap" as const,
      title: `Missing: ${req.requirementTitle}`,
      description: `Requirement "${req.requirementTitle}" (${req.requirementId}) was not found in the implementation.`,
      affectedFiles: [],
      affectedRoutes: [],
      requirementIds: [req.requirementId],
      evidence: req.evidence.join("; ") || "No evidence found",
      reproductionSteps: ["Review the project against this requirement"],
      expectedBehavior: "Requirement should be implemented",
      actualBehavior: "Requirement not found in codebase",
      suggestedFix: "Implement the missing requirement",
      confidenceScore: req.confidence,
      sourceTool: "traceability-analyzer",
      llmSummary: req.llmReasoning,
      timestamp: new Date().toISOString(),
    }));

    jsonReporter.saveSRSGapBugs(srsGapBugs);
    allBugs.push(...srsGapBugs);

    updateRunMetrics(runId, {
      implementedRequirements: traceabilityReport.implemented,
      missingRequirements: traceabilityReport.missing,
    });

    emit(runId, "traceability", `Coverage: ${traceabilityReport.coveragePercent}% | Missing: ${traceabilityReport.missing}`);
    phaseComplete(runId, "traceability");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "traceability", msg);
    traceabilityReport = {
      records: [], implemented: 0, partiallyImplemented: 0,
      missing: 0, unverifiable: 0, coveragePercent: 0,
    };
  }

  // =============================================================
  // PHASE 5: Unit Test Generation
  // =============================================================
  phaseStart(runId, "unit_gen", "Unit Test Generation");
  let generatedUnitTests: { testFile: string; testCount: number }[] = [];
  try {
    const unitTargetCount = getUnitTestTargetCount(inventory);
    if (unitTargetCount === 0) {
      const message = "No testable files found for unit generation (services, controllers, models, middleware, routes, or entry points).";
      emit(runId, "unit_gen", message);
      phaseSkip(runId, "unit_gen", message);
    } else {
    const unitGen = new UnitTestGenerator(llm);
    const unitOutDir = path.join(outputPath, "generated-tests", "unit");
    emit(runId, "unit_gen", "Generating unit tests...");
    phaseProgress(runId, "unit_gen", 30);
    generatedUnitTests = await unitGen.generate(config.projectPath, inventory, unitOutDir);
    const totalTests = generatedUnitTests.reduce((s, t) => s + t.testCount, 0);
    emit(runId, "unit_gen", `Generated ${generatedUnitTests.length} test files (${totalTests} tests)`);
    updateRunMetrics(runId, { unitTestsGenerated: totalTests });
      phaseComplete(runId, "unit_gen");
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "unit_gen", msg);
  }

  // =============================================================
  // PHASE 6: Unit Test Execution
  // =============================================================
  phaseStart(runId, "unit_exec", "Unit Test Execution");
  try {
    const unitDir = path.join(outputPath, "generated-tests", "unit");
    if (generatedUnitTests.length > 0) {
      emit(runId, "unit_exec", "Running unit tests with Vitest...");
      phaseProgress(runId, "unit_exec", 30);
      const projectUnitDir = path.join(config.projectPath, "__tests__", "backend");
      const vitestResult = await runVitest(
        config.projectPath,
        projectUnitDir
      );
      fs.writeFileSync(
        path.join(outputPath, "raw-logs", "vitest-output.txt"),
        vitestResult.raw,
        "utf-8"
      );

      if (!vitestResult.available) {
        emit(runId, "unit_exec", vitestResult.raw);
        phaseSkip(runId, "unit_exec", vitestResult.raw);
      } else {
        unitTestSuite = vitestResult.result;
        if (unitTestSuite.total === 0) {
          const executionError = getExecutionError(vitestResult.raw);
          if (executionError) {
            throw new Error(`Vitest did not execute unit tests successfully. ${executionError}`);
          }
        }

        const unitBugs: BugRecord[] = unitTestSuite.tests
          .filter((t) => t.status === "failed")
          .map((t) => ({
            bugId: `UNIT-${uuidv4().substring(0, 8)}`,
            phase: "unit_test",
            severity: "medium" as const,
            category: "functional" as const,
            title: `Unit test failed: ${t.name}`,
            description: t.error || "Test assertion failed",
            affectedFiles: t.file ? [t.file] : [],
            affectedRoutes: [],
            requirementIds: [],
            evidence: t.error || "",
            reproductionSteps: [`Run test: ${t.name}`],
            expectedBehavior: "Test should pass",
            actualBehavior: t.error || "Test failed",
            suggestedFix: "Fix the implementation to make the test pass",
            confidenceScore: 0.9,
            sourceTool: "vitest",
            timestamp: new Date().toISOString(),
          }));

        jsonReporter.saveUnitTestBugs(unitBugs);
        allBugs.push(...unitBugs);

        updateRunMetrics(runId, {
          unitTestsPassed: unitTestSuite.passed,
          unitTestsFailed: unitTestSuite.failed,
        });

        emit(runId, "unit_exec", `Results: ${unitTestSuite.passed} passed, ${unitTestSuite.failed} failed`);
        phaseComplete(runId, "unit_exec");
      }
    } else {
      const message = "No unit tests were generated, so execution was skipped.";
      emit(runId, "unit_exec", message);
      phaseSkip(runId, "unit_exec", message);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "unit_exec", msg);
  }

  // =============================================================
  // PHASE 7: Integration Test Generation
  // =============================================================
  phaseStart(runId, "integration_gen", "Integration Test Generation");
  let generatedIntegrationTests: { name: string; testFile: string; testCount: number }[] = [];
  try {
    const hasIntegrationTargets =
      inventory.routes.length > 0 ||
      inventory.models.length > 0 ||
      inventory.allFiles.some((f) => f.toLowerCase().includes("auth") || f.toLowerCase().includes("login"));

    if (!hasIntegrationTargets) {
      const message = "No API routes, auth flows, or models were detected for integration test generation.";
      emit(runId, "integration_gen", message);
      phaseSkip(runId, "integration_gen", message);
    } else {
      const intGen = new IntegrationTestGenerator(llm);
      const intOutDir = path.join(outputPath, "generated-tests", "integration");
      emit(runId, "integration_gen", "Generating integration tests...");
      phaseProgress(runId, "integration_gen", 30);
      generatedIntegrationTests = await intGen.generate(config.projectPath, inventory, intOutDir);
      const totalTests = generatedIntegrationTests.reduce((s, t) => s + t.testCount, 0);
      emit(runId, "integration_gen", `Generated ${generatedIntegrationTests.length} integration test files`);
      updateRunMetrics(runId, { integrationTestsGenerated: totalTests });
      phaseComplete(runId, "integration_gen");
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "integration_gen", msg);
  }

  // =============================================================
  // PHASE 8: Integration Test Execution
  // =============================================================
  phaseStart(runId, "integration_exec", "Integration Test Execution");
  try {
    if (generatedIntegrationTests.length > 0) {
      const intDir = path.join(outputPath, "generated-tests", "integration");
      emit(runId, "integration_exec", "Running integration tests...");
      phaseProgress(runId, "integration_exec", 30);
      const projectIntegrationDir = path.join(config.projectPath, "__tests__", "integration");
      const vitestResult = await runVitest(
        config.projectPath,
        projectIntegrationDir
      );
      fs.writeFileSync(
        path.join(outputPath, "raw-logs", "vitest-integration-output.txt"),
        vitestResult.raw,
        "utf-8"
      );

      if (!vitestResult.available) {
        emit(runId, "integration_exec", vitestResult.raw);
        phaseSkip(runId, "integration_exec", vitestResult.raw);
      } else {
        integrationTestSuite = vitestResult.result;
        if (integrationTestSuite.total === 0) {
          const executionError = getExecutionError(vitestResult.raw);
          if (executionError) {
            throw new Error(`Vitest did not execute integration tests successfully. ${executionError}`);
          }
        }

        const intBugs: BugRecord[] = integrationTestSuite.tests
          .filter((t) => t.status === "failed")
          .map((t) => ({
            bugId: `INT-${uuidv4().substring(0, 8)}`,
            phase: "integration_test",
            severity: "high" as const,
            category: "functional" as const,
            title: `Integration test failed: ${t.name}`,
            description: t.error || "Integration test assertion failed",
            affectedFiles: t.file ? [t.file] : [],
            affectedRoutes: [],
            requirementIds: [],
            evidence: t.error || "",
            reproductionSteps: [`Run test: ${t.name}`],
            expectedBehavior: "Test should pass",
            actualBehavior: t.error || "Test failed",
            suggestedFix: "Fix the implementation or test setup",
            confidenceScore: 0.85,
            sourceTool: "vitest-integration",
            timestamp: new Date().toISOString(),
          }));

        jsonReporter.saveIntegrationTestBugs(intBugs);
        allBugs.push(...intBugs);

        updateRunMetrics(runId, {
          integrationTestsPassed: integrationTestSuite.passed,
          integrationTestsFailed: integrationTestSuite.failed,
        });

        emit(runId, "integration_exec", `Results: ${integrationTestSuite.passed} passed, ${integrationTestSuite.failed} failed`);
        phaseComplete(runId, "integration_exec");
      }
    } else {
      const message = "No integration tests were generated, so execution was skipped.";
      emit(runId, "integration_exec", message);
      phaseSkip(runId, "integration_exec", message);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "integration_exec", msg);
  }

  // =============================================================
  // PHASE 9: Quality Review
  // =============================================================
  phaseStart(runId, "quality", "Code Quality Analysis");
  let qualityReport;
  try {
    const qualityAnalyzer = new QualityAnalyzer(llm);
    emit(runId, "quality", "Running ESLint and TypeScript checks...");
    phaseProgress(runId, "quality", 30);
    qualityReport = await qualityAnalyzer.analyze(config.projectPath, inventory);
    phaseProgress(runId, "quality", 80);
    jsonReporter.saveQuality(qualityReport);
    emit(runId, "quality", `Quality Score: ${qualityReport.score.overall}/100 | ESLint errors: ${qualityReport.eslintIssues.errorCount}`);
    updateRunMetrics(runId, {
      qualityScore: qualityReport.score.overall,
      passed: qualityReport.score.passed,
    });
    phaseComplete(runId, "quality");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "quality", msg);
    qualityReport = {
      score: { functionalCorrectness: 50, codeQuality: 50, security: 50, performance: 50, overall: 50, passed: false, details: {} },
      eslintIssues: { errorCount: 0, warningCount: 0 },
      typeErrors: 0, duplications: 0, maintainabilityIssues: [], architectureIssues: [], raw: {},
    };
  }

  // =============================================================
  // PHASE 10: Security Scan
  // =============================================================
  phaseStart(runId, "security", "Security Analysis");
  let securityReport;
  try {
    const secAnalyzer = new SecurityAnalyzer(llm);
    emit(runId, "security", `Running security checks (semgrep: ${config.enableSecurity})...`);
    phaseProgress(runId, "security", 20);
    securityReport = await secAnalyzer.analyze(config.projectPath, inventory, config.enableSecurity);
    phaseProgress(runId, "security", 90);
    jsonReporter.saveSecurity(securityReport);
    allBugs.push(...securityReport.bugs);
    updateRunMetrics(runId, { securityIssues: securityReport.summary.total });
    emit(runId, "security", `Security: ${securityReport.summary.critical} critical, ${securityReport.summary.high} high`);
    phaseComplete(runId, "security");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "security", msg);
    securityReport = {
      findings: [], bugs: [], toolsUsed: [],
      summary: { critical: 0, high: 0, medium: 0, low: 0, total: 0 },
    };
  }

  // =============================================================
  // PHASE 11: Performance Analysis
  // =============================================================
  phaseStart(runId, "performance", "Performance Analysis");
  let perfReport;
  try {
    const perfAnalyzer = new PerformanceAnalyzer(llm);
    emit(runId, "performance", "Running performance analysis...");
    phaseProgress(runId, "performance", 20);
    perfReport = await perfAnalyzer.analyze(config.projectPath, inventory, config.enablePerformance);
    phaseProgress(runId, "performance", 80);
    jsonReporter.savePerformance(perfReport);
    allBugs.push(...perfReport.bugs);
    updateRunMetrics(runId, { performanceAlerts: perfReport.summary.alerts });
    emit(runId, "performance", `Performance: ${perfReport.summary.total} findings, ${perfReport.summary.alerts} alerts`);
    phaseComplete(runId, "performance");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "performance", msg);
    perfReport = {
      findings: [], bugs: [], summary: { total: 0, alerts: 0, critical: 0 }, toolsUsed: [],
    };
  }

  // =============================================================
  // PHASE 12: Report Generation
  // =============================================================
  phaseStart(runId, "report_gen", "Final Report Generation");
  let finalReport;
  try {
    jsonReporter.saveMergedBugs(allBugs);

    const artifacts = [
      "inventory/project_inventory.json",
      "inventory/srs_normalized.json",
      "reports/requirements_traceability.json",
      "reports/missing_parts_report.json",
      "reports/quality_review.json",
      "reports/quality_gate.json",
      "reports/security_report.json",
      "reports/security_findings.json",
      "reports/performance_report.json",
      "bugs/all_bugs_merged.json",
      "bugs/unit_test_bugs.json",
      "bugs/integration_test_bugs.json",
      "bugs/security_bugs.json",
      "bugs/srs_gap_bugs.json",
    ].map((a) => path.join(outputPath, a));

    finalReport = jsonReporter.buildFinalReport({
      run, inventory, srs, traceability: traceabilityReport,
      unitTests: unitTestSuite, integrationTests: integrationTestSuite,
      security: securityReport, performance: perfReport,
      quality: qualityReport, allBugs, artifacts,
    });

    jsonReporter.saveFinalReport(finalReport);
    updateRunMetrics(runId, {
      warnings: allBugs.filter((b) => b.severity === "medium").length,
      passed: qualityReport.score.passed,
      qualityScore: qualityReport.score.overall,
    });

    emit(runId, "report_gen", "Final JSON report saved");
    phaseComplete(runId, "report_gen");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "report_gen", msg);
    finalReport = null;
  }

  // =============================================================
  // PHASE 13: PDF Generation
  // =============================================================
  phaseStart(runId, "pdf_gen", "PDF Report Generation");
  try {
    if (finalReport) {
      const htmlReporter = new HTMLReporter();
      const htmlPath = htmlReporter.generateHTML(finalReport, outputPath);
      emit(runId, "pdf_gen", "HTML report generated");
      phaseProgress(runId, "pdf_gen", 50);

      const pdfReporter = new PDFReporter();
      const pdfPath = await pdfReporter.generatePDF(finalReport, htmlPath, outputPath);
      emit(runId, "pdf_gen", `PDF saved: ${pdfPath}`);
    }
    phaseComplete(runId, "pdf_gen");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    phaseError(runId, "pdf_gen", msg);
    emit(runId, "pdf_gen", `PDF generation skipped: ${msg}`);
  }

  // Save provider log
  try {
    const providerLog = llm.getProviderLog();
    fs.writeFileSync(
      path.join(outputPath, "raw-logs", "llm-provider-log.json"),
      JSON.stringify(providerLog, null, 2),
      "utf-8"
    );
  } catch {}

  updateRunStatus(runId, "completed");
  emit(runId, "complete", "Analysis complete!");
  emitProgress(runId, buildEvent("complete", { message: "Analysis pipeline completed", data: { outputPath } }));
}
