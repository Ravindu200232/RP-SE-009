/**
 * Typed API client.
 *
 * Calls go DIRECTLY to the FastAPI backend (CORS is configured server-side).
 * We deliberately bypass the Next.js dev rewrite-proxy because that proxy
 * times out long requests at ~30s — and agentic /analyze and /generate calls
 * routinely take longer with a local LLM. A direct browser fetch has no such
 * timeout. Falls back to the same-origin "/api" proxy only if no base URL is
 * configured (e.g. a same-origin production deployment).
 */
import type {
  Project,
  Question,
  AgentEvent,
  SrsEnvelope,
  SrsSummary,
  FunctionalRequirement,
  NonFunctionalRequirement,
  Ambiguity,
  RiskPriority,
  DiagramArtifact,
  Answer,
  DomainClassification,
  SrsVersion,
} from "@agentforge/shared";

const RAW_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// Use the direct backend URL when configured; else same-origin proxy.
export const API_BASE = RAW_BASE ? RAW_BASE.replace(/\/$/, "") : "/api";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  createProject: (idea: string, language?: string) =>
    http<{ project: Project }>("/projects", {
      method: "POST",
      body: JSON.stringify({ idea, language }),
    }),

  listProjects: () => http<{ projects: Project[] }>("/projects"),

  getProject: (id: string) =>
    http<{
      project: Project;
      srs?: SrsEnvelope;
      summary?: SrsSummary;
      versions: SrsVersion[];
    }>(`/projects/${id}`),

  addTextInput: (id: string, text: string) => {
    const fd = new FormData();
    fd.append("mode", "text");
    fd.append("text", text);
    return fetch(`${API_BASE}/projects/${id}/inputs`, { method: "POST", body: fd }).then((r) => r.json());
  },

  uploadFile: (id: string, file: File, mode: string) => {
    const fd = new FormData();
    fd.append("mode", mode);
    fd.append("file", file);
    return fetch(`${API_BASE}/projects/${id}/inputs`, { method: "POST", body: fd }).then((r) => r.json());
  },

  analyze: (id: string) =>
    http<{
      project: Project;
      classification: DomainClassification;
      needs_clarification: boolean;
      clarification_reason?: string;
      questions: Question[];
    }>(`/projects/${id}/analyze`, { method: "POST" }),

  getQuestions: (id: string) =>
    http<{ session: { questions: Question[]; coverage_score: number; complete: boolean } | null; questions: Question[] }>(
      `/projects/${id}/questions`,
    ),

  submitAnswers: (id: string, answers: Answer[]) =>
    http<{ coverage_score: number; complete: boolean; follow_up_questions: Question[] }>(
      `/projects/${id}/answers`,
      { method: "POST", body: JSON.stringify({ answers }) },
    ),

  generateSrs: (id: string) =>
    http<{ project: Project; version: string; summary: SrsSummary }>(`/projects/${id}/generate-srs`, {
      method: "POST",
    }),

  srsJson: (id: string) => http<SrsEnvelope>(`/projects/${id}/srs-json`),

  requirements: (id: string) =>
    http<{ functional_requirements: FunctionalRequirement[]; non_functional_requirements: NonFunctionalRequirement[] }>(
      `/projects/${id}/requirements`,
    ),

  diagrams: (id: string) => http<{ diagrams: DiagramArtifact[] }>(`/projects/${id}/diagrams`),

  ambiguities: (id: string) =>
    http<{ ambiguities: Ambiguity[]; assumptions: string[] }>(`/projects/${id}/ambiguities`),

  risks: (id: string) => http<{ risk_priority: RiskPriority[] }>(`/projects/${id}/risks`),

  customize: (id: string, prompt: string) =>
    http<{ project: Project; version: string; diff_summary: string[]; summary: SrsSummary }>(
      `/projects/${id}/customize`,
      { method: "POST", body: JSON.stringify({ prompt }) },
    ),

  approve: (id: string) => http<{ project: Project }>(`/projects/${id}/approve`, { method: "POST" }),

  events: (id: string) => http<{ events: AgentEvent[] }>(`/projects/${id}/events`),

  downloadJsonUrl: (id: string) => `${API_BASE}/projects/${id}/download/json`,
  downloadPdfUrl: (id: string) => `${API_BASE}/projects/${id}/download/pdf`,
  eventStreamUrl: (id: string) => `${API_BASE}/projects/${id}/events/stream`,
};
