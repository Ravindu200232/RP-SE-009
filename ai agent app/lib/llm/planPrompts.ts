import type { AppTypeDef } from '../appTypes';
import type { ChatMessage } from './ollama';
import { buildSrsDigest } from './srsDigest';

/**
 * The planner now produces one comprehensive implementation plan instead of a
 * chain of separate AppSpec/reference/coverage/master/page/component plans.
 *
 * Builder compatibility is handled by deriving legacy in-memory plan views from
 * this one document. The UI only exposes the implementation plan.
 */
export const PLAN_STAGES = ['implementation'] as const;

export type PlanStage = (typeof PLAN_STAGES)[number];

export const PLAN_META: Record<PlanStage, { title: string; short: string }> = {
  implementation: {
    title: 'Implementation Plan',
    short: 'Complete build blueprint',
  },
};

const LEGACY_PLAN_KEYS = [
  'reference',
  'coverage',
  'master',
  'datatypes',
  'backend',
  'uidesign',
  'pages',
  'pagewise',
  'components',
] as const;

/** Stages to run for the current backend choice. Kept for UI/store callers. */
export function stagesFor(_hasBackend: boolean): PlanStage[] {
  return [...PLAN_STAGES];
}

function envNumber(name: string, fallback: number): number {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function trimSrs(srs: string): string {
  return buildSrsDigest(srs, envNumber('SRS_DIGEST_IMPLEMENTATION_CAP', 100_000));
}

function headingSection(markdown: string, headings: string[]): string {
  const lines = (markdown || '').split(/\r?\n/);
  const lowerHeadings = headings.map((heading) => heading.toLowerCase());
  const start = lines.findIndex((line) => {
    const normalized = line
      .replace(/^#{1,6}\s*/, '')
      .replace(/^\d+\.\s*/, '')
      .trim()
      .toLowerCase();
    return lowerHeadings.some((heading) => normalized.includes(heading));
  });
  if (start < 0) return '';

  const out: string[] = [lines[start]];
  for (let i = start + 1; i < lines.length; i++) {
    if (/^#{1,3}\s+/.test(lines[i]) || /^\d+\.\s+\*\*/.test(lines[i])) break;
    out.push(lines[i]);
  }
  return out.join('\n').trim();
}

function pickSections(markdown: string, groups: string[][]): string {
  const sections = groups
    .map((headings) => headingSection(markdown, headings))
    .filter(Boolean);
  return sections.length ? sections.join('\n\n') : markdown;
}

/**
 * Build-time compatibility: existing build parsers still look for plans.pages,
 * plans.backend, plans.datatypes, etc. Do not write extra plan files; derive
 * those views from the single implementation plan wherever plans are read.
 */
export function expandImplementationPlanAliases(
  plans: Record<string, string>,
): Record<string, string> {
  const implementation = plans.implementation?.trim();
  if (!implementation) return plans;

  const aliases: Record<(typeof LEGACY_PLAN_KEYS)[number], string> = {
    reference: pickSections(implementation, [
      ['project overview'],
      ['quality bar'],
      ['acceptance checklist'],
    ]),
    coverage: pickSections(implementation, [
      ['requirement summary'],
      ['feature inventory'],
      ['workflow'],
      ['acceptance checklist'],
    ]),
    master: pickSections(implementation, [
      ['project overview'],
      ['architecture'],
      ['module breakdown'],
      ['development phases'],
    ]),
    datatypes: pickSections(implementation, [
      ['database schema summary'],
      ['data model summary'],
      ['state model summary'],
    ]),
    backend: pickSections(implementation, [
      ['api routes list'],
      ['backend services'],
      ['authentication'],
      ['workflow'],
    ]),
    uidesign: pickSections(implementation, [
      ['ui and component strategy'],
      ['app shell'],
      ['responsive'],
      ['accessibility'],
    ]),
    pages: pickSections(implementation, [['page/module list'], ['pages and routes']]),
    pagewise: pickSections(implementation, [
      ['page-by-page build blueprint'],
      ['page wise build blueprint'],
      ['page-wise build blueprint'],
    ]),
    components: pickSections(implementation, [
      ['ui and component strategy'],
      ['component strategy'],
      ['page-by-page build blueprint'],
    ]),
  };

  const expanded = { ...plans };
  for (const key of LEGACY_PLAN_KEYS) {
    if (!expanded[key]?.trim()) expanded[key] = aliases[key] || implementation;
  }
  return expanded;
}

const IMPLEMENTATION_PLAN_INSTRUCTIONS = `Produce ONE comprehensive implementation plan in Markdown. Be complete but concise; do not spend tokens explaining methodology.

Use these exact Markdown headings, in this exact order. Do not include numbering before the headings:
# Implementation Plan - <App Name>
## Project Overview & Design Philosophy
## Requirement Summary
## Architecture & Folder Strategy
## Database Schema Summary
## Page/Module List
## API Routes List
## UI and Component Strategy
## Page-by-Page Build Blueprint
## Development Phases
## Quality & Acceptance Checklist

Rules:
- Do not hardcode any example app. Derive every app name, module, route, model, API, role, and workflow from the provided user input.
- If the input is small, keep the plan appropriately small. If the input is large, produce a large production-grade plan.
- If backend/database/auth/CRUD is not required, say "Not required" in the relevant sections and do not invent those systems.
- Stay strictly tied to the user input. Ambiguous items may be listed as assumptions, but do not silently add unrelated dashboards, roles, reports, or CRUD.
- The plan must be actionable enough for a Next.js builder to implement module by module.
- Use Tailwind CSS, TypeScript, shadcn/ui primitives, and Next.js App Router. Use MongoDB/Mongoose only when backend data is required or clearly implied.
- Do not use markdown code fences anywhere in the plan. All tables and lists must be plain Markdown.
- Do not output TypeScript interfaces, code snippets, pseudo-code, JSON, or <file> tags. A plan is prose plus Markdown tables/lists only.
- Keep page routes and API routes separate. Page routes must NEVER start with /api. Login/register pages should be /login, /register, /auth/login, or /auth/register, while API handlers belong only in "API Routes List".
- Preserve exact field names from the input when they are provided. For example, if the input says passwordHash, do not rename it to password.
- Spell shadcn/ui exactly as "shadcn/ui"; never write "shadcs/ui" or another variant.
- For a large enterprise/specification input (many roles/modules/pages/models), do not summarize away coverage. Include at least 12 page routes when the spec names that many pages, at least 8 data models when the spec names that many collections, at least 10 API endpoints when CRUD/workflows are requested, and a page-by-page block for every route in the Page/Module List. Keep each page block compact: 1-3 bullets per label.
- For a small utility or single-page app, these large-app minimums do not apply; stay proportionate.

Mandatory section details:

## Requirement Summary
- Summarize the app goal, target users/roles, must-have workflows, and assumptions.
- Include a compact "Feature Inventory" table with columns: ID | Feature / requirement | User role | Priority | Notes.

## Architecture & Folder Strategy
- Explain app/, components/, lib/, lib/models/, app/api/ organization.
- Include the shared files/components the build should create.
- Keep the architecture reusable and generic for this specific app, not a fixed template.

## Database Schema Summary
- For backend apps, list every collection/model with fields. Use "### ModelName (lib/models/ModelName.ts)" headings.
- Under each model heading, use a Markdown table with exactly: Field | Type | Required | Notes.
- Include field names, types, required/unique/default/ref notes, indexes, and seed-data notes.
- Cover every collection/model explicitly named in the input. Do not stop after only a few examples.
- If the input has a "Database Collections", "Models", "Entities", or schema section, scan it line-by-line and include every named model/collection from that section. For retail/POS specs this commonly includes User, Branch, Category, Brand, Product, Stock, Customer, Supplier, PurchaseOrder, GRN, Sale, OnlineOrder, Payment, and StockMovement when present.
- Model file names must be PascalCase exactly like "lib/models/Product.ts", not lowercase "lib/models/product.ts".
- For no-backend apps, list only client state/local data structures that are truly needed.

## Page/Module List
- Output a Markdown table that starts exactly with:
| Route | Page | Type | Access | Purpose |
| --- | --- | --- | --- | --- |
- Copy those two header lines literally. Do not rename "Page" to "Page Name", "Page / Module Name", or anything else.
- Include every route needed by the input. Use practical Next.js App Router routes.
- This table is for UI/application pages only. Do not put /api/... routes here.
- Keep route rows concise but complete because the builder derives page files from this table.

## API Routes List
- For backend apps, list concrete route handlers in this exact style: "GET /api/products - purpose - access(role)".
- Include collection routes and item routes where CRUD is required.
- For no-backend apps, write "Not required by this specification."
- Use only GET, POST, PUT, PATCH, and DELETE. Do not put endpoint descriptions inside backticks; keep each endpoint as a normal bullet.

## UI and Component Strategy
- Decide the app shell/navigation pattern: Top navbar, Sidebar, Both, or None.
- Describe visual direction, responsive behavior, accessibility notes, and app-specific composite components.
- Require shadcn/ui primitives for controls and native <select> for dropdowns.

## Page-by-Page Build Blueprint
- For each route from Page/Module List, output a block with heading "### /route - Page name".
- Copy the heading shape exactly. Do not wrap the route in backticks. Correct: "### /products - Product listing page". Wrong: "### \`/products\` - Product listing page".
- Under each page heading include exactly these bold labels:
  - **Sections**: concrete top-to-bottom sections with real labels/copy ideas where possible.
  - **Functions**: data fetching, create/edit/delete, search/filter/sort, validation, auth/permission behavior, or local interactions.
  - **Data**: models/fields/API routes/state the page reads or writes.
  - **Design**: the distinctive layout treatment for that page.
- The labels must be exactly "**Sections**:", "**Functions**:", "**Data**:", and "**Design**:" on their own lines. Do not convert them to #### headings.
- Include one page block for every route row from the Page/Module List. Do not skip secondary dashboard pages.

## Development Phases
- Break implementation into 4-8 practical phases. For large apps, group related modules.

## Quality & Acceptance Checklist
- List concrete checks the finished app must pass, including loading/empty/error states, responsive behavior, auth/RBAC if required, CRUD/API validation if required, and no dead buttons.`;

export function buildPlanConversation(opts: {
  srs: string;
  appType: AppTypeDef;
  hasBackend: boolean;
  stage: PlanStage;
  prior?: { stage: string; content: string }[];
}): ChatMessage[] {
  const { srs, appType, hasBackend } = opts;

  const system = `You are a senior full-stack Next.js architect. Think carefully but briefly, then write one precise implementation plan.
Target stack: Next.js 15 App Router + TypeScript + Tailwind CSS + shadcn/ui${
    hasBackend ? ' + MongoDB/Mongoose + Route Handlers' : ''
  }.
The app type is ${appType.label}. ${appType.guidance}
Output only the final Markdown implementation plan. Do not output code, file tags, hidden reasoning, or commentary. Start the answer immediately with "# Implementation Plan - ...".`;

  const srsBlock = srs?.trim()
    ? `Here is the user input/specification to plan from:\n\n"""\n${trimSrs(srs)}\n"""`
    : `No formal SRS was provided. Plan a sensible, complete ${appType.label} based on best practices.`;

  const user = `${srsBlock}

App type: ${appType.label} (${appType.scale} scale).
Backend: ${hasBackend ? 'YES - MongoDB + Mongoose + Next.js Route Handlers.' : 'NO backend unless the input clearly requires it.'}

${IMPLEMENTATION_PLAN_INSTRUCTIONS}

Output ONLY the Markdown for the Implementation Plan.`;

  return [
    { role: 'system', content: system },
    { role: 'user', content: user },
  ];
}

export function buildPlanRepairConversation(opts: {
  srs: string;
  appType: AppTypeDef;
  hasBackend: boolean;
  draft: string;
  diagnostics: string;
}): ChatMessage[] {
  const { srs, appType, hasBackend, draft, diagnostics } = opts;

  const system = `You repair implementation plans for a local Next.js builder. Output one full replacement plan only.
Keep the plan tied to the user input. Fix coverage and structure problems without adding unrelated features.
Output only Markdown. Do not output code, file tags, hidden reasoning, or commentary.`;

  const user = `Original user input/specification:

"""
${trimSrs(srs)}
"""

Current draft implementation plan:

"""
${draft.slice(0, envNumber('PLAN_REPAIR_DRAFT_CAP', 45_000))}
"""

Validator findings to repair:
${diagnostics}

Rewrite the FULL implementation plan. You must preserve valid parts of the draft, but fix every validator finding.

${IMPLEMENTATION_PLAN_INSTRUCTIONS}

Additional repair requirements:
- If expected models are listed in the validator findings, include every one as "### ModelName (lib/models/ModelName.ts)" under Database Schema Summary.
- Include one Page-by-Page Build Blueprint block for every route in the Page/Module List.
- Keep Page/Module List and API Routes List separate.
- Ensure API Routes List has enough concrete endpoint bullets for the workflows in the input.
- The final answer must start with "# Implementation Plan -".`;

  return [
    { role: 'system', content: system },
    {
      role: 'user',
      content: `App type: ${appType.label}. Backend: ${hasBackend ? 'YES' : 'NO'}.\n\n${user}`,
    },
  ];
}

/** A page row the builder can derive from the plan table if needed. */
export interface PlanPage {
  route: string;
  title: string;
  purpose?: string;
}

/**
 * Parse a Markdown route table into pages. Kept for compatibility with older
 * callers and tolerant of this single implementation-plan format.
 */
export function pagesFromPagesPlan(pagesPlan: string, cap = 60): PlanPage[] {
  const out: PlanPage[] = [];
  const seen = new Set<string>();
  for (const line of (pagesPlan || '').split('\n')) {
    const row = line.trim();
    if (!row.startsWith('|')) continue;
    const cells = row
      .split('|')
      .map((c) => c.trim())
      .filter((_, i, a) => i > 0 && i < a.length - 1);
    if (cells.length < 2) continue;
    const routeCell = cells[0].replace(/`/g, '').trim();
    if (!routeCell.startsWith('/')) continue;
    const route = routeCell.split(/\s+/)[0];
    if (seen.has(route)) continue;
    seen.add(route);
    out.push({ route, title: cells[1] || route, purpose: cells[cells.length - 1] });
    if (out.length >= cap) break;
  }
  return out;
}
