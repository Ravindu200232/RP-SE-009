import type { GeneratedFile } from '../artifact/types';
import { isProtectedPath } from '../workspace/fs';

/**
 * Deterministic static analysis of a generated project. Catches the failure
 * modes a 12B model produces most often — broken local imports and
 * client/server boundary violations — WITHOUT needing to install deps or run
 * tsc. The findings drive the auto-repair loop.
 */

export interface FileIssue {
  file: string;
  issues: string[];
}

const CODE_EXT = ['.ts', '.tsx', '.js', '.jsx', '.mjs'];

// import ... from 'x'   |   import 'x'   |   import('x')
const IMPORT_FROM = /\bfrom\s+['"]([^'"]+)['"]/g;
const IMPORT_BARE = /\bimport\s+['"]([^'"]+)['"]/g;
const IMPORT_DYNAMIC = /\bimport\(\s*['"]([^'"]+)['"]\s*\)/g;

function collectSpecs(content: string): string[] {
  const specs = new Set<string>();
  for (const re of [IMPORT_FROM, IMPORT_BARE, IMPORT_DYNAMIC]) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(content))) specs.add(m[1]);
  }
  return [...specs];
}

function isLocal(spec: string): boolean {
  return spec.startsWith('@/') || spec.startsWith('./') || spec.startsWith('../');
}

function usesRechartsUnderscoreExport(content: string): boolean {
  const importRe = /import\s*\{([\s\S]*?)\}\s*from\s*["']recharts["']/g;
  let m: RegExpExecArray | null;
  while ((m = importRe.exec(content))) {
    if (/\b[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]*\b/.test(m[1])) return true;
  }
  return /<\s*(?:Responsive_Container|Area_Chart|Bar_Chart|Line_Chart|Pie_Chart|Radar_Chart|Radial_Bar_Chart|Composed_Chart|Cartesian_Grid|[XYZ]_Axis)\b/.test(
    content,
  );
}

function usesHardcodedBusinessFallback(content: string): boolean {
  const fallbackArray =
    /\?\s*[\w.()]+[\s\S]{0,500}:\s*\(?\s*(?:\/\*[\s\S]*?\*\/\s*)?\[\s*\{[\s\S]{0,1200}?\}\s*\](?:\s*\.map|\s*[),}])/m;
  const namedBusinessArray =
    /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*(?:Data|Items|List|Records|Vehicles|Bookings|Orders|Rooms|Products|Students|Courses|Cars|Rentals|Services|Parts|Inventory|Invoices|Users|Staff|Customers|Reservations|Sales|Metrics|Kpis|KPIs|Activity|Alerts))\s*(?::[^=]+)?=\s*\[\s*\{[\s\S]{0,1200}?\}\s*\]/m;
  const hardcodedMetric =
    /\b(?:Last Sync:\s*Today|Total\s+(?:Inventory Value|Revenue|Sales|Orders|Users|Bookings|Rentals|Products|Customers)\s*:\s*[$0-9])/i;
  return fallbackArray.test(content) || namedBusinessArray.test(content) || hardcodedMetric.test(content);
}

/** True if a local import spec resolves to a file that exists in the project. */
function resolves(fromFile: string, spec: string, files: Set<string>): boolean {
  let base: string;
  if (spec.startsWith('@/')) {
    base = spec.slice(2); // "@/*" maps to project root in the scaffold
  } else {
    const dir = fromFile.split('/').slice(0, -1);
    for (const part of spec.split('/')) {
      if (part === '.' || part === '') continue;
      else if (part === '..') dir.pop();
      else dir.push(part);
    }
    base = dir.join('/');
  }
  const candidates = [
    base,
    base + '.css',
    base + '.json',
    ...CODE_EXT.map((e) => base + e),
    ...CODE_EXT.map((e) => base + '/index' + e),
  ];
  return candidates.some((c) => files.has(c));
}

