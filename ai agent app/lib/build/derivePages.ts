/**
 * Derives an ordered list of concrete pages to build from the Pages Plan that
 * the planner produced (a Markdown table: Route | Page | Type | Access | Purpose).
 *
 * The build orchestrator then builds ONE page per step, each with layout
 * guidance specific to its kind — so every page gets its own distinct layout
 * instead of one reused template.
 */

export type PageKind =
  | 'landing'
  | 'auth'
  | 'dashboard'
  | 'list'
  | 'detail'
  | 'form'
  | 'profile'
  | 'settings'
  | 'content'
  | 'generic';

export interface DerivedPage {
  route: string; // "/", "/dashboard", "/products/[id]"
  filePath: string; // "app/page.tsx", "app/products/[id]/page.tsx"
  title: string;
  kind: PageKind;
  access: string;
  purpose: string;
}

/** Map a route like "/products/[id]" to its App Router page file. */
export function routeToFile(route: string): string {
  const clean = route.replace(/^\/+|\/+$/g, '');
  return clean ? `app/${clean}/page.tsx` : 'app/page.tsx';
}

function inferKind(route: string, title: string, type: string): PageKind {
  // Route + title carry the SPECIFIC intent. The Type column is broad (it tags
  // most app pages "dashboard"/"portal"), so it's only a weak fallback — never
  // let it override a more specific list/form/detail/settings signal.
  const rt = `${route} ${title}`.toLowerCase();
  const ty = (type || '').toLowerCase();
  const isRoot = route === '/' || route === '';

  if (isRoot && /(landing|home|marketing|public|website)/.test(rt)) return 'landing';
  if (/(login|sign[\s-]?in|sign[\s-]?up|register|auth|forgot|reset[\s-]?password)/.test(rt))
    return 'auth';
  if (/\[[^\]]+\]/.test(route) || /(detail|view|single|\bshow\b)/.test(rt)) return 'detail';
  if (/(cart|basket|notifications?|alerts?)/.test(rt)) return 'generic';
  if (/(new|create|add|edit|compose|checkout|\bform\b|submit|apply)/.test(rt)) return 'form';
  if (/(settings|preferences|configuration)/.test(rt)) return 'settings';
  if (/(profile|account|\bmy )/.test(rt)) return 'profile';
  if (/(dashboard|overview|analytics|\bstats\b|metrics|reports?)/.test(rt)) return 'dashboard';
  if (/(about|contact|faq|terms|privacy|pricing|blog|article|docs|help)/.test(rt))
    return 'content';
  if (
    /(list|all |manage|table|index|browse|catalog|directory|inbox|orders?|users?|products?|customers?|courses?|posts?|items?|inventory|transactions?|bookings?|tickets?|appointments?|invoices?|leads?|projects?|tasks?|members?|employees?|patients?|students?|vehicles?|rooms?|lessons?|assignments?|exams?|notices?|subjects?|classes|sections?|teachers?|parents?|fees?|books?|routes?|staff|suppliers?|guests?|reservations?)/.test(
      rt,
    )
  )
    return 'list';
  // Weak fallbacks from the Type column only after specific checks fail.
  if (/detail/.test(ty)) return 'detail';
  if (/auth|login/.test(ty)) return 'auth';
  if (/dashboard|portal|pos/.test(ty)) return 'dashboard';
  if (isRoot) return 'landing';
  return 'generic';
}

/** Extract a route-looking token from a table cell ("`/foo`", "/foo", "[/foo]"). */
function extractRoute(cell: string): string | null {
  const m = cell.match(/\/[A-Za-z0-9_\-/[\]:.]*/);
  if (!m) {
    if (/^\/?$/.test(cell.trim())) return '/';
    return null;
  }
  let r = m[0].trim().replace(/[`*]/g, '');
  // Normalize Express-style :id to App Router [id].
  r = r.replace(/:([A-Za-z0-9_]+)/g, '[$1]');
  if (r.length > 1) r = r.replace(/\/+$/, '');
  return r || '/';
}

/**
 * Parse the Pages Plan markdown table into a deduped, ordered page list.
 * `cap` bounds how many pages the orchestrator will spend a build step on.
 */
export function derivePages(pagesPlan: string, cap = 11): DerivedPage[] {
  const out: DerivedPage[] = [];
  const seen = new Set<string>();
  const lines = (pagesPlan || '').split(/\r?\n/);

  for (const line of lines) {
    if (!line.includes('|')) continue;
    const cells = line
      .split('|')
      .map((c) => c.trim())
      .filter((_, i, arr) => !(i === 0 && arr[0] === '') && true);
    // Drop empty edge cells from "| a | b |".
    while (cells.length && cells[0] === '') cells.shift();
    while (cells.length && cells[cells.length - 1] === '') cells.pop();
    if (cells.length < 2) continue;

    const first = cells[0].toLowerCase();
    if (/^[-:\s]+$/.test(cells.join(''))) continue; // separator row
    if (first === 'route' || first.startsWith('route ')) continue; // header

    const route = extractRoute(cells[0]);
    if (!route) continue;
    if (seen.has(route)) continue;

    const title = (cells[1] || route).replace(/[`*]/g, '').trim() || route;
    const type = cells[2] || '';
    const access = cells[3] || '';
    const purpose = cells[cells.length - 1] || '';

    seen.add(route);
    out.push({
      route,
      filePath: routeToFile(route),
      title,
      kind: inferKind(route, title, type),
      access,
      purpose,
    });
  }

  // Build the landing/home first, then the rest, capped.
  out.sort((a, b) => (a.route === '/' ? -1 : b.route === '/' ? 1 : 0));
  return out.slice(0, cap);
}

