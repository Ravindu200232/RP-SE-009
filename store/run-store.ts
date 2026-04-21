import path from "path";
import fs from "fs";
import type { RunRecord, RunConfig, RunStatus, Phase, RunMetrics } from "@/types";
import { v4 as uuidv4 } from "uuid";
import { slugify } from "@/lib/utils";

const DATA_DIR = path.join(process.cwd(), ".agent3-data");
const STORE_FILE = path.join(DATA_DIR, "runs.json");

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function readStore(): Record<string, RunRecord> {
  ensureDir();
  if (!fs.existsSync(STORE_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(STORE_FILE, "utf-8")) as Record<string, RunRecord>;
  } catch {
    return {};
  }
}

function writeStore(store: Record<string, RunRecord>): void {
  ensureDir();
  fs.writeFileSync(STORE_FILE, JSON.stringify(store, null, 2), "utf-8");
}

const DEFAULT_METRICS: RunMetrics = {
  totalFiles: 0,
  totalRequirements: 0,
  implementedRequirements: 0,
  missingRequirements: 0,
  unitTestsGenerated: 0,
  unitTestsPassed: 0,
  unitTestsFailed: 0,
  integrationTestsGenerated: 0,
  integrationTestsPassed: 0,
  integrationTestsFailed: 0,
  securityIssues: 0,
  performanceAlerts: 0,
  qualityScore: 0,
  passed: false,
  warnings: 0,
};

const DEFAULT_PHASES: Phase[] = [
  { id: "intake", name: "Project Intake & Discovery", status: "pending", progress: 0 },
  { id: "inventory", name: "Build Inventory", status: "pending", progress: 0 },
  { id: "srs_parse", name: "SRS Parsing", status: "pending", progress: 0 },
  { id: "traceability", name: "Requirement Traceability", status: "pending", progress: 0 },
  { id: "unit_gen", name: "Unit Test Generation", status: "pending", progress: 0 },
  { id: "unit_exec", name: "Unit Test Execution", status: "pending", progress: 0 },
  { id: "integration_gen", name: "Integration Test Generation", status: "pending", progress: 0 },
  { id: "integration_exec", name: "Integration Test Execution", status: "pending", progress: 0 },
  { id: "quality", name: "Quality & Code Review", status: "pending", progress: 0 },
  { id: "security", name: "Security Scan", status: "pending", progress: 0 },
  { id: "performance", name: "Performance Test", status: "pending", progress: 0 },
  { id: "report_gen", name: "Report Generation", status: "pending", progress: 0 },
  { id: "pdf_gen", name: "PDF Generation", status: "pending", progress: 0 },
];

export function createRun(config: RunConfig): RunRecord {
  const id = uuidv4();
  const projectSlug = slugify(path.basename(config.projectPath) || "project");
  const outputRoot =
    process.env.AGENT3_OUTPUT_ROOT ||
    path.join(process.cwd(), "output", "agent3");
  const outputPath = path.join(outputRoot, projectSlug, id);
  const now = new Date().toISOString();

  const record: RunRecord = {
    id,
    config,
    status: "pending",
    createdAt: now,
    updatedAt: now,
    outputPath,
    phases: JSON.parse(JSON.stringify(DEFAULT_PHASES)) as Phase[],
    metrics: { ...DEFAULT_METRICS },
    projectSlug,
  };

  const store = readStore();
  store[id] = record;
  writeStore(store);

  return record;
}

export function getRun(id: string): RunRecord | null {
  const store = readStore();
  return store[id] || null;
}

export function listRuns(limit = 20): RunRecord[] {
  const store = readStore();
  return Object.values(store)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, limit);
}

export function updateRunStatus(id: string, status: RunStatus): void {
  const store = readStore();
  if (!store[id]) return;
  store[id].status = status;
  store[id].updatedAt = new Date().toISOString();
  writeStore(store);
}

export function updateRunPhase(
  id: string,
  phaseId: string,
  update: Partial<Phase>
): void {
  const store = readStore();
  if (!store[id]) return;
  const idx = store[id].phases.findIndex((p) => p.id === phaseId);
  if (idx !== -1) {
    store[id].phases[idx] = { ...store[id].phases[idx], ...update };
  }
  store[id].updatedAt = new Date().toISOString();
  writeStore(store);
}

export function updateRunMetrics(id: string, metrics: Partial<RunMetrics>): void {
  const store = readStore();
  if (!store[id]) return;
  store[id].metrics = { ...store[id].metrics, ...metrics };
  store[id].updatedAt = new Date().toISOString();
  writeStore(store);
}
