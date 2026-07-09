import type { NextRequest } from 'next/server';
import { customAlphabet } from 'nanoid';
import {
  streamOllamaChat,
  OLLAMA_CODE_MODEL,
  type ChatMessage,
} from '@/lib/llm/ollama';
import { SYSTEM_PROMPT } from '@/lib/llm/prompts';
import { parseArtifact } from '@/lib/artifact/parser';
import { writeProjectFiles, writeProjectEnv } from '@/lib/workspace/fs';
import { ensureScaffoldAssets, scaffoldProject } from '@/lib/workspace/scaffold';
import { autofixProject } from '@/lib/build/autofix';
import { syncGeneratedDependencies } from '@/lib/build/dependencies';
import { connectDB } from '@/lib/db/mongoose';
import { Project } from '@/lib/db/models/Project';
import { Message } from '@/lib/db/models/Message';
import { safeMongoDbName } from '@/lib/utils';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

// Lowercase only: the id doubles as the create-next-app project (npm package)
// name, which forbids uppercase characters.
const newProjectId = customAlphabet('0123456789abcdefghijklmnopqrstuvwxyz', 12);

export async function POST(req: NextRequest) {
  let body: { projectId?: string; messages?: ChatMessage[] };
  try {
    body = await req.json();
  } catch {
    return new Response('Invalid JSON body', { status: 400 });
  }

  const history = (body.messages ?? []).filter(
    (m) => m.role === 'user' || m.role === 'assistant',
  );
  if (history.length === 0) {
    return new Response('No messages provided', { status: 400 });
  }

  const projectId =
    body.projectId && /^[a-zA-Z0-9_-]+$/.test(body.projectId)
      ? body.projectId
      : newProjectId();

  // Scaffold the base Next.js app (official create-next-app) in parallel with
  // generation; awaited before the model's files are written on top. No-op if
  // the project already exists (an iteration on an earlier app).
  const scaffolding = scaffoldProject(projectId).catch((e) => {
    console.error('[chat] scaffold failed:', e);
  });

  const lastUser = [...history].reverse().find((m) => m.role === 'user');
  const messages: ChatMessage[] = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...history,
  ];

  const encoder = new TextEncoder();
  const emit = (
    controller: ReadableStreamDefaultController<Uint8Array>,
    obj: unknown,
  ) => controller.enqueue(encoder.encode(JSON.stringify(obj) + '\n'));
  let full = '';

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        for await (const delta of streamOllamaChat(messages, {
          // Code generation uses Gemma too; keep thinking off here for speed.
          model: OLLAMA_CODE_MODEL,
          context: 'code',
          think: false,
          signal: req.signal,
          onThinking: (t) => emit(controller, { type: 'thinking', text: t }),
        })) {
          full += delta;
          emit(controller, { type: 'content', text: delta });
        }
      } catch (err) {
        const msg = `\n\n[AI Web Builder error: ${
          err instanceof Error ? err.message : String(err)
        }]`;
        full += msg;
        emit(controller, { type: 'content', text: msg });
      }

      // Post-processing: extract files, write them to disk, persist to MongoDB.
      // All best-effort — a failure here must not break the already-streamed reply.
      try {
        const artifact = parseArtifact(full);
        const name =
          artifact.name ||
          (lastUser ? lastUser.content.slice(0, 60).trim() : 'Untitled app');
        const dbName = safeMongoDbName(artifact.name || name);

        if (artifact.files.length > 0) {
          // Make sure the create-next-app base is on disk before layering files.
          await scaffolding;
          await ensureScaffoldAssets(projectId);
          await writeProjectFiles(projectId, artifact.files);
          // Deterministic repair pass: fix the mechanical mistakes the local
          // model makes that would crash the app at runtime (missing/hallucinated
          // lucide icons, missing cn import, broken arrows, missing mongoose
          // Schema import, undefined _foo() typo calls, invalid new URL._parse).
          const fixes = await autofixProject(projectId).catch(() => [] as string[]);
          if (fixes.length) {
            emit(controller, { type: 'autofix', fixes });
          }
          // Inject a ready-to-run .env.local so the workspace folder runs as-is.
          await writeProjectEnv(projectId, dbName);
          await syncGeneratedDependencies(projectId);
        }

        try {
          await connectDB();
          await Project.findByIdAndUpdate(
            projectId,
            {
              $set: {
                name,
                description: artifact.description || '',
                dbName,
                ...(artifact.files.length > 0 ? { files: artifact.files } : {}),
              },
            },
            { upsert: true, setDefaultsOnInsert: true },
          );
          if (lastUser) {
            await Message.create({
              projectId,
              role: 'user',
              content: lastUser.content,
            });
          }
          await Message.create({ projectId, role: 'assistant', content: full });
        } catch (dbErr) {
          console.error('[chat] DB persistence failed:', dbErr);
        }
      } catch (e) {
        console.error('[chat] post-processing failed:', e);
      }

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