/**
 * Per-kind layout guidance — a concrete "must include" checklist so each page
 * is genuinely distinct AND substantial (not a thin stub).
 */
export const KIND_LAYOUT: Record<PageKind, string> = {
  landing:
    'A full marketing landing page. MUST include: a navbar; a strong hero (headline + subcopy + primary & secondary CTA + a visual); a social-proof/logos strip; a features grid (4–6 icon cards); a "how it works" steps section; a stats/metrics band; testimonials; a pricing or final CTA; and a rich multi-column footer. Full-bleed, sectioned, editorial — NEVER a dashboard or table.',
  auth:
    'A centered narrow auth card (max-w-sm) on a clean/branded background. MUST include: heading + subtext, labeled fields with inline validation, a primary submit with loading state, an error area, a divider, and a link to the alternate action. Minimal chrome.',
  dashboard:
    'A real analytics dashboard. MUST include: a header with title + range filter + primary action; a row of 4–6 KPI stat cards (icon, value, label, trend delta); a main chart/visualization panel; a secondary breakdown panel; and a recent-records table with status badges, sorting and pagination. Dense but well-spaced, responsive grid.',
  list:
    'A full management/index page. MUST include: a header with title + count + a primary "create" action; a toolbar with search, filters and sort; records as a responsive table (or card grid) with per-record row/card actions labeled View, Edit and Delete/Archive, status badges and pagination; and explicit isLoading, error, empty/no-data states. Backend apps should fetch seeded MongoDB records from the API instead of client-side sample rows.',
  detail:
    'A single-record detail page that reads the [id] param and fetches that record. MUST include: a back/breadcrumb link; a prominent header (title, key meta, status, action buttons); the body in organized sections or tabs; related sub-records; and loading/not-found states. Clearly distinct from the list layout.',
  form:
    'A focused create/edit page. MUST include: a titled, width-constrained form with fields grouped into logical sections, labels + helper text + inline validation, appropriate input types (select, date, textarea), a clear primary submit (loading state) + cancel, and success/error feedback. Pre-fills when editing.',
  profile:
    'A profile/account page. MUST include: an identity header (avatar, name, role, key meta, edit action) then tabbed or sectioned details (personal info, activity, security), each as cards. Personal and well-structured.',
  settings:
    'A settings page. MUST include: a section nav (or tabs) plus a column of grouped setting cards — each with a title, description and controls (toggles, selects, inputs) and a save action with saved-feedback. Cover several realistic groups.',
  content:
    'A readable content page at prose width (max-w-3xl). MUST include: a clear title/lead, strong typographic hierarchy with several real sections, and supporting elements (FAQ accordion, contact form, or cards) that fit the page. Not a dashboard or card grid.',
  generic:
    'A purpose-built, substantial layout tailored to this page\'s specific job from the plan — several real sections, the right components, and proper states. Do not copy another page\'s structure.',
};

/**
 * Pull ONE page's detailed block out of the Page-wise plan, which uses
 * "### /route — Name" (or "## …") headings followed by sections / data / actions
 * / design for that page. The build feeds this single block to that page's round
 * so the model has the exact sections + functions + design to implement.
 */
export function extractPageSpec(pagewise: string, route: string): string {
  if (!pagewise) return '';
  const blocks = pagewise.split(/\n(?=#{2,4}\s)/);
  const r = route.toLowerCase();
  for (const b of blocks) {
    const head = (b.split('\n')[0] || '').toLowerCase();
    if (
      head.includes(` ${r} `) ||
      head.includes(`${r} `) ||
      head.endsWith(r) ||
      head.includes(`(${r})`) ||
      (route === '/' && /\b(home|landing|index)\b/.test(head))
    ) {
      return b.trim().slice(0, 2600);
    }
  }
  return '';
}
