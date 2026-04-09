export interface GeneratedFile {
  path: string;
  content: string;
  service: string;
}

export interface ServiceInfo {
  name: string;
  port: number;
  status: 'pending' | 'generating' | 'validating' | 'installing' | 'starting' | 'running' | 'error';
  url?: string;
  error?: string;
  routes?: string[];
}

export interface LogEntry {
  timestamp: string;
  agent: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'warning' | 'code' | 'command' | 'terminal' | 'prompt' | 'thinking';
  level?: string;
  service?: string;
}

export interface StepResult {
  name: string;
  stage: string;
  status: 'pending' | 'running' | 'success' | 'warning' | 'error';
  summary: string;
  details?: Record<string, unknown>;
  startedAt?: string;
  completedAt?: string;
}

export interface ArtifactAuditService {
  service: string;
  expectedFiles: string[];
  foundFiles: string[];
  missingFiles: string[];
  extraFiles: string[];
}

export interface ArtifactAudit {
  services: Record<string, ArtifactAuditService>;
}

export interface GenerationJob {
  jobId: string;
  workspaceId?: string;
  threadId?: string;
  mode?: 'new' | 'continue';
  task?: string;
  model?: string;
  timeoutSeconds?: number;
  status: string;
  stage?: string;
  progress: number;
  currentAgent: string;
  plan?: ProjectPlan;
  services?: ServiceInfo[];
  gatewayUrl?: string;
  frontendUrl?: string;
  allUrls?: AllUrls;
  stepResults?: StepResult[];
  memorySummary?: MemorySummary;
  artifactAudit?: ArtifactAudit;
  error?: string;
  errorSummary?: string;
  logs?: LogEntry[];
}

export interface ProjectPlan {
  projectName: string;
  description: string;
  services: PlanService[];
  frontend: FrontendSpec;
  gateway: GatewaySpec;
}

export interface PlanService {
  name: string;
  description: string;
  port: number;
  entities?: string[];
  controllers?: string[];
  routes: { method: string; path: string; description: string }[];
  models: { name: string; fields: { name: string; type: string }[] }[];
  requiredFiles?: string[];
  packageDependencies?: string[];
  devDependencies?: string[];
  serviceDependencies?: string[];
  envVars?: string[];
  serviceCalls?: { service: string; envVar: string; baseUrl?: string; purpose?: string }[];
  dependencies?: string[];
}

export interface FrontendSpec {
  port?: number;
  pages: { name: string; route: string; description: string }[];
  routeGroups?: string[];
  components: string[];
  apis?: string[];
  serviceUrls?: string[];
}

export interface GatewaySpec {
  port: number;
  routes: { prefix: string; target: string; service?: string }[];
}

export interface AllUrls {
  gateway: string;
  frontend: string;
  services: Record<string, string>;
  apiRoutes: { prefix: string; target: string; viaGateway: string }[];
}

export interface MemorySummary {
  fileNames: string[];
  hasProjectState: boolean;
  indexedFiles: number;
  servicesTracked: number;
  failurePatterns: number;
}

export interface WorkspaceSummary {
  workspaceId: string;
  slug: string;
  name: string;
  description: string;
  status: string;
  latestThreadId?: string;
  latestGenerationId?: string;
  lastRunSettings?: {
    model?: string;
    timeoutSeconds?: number;
  };
  lastErrorSummary?: string;
  memorySummary?: MemorySummary;
  serviceNames?: string[];
  updatedAt: string;
  createdAt: string;
}

export interface ThreadSummary {
  threadId: string;
  title: string;
  mode: 'new' | 'continue';
  latestTask: string;
  status: string;
  messageCount: number;
  updatedAt: string;
  createdAt: string;
}

export interface WorkspaceDetail {
  workspace: WorkspaceSummary & {
    latestPlan?: ProjectPlan;
    appDir?: string;
  };
  threads: ThreadSummary[];
}

export interface ThreadMessage {
  role: 'system' | 'user' | 'assistant';
  agent?: string;
  phase?: string;
  content: string;
  createdAt: string;
}

export type AgentName = 'Planner' | 'Developer' | 'Analyzer' | 'Fixer' | 'Runner' | 'Orchestrator';

export interface AgentStatus {
  name: AgentName;
  status: 'idle' | 'working' | 'done' | 'error';
  message?: string;
}
