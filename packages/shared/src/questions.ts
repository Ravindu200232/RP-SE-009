/** Requirement-gathering question types. */

export type AnswerType =
  | "single_choice"
  | "multi_choice"
  | "free_text"
  | "number"
  | "yes_no";

export interface Question {
  id: string; // Q1, Q2 ...
  question: string;
  why_needed: string;
  answer_type: AnswerType;
  suggested_options: string[];
  maps_to_srs_fields: string[];
  /** coverage areas this question contributes to (used by CoverageAuditor). */
  coverage_areas: string[];
  required: boolean;
}

export interface QuestionSession {
  id: string;
  project_id: string;
  questions: Question[];
  total: number;
  coverage_score: number;
  complete: boolean;
  created_at: string;
}

export interface Answer {
  question_id: string;
  value: string | string[] | number | boolean;
  raw_text?: string; // when user picked "Other — type your answer"
}

export interface AnswersPayload {
  answers: Answer[];
}

/** The fixed checklist the CoverageAuditor scores against. */
export const COVERAGE_AREAS = [
  "business_type",
  "main_goal",
  "users_roles",
  "auth",
  "public_pages",
  "app_surfaces", // portal / admin / POS / PWA
  "features_modules",
  "data_entities",
  "payments_billing",
  "reports",
  "notifications",
  "file_uploads",
  "integrations",
  "security_privacy",
  "performance",
  "devices_mobile",
  "languages",
  "deployment_stack",
  "special_rules",
] as const;

export type CoverageArea = (typeof COVERAGE_AREAS)[number];
