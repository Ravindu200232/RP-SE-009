/**
 * scripts/analyzer.mjs — the generator's compiler.
 *
 * A long-lived process holding an incremental TypeScript LanguageService for ONE generated app, so
 * the generator can ask "is this file correct?" *before* writing it — instead of finding out from
 * `next build` ten minutes later, when only the repair loop can help and often can't.
 *
 * Cost, measured on a real app: ~2.5s to build the program once, then ~1s per file — against 60-120s
 * to generate that file. Checking is ~1% of writing.
 *
 * Protocol: JSON lines on stdin/stdout. One request per line, one response per line.
 *   → {"id":1,"op":"check","path":"components/pages/HomePage.tsx","source":"'use client'…"}
 *   ← {"id":1,"ok":true,"diagnostics":[{"line":12,"code":2769,"message":"No overload matches…"}]}
 *   → {"id":2,"op":"interface","path":"components/pages/HomePage.tsx"}
 *   ← {"id":2,"ok":true,"name":"HomePage","props":"{ initialItem: Record<string, any> }"}
 *   → {"id":3,"op":"exports","module":"@mui/icons-material/Favorite"}
 *   ← {"id":3,"ok":true,"exists":true,"names":["default"]}
 *
 * Usage: node scripts/analyzer.mjs <projectDir>
 * The app's OWN typescript is used (every generated app installs it), so diagnostics match the
 * `tsc --noEmit` the harness runs later, exactly.
 */
import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'
import { createRequire } from 'node:module'

const projectDir = path.resolve(process.argv[2] || '.')
const require = createRequire(path.join(projectDir, 'noop.js'))

let ts
try {
  ts = require('typescript') // the app's own compiler — same version the build will use
} catch {
  process.stdout.write(JSON.stringify({
    id: 0, ok: false, fatal: 'typescript-not-installed',
    error: `no typescript in ${projectDir}/node_modules — run the install before generating`,
  }) + '\n')
  process.exit(2)
}

// ── program state ────────────────────────────────────────────────────────────
// Overlays hold files the generator has NOT written yet: we check a candidate source in memory, so a
// bad file never reaches disk.
// Keys are POSIX-normalised: TypeScript hands the host forward-slash paths, so a Map keyed by
// Windows backslashes silently misses every lookup — the overlay is never found, the file reads as
// empty, and every check comes back "clean". Normalise on the way in and on every host callback.
const norm = (p) => path.resolve(projectDir, p).replace(/\\/g, '/')
const overlays = new Map() // normalised absolute path -> text
// Versions must be MONOTONIC and outlive their overlay: the document registry caches by
// (path, version), so recycling version 1 for a second candidate hands back the first one's AST —
// every file after the first gets checked as if it were the first.
const versions = new Map() // normalised absolute path -> int
const bump = (f) => {
  const v = (versions.get(f) || 0) + 1
  versions.set(f, v)
  return v
}
let rootNames = []
let options = {}

function loadConfig() {
  const configPath = path.join(projectDir, 'tsconfig.json')
  // No tsconfig means no `jsx` and no `paths`: every file would report "Cannot use JSX unless the
  // '--jsx' flag is provided" and "Cannot find module '@/types'". Refuse loudly — a misconfigured
  // analyzer that reports confident nonsense is worse than no analyzer at all.
  if (!fs.existsSync(configPath)) {
    process.stdout.write(JSON.stringify({
      id: 0, ok: false, fatal: 'no-tsconfig',
      error: `no tsconfig.json in ${projectDir} — cannot type-check without the app's own config`,
    }) + '\n')
    process.exit(2)
  }
  const read = ts.readConfigFile(configPath, ts.sys.readFile)
  const parsed = ts.parseJsonConfigFileContent(read.config || {}, ts.sys, projectDir)
  rootNames = parsed.fileNames.map(norm)
  options = parsed.options
}
loadConfig()

