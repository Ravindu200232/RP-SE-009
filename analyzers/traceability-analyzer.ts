import fs from "fs";
import path from "path";
import type {
  SRSDocument,
  ProjectInventory,
  TraceabilityRecord,
  RequirementStatus,
} from "@/types";
import type { LLMRouter } from "@/providers/llm-router";

export interface TraceabilityReport {
  records: TraceabilityRecord[];
  implemented: number;
  partiallyImplemented: number;
  missing: number;
  unverifiable: number;
  coveragePercent: number;
}

export class TraceabilityAnalyzer {
  constructor(private llm: LLMRouter) {}

  async analyze(
    srs: SRSDocument,
    inventory: ProjectInventory,
    projectPath: string
  ): Promise<TraceabilityReport> {
    const allReqs = [
      ...srs.functionalRequirements,
      ...srs.nonFunctionalRequirements,
    ];

    if (allReqs.length === 0) {
      return {
        records: [],
        implemented: 0,
        partiallyImplemented: 0,
        missing: 0,
        unverifiable: 0,
        coveragePercent: 0,
      };
    }

    const projectContext = this.buildProjectContext(inventory, projectPath);
    const records: TraceabilityRecord[] = [];

    // Batch requirements for LLM analysis
    const batchSize = 10;
    for (let i = 0; i < allReqs.length; i += batchSize) {
      const batch = allReqs.slice(i, i + batchSize);
      const batchRecords = await this.analyzeBatch(batch, projectContext, inventory);
      records.push(...batchRecords);
    }

    const implemented = records.filter((r) => r.status === "implemented").length;
    const partiallyImplemented = records.filter(
      (r) => r.status === "partially_implemented"
    ).length;
    const missing = records.filter((r) => r.status === "missing").length;
    const unverifiable = records.filter((r) => r.status === "unverifiable").length;
    const coveragePercent = allReqs.length
      ? Math.round(((implemented + partiallyImplemented * 0.5) / allReqs.length) * 100)
      : 0;

    return {
      records,
      implemented,
      partiallyImplemented,
      missing,
      unverifiable,
      coveragePercent,
    };
  }

  private async analyzeBatch(
    requirements: SRSDocument["functionalRequirements"],
    projectContext: string,
    inventory: ProjectInventory
  ): Promise<TraceabilityRecord[]> {
    const reqList = requirements
      .map((r) => `- ID: ${r.id}\n  Title: ${r.title}\n  Description: ${r.description}`)
      .join("\n");

    const systemPrompt = `You are a software QA engineer performing requirement traceability analysis.
Given a project inventory and a list of requirements, determine which are implemented, partially implemented, missing, or unverifiable.
Respond ONLY with a valid JSON array. No markdown, no explanation.`;

    const prompt = `PROJECT INVENTORY:
${projectContext}

REQUIREMENTS TO ANALYZE:
${reqList}

For each requirement, respond with a JSON object in this exact array format:
[
  {
    "requirementId": "REQ-1",
    "status": "implemented|partially_implemented|missing|unverifiable",
    "files": ["list of relevant files"],
    "evidence": ["brief evidence snippet"],
    "confidence": 0.85,
    "reasoning": "brief explanation"
  }
]`;

    try {
      const response = await this.llm.chat(
        "traceability",
        [{ role: "user", content: prompt }],
        systemPrompt
      );

      const jsonStr = this.extractJSON(response.content);
      const parsed = JSON.parse(jsonStr) as Array<{
        requirementId: string;
        status: RequirementStatus;
        files?: string[];
        evidence?: string[];
        confidence?: number;
        reasoning?: string;
      }>;

      return requirements.map((req, i) => {
        const analysis = parsed.find((p) => p.requirementId === req.id) || parsed[i];
        return {
          requirementId: req.id,
          requirementTitle: req.title,
          status: analysis?.status || "unverifiable",
          files: analysis?.files || [],
          routes: this.matchRoutes(req, inventory),
          components: this.matchComponents(req, inventory),
          models: this.matchModels(req, inventory),
          tests: [],
          evidence: analysis?.evidence || [],
          confidence: analysis?.confidence || 0.5,
          llmReasoning: analysis?.reasoning,
        };
      });
    } catch {
      return requirements.map((req) => ({
        requirementId: req.id,
        requirementTitle: req.title,
        status: "unverifiable" as RequirementStatus,
        files: this.keywordMatchFiles(req.description, inventory),
        routes: this.matchRoutes(req, inventory),
        components: this.matchComponents(req, inventory),
        models: this.matchModels(req, inventory),
        tests: [],
        evidence: [],
        confidence: 0.3,
      }));
    }
  }

  private buildProjectContext(inventory: ProjectInventory, projectPath: string): string {
    const lines: string[] = [
      `Project Type: ${inventory.projectType}`,
      `Frameworks: ${inventory.frameworks.join(", ")}`,
      `Total Files: ${inventory.allFiles.length}`,
      `Routes: ${inventory.routes.map((r) => `${r.method} ${r.path}`).join(", ")}`,
      `Models: ${inventory.models.map((m) => m.name).join(", ")}`,
      `Controllers: ${inventory.controllers.map((c) => c.name).join(", ")}`,
      `Services: ${inventory.services.map((s) => s.name).join(", ")}`,
      `Components: ${inventory.components.slice(0, 20).map((c) => c.name).join(", ")}`,
    ];
    return lines.join("\n");
  }

  private extractJSON(content: string): string {
    const arrayMatch = content.match(/\[[\s\S]*\]/);
    if (arrayMatch) return arrayMatch[0];
    return "[]";
  }

  private keywordMatchFiles(description: string, inventory: ProjectInventory): string[] {
    const keywords = description.toLowerCase().split(/\s+/).filter((w) => w.length > 4);
    return inventory.allFiles.filter((f) => {
      const fl = f.toLowerCase();
      return keywords.some((kw) => fl.includes(kw));
    }).slice(0, 5);
  }

  private matchRoutes(req: { title: string; description: string }, inventory: ProjectInventory): string[] {
    const text = `${req.title} ${req.description}`.toLowerCase();
    return inventory.routes
      .filter((r) => {
        const routeLower = r.path.toLowerCase();
        return text.split(/\s+/).some((word) => word.length > 3 && routeLower.includes(word));
      })
      .map((r) => `${r.method || "ANY"} ${r.path}`)
      .slice(0, 5);
  }

  private matchComponents(req: { title: string }, inventory: ProjectInventory): string[] {
    const text = req.title.toLowerCase();
    return inventory.components
      .filter((c) => {
        const cl = c.name.toLowerCase();
        return text.split(/\s+/).some((word) => word.length > 3 && cl.includes(word));
      })
      .map((c) => c.path)
      .slice(0, 3);
  }

  private matchModels(req: { title: string; description: string }, inventory: ProjectInventory): string[] {
    const text = `${req.title} ${req.description}`.toLowerCase();
    return inventory.models
      .filter((m) => {
        const ml = m.name.toLowerCase().replace(/model|schema/i, "");
        return text.includes(ml) && ml.length > 2;
      })
      .map((m) => m.path)
      .slice(0, 3);
  }
}
