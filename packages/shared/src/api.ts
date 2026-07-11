/** API request/response contracts. */
import type {
  Project,
  ProjectStatus,
  DomainClassification,
  ComplexityEstimate,
  SuggestedStack,
  AgentEvent,
  SrsVersion,
} from "./project";
import type { Question, QuestionSession, Answer } from "./questions";
import type {
  SrsEnvelope,
  SrsSummary,
  FunctionalRequirement,
  Ambiguity,
  RiskPriority,
  DiagramArtifact,
} from "./srs";

export interface CreateProjectRequest {
  idea: string;
  language?: string;
}

export interface CreateProjectResponse {
  project: Project;
}

export interface AnalyzeResponse {
  project: Project;
  classification: DomainClassification;
  needs_clarification: boolean;
  clarification_reason?: string;
}

export interface QuestionsResponse {
  session: QuestionSession;
  questions: Question[];
}

export interface SubmitAnswersResponse {
  coverage_score: number;
  complete: boolean;
  follow_up_questions: Question[];
}

export interface GenerateSrsResponse {
  project: Project;
  version: string;
  summary: SrsSummary;
}

export interface RequirementsResponse {
  functional_requirements: FunctionalRequirement[];
  non_functional_requirements: SrsEnvelope["srs_document"]["non_functional_requirements"];
}

export interface DiagramsResponse {
  diagrams: DiagramArtifact[];
}

export interface AmbiguitiesResponse {
  ambiguities: Ambiguity[];
  assumptions: string[];
}

export interface RisksResponse {
  risk_priority: RiskPriority[];
}

export interface CustomizeRequest {
  prompt: string;
}

export interface CustomizeResponse {
  project: Project;
  version: string;
  diff_summary: string[];
  summary: SrsSummary;
}

export interface ProjectDetailResponse {
  project: Project;
  srs?: SrsEnvelope;
  summary?: SrsSummary;
  versions: SrsVersion[];
}

export interface EventsResponse {
  events: AgentEvent[];
}

export type { Project, ProjectStatus, ComplexityEstimate, SuggestedStack };
