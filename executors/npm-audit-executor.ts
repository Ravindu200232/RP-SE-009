import path from "path";
import { runCommand, checkCommandAvailable } from "./runner";
import type { SecurityFinding, Severity } from "@/types";

export interface NpmAuditResult {
  available: boolean;
  findings: SecurityFinding[];
  raw: string;
  summary: { critical: number; high: number; medium: number; low: number };
}

export async function runNpmAudit(projectPath: string): Promise<NpmAuditResult> {
  const available = await checkCommandAvailable("npm");
  if (!available) {
    return { available: false, findings: [], raw: "", summary: { critical: 0, high: 0, medium: 0, low: 0 } };
  }

  const result = await runCommand("npm", ["audit", "--json"], {
    cwd: projectPath,
    timeoutMs: 60000,
  });

  const summary = { critical: 0, high: 0, medium: 0, low: 0 };
  const findings: SecurityFinding[] = [];

  try {
    const data = JSON.parse(result.stdout) as {
      vulnerabilities?: Record<string, {
        name: string;
        severity: string;
        via: Array<{ title?: string; url?: string; range?: string }>;
        range?: string;
        fixAvailable?: boolean;
      }>;
      metadata?: { vulnerabilities: Record<string, number> };
    };

    if (data.metadata?.vulnerabilities) {
      const v = data.metadata.vulnerabilities;
      summary.critical = Number(v.critical || 0);
      summary.high = Number(v.high || 0);
      summary.medium = Number(v.moderate || 0);
      summary.low = Number(v.low || 0);
    }

    let id = 0;
    if (data.vulnerabilities) {
      for (const [pkgName, vuln] of Object.entries(data.vulnerabilities)) {
        const sev = normalizeSeverity(vuln.severity);
        const via = Array.isArray(vuln.via) ? vuln.via : [];
        const firstVia = via.find((v) => typeof v === "object" && v.title);
        findings.push({
          id: `npm-audit-${++id}`,
          rule: "dependency-vulnerability",
          severity: sev,
          file: "package.json",
          message: `${pkgName}@${vuln.range || "unknown"}: ${
            firstVia?.title || "Known vulnerability"
          }`,
          tool: "npm-audit",
          owasp: "A06:2021",
        });
      }
    }
  } catch {
    // parse failure - just use empty results
  }

  return { available: true, findings, raw: result.stdout, summary };
}

function normalizeSeverity(s: string): Severity {
  switch (s?.toLowerCase()) {
    case "critical": return "critical";
    case "high": return "high";
    case "moderate": return "medium";
    case "low": return "low";
    default: return "info";
  }
}
