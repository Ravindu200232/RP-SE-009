import { promises as fs } from 'fs';
import path from 'path';
import { projectDir, isProtectedPath } from '../workspace/fs';

/**
 * Deterministic post-build repair pass.
 *
 * A 12B local model reliably produces a small set of mechanical mistakes that
 * break the generated app at runtime even when the logic is fine:
 *   1. It uses a lucide-react icon in JSX but forgets to import it.
 *   2. It imports a lucide icon name that does not exist (a hallucinated icon,
 *      e.g. "FolderCanvas").
 *   3. It calls cn(...) without importing it from "@/lib/utils".
 *
 * These are all detectable and fixable without the model, so we sweep every
 * generated source file and repair them. This is what turns "generates a
 * plausible app" into "generates an app that actually boots".
 */

// The pre-seeded shadcn/ui exports â†’ their import path. When a page uses one of
// these in JSX but forgot the import, we add it (the same way missing lucide
// icons are auto-imported). Keeps generated "used <Card> but didn't import it"
// mistakes from 500-ing a page.
const SHADCN_EXPORTS: Record<string, string> = Object.fromEntries(
  (
    [
      ['@/components/ui/button', ['Button']],
      ['@/components/ui/card', ['Card', 'CardHeader', 'CardTitle', 'CardDescription', 'CardContent', 'CardFooter']],
      ['@/components/ui/table', ['Table', 'TableHeader', 'TableBody', 'TableFooter', 'TableHead', 'TableRow', 'TableCell', 'TableCaption']],
      ['@/components/ui/badge', ['Badge']],
      ['@/components/ui/alert', ['Alert', 'AlertTitle', 'AlertDescription']],
      ['@/components/ui/input', ['Input']],
      ['@/components/ui/textarea', ['Textarea']],
      ['@/components/ui/label', ['Label']],
      ['@/components/ui/dialog', ['Dialog', 'DialogTrigger', 'DialogContent', 'DialogHeader', 'DialogFooter', 'DialogTitle', 'DialogDescription', 'DialogClose', 'DialogOverlay', 'DialogPortal']],
      ['@/components/ui/tabs', ['Tabs', 'TabsList', 'TabsTrigger', 'TabsContent']],
      ['@/components/ui/avatar', ['Avatar', 'AvatarImage', 'AvatarFallback']],
      ['@/components/ui/switch', ['Switch']],
    ] as [string, string[]][]
  ).flatMap(([p, names]) => names.map((n) => [n, p] as [string, string])),
);

// Valid lucide icon names, read once from the builder's own lucide-react. The
// generated app pins a slightly different patch of lucide, but the icon name
// set is stable across patches, so this is an authoritative-enough allow-list.
let LUCIDE: Set<string> | null = null;
async function lucideNames(): Promise<Set<string>> {
  if (LUCIDE) return LUCIDE;
  const set = new Set<string>();
  try {
    const mod = (await import('lucide-react')) as Record<string, unknown>;
    for (const k of Object.keys(mod)) {
      // Icon components are PascalCase; skip helpers like createLucideIcon, Icon,
      // icons, and the Lucide*-prefixed internal aliases.
      if (/^[A-Z][A-Za-z0-9]*$/.test(k) && k !== 'Icon' && !k.startsWith('Lucide')) {
        set.add(k);
      }
    }
  } catch {
    /* lucide not resolvable â€” icon fixes are skipped, cn fix still runs */
  }
  LUCIDE = set;
  return set;
}

/** A safe, always-present fallback for a hallucinated/unknown icon. */
const FALLBACK_ICON = 'Circle';

/**
 * Map a mistyped icon identifier back to the real lucide icon it was meant to
 * be: strip separators / underscores and re-PascalCase (Book_Open â†’ BookOpen),
 * then fall back to a case-insensitive match (shoppingcart â†’ ShoppingCart).
 * Returns null when nothing plausibly matches so the caller uses the fallback.
 */
function nearestIcon(name: string, valid: Set<string>): string | null {
  if (/^Loader\d+$/i.test(name) && valid.has('Loader2')) return 'Loader2';
  const pascal = name
    .replace(/[^a-zA-Z0-9]+/g, ' ')
    .trim()
    .split(/\s+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join('');
  if (valid.has(pascal)) return pascal;
  if (/Icon$/.test(pascal)) {
    const withoutIcon = pascal.replace(/Icon$/, '');
    if (valid.has(withoutIcon)) return withoutIcon;
  }
  const flat = name.toLowerCase().replace(/[^a-z0-9]/g, '');
  for (const v of valid) {
    if (v.toLowerCase() === flat) return v;
  }
  // Compound typo where only the FIRST word is a real icon: Lock_Key â†’ Lock,
  // Settings_Remote â†’ Settings. Far better than the generic Circle fallback.
  const first = name.replace(/[^a-zA-Z0-9]+/g, ' ').trim().split(/\s+/)[0];
  if (first) {
    const fp = first.charAt(0).toUpperCase() + first.slice(1);
    if (valid.has(fp)) return fp;
  }
  return null;
}

const SRC_EXT = ['.tsx', '.jsx', '.ts'];
const RECHARTS_COMPONENT_FIXES: Record<string, string> = {
  Responsive_Container: 'ResponsiveContainer',
  Area_Chart: 'AreaChart',
  Bar_Chart: 'BarChart',
  Line_Chart: 'LineChart',
  Pie_Chart: 'PieChart',
  Radar_Chart: 'RadarChart',
  Radial_Bar_Chart: 'RadialBarChart',
  Composed_Chart: 'ComposedChart',
  Cartesian_Grid: 'CartesianGrid',
  X_Axis: 'XAxis',
  Y_Axis: 'YAxis',
  Z_Axis: 'ZAxis',
};

/** Collect every identifier brought in by any import statement in the file. */
function importedIdentifiers(src: string): Set<string> {
  const ids = new Set<string>();
  const importRe = /import\s+([^;]+?)\s+from\s+["'][^"']+["']/g;
  let m: RegExpExecArray | null;
  while ((m = importRe.exec(src))) {
    const clause = m[1];
    // default import: `Foo` or `Foo, { ... }`
    const def = clause.match(/^\s*([A-Za-z_$][\w$]*)\s*(?:,|$)/);
    if (def && !clause.trimStart().startsWith('{')) ids.add(def[1]);
    // namespace: `* as Foo`
    const ns = clause.match(/\*\s+as\s+([A-Za-z_$][\w$]*)/);
    if (ns) ids.add(ns[1]);
    // named: `{ A, B as C }`
    const named = clause.match(/\{([^}]*)\}/);
    if (named) {
      for (const part of named[1].split(',')) {
        const name = part.trim().split(/\s+as\s+/).pop()?.trim();
        if (name) ids.add(name);
      }
    }
  }
  return ids;
}

/** Identifiers DECLARED in the file (function/const/class/let X) â€” so we never
 *  import an icon whose name the file already defines locally. */
function locallyDeclared(src: string): Set<string> {
  const ids = new Set<string>();
  for (const re of [
    /\bfunction\s+([A-Za-z_$][\w$]*)/g,
    /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g,
    /\bclass\s+([A-Za-z_$][\w$]*)/g,
  ]) {
    let m: RegExpExecArray | null;
    while ((m = re.exec(src))) ids.add(m[1]);
  }
  return ids;
}

/** PascalCase tags used as JSX elements: `<Foo`, `<Foo.Bar` â†’ "Foo". */
function jsxTagsUsed(src: string): Set<string> {
  const tags = new Set<string>();
  const re = /<([A-Z][A-Za-z0-9]+)[\s/>.]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) tags.add(m[1]);
  return tags;
}

