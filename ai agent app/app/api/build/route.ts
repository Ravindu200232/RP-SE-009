import type { NextRequest } from 'next/server';
import {
  streamOllamaChat,
  OLLAMA_CODE_MODEL,
  type ChatMessage,
} from '@/lib/llm/ollama';
import {
  buildFoundationMessages,
  buildShellMessages,
  buildApiBatchMessages,
  buildPageMessages,
  buildPageBatchMessages,
  buildFinalMessages,
  MAX_BUILD_STEPS,
} from '@/lib/llm/buildPrompts';
import {
  parseArtifact,
  parseFencedFiles,
  parseSingleFileRepair,
} from '@/lib/artifact/parser';
import {
  writeProjectFiles,
  writeProjectEnv,
  projectDir,
  listProjectFiles,
  readProjectManifest,
  readProjectFile,
  readProjectFiles,
  readPlansFromDisk,
  writeProjectFileRaw,
  deleteProjectFile,
  protectPaths,
} from '@/lib/workspace/fs';
import { ensureScaffoldAssets, scaffoldProject } from '@/lib/workspace/scaffold';
import { designDirection } from '@/lib/build/designIdentity';
import { derivePages, extractPageSpec, type DerivedPage } from '@/lib/build/derivePages';
import { autofixProject, autofixFiles } from '@/lib/build/autofix';
import { findBrokenFiles, syntaxErrors } from '@/lib/build/verify';
import { analyzeProject } from '@/lib/build/analyze';
import {
  auditGeneratedProject,
  collectPageQualityFindings,
  isBlockingPageQualityIssue,
  plannedApiFilesFromPlans,
  referencedApiFiles,
  unifyDynamicSegments,
} from '@/lib/build/audit';
import { syncGeneratedDependencies } from '@/lib/build/dependencies';
import { buildRepairMessages, buildEditRepairMessages } from '@/lib/llm/repairPrompts';
import { parseEditBlocks, applyEditBlocks } from '@/lib/build/editBlocks';
import { ensureSeededUsers, writeCredentialsTxt } from '@/lib/build/credentials';
import { ensureInstalled, runTsc } from '@/lib/build/tsc';
import { repairQualityFindings } from '@/lib/build/qualityRepair';
import { generateDeterministicApis } from '@/lib/build/apiGen';
import { seedBackendKit } from '@/lib/build/backendKit';
import {
  fixComponentImports,
  fixMissingModelRoutes,
  fixDeadInternalLinks,
} from '@/lib/preview/runtimeFixer';

// LLM repair pass bounds — keep a build from ever looping on a file the model
// cannot fix: at most this many passes, this many files repaired per pass.
const MAX_STATIC_REPAIR_PASSES = 2;
const MAX_REPAIR_PASSES = 3;
const REPAIR_FILES_PER_PASS = 10;
const MAX_TSC_REPAIR_PASSES = Number(process.env.MAX_TSC_REPAIR_PASSES || 4);
const TSC_REPAIR_FILES_PER_PASS = Number(process.env.TSC_REPAIR_FILES_PER_PASS || 16);
// Per-step runaway guards: a local model occasionally enters a repetition loop
// (seen live: ONE page step emitted >1MB before the client gave up) or hangs
// producing no tokens (Ollama lease expired mid-request, GPU pinned). Cap the
// step's output and abort when no tokens arrive for a while — the step then
// fails cleanly into the quarantine/retry path instead of freezing the build.
// 1 page per step so each page goes through buildPageMessages (which mandates
// the components/<page>/ decomposition). Concurrency (BUILD_CONCURRENCY) still
// runs several pages at once — this changes step granularity, not throughput.
const PAGE_BATCH_SIZE = Math.max(1, Number(process.env.PAGE_BATCH_SIZE || 1));
const API_BATCH_SIZE = Math.max(1, Number(process.env.API_BATCH_SIZE || 4));
const DEFAULT_STEP_OUTPUT_CHAR_CAP = Math.max(60_000, 38_000 * Math.max(PAGE_BATCH_SIZE, API_BATCH_SIZE));
const STEP_OUTPUT_CHAR_CAP = Math.max(
  20_000,
  Number(process.env.STEP_OUTPUT_CHAR_CAP || DEFAULT_STEP_OUTPUT_CHAR_CAP),
);
const STEP_IDLE_TIMEOUT_MS = Math.max(60_000, Number(process.env.STEP_IDLE_TIMEOUT_MS || 240_000));
// deepseek-r1:8b is a reasoning model — let it THINK before it writes each page/
// API file (better types, imports, structure → fewer bugs). Ollama streams the
// <think> tokens on a separate thinking channel, so only the final file content
// reaches the artifact parser. Mechanical line-level repairs keep thinking off
// for speed. Set OLLAMA_CODE_THINK=false to force fast, no-think generation.
const CODE_THINK = process.env.OLLAMA_CODE_THINK === 'true';
import { connectDB } from '@/lib/db/mongoose';
import { Project } from '@/lib/db/models/Project';
import { getAppType } from '@/lib/appTypes';
import { safeMongoDbName } from '@/lib/utils';
import { expandImplementationPlanAliases } from '@/lib/llm/planPrompts';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

async function ensureModelsIndex(projectId: string): Promise<void> {
  const files = await listProjectFiles(projectId);
  const modelFiles = files
    .filter(
      (file) =>
        file.startsWith('lib/models/') &&
        file.endsWith('.ts') &&
        file !== 'lib/models/index.ts',
    )
    .sort();
  if (!modelFiles.length) return;

  const content =
    modelFiles
      .map((file) => `export * from "./${file.split('/').pop()!.replace(/\.ts$/, '')}";`)
      .join('\n') + '\n';
  await writeProjectFileRaw(projectId, 'lib/models/index.ts', content);
}

function chunks<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

function isHeavySingletonPage(page: DerivedPage): boolean {
  const signal = `${page.route} ${page.title} ${page.purpose} ${page.kind}`;
  return (
    /\/$|\/pos\b|cashier|checkout|products?|catalog|inventory|orders?|profile|dashboard|reports?|analytics|suppliers?|purchase|returns?/i.test(
      signal,
    ) ||
    page.kind === 'list' ||
    page.kind === 'dashboard'
  );
}

