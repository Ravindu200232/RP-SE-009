import type { NextRequest } from 'next/server';
import { customAlphabet } from 'nanoid';
import { promises as fs } from 'fs';
import path from 'path';
import { streamOllamaChat } from '@/lib/llm/ollama';
import {
  buildPlanConversation,
  buildPlanRepairConversation,
  expandImplementationPlanAliases,
  PLAN_STAGES,
  type PlanStage,
} from '@/lib/llm/planPrompts';
import {
  analyzeImplementationPlan,
  formatPlanDiagnosticsForPrompt,
  normalizeImplementationPlanCoverage,
} from '@/lib/llm/planQuality';
import { getAppType } from '@/lib/appTypes';
import { projectDir } from '@/lib/workspace/fs';
import { connectDB } from '@/lib/db/mongoose';
import { Project } from '@/lib/db/models/Project';
import { assertMongoCollectionCapacity } from '@/lib/db/capacity';
import { safeMongoDbName } from '@/lib/utils';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

// Lowercase ids stay compatible with create-next-app package names + Mongo ids.
const makeId = customAlphabet('0123456789abcdefghijklmnopqrstuvwxyz', 10);

function envNumber(name: string, fallback: number): number {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function planContextForStage(_stage: PlanStage): number {
  return envNumber('OLLAMA_IMPLEMENTATION_PLAN_CTX', envNumber('OLLAMA_PLAN_LARGE_CTX', 65536));
}

function planThinkingForStage(_stage: PlanStage): boolean {
  return process.env.OLLAMA_PLAN_THINK !== 'false';
}

export async function POST(req: NextRequest) {
  let body: {
    projectId?: string;
    srs?: string;
    appType?: string;
    hasBackend?: boolean;
    stage?: string;
    name?: string;
    prior?: { stage: string; content: string }[];
  };
  try {
    body = await req.json();
  } catch {
    return new Response('Invalid JSON body', { status: 400 });
  }

  const stage = body.stage as PlanStage;
  if (!PLAN_STAGES.includes(stage)) {
    return new Response('Invalid plan stage', { status: 400 });
  }
  const appType = getAppType(body.appType);
  if (!appType) {
    return new Response('Invalid app type', { status: 400 });
  }

  const hasBackend = !!body.hasBackend;
  const srs = body.srs ?? '';
  const projectId =
    body.projectId && /^[a-z0-9_-]+$/.test(body.projectId) ? body.projectId : makeId();
  const name = body.name?.trim() || `${appType.label} app`;

  if (hasBackend && !body.projectId) {
    try {
      await assertMongoCollectionCapacity();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return new Response(message, { status: 507 });
    }
  }

  const prior = (body.prior ?? [])
    .filter((p) => PLAN_STAGES.includes(p.stage as PlanStage) && p.content)
    .map((p) => ({ stage: p.stage as PlanStage, content: p.content }));

  // The pagewise AND components stages are AUTO-DECOMPOSED in BATCHES: instead
  // of one giant prompt covering every page (a 12B model drops pages on a large
  // app) OR one call per page (reliable but 20+ calls = the agent stuck on one
  // huge step), we derive the route list from the Pages Plan and detail a small
  // BATCH of pages per call. Few enough pages per call that none are dropped;
  // few enough calls that a 20-page app plans in ~4 rounds. No page is ever
  // missed. components is "session-wise" — same batching, one call plans the
  // composite components for each page in the batch.
  const planNumCtx = planContextForStage(stage);
  const planThink = planThinkingForStage(stage);

  const encoder = new TextEncoder();
  const emit = (
    controller: ReadableStreamDefaultController<Uint8Array>,
    obj: unknown,
  ) => controller.enqueue(encoder.encode(JSON.stringify(obj) + '\n'));
  let full = '';

  const persistPlanSnapshot = async () => {
    try {
      const dir = projectDir(projectId);
      await fs.mkdir(path.join(dir, '_plans'), { recursive: true });
      await fs.writeFile(path.join(dir, '_plans', `${stage}.md`), full, 'utf8');
      await fs.writeFile(
        path.join(dir, '_plans', '_meta.json'),
        JSON.stringify({ name, appType: appType.key, hasBackend }, null, 2),
        'utf8',
      );
    } catch (e) {
      console.error('[plan] disk write failed:', e);
    }

    try {
      const planSet = Object.fromEntries(
        Object.entries(expandImplementationPlanAliases({ [stage]: full })).map(
          ([key, value]) => [`plans.${key}`, value],
        ),
      );
      await connectDB();
      await Project.findByIdAndUpdate(
        projectId,
        {
          $set: {
            name,
            dbName: safeMongoDbName(name),
            srs,
            appType: appType.key,
            hasBackend,
            ...planSet,
          },
        },
        { upsert: true, setDefaultsOnInsert: true },
      );
    } catch (e) {
      console.error('[plan] DB persist failed:', e);
    }
  };

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let lastThinkingAt = 0;
      let planningError = false;
      const onThinking = (text: string) => {
        const now = Date.now();
        if (now - lastThinkingAt < 750) return;
        lastThinkingAt = now;
        emit(controller, { type: 'thinking', stage, text });
      };

      try {
        const convo = buildPlanConversation({ srs, appType, hasBackend, stage, prior });
        for await (const delta of streamOllamaChat(convo, {
          context: 'plan',
          numCtx: planNumCtx,
          think: planThink,
          temperature: envNumber('OLLAMA_PLAN_TEMPERATURE', 0.35),
          signal: req.signal,
          onThinking,
        })) {
          full += delta;
          emit(controller, { type: 'content', text: delta });
        }
      } catch (err) {
        planningError = true;
        const msg = `\n\n[planning error: ${err instanceof Error ? err.message : String(err)}]`;
        full += msg;
        emit(controller, { type: 'content', text: msg });
        emit(controller, {
          type: 'error',
          message: err instanceof Error ? err.message : String(err),
        });
      }

      if (!planningError && full.trim()) {
        let diagnostics = analyzeImplementationPlan(full, srs, hasBackend);
        let normalized = normalizeImplementationPlanCoverage(full, srs, hasBackend);
        let normalizedDiagnostics = analyzeImplementationPlan(normalized, srs, hasBackend);

        if (normalized !== full && normalizedDiagnostics.issues.length <= diagnostics.issues.length) {
          full = normalized;
          diagnostics = normalizedDiagnostics;
          emit(controller, { type: 'replace', stage, text: full });
        }

        if (
          !diagnostics.valid &&
          process.env.OLLAMA_PLAN_REPAIR !== 'false' &&
          !req.signal.aborted
        ) {
          emit(controller, {
            type: 'thinking',
            stage,
            text: `\nRepairing Implementation Plan coverage: ${diagnostics.issues
              .slice(0, 3)
              .join('; ')}\n`,
          });

          try {
            let repaired = '';
            const repairConvo = buildPlanRepairConversation({
              srs,
              appType,
              hasBackend,
              draft: full,
              diagnostics: formatPlanDiagnosticsForPrompt(diagnostics),
            });
            for await (const delta of streamOllamaChat(repairConvo, {
              context: 'plan',
              numCtx: planNumCtx,
              think: planThink,
              temperature: envNumber('OLLAMA_PLAN_REPAIR_TEMPERATURE', 0.25),
              signal: req.signal,
              onThinking,
            })) {
              repaired += delta;
            }

            if (repaired.trim()) {
              const repairedNormalized = normalizeImplementationPlanCoverage(
                repaired,
                srs,
                hasBackend,
              );
              const repairedDiagnostics = analyzeImplementationPlan(
                repairedNormalized,
                srs,
                hasBackend,
              );
              const currentDiagnostics = analyzeImplementationPlan(full, srs, hasBackend);
              if (
                repairedDiagnostics.valid ||
                repairedDiagnostics.issues.length <= currentDiagnostics.issues.length
              ) {
                full = repairedNormalized;
                diagnostics = repairedDiagnostics;
                emit(controller, { type: 'replace', stage, text: full });
              }
            }
          } catch (err) {
            const fallback = normalizeImplementationPlanCoverage(full, srs, hasBackend);
            if (fallback !== full) {
              full = fallback;
              diagnostics = analyzeImplementationPlan(full, srs, hasBackend);
              emit(controller, { type: 'replace', stage, text: full });
            }
            console.error('[plan] repair failed:', err);
          }
        }

        const finalNormalized = normalizeImplementationPlanCoverage(full, srs, hasBackend);
        if (finalNormalized !== full) {
          full = finalNormalized;
          emit(controller, { type: 'replace', stage, text: full });
        }

        const finalDiagnostics = analyzeImplementationPlan(full, srs, hasBackend);
        if (!finalDiagnostics.valid) {
          console.warn('[plan] final diagnostics:', finalDiagnostics.issues);
        }
      }

      await persistPlanSnapshot();

      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'application/x-ndjson; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'X-Project-Id': projectId,
      'X-Accel-Buffering': 'no',
    },
  });
}