/** PascalCase icon identifiers used as data values, e.g. `{ icon: Star }`. */
function iconValuesUsed(src: string): Set<string> {
  const names = new Set<string>();
  const re = /\b(?:icon|Icon)\s*:\s*([A-Z][A-Za-z0-9]*)\b/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) names.add(m[1]);
  return names;
}

function mergeDuplicateNamedImports(src: string): { content: string; changed: boolean } {
  const lines = src.split('\n');
  const seen = new Map<string, { index: number; names: Set<string> }>();
  const remove = new Set<number>();
  const re = /^(\s*)import\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']\s*;?(?:\s*\/\/.*)?\s*$/;

  lines.forEach((line, index) => {
    const m = line.match(re);
    if (!m) return;
    const names = m[2]
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!names.length) return;
    const spec = m[3];
    const existing = seen.get(spec);
    if (!existing) {
      seen.set(spec, { index, names: new Set(names) });
      return;
    }
    for (const name of names) existing.names.add(name);
    remove.add(index);
  });

  let changed = remove.size > 0;
  for (const { index, names } of seen.values()) {
    const line = lines[index];
    const m = line.match(re);
    if (!m) continue;
    const merged = [...names].sort().join(', ');
    const next = `${m[1]}import { ${merged} } from "${m[3]}";`;
    if (next !== line) {
      lines[index] = next;
      changed = true;
    }
  }

  if (!changed) return { content: src, changed: false };
  return { content: lines.filter((_, index) => !remove.has(index)).join('\n'), changed: true };
}

function normalizeIdentifier(name: string): string {
  return name.replace(/_/g, '').toLowerCase();
}

function lowerCamel(name: string): string {
  return name.charAt(0).toLowerCase() + name.slice(1);
}

function declaredIdentifiers(src: string): Set<string> {
  const ids = new Set<string>();
  for (const re of [
    /\bfunction\s+([A-Za-z_$][\w$]*)/g,
    /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g,
    /\bclass\s+([A-Za-z_$][\w$]*)/g,
  ]) {
    let m: RegExpExecArray | null;
    while ((m = re.exec(src))) ids.add(m[1]);
  }
  const arrayDecl = /\b(?:const|let|var)\s*\[([^\]]+)\]/g;
  let arr: RegExpExecArray | null;
  while ((arr = arrayDecl.exec(src))) {
    for (const part of arr[1].split(',')) {
      const id = part.trim();
      if (/^[A-Za-z_$][\w$]*$/.test(id)) ids.add(id);
    }
  }
  return ids;
}

