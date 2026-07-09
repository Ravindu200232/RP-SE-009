/**
 * Prompt for the auto-repair loop. Given one file, the concrete issues found in
 * it, and the project's file manifest, Gemma returns the corrected file.
 */
export function buildRepairMessages(opts: {
  filePath: string;
  fileContent: string;
  issues: string[];
  manifest: string[];
}): { system: string; user: string } {
  const system = `You fix issues in a single file of a Next.js (App Router) + TypeScript + Tailwind + Mongoose project.

Rules:
- Output ONLY one <file path="..."> block containing the COMPLETE corrected file. No prose, no markdown fences.
- Change ONLY what is needed to resolve the listed issues; keep all other working code intact.
- Use the "@/..." import alias (it maps to the project root). Only import from files that exist in the manifest, or from installed packages (next, react, react-dom, mongoose, zod, lucide-react, date-fns, recharts, bcryptjs, jsonwebtoken, class-variance-authority, clsx, tailwind-merge, @radix-ui/*).
- Never import the DB or Mongoose models into a "use client" file; fetch from an API route instead.
- Imports must be real TypeScript imports: import { Badge } from "@/components/ui/badge"; never import { Badge }/ @components..., never import React, { useState } = React, never doubled braces like } } from.
- Fix JSX balance by simplifying structure if needed. Prefer smaller local subcomponents over one huge nested return. Every TabsContent/Card/div must close exactly once with the same tag name.
- Fix corrupt object/sample-data tokens such as lesson.type:, lastUpdated..., repeated spreads, or comma-color fragments; do not preserve invalid syntax.
- If the issue says to remove mock/demo/temporary data, do not merely rename the comment. Remove page-level static record arrays/objects/useMemo data used as primary business data. For backend pages, add a "use client" fetch flow to a relative /api route that matches the page domain (for example /admin/reports -> /api/reports, /vehicles -> /api/vehicles), include loading/error/empty states, parse each response once, unwrap { success, data } into a payload, and guard list payloads with Array.isArray before .map. The API route will seed MongoDB later; the page must not keep static records as source of truth.
- If the issue says hardcoded fallback business records/metrics, remove ternary fallback arrays like data.length ? data : [{...}], static chart rows, KPI fallback arrays, "Last Sync: Today", and fake totals. Render typed empty states instead and fetch/derive every business metric from the API response.
- If the issue says simulated API delays, fake latency, await new Promise, or setTimeout, remove that flow entirely. Replace it with fetch("/api/...") to the nearest domain route (for example /customer/dashboard -> /api/customer/dashboard, /contact -> /api/contact, /spare-parts -> /api/spare-parts). Keep loading/error/empty/success states, but never use timers as backend data.
- If the issue says response.json() is called twice, parse every response exactly once into a named variable, unwrap { success, data } when present, then guard that payload with Array.isArray or object checks.
- Keep API responses on the standard envelope: Response.json({ success: true, data }) for success and Response.json({ success: false, error }, { status }) for failures. Pages must unwrap data after parsing JSON once.
- If the issue says missing loading state, add real React state named isLoading/setIsLoading around the fetch/submit flow and render a visible loading branch before the list/dashboard/form result.
- If the issue says missing error state, add real React state named error/setError and render an Alert or visible error block when it is set.
- If the issue says missing empty/no-data state, render an explicit empty/no-data branch when the fetched array is empty or the filtered results are empty.
- If the issue says missing row action signal, add per-record controls inside every rendered table row/card with literal visible labels or aria-labels containing View, Edit, and Delete (or Archive/Deactivate when deletion is unsafe). Header-only buttons do not count.
- If the issue says POS page, replace hardcoded quick-search products with a fetch to /api/spare-parts (or the nearest inventory API), show loading/error/empty search results, and submit checkout with fetch("/api/pos/sales", { method: "POST", ... }). No fake transaction number, no Math.random ids for saved records, no simulated receipt success.
- If the issue says invalid Recharts component/import name, use exact Recharts exports with no underscores, for example ResponsiveContainer, AreaChart, BarChart, LineChart, CartesianGrid, XAxis, and YAxis.
- If the issue says 'any', replace every any with explicit interfaces, unknown in catch blocks, typed response payloads, or Record<string, unknown> where needed.
- If the issue mentions Mongoose Schema options, remove invalid options such as toJSON: { noTransform: ... }. Use only { timestamps: true } unless a real transform function is required.
- For report/dashboard pages, fetch metrics and recent rows from /api/reports (or the nearest planned API route), use typed empty defaults, and render charts/tables from fetched state. Static decorative labels are okay; static business records are not.
- Write complete, valid, runnable code; no placeholders or TODO stubs.`;

  const user = `FILE: ${opts.filePath}

ISSUES TO FIX:
${opts.issues.map((e) => '- ' + e).join('\n')}

CURRENT CONTENT:
${opts.fileContent}

OTHER FILES IN THE PROJECT (use these for correct import paths):
${opts.manifest
  .filter((p) => p !== opts.filePath)
  .map((p) => '- ' + p)
  .join('\n')}

Return the corrected file as a single <file path="${opts.filePath}"> block.`;

  return { system, user };
}

/**
 * LINE-LEVEL repair: ask for minimal SEARCH/REPLACE edit blocks instead of the
 * whole file. Best for localized TSC/import/syntax errors — the model emits
 * only the few changed lines, so it is fast and can never lose the rest of the
 * file. The caller applies each block by exact match (see lib/build/editBlocks).
 */
