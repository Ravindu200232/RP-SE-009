import fs from "fs";
import path from "path";
import type { ProjectInventory, RouteInfo } from "@/types";
import type { LLMRouter } from "@/providers/llm-router";

export interface GeneratedIntegrationTest {
  name: string;
  testFile: string;
  content: string;
  testCount: number;
  type: "api" | "auth" | "database" | "e2e";
}

export class IntegrationTestGenerator {
  constructor(private llm: LLMRouter) {}

  async generate(
    projectPath: string,
    inventory: ProjectInventory,
    outputDir: string
  ): Promise<GeneratedIntegrationTest[]> {
    fs.mkdirSync(outputDir, { recursive: true });
    const generated: GeneratedIntegrationTest[] = [];
    const failures: string[] = [];

    // API flow tests
    if (inventory.routes.length > 0) {
      const apiTest = await this.generateApiTests(projectPath, inventory, outputDir, failures);
      if (apiTest) generated.push(apiTest);
    }

    // Auth flow tests
    const hasAuth = inventory.allFiles.some(
      (f) => f.toLowerCase().includes("auth") || f.toLowerCase().includes("login")
    );
    if (hasAuth) {
      const authTest = await this.generateAuthTests(projectPath, inventory, outputDir, failures);
      if (authTest) generated.push(authTest);
    }

    // Database integration
    if (inventory.models.length > 0) {
      const dbTest = await this.generateDatabaseTests(inventory, projectPath, outputDir, failures);
      if (dbTest) generated.push(dbTest);
    }

    if (generated.length === 0 && failures.length > 0) {
      throw new Error(`Integration test generation failed. ${failures.slice(0, 3).join(" | ")}`);
    }

    return generated;
  }