const host = {
  getScriptFileNames: () => [...new Set([...rootNames, ...overlays.keys()])],
  getScriptVersion: (f) => {
    const k = norm(f)
    if (versions.has(k)) return String(versions.get(k))
    try {
      return String(fs.statSync(f).mtimeMs)
    } catch {
      return '0'
    }
  },
  getScriptSnapshot: (f) => {
    const k = norm(f)
    if (overlays.has(k)) return ts.ScriptSnapshot.fromString(overlays.get(k))
    try {
      return ts.ScriptSnapshot.fromString(fs.readFileSync(f, 'utf8'))
    } catch {
      return undefined
    }
  },
  getCurrentDirectory: () => projectDir,
  getCompilationSettings: () => options,
  getDefaultLibFileName: (o) => ts.getDefaultLibFilePath(o),
  fileExists: (f) => overlays.has(norm(f)) || ts.sys.fileExists(f),
  readFile: (f) => (overlays.get(norm(f)) ?? ts.sys.readFile(f)),
  readDirectory: ts.sys.readDirectory,
  directoryExists: ts.sys.directoryExists,
  getDirectories: ts.sys.getDirectories,
  realpath: ts.sys.realpath,
}
const service = ts.createLanguageService(host, ts.createDocumentRegistry())

// ── ops ──────────────────────────────────────────────────────────────────────
const abs = norm

function fmt(d) {
  const out = { code: d.code, message: ts.flattenDiagnosticMessageText(d.messageText, ' ') }
  if (d.file && typeof d.start === 'number') {
    const { line, character } = d.file.getLineAndCharacterOfPosition(d.start)
    out.line = line + 1
    out.column = character + 1
  }
  return out
}

function check({ path: rel, source }) {
  const file = abs(rel)
  if (typeof source === 'string') {
    overlays.set(file, source)
    bump(file)
    if (!rootNames.includes(file)) rootNames.push(file)
  }
  // Syntactic first: a file that does not parse produces meaningless semantic noise.
  const syntactic = service.getSyntacticDiagnostics(file).map(fmt)
  if (syntactic.length) return { diagnostics: syntactic, kind: 'syntactic' }
  const semantic = service.getSemanticDiagnostics(file).map(fmt)
  return { diagnostics: semantic, kind: semantic.length ? 'semantic' : 'clean' }
}

/** Drop an overlay once the real file is on disk (or the candidate is abandoned). */
function release({ path: rel }) {
  const file = abs(rel)
  overlays.delete(file)
  bump(file) // the next read must come from disk, not the registry's cache of the overlay
  return { released: true }
}

/**
 * The default export's name and its exact props — what a consumer must be told so it stops guessing.
 * This is the fact behind the page/body prop mismatches: two agents agreeing by convention instead of
 * one reading the other.
 */
function iface({ path: rel }) {
  const file = abs(rel)
  // A file written after this process booted is not in the program yet — the composer asks for the
  // chunk's signature moments after the chunk was created, so without this it always answered "no
  // such file" and the page fell back to guessing the props.
  if (!rootNames.includes(file) && fs.existsSync(file)) {
    rootNames.push(file)
    bump(file)
  }
  const prog = service.getProgram()
  const sf = prog?.getSourceFile(file)
  if (!sf) return { name: null, props: null, found: false }
  let name = null
  let props = null
  const checker = prog.getTypeChecker()
  for (const st of sf.statements) {
    // `export default Name` is an ExportAssignment without a DefaultKeyword modifier.
    if (ts.isExportAssignment(st) && ts.isIdentifier(st.expression)) {
      name = st.expression.getText(sf)
      const declaration = sf.statements.find((candidate) =>
        ts.isFunctionDeclaration(candidate) && candidate.name?.text === name)
      const variable = sf.statements
        .filter((candidate) => ts.isVariableStatement(candidate))
        .flatMap((candidate) => [...candidate.declarationList.declarations])
        .find((candidate) => ts.isIdentifier(candidate.name) && candidate.name.text === name)
      const callable = declaration || ((variable?.initializer &&
        (ts.isArrowFunction(variable.initializer) || ts.isFunctionExpression(variable.initializer)))
        ? variable.initializer : null)
      const p = callable?.parameters?.[0]
      if (p) {
        const t = checker.getTypeAtLocation(p)
        props = p.type ? p.type.getText(sf) : checker.typeToString(t)
      } else if (callable?.parameters) {
        props = ''
      }
      continue
    }
    const isDefault = st.modifiers?.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword)
    if (!isDefault) continue
    if (ts.isFunctionDeclaration(st)) {
      name = st.name?.getText(sf) ?? null
      const p = st.parameters?.[0]
      if (p) {
        const t = checker.getTypeAtLocation(p)
        props = p.type ? p.type.getText(sf) : checker.typeToString(t)
      } else {
        props = '' // takes no props — say so explicitly, it is the fact consumers need
      }
    } else if (ts.isExportAssignment(st) && ts.isIdentifier(st.expression)) {
      name = st.expression.getText(sf)
    }
  }
  return { name, props, found: true }
}