export function buildEditRepairMessages(opts: {
  filePath: string;
  fileContent: string;
  issues: string[];
  manifest: string[];
}): { system: string; user: string } {
  const numbered = opts.fileContent
    .split('\n')
    .map((line, i) => `${String(i + 1).padStart(4, ' ')}| ${line}`)
    .join('\n');

  const system = `You fix specific errors in ONE TypeScript file by emitting MINIMAL edits — never the whole file.

Output format — ONLY one or more edit blocks, nothing else (no prose, no fences):
<<<<<<< SEARCH
<exact lines copied verbatim from the current file, including indentation>
=======
<the corrected lines>
>>>>>>> REPLACE

Rules:
- The SEARCH text MUST be an EXACT copy of consecutive lines from the current file (match whitespace). Keep it small — just enough unique context around the error (1-6 lines).
- Change ONLY what is needed to resolve the listed errors. Do NOT reformat or rewrite untouched code.
- Common fixes: add a missing import; correct an import path/name to one that exists in the manifest; add a missing field to an interface so a used property type-checks; replace an undefined identifier with the correct one; annotate a type; fix a typo.
- If an error is "Property 'x' does not exist on type 'T'", prefer ADDING x to interface T (a SEARCH/REPLACE on the interface) over deleting the usage.
- If an error is "Cannot find name 'X'", either import X from the correct manifest path or define/rename it.
- Never introduce 'any'. Use real types, unknown in catch, or Record<string, unknown>.
- Emit one block per distinct edit site. Do not wrap output in markdown.`;

  const user = `FILE: ${opts.filePath}

ERRORS TO FIX:
${opts.issues.map((e) => '- ' + e).join('\n')}

CURRENT CONTENT (line-numbered for reference — do NOT include the "N| " prefixes in SEARCH):
${numbered}

FILES THAT EXIST (for correct import paths):
${opts.manifest
  .filter((p) => p !== opts.filePath)
  .map((p) => '- ' + p)
  .join('\n')}

Emit only SEARCH/REPLACE edit blocks that fix the listed errors.`;

  return { system, user };
}

export function buildQualityRepairMessages(opts: {
  filePath: string;
  fileContent: string;
  route: string;
  issues: string[];
  manifest: string[];
  pageSpec?: string;
  plans?: Record<string, string>;
  hasBackend: boolean;
}): { system: string; user: string } {
  const system = `You upgrade ONE generated Next.js page/component to satisfy product-quality audit gates.

Rules:
- Output ONLY one <file path="..."> block containing the COMPLETE corrected file. No prose, no markdown fences.
- Keep the route and visible purpose intact, but fix every listed quality issue.
- Use the existing shadcn/ui primitives from "@/components/ui/*" and lucide-react icons only.
- Every list/dashboard page must contain explicit loading, error, and empty states in code, plus search/filter/sort or pagination where relevant.
- If the issue mentions missing loading state, add real React state named isLoading/setIsLoading around the fetch/submit flow and render a visible loading branch or loading Card before the records/metrics.
- If the issue mentions missing row action signal, add per-record actions in each rendered row/card with literal visible labels or aria-labels containing View, Edit, and Delete (or Archive/Deactivate when deletion is unsafe). Put them inside the row/card, not only in the page header.
- If the issue mentions POS page, include inventory isLoading/error/empty states, cart empty state, checkout loading state, and success/error feedback around the checkout POST.
- Every real form must use Label with Input/Textarea/Select, an onSubmit/handleSubmit flow, validation feedback, and success/error feedback.
- Remove all comments/text saying mock/demo/dummy/temporary. Do not use /api/placeholder image URLs.
- Remove all fake network code: no await new Promise, no setTimeout for simulated loading, and no comments saying simulate/demo. Backend pages must call relative /api routes instead.
- Parse each fetch Response body once. Never write Array.isArray(await res.json()) ? await res.json() : [].
- For backend apps, do not keep page-level mock/sample/demo/static arrays as the source of truth, even if they are not labeled mock. Fetch from relative /api routes inside useEffect, unwrap { success, data } responses, guard payloads with Array.isArray before .map, and render seeded API records. Use a small typed fallback ONLY for non-persistent decorative content such as image URLs, never as the page's primary records.
- Do not use hardcoded populated fallback arrays/metrics for dashboards or lists. No data.length ? data : [{...}], no static chart rows, no fake KPI totals, and no "Last Sync: Today". Empty API data should show empty states.
- Recharts imports and JSX tags must use exact names with no underscores: ResponsiveContainer, AreaChart, BarChart, LineChart, CartesianGrid, XAxis, YAxis.
- Never import mongoose, "@/lib/db", or "@/lib/models/*" into a "use client" file.
- Preserve TypeScript correctness: no any, no undefined identifiers, no unsupported component props.`;

  const planBits = [
    opts.pageSpec && `PAGE SPEC FOR ${opts.route}:\n${opts.pageSpec.slice(0, 2200)}`,
    opts.plans?.appspec && `APP SPEC JSON:\n${opts.plans.appspec.slice(0, 1200)}`,
    opts.plans?.backend && `BACKEND/API PLAN:\n${opts.plans.backend.slice(0, 1400)}`,
    opts.plans?.datatypes && `DATA MODEL PLAN:\n${opts.plans.datatypes.slice(0, 1400)}`,
  ]
    .filter(Boolean)
    .join('\n\n');

  const user = `FILE: ${opts.filePath}
ROUTE: ${opts.route}
BACKEND APP: ${opts.hasBackend ? 'YES' : 'NO'}

QUALITY ISSUES TO FIX:
${opts.issues.map((e) => '- ' + e).join('\n')}

${planBits}

CURRENT CONTENT:
${opts.fileContent}

OTHER FILES IN THE PROJECT:
${opts.manifest
  .filter((p) => p !== opts.filePath)
  .map((p) => '- ' + p)
  .join('\n')}

Return the upgraded file as a single <file path="${opts.filePath}"> block.`;

  return { system, user };
}