  private async generateApiTests(
    projectPath: string,
    inventory: ProjectInventory,
    outputDir: string,
    failures: string[]
  ): Promise<GeneratedIntegrationTest | null> {
    const routes = inventory.routes.slice(0, 15);
    const routeList = routes
      .map((r) => `${r.method || "GET"} ${r.path}`)
      .join("\n");

    const systemPrompt = `You are an expert API test engineer.
Write integration tests using supertest (for Express) or fetch (for Next.js).
Use vitest as the test runner.
Prefer direct HTTP/fetch-based tests when the application entry point is unclear.
Output ONLY the test file content with no markdown fences.`;

    const isNextjs =
      inventory.projectType === "nextjs_fullstack" ||
      inventory.projectType === "nextjs_frontend_separate_backend";

    const prompt = `Generate API integration tests for a ${inventory.projectType} project.

AVAILABLE ROUTES:
${routeList}

STACK: ${inventory.frameworks.join(", ")}
IS NEXTJS: ${isNextjs}

Write tests that:
- Test each major route (GET, POST, PUT, DELETE)
- Check response status codes
- Verify response schema/keys
- Test auth middleware (expect 401 without token)
- Test validation (expect 400 with bad payload)
- Use supertest for Express OR undici/fetch for Next.js
- Include beforeAll/afterAll for setup/teardown

Import paths should be relative. Assume server runs on port 3001 in test env.`;

    try {
      const response = await this.llm.chat(
        "integration_reasoning",
        [{ role: "user", content: prompt }],
        systemPrompt
      );

      const content = this.clean(response.content);
      const testFilePath = this.getProjectIntegrationTestFilePath(projectPath, "api", inventory);
      fs.mkdirSync(path.dirname(testFilePath), { recursive: true });
      fs.writeFileSync(testFilePath, content, "utf-8");
      fs.writeFileSync(path.join(outputDir, path.basename(testFilePath)), content, "utf-8");
      const testCount = (content.match(/\bit\(|\btest\(/g) || []).length;

      return { name: "API Integration Tests", testFile: testFilePath, content, testCount, type: "api" };
    } catch (err) {
      failures.push(`API tests: ${err instanceof Error ? err.message : String(err)}`);
      return null;
    }
  }

  private async generateAuthTests(
    projectPath: string,
    inventory: ProjectInventory,
    outputDir: string,
    failures: string[]
  ): Promise<GeneratedIntegrationTest | null> {
    const authFiles = inventory.allFiles
      .filter((f) => f.toLowerCase().includes("auth") || f.toLowerCase().includes("login"))
      .slice(0, 5);

    const prompt = `Generate auth flow integration tests for a ${inventory.projectType} project.

AUTH-RELATED FILES: ${authFiles.join(", ")}
FRAMEWORKS: ${inventory.frameworks.join(", ")}

Test scenarios:
1. Register with valid data → 201
2. Register with duplicate email → 400/409
3. Login with valid credentials → 200 with token
4. Login with wrong password → 401
5. Access protected route with valid token → 200
6. Access protected route without token → 401
7. Access protected route with expired token → 401

Use vitest + supertest or fetch. Output ONLY test file content.`;

    try {
      const response = await this.llm.chat(
        "integration_reasoning",
        [{ role: "user", content: prompt }],
        `You are an auth testing expert. Output ONLY test file content, no markdown.`
      );

      const content = this.clean(response.content);
      const testFilePath = this.getProjectIntegrationTestFilePath(projectPath, "auth", inventory);
      fs.mkdirSync(path.dirname(testFilePath), { recursive: true });
      fs.writeFileSync(testFilePath, content, "utf-8");
      fs.writeFileSync(path.join(outputDir, path.basename(testFilePath)), content, "utf-8");
      const testCount = (content.match(/\bit\(|\btest\(/g) || []).length;

      return { name: "Auth Flow Tests", testFile: testFilePath, content, testCount, type: "auth" };
    } catch (err) {
      failures.push(`Auth tests: ${err instanceof Error ? err.message : String(err)}`);
      return null;
    }
  }

  private async generateDatabaseTests(
    inventory: ProjectInventory,
    projectPath: string,
    outputDir: string,
    failures: string[]
  ): Promise<GeneratedIntegrationTest | null> {
    const models = inventory.models.slice(0, 3);
    const modelNames = models.map((m) => m.name.replace(/\.(js|ts)$/, ""));

    let modelSnippets = "";
    for (const model of models) {
      try {
        const content = fs.readFileSync(path.join(projectPath, model.path), "utf-8");
        modelSnippets += `\n--- ${model.name} ---\n${content.substring(0, 500)}\n`;
      } catch {}
    }

    const prompt = `Generate database integration tests for these models: ${modelNames.join(", ")}

MODEL SNIPPETS:
${modelSnippets.substring(0, 2000)}

FRAMEWORKS: ${inventory.frameworks.join(", ")}

Write tests that:
- Connect to a test database
- Test CRUD operations
- Test schema validation
- Test relationships/references
- Clean up after tests

Use vitest. Output ONLY test file content.`;

    try {
      const response = await this.llm.chat(
        "integration_reasoning",
        [{ role: "user", content: prompt }],
        `You are a database testing expert. Output ONLY test file content, no markdown.`
      );

      const content = this.clean(response.content);
      const testFilePath = this.getProjectIntegrationTestFilePath(projectPath, "database", inventory);
      fs.mkdirSync(path.dirname(testFilePath), { recursive: true });
      fs.writeFileSync(testFilePath, content, "utf-8");
      fs.writeFileSync(path.join(outputDir, path.basename(testFilePath)), content, "utf-8");
      const testCount = (content.match(/\bit\(|\btest\(/g) || []).length;

      return { name: "Database Integration Tests", testFile: testFilePath, content, testCount, type: "database" };
    } catch (err) {
      failures.push(`Database tests: ${err instanceof Error ? err.message : String(err)}`);
      return null;
    }
  }

  private clean(content: string): string {
    const cleaned = content
      .replace(/^```[\w]*\n?/gm, "")
      .replace(/```$/gm, "")
      .trim();
    return this.ensureVitestImports(cleaned);
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

  private getProjectIntegrationTestFilePath(
    projectPath: string,
    name: "api" | "auth" | "database" | "e2e",
    inventory: ProjectInventory
  ): string {
    const ext = inventory.hasTypeScript ? ".ts" : ".js";
    return path.join(projectPath, "__tests__", "integration", `${name}.integration.test${ext}`);
  }
}
