/**
 * Runtime terminal bug-fixer.
 *
 * Instead of running slow, speculative LLM repair loops *after* generation, the
 * builder now fixes real bugs the way a developer does: it starts the generated
 * app's dev server, walks the site page-by-page (which is what makes Next.js
 * lazily compile each route), reads the errors the dev-server terminal prints,
 * and fixes ONLY what the terminal complains about:
 *
 *   • a missing library  → run `npm install <pkg>` in the project,
 *   • a code error        → hand the ONE erroring file + its exact error to
 *                           Gemma and write back a minimally-corrected file.
 *
 * This module holds the pure pieces (error parsing, package install, one-file
 * Gemma repair, route discovery). The orchestration loop that drives a live
 * preview lives in ./manager.ts, which owns the child process + log buffer.
 */

import { spawn } from 'child_process';
import { promises as fs } from 'fs';
import path from 'path';
import { builtinModules } from 'module';
import {
  projectDir,
  readProjectFile,
  readProjectFiles,
  writeProjectFileRaw,
  isProtectedPath,
} from '../workspace/fs';
import {
  streamOllamaChat,
  OLLAMA_CODE_MODEL,
  type ChatMessage,
} from '../llm/ollama';
import { autofixFiles } from '../build/autofix';

const NODE_BUILTINS = new Set([
  ...builtinModules,
  ...builtinModules.map((m) => `node:${m}`),
]);

// Framework packages that are ALWAYS installed by the scaffold — a
// module-not-found on one of their subpaths is a wrong-import code bug, never a
// missing package to install (npm install next/next is nonsense).
const NEVER_INSTALL = new Set(['next', 'react', 'react-dom']);

export type RuntimeErrorKind =
  | 'missing-package'
  | 'missing-module'
  | 'syntax'
  | 'runtime'
  | 'unknown';

export interface RuntimeError {
  kind: RuntimeErrorKind;
  file?: string; // project-relative, e.g. "app/admin/page.tsx"
  line?: number;
  spec?: string; // unresolved import specifier (for missing-package/module)
  message: string;
  signature: string; // dedupe key
}

const SOURCE_DIR =
  '(?:src/)?(?:app|components|lib|hooks|pages|context|contexts|providers|store|stores|utils|types|styles|config)';
// A source-file reference, optionally suffixed with :line:col. Matched AFTER the
// absolute workspace prefix has been stripped, so it anchors on the app-relative
// path even when the terminal printed an absolute Windows path.
const FILE_RE = new RegExp(
  `(?:\\./)?(${SOURCE_DIR}/[^\\s:?)'"\`\\]]+\\.(?:tsx?|jsx?|css|mjs|cjs))(?::(\\d+))?(?::\\d+)?`,
);

// Turbopack/SWC compile-error message phrases that appear on the line AFTER a
// "<path>:line:col" header (so they carry no path of their own).
const COMPILE_ERROR_RE =
  /(defined multiple times|has already been declared|is not defined|Cannot find name|Cannot find module|Unexpected (?:token|eof|reserved)|Expected .*?,? ?got|Unterminated|Unknown word|Ecmascript file had an error|Parsing ecmascript source code failed|export .* was not found|is not exported|JSX element .* has no corresponding closing tag|Return statement is not allowed here)/i;

