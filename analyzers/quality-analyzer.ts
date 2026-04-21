import fs from "fs";
import path from "path";
import type { ProjectInventory, QualityScore } from "@/types";
import type { LLMRouter } from "@/providers/llm-router";
import { runESLint } from "@/executors/eslint-executor";
import { runCommand, checkCommandAvailable } from "@/executors/runner";

export interface QualityReport {
  score: QualityScore;
  eslintIssues: { errorCount: number; warningCount: number };
  typeErrors: number;
  duplications: number;
  maintainabilityIssues: string[];
  architectureIssues: string[];
  llmReview?: string;
  raw: Record<string, unknown>;
}

export class QualityAnalyzer {
  constructor(private llm: LLMRouter) {}

  async analyze(
    projectPath: string,
    inventory: ProjectInventory
  ): Promise<QualityReport> {
    const [eslintResult, typeCheckResult] = await Promise.all([
      runESLint(projectPath).catch(() => ({ available: false, issues: [], errorCount: 0, warningCount: 0, raw: "" })),
      this.runTypeCheck(projectPath),
    ]);

    const duplications = this.detectDuplications(projectPath, inventory);
    const architectureIssues = this.detectArchitectureIssues(inventory);
    const maintainabilityIssues = this.detectMaintainabilityIssues(projectPath, inventory);

    const llmReview = await this.getLLMReview(inventory, {
      eslintErrors: eslintResult.errorCount,
      typeErrors: typeCheckResult.errorCount,
      architectureIssues,
    }).catch(() => undefined);

    const score = this.computeScore({
      eslintErrors: eslintResult.errorCount,
      eslintWarnings: eslintResult.warningCount,
      typeErrors: typeCheckResult.errorCount,
      duplications,
      architectureIssues: architectureIssues.length,
      totalFiles: inventory.allFiles.length,
    });

    return {
      score,
      eslintIssues: { errorCount: eslintResult.errorCount, warningCount: eslintResult.warningCount },
      typeErrors: typeCheckResult.errorCount,
      duplications,
      maintainabilityIssues,
      architectureIssues,
      llmReview,
      raw: {
        eslint: eslintResult.raw,
        typeCheck: typeCheckResult.raw,
      },
    };
  }

  private async runTypeCheck(projectPath: string): Promise<{ errorCount: number; raw: string }> {
    const tsconfigPath = path.join(projectPath, "tsconfig.json");
    if (!fs.existsSync(tsconfigPath)) {
      return { errorCount: 0, raw: "No tsconfig.json found" };
    }

    const result = await runCommand("npx", ["tsc", "--noEmit", "--pretty", "false"], {
      cwd: projectPath,
      timeoutMs: 60000,
    });

    const errorMatches = result.stdout.match(/error TS\d+/g) || [];
    return {
      errorCount: errorMatches.length,
      raw: result.stdout,
    };
  }

  private detectDuplications(projectPath: string, inventory: ProjectInventory): number {
    let dupCount = 0;
    const codeFiles = inventory.allFiles.filter((f) =>
      /\.(js|ts|jsx|tsx)$/.test(f) && !f.includes("node_modules")
    ).slice(0, 50);

    const contentMap = new Map<string, string[]>();
    for (const f of codeFiles) {
      try {
        const content = fs.readFileSync(path.join(projectPath, f), "utf-8");
        const lines = content.split("\n").filter((l) => l.trim().length > 20);
        for (const line of lines) {
          const normalized = line.trim();
          const existing = contentMap.get(normalized) || [];
          if (existing.length === 1) dupCount++;
          contentMap.set(normalized, [...existing, f]);
        }
      } catch {}
    }
    return Math.min(dupCount, 9999);
  }

