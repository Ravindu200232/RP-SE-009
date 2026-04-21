import fs from "fs";
import path from "path";
import fg from "fast-glob";
import type { ProjectInventory, FileInfo, RouteInfo, ProjectType } from "@/types";

export class ProjectParser {
  async parse(rootPath: string): Promise<ProjectInventory> {
    const normalizedRoot = rootPath.replace(/\\/g, "/");

    const allFiles = await fg("**/*", {
      cwd: normalizedRoot,
      onlyFiles: true,
      ignore: [
        "**/node_modules/**",
        "**/.git/**",
        "**/.next/**",
        "**/dist/**",
        "**/build/**",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/*.log",
        "**/.DS_Store",
      ],
      dot: true,
      absolute: false,
    });

    const packageJsonPath = this.findFile(allFiles, [
      "package.json",
      "frontend/package.json",
      "backend/package.json",
    ]);
    const packageJson = packageJsonPath
      ? this.readJSON(path.join(rootPath, packageJsonPath))
      : undefined;

    const tsConfigPath = this.findFile(allFiles, [
      "tsconfig.json",
      "frontend/tsconfig.json",
    ]);
    const tsConfig = tsConfigPath
      ? this.readJSON(path.join(rootPath, tsConfigPath))
      : undefined;

    const hasTypeScript = allFiles.some((f) => f.endsWith(".ts") || f.endsWith(".tsx"));
    const hasPython = allFiles.some((f) => f.endsWith(".py"));
    const packageManager = this.detectPackageManager(rootPath, allFiles);
    const projectType = this.detectProjectType(rootPath, allFiles, packageJson);
    const frameworks = this.detectFrameworks(packageJson, allFiles);

    const scripts = ((packageJson?.scripts as Record<string, string>) || {});
    const dependencies = ((packageJson?.dependencies as Record<string, string>) || {});
    const devDependencies = ((packageJson?.devDependencies as Record<string, string>) || {});

    return {
      projectType,
      packageManager,
      hasTypeScript,
      hasPython,
      frameworks,
      rootPath,
      frontendPath: this.findFrontendPath(rootPath, allFiles),
      backendPath: this.findBackendPath(rootPath, allFiles),
      entryPoints: this.findEntryPoints(allFiles),
      routes: await this.extractRoutes(rootPath, allFiles),
      models: this.filterFileInfo(rootPath, allFiles, this.isModelFile),
      controllers: this.filterFileInfo(rootPath, allFiles, this.isControllerFile),
      services: this.filterFileInfo(rootPath, allFiles, this.isServiceFile),
      middleware: this.filterFileInfo(rootPath, allFiles, this.isMiddlewareFile),
      schemas: this.filterFileInfo(rootPath, allFiles, this.isSchemaFile),
      components: this.filterFileInfo(rootPath, allFiles, this.isComponentFile),
      apiHandlers: this.filterFileInfo(rootPath, allFiles, this.isApiHandlerFile),
      configFiles: allFiles.filter((f) => this.isConfigFile(f)),
      envFiles: allFiles.filter((f) => f.includes(".env")),
      testFiles: allFiles.filter((f) => this.isTestFile(f)),
      allFiles,
      packageJson,
      tsConfig,
      scripts,
      dependencies,
      devDependencies,
    };
  }

  private findFile(files: string[], candidates: string[]): string | undefined {
    for (const c of candidates) {
      if (files.includes(c)) return c;
    }
    return undefined;
  }

  private readJSON(filePath: string): Record<string, unknown> | undefined {
    try {
      return JSON.parse(fs.readFileSync(filePath, "utf-8"));
    } catch {
      return undefined;
    }
  }

  private detectPackageManager(
    root: string,
    files: string[]
  ): ProjectInventory["packageManager"] {
    if (files.includes("pnpm-lock.yaml")) return "pnpm";
    if (files.includes("yarn.lock")) return "yarn";
    if (files.includes("bun.lockb")) return "bun";
    return "npm";
  }

  private detectProjectType(
    root: string,
    files: string[],
    pkg?: Record<string, unknown>
  ): ProjectType {
    const deps = {
      ...(pkg?.dependencies as Record<string, string>),
      ...(pkg?.devDependencies as Record<string, string>),
    };

    const hasNext = "next" in deps;
    const hasExpress = "express" in deps;
    const hasMongoose = "mongoose" in deps;
    const hasAppRouter = files.some((f) => f.includes("app/") && f.endsWith("route.ts"));
    const hasSeparateFrontend = files.some((f) => f.startsWith("frontend/"));
    const hasSeparateBackend = files.some((f) => f.startsWith("backend/"));

    if (hasNext && hasAppRouter) {
      if (hasSeparateBackend) return "nextjs_frontend_separate_backend";
      return "nextjs_fullstack";
    }
    if (hasMongoose && hasExpress) return "mern";
    if (hasExpress) {
      if (hasSeparateFrontend) return "react_express";
      return "mern";
    }
    if (hasNext) return "nextjs_fullstack";
    return "unknown";
  }

  private detectFrameworks(
    pkg?: Record<string, unknown>,
    files?: string[]
  ): string[] {
    const frameworks: string[] = [];
    const deps = {
      ...(pkg?.dependencies as Record<string, string>),
      ...(pkg?.devDependencies as Record<string, string>),
    };

    if ("next" in deps) frameworks.push("Next.js");
    if ("react" in deps) frameworks.push("React");
    if ("express" in deps) frameworks.push("Express");
    if ("mongoose" in deps) frameworks.push("Mongoose/MongoDB");
    if ("prisma" in deps || "@prisma/client" in deps) frameworks.push("Prisma");
    if ("typeorm" in deps) frameworks.push("TypeORM");
    if ("fastify" in deps) frameworks.push("Fastify");
    if ("socket.io" in deps) frameworks.push("Socket.io");
    if ("redis" in deps || "ioredis" in deps) frameworks.push("Redis");
    if ("jsonwebtoken" in deps) frameworks.push("JWT Auth");
    if ("tailwindcss" in deps) frameworks.push("Tailwind CSS");

    return frameworks;
  }

