import type { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * Explicit build cancellation. The build loop in /api/build no longer dies when
 * the client connection drops (so a closed tab / navigated preview / ended
 * session can't orphan a half-built project). Instead, the ONLY way to cancel
 * is this endpoint: it flags the projectId in the shared stop registry, which
 * the build checks between steps and unwinds cleanly.
 */
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
  const stops = ((globalThis as typeof globalThis & {
    _buildStops?: Set<string>;
  })._buildStops ??= new Set<string>());
  stops.add(projectId);
  return Response.json({ ok: true, stopped: projectId });
}
