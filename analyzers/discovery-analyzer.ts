import fs from "fs";
import path from "path";
import type { ProjectInventory } from "@/types";
import { ProjectParser } from "@/parsers/project-parser";
import type { LLMRouter } from "@/providers/llm-router";

export class DiscoveryAnalyzer {
  private parser: ProjectParser;
  private llm: LLMRouter;

  constructor(llm: LLMRouter) {
    this.parser = new ProjectParser();
    this.llm = llm;
  }

  async analyze(projectPath: string): Promise<ProjectInventory> {
    const inventory = await this.parser.parse(projectPath);
    return inventory;
  }

  async summarize(inventory: ProjectInventory): Promise<string> {
    const prompt = `Summarize this software project inventory in 3-4 sentences:
Project Type: ${inventory.projectType}
Frameworks: ${inventory.frameworks.join(", ")}
Total Files: ${inventory.allFiles.length}
Has TypeScript: ${inventory.hasTypeScript}
Models: ${inventory.models.length}
Controllers: ${inventory.controllers.length}
Services: ${inventory.services.length}
Routes: ${inventory.routes.length}
Components: ${inventory.components.length}
`;
    return this.llm.simplePrompt("folder_summarization", prompt);
  }

  readFileContent(projectPath: string, filePath: string): string {
    try {
      const full = path.join(projectPath, filePath);
      const stat = fs.statSync(full);
      if (stat.size > 200 * 1024) return `[File too large: ${stat.size} bytes]`;
      return fs.readFileSync(full, "utf-8");
    } catch {
      return "";
    }
  }

  getKeyFileContents(
    projectPath: string,
    inventory: ProjectInventory,
    maxFiles = 10
  ): Record<string, string> {
    const result: Record<string, string> = {};
    const priority = [
      ...inventory.entryPoints,
      ...inventory.models.slice(0, 3).map((f) => f.path),
      ...inventory.controllers.slice(0, 3).map((f) => f.path),
      ...inventory.services.slice(0, 2).map((f) => f.path),
    ].slice(0, maxFiles);

    for (const f of priority) {
      result[f] = this.readFileContent(projectPath, f);
    }
    return result;
  }
}
