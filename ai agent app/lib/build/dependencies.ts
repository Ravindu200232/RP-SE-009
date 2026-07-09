import { builtinModules } from 'module';
import { promises as fs } from 'fs';
import path from 'path';
import type { GeneratedFile } from '../artifact/types';
import { projectDir, readProjectFiles } from '../workspace/fs';

// Only REAL import/export statements — an `import`/`export` keyword must
// precede `from`. The old bare /\bfrom ['"]X['"]/ also matched prose inside
// comments/strings (a JSDoc "e.g. from 'Available' to 'Sold'" got added as a
// package "Available", which npm rejects → the whole build aborted at install).
const IMPORT_FROM = /(?:^|[\n;])\s*(?:import|export)\b[^\n;]*?\bfrom\s+['"]([^'"]+)['"]/g;
const IMPORT_BARE = /(?:^|[\n;])\s*import\s+['"]([^'"]+)['"]/g;
const IMPORT_DYNAMIC = /\bimport\(\s*['"]([^'"]+)['"]\s*\)/g;

/** Drop block + line comments so prose like `from 'X'` is never seen as an import. */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

const NODE_BUILTINS = new Set([
  ...builtinModules,
  ...builtinModules.map((m) => `node:${m}`),
]);

const BOGUS_IMPORT_SPECS = new Set([
  'use client',
  'use server',
  'pending',
  'confirmed',
  'completed',
  'cancelled',
  'canceled',
  'preparing',
  'served',
  'checked_in',
  'checked_out',
]);

const DENIED_EXTERNAL_PACKAGES = new Set([
  '_next',
  '@radix-ui/react-card',
  '@radix-ui/react-button',
  '@radix-ui/react-badge',
  '@radix-ui/react-input',
  '@radix-ui/react-select',
  '@radix-ui/react-textarea',
  '@inner-logic/zod-schemas',
  'framer-motion',
  'json',
]);

const VERSION_HINTS: Record<string, string> = {
  '@radix-ui/react-avatar': '^1.1.2',
  '@radix-ui/react-dialog': '^1.1.4',
  '@radix-ui/react-dropdown-menu': '^2.1.4',
  '@radix-ui/react-label': '^2.1.1',
  '@radix-ui/react-separator': '^1.1.0',
  '@radix-ui/react-switch': '^1.1.2',
  '@radix-ui/react-slot': '^1.1.1',
  '@radix-ui/react-tabs': '^1.1.2',
  '@radix-ui/react-toast': '^1.2.4',
  '@tanstack/react-table': '^8.21.3',
  bcryptjs: '^3.0.3',
  'class-variance-authority': '^0.7.1',
  clsx: '^2.1.1',
  'date-fns': '^4.4.0',
  jsonwebtoken: '^9.0.3',
  'lucide-react': '^0.475.0',
  mongoose: '^8.9.5',
  recharts: '^3.9.1',
  'react-hook-form': '^7.68.0',
  'tailwind-merge': '^2.6.0',
  zod: '^4.4.3',
};

export interface DependencySyncReport {
  imported: string[];
  added: string[];
  installCommand: string;
  libraryPath: string;
}

function isSourceFile(file: GeneratedFile): boolean {
  return /\.(ts|tsx|js|jsx|mjs|cjs)$/.test(file.path);
}

function packageName(spec: string): string {
  if (spec.startsWith('node:')) return spec;
  if (spec.startsWith('@')) return spec.split('/').slice(0, 2).join('/');
  return spec.split('/')[0];
}

function isPlausiblePackageSpec(spec: string): boolean {
  if (!spec || BOGUS_IMPORT_SPECS.has(spec.toLowerCase())) return false;
  if (/\s/.test(spec)) return false;
  if (/^[.#?]/.test(spec)) return false;
  // npm names are lowercase — NO /i flag (that let "Available" through).
  if (spec.startsWith('@')) {
    return /^@[a-z0-9._~-]+\/[a-z0-9._~-]+(?:\/[\w./~-]+)?$/.test(spec);
  }
  return /^[a-z0-9._~-]+(?:\/[\w./~-]+)?$/.test(spec);
}

function isExternalImport(spec: string): boolean {
  if (!isPlausiblePackageSpec(spec)) return false;
  if (DENIED_EXTERNAL_PACKAGES.has(packageName(spec))) return false;
  if (
    spec.startsWith('@/') ||
    spec.startsWith('./') ||
    spec.startsWith('../') ||
    spec.startsWith('/') ||
    spec.endsWith('.css')
  ) {
    return false;
  }
  return !NODE_BUILTINS.has(spec) && !NODE_BUILTINS.has(packageName(spec));
}

function collectSpecs(content: string): string[] {
  const clean = stripComments(content);
  const specs = new Set<string>();
  for (const re of [IMPORT_FROM, IMPORT_BARE, IMPORT_DYNAMIC]) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(clean))) specs.add(m[1]);
  }
  return [...specs];
}

