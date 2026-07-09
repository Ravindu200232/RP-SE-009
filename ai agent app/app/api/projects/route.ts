import { connectDB } from '@/lib/db/mongoose';
import { Project } from '@/lib/db/models/Project';
import { listWorkspaceProjects } from '@/lib/workspace/fs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface ProjectListItem {
  id: string;
  name: string;
  description: string;
  dbName: string;
  updatedAt: string;
}

export async function GET() {
  const items: ProjectListItem[] = [];

  // Primary source: MongoDB (has names, descriptions, timestamps).
  try {
    await connectDB();
    const projects = await Project.find(
      {},
      { name: 1, description: 1, dbName: 1, updatedAt: 1 },
    )
      .sort({ updatedAt: -1 })
      .limit(100)
      .lean();

    for (const p of projects) {
      items.push({
        id: String(p._id),
        name: p.name ?? 'Untitled app',
        description: p.description ?? '',
        dbName: p.dbName ?? '',
        updatedAt: p.updatedAt ? new Date(p.updatedAt as Date).toISOString() : '',
      });
    }
  } catch (e) {
    console.error('[projects] DB list failed, falling back to disk:', e);
  }

  // Fallback / merge: include projects that exist on disk but not in the DB,
  // so the builder keeps working when MongoDB is offline.
  const seen = new Set(items.map((i) => i.id));
  for (const d of await listWorkspaceProjects()) {
    if (!seen.has(d.id)) {
      items.push({
        id: d.id,
        name: d.name,
        description: '',
        dbName: '',
        updatedAt: d.updatedAt,
      });
    }
  }

  items.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return Response.json(items);
}