function pageBatches(
  pages: DerivedPage[],
  size: number,
  retryAsSingleton = new Set<string>(),
): DerivedPage[][] {
  const out: DerivedPage[][] = [];
  let current: DerivedPage[] = [];
  const flush = () => {
    if (current.length) out.push(current);
    current = [];
  };

  for (const page of pages) {
    if (isHeavySingletonPage(page) || retryAsSingleton.has(page.filePath)) {
      flush();
      out.push([page]);
      continue;
    }
    current.push(page);
    if (current.length >= size) flush();
  }
  flush();
  return out;
}

/**
 * Strip schema definitions that fight MongoDB itself (deterministic,
 * idempotent, runs every build pass):
 * 1. A literal `id` field — models faithfully copy the SRS's `id: uuid`
 *    primary-key column, but Mongo already provides _id (+ the `id` virtual),
 *    and a required `id` makes EVERY insert/seed fail ("Path `id` is
 *    required" 500s on whole collections — seen live).
 * 2. EVERY `required: true` — the model's own seed/create code routinely
 *    omits fields it marked required (phone/email on School, user_id on
 *    Student — both seen live), turning whole features into silent 500s.
 *    Input quality is enforced where it belongs: the zod validation the
 *    prompts mandate in every API route. unique/refs/defaults all stay.
 */
async function sanitizeModels(projectId: string): Promise<void> {
  const files = await listProjectFiles(projectId);
  for (const rel of files) {
    if (
      !rel.startsWith('lib/models/') ||
      !rel.endsWith('.ts') ||
      rel === 'lib/models/index.ts'
    ) {
      continue;
    }
    const src = await readProjectFile(projectId, rel);
    if (!src) continue;
    let out = src
      .split('\n')
      .filter((line) => !/^\s*id\s*:\s*\{[^}]*\}\s*,?\s*$/.test(line))
      .join('\n');
    out = out
      .replace(/required\s*:\s*(?:true|\[[^\]]*\])\s*,\s*/g, '')
      .replace(/,\s*required\s*:\s*(?:true|\[[^\]]*\])/g, '')
      .replace(/required\s*:\s*(?:true|\[[^\]]*\])/g, '');
    if (out !== src) await writeProjectFileRaw(projectId, rel, out);
  }
}

async function ensureDbHelper(projectId: string): Promise<void> {
  const files = await listProjectFiles(projectId);
  if (files.includes('lib/db.ts')) return;
  await writeProjectFileRaw(
    projectId,
    'lib/db.ts',
    `import mongoose from "mongoose";
import dns from "dns";
const MONGODB_URI = process.env.MONGODB_URI as string;
const PUBLIC_DNS_SERVERS = ["8.8.8.8", "1.1.1.1"];
type MongooseCache = {
  conn: typeof mongoose | null;
  promise: Promise<typeof mongoose> | null;
};
const globalForMongoose = globalThis as typeof globalThis & {
  _mongoose?: MongooseCache;
};
const cached = globalForMongoose._mongoose ?? { conn: null, promise: null };
globalForMongoose._mongoose = cached;
function configuredDnsServers(): string[] {
  const value = process.env.DNS_SERVERS?.trim();
  if (!value || value.toLowerCase() === "auto") return [];
  if (value.toLowerCase() === "off") return [];
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}
async function connectOnce() {
  // Tolerate populate("x") on paths the schema names differently (x_id):
  // return docs unpopulated instead of throwing StrictPopulateError 500s.
  mongoose.set("strictPopulate", false);
  return mongoose.connect(MONGODB_URI, { bufferCommands: false });
}
function shouldRetryWithPublicDns(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /querySrv|ENOTFOUND|ETIMEOUT|ECONNREFUSED/i.test(msg);
}
export async function connectDB() {
  if (!MONGODB_URI) throw new Error("Please define MONGODB_URI");
  if (cached.conn) return cached.conn;
  if (!cached.promise) {
    cached.promise = (async () => {
      const explicitServers = configuredDnsServers();
      if (explicitServers.length) {
        try { dns.setServers(explicitServers); } catch {}
      }
      try {
        return await connectOnce();
      } catch (err) {
        if (explicitServers.length || !shouldRetryWithPublicDns(err)) throw err;
        try { dns.setServers(PUBLIC_DNS_SERVERS); } catch { throw err; }
        return connectOnce();
      }
    })();
  }
  cached.conn = await cached.promise;
  return cached.conn;
}
`,
  );
}

