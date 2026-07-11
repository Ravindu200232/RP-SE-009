/** Project + workflow domain types shared between web and api. */

export type ProjectStatus =
  | "intake"
  | "questioning"
  | "analyzing"
  | "generated"
  | "approved"
  | "customized"
  | "needs_clarification"
  | "error";

export type InputMode = "text" | "pdf" | "image" | "voice";

export interface ComplexityEstimate {
  overall: string; // e.g. "Medium-High"
  backend: string;
  frontend: string;
}

export interface SuggestedStack {
  frontend: string;
  backend: string;
  database: string;
  architecture: string;
  locked: boolean;
}

export interface DomainClassification {
  detected_domain: string; // human label e.g. "Hospitality SaaS"
  domain_key: string; // e.g. "hotel"
  app_type: string; // e.g. "SPA", "POS", "admin dashboard"
  confidence: number; // 0..1
  similar_patterns: number;
  reasoning?: string;
}

export interface Project {
  id: string;
  title: string;
  raw_idea: string;
  detected_domain: string;
  domain_key: string;
  status: ProjectStatus;
  current_version: string;
  language: string;
  classification?: DomainClassification;
  complexity?: ComplexityEstimate;
  suggested_stack?: SuggestedStack;
  coverage_score?: number;
  needs_clarification?: boolean;
  clarification_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface ExtractedSource {
  id: string;
  project_id: string;
  mode: InputMode;
  filename?: string;
  text: string;
  meta?: Record<string, unknown>;
  created_at: string;
}

export interface SrsVersion {
  id: string;
  project_id: string;
  version: string; // semver-ish "1.0.0"
  label: string; // "Initial generation" / "Customized: add multi-currency"
  srs: { srs_document: unknown };
  diff_summary?: string[];
  created_at: string;
}

export type AgentEventLevel = "info" | "success" | "warn" | "error" | "debug";
export type ConsoleChannel =
  | "live_logs"
  | "agent_events"
  | "terminal"
  | "prompt_trace"
  | "errors";

export interface AgentEvent {
  id: string;
  project_id: string;
  agent: string; // e.g. "DomainClassifierAgent"
  channel: ConsoleChannel;
  level: AgentEventLevel;
  message: string;
  progress?: number; // 0..100
  data?: Record<string, unknown>;
  created_at: string;
}
