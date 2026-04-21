import fs from "fs";
import path from "path";
import type { ProjectInventory, FileInfo } from "@/types";
import type { LLMRouter } from "@/providers/llm-router";

export interface GeneratedTestFile {
  targetFile: string;
  testFile: string;
  content: string;
  testCount: number;
}

export class UnitTestGenerator {
  constructor(private llm: LLMRouter) {}

  async generate(
    projectPath: string,
    inventory: ProjectInventory,
    outputDir: string
  ): Promise<GeneratedTestFile[]> {
    const targets = this.buildTargets(inventory);

    const generated: GeneratedTestFile[] = [];
    const failures: string[] = [];
    fs.mkdirSync(outputDir, { recursive: true });

    for (const target of targets) {
      const content = this.readFile(projectPath, target.path);
      if (!content || content.length < 50) continue;

      try {
        const projectTestFilePath = this.getProjectTestFilePath(projectPath, target.path);
        const sourceImportPath = this.getImportPath(projectTestFilePath, projectPath, target.path);
        const testContent = await this.generateTest(target, content, inventory, sourceImportPath);

        fs.mkdirSync(path.dirname(projectTestFilePath), { recursive: true });
        fs.writeFileSync(projectTestFilePath, testContent, "utf-8");

        const snapshotFilePath = path.join(outputDir, this.getSnapshotFileName(target.path));
        fs.writeFileSync(snapshotFilePath, testContent, "utf-8");

        const testCount = (testContent.match(/\bit\(|\btest\(/g) || []).length;
        generated.push({
          targetFile: target.path,
          testFile: projectTestFilePath,
          content: testContent,
          testCount,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        failures.push(`${target.path}: ${message}`);
        console.warn(`[UnitTestGenerator] Failed to generate test for ${target.path}:`, err);
      }
    }

    if (generated.length === 0 && failures.length > 0) {
      throw new Error(`Unit test generation failed for all targets. ${failures.slice(0, 3).join(" | ")}`);
    }

    return generated;
  }

  private async generateTest(
    target: FileInfo,
    content: string,
    inventory: ProjectInventory,
    sourceImportPath: string
  ): Promise<string> {
    const framework = inventory.frameworks.includes("React") ? "vitest + @testing-library/react" : "vitest";
    const isESM = inventory.packageJson
      ? (inventory.packageJson as { type?: string }).type === "module"
      : false;
    const importStyle = isESM ? "esm" : "cjs";

    const systemPrompt = `You are an expert JavaScript/TypeScript test engineer.
Write comprehensive unit tests using Vitest (not Jest).
Use describe/it/expect syntax.
Mock external dependencies.
Test: happy path, edge cases, error cases.
Output ONLY the test file content. No markdown fences, no explanation.`;

    const prompt = `Generate Vitest unit tests for this ${target.type} file.

FILE: ${target.path}
FRAMEWORK: ${framework}
IMPORT STYLE: ${importStyle}

SOURCE CODE:
\`\`\`
${content.substring(0, 3000)}
\`\`\`

Requirements:
- Import the module from this exact path when needed: ${sourceImportPath}
- Mock all external dependencies (DB, external APIs)
- Test exported functions
- Test happy paths AND error/edge cases
- Use vi.mock() for mocking
- Include at least 3-5 test cases`;

    const response = await this.llm.chat(
      "test_stub_generation",
      [{ role: "user", content: prompt }],
      systemPrompt
    );

    const testContent = this.cleanTestContent(response.content, sourceImportPath);
    return testContent;
  }

  private cleanTestContent(content: string, sourceImportPath: string): string {
    let cleaned = content
      .replace(/^```[\w]*\n?/gm, "")
      .replace(/```$/gm, "")
      .trim();

    cleaned = this.ensureVitestImports(cleaned);

    if (!cleaned.includes("import") && !cleaned.includes("require")) {
      cleaned = `import { describe, it, expect, vi, beforeEach } from 'vitest';\nimport * as module from '${sourceImportPath}';\n\n${cleaned}`;
    }

    return cleaned;
  }

  private buildTargets(inventory: ProjectInventory): FileInfo[] {
    const seen = new Set<string>();
    const targets: FileInfo[] = [];

    const add = (file: FileInfo | undefined) => {
      if (!file || seen.has(file.path)) return;
      if (file.path.includes("__tests__")) return;
      seen.add(file.path);
      targets.push(file);
    };

    inventory.services.slice(0, 5).forEach(add);
    inventory.controllers.slice(0, 5).forEach(add);
    inventory.models.slice(0, 4).forEach(add);
    inventory.middleware.slice(0, 4).forEach(add);

    for (const route of inventory.routes.slice(0, 5)) {
      add({
        path: route.file,
        name: path.basename(route.file),
        type: path.extname(route.file).slice(1),
        size: 0,
      });
    }

    for (const entryPoint of inventory.entryPoints.slice(0, 3)) {
      add({
        path: entryPoint,
        name: path.basename(entryPoint),
        type: path.extname(entryPoint).slice(1),
        size: 0,
      });
    }

    return targets;
  }

  private getImportPath(testFilePath: string, projectPath: string, sourcePath: string): string {
    const absoluteSourcePath = path.join(projectPath, sourcePath);
    const relativePath = path.relative(path.dirname(testFilePath), absoluteSourcePath);
    const normalized = relativePath.replace(/\\/g, "/").replace(/\.(js|ts|jsx|tsx)$/, "");
    return normalized.startsWith(".") ? normalized : `./${normalized}`;
  }

  private getProjectTestFilePath(projectPath: string, sourcePath: string): string {
    const ext = path.extname(sourcePath) || ".js";
    const base = path.basename(sourcePath, ext);
    const sourceDir = path.dirname(sourcePath);
    return path.join(projectPath, "__tests__", sourceDir, `${base}.test${ext}`);
  }

  private getSnapshotFileName(sourcePath: string): string {
    const ext = path.extname(sourcePath) || ".js";
    const base = path.basename(sourcePath, ext);
    const dir = path.dirname(sourcePath).replace(/[/\\]/g, "_").replace(/^_/, "");
    return `${dir}_${base}.test${ext}`.replace(/^_/, "");
  }

  private ensureVitestImports(content: string): string {
    const required = new Set<string>();
    if (/\bdescribe\s*\(/.test(content)) required.add("describe");
    if (/\bit\s*\(/.test(content)) required.add("it");
    if (/\btest\s*\(/.test(content)) required.add("test");
    if (/\bexpect\s*\(/.test(content)) required.add("expect");
    if (/\bvi\./.test(content) || /\bvi\s*\(/.test(content)) required.add("vi");
    if (/\bbeforeEach\s*\(/.test(content)) required.add("beforeEach");
    if (/\bafterEach\s*\(/.test(content)) required.add("afterEach");
    if (/\bbeforeAll\s*\(/.test(content)) required.add("beforeAll");
    if (/\bafterAll\s*\(/.test(content)) required.add("afterAll");

    const vitestImportPattern = /import\s*{([^}]+)}\s*from\s*['"]vitest['"];?/;
    const match = content.match(vitestImportPattern);

    if (match) {
      const existing = match[1]
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);
      for (const item of existing) required.add(item);
      const ordered = Array.from(required);
      return content.replace(vitestImportPattern, `import { ${ordered.join(", ")} } from 'vitest';`);
    }

    if (required.size === 0) return content;
    return `import { ${Array.from(required).join(", ")} } from 'vitest';\n${content}`;
  }

  private readFile(projectPath: string, filePath: string): string {
    try {
      const full = path.join(projectPath, filePath);
      const stat = fs.statSync(full);
      if (stat.size > 100 * 1024) return "";
      return fs.readFileSync(full, "utf-8");
    } catch {
      return "";
    }
  }
}
