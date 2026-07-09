import type { GeneratedFile } from '../artifact/types';
import type { DerivedPage } from './derivePages';
import { analyzeProject } from './analyze';
import { syntaxErrors } from './verify';

export interface BuildAuditItem {
  label: string;
  ok: boolean;
  details: string[];
}

export interface BuildAuditReport {
  score: number;
  summary: string;
  checks: BuildAuditItem[];
}

export interface PageQualityFinding {
  route: string;
  filePath: string;
  issues: string[];
}

const CODE_EXT = ['.ts', '.tsx', '.js', '.jsx'];

function fileMap(files: GeneratedFile[]): Map<string, string> {
  return new Map(files.map((f) => [f.path.replace(/\\/g, '/'), f.content ?? '']));
}

export function apiRouteToFile(route: string): string {
  const clean = route
    .replace(/^\/api\/?/, '')
    .replace(/^\/+|\/+$/g, '')
    .replace(/:([A-Za-z0-9_]+)/g, '[$1]');
  const normalized = clean
    .split('/')
    .map((segment) => (segment.startsWith('[') ? segment : segment.replace(/_/g, '-')))
    .join('/');
  return normalized ? `app/api/${normalized}/route.ts` : 'app/api/route.ts';
}

/**
 * Next.js forbids sibling dynamic segments with different slug names
 * ('id' !== 'param' boot crash, seen live: pages fetching
 * /api/students/${admission_number} derived app/api/students/[param] next to
 * the model's app/api/students/[id]). Unify: for each parent dir, the FIRST
 * dynamic name seen (existing disk files first) wins, and every other derived
 * path at that position is renamed to it. Also dedupes the result.
 */
export function unifyDynamicSegments(paths: string[], existing: string[] = []): string[] {
  const chosen = new Map<string, string>();
  const record = (p: string) => {
    const parts = p.replace(/\\/g, '/').split('/');
    for (let i = 0; i < parts.length; i++) {
      if (/^\[.+\]$/.test(parts[i])) {
        const parent = parts.slice(0, i).join('/');
        if (!chosen.has(parent)) chosen.set(parent, parts[i]);
      }
    }
  };
  for (const p of existing) record(p);
  const out: string[] = [];
  for (const p of paths) {
    const parts = p.replace(/\\/g, '/').split('/');
    for (let i = 0; i < parts.length; i++) {
      if (/^\[.+\]$/.test(parts[i])) {
        const parent = parts.slice(0, i).join('/');
        const picked = chosen.get(parent);
        if (picked) parts[i] = picked;
        else chosen.set(parent, parts[i]);
      }
    }
    out.push(parts.join('/'));
  }
  return [...new Set(out)];
}

