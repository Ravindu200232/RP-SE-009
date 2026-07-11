/**
 * SRS document types — the canonical artifact produced by the Requirement
 * Analyzer agent. Mirrors the Pydantic schema in apps/api/app/schemas/srs.py.
 *
 * The root key is always `srs_document`. Sections are intentionally rich but
 * tolerant: the LLM occasionally adds extra keys, so objects allow extra
 * fields rather than failing the whole document.
 */

export type Priority = "high" | "medium" | "low";

export interface AppSummary {
  app_name: string;
  short_description: string;
  business_goal: string;
  target_users: string[];
}

export interface AppType {
  primary_type: string;
  supported_types?: string[];
  frontend_type?: string;
  backend_type?: string;
  database_type?: string;
  example_stack?: Record<string, string>;
}

export interface AuthenticationRequirement {
  login_required: boolean;
  public_landing_pages_required?: boolean;
  multi_role_access_required?: boolean;
  password_reset_required?: boolean;
  email_verification_required?: boolean;
  two_factor_authentication_optional?: boolean;
  [key: string]: boolean | undefined;
}

export interface Role {
  role_key: string;
  role_name: string;
  description: string;
}

export interface RoleAccessEntry {
  role: string;
  allowed_pages: string[];
  allowed_functions: string[];
  restricted_functions?: string[];
}

export interface PageDef {
  page_name: string;
  route: string;
  page_type?: string;
  login_required?: boolean;
  allowed_roles?: string[];
  sections?: string[];
  functions?: string[];
}

export interface TableField {
  name: string;
  type: string;
  primary_key?: boolean;
  nullable?: boolean;
  unique?: boolean;
  default?: string | number | boolean | null;
  values?: string[]; // enum values
  references?: string; // e.g. "users.id"
}

export interface DbTable {
  table_name: string;
  description?: string;
  fields: TableField[];
}

export interface DbRelationship {
  from: string;
  to: string;
  type: "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many" | string;
  via?: string;
  description?: string;
}

export interface DatabaseDesign {
  data_type_standards?: Record<string, string>;
  tables: DbTable[];
  relationships: DbRelationship[];
}

export interface ApiEndpoint {
  method: string;
  path: string;
  description?: string;
  auth_required?: boolean;
  allowed_roles?: string[];
}

export interface FunctionalRequirement {
  id: string; // FR-001
  module: string;
  requirement: string;
  priority: Priority;
}

export interface NonFunctionalRequirement {
  id: string; // NFR-001
  category: string;
  requirement: string;
}

export interface BusinessWorkflow {
  workflow_name: string;
  steps: string[];
}

export interface ValidationRule {
  field: string;
  rule: string;
}

export interface NotificationRule {
  event: string;
  recipients: string[];
  channels: string[];
}

export interface ReportingRequirement {
  report_name: string;
  filters: string[];
  exports: string[];
}

export interface IntegrationRequirement {
  name: string;
  type: string;
  description: string;
  required?: boolean;
}

export interface Ambiguity {
  id: string; // AMB-001
  area: string;
  description: string;
  assumption_made: string;
  needs_clarification: boolean;
}

export interface RiskPriority {
  id: string; // RISK-001
  area: string;
  risk: string;
  severity: "High" | "Medium" | "Low" | string;
  reason: string;
  mitigation: string;
}

export interface AcceptanceCriterion {
  id?: string;
  criterion: string;
}

export interface TraceabilityEntry {
  requirement_id: string;
  module: string;
  pages?: string[];
  tables?: string[];
  test_case?: string;
}

export type DiagramKind =
  | "use_case"
  | "activity"
  | "sequence"
  | "erd"
  | "system_context"
  | "component"
  | "deployment";

export interface DiagramArtifact {
  id: string;
  kind: DiagramKind;
  title: string;
  format: "mermaid" | "plantuml";
  source: string;
  mmd_path?: string;
  svg_path?: string;
  png_path?: string;
}

export interface UiUxRequirements {
  design_style?: string;
  theme?: string;
  dashboard_layout?: string;
  mobile_support?: boolean;
  pwa_support?: boolean;
  required_components?: string[];
  [key: string]: unknown;
}

export interface SrsDocument {
  document_title: string;
  project_name: string;
  version: string;
  document_language: string;
  system_category: string;
  prepared_for: string;
  app_summary: AppSummary;
  app_type: AppType;
  authentication_requirement: AuthenticationRequirement;
  roles: Role[];
  role_access_matrix: RoleAccessEntry[];
  public_pages: PageDef[];
  protected_pages: PageDef[];
  main_modules: string[];
  database_design: DatabaseDesign;
  api_design: ApiEndpoint[];
  functional_requirements: FunctionalRequirement[];
  non_functional_requirements: NonFunctionalRequirement[];
  business_workflows: BusinessWorkflow[];
  validation_rules: ValidationRule[];
  notification_rules: NotificationRule[];
  security_requirements: string[];
  ui_ux_requirements: UiUxRequirements;
  reporting_requirements: ReportingRequirement[];
  integration_requirements: IntegrationRequirement[];
  assumptions: string[];
  constraints: string[];
  ambiguities: Ambiguity[];
  risk_priority: RiskPriority[];
  acceptance_criteria: AcceptanceCriterion[];
  requirement_traceability_matrix: TraceabilityEntry[];
  diagrams: DiagramArtifact[];
}

export interface SrsEnvelope {
  srs_document: SrsDocument;
}

/** Lightweight counts used by the analyzer inspector panel. */
export interface SrsSummary {
  functional: number;
  non_functional: number;
  use_cases: number;
  open_ambiguities: number;
  tables: number;
  roles: number;
  modules: number;
  diagrams: number;
}
