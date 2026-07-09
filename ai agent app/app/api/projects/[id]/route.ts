import { promises as fs } from 'fs';
import path from 'path';
import { connectDB } from '@/lib/db/mongoose';
import { Project } from '@/lib/db/models/Project';
import { Message } from '@/lib/db/models/Message';
import { dropDatabaseByUri } from '@/lib/db/capacity';
import { projectDir, readProjectFiles, readPlansFromDisk } from '@/lib/workspace/fs';
import type { GeneratedFile } from '@/lib/artifact/types';
import { expandImplementationPlanAliases } from '@/lib/llm/planPrompts';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Disk is the source of truth for generated files; DB holds metadata + chat.
  let files: GeneratedFile[] = await readProjectFiles(id);

  let project: Record<string, unknown> | null = null;
  let messages: { role: string; content: string }[] = [];

  try {
    await connectDB();
    project = await Project.findById(id).lean();
    const msgs = await Message.find({ projectId: id })
      .sort({ createdAt: 1 })
      .lean();
    messages = msgs.map((m) => ({ role: m.role, content: m.content }));

    if (files.length === 0 && Array.isArray((project as { files?: GeneratedFile[] })?.files)) {
      files = (project as { files: GeneratedFile[] }).files;
    }
  } catch (e) {
    console.error('[projects/:id] DB read failed:', e);
  }

  // Plans live in MongoDB, but the plan step also writes them to disk — fall
  // back to disk so the builder works offline (and the Build button enables).
  let plans = (project?.plans as Record<string, string>) ?? {};
  let appType = (project?.appType as string) ?? '';
  let hasBackend = !!(project?.hasBackend as boolean);
  let name = (project?.name as string) ?? id;
  const disk = await readPlansFromDisk(id);
  if (disk) {
    plans = { ...plans, ...disk.plans };
    if (!appType) appType = disk.appType ?? '';
    hasBackend = hasBackend || disk.hasBackend;
    if (name === id) name = disk.name;
  }

  if (!project && files.length === 0 && Object.keys(plans).length === 0) {
    return new Response('Project not found', { status: 404 });
  }

  plans = expandImplementationPlanAliases(plans);

  return Response.json({
    id,
    name,
    description: (project?.description as string) ?? '',
    dbName: (project?.dbName as string) ?? '',
    srs: (project?.srs as string) ?? '',
    appType,
    hasBackend,
    plans,
    audit: project?.audit ?? null,
    files,
    messages,
  });
}

/**
 * Drop the GENERATED APP's own MongoDB database (best-effort). Every generated
 * app gets its own db (writeProjectEnv), so deleted projects otherwise leak
 * ~20 collections each until the Atlas free-tier 500-collection cap kills all
 * future builds (happened live 2026-07-03; 89 stale dbs had filled the cap).
 */
async function dropGeneratedAppDatabase(id: string): Promise<void> {
  try {
    const env = await fs.readFile(path.join(projectDir(id), '.env.local'), 'utf8');
    const uri = (env.match(/^MONGODB_URI=(.+)$/m) ?? [])[1]?.trim();
    if (!uri) return;
    await dropDatabaseByUri(uri);
  } catch {
    /* best-effort — no env / unreachable cluster just skips the drop */
  }
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Never delete a project mid-build (shares the build route's lock).
  const buildLocks = (globalThis as typeof globalThis & { _buildLocks?: Set<string> })
    ._buildLocks;
  if (buildLocks?.has(id)) {
    return new Response('Project is currently building — stop the build first.', {
      status: 409,
    });
  }

  await dropGeneratedAppDatabase(id);
  // Remove the workspace directory too (the generated app + node_modules),
  // otherwise deleted projects pile up on disk forever.
  try {
    await fs.rm(projectDir(id), { recursive: true, force: true });
  } catch (e) {
    console.error('[projects/:id] workspace delete failed:', e);
  }
  try {
    await connectDB();
    await Project.findByIdAndDelete(id);
    await Message.deleteMany({ projectId: id });
  } catch (e) {
    console.error('[projects/:id] delete failed:', e);
  }
  return Response.json({ ok: true });
}