function normalizeApiRouteLiteral(route: string): string {
  return route
    .replace(/\$\{[^}]*\}/g, (expr) => (/\bid\b|_id\b|slug|code/i.test(expr) ? '[id]' : '[param]'))
    .split(/[?#]/)[0]
    .replace(/\/+$/g, '');
}

function isConcreteApiRoute(route: string): boolean {
  if (!route || route === '/api') return false;
  if (/\[(?:resource|route|api|endpoint|collection|model|table)\]/i.test(route)) return false;
  if (/\/route$/i.test(route)) return false;
  return true;
}

export interface ApiReference {
  sourceFile: string;
  route: string;
  filePath: string;
}

export function collectApiReferences(files: GeneratedFile[]): ApiReference[] {
  const refs: ApiReference[] = [];
  const seen = new Set<string>();
  const fetchRe = /\bfetch\s*\(\s*([`'"])(\/api\/[\s\S]*?)\1/g;

  for (const file of files) {
    if (!CODE_EXT.some((ext) => file.path.endsWith(ext))) continue;
    if (file.path.startsWith('app/api/')) continue;

    fetchRe.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = fetchRe.exec(file.content || ''))) {
      const route = normalizeApiRouteLiteral(m[2]);
      if (!isConcreteApiRoute(route)) continue;
      const filePath = apiRouteToFile(route);
      const key = `${file.path}:${filePath}`;
      if (seen.has(key)) continue;
      seen.add(key);
      refs.push({ sourceFile: file.path, route, filePath });
    }
  }

  return refs;
}

export function referencedApiFiles(files: GeneratedFile[]): string[] {
  return [...new Set(collectApiReferences(files).map((ref) => ref.filePath))].sort();
}

export function plannedApiFiles(backendPlan: string): string[] {
  const out = new Set<string>();
  const re = /\b(?:GET|POST|PUT|PATCH|DELETE)\s+(\/api\/[A-Za-z0-9_\-/:[\]]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(backendPlan || ''))) {
    const route = normalizeApiRouteLiteral(m[1]);
    if (isConcreteApiRoute(route)) out.add(apiRouteToFile(route));
  }
  return [...out].sort();
}

export function plannedApiFilesFromPlans(plans: Record<string, string>): string[] {
  const out = new Set(plannedApiFiles(plans.backend || ''));
  const text = Object.values(plans).join('\n');
  const re = /`?(\/api\/[A-Za-z0-9_\-/:[\]{}]+)`?/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const route = m[1]
      .replace(/\{([A-Za-z0-9_]+)\}/g, '[$1]')
      .replace(/\/\*$/, '')
      .replace(/\/+$/, '');
    if (isConcreteApiRoute(route)) out.add(apiRouteToFile(route));
  }
  return [...out].sort();
}

function hasAny(content: string, needles: string[]): boolean {
  const lower = content.toLowerCase();
  return needles.some((n) => lower.includes(n));
}

function sectionAfter(markdown: string, heading: string): string {
  const lines = (markdown || '').split(/\r?\n/);
  const start = lines.findIndex((line) =>
    line.toLowerCase().includes(heading.toLowerCase()),
  );
  if (start < 0) return '';
  const out: string[] = [];
  for (let i = start + 1; i < lines.length; i++) {
    if (/^#{1,4}\s+/.test(lines[i]) || /^\d+\.\s+\*\*/.test(lines[i])) break;
    out.push(lines[i]);
  }
  return out.join('\n');
}

function criticalReqIds(coverage: string): string[] {
  const ids = new Set<string>();
  for (const line of (coverage || '').split(/\r?\n/)) {
    if (!/\b(high|critical)\b/i.test(line)) continue;
    const matches = line.match(/\bREQ-\d+\b/gi) ?? [];
    for (const id of matches) ids.add(id.toUpperCase());
  }
  return [...ids].sort();
}

function mappedReqIds(coverage: string): Set<string> {
  const pageMapping = sectionAfter(coverage, 'Page Mapping') || coverage;
  const ids = new Set<string>();
  const matches = pageMapping.match(/\bREQ-\d+\b/gi) ?? [];
  for (const id of matches) ids.add(id.toUpperCase());
  return ids;
}

function addReqIdsFromText(ids: Set<string>, text: string | undefined): void {
  const matches = (text || '').match(/\bREQ-\d+\b/gi) ?? [];
  for (const id of matches) ids.add(id.toUpperCase());
}

function hasPageLevelStaticRecordArray(content: string): boolean {
  const namedArray =
    /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*(?:Data|Items|List|Records|Vehicles|Bookings|Orders|Rooms|Products|Students|Courses|Cars|Rentals|Services|Parts|Inventory|Invoices|Users|Staff|Customers|Reservations|Sales|Metrics|Kpis|KPIs|Activity|Alerts))\s*(?::[^=]+)?=\s*\[\s*\{[\s\S]{0,1200}?\}\s*\]/m;
  if (namedArray.test(content)) return true;
  const firstObjectArray =
    /\b(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*(?::[^=]+)?=\s*\[\s*\{([\s\S]{0,900}?)\}\s*(?:,|\])/m.exec(
      content,
    );
  return !!firstObjectArray?.[1] && /\b(?:id|_id|status|price|amount|email|vehicle|booking|order|customer|room|product|rental|invoice|revenue|stock|mileage)\s*:/.test(firstObjectArray[1]);
}

function hasInlineFallbackRecordArray(content: string): boolean {
  return /\?\s*[\w.()]+[\s\S]{0,500}:\s*\(?\s*(?:\/\*[\s\S]*?\*\/\s*)?\[\s*\{[\s\S]{0,1200}?\}\s*\](?:\s*\.map|\s*[),}])/m.test(
    content,
  );
}

function hasHardcodedBusinessMetric(content: string): boolean {
  return /\b(?:Last Sync:\s*Today|Total\s+(?:Inventory Value|Revenue|Sales|Orders|Users|Bookings|Rentals|Products|Customers)\s*:\s*[$0-9])/i.test(
    content,
  );
}

function pageQualityIssues(page: DerivedPage, content: string, hasBackend: boolean): string[] {
  const issues: string[] = [];
  const isPosRoute = /\/pos\b/i.test(page.route);

  if (content.trim().length < 2200) {
    issues.push('page looks too thin for a production screen');
  }
  if (!/from\s+["']@\/components\/ui\//.test(content)) {
    issues.push('does not use the pre-seeded UI primitives');
  }
  if (
    // Word-bounded/comment-scoped markers, NOT bare substrings: bare "mock"
    // also hits legitimate content ("To Kill a Mockingbird") and bare "todo"
    // hits every page of a todo APP — both then quarantine perfectly good
    // pages. TODO only counts as a comment marker or "TODO:" label.
    /((?:\/\/|\/\*)\s*todo\b|\btodo:|\/api\/placeholder|placeholder for|expert name|mock(?:ed)?\s+data|\bmocks?\b|demo purposes|temporary data|sample data|dummy data|lorem ipsum|coming soon|add your logic|in real app|in a real app|in real production app)/i.test(
      content,
    )
  ) {
    issues.push('contains placeholder/demo wording');
  }

  if (/<Select(?:Trigger|Content|Value|Item)\b|from\s+["']@\/components\/ui\/select["']/i.test(content)) {
    issues.push('uses fragile Radix Select components instead of native labeled select');
  }

  if (
    hasBackend &&
    (/\bsetTimeout\s*\(|await\s+new\s+Promise\b|fake\s+delay/i.test(content) ||
      /\bsimulat(?:e|ed|ing|ion)\s+(?:api|backend|delay|latency|loading|fetch|request|response|server|data)/i.test(
        content,
      ))
  ) {
    issues.push('uses simulated API delays instead of real route fetches');
  }

  if (
    hasBackend &&
    ['list', 'dashboard', 'detail'].includes(page.kind) &&
    hasPageLevelStaticRecordArray(content)
  ) {
    issues.push('uses page-level static record arrays instead of MongoDB-backed API data');
  }

  if (
    hasBackend &&
    ['list', 'dashboard', 'detail'].includes(page.kind) &&
    (hasInlineFallbackRecordArray(content) || hasHardcodedBusinessMetric(content))
  ) {
    issues.push('uses hardcoded fallback business records/metrics instead of MongoDB-backed API data');
  }

  if (['list', 'dashboard'].includes(page.kind)) {
    if (!hasAny(content, ['loading', 'isloading'])) issues.push('missing loading state');
    if (!hasAny(content, ['error', 'seterror'])) issues.push('missing error state');
    if (!hasAny(content, ['empty', 'no ', 'not found'])) issues.push('missing empty/no-data state');
  }

  if (page.kind === 'list') {
    if (!hasAny(content, ['search', 'filter'])) issues.push('missing search/filter controls');
    if (!hasAny(content, ['pagination', 'page', 'next'])) issues.push('missing pagination signal');
    if (!hasAny(content, ['edit', 'delete', 'view'])) issues.push('missing row action signal');
  }

  const hasActualForm = /<form\b|onSubmit|type=["']submit["']/i.test(content);
  const hasControl = /<(?:Input|Textarea|select)\b/i.test(content);
  if (hasControl && !/<Label\b[^>]*htmlFor=/i.test(content)) {
    issues.push('controls lack Label htmlFor/id pairs');
  }
  if (page.kind === 'form' || hasActualForm) {
    if (!/onSubmit|handleSubmit|form/i.test(content)) issues.push('missing real form submit handler');
    if (!/Label/.test(content) || !/Input|Textarea|select/i.test(content)) {
      issues.push('form lacks labeled controls');
    }
  }

  if (isPosRoute && hasBackend) {
    if (!/\bfetch\s*\(\s*['"`]\/api\/(?:spare-parts|parts|products|inventory)/i.test(content)) {
      issues.push('POS page does not fetch sellable inventory from an API route');
    }
    if (!/\bfetch\s*\(\s*['"`]\/api\/(?:pos|sales|orders)/i.test(content) || !/method:\s*['"]POST['"]/i.test(content)) {
      issues.push('POS page does not submit completed sale/order to an API route');
    }
  }

  if (page.kind === 'dashboard' && !isPosRoute) {
    if (!hasAny(content, ['chart', 'recharts', 'trend', 'metric', 'kpi'])) {
      issues.push('dashboard lacks chart/metric signal');
    }
  }

  return issues;
}

export function isBlockingPageQualityIssue(issue: string): boolean {
  // NOTE: "dashboard lacks chart/metric signal" is deliberately NOT blocking —
  // kind inference can misclassify a list page as a dashboard (seen live with
  // /lms/lessons), and deleting a complete page over a missing chart keyword
  // wedges coverage. It stays an advisory finding for the repair pass instead.
  return /too thin|placeholder|mock|demo|temporary|dummy|fragile Radix Select|simulated API delays|controls lack|static record arrays|hardcoded fallback|business records|business metrics|POS page|missing loading|missing error|missing empty|missing no-data|missing search|missing filter|missing row action|missing real form submit|form lacks/i.test(
    issue,
  );
}

export function collectPageQualityFindings(
  files: GeneratedFile[],
  pages: DerivedPage[],
  hasBackend = false,
): PageQualityFinding[] {
  const byPath = fileMap(files);
  return pages
    .map((page) => {
      const content = byPath.get(page.filePath);
      if (!content) return null;
      const issues = pageQualityIssues(page, content, hasBackend);
      return issues.length
        ? { route: page.route, filePath: page.filePath, issues }
        : null;
    })
    .filter((finding): finding is PageQualityFinding => Boolean(finding));
}

function scoreChecks(checks: BuildAuditItem[]): number {
  if (!checks.length) return 0;
  const passed = checks.filter((c) => c.ok).length;
  return Math.round((passed / checks.length) * 100);
}

export function auditGeneratedProject(opts: {
  files: GeneratedFile[];
  pages: DerivedPage[];
  plans: Record<string, string>;
  hasBackend: boolean;
}): BuildAuditReport {
  const { files, pages, plans, hasBackend } = opts;
  const byPath = fileMap(files);
  const checks: BuildAuditItem[] = [];

  const builtMissing = pages
    .filter((p) => !byPath.has(p.filePath))
    .map((p) => `${p.route} -> ${p.filePath}`);
  checks.push({
    label: 'Planned page coverage',
    ok: builtMissing.length === 0,
    details: builtMissing.length ? builtMissing : [`${pages.length} planned pages built`],
  });

  if (plans.coverage) {
    const critical = criticalReqIds(plans.coverage);
    const mapped = mappedReqIds(plans.coverage);
    addReqIdsFromText(mapped, plans.pages);
    addReqIdsFromText(mapped, plans.pagewise);
    const unmapped = critical.filter((id) => !mapped.has(id));
    checks.push({
      label: 'SRS requirement mapping',
      ok: critical.length === 0 || unmapped.length === 0,
      details: critical.length
        ? unmapped.length
          ? unmapped.slice(0, 20)
          : [`${critical.length} critical/high requirements mapped to pages`]
        : ['No critical/high REQ IDs parsed from coverage map'],
    });
  }

  const syntax = files
    .filter((f) => CODE_EXT.some((ext) => f.path.endsWith(ext)))
    .flatMap((f) => syntaxErrors(f.path, f.content).map((e) => `${f.path}: ${e}`));
  checks.push({
    label: 'Syntax safety',
    ok: syntax.length === 0,
    details: syntax.length ? syntax.slice(0, 12) : ['No parser errors found'],
  });

  const staticIssues = analyzeProject(files).flatMap((i) =>
    i.issues.map((issue) => `${i.file}: ${issue}`),
  );
  checks.push({
    label: 'Import and client/server safety',
    ok: staticIssues.length === 0,
    details: staticIssues.length ? staticIssues.slice(0, 12) : ['No static issues found'],
  });

  if (hasBackend) {
    const expectedApis = unifyDynamicSegments(plannedApiFilesFromPlans(plans), [
      ...byPath.keys(),
    ]);
    const missingApis = expectedApis.filter((p) => !byPath.has(p));
    checks.push({
      label: 'Planned API coverage',
      ok: missingApis.length === 0,
      details: expectedApis.length
        ? missingApis.length
          ? missingApis.slice(0, 20)
          : [`${expectedApis.length} planned API route files exist`]
        : ['No explicit API routes were parsed from the backend plan'],
    });

    const diskPaths = [...byPath.keys()];
    const fetchedApis = collectApiReferences(files).map((ref) => ({
      ...ref,
      filePath: unifyDynamicSegments([ref.filePath], diskPaths)[0],
    }));
    const missingFetchedApis = fetchedApis.filter((ref) => !byPath.has(ref.filePath));
    checks.push({
      label: 'Fetched API coverage',
      ok: missingFetchedApis.length === 0,
      details: fetchedApis.length
        ? missingFetchedApis.length
          ? missingFetchedApis
              .slice(0, 20)
              .map((ref) => `${ref.sourceFile} fetches ${ref.route} -> missing ${ref.filePath}`)
          : [`${referencedApiFiles(files).length} fetched API route files exist`]
        : ['No page-level API fetches detected'],
    });
  }

  const perPageIssues = pages.flatMap((p) => {
    const content = byPath.get(p.filePath);
    if (!content) return [];
    return pageQualityIssues(p, content, hasBackend).map((issue) => `${p.route}: ${issue}`);
  });
  checks.push({
    label: 'Function and state coverage',
    ok: perPageIssues.length === 0,
    details: perPageIssues.length ? perPageIssues.slice(0, 20) : ['Pages include expected function/state signals'],
  });

  const globals = byPath.get('app/globals.css') || '';
  const tokenNames = [
    '--color-primary',
    '--color-primary-foreground',
    '--color-accent',
    '--color-bg',
    '--color-surface',
    '--color-fg',
    '--color-muted',
    '--color-border',
  ];
  const missingTokens = tokenNames.filter((t) => !globals.includes(t));
  checks.push({
    label: 'Design system foundation',
    ok: missingTokens.length === 0 && globals.includes('@import "tailwindcss"'),
    details:
      missingTokens.length === 0
        ? ['Tailwind import and required design tokens found']
        : [`Missing design tokens: ${missingTokens.join(', ')}`],
  });

  const score = scoreChecks(checks);
  return {
    score,
    summary:
      score >= 90
        ? 'Strong build: coverage and quality gates look good.'
        : score >= 70
          ? 'Usable build, but review the listed gaps before shipping.'
          : 'Needs another build/repair pass; important coverage or bug gates failed.',
    checks,
  };
}
