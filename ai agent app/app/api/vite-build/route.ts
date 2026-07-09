import type { NextRequest } from 'next/server';
import {
  streamOllamaChat,
  OLLAMA_CODE_MODEL,
  type ChatMessage,
} from '@/lib/llm/ollama';
import { parseArtifact } from '@/lib/artifact/parser';
import {
  projectDir,
  readPlansFromDisk,
  writeProjectFileRaw,
  readProjectFile,
} from '@/lib/workspace/fs';
import { scaffoldViteProject, VITE_PROTECTED } from '@/lib/workspace/viteScaffold';
import { renderGeneratedEnv } from '@/lib/workspace/fs';
import { safeMongoDbName } from '@/lib/utils';
import {
  buildViteDataLayerMessages,
  buildViteServerMessages,
  buildViteAppShellMessages,
  buildViteModuleMessages,
} from '@/lib/llm/vitePrompts';
import { promises as fs } from 'fs';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

/** Derive the module components to generate from the pages/master plan. */
function deriveModules(plans: Record<string, string>): { name: string; purpose: string }[] {
  const text = `${plans.pages || ''}\n${plans.master || ''}`;
  const hasPublic = /public|landing|home page|hero|marketing/i.test(text);
  const mods: { name: string; purpose: string }[] = [];
  mods.push({ name: 'Sidebar', purpose: 'the left navigation sidebar for logged-in users; its items set the active tab based on the current user role.' });
  if (hasPublic) mods.push({ name: 'PublicWebsite', purpose: 'the public marketing site (hero, features/services, offers, gallery, contact) shown to visitors before login, with a call-to-action to log in / register.' });
  mods.push({ name: 'AuthPages', purpose: 'the login and register forms (modal or view) that POST to /api/auth/login and /api/auth/register and call an onAuthSuccess(user) prop.' });
  mods.push({ name: 'Dashboard', purpose: 'the main dashboard shown after login: summary stat cards and recent activity fetched from the API, adapting to the user role.' });

  // One CRUD module per top-level admin area found in the pages plan.
  const areas = new Set<string>();
  const re = /`?\/(admin\/[a-z-]+|pos|customer\/[a-z-]+|[a-z-]+)`?/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(plans.pages || ''))) {
    const seg = m[1].replace(/^admin\//, '').replace(/^customer\//, '').replace(/[^a-z-]/gi, '');
    if (seg && !/^(login|register|dashboard|home|about|contact|gallery|facilities|offers|rooms?|index)$/i.test(seg)) {
      areas.add(seg);
    }
  }
  for (const a of [...areas].slice(0, 6)) {
    const Name = a.split('-').map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join('') + 'Module';
    mods.push({ name: Name, purpose: `manage ${a.replace(/-/g, ' ')}: list records in a table from its /api route, create/edit via a modal form, and delete — all with working buttons and loading/empty/error states.` });
  }
  return mods.slice(0, 9);
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

  const disk = await readPlansFromDisk(projectId);
  if (!disk) return new Response('Project (with plans) not found', { status: 404 });
  const plans = disk.plans;
  const appName = disk.name || 'Generated App';

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const emit = (obj: unknown) => {
        try {
          controller.enqueue(encoder.encode(JSON.stringify(obj) + '\n'));
        } catch {
          /* client gone — build continues */
        }
      };

      const gen = async (messages: ChatMessage[]): Promise<string> => {
        let full = '';
        for await (const delta of streamOllamaChat(messages, {
          model: OLLAMA_CODE_MODEL,
          context: 'code',
          think: false,
        })) {
          full += delta;
        }
        return full;
      };

      const writeFiles = async (raw: string): Promise<string[]> => {
        const artifact = parseArtifact(raw);
        const written: string[] = [];
        for (const f of artifact.files) {
          const rel = f.path.replace(/^\/+/, '');
          if (VITE_PROTECTED.has(rel) || rel.includes('..')) continue;
          await writeProjectFileRaw(projectId, rel, f.content ?? '');
          written.push(rel);
        }
        return written;
      };

      try {
        emit({ type: 'scaffold', status: 'start' });
        await scaffoldViteProject(projectId, appName);
        await fs.writeFile(
          path.join(projectDir(projectId), '.env'),
          renderGeneratedEnv(safeMongoDbName(appName)),
          'utf8',
        );
        emit({ type: 'scaffold', status: 'done' });

        // Stage 1 — data layer (types + models)
        emit({ type: 'step', label: 'Data layer', status: 'start' });
        const dl = await gen(buildViteDataLayerMessages({ appName, plans }));
        const dlFiles = await writeFiles(dl);
        emit({ type: 'step', label: 'Data layer', status: 'done', files: dlFiles });

        const types = await readProjectFile(projectId, 'src/types.ts');
        const modelsSrc = await readProjectFile(projectId, 'server/models.ts');
        const modelNames = [...modelsSrc.matchAll(/export const (\w+)\s*=\s*mongoose\.models/g)].map((x) => x[1]);

        // Stage 2 — server.ts (all API routes)
        emit({ type: 'step', label: 'Server (API routes)', status: 'start' });
        const srv = await gen(buildViteServerMessages({ appName, plans, types, modelNames }));
        const srvFiles = await writeFiles(srv);
        emit({ type: 'step', label: 'Server (API routes)', status: 'done', files: srvFiles });

        // Stage 3 — App.tsx shell
        const modules = deriveModules(plans);
        emit({ type: 'step', label: 'App shell', status: 'start' });
        const appShell = await gen(
          buildViteAppShellMessages({ appName, plans, moduleFiles: modules.map((x) => x.name) }),
        );
        const appFiles = await writeFiles(appShell);
        emit({ type: 'step', label: 'App shell', status: 'done', files: appFiles });

        // Stage 4 — module components
        for (const mod of modules) {
          emit({ type: 'step', label: `Module ${mod.name}`, status: 'start' });
          const out = await gen(
            buildViteModuleMessages({ appName, plans, moduleName: mod.name, purpose: mod.purpose, types }),
          );
          const files = await writeFiles(out);
          emit({ type: 'step', label: `Module ${mod.name}`, status: 'done', files });
        }

        emit({ type: 'done', appName });
      } catch (err) {
        emit({ type: 'error', message: err instanceof Error ? err.message : String(err) });
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
