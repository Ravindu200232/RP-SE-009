import fs from "fs";
import path from "path";
import type { ProjectInventory, SecurityFinding, BugRecord, Severity } from "@/types";
import type { LLMRouter } from "@/providers/llm-router";
import { runNpmAudit } from "@/executors/npm-audit-executor";
import { runSemgrep } from "@/executors/semgrep-executor";
import { v4 as uuidv4 } from "uuid";

export interface SecurityReport {
  findings: SecurityFinding[];
  bugs: BugRecord[];
  summary: { critical: number; high: number; medium: number; low: number; total: number };
  toolsUsed: string[];
  llmAnalysis?: string;
}

export class SecurityAnalyzer {
  constructor(private llm: LLMRouter) {}

  async analyze(
    projectPath: string,
    inventory: ProjectInventory,
    enableSemgrep: boolean
  ): Promise<SecurityReport> {
    const allFindings: SecurityFinding[] = [];
    const toolsUsed: string[] = [];

    // Static code analysis
    const staticFindings = this.runStaticAnalysis(projectPath, inventory);
    allFindings.push(...staticFindings);
    toolsUsed.push("static-analysis");

    // npm audit
    const auditResult = await runNpmAudit(projectPath);
    if (auditResult.available) {
      allFindings.push(...auditResult.findings);
      toolsUsed.push("npm-audit");
    }

    // Semgrep
    if (enableSemgrep) {
      const semgrepResult = await runSemgrep(projectPath);
      if (semgrepResult.available) {
        allFindings.push(...semgrepResult.findings);
        toolsUsed.push("semgrep");
      }
    }

    const summary = this.computeSummary(allFindings);
    const bugs = this.findingsToBugs(allFindings);

    const llmAnalysis = await this.getLLMAnalysis(allFindings, inventory).catch(
      () => undefined
    );

    return { findings: allFindings, bugs, summary, toolsUsed, llmAnalysis };
  }

