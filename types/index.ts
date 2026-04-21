export type RunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type PhaseStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type BugCategory = "functional" | "security" | "performance" | "quality" | "srs_gap";
export type RequirementStatus = "implemented" | "partially_implemented" | "missing" | "unverifiable";
export type ProjectType =
  | "mern"
  | "nextjs_fullstack"
  | "nextjs_frontend_separate_backend"
  | "react_express"
  | "unknown";
export type LLMProvider = "ollama" | "glm_cloud";

export interface Phase {
  id: string;
  name: string;
  status: PhaseStatus;
  progress: number;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  detail?: string;
}

export interface RunConfig {
  projectPath: string;
  srsPath: string;
  runName?: string;
  enableSecurity: boolean;
  enablePerformance: boolean;
  enablePlaywright: boolean;
  ollamaBaseUrl: string;
  ollamaModel: string;
  glmApiKey?: string;
  glmModel: string;
}

export interface RunRecord {
  id: string;
  config: RunConfig;
  status: RunStatus;
  createdAt: string;
  updatedAt: string;
  outputPath: string;
  phases: Phase[];
  metrics: RunMetrics;
  projectSlug?: string;
}

export interface RunMetrics {
  totalFiles: number;
  totalRequirements: number;
  implementedRequirements: number;
  missingRequirements: number;
  unitTestsGenerated: number;
  unitTestsPassed: number;
  unitTestsFailed: number;
  integrationTestsGenerated: number;
  integrationTestsPassed: number;
  integrationTestsFailed: number;
  securityIssues: number;
  performanceAlerts: number;
  qualityScore: number;
  passed: boolean;
  warnings: number;
}

export interface ProjectInventory {
  projectType: ProjectType;
  packageManager: "npm" | "pnpm" | "yarn" | "bun";
  hasTypeScript: boolean;
  hasPython: boolean;
  frameworks: string[];
  rootPath: string;
  frontendPath?: string;
  backendPath?: string;
  entryPoints: string[];
  routes: RouteInfo[];
  models: FileInfo[];
  controllers: FileInfo[];
  services: FileInfo[];
  middleware: FileInfo[];
  schemas: FileInfo[];
  components: FileInfo[];
  apiHandlers: FileInfo[];
  configFiles: string[];
  envFiles: string[];
  testFiles: string[];
  allFiles: string[];
  packageJson?: Record<string, unknown>;
  tsConfig?: Record<string, unknown>;
  scripts: Record<string, string>;
  dependencies: Record<string, string>;
  devDependencies: Record<string, string>;
}

export interface RouteInfo {
  path: string;
  method?: string;
  file: string;
  handler?: string;
  middleware?: string[];
}

export interface FileInfo {
  path: string;
  name: string;
  type: string;
  size: number;
  exports?: string[];
}

export interface SRSDocument {
  projectName: string;
  version?: string;
  actors?: string[];
  functionalRequirements: Requirement[];
  nonFunctionalRequirements: Requirement[];
  modules?: Module[];
  dataEntities?: DataEntity[];
  apiContracts?: APIContract[];
  constraints?: string[];
  raw: Record<string, unknown>;
}

export interface Requirement {
  id: string;
  title: string;
  description: string;
  priority?: "must" | "should" | "could" | "wont";
  module?: string;
  category?: string;
}

export interface Module {
  id: string;
  name: string;
  description: string;
  requirements?: string[];
}

export interface DataEntity {
  name: string;
  fields?: FieldDef[];
  relationships?: string[];
}

export interface FieldDef {
  name: string;
  type: string;
  required?: boolean;
}

export interface APIContract {
  path: string;
  method: string;
  description?: string;
  requestBody?: Record<string, unknown>;
  response?: Record<string, unknown>;
}

export interface TraceabilityRecord {
  requirementId: string;
  requirementTitle: string;
  status: RequirementStatus;
  files: string[];
  routes: string[];
  components: string[];
  models: string[];
  tests: string[];
  evidence: string[];
  confidence: number;
  llmReasoning?: string;
}

export interface BugRecord {
  bugId: string;
  phase: string;
  severity: Severity;
  category: BugCategory;
  title: string;
  description: string;
  affectedFiles: string[];
  affectedRoutes: string[];
  requirementIds: string[];
  evidence: string;
  reproductionSteps: string[];
  expectedBehavior: string;
  actualBehavior: string;
  suggestedFix: string;
  confidenceScore: number;
  sourceTool: string;
  llmSummary?: string;
  timestamp: string;
}

export interface ProgressEvent {
  type:
    | "phase_start"
    | "phase_progress"
    | "phase_complete"
    | "phase_error"
    | "log"
    | "metric"
    | "complete"
    | "error";
  phase?: string;
  progress?: number;
  message?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

export interface LLMMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LLMResponse {
  content: string;
  provider: LLMProvider;
  model: string;
  tokensUsed?: number;
  latencyMs: number;
}

export interface SecurityFinding {
  id: string;
  rule: string;
  severity: Severity;
  file: string;
  line?: number;
  message: string;
  tool: string;
  cwe?: string;
  owasp?: string;
}

export interface PerformanceFinding {
  id: string;
  type: string;
  severity: Severity;
  file?: string;
  message: string;
  metric?: string;
  value?: number;
  threshold?: number;
}

export interface QualityScore {
  functionalCorrectness: number;
  codeQuality: number;
  security: number;
  performance: number;
  overall: number;
  passed: boolean;
  details: Record<string, unknown>;
}

export interface TestResult {
  name: string;
  status: "passed" | "failed" | "skipped";
  duration?: number;
  error?: string;
  file?: string;
}

export interface TestSuiteResult {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  tests: TestResult[];
  raw?: string;
}

export interface FinalReport {
  runId: string;
  projectName: string;
  projectPath: string;
  srsPath: string;
  analysisDate: string;
  projectSummary: {
    detectedStack: ProjectType;
    frameworks: string[];
    totalFiles: number;
    hasTypeScript: boolean;
    hasPython: boolean;
  };
  requirementsSummary: {
    total: number;
    implemented: number;
    partiallyImplemented: number;
    missing: number;
    unverifiable: number;
    coveragePercent: number;
  };
  unitTestSummary: TestSuiteResult;
  integrationTestSummary: TestSuiteResult;
  securitySummary: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  performanceSummary: {
    total: number;
    alerts: number;
  };
  qualityScore: QualityScore;
  majorBlockers: string[];
  recommendations: string[];
  artifacts: string[];
}