  private detectArchitectureIssues(inventory: ProjectInventory): string[] {
    const issues: string[] = [];

    if (inventory.controllers.length === 0 && inventory.routes.length > 5) {
      issues.push("Routes detected but no controller layer found - consider MVC separation");
    }
    if (inventory.services.length === 0 && inventory.models.length > 2) {
      issues.push("Models present but no service layer - business logic may be in controllers");
    }
    if (inventory.testFiles.length === 0) {
      issues.push("No test files found - project lacks automated test coverage");
    }
    if (inventory.envFiles.length === 0) {
      issues.push("No .env.example found - environment configuration is undocumented");
    }
    if (inventory.middleware.length === 0 && inventory.projectType !== "nextjs_fullstack") {
      issues.push("No middleware layer detected - authentication/validation may be inline");
    }

    return issues;
  }

  private detectMaintainabilityIssues(
    projectPath: string,
    inventory: ProjectInventory
  ): string[] {
    const issues: string[] = [];
    const longFiles = inventory.allFiles.filter((f) => {
      try {
        const content = fs.readFileSync(path.join(projectPath, f), "utf-8");
        return content.split("\n").length > 400;
      } catch {
        return false;
      }
    });

    if (longFiles.length > 0) {
      issues.push(`${longFiles.length} files exceed 400 lines - consider splitting`);
    }

    const noCommentFiles = inventory.allFiles
      .filter((f) => /\.(js|ts|jsx|tsx)$/.test(f))
      .filter((f) => {
        try {
          const content = fs.readFileSync(path.join(projectPath, f), "utf-8");
          return !content.includes("//") && !content.includes("/*") && content.length > 500;
        } catch {
          return false;
        }
      });

    if (noCommentFiles.length > 5) {
      issues.push(`${noCommentFiles.length} large files have no comments`);
    }

    return issues;
  }

  private async getLLMReview(
    inventory: ProjectInventory,
    metrics: { eslintErrors: number; typeErrors: number; architectureIssues: string[] }
  ): Promise<string> {
    const prompt = `Perform a brief code quality review for this project:
Project Type: ${inventory.projectType}
Frameworks: ${inventory.frameworks.join(", ")}
Total Files: ${inventory.allFiles.length}
Models: ${inventory.models.length}, Controllers: ${inventory.controllers.length}, Services: ${inventory.services.length}
ESLint Errors: ${metrics.eslintErrors}
TypeScript Errors: ${metrics.typeErrors}
Architecture Issues: ${metrics.architectureIssues.join("; ")}

Provide 3-5 actionable quality improvement recommendations in 200 words or less.`;

    return this.llm.simplePrompt("code_quality_review", prompt);
  }

  private computeScore(metrics: {
    eslintErrors: number;
    eslintWarnings: number;
    typeErrors: number;
    duplications: number;
    architectureIssues: number;
    totalFiles: number;
  }): QualityScore {
    const normalizedEslint = Math.max(
      0,
      100 - (metrics.eslintErrors * 5 + metrics.eslintWarnings * 1)
    );
    const normalizedType = Math.max(0, 100 - metrics.typeErrors * 3);
    const normalizedDup = Math.max(0, 100 - metrics.duplications * 0.1);
    const normalizedArch = Math.max(0, 100 - metrics.architectureIssues * 10);

    const codeQuality = Math.round(
      normalizedEslint * 0.4 +
        normalizedType * 0.3 +
        normalizedDup * 0.15 +
        normalizedArch * 0.15
    );

    const functionalCorrectness = Math.round(
      Math.max(0, 100 - metrics.eslintErrors * 2 - metrics.typeErrors * 3)
    );
    const security = Math.round(
      Math.max(0, 100 - metrics.architectureIssues * 5)
    );
    const performance = 70;

    const overall = Math.round(
      functionalCorrectness * 0.4 +
        codeQuality * 0.25 +
        security * 0.2 +
        performance * 0.15
    );

    return {
      functionalCorrectness: Math.min(100, functionalCorrectness),
      codeQuality: Math.min(100, codeQuality),
      security: Math.min(100, security),
      performance,
      overall: Math.min(100, overall),
      passed: overall >= 60,
      details: { ...metrics, normalizedEslint, normalizedType },
    };
  }
}