/**
 * What a module REALLY exports. `@mui/icons-material/Heart` does not exist; `Favorite` does — and the
 * model cannot tell without being shown. A file check is enough for icons; anything else is parsed.
 */
function exportsOf({ module: spec }) {
  // Bare package (possibly with a subpath) → resolve inside node_modules.
  if (!spec.startsWith('.') && !spec.startsWith('@/')) {
    const parts = spec.split('/')
    const pkg = spec.startsWith('@') ? parts.slice(0, 2).join('/') : parts[0]
    const sub = spec.slice(pkg.length + 1)
    const base = path.join(projectDir, 'node_modules', ...pkg.split('/'))
    if (!fs.existsSync(base)) return { exists: false, reason: 'package-not-installed', names: [] }
    if (!sub) return { exists: true, names: [] }
    const candidates = [`${sub}.js`, `${sub}.d.ts`, path.join(sub, 'index.js'), sub]
    const hit = candidates.some((c) => fs.existsSync(path.join(base, c)))
    return { exists: hit, reason: hit ? null : 'subpath-not-found', names: hit ? ['default'] : [] }
  }
  // Internal module → ask the compiler what it exports.
  const rel = spec.startsWith('@/') ? spec.slice(2) : spec
  const prog = service.getProgram()
  for (const ext of ['.ts', '.tsx', '/index.ts', '/index.tsx', '']) {
    const sf = prog?.getSourceFile(abs(rel + ext))
    if (!sf) continue
    const sym = prog.getTypeChecker().getSymbolAtLocation(sf)
    const names = sym ? prog.getTypeChecker().getExportsOfModule(sym).map((s) => s.getName()) : []
    return { exists: true, names }
  }
  return { exists: false, reason: 'module-not-found', names: [] }
}

const OPS = { check, interface: iface, exports: exportsOf, release, ping: () => ({ pong: true }) }

// ── stdio loop ───────────────────────────────────────────────────────────────
const rl = readline.createInterface({ input: process.stdin })
rl.on('line', (line) => {
  if (!line.trim()) return
  let req
  try {
    req = JSON.parse(line)
  } catch (e) {
    process.stdout.write(JSON.stringify({ id: null, ok: false, error: `bad json: ${e.message}` }) + '\n')
    return
  }
  const op = OPS[req.op]
  if (!op) {
    process.stdout.write(JSON.stringify({ id: req.id, ok: false, error: `unknown op: ${req.op}` }) + '\n')
    return
  }
  try {
    process.stdout.write(JSON.stringify({ id: req.id, ok: true, ...op(req) }) + '\n')
  } catch (e) {
    process.stdout.write(JSON.stringify({ id: req.id, ok: false, error: String(e?.message || e) }) + '\n')
  }
})
rl.on('close', () => process.exit(0))
process.stdout.write(JSON.stringify({ id: 0, ok: true, ready: true, ts: ts.version }) + '\n')
