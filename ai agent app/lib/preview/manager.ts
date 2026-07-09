import { spawn, type ChildProcess } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { projectDir } from '../workspace/fs';
import { syncGeneratedDependencies } from '../build/dependencies';
import { ensureScaffoldAssets } from '../workspace/scaffold';
import {
  parseDevErrors,
  installPackages,
  gemmaRepairFile,
  deterministicFileFix,
  fixTailwindTokenBugs,
  fixMissingModelRoutes,
  fixComponentImports,
  fixDeadInternalLinks,
  collectErrorFiles,
  errorContext,
  listAppRoutes,
} from './runtimeFixer';

/**
 * Runs generated projects as real local dev servers so the builder can show a
 * live <iframe> preview (bolt-style). State is kept on globalThis so it
 * survives Next.js dev hot-reloads instead of orphaning child processes.
 */

export type PreviewPhase =
  | 'idle'
  | 'installing'
  | 'starting'
  | 'ready'
  | 'error'
  | 'stopped';

export interface PageCheck {
  route: string;
  status: number;
  ok: boolean;
  fixed: string[];
}

interface PreviewState {
  id: string;
  port: number;
  phase: PreviewPhase;
  url: string;
  logs: string[];
  error?: string;
  proc?: ChildProcess;
  startedAt: number;
  // Runtime terminal bug-fixer state.
  fixing?: boolean;
  autoFixDone?: boolean;
  restarting?: boolean;
  pageChecks?: PageCheck[];
}

interface PreviewStore {
  previews: Map<string, PreviewState>;
  nextPort: number;
}

const store: PreviewStore = ((globalThis as Record<string, unknown>)._previewStore ??= {
  previews: new Map<string, PreviewState>(),
  nextPort: 3100,
}) as PreviewStore;

