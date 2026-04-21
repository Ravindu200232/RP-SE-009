import fs from "fs";
import path from "path";
import type { ProjectInventory, PerformanceFinding, BugRecord, Severity } from "@/types";
import type { LLMRouter } from "@/providers/llm-router";
import { runCommand, checkCommandAvailable } from "@/executors/runner";
import { v4 as uuidv4 } from "uuid";

export interface PerformanceReport {
  findings: PerformanceFinding[];
  bugs: BugRecord[];
  summary: { total: number; alerts: number; critical: number };
  toolsUsed: string[];
  autocannon?: AutocannonResult;
}

export interface AutocannonResult {
  available: boolean;
  requests?: { average: number; stddev: number };
  latency?: { average: number; p99: number };
  errors?: number;
}

export class PerformanceAnalyzer {
  constructor(private llm: LLMRouter) {}

  async analyze(
    projectPath: string,
    inventory: ProjectInventory,
    enableK6: boolean
  ): Promise<PerformanceReport> {
    const findings: PerformanceFinding[] = [];
    const toolsUsed: string[] = [];

    const staticFindings = this.runStaticAnalysis(projectPath, inventory);
    findings.push(...staticFindings);
    toolsUsed.push("static-analysis");

    let autocannon: AutocannonResult | undefined;
    if (enableK6) {
      const acResult = await this.runAutocannon(inventory).catch(
        () => ({ available: false } as AutocannonResult)
      );
      autocannon = acResult;
      if (acResult.available) toolsUsed.push("autocannon");
    }

    const summary = {
      total: findings.length,
      alerts: findings.filter((f) => f.severity !== "info").length,
      critical: findings.filter((f) => f.severity === "critical" || f.severity === "high").length,
    };

    const bugs = this.findingsToBugs(findings);

    return { findings, bugs, summary, toolsUsed, autocannon };
  }

  private runStaticAnalysis(
    projectPath: string,
    inventory: ProjectInventory
  ): PerformanceFinding[] {
    const findings: PerformanceFinding[] = [];
    let id = 0;

    const codeFiles = inventory.allFiles
      .filter((f) => /\.(js|ts|jsx|tsx)$/.test(f))
      .slice(0, 80);

    for (const relFile of codeFiles) {
      try {
        const content = fs.readFileSync(path.join(projectPath, relFile), "utf-8");
        const lines = content.split("\n");

        lines.forEach((line, lineNum) => {
          if (/\.find\(\)/.test(line) && /await/.test(line) && !/\.limit\(/.test(line) &&
              !/\.select\(/.test(line)) {
            findings.push({
              id: `perf-${++id}`,
              type: "missing-pagination",
              severity: "medium",
              file: relFile,
              message: `Potential missing pagination/limit in DB query at line ${lineNum + 1}`,
            });
          }

          if (/for\s*\(.*\)\s*\{[\s\S]{0,200}await\s/.test(line)) {
            findings.push({
              id: `perf-${++id}`,
              type: "sequential-await-in-loop",
              severity: "high",
              file: relFile,
              message: `Await inside loop at line ${lineNum + 1} - consider Promise.all()`,
            });
          }

          if (/\.findOne\(.*\{/.test(line) && !/index/i.test(content.substring(0, 500))) {
            findings.push({
              id: `perf-${++id}`,
              type: "missing-index-hint",
              severity: "low",
              file: relFile,
              message: `DB query at line ${lineNum + 1} - verify appropriate indexes exist`,
            });
          }

          if (/require\(/.test(line) && /\bfunction\b|\bconst\b/.test(
              content.split("\n").slice(Math.max(0, lineNum - 2), lineNum + 2).join(" ")
          )) {
            findings.push({
              id: `perf-${++id}`,
              type: "require-inside-function",
              severity: "medium",
              file: relFile,
              message: `Dynamic require() inside function at line ${lineNum + 1} - move to top-level`,
            });
          }
        });

        if (content.split("\n").length > 600) {
          findings.push({
            id: `perf-${++id}`,
            type: "large-file",
            severity: "low",
            file: relFile,
            message: `File has ${content.split("\n").length} lines - consider code splitting`,
          });
        }
      } catch {}
    }

    if (inventory.projectType === "nextjs_fullstack" || inventory.projectType === "nextjs_frontend_separate_backend") {
      const apiRoutes = inventory.apiHandlers.slice(0, 30);
      for (const handler of apiRoutes) {
        try {
          const content = fs.readFileSync(path.join(projectPath, handler.path), "utf-8");
          if (!content.includes("cache") && !content.includes("revalidate")) {
            findings.push({
              id: `perf-${++id}`,
              type: "no-caching",
              severity: "low",
              file: handler.path,
              message: "API route has no caching headers or revalidation strategy",
            });
          }
        } catch {}
      }
    }

    return findings;
  }

  private async runAutocannon(inventory: ProjectInventory): Promise<AutocannonResult> {
    const available = await checkCommandAvailable("autocannon");
    if (!available) return { available: false };

    let port = 3000;
    for (const envFile of inventory.envFiles) {
      try {
        const content = fs.readFileSync(envFile, "utf-8");
        const portMatch = content.match(/PORT\s*=\s*(\d+)/);
        if (portMatch) { port = parseInt(portMatch[1]); break; }
      } catch {}
    }

    const result = await runCommand(
      "autocannon",
      ["-c", "10", "-d", "5", "--json", `http://localhost:${port}/`],
      { timeoutMs: 30000 }
    );

    try {
      const data = JSON.parse(result.stdout) as {
        requests: { average: number; stddev: number };
        latency: { average: number; p99: number };
        errors: number;
      };
      return {
        available: true,
        requests: data.requests,
        latency: data.latency,
        errors: data.errors,
      };
    } catch {
      return { available: true };
    }
  }

  private findingsToBugs(findings: PerformanceFinding[]): BugRecord[] {
    return findings
      .filter((f) => f.severity === "high" || f.severity === "critical")
      .map((f) => ({
        bugId: `PERF-${uuidv4().substring(0, 8)}`,
        phase: "performance",
        severity: f.severity,
        category: "performance" as const,
        title: f.type,
        description: f.message,
        affectedFiles: f.file ? [f.file] : [],
        affectedRoutes: [],
        requirementIds: [],
        evidence: f.file || "Code analysis",
        reproductionSteps: ["Profile the identified code path"],
        expectedBehavior: "Efficient execution",
        actualBehavior: f.message,
        suggestedFix: "Optimize the identified performance bottleneck",
        confidenceScore: 0.6,
        sourceTool: "static-analysis",
        timestamp: new Date().toISOString(),
      }));
  }
}