  private findFrontendPath(root: string, files: string[]): string | undefined {
    if (files.some((f) => f.startsWith("frontend/"))) return path.join(root, "frontend");
    if (files.some((f) => f.startsWith("client/"))) return path.join(root, "client");
    return undefined;
  }

  private findBackendPath(root: string, files: string[]): string | undefined {
    if (files.some((f) => f.startsWith("backend/"))) return path.join(root, "backend");
    if (files.some((f) => f.startsWith("server/"))) return path.join(root, "server");
    if (files.some((f) => f.startsWith("api/"))) return path.join(root, "api");
    return undefined;
  }

  private findEntryPoints(files: string[]): string[] {
    const candidates = [
      "index.js", "index.ts", "server.js", "server.ts",
      "app.js", "app.ts", "main.js", "main.ts", "main.jsx", "main.tsx",
      "src/index.js", "src/index.ts", "src/server.js", "src/server.ts",
      "src/app.js", "src/app.ts", "src/main.js", "src/main.ts",
      "backend/index.js", "backend/server.js",
    ];
    return candidates.filter((c) => files.includes(c));
  }

  private async extractRoutes(root: string, files: string[]): Promise<RouteInfo[]> {
    const routes: RouteInfo[] = [];

    // Next.js App Router routes
    const appRoutes = files.filter(
      (f) => (f.includes("app/api/") || f.includes("app\\api\\")) && f.endsWith("route.ts")
    );
    for (const f of appRoutes) {
      const apiPath = f.replace(/app[/\\]api/, "").replace(/[/\\]route\.ts$/, "");
      routes.push({ path: `/api${apiPath}`, file: f, method: "ANY" });
    }

    // Pages API routes
    const pagesRoutes = files.filter(
      (f) => (f.includes("pages/api/") || f.includes("pages\\api\\")) && (f.endsWith(".ts") || f.endsWith(".js"))
    );
    for (const f of pagesRoutes) {
      const apiPath = f.replace(/pages[/\\]api/, "").replace(/\.(ts|js)$/, "");
      routes.push({ path: `/api${apiPath}`, file: f, method: "ANY" });
    }

    // Express routes
    const routeFiles = files.filter(
      (f) => this.isRouteFile(f) && (f.endsWith(".js") || f.endsWith(".ts"))
    );
    for (const f of routeFiles) {
      try {
        const content = fs.readFileSync(path.join(root, f), "utf-8");
        const expressRoutes = this.extractExpressRoutes(content, f);
        routes.push(...expressRoutes);
      } catch {
        // skip unreadable
      }
    }

    return routes;
  }

  private extractExpressRoutes(content: string, file: string): RouteInfo[] {
    const routes: RouteInfo[] = [];
    const routePattern = /router\.(get|post|put|patch|delete|all)\s*\(\s*['"`]([^'"`]+)['"`]/gi;
    let match;
    while ((match = routePattern.exec(content)) !== null) {
      routes.push({
        path: match[2],
        method: match[1].toUpperCase(),
        file,
      });
    }
    return routes;
  }

  private filterFileInfo(
    root: string,
    files: string[],
    predicate: (f: string) => boolean
  ): FileInfo[] {
    return files
      .filter(predicate)
      .slice(0, 200)
      .map((f) => {
        let size = 0;
        try {
          size = fs.statSync(path.join(root, f)).size;
        } catch {}
        return {
          path: f,
          name: path.basename(f),
          type: path.extname(f).slice(1),
          size,
        };
      });
  }

  private isModelFile = (f: string): boolean =>
    /[/\\]models?[/\\]/.test(f) && this.isCodeFile(f);

  private isControllerFile = (f: string): boolean =>
    /[/\\]controllers?[/\\]/.test(f) && this.isCodeFile(f);

  private isServiceFile = (f: string): boolean =>
    /[/\\]services?[/\\]/.test(f) && this.isCodeFile(f);

  private isMiddlewareFile = (f: string): boolean =>
    /[/\\]middlewares?[/\\]|middleware\.(js|ts)/.test(f) && this.isCodeFile(f);

  private isSchemaFile = (f: string): boolean =>
    /[/\\]schemas?[/\\]|Schema\.(js|ts)/.test(f) && this.isCodeFile(f);

  private isComponentFile = (f: string): boolean =>
    /[/\\]components?[/\\]/.test(f) && /\.(jsx|tsx)$/.test(f);

  private isApiHandlerFile = (f: string): boolean =>
    (/[/\\]api[/\\]/.test(f) || /route\.(ts|js)$/.test(f)) && this.isCodeFile(f);

  private isRouteFile = (f: string): boolean =>
    /[/\\]routes?[/\\]/.test(f) && this.isCodeFile(f);

  private isCodeFile = (f: string): boolean =>
    /\.(js|ts|jsx|tsx|py)$/.test(f);

  private isConfigFile = (f: string): boolean =>
    /\.(config\.(js|ts|mjs|cjs)|json|yaml|yml|toml)$/.test(f) && !f.includes("node_modules");

  private isTestFile = (f: string): boolean =>
    /\.(test|spec)\.(js|ts|jsx|tsx|py)$/.test(f) ||
    /[/\\]__tests__[/\\]/.test(f) ||
    /[/\\]tests?[/\\]/.test(f);
}