const MAX_LOGS = 1000;
const isWindows = process.platform === 'win32';
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function pushLog(state: PreviewState, chunk: string) {
  for (const line of chunk.split(/\r?\n/)) {
    if (line.trim()) state.logs.push(line.replace(/\x1b\[[0-9;]*m/g, ''));
  }
  if (state.logs.length > MAX_LOGS) {
    state.logs.splice(0, state.logs.length - MAX_LOGS);
  }
}

export type PublicPreview = Omit<PreviewState, 'proc'>;

export function getPreview(id: string): PublicPreview | null {
  const s = store.previews.get(id);
  if (!s) return null;
  const { proc: _proc, ...rest } = s;
  return rest;
}

function killTree(proc: ChildProcess) {
  if (!proc.pid) return;
  if (isWindows) {
    spawn('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { shell: true });
  } else {
    try {
      process.kill(-proc.pid, 'SIGTERM');
    } catch {
      proc.kill('SIGTERM');
    }
  }
}

export function stopPreview(id: string) {
  const s = store.previews.get(id);
  if (!s) return;
  if (s.proc) killTree(s.proc);
  s.proc = undefined;
  s.phase = 'stopped';
  pushLog(s, '[preview] stopped');
}

async function waitForServer(state: PreviewState, timeoutMs = 150000) {
  const deadline = Date.now() + timeoutMs;
  const url = `http://127.0.0.1:${state.port}/`;
  while (Date.now() < deadline) {
    if (state.phase === 'stopped' || state.phase === 'error') return;
    try {
      await fetch(url, { cache: 'no-store' });
      state.phase = 'ready';
      pushLog(state, `[preview] ready on ${state.url}`);
      return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  if (state.phase !== 'ready') {
    state.phase = 'error';
    state.error = 'Timed out waiting for the dev server to start';
  }
}

function runDevServer(state: PreviewState): Promise<void> {
  state.phase = 'starting';
  pushLog(state, `[preview] starting dev server on port ${state.port}…`);

  // Vite (Google-AI-Studio format) apps run `tsx server.ts`, which listens on
  // process.env.PORT — pass it via env. Next apps take a `-p` flag instead.
  const isVite = existsSync(path.join(projectDir(state.id), 'vite.config.ts'));
  const cmd = isVite ? 'npm run dev' : `npm run dev -- -p ${state.port}`;
  const proc = spawn(cmd, {
    cwd: projectDir(state.id),
    shell: true,
    env: isVite
      ? { ...process.env, BROWSER: 'none', PORT: String(state.port) }
      : { ...process.env, BROWSER: 'none' },
    detached: !isWindows,
  });
  state.proc = proc;

  proc.stdout?.on('data', (d) => pushLog(state, d.toString()));
  proc.stderr?.on('data', (d) => pushLog(state, d.toString()));
  proc.on('exit', (code) => {
    // A deliberate restart (auto-fixer installed a package) kills the old proc;
    // don't let that flip the preview into an error state.
    if (state.phase !== 'stopped' && !state.restarting) {
      state.phase = code === 0 ? 'stopped' : 'error';
      if (code !== 0 && !state.error) {
        state.error = `Dev server exited (code ${code}) — check logs`;
      }
    }
    pushLog(state, `[preview] dev server exited (code ${code})`);
  });

  return waitForServer(state);
}

/**
 * Restart the dev server in place (same port). Needed after the auto-fixer
 * `npm install`s a missing package: the running server won't always re-resolve
 * a previously-unresolvable module without a fresh start.
 */
async function restartDevServer(state: PreviewState): Promise<void> {
  state.restarting = true;
  try {
    if (state.proc) {
      const dead = new Promise<void>((resolve) => state.proc?.once('exit', () => resolve()));
      killTree(state.proc);
      state.proc = undefined;
      await Promise.race([dead, sleep(4000)]);
    }
    pushLog(state, '[autofix] restarting dev server to pick up installed packages…');
    await runDevServer(state);
  } finally {
    state.restarting = false;
  }
}

// True when a log slice contains a real COMPILE error (module/parse/type), as
// opposed to a plain runtime 500 the handler returned. Used to tell a genuine
// broken API route from one that merely 500s on a synthetic dynamic value.
const COMPILE_MARKER_RE =
  /Module not found|Parsing (?:CSS|ecmascript)|Ecmascript file had an error|CssSyntaxError|Failed to compile|is not defined|has already been declared|defined multiple times|Cannot find (?:name|module)|Unexpected token|Export .* was not found|You're importing/i;
function hasCompileMarker(slice: string[]): boolean {
  return slice.some((l) => COMPILE_MARKER_RE.test(l));
}

/** Fetch one route to force Next.js to compile it; returns the HTTP status. */
async function fetchRoute(port: number, route: string): Promise<number> {
  const url = `http://127.0.0.1:${port}${route}`;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, { cache: 'no-store', redirect: 'manual' });
      return res.status;
    } catch {
      // Server may be recompiling or restarting — give it a moment.
      await sleep(1500);
    }
  }
  return 0;
}

const MAX_FILE_ATTEMPTS = 4; // per file, across the whole page-check run
const MAX_PAGE_ROUNDS = 8; // fetch→fix cycles per page before giving up
const MAX_FIXES_PER_ROUND = 5; // cap files touched per fetch (avoid over-editing)

/**
 * The page-check + terminal bug-fix agent. Walks every generated page (which is
 * what makes Next.js lazily compile each route), reads the errors the dev-server
 * terminal prints, and fixes only those: `npm install` for a missing library,
 * one-file Gemma repair for a code error. Loops each page until it renders with
 * no terminal error (HTTP < 500) or nothing actionable is left.
 */
async function runAutoFix(state: PreviewState): Promise<void> {
  state.fixing = true;
  const root = projectDir(state.id);
  const routes = await listAppRoutes(state.id);
  pushLog(state, `[autofix] page-check agent started — ${routes.length} page(s) to verify`);

  // Clear structural cascade-triggers UPFRONT (before walking pages), so one
  // broken import doesn't 500 the whole graph and make every page look broken:
  // a mis-pathed/missing component import, a route importing a non-existent
  // model, or a link to a route with no page. These are the highest-leverage
  // fixes and cheap to run once.
  const preFixes = [
    ...(await fixComponentImports(state.id, (l) => pushLog(state, l)).catch(() => [])),
    ...(await fixMissingModelRoutes(state.id, (l) => pushLog(state, l)).catch(() => [])),
    ...(await fixDeadInternalLinks(state.id, (l) => pushLog(state, l)).catch(() => [])),
  ];
  if (preFixes.length) {
    await restartDevServer(state);
    if (state.phase !== 'ready') {
      state.fixing = false;
      return;
    }
  }

  const installedSpecs = new Set<string>();
  const fileAttempts = new Map<string, number>();
  const checks: PageCheck[] = [];
  let tailwindSwept = false;
  let modelRoutesSwept = false;
  let componentsSwept = false;

  for (const route of routes) {
    if (state.phase === 'stopped' || state.phase === 'error') break;
    const isApiRoute = route.startsWith('/api/');
    let status = 0;
    let ok = false;
    const fixedHere: string[] = [];

    for (let round = 0; round < MAX_PAGE_ROUNDS; round++) {
      const startLen = state.logs.length;
      status = await fetchRoute(state.port, route);
      await sleep(700); // let the compile + any stderr flush into the log buffer
      const slice = state.logs.slice(Math.min(startLen, state.logs.length));
      const errors = parseDevErrors(slice, root);

      if (status && status < 500 && errors.length === 0) {
        ok = true;
        break;
      }

      // An API route that COMPILED (no compile-error marker) but 500s is almost
      // always our synthetic dynamic value (GET /api/notes/[id] with id "1" →
      // invalid ObjectId) or a missing request body — expected runtime
      // behavior, not a build bug. Don't chase it.
      if (isApiRoute && status >= 500 && !hasCompileMarker(slice)) {
        ok = true;
        break;
      }

      let progressed = false;

      // 1) Missing libraries → install (once per spec), then restart so the
      //    running server actually resolves them.
      const pkgs = [
        ...new Set(
          errors
            .filter((e) => e.kind === 'missing-package' && e.spec)
            .map((e) => e.spec as string),
        ),
      ].filter((s) => !installedSpecs.has(s));
      if (pkgs.length) {
        pkgs.forEach((s) => installedSpecs.add(s));
        const installed = await installPackages(state.id, pkgs, (l) => pushLog(state, l));
        if (installed) {
          fixedHere.push(`installed ${pkgs.join(', ')}`);
          progressed = true;
          await restartDevServer(state);
          if (state.phase !== 'ready') break;
        }
      }

      // 1b) A CSS "Parsing CSS source code failed" blames globals.css but is
      //     usually a bad Tailwind arbitrary-value token in a .tsx className.
      //     Sweep the whole project once — the failing .tsx is never named.
      if (
        !tailwindSwept &&
        slice.some((l) => /Parsing CSS source code failed|CssSyntaxError|--tw-theme_/.test(l))
      ) {
        tailwindSwept = true;
        const swept = await fixTailwindTokenBugs(state.id, (l) => pushLog(state, l));
        if (swept.length) {
          fixedHere.push(`swept ${swept.length} tailwind-token file(s)`);
          progressed = true;
        }
      }

      // 1c) One API route importing a non-existent model 500s EVERY API route
      //     (Turbopack fails the whole graph). The error floods logs but names
      //     the culprit file — stub the broken route once to un-poison the graph.
      if (
        !modelRoutesSwept &&
        slice.some((l) => /Can't resolve ['"]@\/lib\/models\//.test(l))
      ) {
        modelRoutesSwept = true;
        const stubbed = await fixMissingModelRoutes(state.id, (l) => pushLog(state, l));
        if (stubbed.length) {
          fixedHere.push(`stubbed ${stubbed.length} broken model route(s)`);
          progressed = true;
        }
      }

      // 1d) A decomposed page importing a section from the wrong path or a
      //     section the model forgot to write also cascades 500s. Remap the
      //     import to the real file or stub the missing one — once per run.
      if (
        !componentsSwept &&
        slice.some((l) => /Can't resolve ['"]@\/components\//.test(l))
      ) {
        componentsSwept = true;
        const fixed = await fixComponentImports(state.id, (l) => pushLog(state, l));
        if (fixed.length) {
          fixedHere.push(`fixed ${fixed.length} component import(s)`);
          progressed = true;
        }
      }

      // 2) Code errors. Precise per-format parsing misses many Turbopack/SWC
      //    shapes, so fix EVERY project file the failing route's error output
      //    mentions: deterministic fence-strip first (the only fixer for .css),
      //    then hand the file + the RAW error text to Gemma. The raw block is
      //    far more reliable context than a single parsed message.
      const rawErrors = errorContext(slice);
      const filesToFix = new Set<string>();
      for (const e of errors) {
        if (e.file && e.kind !== 'missing-package') filesToFix.add(e.file);
      }
      for (const f of collectErrorFiles(slice, root)) filesToFix.add(f);

      let fixedThisRound = 0;
      for (const file of filesToFix) {
        if (fixedThisRound >= MAX_FIXES_PER_ROUND) break;
        const det = await deterministicFileFix(state.id, file, (l) => pushLog(state, l));
        if (det) {
          fixedHere.push(`fixed ${file}`);
          progressed = true;
          fixedThisRound++;
          continue;
        }
        const n = fileAttempts.get(file) ?? 0;
        if (n >= MAX_FILE_ATTEMPTS) continue;
        fileAttempts.set(file, n + 1);
        const changed = await gemmaRepairFile(state.id, file, rawErrors, (l) => pushLog(state, l));
        if (changed) {
          fixedHere.push(`fixed ${file}`);
          progressed = true;
          fixedThisRound++;
        }
      }

      if (!progressed) break; // nothing left we can do for this page
      await sleep(1200); // let Turbopack recompile the just-written file(s)
    }

    checks.push({ route, status, ok, fixed: fixedHere });
    pushLog(
      state,
      `[autofix] ${route} → ${ok ? 'OK' : `still failing (status ${status})`}` +
        (fixedHere.length ? ` | ${fixedHere.join('; ')}` : ''),
    );
  }

  state.pageChecks = checks;
  state.fixing = false;
  const good = checks.filter((c) => c.ok).length;
  pushLog(state, `[autofix] page-check complete: ${good}/${checks.length} page(s) OK`);
}

function runInstall(state: PreviewState): Promise<void> {
  return new Promise((resolve) => {
    state.phase = 'installing';
    pushLog(state, '[preview] installing dependencies (npm install)…');

    // --legacy-peer-deps keeps install resilient when the model picks slightly
    // mismatched peer versions; --no-audit/--no-fund speed it up.
    const proc = spawn('npm install --legacy-peer-deps --no-audit --no-fund', {
      cwd: projectDir(state.id),
      shell: true,
      env: { ...process.env },
    });
    state.proc = proc;

    proc.stdout?.on('data', (d) => pushLog(state, d.toString()));
    proc.stderr?.on('data', (d) => pushLog(state, d.toString()));
    proc.on('exit', (code) => {
      pushLog(state, `[preview] npm install exited (code ${code})`);
      if (code !== 0) {
        state.phase = 'error';
        state.error = `npm install failed (code ${code}) — check logs`;
      }
      resolve();
    });
  });
}

/**
 * Production build gate. The dev page-check catches most compile errors, but a
 * `next build` also surfaces production-only failures (a client hook used
 * without Suspense, a bad server/client boundary, a prerender crash). This runs
 * `npm run build`; if it fails, it fixes every file the build output blames
 * (deterministic fence/JSX strip → Gemma one-file repair) and rebuilds, up to a
 * small cap. Runs with the dev server STOPPED (they can't share .next), then the
 * caller restarts dev. Returns true if the build ultimately succeeds.
 */
async function runBuildCheck(state: PreviewState): Promise<boolean> {
  const root = projectDir(state.id);
  const MAX_BUILD_ROUNDS = Number(process.env.BUILD_CHECK_ROUNDS || 3);
  const fileAttempts = new Map<string, number>();

  // Free .next for the build — stop the running dev server.
  if (state.proc) killTree(state.proc);
  state.proc = undefined;
  await sleep(800);

  const runBuild = (): Promise<{ code: number; out: string[] }> =>
    new Promise((resolve) => {
      const out: string[] = [];
      const proc = spawn('npm run build', { cwd: root, shell: true, env: { ...process.env } });
      state.proc = proc;
      const onData = (d: Buffer) => {
        const text = d.toString();
        out.push(text);
        pushLog(state, text);
      };
      proc.stdout?.on('data', onData);
      proc.stderr?.on('data', onData);
      proc.on('exit', (code) => resolve({ code: code ?? 1, out }));
      proc.on('error', () => resolve({ code: 1, out }));
    });

  for (let round = 0; round < MAX_BUILD_ROUNDS; round++) {
    pushLog(state, `[build-check] npm run build (round ${round + 1}/${MAX_BUILD_ROUNDS})…`);
    const { code, out } = await runBuild();
    if (code === 0) {
      pushLog(state, '[build-check] production build succeeded ✓');
      return true;
    }
    const logs = out.join('').split('\n');
    const files = new Set<string>();
    for (const e of parseDevErrors(logs, root)) if (e.file && e.kind !== 'missing-package') files.add(e.file);
    for (const f of collectErrorFiles(logs, root)) files.add(f);
    if (files.size === 0) {
      pushLog(state, '[build-check] build failed but no fixable file was named — leaving as is');
      return false;
    }
    const rawErrors = errorContext(logs);
    let fixed = 0;
    for (const file of files) {
      if (await deterministicFileFix(state.id, file, (l) => pushLog(state, l))) {
        fixed++;
        continue;
      }
      const n = fileAttempts.get(file) ?? 0;
      if (n >= 2) continue;
      fileAttempts.set(file, n + 1);
      if (await gemmaRepairFile(state.id, file, rawErrors, (l) => pushLog(state, l))) fixed++;
    }
    if (fixed === 0) {
      pushLog(state, '[build-check] no further fixes available — stopping build gate');
      return false;
    }
    pushLog(state, `[build-check] applied ${fixed} fix(es); rebuilding`);
  }
  pushLog(state, '[build-check] still failing after max rounds');
  return false;
}

export interface StartPreviewOptions {
  /**
   * After the dev server is up, run the page-check + terminal bug-fix agent
   * once (walk every page, fix the errors the terminal reports). Defaults to
   * true; runs at most once per preview lifetime.
   */
  autoFix?: boolean;
  /** Run a `npm run build` production gate after the page-check. Default true. */
  buildCheck?: boolean;
}

export function startPreview(id: string, opts: StartPreviewOptions = {}): PublicPreview {
  const autoFix = opts.autoFix ?? true;
  const buildCheck = opts.buildCheck ?? process.env.PREVIEW_BUILD_CHECK !== 'false';
  const existing = store.previews.get(id);

  // Idempotent: if it's already coming up or running, just report status.
  if (
    existing &&
    (existing.phase === 'ready' ||
      existing.phase === 'starting' ||
      existing.phase === 'installing')
  ) {
    return getPreview(id)!;
  }

  const port = existing?.port ?? store.nextPort++;
  const state: PreviewState = {
    id,
    port,
    phase: 'idle',
    url: `http://localhost:${port}`,
    logs: existing?.logs ?? [],
    startedAt: Date.now(),
    // Do NOT carry autoFixDone across a fresh start: reaching this point means
    // the dev server is being (re)started, and the code may have just been
    // rebuilt — so the page-check/autofix pass must run again. (Repeated status
    // polls while ready are short-circuited by the idempotent guard above, so
    // this never re-runs autofix redundantly within one session.)
    autoFixDone: false,
  };
  store.previews.set(id, state);

  // Kick off install (if needed) + dev server without blocking the response.
  void (async () => {
    try {
      await ensureScaffoldAssets(id);
      const deps = await syncGeneratedDependencies(id);
      if (deps.added.length) {
        pushLog(state, `[preview] added missing package(s): ${deps.added.join(', ')}`);
        pushLog(state, `[preview] ${deps.installCommand}`);
      }
      const hasNodeModules = existsSync(path.join(projectDir(id), 'node_modules'));
      if (!hasNodeModules || deps.added.length > 0) {
        await runInstall(state);
        if (state.phase === 'error') return;
      }
      await runDevServer(state);
      if (autoFix && state.phase === 'ready' && !state.autoFixDone) {
        state.autoFixDone = true;
        await runAutoFix(state).catch((e) =>
          pushLog(state, `[autofix] aborted: ${e instanceof Error ? e.message : String(e)}`),
        );
        // Production build gate: fix anything `next build` catches that the dev
        // page-check missed, then bring the dev server back up for the preview.
        if (buildCheck) {
          await runBuildCheck(state).catch((e) =>
            pushLog(state, `[build-check] aborted: ${e instanceof Error ? e.message : String(e)}`),
          );
          await restartDevServer(state).catch(() => {});
        }
      }
    } catch (e) {
      state.phase = 'error';
      state.error = e instanceof Error ? e.message : String(e);
    }
  })();

  return getPreview(id)!;
}
