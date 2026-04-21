import path from "path";
import fs from "fs";
import { runCommand, checkCommandAvailable } from "./runner";
import type { TestSuiteResult, TestResult } from "@/types";

export interface VitestRunResult {
  available: boolean;
  result: TestSuiteResult;
  raw: string;
}

export async function runVitest(
  projectPath: string,
  testDir: string,
  explicitTestFiles?: string[]
): Promise<VitestRunResult> {
  const jsonResultPath = path.join(testDir, "vitest-results.json");
  const workspaceRoot = process.cwd();
  const localVitestModule = path.join(workspaceRoot, "node_modules", "vitest", "vitest.mjs");
  const testFiles = explicitTestFiles?.length
    ? explicitTestFiles
    : collectTestFiles(testDir);

  if (testFiles.length === 0) {
    return {
      available: false,
      result: emptyResult(),
      raw: `No test files were found in ${testDir}.`,
    };
  }

  let command = process.execPath;
  let args = [localVitestModule, "run", "--pool=threads", "--reporter=json", "--outputFile", jsonResultPath, ...testFiles];
  let available = fs.existsSync(localVitestModule);
  let shell = false;

  if (!available) {
    available = await checkCommandAvailable("npx");
    command = "npx";
    args = ["vitest", "run", "--pool=threads", "--reporter=json", "--outputFile", jsonResultPath, ...testFiles];
    shell = process.platform === "win32";
  }

  if (!available) {
    return {
      available: false,
      result: emptyResult(),
      raw: "Vitest is not available. Install it in the Agent 3 workspace or make npx available.",
    };
  }

  const result = await runCommand(
    command,
    args,
    {
      cwd: testDir,
      env: {
        AGENT3_PROJECT_PATH: projectPath,
        NODE_PATH: path.join(workspaceRoot, "node_modules"),
      },
      shell,
      timeoutMs: 120000,
    }
  );

  if (fs.existsSync(jsonResultPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(jsonResultPath, "utf-8")) as VitestJSONReport;
      return { available: true, result: parseVitestJSON(data), raw: result.stdout + result.stderr };
    } catch {}
  }

  return {
    available: true,
    result: parseVitestOutput(result.stdout + result.stderr),
    raw: result.stdout + result.stderr,
  };
}

interface VitestJSONReport {
  numTotalTestSuites?: number;
  numPassedTestSuites?: number;
  numFailedTestSuites?: number;
  numPendingTestSuites?: number;
  numPassedTests?: number;
  numFailedTests?: number;
  numPendingTests?: number;
  testResults?: Array<{
    name?: string;
    testFilePath: string;
    status: string;
    duration?: number;
    message?: string;
    assertionResults?: Array<{
      fullName: string;
      status: string;
      duration?: number;
      failureMessages?: string[];
    }>;
  }>;
}

function parseVitestJSON(data: VitestJSONReport): TestSuiteResult {
  const tests: TestResult[] = [];
  let total = 0, passed = 0, failed = 0, skipped = 0, duration = 0;

  for (const suite of data.testResults || []) {
    if ((!suite.assertionResults || suite.assertionResults.length === 0) && suite.status === "failed") {
      total++;
      failed++;
      tests.push({
        name: suite.name || path.basename(suite.testFilePath),
        status: "failed",
        duration: suite.duration,
        error: suite.message,
        file: suite.testFilePath,
      });
      continue;
    }

    for (const t of suite.assertionResults || []) {
      total++;
      const status = t.status === "passed" ? "passed" : t.status === "pending" ? "skipped" : "failed";
      if (status === "passed") passed++;
      else if (status === "failed") failed++;
      else skipped++;
      duration += t.duration || 0;
      tests.push({
        name: t.fullName,
        status,
        duration: t.duration,
        error: t.failureMessages?.join("\n"),
        file: suite.testFilePath,
      });
    }
  }

  if (total === 0) {
    total = data.numPassedTests || 0;
    total += data.numFailedTests || 0;
    total += data.numPendingTests || 0;
    passed = data.numPassedTests || 0;
    failed = data.numFailedTests || 0;
    skipped = data.numPendingTests || 0;
  }

  if (total === 0) {
    total = data.numPassedTestSuites || 0;
    total += data.numFailedTestSuites || 0;
    total += data.numPendingTestSuites || 0;
    passed = data.numPassedTestSuites || 0;
    failed = data.numFailedTestSuites || 0;
    skipped = data.numPendingTestSuites || 0;
  }

  return { total, passed, failed, skipped, duration, tests };
}

function parseVitestOutput(output: string): TestSuiteResult {
  const tests: TestResult[] = [];
  const passMatch = output.match(/(\d+)\s+passed/);
  const failMatch = output.match(/(\d+)\s+failed/);
  const passed = passMatch ? parseInt(passMatch[1]) : 0;
  const failed = failMatch ? parseInt(failMatch[1]) : 0;
  return { total: passed + failed, passed, failed, skipped: 0, duration: 0, tests };
}

function emptyResult(): TestSuiteResult {
  return { total: 0, passed: 0, failed: 0, skipped: 0, duration: 0, tests: [] };
}

function collectTestFiles(rootDir: string): string[] {
  const files: string[] = [];

  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
        continue;
      }

      if (/\.(test|spec)\.(js|ts|jsx|tsx)$/.test(entry.name)) {
        files.push(fullPath);
      }
    }
  };

  if (fs.existsSync(rootDir)) {
    walk(rootDir);
  }

  return files;
}