export async function POST(req: NextRequest) {
  let body: { projectId?: string };
  try {
    body = await req.json();
  } catch {
    return new Response('Invalid JSON body', { status: 400 });
  }

  const projectId = body.projectId;
  if (!projectId || !/^[a-z0-9_-]+$/.test(projectId)) {
    return new Response('Invalid projectId', { status: 400 });
  }

  // Load the plans this build is driven by — from MongoDB, or from disk
  // (_plans/*.md + _meta.json) when Mongo is unreachable (offline-friendly).
  let appTypeKey: string | undefined;
  let hasBackend = false;
  let plans: Record<string, string> = {};
  let name = 'app';

  let project: Record<string, unknown> | null = null;
  try {
    await connectDB();
    project = await Project.findById(projectId).lean();
  } catch (e) {
    console.error('[build] DB read failed:', e);
  }

  if (project) {
    appTypeKey = project.appType as string;
    hasBackend = !!(project.hasBackend as boolean);
    plans = (project.plans as Record<string, string>) ?? {};
    name = (project.name as string) || 'app';
  } else {
    const disk = await readPlansFromDisk(projectId);
    if (!disk) {
      return new Response('Project (with plans) not found', { status: 404 });
    }
    appTypeKey = disk.appType;
    hasBackend = disk.hasBackend;
    plans = disk.plans;
    name = disk.name;
  }

  // Disk checkpoints are the most reliable source after long streaming plans:
  // a client can disconnect, Mongo can lag, or a stage can checkpoint to disk
  // before DB persistence finishes. Merge disk plans over Mongo so the build
  // never silently uses a partial page list.
  const diskPlans = await readPlansFromDisk(projectId);
  if (diskPlans) {
    appTypeKey = diskPlans.appType || appTypeKey;
    hasBackend = diskPlans.hasBackend;
    name = diskPlans.name || name;
    plans = { ...plans, ...diskPlans.plans };
  }
  plans = expandImplementationPlanAliases(plans);

  const appType = getAppType(appTypeKey) ?? getAppType('enterprise')!;
  hasBackend =
    hasBackend ||
    Boolean(
      plans.backend?.trim() ||
        plans.datatypes?.trim() ||
        /MongoDB|Mongoose|Route Handlers|\/api\//i.test(Object.values(plans).join('\n')),
    );

  // PER-PROJECT BUILD LOCK: two builds writing the same project at once
  // contend for Ollama and race the quality gates on the same files (seen
  // live: a still-open browser build + a curl resume degraded both). The lock
  // lives on globalThis so it survives dev-server module recompiles.
  const buildLocks = ((globalThis as typeof globalThis & {
    _buildLocks?: Set<string>;
  })._buildLocks ??= new Set<string>());
  if (buildLocks.has(projectId)) {
    return new Response(
      'A build for this project is already running. Wait for it to finish (or stop it) before starting another.',
      { status: 409 },
    );
  }
  buildLocks.add(projectId);

  // Explicit-cancel registry. A DROPPED CLIENT CONNECTION must NOT cancel a
  // build — that was the #1 cause of "stuck for hours" half-built projects: the
  // browser tab closed / preview navigated / session ended, the HTTP stream
  // aborted, and the build died at (say) 33/33 pages needing a manual restart.
  // Now the build runs to completion inside the stream's start() regardless of
  // the client; only an explicit Stop (POST /api/build/stop) sets this flag.
  const buildStops = ((globalThis as typeof globalThis & {
    _buildStops?: Set<string>;
  })._buildStops ??= new Set<string>());
  buildStops.delete(projectId); // clear any stale stop from a previous run

  const encoder = new TextEncoder();
  // Best-effort enqueue: once the client is gone, enqueue throws — we swallow
  // it and let the build keep writing files to disk server-side.
  const emit = (
    controller: ReadableStreamDefaultController<Uint8Array>,
    obj: unknown,
  ) => {
    try {
      controller.enqueue(encoder.encode(JSON.stringify(obj) + '\n'));
    } catch {
      /* client disconnected — keep building, just stop streaming to it */
    }
  };

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      // Thrown to unwind the whole build when the model backend is unreachable.
      class BuildAbort extends Error {}

      let stepNo = 0;
      // Shared conversation so each step REMEMBERS what earlier steps produced
      // (like a real Ollama chat) — keeps imports, exports and style consistent.
      // Windowed to system + the most recent turns so it fits the context.
      const convo: ChatMessage[] = [];

      const isPageFile = (filePath: string) =>
        filePath === 'app/page.tsx' || /^app\/.+\/page\.(tsx|jsx)$/.test(filePath);

      const repairKeepsSubstance = (
        filePath: string,
        before: string,
        after: string,
      ): boolean => {
        const nextLength = after.trim().length;
        if (!isPageFile(filePath)) return nextLength > 40;
        const previousLength = before.trim().length;
        const minimum = Math.max(1200, Math.floor(previousLength * 0.4));
        return nextLength >= minimum;
      };

      const streamRepair = async (system: string, user: string): Promise<string> => {
        let out = '';
        // Idle watchdog: a hung/dead Ollama during a repair used to FREEZE the
        // whole build forever (no timeout on the repair stream). Abort the call
        // if no token arrives for STEP_IDLE_TIMEOUT_MS; the caller then falls
        // back / skips the file and the build keeps moving instead of hanging.
        const ac = new AbortController();
        let idle: ReturnType<typeof setTimeout> | null = null;
        const arm = () => {
          if (idle) clearTimeout(idle);
          idle = setTimeout(() => ac.abort(), STEP_IDLE_TIMEOUT_MS);
        };
        try {
          arm();
          for await (const delta of streamOllamaChat(
            [
              { role: 'system', content: system },
              { role: 'user', content: user },
            ],
            { model: OLLAMA_CODE_MODEL, context: 'code', think: false, signal: ac.signal },
          )) {
            out += delta;
            arm();
          }
        } catch {
          /* hung, aborted, or failed — return whatever streamed so far */
        } finally {
          if (idle) clearTimeout(idle);
        }
        return out;
      };

      const repairOneFile = async (
        filePath: string,
        fileContent: string,
        issues: string[],
        kind: 'syntax' | 'static' | 'tsc',
      ): Promise<boolean> => {
        const manifest = await readProjectManifest(projectId);

        // 1. LINE-LEVEL first: ask for minimal SEARCH/REPLACE edits and apply
        //    them surgically. Fast (few lines out) and it can never lose the
        //    working parts of the file. Only accept if it actually resolves the
        //    file's syntax and keeps the file's substance.
        const em = buildEditRepairMessages({ filePath, fileContent, issues, manifest });
        const editText = await streamRepair(em.system, em.user);
        const blocks = parseEditBlocks(editText);
        if (blocks.length > 0) {
          const { content, applied } = applyEditBlocks(fileContent, blocks);
          if (
            applied > 0 &&
            content !== fileContent &&
            content.trim().length > 5 &&
            repairKeepsSubstance(filePath, fileContent, content) &&
            syntaxErrors(filePath, content).length === 0
          ) {
            await writeProjectFiles(projectId, [{ path: filePath, content }]);
            emit(controller, { type: 'repair', kind: `edit-${kind}`, files: [filePath] });
            return true;
          }
        }

        // 2. FALLBACK: full-file regeneration (structural fixes the edit form
        //    can't express, or when no edit block matched).
        const rm = buildRepairMessages({ filePath, fileContent, issues, manifest });
        const repairedText = await streamRepair(rm.system, rm.user);
        const repaired = parseSingleFileRepair(repairedText, filePath);
        if (!repaired || repaired.content.trim().length <= 5) return false;
        if (!repairKeepsSubstance(filePath, fileContent, repaired.content)) return false;
        if (syntaxErrors(repaired.path, repaired.content).length > 0) return false;
        await writeProjectFiles(projectId, [repaired]);
        emit(controller, { type: 'repair', kind: `step-${kind}`, files: [filePath] });
        return true;
      };

      const gateWrittenFiles = async (paths: string[], n: number): Promise<string[]> => {
        const targets = new Set(
          paths
            .map((p) => p.replace(/\\/g, '/').replace(/^\/+/, ''))
            .filter((p) => /\.(ts|tsx|js|jsx|mjs)$/.test(p)),
        );
        if (!targets.size) return [];

        emit(controller, { type: 'quality', n, status: 'start', files: [...targets] });

        // ONE generation per page — no per-page LLM repair, no quarantine.
        // This used to run up to 6 LLM repair passes (syntax → static → page
        // quality, each re-prompting Gemma) AND delete+regenerate any page that
        // still failed, which is exactly the "same page generated over and over"
        // loop that made a 3-4 page app take an hour. Real bugs are now fixed at
        // runtime by the preview terminal bug-fixer against the live dev server.
        // A single deterministic mechanical sweep still runs (broken arrows,
        // missing imports, stray fences) — fast, no model call. The page is kept
        // as-is regardless, so it never gets deleted and regenerated.
        await autofixFiles(projectId, [...targets]).catch(() => []);
        const allFiles = await readProjectFiles(projectId);
        const byPath = new Map(allFiles.map((file) => [file.path, file.content ?? '']));
        const syntaxIssues = [...targets].flatMap((file) =>
          syntaxErrors(file, byPath.get(file) ?? '').map((issue) => `${file}: ${issue}`),
        );
        const staticIssues = analyzeProject(allFiles)
          .filter((issue) => targets.has(issue.file))
          .flatMap((issue) => issue.issues.map((detail) => `${issue.file}: ${detail}`));
        const remaining = [...syntaxIssues, ...staticIssues];
        emit(controller, { type: 'quality', n, status: 'done', remaining });
        return remaining;
      };

      // Per-file budget. With the gate now non-destructive, a page that WROTE a
      // file is always kept — this budget only bounds pages that produced NO
      // output at all (model answered in prose), giving them one extra attempt
      // before the coverage report lists them. It is NOT a repair/regenerate
      // loop for already-generated pages.
      const MAX_FILE_ATTEMPTS = Math.max(1, Number(process.env.MAX_FILE_ATTEMPTS || 2));
      const fileAttempts = new Map<string, number>();
      const bumpAttempt = (file: string) =>
        fileAttempts.set(file, (fileAttempts.get(file) ?? 0) + 1);
      const attemptsExhausted = (file: string) =>
        (fileAttempts.get(file) ?? 0) >= MAX_FILE_ATTEMPTS;

      // How many independent steps (pages / API routes) may generate at once.
      // Matches Ollama's OLLAMA_NUM_PARALLEL: the GPU batches these sequences,
      // reading the model weights once for all of them, so total throughput
      // rises ~2-2.5x with NO change to any single step's prompt or output.
      const BUILD_CONCURRENCY = Math.max(1, Number(process.env.BUILD_CONCURRENCY || 3));

      // Run fn over items with a bounded number of concurrent workers.
      const runConcurrent = async <T>(
        items: T[],
        limit: number,
        fn: (item: T) => Promise<void>,
      ): Promise<void> => {
        let cursor = 0;
        const workers = Array.from(
          { length: Math.min(Math.max(1, limit), items.length) },
          async () => {
            while (cursor < items.length) {
              const item = items[cursor++];
              await fn(item);
            }
          },
        );
        await Promise.all(workers);
      };

      // The GENERATION (token streaming) of parallel steps overlaps freely, but
      // the FILE-MUTATING tail — writeProjectFiles + the project-wide quality
      // gate (autofix rewrites many files) + quarantine deletes — must run one
      // at a time or concurrent steps corrupt each other's files. This chain is
      // that mutex; it serializes only the fast tail, not the slow generation.
      let gateChain: Promise<unknown> = Promise.resolve();
      const withGateLock = <T>(fn: () => Promise<T>): Promise<T> => {
        const run = gateChain.then(fn, fn);
        gateChain = run.then(
          () => undefined,
          () => undefined,
        );
        return run;
      };

      const isFoundationOwnedFile = (filePath: string): boolean => {
        const p = filePath.replace(/\\/g, '/').replace(/^\/+/, '');
        return (
          p === 'credentials.txt' ||
          p === 'package.json' ||
          p === 'tsconfig.json' ||
          p === 'next.config.ts' ||
          p === 'next.config.js' ||
          p === 'postcss.config.mjs' ||
          p.startsWith('lib/db') ||
          p.startsWith('lib/models/')
        );
      };

      const runStep = async (
        messages: { system: string; user: string },
        label: string,
        expectedFiles: string[] = [],
        opts: { critical?: boolean; isolated?: boolean } = {},
      ): Promise<void> => {
        const critical = opts.critical === true;
        // Isolated steps get their OWN fresh [system,user] conversation instead
        // of the shared running one, so they can run concurrently and never
        // cross-contaminate. Quality is preserved: each page/API already gets
        // the full plans + manifest (exact export names) + design brief, so a
        // page built "as if first" produces the same code — no page imports
        // another page. Only the sequential foundation/shell steps share convo.
        const isolated = opts.isolated === true;
        // Explicit Stop only — a dropped client connection never reaches here.
        if (buildStops.has(projectId)) throw new BuildAbort();
        stepNo += 1;
        const n = stepNo;
        const conv: ChatMessage[] = isolated ? [] : convo;
        if (isolated) {
          conv.push({ role: 'system', content: messages.system });
          conv.push({ role: 'user', content: messages.user });
        } else {
          if (conv.length === 0) {
            conv.push({ role: 'system', content: messages.system });
          }
          conv.push({ role: 'user', content: messages.user });
        }
        emit(controller, { type: 'step', n, label, status: 'start' });

        let full = '';
        let thoughtSignalled = false;
        // Watchdog: abort THIS step (not the build) on runaway output or a
        // token drought, then fall through with whatever streamed so far.
        // NOT wired to the client connection — the build survives disconnects.
        const stepAc = new AbortController();
        let watchdogTripped = false;
        let idleTimer: ReturnType<typeof setTimeout> | null = null;
        const armIdle = () => {
          if (idleTimer) clearTimeout(idleTimer);
          idleTimer = setTimeout(() => {
            watchdogTripped = true;
            stepAc.abort();
          }, STEP_IDLE_TIMEOUT_MS);
        };
        try {
          armIdle();
          for await (const delta of streamOllamaChat(conv, {
            // deepseek-r1 reasons first (routed to the thinking channel) then
            // emits the file — CODE_THINK gates this per OLLAMA_CODE_THINK.
            model: OLLAMA_CODE_MODEL,
            context: 'code',
            think: CODE_THINK,
            signal: stepAc.signal,
            onThinking: () => {
              armIdle();
              if (!thoughtSignalled) {
                thoughtSignalled = true;
                emit(controller, { type: 'thinking', n });
              }
            },
          })) {
            full += delta;
            armIdle();
            // Stream the raw code deltas so the workbench can show the file
            // being written live, bolt-style.
            emit(controller, { type: 'delta', n, text: delta });
            if (full.length > STEP_OUTPUT_CHAR_CAP) {
              watchdogTripped = true;
              stepAc.abort();
              break;
            }
          }
        } catch (err) {
          if (buildStops.has(projectId)) throw new BuildAbort();
          if (!watchdogTripped) {
            emit(controller, {
              type: 'step',
              n,
              label,
              status: 'error',
              message: err instanceof Error ? err.message : String(err),
            });
            if (!critical && isolated) {
              for (const file of expectedFiles) bumpAttempt(file);
              return;
            }
            throw new BuildAbort();
          }
          // watchdog abort: keep the partial output and continue below.
        } finally {
          if (idleTimer) clearTimeout(idleTimer);
        }
        if (watchdogTripped) {
          emit(controller, {
            type: 'step',
            n,
            label,
            status: 'watchdog',
            message: `step aborted by watchdog at ${full.length} chars (runaway output or idle timeout); salvaging complete files`,
          });
        }

        // Remember this step's output, then window the conversation so it
        // never outgrows the context (keep system + the last few turns).
        conv.push({ role: 'assistant', content: full });
        if (conv.length > 7) conv.splice(1, conv.length - 7);

        let artifact = parseArtifact(full);
        if (artifact.files.length === 0) {
          // The model forgot the <file> wrapper — recover path-commented
          // fenced blocks instead of discarding the whole step's output.
          const fenced = parseFencedFiles(full);
          if (fenced.length > 0) artifact = { ...artifact, files: fenced };
        }
        if (artifact.files.length === 0 && /```/.test(full)) {
          // Still nothing usable but the model DID write fenced code — ask it
          // once to re-emit the same files in the required <file> format.
          conv.push({
            role: 'user',
            content:
              'Your previous answer lost every file because it used markdown code fences instead of the required format. Re-emit ALL the files from your previous answer RIGHT NOW as <file path="relative/path">FULL file content</file> blocks. Output ONLY <file> blocks — no prose, no ``` fences, no explanations.',
          });
          let retry = '';
          try {
            for await (const delta of streamOllamaChat(conv, {
              model: OLLAMA_CODE_MODEL,
              context: 'code',
              think: false,
            })) {
              retry += delta;
              emit(controller, { type: 'delta', n, text: delta });
            }
          } catch {
            /* fall through with whatever we have */
          }
          conv.push({ role: 'assistant', content: retry });
          if (conv.length > 7) conv.splice(1, conv.length - 7);
          artifact = parseArtifact(retry);
          if (artifact.files.length === 0) {
            const fenced = parseFencedFiles(retry);
            if (fenced.length > 0) artifact = { ...artifact, files: fenced };
          }
        }
        // Serialize the file-mutating tail: concurrent isolated steps stream in
        // parallel but must write + gate + quarantine one at a time (the gate's
        // autofix rewrites files project-wide).
        await withGateLock(async () => {
          let written = 0;
          let stepFiles = artifact.files;
          if (isolated && stepFiles.length > 0) {
            const dropped = stepFiles
              .map((file) => file.path)
              .filter(isFoundationOwnedFile);
            if (dropped.length > 0) {
              stepFiles = stepFiles.filter((file) => !isFoundationOwnedFile(file.path));
              emit(controller, {
                type: 'scope-filter',
                n,
                label,
                dropped,
                message:
                  'Dropped foundation-owned file(s) from an isolated page/API step; data models and scaffold files are generated only by the foundation/shell phases.',
              });
            }
          }
          const paths = stepFiles.map((f) => f.path);
          if (stepFiles.length > 0) {
            written = await writeProjectFiles(projectId, stepFiles);
            const remaining = await gateWrittenFiles([...new Set([...paths, ...expectedFiles])], n);
            if (remaining.length) {
              const message = `Quality gate failed for generated files:\n${remaining.join('\n')}`;
              // NEVER wedge the whole build on one bad file: quarantine the
              // offenders (delete them from disk) so the page/API loops re-derive
              // and rebuild them fresh, then CONTINUE with the rest of the build.
              // Only foundation steps (data layer / app shell) abort the run —
              // everything depends on those.
              const badFiles = [
                ...new Set(
                  remaining
                    .map((entry) => entry.split(':')[0].trim())
                    .filter((p) => p.includes('/')),
                ),
              ];
              const removed: string[] = [];
              for (const file of badFiles) {
                bumpAttempt(file);
                if (await deleteProjectFile(projectId, file)) removed.push(file);
              }
              emit(controller, { type: 'quarantine', n, files: removed, message });
              emit(controller, { type: 'step', n, label, status: 'error', message });
              if (critical) {
                emit(controller, { type: 'error', message });
                throw new BuildAbort();
              }
              // Drop this failed step's turns so the model's own broken output
              // never poisons later steps (shared-convo path only).
              if (!isolated) conv.splice(conv.length - 2, 2);
              return;
            }
            // Isolated (concurrent) steps skip the per-step dependency sync —
            // it writes package.json and would race sibling steps; the caller
            // syncs once per concurrency wave instead.
            if (!isolated) {
              const dependencyReport = await syncGeneratedDependencies(projectId);
              emit(controller, { type: 'dependencies', n, report: dependencyReport });
            }
          }
          if (expectedFiles.length > 0) {
            const diskPaths = await listProjectFiles(projectId);
            const missingExpected = expectedFiles.filter((file) => !diskPaths.includes(file));
            if (missingExpected.length > 0) {
              const message = `Step did not produce required file(s): ${missingExpected.join(', ')}`;
              for (const file of missingExpected) bumpAttempt(file);
              emit(controller, { type: 'step', n, label, status: 'error', message, files: paths });
              if (critical) {
                emit(controller, { type: 'error', message });
                throw new BuildAbort();
              }
              if (!isolated) conv.splice(conv.length - 2, 2);
              return;
            }
          }
          emit(controller, { type: 'step', n, label, status: 'done', written, files: paths });
        });
      };

      try {
        // 1. Scaffold only. NO permanent design template — the model invents
        //    and implements the design itself (globals.css tokens + usage).
        emit(controller, { type: 'scaffold', status: 'start' });
        await scaffoldProject(projectId);
        await ensureScaffoldAssets(projectId);
        const brief = designDirection();
        emit(controller, { type: 'scaffold', status: 'done' });

        // Self-heal: if an earlier (aborted) run left syntactically broken
        // generated files on disk, autofix what's mechanical and QUARANTINE the
        // rest, so this resume rebuilds them instead of re-failing every gate.
        {
          const preBroken = await findBrokenFiles(projectId);
          if (preBroken.length) {
            await autofixProject(projectId).catch(() => []);
            const stillBroken = await findBrokenFiles(projectId);
            const removed: string[] = [];
            for (const bad of stillBroken) {
              if (await deleteProjectFile(projectId, bad.rel)) removed.push(bad.rel);
            }
            if (removed.length) {
              emit(controller, {
                type: 'quarantine',
                files: removed,
                message: `Removed ${removed.length} broken file(s) from a previous run; they will be rebuilt.`,
              });
            }
          }
        }

        const generateMissingApiRoutes = async (labelPrefix: string) => {
          if (!hasBackend) return;
          for (;;) {
            if (stepNo >= MAX_BUILD_STEPS - 1) break;
            const files = await readProjectFiles(projectId);
            const expectedApiFiles = unifyDynamicSegments(
              [...plannedApiFilesFromPlans(plans), ...referencedApiFiles(files)],
              files.map((file) => file.path),
            ).sort();
            const paths = files.map((file) => file.path);
            const missingApis = expectedApiFiles.filter(
              (file) => !paths.includes(file) && !attemptsExhausted(file),
            );
            if (!missingApis.length) break;
            const templated = await generateDeterministicApis(projectId, missingApis);
            if (templated.written.length || templated.skipped.length) {
              emit(controller, {
                type: 'api-template',
                label: labelPrefix,
                written: templated.written,
                skipped: templated.skipped,
              });
            }
            if (templated.written.length) {
              await autofixFiles(projectId, templated.written).catch(() => []);
            }
            const unresolvedApis = templated.skipped.filter(
              (file) => !attemptsExhausted(file),
            );
            if (!unresolvedApis.length) {
              const depReport = await syncGeneratedDependencies(projectId);
              emit(controller, { type: 'dependencies', report: depReport });
              continue;
            }
            const slotsLeft = Math.max(1, MAX_BUILD_STEPS - 1 - stepNo);
            const wave = chunks(unresolvedApis.slice(0, slotsLeft * API_BATCH_SIZE), API_BATCH_SIZE);
            const manifest = await readProjectManifest(projectId);
            await runConcurrent(wave, BUILD_CONCURRENCY, async (batch) => {
              await runStep(
                buildApiBatchMessages({
                  appType,
                  hasBackend,
                  designBrief: brief,
                  plans,
                  manifest,
                  apiFiles: batch,
                }),
                `${labelPrefix} batch ${batch
                  .map((file) => file.replace(/^app\/api\//, '/api/'))
                  .join(', ')}`,
                batch,
                { isolated: true },
              );
            });
            const depReport = await syncGeneratedDependencies(projectId);
            emit(controller, { type: 'dependencies', report: depReport });
          }
        };

        // 1b. Backend reliability kit: seed the UNIVERSAL, correct-by-design
        //     plumbing the model gets wrong (API response shape, password
        //     hashing, JWT session, and — when the plan needs auth — the whole
        //     User model + register/login/logout/me routes). Seeded + protected
        //     BEFORE the model generates anything, so it imports these instead of
        //     rewriting them (the register/login bug class disappears). Only when
        //     there's a backend; auth files only when the plan signals auth.
        if (hasBackend) {
          const kit = await seedBackendKit(projectId, plans);
          protectPaths(kit.paths);
          emit(controller, { type: 'backend-kit', seeded: kit.seeded, auth: kit.auth });
        }

        // 2. Data layer (backend only): db + every Mongoose model — its own step.
        if (hasBackend) {
          const pre = await listProjectFiles(projectId);
          const hasModels = pre.some(
            (p) => p.startsWith('lib/models/') && p.endsWith('.ts') && p !== 'lib/models/index.ts',
          );
          if (!pre.includes('lib/db.ts') || !hasModels) {
            await runStep(
              buildFoundationMessages({
                appType,
                hasBackend,
                designBrief: brief,
                plans,
                manifest: await readProjectManifest(projectId),
              }),
              'Data layer',
              [],
              { critical: true },
            );
          }
          await ensureDbHelper(projectId);
          await ensureModelsIndex(projectId);
          await sanitizeModels(projectId);
          {
            const files = await readProjectFiles(projectId);
            const paths = files.map((file) => file.path);
            const plannedApis = unifyDynamicSegments(plannedApiFilesFromPlans(plans), paths).sort();
            const missingPlannedApis = plannedApis.filter(
              (file) => !paths.includes(file) && !attemptsExhausted(file),
            );
            if (missingPlannedApis.length) {
              const templated = await generateDeterministicApis(projectId, missingPlannedApis);
              emit(controller, {
                type: 'api-template',
                label: 'Planned API templates',
                written: templated.written,
                skipped: templated.skipped,
              });
              if (templated.written.length) {
                await autofixFiles(projectId, templated.written).catch(() => []);
                const depReport = await syncGeneratedDependencies(projectId);
                emit(controller, { type: 'dependencies', report: depReport });
              }
            }
          }
        }

        // 3. App shell: shared nav (per the plan's decision) + base UI + layout
        //    in its OWN focused round, so navigation/layout never gets dropped
        //    when many models fill the response (the cause of the missing navbar
        //    earlier). Re-runs while: no components/ yet OR app/layout.tsx is
        //    still the create-next-app default (so a failed shell round retries),
        //    regardless of whether the plan chose a navbar, sidebar, or none.
        {
          const pre = await listProjectFiles(projectId);
          const layoutContent = await readProjectFile(projectId, 'app/layout.tsx');
          // The scaffold default sets title "Create Next App"; once the shell
          // step replaces layout.tsx that marker is gone. This works whether the
          // plan chose a navbar, a sidebar, or no global nav at all.
          const layoutReplaced =
            layoutContent.length > 0 && !/Create Next App/i.test(layoutContent);
          const shellDone =
            pre.some((p) => p.startsWith('components/')) && layoutReplaced;
          if (!shellDone) {
            await runStep(
              buildShellMessages({
                appType,
                hasBackend,
                designBrief: brief,
                plans,
                manifest: await readProjectManifest(projectId),
              }),
              'App shell',
              ['app/layout.tsx'],
              { critical: true },
            );
          }
        }

        // 3. One focused step per page (each with its own distinct layout).
        //    Pages already on disk are skipped, so re-running Build resumes
        //    where it left off and covers more of the plan on each pass.
        const pages = derivePages(
          plans.pages || '',
          Number(process.env.MAX_BUILD_PAGES || 60),
        );
        const remainingPages = async (ignoreAttempts = false) => {
          const paths = await listProjectFiles(projectId);
          return pages.filter(
            (page) =>
              !paths.includes(page.filePath) &&
              (ignoreAttempts || !attemptsExhausted(page.filePath)),
          );
        };

        const runPageCatchup = async (
          opts: { ignoreAttempts?: boolean; maxWaves?: number } = {},
        ) => {
          let waves = 0;
          for (;;) {
            if (stepNo >= MAX_BUILD_STEPS - 1) break; // leave room for the final step
            if (opts.maxWaves != null && waves >= opts.maxWaves) break;
            const pending = await remainingPages(!!opts.ignoreAttempts);
            if (!pending.length) break;

            const slotsLeft = Math.max(1, MAX_BUILD_STEPS - 1 - stepNo);
            const retryAsSingleton = new Set(
              opts.ignoreAttempts
                ? pending.map((page) => page.filePath)
                : [...fileAttempts.entries()]
                    .filter(([, attempts]) => attempts > 0)
                    .map(([file]) => file),
            );
            const wave = pageBatches(
              pending.slice(0, slotsLeft * PAGE_BATCH_SIZE),
              PAGE_BATCH_SIZE,
              retryAsSingleton,
            );
            // ONE manifest snapshot for the whole wave — pages don't import each
            // other, so they don't need to see each other's just-written files.
            const manifest = await readProjectManifest(projectId);
            await runConcurrent(wave, BUILD_CONCURRENCY, async (batch) => {
              await runStep(
                batch.length === 1
                  ? buildPageMessages({
                      appType,
                      hasBackend,
                      designBrief: brief,
                      plans,
                      manifest,
                      page: batch[0],
                      pageSpec: extractPageSpec(plans.pagewise || '', batch[0].route),
                    })
                  : buildPageBatchMessages({
                      appType,
                      hasBackend,
                      designBrief: brief,
                      plans,
                      manifest,
                      pages: batch.map((page) => ({
                        page,
                        pageSpec: extractPageSpec(plans.pagewise || '', page.route),
                      })),
                    }),
                batch.length === 1
                  ? `Page ${batch[0].route}`
                  : `Pages ${batch.map((page) => page.route).join(', ')}`,
                batch.map((page) => page.filePath),
                { isolated: true },
              );
            });
            // Sync deps once per wave (isolated steps skip the per-step sync);
            // failed pages are re-derived and retried on the next loop pass until
            // their attempt budget runs out.
            const depReport = await syncGeneratedDependencies(projectId);
            emit(controller, { type: 'dependencies', report: depReport });
            waves += 1;
          }
        };

        await runPageCatchup();

        // 4. Backend API route handlers: generate explicitly from the Backend
        //    Plan before the generic final pass, otherwise the model often
        //    answers "done" in prose and leaves the backend surface missing.
        await generateMissingApiRoutes('API');
        await runPageCatchup({ ignoreAttempts: true, maxWaves: 1 });

        // 5. Final wiring: remaining components + validation/shared glue.
        // Run this only when there is a concrete missing artifact. Open-ended
        // "final pass" prompts are the easiest place for a local model to drift
        // into prose loops on resumes, and the deterministic gates below are
        // better at mechanical cleanup once pages/APIs already exist.
        {
          const manifest = await readProjectManifest(projectId);
          const rawPaths = await listProjectFiles(projectId);
          const manifestSet = new Set(rawPaths);
          const expectedApiFiles = hasBackend
            ? unifyDynamicSegments(
                [
                  ...plannedApiFilesFromPlans(plans),
                  ...referencedApiFiles(await readProjectFiles(projectId)),
                ],
                rawPaths,
              )
            : [];
          const missingPages = pages.filter((page) => !manifestSet.has(page.filePath));
          const missingApis = expectedApiFiles.filter((file) => !manifestSet.has(file));
          const needsCredentials =
            /auth|rbac|role|login|register|permission/i.test(Object.values(plans).join('\n')) &&
            !manifestSet.has('credentials.txt');
          const forceFinal = process.env.ALWAYS_RUN_FINAL_WIRING === '1';

          if (forceFinal) {
            await runStep(
              buildFinalMessages({
                appType,
                hasBackend,
                designBrief: brief,
                plans,
                manifest,
              }),
              'Finish & wire up',
            );
          } else {
            emit(controller, {
              type: 'step',
              label: 'Finish & wire up',
              status: 'skipped',
              reason:
                missingPages.length || missingApis.length || needsCredentials
                  ? `Skipped LLM final wiring by default (${missingPages.length} missing page(s), ${missingApis.length} missing API route(s), credentials needed: ${needsCredentials}). Concrete page/API catch-up and deterministic gates remain active. Set ALWAYS_RUN_FINAL_WIRING=1 to force this pass.`
                  : 'No missing pages, API routes, or credentials; deterministic gates will finish the build.',
            });
          }
        }

        // 5. Deterministic repair pass: fix the mechanical mistakes a local
        //    model makes that would otherwise crash the app at runtime
        //    (missing/hallucinated lucide icons, missing cn import).
        emit(controller, { type: 'autofix', status: 'start' });
        const fixes = await autofixProject(projectId).catch(() => [] as string[]);
        emit(controller, { type: 'autofix', status: 'done', fixes });

        // Deterministic CASCADE-BREAKERS at BUILD time (not just preview): a
        // decomposed page importing a section from the wrong path or one the
        // model forgot to write, or a route importing a non-existent model, is a
        // Module-not-found that 500s the WHOLE app graph. Remap/stub them here so
        // the app compiles before it is ever previewed.
        const compFixes = await fixComponentImports(projectId, () => {}).catch(() => [] as string[]);
        const routeStubs = await fixMissingModelRoutes(projectId, () => {}).catch(() => [] as string[]);
        const linkStubs = await fixDeadInternalLinks(projectId, () => {}).catch(() => [] as string[]);
        if (compFixes.length || routeStubs.length || linkStubs.length) {
          emit(controller, {
            type: 'autofix',
            status: 'done',
            fixes: [...compFixes, ...routeStubs, ...linkStubs],
          });
        }

        // 6. Completeness catch-up — NOT bug-fixing. Make sure every planned
        //    API route and page actually exists on disk. Real bug-fixing no
        //    longer happens in this pipeline: the slow, speculative LLM repair
        //    loops (static → syntax → quality → tsc, each re-prompting Gemma to
        //    GUESS at errors) were removed by design. They wasted minutes on
        //    errors the running app reports exactly. Instead, after the build
        //    the preview dev server is started and a page-check agent walks the
        //    live app, reads the terminal, and fixes only what actually breaks
        //    (npm install for a missing lib, one-file Gemma repair for a code
        //    error). The fast deterministic autofix above still runs to prevent
        //    the mechanical mistakes up front.
        await generateMissingApiRoutes('API catch-up');
        await runPageCatchup({ ignoreAttempts: true, maxWaves: 1 });
        // Final mechanical sweep after catch-up may have written new files.
        await autofixProject(projectId).catch(() => []);
        emit(controller, { type: 'repair', status: 'done', remaining: [] });

        await writeProjectEnv(projectId, safeMongoDbName(name));
        await writeCredentialsTxt(projectId, name, plans);
        if (hasBackend) {
          // Guarantee the credentials.txt accounts actually exist in the app's
          // database — the model's login route only CHECKS credentials.
          try {
            const seedReport = await ensureSeededUsers(projectId, plans);
            emit(controller, { type: 'seed-users', ...seedReport });
          } catch (err) {
            emit(controller, {
              type: 'seed-users',
              seeded: 0,
              reason: err instanceof Error ? err.message : String(err),
            });
          }
        }
        let finalFileObjects = await readProjectFiles(projectId);
        const dependencyReport = await syncGeneratedDependencies(projectId, finalFileObjects);
        emit(controller, { type: 'dependencies', report: dependencyReport });
        finalFileObjects = await readProjectFiles(projectId);
        const audit = auditGeneratedProject({
          files: finalFileObjects,
          pages,
          plans,
          hasBackend,
        });
        emit(controller, { type: 'audit', report: audit });
        try {
          await connectDB();
          await Project.findByIdAndUpdate(projectId, {
            $set: { updatedAt: new Date(), audit },
          });
        } catch {
          /* best-effort */
        }

        const blockingAuditChecks = audit.checks.filter(
          (check) =>
            !check.ok &&
            ['Planned API coverage', 'Fetched API coverage', 'Syntax safety', 'Import and client/server safety'].includes(
              check.label,
            ),
        );
        if (blockingAuditChecks.length > 0) {
          const message = [
            'Build stopped because final bug gates failed.',
            ...blockingAuditChecks.flatMap((check) =>
              check.details.slice(0, 6).map((detail) => `${check.label}: ${detail}`),
            ),
          ].join('\n');
          emit(controller, { type: 'error', message });
          throw new BuildAbort();
        }

        const finalFiles = finalFileObjects.map((f) => f.path);
        // Plan-coverage: how many planned pages actually exist on disk now.
        const builtPages = pages.filter((p) => finalFiles.includes(p.filePath));
        const missingPages = pages.filter((p) => !finalFiles.includes(p.filePath));
        emit(controller, {
          type: 'coverage',
          planned: pages.length,
          built: builtPages.length,
          missing: missingPages.map((p) => p.route),
        });
        if (missingPages.length > 0) {
          const message = `Build incomplete: ${missingPages.length} planned page(s) were not generated: ${missingPages
            .slice(0, 20)
            .map((p) => p.route)
            .join(', ')}${missingPages.length > 20 ? ', ...' : ''}`;
          emit(controller, { type: 'error', message });
          throw new BuildAbort();
        }
        emit(controller, {
          type: 'done',
          files: finalFiles.length,
          planned: pages.length,
          built: builtPages.length,
        });

        // Auto preview: start the generated app's dev server and let the
        // page-check + terminal bug-fixer walk every page, reading real errors
        // off the running terminal and fixing only those (npm install for a
        // missing lib, one-file Gemma repair for a code error). This replaces
        // the removed post-generation LLM repair loops. Fire-and-forget — it
        // runs server-side after this build stream closes.
        try {
          const { startPreview } = await import('@/lib/preview/manager');
          startPreview(projectId, { autoFix: true });
          emit(controller, {
            type: 'preview',
            status: 'starting',
            message: 'Auto preview + terminal bug-fixer started',
          });
        } catch (e) {
          emit(controller, {
            type: 'preview',
            status: 'error',
            message: e instanceof Error ? e.message : String(e),
          });
        }
      } catch (err) {
        if (!(err instanceof BuildAbort)) {
          emit(controller, {
            type: 'error',
            message: err instanceof Error ? err.message : String(err),
          });
        } else {
          emit(controller, { type: 'done', aborted: true });
        }
      } finally {
        buildLocks.delete(projectId);
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'application/x-ndjson; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    },
  });
}
