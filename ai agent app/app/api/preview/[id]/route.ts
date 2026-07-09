import { startPreview, getPreview, stopPreview } from '@/lib/preview/manager';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function validId(id: string) {
  return /^[a-zA-Z0-9_-]+$/.test(id);
}

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!validId(id)) return new Response('Invalid id', { status: 400 });
  return Response.json(startPreview(id));
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!validId(id)) return new Response('Invalid id', { status: 400 });
  const state = getPreview(id);
  return Response.json(
    state ?? { id, phase: 'idle', port: 0, url: '', logs: [] },
  );
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!validId(id)) return new Response('Invalid id', { status: 400 });
  stopPreview(id);
  return Response.json({ ok: true });
}