  private runStaticAnalysis(
    projectPath: string,
    inventory: ProjectInventory
  ): SecurityFinding[] {
    const findings: SecurityFinding[] = [];
    let id = 0;

    const codeFiles = inventory.allFiles
      .filter((f) => /\.(js|ts|jsx|tsx)$/.test(f))
      .slice(0, 100);

    for (const relFile of codeFiles) {
      try {
        const content = fs.readFileSync(path.join(projectPath, relFile), "utf-8");
        const lines = content.split("\n");

        lines.forEach((line, lineNum) => {
          const lineLower = line.toLowerCase();

          if (/process\.env\.[A-Z_]+ *= *['"]/.test(line)) {
            findings.push({
              id: `static-${++id}`,
              rule: "hardcoded-env-default",
              severity: "medium",
              file: relFile,
              line: lineNum + 1,
              message: "Possible hardcoded secret or env default value",
              tool: "static-analysis",
              cwe: "CWE-798",
            });
          }

          if (/password\s*=\s*['"][^'"]{3,}['"]/.test(lineLower) ||
              /secret\s*=\s*['"][^'"]{3,}['"]/.test(lineLower) ||
              /api_?key\s*=\s*['"][^'"]{8,}['"]/.test(lineLower)) {
            findings.push({
              id: `static-${++id}`,
              rule: "hardcoded-secret",
              severity: "critical",
              file: relFile,
              line: lineNum + 1,
              message: "Potential hardcoded secret detected",
              tool: "static-analysis",
              cwe: "CWE-798",
              owasp: "A02:2021",
            });
          }

          if (/eval\s*\(/.test(line)) {
            findings.push({
              id: `static-${++id}`,
              rule: "eval-usage",
              severity: "high",
              file: relFile,
              line: lineNum + 1,
              message: "eval() is dangerous and can lead to code injection",
              tool: "static-analysis",
              cwe: "CWE-95",
              owasp: "A03:2021",
            });
          }

          if (/innerHTML\s*=/.test(line) || /dangerouslySetInnerHTML/.test(line)) {
            findings.push({
              id: `static-${++id}`,
              rule: "xss-risk",
              severity: "high",
              file: relFile,
              line: lineNum + 1,
              message: "Direct HTML injection can lead to XSS",
              tool: "static-analysis",
              cwe: "CWE-79",
              owasp: "A03:2021",
            });
          }

          if (/console\.(log|error|warn)\s*\(.*(?:password|token|secret|key)/i.test(line)) {
            findings.push({
              id: `static-${++id}`,
              rule: "sensitive-data-log",
              severity: "medium",
              file: relFile,
              line: lineNum + 1,
              message: "Sensitive data may be logged to console",
              tool: "static-analysis",
              cwe: "CWE-532",
              owasp: "A09:2021",
            });
          }

          if (/cors\(\)/.test(lineLower) || /allowedorigins.*\*/.test(lineLower)) {
            findings.push({
              id: `static-${++id}`,
              rule: "open-cors",
              severity: "medium",
              file: relFile,
              line: lineNum + 1,
              message: "CORS may be too permissive (wildcard or no config)",
              tool: "static-analysis",
              owasp: "A01:2021",
            });
          }

          if (/\.find\(.*req\.(?:body|params|query)/.test(line) ||
              /\$where.*req\./.test(line)) {
            findings.push({
              id: `static-${++id}`,
              rule: "nosql-injection-risk",
              severity: "high",
              file: relFile,
              line: lineNum + 1,
              message: "Possible NoSQL injection - unsanitized user input in query",
              tool: "static-analysis",
              cwe: "CWE-943",
              owasp: "A03:2021",
            });
          }

          if (/jwt\.sign\s*\([^,]+,\s*['"][^'"]{1,10}['"]/.test(line)) {
            findings.push({
              id: `static-${++id}`,
              rule: "weak-jwt-secret",
              severity: "high",
              file: relFile,
              line: lineNum + 1,
              message: "JWT signed with potentially weak secret (short string literal)",
              tool: "static-analysis",
              cwe: "CWE-798",
              owasp: "A02:2021",
            });
          }
        });
      } catch {}
    }

    return findings;
  }

  private computeSummary(findings: SecurityFinding[]) {
    return {
      critical: findings.filter((f) => f.severity === "critical").length,
      high: findings.filter((f) => f.severity === "high").length,
      medium: findings.filter((f) => f.severity === "medium").length,
      low: findings.filter((f) => f.severity === "low").length,
      total: findings.length,
    };
  }

  private findingsToBugs(findings: SecurityFinding[]): BugRecord[] {
    return findings
      .filter((f) => f.severity === "critical" || f.severity === "high")
      .map((f) => ({
        bugId: `SEC-${uuidv4().substring(0, 8)}`,
        phase: "security",
        severity: f.severity,
        category: "security" as const,
        title: f.rule,
        description: f.message,
        affectedFiles: [f.file],
        affectedRoutes: [],
        requirementIds: [],
        evidence: `${f.file}${f.line ? `:${f.line}` : ""}`,
        reproductionSteps: ["Inspect the flagged code location"],
        expectedBehavior: "No security vulnerability",
        actualBehavior: f.message,
        suggestedFix: "Review and remediate the identified security issue",
        confidenceScore: 0.7,
        sourceTool: f.tool,
        timestamp: new Date().toISOString(),
      }));
  }

  private async getLLMAnalysis(
    findings: SecurityFinding[],
    inventory: ProjectInventory
  ): Promise<string> {
    const top = findings
      .filter((f) => f.severity === "critical" || f.severity === "high")
      .slice(0, 10)
      .map((f) => `- [${f.severity.toUpperCase()}] ${f.rule}: ${f.message} (${f.file})`)
      .join("\n");

    const prompt = `Security analysis for a ${inventory.projectType} project.
Top security findings:
${top || "No critical/high findings"}

Provide a 200-word security assessment and top 3 remediation priorities.`;

    return this.llm.simplePrompt("security_reasoning", prompt);
  }
}
