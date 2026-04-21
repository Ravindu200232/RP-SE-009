import path from "path";
import fs from "fs";
import { runCommand, checkCommandAvailable } from "./runner";

export interface ESLintIssue {
  file: string;
  line: number;
  column: number;
  severity: "error" | "warning";
  message: string;
  rule?: string;
}

export interface ESLintResult {
  available: boolean;
  issues: ESLintIssue[];
  errorCount: number;
  warningCount: number;
  raw: string;
}

export async function runESLint(projectPath: string): Promise<ESLintResult> {
  const available = await checkCommandAvailable("npx");
  if (!available) {
    return { available: false, issues: [], errorCount: 0, warningCount: 0, raw: "" };
  }

  const result = await runCommand(
    "npx",
    ["eslint", ".", "--format", "json", "--max-warnings", "9999", "--ext", ".js,.ts,.jsx,.tsx"],
    {
      cwd: projectPath,
      timeoutMs: 60000,
    }
  );

  const issues: ESLintIssue[] = [];
  let errorCount = 0;
  let warningCount = 0;

  try {
    const data = JSON.parse(result.stdout || result.stderr || "[]") as Array<{
      filePath: string;
      messages: Array<{
        line: number;
        column: number;
        severity: number;
        message: string;
        ruleId?: string;
      }>;
      errorCount: number;
      warningCount: number;
    }>;

    for (const fileResult of data) {
      errorCount += fileResult.errorCount;
      warningCount += fileResult.warningCount;
      const relFile = fileResult.filePath.replace(projectPath, "").replace(/^[/\\]/, "");
      for (const msg of fileResult.messages) {
        issues.push({
          file: relFile,
          line: msg.line,
          column: msg.column,
          severity: msg.severity === 2 ? "error" : "warning",
          message: msg.message,
          rule: msg.ruleId ?? undefined,
        });
      }
    }
  } catch {
    // parse failure
  }

  return { available: true, issues, errorCount, warningCount, raw: result.stdout };
}