/** Is this import specifier an installable npm package (not a local/alias path)? */
export function looksLikePackage(spec: string): boolean {
  if (!spec) return false;
  if (/^[.#/]/.test(spec)) return false; // ./  ../  /  #alias
  if (spec.startsWith('@/')) return false; // project path alias
  if (spec.endsWith('.css') || spec.endsWith('.json')) return false;
  if (NODE_BUILTINS.has(spec)) return false;
  const name = spec.startsWith('@') ? spec.split('/').slice(0, 2).join('/') : spec.split('/')[0];
  if (NODE_BUILTINS.has(name)) return false;
  if (name.startsWith('@')) return /^@[a-z0-9._~-]+\/[a-z0-9._~-]+$/.test(name);
  return /^[a-z0-9._~-]+$/.test(name);
}

function packageName(spec: string): string {
  return spec.startsWith('@') ? spec.split('/').slice(0, 2).join('/') : spec.split('/')[0];
}

/** Strip the absolute workspace prefix so paths become project-relative. */
function relativize(line: string, root: string): string {
  const fwd = line.replace(/\\/g, '/');
  const rootFwd = root.replace(/\\/g, '/');
  return fwd.split(rootFwd + '/').join('').split(rootFwd).join('');
}

function fileFrom(line: string): { file?: string; line?: number } {
  const m = FILE_RE.exec(line);
  if (!m) return {};
  return { file: m[1].replace(/^\.\//, ''), line: m[2] ? Number(m[2]) : undefined };
}

/**
 * Parse a slice of dev-server terminal output into structured errors. `logs`
 * is expected to already have ANSI codes stripped (manager.pushLog does that).
 * `root` is the project directory so absolute paths can be relativized.
 */
export function parseDevErrors(logs: string[], root: string): RuntimeError[] {
  const out: RuntimeError[] = [];
  const seen = new Set<string>();
  const lines = logs.map((l) => relativize(l, root));

  // Track the most recent source-file reference so an error line that names no
  // file (e.g. a bare "Module not found") can be attributed to it.
  let lastFile: string | undefined;
  let lastLine: number | undefined;

  const push = (e: RuntimeError) => {
    if (seen.has(e.signature)) return;
    seen.add(e.signature);
    out.push(e);
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trim();
    if (!line) continue;

    const ff = fileFrom(line);
    if (ff.file) {
      lastFile = ff.file;
      lastLine = ff.line ?? lastLine;
    }

    // 1) Module not found — the single most common generated-app failure.
    const mnf =
      line.match(/Can't resolve ['"]([^'"]+)['"]/) ||
      line.match(/Cannot find module ['"]([^'"]+)['"]/) ||
      line.match(/Module not found:.*['"]([^'"]+)['"]/);
    if (mnf) {
      const spec = mnf[1];
      const file = ff.file || lastFile;
      // A module-not-found on a SUBPATH of an already-installed framework
      // package (next/next, react/foo) is a wrong-import CODE bug, never an
      // install — the base is present; the subpath is hallucinated.
      const base = packageName(spec);
      const frameworkSubpath = spec.includes('/') && NEVER_INSTALL.has(base);
      const isPkg = looksLikePackage(spec) && !frameworkSubpath;
      push({
        kind: isPkg ? 'missing-package' : 'missing-module',
        spec,
        file,
        line: ff.line ?? lastLine,
        message: `Module not found: Can't resolve '${spec}'`,
        signature: `mnf:${spec}`,
      });
      continue;
    }

    // 2) SWC parse/syntax errors carry a ",-[<abs path>:<line>:<col>]" marker.
    const swc = raw.match(/,-\[([^\]]+?):(\d+):\d+\]/);
    if (swc) {
      const file = fileFrom(swc[1].replace(/\\/g, '/')).file || lastFile;
      // The human message is usually the "x <msg>" line just above the marker.
      const msg =
        [lines[i - 1], lines[i - 2]]
          .map((l) => (l || '').trim())
          .find((l) => /^(x |Error|Expected|Unexpected|Unterminated)/i.test(l)) ||
        'Syntax error';
      if (file) {
        push({
          kind: 'syntax',
          file,
          line: Number(swc[2]),
          message: msg.replace(/^x\s*/, ''),
          signature: `syntax:${file}:${swc[2]}`,
        });
      }
      continue;
    }

    // 2b) Turbopack CSS errors (a stray "```css" fence, a bad token) — every
    //     route 500s off app/globals.css. Route to a deterministic fix, never
    //     an LLM (CSS mistakes here are almost always a wrapping fence).
    if (/CssSyntaxError|postcss/i.test(line)) {
      const file = ff.file || lastFile;
      if (file && /\.css$/.test(file)) {
        push({
          kind: 'syntax',
          file,
          line: ff.line ?? lastLine,
          message: line.replace(/^.*?CssSyntaxError:\s*/, 'CssSyntaxError: ').slice(0, 240),
          signature: `css:${file}`,
        });
        continue;
      }
    }

    // 2c) Turbopack/SWC compile errors printed as a "<path>:line:col" header
    //     line (often "[browser] ./…") followed by the message on the NEXT
    //     line: "the name `x` is defined multiple times", "x is not defined",
    //     "has already been declared", etc. These don't match the ,-[…] shape.
    if (COMPILE_ERROR_RE.test(line) && lastFile) {
      push({
        kind: 'syntax',
        file: lastFile,
        line: lastLine,
        message: line.replace(/^x\s*/, '').slice(0, 240),
        signature: `syntax:${lastFile}`,
      });
      continue;
    }

    // 3) Runtime exceptions surfaced on request (ReferenceError, TypeError, …).
    const runtime = line.match(
      /\b(ReferenceError|TypeError|SyntaxError|RangeError|Error):\s*(.+)$/,
    );
    if (runtime && !/Module not found/.test(line)) {
      // Prefer a project-owned stack frame for the file, if one follows.
      let file = ff.file || lastFile;
      let atLine = ff.line ?? lastLine;
      for (let j = i + 1; j < Math.min(i + 12, lines.length); j++) {
        const at = lines[j].match(/\bat\b.*\(?([^\s(]+\.(?:tsx?|jsx?|mjs|cjs)):(\d+):\d+/);
        if (at) {
          const ff2 = fileFrom(at[1]);
          if (ff2.file) {
            file = ff2.file;
            atLine = Number(at[2]);
            break;
          }
        }
      }
      if (file) {
        push({
          kind: 'runtime',
          file,
          line: atLine,
          message: `${runtime[1]}: ${runtime[2]}`.slice(0, 300),
          signature: `runtime:${file}:${runtime[1]}:${runtime[2].slice(0, 60)}`,
        });
      }
      continue;
    }
  }

  return out;
}

/**
 * Robust, format-agnostic fallback: collect every project-owned source file
 * mentioned anywhere in an error log slice (import traces, stack frames, header
 * lines). When precise error parsing misses a Turbopack/SWC format, we still
 * know WHICH files the failing route touched, and can hand each to Gemma with
 * the raw error text. Excludes node_modules/.next noise.
 */
export function collectErrorFiles(logs: string[], root: string): string[] {
  const files = new Set<string>();
  const re = new RegExp(FILE_RE.source, 'g');
  for (const raw of logs) {
    const line = relativize(raw, root);
    if (line.includes('node_modules') || line.includes('.next/')) continue;
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line))) {
      const f = m[1].replace(/^\.\//, '');
      if (/\.(tsx?|jsx?|css)$/.test(f)) files.add(f);
    }
  }
  return [...files];
}

/** The tail of a log slice that carries the actual error text, for LLM context. */
export function errorContext(logs: string[]): string[] {
  return logs.map((l) => l.trim()).filter(Boolean).slice(-40);
}

/**
 * A single API route importing a model that does NOT exist (e.g. a hallucinated
 * `@/lib/models/gallery` for static content) is a HARD Turbopack compile error
 * that fails the whole API graph and cascades 500s to EVERY other API route —
 * seen live: one broken route 500'd 22 otherwise-valid routes. Gemma can't fix a
 * "model that isn't there". So find any app/api route importing a non-existent
 * lib/models/<name> and stub it (GET → apiSuccess([])) to un-poison the graph;
 * its page just renders an empty state. Returns the paths stubbed.
 */
export async function fixMissingModelRoutes(
  id: string,
  onLog: (line: string) => void,
): Promise<string[]> {
  const files = await readProjectFiles(id);
  const modelNames = new Set(
    files
      .filter((f) => /^lib\/models\/.+\.ts$/.test(f.path) && f.path !== 'lib/models/index.ts')
      .map((f) => f.path.replace(/^lib\/models\//, '').replace(/\.ts$/, '').toLowerCase()),
  );
  const importRe = /from\s*["']@\/lib\/models\/([a-z0-9_-]+)["']/gi;
  const fixed: string[] = [];
  for (const f of files) {
    if (!/^app\/api\/.+route\.ts$/.test(f.path)) continue;
    let broken = false;
    importRe.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = importRe.exec(f.content))) {
      if (!modelNames.has(m[1].toLowerCase())) {
        broken = true;
        break;
      }
    }
    if (!broken) continue;
    const stub =
      `import { apiSuccess } from "@/lib/api/response";\n\n` +
      `// Auto-stubbed: this route imported a model that does not exist.\n` +
      `export async function GET() {\n  return apiSuccess([]);\n}\n`;
    await writeProjectFileRaw(id, f.path, stub);
    fixed.push(f.path);
  }
  if (fixed.length) {
    onLog(`[autofix] stubbed ${fixed.length} route(s) importing a non-existent model: ${fixed.join(', ')}`);
  }
  return fixed;
}

/**
 * Decomposition (thin page + components/<slug>/ sections) sometimes imports a
 * section from the WRONG path (e.g. `@/components/book-table` when the file is
 * `components/admin-books/book-table.tsx`) or imports a section the model FORGOT
 * to write. Either is a "Module not found" that poisons the whole graph and
 * 500s every route. Fix by: (1) remapping the import to the real file if a
 * unique match exists, (2) otherwise creating a stub so the import resolves and
 * the cascade clears (that one section renders empty; the rest of the app works).
 */
export async function fixComponentImports(
  id: string,
  onLog: (line: string) => void,
): Promise<string[]> {
  const files = await readProjectFiles(id);
  const existing = new Set(files.map((f) => f.path));
  const resolves = (p: string) =>
    ['.tsx', '.ts', '.jsx', '.js'].some((e) => existing.has(p + e)) ||
    existing.has(p + '/index.tsx') ||
    existing.has(p + '/index.ts');
  const byBase = new Map<string, string>();
  const dup = new Set<string>();
  for (const f of files) {
    const m = f.path.match(/^(components\/.+)\.(?:tsx|ts|jsx|js)$/);
    if (!m || f.path.startsWith('components/ui/')) continue;
    const base = m[1].split('/').pop() as string;
    if (byBase.has(base)) dup.add(base);
    else byBase.set(base, m[1]);
  }
  const importRe =
    /import\s+(?:(\w+)|\{([^}]*)\})\s+from\s+(["'])@\/(components\/[A-Za-z0-9_/-]+)\3/g;
  const changedFiles = new Set<string>();
  const stubs: Array<[string, string]> = [];
  for (const f of files) {
    if (!/\.(?:tsx|ts|jsx|js)$/.test(f.path) || f.path.startsWith('components/ui/')) continue;
    let changed = false;
    const content = f.content.replace(importRe, (full, def, named, _q, path) => {
      if (resolves(path)) return full;
      const base = path.split('/').pop() as string;
      if (byBase.has(base) && !dup.has(base)) {
        changed = true;
        return full.replace('@/' + path, '@/' + byBase.get(base));
      }
      const stubPath = path + '.tsx';
      if (!existing.has(stubPath)) {
        const names: string[] = def
          ? [def]
          : String(named)
              .split(',')
              .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
              .filter(Boolean);
        const body = (names.length ? names : ['Stub'])
          .map((n) =>
            def
              ? `export default function ${n}() {\n  return null;\n}`
              : `export function ${n}() {\n  return null;\n}`,
          )
          .join('\n\n');
        stubs.push([stubPath, `"use client";\n\n${body}\n`]);
        existing.add(stubPath);
      }
      return full;
    });
    if (changed) {
      await writeProjectFileRaw(id, f.path, content);
      changedFiles.add(f.path);
    }
  }
  for (const [p, c] of stubs) {
    await writeProjectFileRaw(id, p, c);
    changedFiles.add(p);
  }
  if (changedFiles.size) {
    onLog(`[autofix] fixed ${changedFiles.size} missing/mis-pathed component import(s): ${[...changedFiles].slice(0, 6).join(', ')}`);
  }
  return [...changedFiles];
}

/**
 * A page links (href / router.push) to a route that has no page.tsx → clicking
 * it 404s ("api route works but the page errors when you use it"). The model
 * does this despite the prompt. Create a minimal stub page for each referenced
 * route that doesn't exist so the link resolves. Only STATIC string routes are
 * considered (a `/books/${id}` template is dynamic and matches its [id] route).
 */
export async function fixDeadInternalLinks(
  id: string,
  onLog: (line: string) => void,
): Promise<string[]> {
  const files = await readProjectFiles(id);
  const paths = new Set(files.map((f) => f.path));
  const pageRoutes: string[] = [];
  for (const f of files) {
    if (f.path === 'app/page.tsx') pageRoutes.push('/');
    const m = f.path.match(/^app\/(.+)\/page\.(?:tsx|ts|jsx|js)$/);
    if (m) pageRoutes.push('/' + m[1]);
  }
  const matchesExisting = (r: string): boolean => {
    if (pageRoutes.includes(r)) return true;
    return pageRoutes.some((p) =>
      new RegExp('^' + p.replace(/[.*+?^${}()|]/g, '\\$&').replace(/\\\[[^\]]+\\\]/g, '[^/]+') + '$').test(r),
    );
  };
  const referenced = new Set<string>();
  const re = /(?:href=|router\.(?:push|replace)\()\s*["'`](\/[A-Za-z0-9_/-]*)["'`]/g;
  for (const f of files) {
    if (!/\.(?:tsx|ts|jsx|js)$/.test(f.path)) continue;
    let m: RegExpExecArray | null;
    re.lastIndex = 0;
    while ((m = re.exec(f.content))) {
      const r = (m[1].replace(/\/+$/, '') || '/');
      if (r === '/' || r.startsWith('/api')) continue;
      referenced.add(r);
    }
  }
  const created: string[] = [];
  for (const r of referenced) {
    if (matchesExisting(r)) continue;
    const filePath = `app/${r.replace(/^\//, '')}/page.tsx`;
    if (paths.has(filePath) || created.includes(filePath)) continue;
    const title = (r.split('/').filter(Boolean).pop() || 'page').replace(/-/g, ' ');
    const stub =
      `export default function Page() {\n` +
      `  return (\n` +
      `    <div className="container mx-auto py-20 text-center">\n` +
      `      <h1 className="text-2xl font-bold capitalize">${title}</h1>\n` +
      `      <p className="mt-2 text-muted">This page is coming soon.</p>\n` +
      `    </div>\n` +
      `  );\n}\n`;
    await writeProjectFileRaw(id, filePath, stub);
    created.push(filePath);
  }
  if (created.length) {
    onLog(`[autofix] created ${created.length} stub page(s) for dead internal links: ${created.slice(0, 6).join(', ')}`);
  }
  return created;
}

/** Run `npm install <pkgs>` in the project. Resolves to true on exit code 0. */
export function installPackages(
  id: string,
  pkgs: string[],
  onLog: (line: string) => void,
): Promise<boolean> {
  const unique = [...new Set(pkgs.map(packageName))].filter(Boolean);
  if (!unique.length) return Promise.resolve(true);
  return new Promise((resolve) => {
    onLog(`[autofix] installing missing package(s): ${unique.join(', ')}`);
    const proc = spawn(
      `npm install --legacy-peer-deps --no-audit --no-fund ${unique.join(' ')}`,
      { cwd: projectDir(id), shell: true, env: { ...process.env } },
    );
    proc.stdout?.on('data', (d) => onLog(d.toString()));
    proc.stderr?.on('data', (d) => onLog(d.toString()));
    proc.on('exit', (code) => {
      onLog(`[autofix] npm install exited (code ${code})`);
      resolve(code === 0);
    });
    proc.on('error', (e) => {
      onLog(`[autofix] npm install error: ${e.message}`);
      resolve(false);
    });
  });
}

/** Strip a wrapping markdown code fence the model left around a whole file. */
export function stripMarkdownFences(content: string): string {
  const isFence = (s: string) => /^`{3,}[a-zA-Z0-9_-]*\s*$/.test(s.trim());
  const lines = content.split('\n');
  let changed = false;
  while (lines.length && (isFence(lines[0]) || lines[0].trim() === '')) {
    if (isFence(lines[0])) changed = true;
    lines.shift();
  }
  while (
    lines.length &&
    (isFence(lines[lines.length - 1]) || lines[lines.length - 1].trim() === '')
  ) {
    if (isFence(lines[lines.length - 1])) changed = true;
    lines.pop();
  }
  return changed ? lines.join('\n') + '\n' : content;
}

/**
 * Fix the CSS mistakes local models make that fail Turbopack's PostCSS parse
 * (and thus 500 EVERY route via globals.css). Both are pure syntax repairs:
 *   var(--color-primary/0.1) → var(--color-primary)   (Tailwind opacity-slash
 *     is not valid inside a raw var(); "Unexpected token Delim('/')")
 *   --tw-theme_--color-x     → --color-x              (a bogus token prefix the
 *     model invents; the un-prefixed token is the real one written in @theme)
 */
function fixCssSyntax(css: string): string {
  return css
    .replace(/var\(\s*(--[A-Za-z0-9_-]+)\s*\/\s*[0-9.]+\s*\)/g, 'var($1)')
    .replace(/--tw-theme_--/g, '--');
}

const TW_TOKEN_BUG_RE = /--tw-theme_|var\(\s*--[A-Za-z0-9_-]+\s*\/\s*[0-9.]/;

/**
 * A Turbopack "Parsing CSS source code failed" error blames app/globals.css,
 * but the real cause is usually a Tailwind arbitrary-value className in a .tsx
 * (e.g. `bg-[radial-gradient(...,var(--tw-theme_--color-primary/0.1),...)]`) —
 * the model invents a `--tw-theme_` token and an opacity-slash inside var(),
 * both invalid raw CSS. The failing .tsx is NOT named by the error, so sweep the
 * whole project and repair the token wherever it appears. Returns fixed paths.
 */
export async function fixTailwindTokenBugs(
  id: string,
  onLog: (line: string) => void,
): Promise<string[]> {
  const files = await readProjectFiles(id);
  const fixed: string[] = [];
  for (const f of files) {
    if (!/\.(tsx?|jsx?|css)$/.test(f.path) || isProtectedPath(f.path)) continue;
    if (!TW_TOKEN_BUG_RE.test(f.content)) continue;
    const next = fixCssSyntax(f.content);
    if (next !== f.content) {
      await writeProjectFileRaw(id, f.path, next);
      fixed.push(f.path);
    }
  }
  if (fixed.length) {
    onLog(`[autofix] fixed invalid Tailwind token in ${fixed.length} file(s): ${fixed.slice(0, 6).join(', ')}`);
  }
  return fixed;
}

/**
 * Fast, LLM-free fix for the mechanical mistakes that show up at runtime. Runs
 * BEFORE any Gemma repair: strips a wrapping markdown fence, repairs the common
 * CSS parse bugs, then runs the full deterministic autofix suite on the single
 * file (missing "use client", missing icon/cn/shadcn imports, broken arrows,
 * etc.). Returns true if the file changed on disk.
 */
export async function deterministicFileFix(
  id: string,
  rel: string,
  onLog: (line: string) => void,
): Promise<boolean> {
  if (isProtectedPath(rel)) return false;
  const before = await readProjectFile(id, rel);
  if (!before) return false;

  let content = stripMarkdownFences(before);
  if (rel.endsWith('.css')) content = fixCssSyntax(content);
  if (content !== before) await writeProjectFileRaw(id, rel, content);

  // The full mechanical autofix suite (skips .css) — adds "use client",
  // missing imports, fixes hallucinated icons, broken arrows, etc.
  let ruleFixes = 0;
  if (!rel.endsWith('.css')) {
    ruleFixes = (await autofixFiles(id, [rel]).catch(() => [] as string[])).length;
  }

  const after = await readProjectFile(id, rel);
  if (after !== before) {
    onLog(`[autofix] deterministic fix ${rel}${ruleFixes ? ` (${ruleFixes} rule)` : ''}`);
    return true;
  }
  return false;
}

const REPAIR_SYSTEM = `You are a senior Next.js engineer fixing ONE file in a running app.
Stack: Next.js 15 App Router, TypeScript, Tailwind CSS v4, shadcn/ui (Radix). Path alias "@/..".
The dev server reported a real error in this file. Fix ONLY the cause of that error.
Rules:
- Return the COMPLETE corrected file, nothing else, inside a single \`\`\`tsx code block.
- Change as few lines as possible. Do NOT redesign, rename, or add features.
- Keep every import that is actually used; remove only a genuinely-broken one.
- shadcn/ui primitives live in "@/components/ui/*" (Button, Card, Input, Badge, Dialog, Select, Tabs, …). Never import a UI primitive from a package.
- "use client" must be the very first line for any file using hooks/handlers/browser APIs.
- No placeholder comments, no "// TODO", no \`any\`. The file must compile.`;

const CSS_REPAIR_SYSTEM = `You are fixing ONE Tailwind CSS v4 stylesheet in a running app.
The dev server's PostCSS parser rejected it (e.g. "Unexpected token", an invalid
value, a stray character). Fix ONLY the parse error(s).
Rules:
- Return the COMPLETE corrected stylesheet, nothing else, inside a single \`\`\`css block.
- Keep the first line \`@import "tailwindcss";\` and any \`@theme { … }\` token block.
- Never use Tailwind opacity-slash syntax inside a raw \`var()\` (e.g. \`var(--color-x/0.1)\` is invalid CSS — use \`var(--color-x)\` or \`color-mix(in srgb, var(--color-x) 10%, transparent)\`).
- Change as little as possible; do not restyle the app.`;

function extractCode(text: string): string {
  const fence = text.match(/```[a-zA-Z0-9_-]*[ \t]*\r?\n([\s\S]*?)```/);
  if (fence) return fence[1].trim();
  // No fence — accept the raw body only if it looks like source, not prose.
  const t = text.trim();
  return /\b(import|export|function|const|return|<)/.test(t) ? t : '';
}

async function collect(messages: ChatMessage[], signal?: AbortSignal): Promise<string> {
  let full = '';
  for await (const delta of streamOllamaChat(messages, {
    model: OLLAMA_CODE_MODEL,
    context: 'code',
    think: false,
    temperature: 0.1,
    signal,
  })) {
    full += delta;
  }
  return full;
}

/**
 * Hand ONE erroring file + its exact terminal errors to Gemma and write back a
 * minimally-corrected version. Returns true if the file content changed.
 * Protected scaffold files (shadcn primitives, lib/utils, lib/db) are never
 * touched — those are correct by construction.
 */
export async function gemmaRepairFile(
  id: string,
  rel: string,
  errors: string[],
  onLog: (line: string) => void,
  signal?: AbortSignal,
): Promise<boolean> {
  if (isProtectedPath(rel)) {
    onLog(`[autofix] ${rel} is protected — skipped`);
    return false;
  }
  const content = await readProjectFile(id, rel);
  if (!content.trim()) return false;

  const isCss = rel.endsWith('.css');
  const messages: ChatMessage[] = [
    { role: 'system', content: isCss ? CSS_REPAIR_SYSTEM : REPAIR_SYSTEM },
    {
      role: 'user',
      content: [
        `File: ${rel}`,
        '',
        'Dev-server error(s):',
        ...errors.slice(0, 10).map((e) => `- ${e}`),
        '',
        'Current file:',
        isCss ? '```css' : '```tsx',
        content,
        '```',
        '',
        'Return the complete corrected file.',
      ].join('\n'),
    },
  ];

  let raw = '';
  try {
    raw = await collect(messages, signal);
  } catch (e) {
    onLog(`[autofix] gemma error on ${rel}: ${e instanceof Error ? e.message : String(e)}`);
    return false;
  }
  const fixed = extractCode(raw);
  if (!fixed || fixed.trim() === content.trim()) return false;
  // Guard against a truncated/gutted response replacing a real file with a stub.
  if (fixed.length < Math.min(content.length * 0.4, 200) && content.length > 400) {
    onLog(`[autofix] gemma returned a suspiciously short file for ${rel} — skipped`);
    return false;
  }
  await writeProjectFileRaw(id, rel, fixed);
  onLog(`[autofix] fixed ${rel}`);
  return true;
}

/**
 * Discover the fetchable routes of a generated app: every page (page.tsx) AND
 * every API route (route.ts, incl. under app/api). Fetching each is what makes
 * Next.js LAZILY compile it, so this is also what surfaces an API route's
 * compile error (e.g. a hallucinated `next/next` import) to the terminal — API
 * routes are otherwise never hit by a page walk. Dynamic segments ("[id]") get
 * a sample value; route groups ("(marketing)") are collapsed. Pages first.
 */
export async function listAppRoutes(id: string): Promise<string[]> {
  const root = projectDir(id);
  const appDir = path.join(root, 'app');
  const pages = new Set<string>();
  const apis = new Set<string>();

  const toUrl = (segs: string[]) =>
    '/' + segs.map((s) => (/^\[.*\]$/.test(s) ? '1' : s)).join('/');

  async function walk(dir: string, segs: string[]): Promise<void> {
    let entries: import('fs').Dirent[];
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.isDirectory()) {
        const name = entry.name;
        if (name.startsWith('_') || name.startsWith('.')) continue;
        // Route groups "(x)" and parallel "@x" slots add no URL segment.
        const seg = /^\(.*\)$/.test(name) || name.startsWith('@') ? null : name;
        await walk(path.join(dir, name), seg === null ? segs : [...segs, seg]);
      } else if (/^page\.(tsx|ts|jsx|js)$/.test(entry.name)) {
        const url = toUrl(segs);
        pages.add(url === '/' ? '/' : url.replace(/\/$/, ''));
      } else if (/^route\.(ts|js)$/.test(entry.name) && segs.includes('api')) {
        apis.add(toUrl(segs).replace(/\/$/, ''));
      }
    }
  }

  await walk(appDir, []);
  const pageList = [...pages].sort((a, b) =>
    a === '/' ? -1 : b === '/' ? 1 : a.localeCompare(b),
  );
  return [...pageList, ...[...apis].sort()];
}