function ensureReactHookImports(src: string): { content: string; added: string[] } {
  const hookNames = [
    'useState',
    'useEffect',
    'useMemo',
    'useCallback',
    'useRef',
    'useReducer',
    'useContext',
    'useLayoutEffect',
  ];
  const imported = importedIdentifiers(src);
  const declared = locallyDeclared(src);
  const needed = hookNames.filter(
    (hook) =>
      new RegExp(`(?<!\\.)\\b${hook}\\s*[(<]`).test(src) &&
      !imported.has(hook) &&
      !declared.has(hook),
  );
  if (!needed.length) return { content: src, added: [] };

  const reactImport = /import\s+React\s*,\s*\{([^}]*)\}\s*from\s*["']react["'][^\n]*/;
  const namedImport = /import\s*\{([^}]*)\}\s*from\s*["']react["'][^\n]*/;
  const defaultImport = /import\s+React\s+from\s*["']react["'][^\n]*/;
  const merge = (inner: string) =>
    [...new Set([...inner.split(',').map((s) => s.trim()).filter(Boolean), ...needed])]
      .sort()
      .join(', ');

  if (reactImport.test(src)) {
    return {
      content: src.replace(reactImport, (_m, inner: string) => `import React, { ${merge(inner)} } from "react";`),
      added: needed,
    };
  }
  if (namedImport.test(src)) {
    return {
      content: src.replace(namedImport, (_m, inner: string) => `import { ${merge(inner)} } from "react";`),
      added: needed,
    };
  }
  if (defaultImport.test(src)) {
    return {
      content: src.replace(defaultImport, `import React, { ${needed.sort().join(', ')} } from "react";`),
      added: needed,
    };
  }
  return {
    content: addImport(src, `import { ${needed.sort().join(', ')} } from "react";`),
    added: needed,
  };
}

/** The set of names imported specifically from "lucide-react", with the span. */
function lucideImport(src: string): { names: string[]; start: number; end: number } | null {
  const re = /import\s*\{([^}]*)\}\s*from\s*["']lucide-react["'][^\n]*/;
  const m = re.exec(src);
  if (!m) return null;
  const names = m[1]
    .split(',')
    .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
    .filter(Boolean);
  return { names, start: m.index, end: m.index + m[0].length };
}

function splitShadcnBarrelImports(src: string): { content: string; changed: boolean } {
  let changed = false;
  const content = src.replace(
    /^(\s*)import\s*\{([^}]*)\}\s*from\s*["']@\/components\/ui\/?["'];?\s*$/gm,
    (full, indent: string, inner: string) => {
      const byPath = new Map<string, string[]>();
      const unknown: string[] = [];
      for (const raw of inner.split(',')) {
        const part = raw.trim();
        if (!part) continue;
        const imported = part.split(/\s+as\s+/)[0]?.trim();
        const path = imported ? SHADCN_EXPORTS[imported] : undefined;
        if (!path) {
          unknown.push(part);
          continue;
        }
        const names = byPath.get(path) ?? [];
        if (!names.includes(part)) names.push(part);
        byPath.set(path, names);
      }
      if (byPath.size === 0) return full;
      changed = true;
      const lines = [...byPath.entries()].map(
        ([path, names]) => `${indent}import { ${names.join(', ')} } from "${path}";`,
      );
      if (unknown.length) {
        lines.push(`${indent}import { ${unknown.join(', ')} } from "@/components/ui";`);
      }
      return lines.join('\n');
    },
  );
  return { content, changed };
}

/**
 * A local model that writes an invalid schema type (e.g. `type: new
 * mongoose.Types.ObjectId()`) sometimes "self-corrects" the same schema over and
 * over inside ONE file — seen live: lib/models/task.ts ballooned to 2907 lines
 * with `new Schema(` 116 times and NO model export. When a model file clearly ran
 * away (many duplicate schemas), keep only the FIRST schema + a clean model
 * export and drop the rest. Returns null if the file looks normal.
 */
function collapseRunawayModel(src: string): string | null {
  const schemaCount = (src.match(/new\s+Schema\s*\(/g) || []).length;
  if (schemaCount <= 3) return null; // 1-2 schemas can be legitimate

  const decl = src.match(/(?:export\s+)?const\s+(\w+)\s*=\s*new\s+Schema\s*\(/);
  if (!decl || decl.index == null) return null;
  const schemaVar = decl[1];
  const openParen = src.indexOf('(', decl.index + decl[0].length - 1);
  if (openParen < 0) return null;

  let depth = 0;
  let end = -1;
  for (let i = openParen; i < src.length; i++) {
    if (src[i] === '(') depth++;
    else if (src[i] === ')') {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  if (end < 0) return null;
  let stmtEnd = end + 1;
  if (src[stmtEnd] === ';') stmtEnd++;

  const head = src.slice(0, stmtEnd);
  const iface = src.match(/export\s+interface\s+(I\w+)/)?.[1];
  const modelName =
    src.match(/export\s+interface\s+I(\w+)/)?.[1] ||
    schemaVar.replace(/Schema.*$/, '') ||
    'Model';
  const generic = iface ? `<${iface}>` : '';
  return `${head}\n\nexport const ${modelName} =\n  mongoose.models.${modelName} || mongoose.model${generic}("${modelName}", ${schemaVar});\n`;
}

/** Repair a single file's content; returns new content + what changed. */
export async function autofixContent(
  src: string,
): Promise<{ content: string; changes: string[] }> {
  const valid = await lucideNames();
  const changes: string[] = [];
  let out = src;

  if (/<\/?_(?:thought|thinking|file|project|artifact)\b|<\/?(?:think|thought|thinking)\b/i.test(out)) {
    out = out
      .replace(/<_(?:thought|thinking)\b[^>]*>[\s\S]*?<\/_(?:thought|thinking)>/gi, '')
      .replace(/<(?:think|thought|thinking)\b[^>]*>[\s\S]*?<\/(?:think|thought|thinking)>/gi, '')
      .replace(/<\/?_(?:thought|thinking)\b[^>]*>/gi, '')
      .replace(/<\/?(?:think|thought|thinking)\b[^>]*>/gi, '')
      .replace(/<\/?_(?:file|project|artifact)\b[^>]*>/gi, '');
    changes.push('removed leaked Gemma control markup');
  }

  // Collapse a runaway self-"correcting" model file BEFORE any other rule wastes
  // time on thousands of duplicate lines.
  {
    const collapsed = collapseRunawayModel(out);
    if (collapsed) {
      out = collapsed;
      changes.push('collapsed runaway duplicate Mongoose schema to a single model');
    }
  }

  // Mongoose foreign-key type mistake: `type: new mongoose.Types.ObjectId()` (or
  // `new_mongoose...`) is invalid in a Schema and is what sends the model into
  // the self-correcting loop above. The correct schema type is
  // mongoose.Schema.Types.ObjectId (works whenever `mongoose` is imported).
  if (/type:\s*new[_\s]*mongoose|new_mongoose/.test(out)) {
    out = out
      .replace(/type:\s*new\s+mongoose\.(?:Schema\.)?Types\.ObjectId\s*(?:\(\s*\))?/g, 'type: mongoose.Schema.Types.ObjectId')
      .replace(/type:\s*new_mongoose\.(?:Schema\.)?Types\.ObjectId\s*(?:\(\s*\))?/g, 'type: mongoose.Schema.Types.ObjectId')
      .replace(/\bnew_mongoose\b/g, 'mongoose');
    changes.push('fixed Mongoose ObjectId schema type');
  }

  // The backend kit's @/lib/api/response exports EXACTLY apiSuccess + apiError.
  // Local models invent variants (apiSuccess_, apiSuccess_as_response) → a hard
  // "export not found" that fails the whole API graph and cascades 500s to every
  // other route. Normalize the import to the two real names.
  {
    const respImp = /import\s*\{([^}]*)\}\s*from\s*["']@\/lib\/api\/response["']/;
    const m = out.match(respImp);
    if (m) {
      const names = new Set<string>();
      for (const raw of m[1].split(',')) {
        const n = raw.trim().replace(/\s+as\s+[\w$]+/, '');
        if (!n) continue;
        if (/^apiSuccess/i.test(n)) names.add('apiSuccess');
        else if (/^apiError/i.test(n)) names.add('apiError');
      }
      if (names.size) {
        const fixed = `import { ${[...names].join(', ')} } from "@/lib/api/response"`;
        if (fixed !== m[0]) {
          out = out.replace(respImp, fixed);
          changes.push('normalized @/lib/api/response import to apiSuccess/apiError');
        }
      }
    }
  }

  {
    const merged = mergeDuplicateNamedImports(out);
    if (merged.changed) {
      out = merged.content;
      changes.push('merged duplicate named imports from the same module');
    }
  }

  {
    const split = splitShadcnBarrelImports(out);
    if (split.changed) {
      out = split.content;
      changes.push('split shadcn/ui barrel import into exact primitive imports');
    }
  }

  if (/\bCard_content\s+as\s+CardContent\b/.test(out)) {
    out = out.replace(/\bCard_content\s+as\s+CardContent\b/g, 'CardContent');
    changes.push('fixed mistyped CardContent import alias');
  }

  if (/variant=(["'])info\1/.test(out) || /variant=\{[^}]*["']info["'][^}]*\}/.test(out)) {
    out = out
      .replace(/variant=(["'])info\1/g, 'variant="secondary"')
      .replace(/variant=\{([^}]*?)["']info["']([^}]*)\}/g, 'variant={$1"secondary"$2}');
    changes.push('normalized unsupported Badge variant "info" to "secondary"');
  }

  if (/\bnew_URLSearchParams\b/.test(out)) {
    out = out.replace(/\bnew_URLSearchParams\b/g, 'new URLSearchParams');
    changes.push('fixed new_URLSearchParams typo');
  }

  if (/\bnew_URL\b/.test(out)) {
    out = out.replace(/\bnew_URL\b/g, 'new URL');
    changes.push('fixed new_URL typo');
  }

  if (/toJSON:\s*\{\s*noTransform\s*:/.test(out)) {
    out = out
      .replace(/,\s*toJSON:\s*\{\s*noTransform\s*:\s*\(\)\s*=>\s*[^}\n]+?\s*\}/g, '')
      .replace(/toJSON:\s*\{\s*noTransform\s*:\s*\(\)\s*=>\s*[^}\n]+?\s*\}\s*,?/g, '');
    changes.push('removed invalid Mongoose toJSON.noTransform option');
  }

  if (/\bor_string\b/.test(out)) {
    out = out.replace(/\bor_string\b/g, 'string');
    changes.push('fixed hallucinated or_string type');
  }

  if (/\._id\s*\(/.test(out)) {
    out = out.replace(/\._id\s*\(\s*\)/g, '.min(1)');
    changes.push('replaced hallucinated zod _id() helper');
  }

  if (/\._description\s*\(/.test(out)) {
    out = out.replace(/\._description\s*\(/g, '.describe(');
    changes.push('replaced hallucinated zod _description() helper');
  }

  if (/\.error_format\s*\(/.test(out)) {
    out = out.replace(/\.error_format\s*\(\s*\)/g, '.error.flatten()');
    changes.push('replaced hallucinated zod error_format() helper');
  }

  if (/\.error\.flatten\(\)\._errors\b/.test(out)) {
    out = out.replace(/\.error\.flatten\(\)\._errors\b/g, '.error.flatten().fieldErrors');
    changes.push('replaced zod flattened _errors with fieldErrors');
  }

  if (/from\s+["'](@\/[^"']+)\.ts["']/.test(out)) {
    out = out.replace(/from\s+["'](@\/[^"']+)\.ts["']/g, 'from "$1"');
    changes.push('removed .ts extension from aliased import');
  }

  if (/\b(?:request|req)\._url\b/.test(out)) {
    out = out.replace(/\b(request|req)\._url\b/g, 'new URL($1.url)');
    changes.push('replaced private request._url access');
  }

  if (/\b(?:request|req)\._params\b/.test(out)) {
    out = out.replace(
      /const\s+\{\s*id\s*\}\s*=\s*await\s+(request|req)\._params\s*;?/g,
      'const body = await $1.json();\n    const { id } = body;',
    );
    out = out.replace(/\b(request|req)\._params\b/g, '{}');
    changes.push('replaced private request._params access');
  }

  if (/\b(?:request|req)\.nextUrl\.params\b/.test(out)) {
    out = out.replace(/\b(request|req)\.nextUrl\.params\.([A-Za-z_$][\w$]*)\b/g, '$1.nextUrl.searchParams.get("$2")');
    out = out.replace(/\b(request|req)\.nextUrl\.params\b/g, '$1.nextUrl.searchParams');
    changes.push('replaced private nextUrl.params access');
  }

  if (/\b(let|const)\s+query\s*=\s*\{\s*\}\s*;/.test(out)) {
    out = out.replace(/\b(let|const)\s+query\s*=\s*\{\s*\}\s*;/g, '$1 query: Record<string, unknown> = {};');
    changes.push('typed empty query object as Record<string, unknown>');
  }

  if (/import\s*\{\s*NextResponse\s*\}\s*from\s*["']_next\/headers["']/.test(out)) {
    out = out.replace(
      /import\s*\{\s*NextResponse\s*\}\s*from\s*["']_next\/headers["'];?/g,
      'import { NextResponse } from "next/server";',
    );
    changes.push('fixed NextResponse import from _next/headers to next/server');
  }

  // NextRequest/NextResponse live in "next/server". Local models hallucinate the
  // subpath ("next/next", "next/response", "next/api", "next/http") — none exist,
  // so Module-not-found 500s every API route that uses them.
  {
    const badServerSubpath =
      /import\s*(\{[^}]*\b(?:NextResponse|NextRequest)\b[^}]*\})\s*from\s*["']next\/(?:next|response|request|api|http|headers)["']/g;
    if (badServerSubpath.test(out)) {
      out = out.replace(badServerSubpath, 'import $1 from "next/server"');
      changes.push('fixed NextResponse/NextRequest import to next/server');
    }
  }

  // Invalid Tailwind token in an arbitrary-value className (or globals.css):
  // the model invents a `--tw-theme_` prefix and puts an opacity-slash inside
  // var() — both fail Turbopack's PostCSS parse and 500 EVERY route.
  //   var(--tw-theme_--color-primary/0.1)  →  var(--color-primary)
  if (/--tw-theme_|var\(\s*--[A-Za-z0-9_-]+\s*\/\s*[0-9.]/.test(out)) {
    const next = out
      .replace(/var\(\s*(--[A-Za-z0-9_-]+)\s*\/\s*[0-9.]+\s*\)/g, 'var($1)')
      .replace(/--tw-theme_--/g, '--');
    if (next !== out) {
      out = next;
      changes.push('fixed invalid Tailwind token/opacity-slash in var()');
    }
  }

  for (const [bad, good] of Object.entries(RECHARTS_COMPONENT_FIXES)) {
    if (new RegExp(`\\b${bad}\\b`).test(out)) {
      out = out.replace(new RegExp(`\\b${bad}\\b`, 'g'), good);
      changes.push(`fixed Recharts export ${bad} -> ${good}`);
    }
  }

  if (/from\s+["']framer-motion["']/.test(out)) {
    out = out
      .replace(/^\s*import\s*\{[^}]*\}\s*from\s*["']framer-motion["'];?\s*$/gm, '')
      .replace(/<motion\.([a-z][A-Za-z0-9-]*)(\s|>)/g, '<$1$2')
      .replace(/<\/motion\.([a-z][A-Za-z0-9-]*)>/g, '</$1>')
      .replace(/<AnimatePresence[^>]*>/g, '<>')
      .replace(/<\/AnimatePresence>/g, '</>');
    changes.push('removed forbidden framer-motion import and downgraded motion tags');
  }

  {
    const schemaNames = new Set<string>();
    out = out.replace(
      /^\s*import\s*\{([^}]+)\}\s*from\s*["']@inner-logic\/zod-schemas["'];?\s*$/gm,
      (_full, inner: string) => {
        for (const raw of inner.split(',')) {
          const name = raw.trim().split(/\s+as\s+/).pop()?.trim();
          if (name && /^[A-Za-z_$][\w$]*$/.test(name)) schemaNames.add(name);
        }
        return '';
      },
    );
    if (schemaNames.size > 0) {
      const declarations = [...schemaNames]
        .map((name) => `const ${name} = z.object({}).passthrough();`)
        .join('\n');
      out = addImport(out, declarations);
      if (!importedIdentifiers(out).has('z')) {
        out = addImport(out, 'import { z } from "zod";');
      }
      changes.push('replaced forbidden @inner-logic/zod-schemas import with local zod schemas');
    }
  }

  if (/\bReact\./.test(out) && !/import\s+React\b/.test(out)) {
    out = addImport(out, `import React from "react";`);
    changes.push('added missing React import for React.* usage');
  }

  {
    const navImport = /import\s*\{([^}]*)\}\s*from\s*["']next\/navigation["'][^\n]*/;
    const allowedNavigation = new Set([
      'useParams',
      'usePathname',
      'useRouter',
      'useSearchParams',
      'redirect',
      'notFound',
      'permanentRedirect',
    ]);
    const m = out.match(navImport);
    if (m) {
      const kept = m[1]
        .split(',')
        .map((part) => part.trim())
        .filter((part) => {
          const imported = part.split(/\s+as\s+/)[0].trim();
          return allowedNavigation.has(imported);
        });
      if (kept.length !== m[1].split(',').filter((part) => part.trim()).length) {
        out = out.replace(navImport, kept.length ? `import { ${kept.join(', ')} } from "next/navigation";` : '');
        changes.push('removed invalid next/navigation named import(s)');
      }
    }
  }

  {
    const reactHooks = ensureReactHookImports(out);
    if (reactHooks.added.length) {
      out = reactHooks.content;
      changes.push(`added missing React hook import(s): ${reactHooks.added.join(', ')}`);
    }
  }

  if (
    /^\s*["']use client["'];?/.test(out) &&
    /<html[\s>]/.test(out) &&
    /\bexport\s+const\s+metadata\s*=/.test(out)
  ) {
    out = out.replace(
      /\n?export\s+const\s+metadata\s*=\s*\{[\s\S]*?\};\s*\n?/,
      '\n',
    );
    changes.push('removed metadata export from client root layout');
  }

  if (/mock|simulate|demo|temporary data|sample data|placeholder for|in a real app|in real production app|would be used here|would trigger an api call/i.test(out)) {
    const lines = out.split('\n');
    const filtered = lines.filter(
      (line) =>
        !/\/\/.*\b(mock|simulate|demo|temporary data|sample data|placeholder for|in a real app|in real production app|would be used here|would trigger an api call)\b/i.test(line) &&
        !/\{\/\*.*\b(mock|simulate|demo|temporary data|sample data|placeholder for|in a real app|in real production app|would be used here|would trigger an api call)\b.*\*\/\}/i.test(
          line,
        ),
    );
    if (filtered.length !== lines.length) {
      out = filtered.join('\n');
      changes.push('removed generated mock/demo/simulate placeholder comments');
    }
  }

  // ---- 0a. "use client" must be the first statement in a module. Repairs can
  //          accidentally insert it below imports; normalize to one top-line
  //          directive before every other expression/import. ----
  const clientDirectiveCount = (out.match(/^\s*["']use client["'];?\s*$/gm) ?? []).length;
  if (
    clientDirectiveCount > 0 &&
    (clientDirectiveCount > 1 || !/^\s*["']use client["'];?/.test(out))
  ) {
    out = out
      .split('\n')
      .filter((line) => !/^\s*["']use client["'];?\s*$/.test(line))
      .join('\n')
      .replace(/^\s+/, '');
    out = `"use client";\n\n${out}`;
    changes.push('moved "use client" directive to the first line');
  }

  // ---- 0. Collapse a broken arrow function: `)` <newline> `=>` is a JS syntax
  //         error ("Unexpected line break between arrow head and arrow"). The
  //         local model emits this on long handler signatures. ----
  if (/\)\s*\n\s*=>/.test(out)) {
    out = out.replace(/\)\s*\n\s*=>/g, ') =>');
    changes.push('fixed broken arrow function line break');
  }

  // ---- 0a2. Stray trailing pseudo-tag the model leaves after the code, e.g. a
  //           lone `</query>` or `</answer>` on the last line (a wrapper tag it
  //           hallucinated). A .tsx module never ends with a bare close-tag, so
  //           removing trailing ones at EOF is safe and fixes the parse error. ----
  if (/\n\s*<\/[a-zA-Z][\w-]*>\s*$/.test(out)) {
    out = out.replace(/(?:\r?\n\s*<\/[a-zA-Z][\w-]*>\s*)+$/, '\n');
    changes.push('removed stray trailing pseudo-tag');
  }

  // ---- 0b. Invalid next/font/google subset. The model often writes
  //          subsets: ["variable"] (confusing variable fonts with subsets),
  //          which throws at build time. "variable" is never a valid subset â€”
  //          drop it, defaulting to "latin". ----
  if (/subsets:\s*\[[^\]]*["']variable["'][^\]]*\]/.test(out)) {
    out = out.replace(/subsets:\s*\[([^\]]*)\]/g, (m, inner) => {
      if (!/["']variable["']/.test(inner)) return m;
      const kept = inner
        .split(',')
        .map((s: string) => s.trim())
        .filter((s: string) => s && !/^["']variable["']$/.test(s));
      return `subsets: [${kept.length ? kept.join(', ') : '"latin"'}]`;
    });
    changes.push('removed invalid "variable" font subset');
  }

  // ---- 0b2. Function declaration written with an arrow body:
  //           `export function X(...) => {` â€” a syntax error. Drop the `=>`. ----
  if (/\bfunction\s+\w+\s*\([^)]*\)\s*=>\s*\{/.test(out)) {
    out = out.replace(/(\bfunction\s+\w+\s*\([^)]*\))\s*=>\s*\{/g, '$1 {');
    changes.push('removed `=>` from a function declaration');
  }

  // ---- 0b3. Garbage numeric spread `{...123}` the model sometimes emits. ----
  if (/\{\s*\.\.\.\s*\d+\s*\}/.test(out)) {
    out = out.replace(/\s*\{\s*\.\.\.\s*\d+\s*\}/g, '');
    changes.push('removed garbage numeric spread {...N}');
  }

  // ---- 0b4. Import written with `=` instead of `from`:
  //           `import { A, B } = "mod"` â†’ `import { A, B } from "mod"`. ----
  if (/import\s+[^;]*\}\s*=\s*["'][^"']+["']/.test(out)) {
    out = out.replace(
      /(import\s+(?:[\w*]+\s*,\s*)?\{[^}]*\}\s*)=\s*(["'][^"']+["'])/g,
      '$1from $2',
    );
    changes.push('fixed import that used `=` instead of `from`');
  }

  // ---- 0b4a. Import clause hallucinated as React assignment:
  //             `import React, { useState } = React;` -> from "react". ----
  if (/import\s+React\s*,\s*\{[^}]*\}\s*=\s*React\s*;?/.test(out)) {
    out = out.replace(
      /import\s+React\s*,\s*\{([^}]*)\}\s*=\s*React\s*;?/g,
      'import React, { $1 } from "react";',
    );
    changes.push('fixed React import that used `= React`');
  }

  // ---- 0b4b. Common malformed shadcn import fragments from local models. ----
  if (/import\s+\{[^}]+\}\s*\/\s*@components\/ui\//.test(out)) {
    out = out.replace(
      /import\s+\{([^}]+)\}\s*\/\s*@components\/ui\/([A-Za-z0-9_-]+)"?\s*/g,
      'import { $1 } from "@/components/ui/$2";',
    );
    changes.push('fixed malformed / @components/ui import');
  }

  if (/import\s+\{[^}]+\}\s*,\s*\{[^}]+\}\s*\}\s*from\s*["'][^"']+["']/.test(out)) {
    out = out.replace(
      /import\s+\{([^}]+)\}\s*,\s*\{([^}]+)\}\s*\}\s*from\s*(["'][^"']+["'])/g,
      (_m, a: string, b: string, spec: string) =>
        `import { ${[a, b]
          .join(',')
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
          .join(', ')} } from ${spec}`,
    );
    changes.push('merged malformed duplicate named import groups');
  }

  if (/import\s+\{[^}]+\}\s*\}\s*from\s*["'][^"']+["']/.test(out)) {
    out = out.replace(/import\s+\{([^}]+)\}\s*\}\s*from\s*(["'][^"']+["'])/g, 'import { $1 } from $2');
    changes.push('removed extra brace from import statement');
  }

  if (/^\s*import\s+\{[^}]+\}\s+of_item\s*;.*$/m.test(out)) {
    out = out.replace(/^\s*import\s+\{[^}]+\}\s+of_item\s*;.*\r?\n?/gm, '');
    changes.push('removed hallucinated `of_item` import line');
  }

  // ---- 0b4c. Small token-level corruptions seen in generated sample data. ----
  if (/\[\s*\.{4,}/.test(out)) {
    out = out.replace(/\[\s*\.{4,}/g, '[...');
    changes.push('fixed over-repeated spread token');
  }
  if (/^\s*,\s*[A-Za-z_$][\w$]*\s*:/m.test(out)) {
    out = out.replace(/^(\s*),\s*([A-Za-z_$][\w$]*\s*:)/gm, '$1$2');
    changes.push('removed leading comma before object property');
  }

  if (/<\/CardDecision>/.test(out)) {
    out = out.replace(/<\/CardDecision>/g, '</CardDescription>');
    changes.push('fixed mistyped </CardDecision> closing tag');
  }

  if (/\b([A-Za-z_$][\w$]*)\.type\s*:/.test(out)) {
    out = out.replace(/\b([A-Za-z_$][\w$]*)\.type\s*:/g, '$1Type:');
    changes.push('fixed dotted object key ending in .type');
  }

  if (/\b([A-Za-z_$][\w$]*)\.\.\./.test(out)) {
    out = out.replace(/\b([A-Za-z_$][\w$]*)\.\.\./g, '$1');
    changes.push('removed accidental ellipsis after identifier');
  }

  if (/cn\(([^)]*),\s*_?color\s*:\s*([^)]+)\)/.test(out)) {
    out = out.replace(/cn\(([^)]*),\s*_?color\s*:\s*([^)]+)\)/g, 'cn($1, $2)');
    changes.push('fixed malformed cn(..., _color: value) fragment');
  }

  // ---- 0b5. Client-only hooks without "use client". usePathname / useState /
  //           useEffect / useRouter etc. require a Client Component; if the file
  //           uses one but has no "use client" directive, add it. ----
  if (
    (/\b(useState|useEffect|usePathname|useRouter|useSearchParams|useRef|useReducer|useContext|useLayoutEffect|useCallback|useMemo)\s*[(<]/.test(
      out,
    ) ||
      /\bon(?:Click|Change|Submit|Input|Blur|Focus|KeyDown|KeyUp|MouseEnter|MouseLeave)=/.test(
        out,
      )) &&
    !/^\s*["']use client["']/.test(out)
  ) {
    out = `"use client";\n\n` + out;
    changes.push('added missing "use client" directive');
  }

  // ---- 0b6. A top-level PascalCase component declared but NOT exported (the
  //           model writes `const Card = ...` then other files do
  //           `import { Card }` â†’ "Export Card doesn't exist"). Export any
  //           top-level PascalCase const not already exported some other way. ----
  {
    const exported: string[] = [];
    out = out.replace(/^const ([A-Z][A-Za-z0-9]*)(\s*[=:])/gm, (m, name, tail) => {
      if (new RegExp(`export\\b[^\\n]*\\b${name}\\b`).test(out)) return m;
      exported.push(name);
      return `export const ${name}${tail}`;
    });
    if (exported.length)
      changes.push(`exported unexported top-level component(s): ${exported.join(', ')}`);
  }

  // ---- 0b7. shadcn/ui component used in JSX but not imported (e.g. `<Card>`
  //           with no import â†’ "Card is not defined"). Add the import from the
  //           known pre-seeded path, grouped per module. ----
  {
    const imported = importedIdentifiers(out);
    const declared = locallyDeclared(out);
    const used = jsxTagsUsed(out);
    const byPath = new Map<string, string[]>();
    for (const tag of used) {
      const p = SHADCN_EXPORTS[tag];
      if (p && !imported.has(tag) && !declared.has(tag)) {
        const arr = byPath.get(p) ?? [];
        if (!arr.includes(tag)) arr.push(tag);
        byPath.set(p, arr);
      }
    }
    for (const [p, names] of byPath) {
      // Merge into an existing import from the same path if present.
      const re = new RegExp(`import\\s*\\{([^}]*)\\}\\s*from\\s*["']${p.replace(/[/\-]/g, '\\$&')}["']`);
      const m = out.match(re);
      if (m) {
        const existing = m[1].split(',').map((s) => s.trim()).filter(Boolean);
        const merged = Array.from(new Set([...existing, ...names])).join(', ');
        out = out.replace(re, `import { ${merged} } from "${p}"`);
      } else {
        out = addImport(out, `import { ${names.join(', ')} } from "${p}";`);
      }
      changes.push(`added missing shadcn import(s): ${names.join(', ')}`);
    }
  }

  // ---- 0c. cva imported under the wrong name. The model writes
  //          `import { variant } from "class-variance-authority"` and calls
  //          `variant(...)` â€” but the package exports `cva`, not `variant`, so
  //          the module fails to load and every component built on it (Button â†’
  //          Card â†’ every page) 500s. Rename ONLY the cva binding + its call
  //          sites (`variant(`), never the `variant` prop or variant keys. ----
  {
    const cvaImp = out.match(
      /import\s*\{([^}]*)\}\s*from\s*["']class-variance-authority["']/,
    );
    if (cvaImp && /\bvariant\b/.test(cvaImp[1]) && !/\bcva\b/.test(cvaImp[1])) {
      out = out.replace(cvaImp[0], cvaImp[0].replace(/\bvariant\b/, 'cva'));
      out = out.replace(/\bvariant\s*\(/g, 'cva(');
      changes.push('fixed cva import (was imported as "variant")');
    }
  }

  // ---- 0c2. Radix does not ship Card/Button/Badge/Input primitives. These are
  //           local shadcn/ui files in generated apps. Rewrite hallucinated
  //           Radix imports before dependency scanning tries to install them.
  const localPrimitiveImports: Record<string, string> = {
    '@radix-ui/react-card': '@/components/ui/card',
    '@radix-ui/react-button': '@/components/ui/button',
    '@radix-ui/react-badge': '@/components/ui/badge',
    '@radix-ui/react-input': '@/components/ui/input',
    '@radix-ui/react-textarea': '@/components/ui/textarea',
  };
  for (const [bad, good] of Object.entries(localPrimitiveImports)) {
    const re = new RegExp(`from\\s+["']${bad.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["']`, 'g');
    if (re.test(out)) {
      out = out.replace(re, `from "${good}"`);
      changes.push(`rewrote ${bad} import to ${good}`);
    }
  }

  // ---- 0d. `Link` is both a lucide icon name and the Next navigation
  //          component. In generated pages, `<Link href="...">` means
  //          next/link; importing it from lucide-react makes JSX invalid at
  //          runtime and often triggers an unnecessary LLM repair. Split it
  //          deterministically.
  {
    const li = lucideImport(out);
    if (li && li.names.includes('Link') && /<Link\b/.test(out)) {
      const kept = li.names.filter((name) => name !== 'Link');
      out =
        out.slice(0, li.start) +
        (kept.length ? `import { ${kept.join(', ')} } from "lucide-react"` : '') +
        out.slice(li.end);
      if (!/import\s+Link\s+from\s+["']next\/link["']/.test(out)) {
        out = addImport(out, `import Link from "next/link";`);
      }
      changes.push('moved Link import from lucide-react to next/link');
    }
    if (/<Link\b[^>]*\bto=/.test(out)) {
      out = out.replace(/<Link\b([^>]*?)\bto=/g, '<Link$1href=');
      changes.push('changed Link to= to href=');
    }
  }

  // ---- 1. Repair invalid lucide icon imports. The model frequently MISTYPES a
  //         real icon (Book_Open â†’ BookOpen, ShoppingcART â†’ ShoppingCart) or
  //         invents one outright. First try to map the typo back to the real
  //         icon (so the intended glyph survives); only if nothing matches do we
  //         fall back to a generic icon so the app still compiles. ----
  if (valid.size) {
    const li = lucideImport(out);
    if (li) {
      for (const name of li.names) {
        if (!valid.has(name)) {
          const fixed = nearestIcon(name, valid) ?? FALLBACK_ICON;
          out = out.replace(new RegExp(`\\b${name}\\b`, 'g'), fixed);
          changes.push(
            fixed === FALLBACK_ICON
              ? `hallucinated icon ${name} â†’ ${FALLBACK_ICON}`
              : `mistyped icon ${name} â†’ ${fixed}`,
          );
        }
      }
    }
  }

  // ---- 1b. Repair lucide icon references used as object values, not JSX tags:
  //          `{ icon: StarIcon }` fails TypeScript if StarIcon was never
  //          imported. Map common `*Icon` suffixes back to the real lucide name.
  if (valid.size) {
    const imported = importedIdentifiers(out);
    const declared = locallyDeclared(out);
    for (const name of iconValuesUsed(out)) {
      if (valid.has(name) || imported.has(name) || declared.has(name)) continue;
      const fixed = nearestIcon(name, valid) ?? FALLBACK_ICON;
      out = out.replace(new RegExp(`\\b${name}\\b`, 'g'), fixed);
      changes.push(
        fixed === FALLBACK_ICON
          ? `unknown icon value ${name} -> ${FALLBACK_ICON}`
          : `fixed icon value ${name} -> ${fixed}`,
      );
    }
  }

  // ---- 2. Add missing lucide icon imports (valid icon used in JSX, not imported).
  //         CRUCIAL: skip names the file DECLARES locally (function/const X) â€”
  //         the model often defines a local <Plus>/<CalendarIcon> helper, and
  //         importing the lucide icon of the same name makes it "defined multiple
  //         times". Only import a tag that is neither imported NOR declared. ----
  if (valid.size) {
    const imported = importedIdentifiers(out);
    const declared = locallyDeclared(out);
    const used = new Set([...jsxTagsUsed(out), ...iconValuesUsed(out)]);
    const missing: string[] = [];
    for (const tag of used) {
      if (
        valid.has(tag) &&
        !imported.has(tag) &&
        !declared.has(tag) &&
        tag !== FALLBACK_ICON
      )
        missing.push(tag);
    }
    // Also ensure the fallback icon is imported if we introduced it above.
    if (
      out.includes(`<${FALLBACK_ICON}`) &&
      !imported.has(FALLBACK_ICON) &&
      !declared.has(FALLBACK_ICON)
    ) {
      if (!missing.includes(FALLBACK_ICON)) missing.push(FALLBACK_ICON);
    }
    if (missing.length) {
      const li = lucideImport(out);
      if (li) {
        // Merge into the existing lucide import.
        const merged = Array.from(new Set([...li.names, ...missing])).join(', ');
        out =
          out.slice(0, li.start) +
          `import { ${merged} } from "lucide-react"` +
          out.slice(li.end);
      } else {
        // No lucide import yet â€” add one after the last top import.
        out = addImport(out, `import { ${missing.join(', ')} } from "lucide-react";`);
      }
      changes.push(`added missing icon import(s): ${missing.join(', ')}`);
    }
  }

  // ---- 3. Add missing cn import (cn(...) used but not imported). Skip files
  //         that DECLARE cn themselves (e.g. lib/utils.ts). ----
  if (
    /\bcn\s*\(/.test(out) &&
    !importedIdentifiers(out).has('cn') &&
    !/(?:function|const|let|var)\s+cn\b/.test(out)
  ) {
    out = addImport(out, `import { cn } from "@/lib/utils";`);
    changes.push('added missing cn import');
  }

  if (/<Button\b[^>]*\bhref=/.test(out)) {
    out = out.replace(
      /<Button\b([^>]*)\bhref=(["'][^"']+["']|\{[^}]+\})([^>]*)>([\s\S]*?)<\/Button>/g,
      (m, before: string, href: string, after: string, children: string) => {
        if (/\basChild\b/.test(before) || /\basChild\b/.test(after)) return m;
        return `<Button${before}${after} asChild><a href=${href}>${children}</a></Button>`;
      },
    );
    changes.push('wrapped Button href usage with asChild anchor');
  }

  // ---- 3b. Strip a hallucinated `new URL(...)._parse` statement. URL has no
  //          `_parse` member, so destructuring it throws at runtime. The model
  //          emits this then writes the correct line right after, so deleting
  //          the broken one is safe. ----
  if (/\bnew\s+URL\([^)]*\)\._parse\b/.test(out)) {
    out = out
      .split('\n')
      .filter((l) => !/=\s*new\s+URL\([^)]*\)\._parse\b/.test(l))
      .join('\n');
    changes.push('removed invalid new URL(...)._parse statement');
  }

  // ---- 3c. Underscore-typo call: the model declares `function loadData()` but
  //          calls `_loadData()` (a stray underscore), throwing "_loadData is
  //          not defined". If the underscore-stripped name IS declared and the
  //          underscored one is NOT, fix the call site. ----
  {
    const declared = declaredIdentifiers(out);
    const byNormalized = new Map<string, string>();
    for (const name of declared) byNormalized.set(normalizeIdentifier(name), name);
    const callRe = /\b_([A-Za-z$][\w$]*)\s*\(/g;
    const renames = new Map<string, string>();
    let c: RegExpExecArray | null;
    while ((c = callRe.exec(out))) {
      const base = c[1];
      if (declared.has(base) && !declared.has('_' + base)) renames.set(`_${base}`, base);
    }
    const snakeCallRe = /\b([A-Za-z_$][\w$]*_[A-Za-z_$][\w$]*)\s*\(/g;
    while ((c = snakeCallRe.exec(out))) {
      const bad = c[1];
      const good = byNormalized.get(normalizeIdentifier(bad));
      if (good && good !== bad) renames.set(bad, good);
    }
    for (const [bad, good] of renames) {
      out = out.replace(new RegExp(`\\b${bad}\\s*\\(`, 'g'), `${good}(`);
      changes.push(`fixed undefined call ${bad}() -> ${good}()`);
    }
  }

  // ---- 4. mongoose Schema used as a value but not imported. Models often do
  //         `import mongoose from "mongoose"` then `new Schema(...)`, which
  //         throws "Schema is not defined" at module load. ----
  if (
    /\bnew\s+Schema\b|\bSchema\s*\(/.test(out) &&
    !importedIdentifiers(out).has('Schema')
  ) {
    const m = out.match(
      /import\s+mongoose\s*(?:,\s*\{([^}]*)\})?\s*from\s*["']mongoose["'][^\n]*/,
    );
    if (m) {
      const names = (m[1] ? m[1].split(',').map((s) => s.trim()) : []).filter(Boolean);
      if (!names.includes('Schema')) names.push('Schema');
      out = out.replace(m[0], `import mongoose, { ${names.join(', ')} } from "mongoose"`);
      changes.push('added missing Schema import from mongoose');
    } else if (!/from\s*["']mongoose["']/.test(out)) {
      out = addImport(out, `import mongoose, { Schema } from "mongoose";`);
      changes.push('added mongoose + Schema import');
    }
  }

  return { content: out, changes };
}

/** Insert an import line after the existing import block (or after "use client"). */
function addImport(src: string, line: string): string {
  const lines = src.split('\n');
  // Insert at the TOP â€” after a leading "use client" directive (which MUST stay
  // first) and any blank line after it. Inserting before all existing imports is
  // always valid and, crucially, never splits a MULTI-LINE import (the old
  // line-by-line scan inserted in the middle of `import {\n  A,\n  B\n} from`,
  // corrupting the file).
  let insertAt = 0;
  if (lines.length && /^\s*["']use client["'];?\s*$/.test(lines[0])) {
    insertAt = 1;
    while (insertAt < lines.length && lines[insertAt].trim() === '') insertAt++;
  }
  lines.splice(insertAt, 0, line);
  return lines.join('\n');
}

/** Find the shared nav component file (Navbar preferred, then Sidebar/Header). */
async function findNavComponent(
  root: string,
): Promise<{ rel: string; importName: string; isDefault: boolean } | null> {
  const compDir = path.join(root, 'components');
  const candidates: string[] = [];
  async function walk(dir: string): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) await walk(full);
      else if (/(navbar|sidebar|header|topbar|^nav)\.(tsx|jsx)$/i.test(e.name))
        candidates.push(full);
    }
  }
  await walk(compDir);
  if (!candidates.length) return null;
  // Prefer a navbar, then sidebar, then anything.
  const rank = (f: string) =>
    /navbar/i.test(f) ? 0 : /sidebar/i.test(f) ? 1 : /header|topbar/i.test(f) ? 2 : 3;
  candidates.sort((a, b) => rank(a) - rank(b));
  const file = candidates[0];
  let content = '';
  try {
    content = await fs.readFile(file, 'utf8');
  } catch {
    return null;
  }
  const exps = extractExports(content);
  const def = exps.find((e) => e.startsWith('default'));
  const named = exps.find((e) => /^[A-Z]/.test(e) && !e.startsWith('default'));
  const isDefault = !!def;
  const m = def?.match(/default \((\w+)\)/);
  const importName = m?.[1] || named || 'Navbar';
  const rel =
    '@/' + path.relative(root, file).replace(/\\/g, '/').replace(/\.(tsx|jsx)$/, '');
  return { rel, importName, isDefault };
}

/** Minimal export-name extractor (mirrors fs.ts) for the nav-wiring pass. */
function extractExports(content: string): string[] {
  const names = new Set<string>();
  const def = content.match(/export\s+default\s+(?:async\s+)?(?:function|class)\s+(\w+)/);
  if (def) names.add(`default (${def[1]})`);
  else if (/export\s+default\b/.test(content)) names.add('default');
  for (const re of [/export\s+const\s+(\w+)/g, /export\s+(?:async\s+)?function\s+(\w+)/g]) {
    let m: RegExpExecArray | null;
    while ((m = re.exec(content))) names.add(m[1]);
  }
  return [...names];
}

/** Wire the shared nav into app/layout.tsx when it renders none. */
async function wireLayoutNav(root: string): Promise<string | null> {
  const layoutPath = path.join(root, 'app', 'layout.tsx');
  let layout: string;
  try {
    layout = await fs.readFile(layoutPath, 'utf8');
  } catch {
    return null;
  }
  // Already renders something from components? Leave it alone.
  if (/from\s+["']@\/components\//.test(layout)) return null;
  if (!/\{\s*children\s*\}/.test(layout) || !/<body[\s>]/.test(layout)) return null;

  const nav = await findNavComponent(root);
  if (!nav) return null;

  const importLine = nav.isDefault
    ? `import ${nav.importName} from "${nav.rel}";`
    : `import { ${nav.importName} } from "${nav.rel}";`;
  let out = addImport(layout, importLine);
  // Render the nav immediately inside <body>, before the rest.
  out = out.replace(/(<body[^>]*>)/, `$1\n        <${nav.importName} />`);
  if (out === layout) return null;
  await fs.writeFile(layoutPath, out, 'utf8');
  return `app/layout.tsx: wired <${nav.importName}/> into the layout (was rendering no navigation)`;
}

async function collectSourceFiles(root: string): Promise<Array<{ rel: string; full: string; content: string }>> {
  const out: Array<{ rel: string; full: string; content: string }> = [];

  async function walk(dir: string): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (e.name === 'node_modules' || e.name === '.next' || e.name === '_plans') continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        await walk(full);
        continue;
      }
      if (!SRC_EXT.some((x) => e.name.endsWith(x))) continue;
      try {
        out.push({
          rel: path.relative(root, full).replace(/\\/g, '/'),
          full,
          content: await fs.readFile(full, 'utf8'),
        });
      } catch {
        /* skip unreadable files */
      }
    }
  }

  for (const d of ['app', 'components', 'lib']) await walk(path.join(root, d));
  return out;
}

function ensureMongooseDefaultImport(src: string): { content: string; changed: boolean } {
  if (/import\s+mongoose\b[^;]*from\s*["']mongoose["']/.test(src)) {
    return { content: src, changed: false };
  }
  const named = src.match(/import\s*\{([^}]*)\}\s*from\s*["']mongoose["'];?/);
  if (named) {
    return {
      content: src.replace(named[0], `import mongoose, { ${named[1].trim()} } from "mongoose";`),
      changed: true,
    };
  }
  return {
    content: addImport(src, 'import mongoose from "mongoose";'),
    changed: true,
  };
}

async function ensureMissingModelExports(root: string): Promise<string[]> {
  const files = await collectSourceFiles(root);
  const requests = new Map<string, Set<string>>();
  const importRe =
    /import\s*\{([^}]+)\}\s*from\s*["']@\/lib\/models\/([^"']+)["']/g;

  for (const file of files) {
    if (file.rel.startsWith('lib/models/')) continue;
    let m: RegExpExecArray | null;
    while ((m = importRe.exec(file.content))) {
      const moduleRel = `lib/models/${m[2].replace(/\.ts$/, '')}.ts`;
      const names = m[1]
        .split(',')
        .map((part) => part.trim().split(/\s+as\s+/)[0].trim())
        .filter((name) => /^[A-Z][A-Za-z0-9]*$/.test(name));
      if (!names.length) continue;
      const set = requests.get(moduleRel) ?? new Set<string>();
      for (const name of names) set.add(name);
      requests.set(moduleRel, set);
    }
  }

  const applied: string[] = [];
  for (const [moduleRel, names] of requests) {
    const full = path.join(root, moduleRel);
    let src: string;
    try {
      src = await fs.readFile(full, 'utf8');
    } catch {
      continue;
    }
    const existing = new Set(extractExports(src));
    const missing = [...names].filter((name) => !existing.has(name));
    if (!missing.length) continue;

    const importFix = ensureMongooseDefaultImport(src);
    let out = importFix.content;
    for (const name of missing) {
      if (new RegExp(`\\b${name}\\b`).test(out) && new RegExp(`export\\s+const\\s+${name}\\b`).test(out)) {
        continue;
      }
      const schemaName = `${lowerCamel(name)}AutofixSchema`;
      out += `\n\nconst ${schemaName} = new mongoose.Schema({}, { strict: false, timestamps: true });\nexport const ${name} = mongoose.models.${name} || mongoose.model("${name}", ${schemaName});\n`;
      applied.push(`${moduleRel}: added missing model export ${name}`);
    }

    if (out !== src) await fs.writeFile(full, out, 'utf8');
  }

  return applied;
}

/**
 * Sweep every generated source file under app/ and components/ and repair the
 * mechanical issues above. Returns a list of human-readable fixes applied.
 */
/**
 * SCOPED autofix: repair only the given files. Used by the per-build-step
 * quality gate so its cost stays CONSTANT instead of re-sweeping the whole
 * (growing) project on every one of ~55 steps — the O(steps x files) blowup
 * that made big builds crawl once they passed ~100 files. The final
 * autofixProject() pass still sweeps everything, so nothing is missed.
 */
export async function autofixFiles(id: string, rels: string[]): Promise<string[]> {
  const root = projectDir(id);
  const applied: string[] = [];
  for (const rel of rels) {
    const norm = rel.replace(/\\/g, '/');
    if (!SRC_EXT.some((x) => norm.endsWith(x))) continue;
    if (isProtectedPath(norm)) continue;
    const full = path.join(root, norm);
    let src: string;
    try {
      src = await fs.readFile(full, 'utf8');
    } catch {
      continue;
    }
    const { content, changes } = await autofixContent(src);
    if (changes.length && content !== src) {
      await fs.writeFile(full, content, 'utf8');
      for (const c of changes) applied.push(`${norm}: ${c}`);
    }
  }
  return applied;
}

export async function autofixProject(id: string): Promise<string[]> {
  const root = projectDir(id);
  const applied: string[] = [];

  async function walk(dir: string): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (e.name === 'node_modules' || e.name === '.next' || e.name === '_plans') continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        // Never touch the pre-seeded, correct shadcn primitives.
        if (full.replace(/\\/g, '/').endsWith('components/ui')) continue;
        await walk(full);
        continue;
      }
      if (!SRC_EXT.some((x) => e.name.endsWith(x))) continue;
      let src: string;
      try {
        src = await fs.readFile(full, 'utf8');
      } catch {
        continue;
      }
      const { content, changes } = await autofixContent(src);
      if (changes.length && content !== src) {
        await fs.writeFile(full, content, 'utf8');
        const rel = path.relative(root, full).replace(/\\/g, '/');
        for (const c of changes) applied.push(`${rel}: ${c}`);
      }
    }
  }

  await walk(path.join(root, 'app'));
  await walk(path.join(root, 'components'));
  await walk(path.join(root, 'lib'));

  applied.push(...(await ensureMissingModelExports(root)));

  // Project-level: ensure the root layout actually renders the shared nav. The
  // model sometimes builds a Navbar/Sidebar component but writes an app/layout
  // that only renders {children} â€” leaving every page with no navigation (the
  // recurring "no navbar" bug). If a nav component exists and the layout does
  // not render any component from @/components, wire it in.
  const navFix = await wireLayoutNav(root);
  if (navFix) applied.push(navFix);

  return applied;
}