function collectPackages(files: GeneratedFile[]): string[] {
  const packages = new Set<string>();
  for (const file of files) {
    if (!isSourceFile(file)) continue;
    for (const spec of collectSpecs(file.content ?? '')) {
      if (isExternalImport(spec)) packages.add(packageName(spec));
    }
  }
  return [...packages].sort();
}

async function readPackageJson(root: string): Promise<Record<string, unknown> | null> {
  try {
    return JSON.parse(await fs.readFile(path.join(root, 'package.json'), 'utf8')) as Record<
      string,
      unknown
    >;
  } catch {
    return null;
  }
}

function depMap(pkg: Record<string, unknown>, key: string): Record<string, string> {
  const value = pkg[key];
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, string>)
    : {};
}

function hasDependency(pkg: Record<string, unknown>, name: string): boolean {
  return Boolean(
    depMap(pkg, 'dependencies')[name] ||
      depMap(pkg, 'devDependencies')[name] ||
      depMap(pkg, 'peerDependencies')[name],
  );
}

async function writeLibraryMd(
  root: string,
  imported: string[],
  added: string[],
): Promise<string> {
  const installCommand = added.length
    ? `npm install --legacy-peer-deps --no-audit --no-fund ${added.join(' ')}`
    : 'npm install --legacy-peer-deps --no-audit --no-fund';
  const content = [
    '# Library Imports',
    '',
    'This file is generated by AI Web Builder after scanning generated source imports.',
    '',
    '## Imported External Packages',
    '',
    ...(imported.length ? imported.map((p) => `- ${p}`) : ['- none']),
    '',
    '## Missing Packages Added To package.json',
    '',
    ...(added.length ? added.map((p) => `- ${p}@${VERSION_HINTS[p] ?? 'latest'}`) : ['- none']),
    '',
    '## Install Command',
    '',
    '```bash',
    installCommand,
    '```',
    '',
  ].join('\n');
  const libraryPath = path.join(root, 'library.md');
  await fs.writeFile(libraryPath, content, 'utf8');
  return installCommand;
}

function pruneBogusDeps(pkg: Record<string, unknown>): boolean {
  let changed = false;
  for (const key of ['dependencies', 'devDependencies', 'peerDependencies']) {
    const deps = depMap(pkg, key);
    for (const name of Object.keys(deps)) {
      if (
        BOGUS_IMPORT_SPECS.has(name.toLowerCase()) ||
        DENIED_EXTERNAL_PACKAGES.has(name) ||
        !isPlausiblePackageSpec(name)
      ) {
        delete deps[name];
        changed = true;
      }
    }
    if (changed) {
      pkg[key] = Object.fromEntries(
        Object.entries(deps).sort(([a], [b]) => a.localeCompare(b)),
      );
    }
  }
  return changed;
}

export async function syncGeneratedDependencies(
  id: string,
  filesArg?: GeneratedFile[],
): Promise<DependencySyncReport> {
  const root = projectDir(id);
  const files = filesArg ?? (await readProjectFiles(id));
  const imported = collectPackages(files);
  const pkg = await readPackageJson(root);
  if (!pkg) {
    const installCommand = await writeLibraryMd(root, imported, []);
    return { imported, added: [], installCommand, libraryPath: 'library.md' };
  }

  let packageChanged = pruneBogusDeps(pkg);
  const deps = { ...depMap(pkg, 'dependencies') };
  const added: string[] = [];
  for (const name of imported) {
    if (hasDependency(pkg, name)) continue;
    deps[name] = VERSION_HINTS[name] ?? 'latest';
    added.push(name);
  }
  if (added.length || packageChanged) {
    pkg.dependencies = Object.fromEntries(
      Object.entries(deps).sort(([a], [b]) => a.localeCompare(b)),
    );
    await fs.writeFile(path.join(root, 'package.json'), JSON.stringify(pkg, null, 2) + '\n');
  }

  const installCommand = await writeLibraryMd(root, imported, added);
  return { imported, added, installCommand, libraryPath: 'library.md' };
}