export function analyzeProject(allFiles: GeneratedFile[]): FileIssue[] {
  const fileSet = new Set(allFiles.map((f) => f.path));
  // Protected (scaffold-owned) files are excluded outright: writeProjectFiles
  // drops any "repair" aimed at them, so flagging one would just make the
  // repair loop retry it forever without effect.
  const codeFiles = allFiles.filter(
    (f) => CODE_EXT.some((e) => f.path.endsWith(e)) && !isProtectedPath(f.path),
  );
  const results: FileIssue[] = [];

  for (const f of codeFiles) {
    const issues: string[] = [];
    const isClient = /^\s*['"]use client['"]/m.test(f.content.slice(0, 60));
    const isPageFile = /^app\/(?:.*\/)?page\.(tsx|jsx)$/.test(f.path);
    const specs = collectSpecs(f.content);

    const clientDirectiveCount = (f.content.match(/^\s*['"]use client['"];?\s*$/gm) ?? [])
      .length;
    if (
      clientDirectiveCount > 0 &&
      (clientDirectiveCount > 1 || !/^\s*['"]use client['"];?/.test(f.content))
    ) {
      issues.push(`The "use client" directive must be the first statement in the file.`);
    }

    for (const spec of specs) {
      if (isLocal(spec) && !resolves(f.path, spec, fileSet)) {
        issues.push(
          `Broken import '${spec}' — that file does not exist in the project. Fix the path or create the dependency.`,
        );
      }
      if (isClient && (spec.includes('/lib/db') || spec.includes('/lib/models/'))) {
        issues.push(
          `"use client" file imports server module '${spec}'. Client components must fetch data from an API route instead of importing the DB/models.`,
        );
      }
      if (
        isPageFile &&
        (spec.includes('/lib/db') || spec.includes('/lib/models') || spec === 'mongoose')
      ) {
        issues.push(
          `Page file imports server/database module '${spec}'. Pages must fetch a relative /api route; only app/api/**/route.ts files may import DB/models.`,
        );
      }
      if (isPageFile && (spec.startsWith('@/app/api/') || /(^|\/)app\/api\//.test(spec))) {
        issues.push(
          `Page file imports API route module '${spec}'. Pages must call fetch("/api/..."); app/api/**/route.ts files are server entrypoints, not page imports.`,
        );
      }
    }

    if (isClient && /\bfrom\s+['"]mongoose['"]/.test(f.content)) {
      issues.push(
        `"use client" file imports mongoose (server-only). Move database access into a route handler or server component.`,
      );
    }

    if (usesRechartsUnderscoreExport(f.content)) {
      issues.push(
        `Invalid Recharts component/import name with underscore. Use exact exports such as ResponsiveContainer, AreaChart, BarChart, LineChart, CartesianGrid, XAxis, and YAxis.`,
      );
    }

    if (/import\s+Link\s+from\s+['"]next\/link['"]/.test(f.content) && /<Link\b[^>]*\bto=/.test(f.content)) {
      issues.push(`next/link uses href, not to. Replace every <Link to=...> with <Link href=...>.`);
    }

    if (f.path === 'app/layout.tsx' && /NEXT_REQUEST_PATH/.test(f.content)) {
      issues.push(
        `app/layout.tsx cannot detect the current route with process.env.NEXT_REQUEST_PATH. Move path-aware shell logic into a client component using usePathname().`,
      );
    }

    if (
      f.path === 'app/layout.tsx' &&
      isClient &&
      /\bexport\s+const\s+metadata\b/.test(f.content)
    ) {
      issues.push(
        `app/layout.tsx cannot export metadata from a "use client" component. Remove the metadata export or move path-aware layout logic into a separate client component.`,
      );
    }

    if (f.path === 'app/layout.tsx') {
      // Imported-but-unrendered navigation: the model imports Navbar/Sidebar
      // into layout.tsx, writes a comment like "handled by a wrapper", and
      // renders NONE of them — shipping an app with no visible navigation
      // (seen live). Flag when layout imports shared components yet renders
      // none of them.
      const named = [
        ...f.content.matchAll(/import\s*\{([^}]+)\}\s*from\s*["']@\/components\/[^"']+["']/g),
      ].flatMap((m) =>
        m[1]
          .split(',')
          .map((s) => s.trim().split(/\s+as\s+/).pop()!.trim())
          .filter(Boolean),
      );
      const defaults = [
        ...f.content.matchAll(
          /import\s+([A-Z][A-Za-z0-9_]*)\s+from\s*["']@\/components\/[^"']+["']/g,
        ),
      ].map((m) => m[1]);
      const fromComponents = [...named, ...defaults];
      const rendersAny = fromComponents.some((n) => new RegExp(`<${n}\\b`).test(f.content));
      if (fromComponents.length > 0 && !rendersAny) {
        issues.push(
          'app/layout.tsx imports shared components (navigation/shell) but renders NONE of them — the app ships with no visible navigation. Render the shared navigation, or an AppShell client wrapper (usePathname) that switches navbar/sidebar, inside <body> around {children}.',
        );
      }
    }

    if (
      f.path.startsWith('app/api/') &&
      f.path.endsWith('/route.ts') &&
      /mongoose\.connect\s*\(/.test(f.content)
    ) {
      issues.push(
        `Route handlers must import { connectDB } from "@/lib/db" and call await connectDB(); do not create local mongoose.connect helpers.`,
      );
    }

    if (/\/api\/placeholder\b/i.test(f.content)) {
      issues.push('Do not use /api/placeholder image URLs; use real assets, CSS visuals, or stable remote images.');
    }

    if (
      /\bmock\b|demo purposes|temporary data|dummy data|sample data|in a real app|in real production app|would be hashed here|would trigger an api call/i.test(f.content) ||
      /\/[/*][\s\S]*?\bplaceholder\s+for\b/i.test(f.content) ||
      /\bExpert Name\b/i.test(f.content) ||
      /\b(?:mock|demo|dummy|sample|temporary)(?:Data|Records|Items|List|Rows)\b/.test(
        f.content,
      ) ||
      // UPPER_SNAKE mock constants (MOCK_LESSONS, DUMMY_USERS, SAMPLE_ROWS…) —
      // \bmock\b misses these because the underscore is a word character.
      /\b(?:MOCK|DUMMY|SAMPLE|DEMO|FAKE|PLACEHOLDER)_[A-Z0-9_]+\b/.test(f.content)
    ) {
      issues.push('Remove mock/demo/temporary data. Backend pages should fetch MongoDB-backed API data with seeded records.');
    }

    if (/await\s+new\s+Promise|simulate(?:d|s)?\s+(?:api|fetch|request)/i.test(f.content)) {
      issues.push('Remove simulated API delays. Backend pages should fetch real route handlers and render seeded MongoDB data.');
    }

    if (
      /setTimeout\s*\(\s*\(\s*\)\s*=>\s*\{[\s\S]{0,500}\b(?:setIsSuccess|setSuccess|setTransaction|receipt|transaction|setCart)\b/i.test(
        f.content,
      )
    ) {
      issues.push('Remove setTimeout-based simulated checkout/success flows. Submit to a real API route and render the API response.');
    }

    if (/setTimeout\s*\([^)]*\bsetCheckoutStatus\b/i.test(f.content)) {
      issues.push('Remove setTimeout-based checkout status simulation. Checkout state should follow the real API response and user action.');
    }

    if (/\btransaction[_-]?id\b[\s\S]{0,180}\bMath\.random\b/i.test(f.content)) {
      issues.push('Do not fabricate transaction or receipt ids with Math.random. Use the API response from the persisted sale/order record.');
    }

    if (
      f.path.startsWith('app/') &&
      f.path.endsWith('/page.tsx') &&
      /\bfetch\s*\(\s*['"`]\/api\//.test(f.content) &&
      usesHardcodedBusinessFallback(f.content)
    ) {
      issues.push(
        'Remove hardcoded fallback business records/metrics. Backend pages must render API/MongoDB data, with empty/loading/error states instead of fake populated fallbacks.',
      );
    }

    if (/Array\.isArray\(\s*await\s+\w+\.json\(\)\s*\)\s*\?\s*\(?\s*await\s+\w+\.json\(\)/.test(f.content)) {
      issues.push('Do not call response.json() twice. Parse each response body once, store it in a variable, then guard that variable with Array.isArray.');
    }

    if (
      !isClient &&
      /\.(tsx|jsx)$/.test(f.path) &&
      (/\b(useState|useEffect|usePathname|useRouter|useSearchParams|useRef|useReducer|useContext|useLayoutEffect|useCallback|useMemo)\s*[(<]/.test(
        f.content,
      ) ||
        /\bon(?:Click|Change|Submit|Input|Blur|Focus|KeyDown|KeyUp|MouseEnter|MouseLeave)=/.test(
          f.content,
        ))
    ) {
      issues.push(
        `Client-only hooks or event handlers are used without a top-line "use client" directive.`,
      );
    }

    if (f.content.trim().length < 5) {
      issues.push('File is empty or a stub — it must contain complete, valid code.');
    }

    if (issues.length) results.push({ file: f.path, issues });
  }

  return results;
}
