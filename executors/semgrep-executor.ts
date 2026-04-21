import { runCommand, checkCommandAvailable } from "./runner";
import type { SecurityFinding, Severity } from "@/types";

export interface SemgrepResult {
  available: boolean;
  findings: SecurityFinding[];
  raw: string;
}

export async function runSemgrep(projectPath: string): Promise<SemgrepResult> {
  const available = await checkCommandAvailable("semgrep");
  if (!available) {
    return { available: false, findings: [], raw: "semgrep not installed" };
  }

  const result = await runCommand(
    "semgrep",
    [
      "--config=auto",
      "--json",
      "--no-git-ignore",
      "--timeout=60",
      ".",
    ],
    {
      cwd: projectPath,
      timeoutMs: 120000,
    }
  );

  const findings: SecurityFinding[] = [];

  try {
    const data = JSON.parse(result.stdout) as {
      results?: Array<{
        check_id: string;
        path: string;
        start?: { line: number };
        extra?: { message: string; severity: string; metadata?: { cwe?: string[]; owasp?: string[] } };
      }>;
    };

    let id = 0;
    for (const item of data.results || []) {
      findings.push({
        id: `semgrep-${++id}`,
        rule: item.check_id,
        severity: normalizeSeverity(item.extra?.severity || "warning"),
        file: item.path,
        line: item.start?.line,
        message: item.extra?.message || item.check_id,
        tool: "semgrep",
        cwe: item.extra?.metadata?.cwe?.[0],
        owasp: item.extra?.metadata?.owasp?.[0],
      });
    }
  } catch {
    // parse failure
  }

  return { available: true, findings, raw: result.stdout };
}

function normalizeSeverity(s: string): Severity {
  switch (s?.toLowerCase()) {
    case "error": return "critical";
    case "warning": return "medium";
    case "info": return "low";
    default: return "info";
  }
}
