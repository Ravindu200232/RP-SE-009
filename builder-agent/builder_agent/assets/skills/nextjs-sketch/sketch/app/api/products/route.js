import { NextResponse } from 'next/server';
import { listProducts } from '@/lib/products.js';

// A route handler that reads the database is dynamic. Without this Next.js
// caches the first response and serves it forever.
export const dynamic = 'force-dynamic';

export async function GET(request) {
  const query = new URL(request.url).searchParams.get('q') ?? '';
  try {
    return NextResponse.json({ products: await listProducts(query) });
  } catch (error) {
    // The client gets a status it can act on; the detail stays in the log.
    console.error('GET /api/products failed', error);
    return NextResponse.json({ error: 'Could not load products' }, { status: 503 });
  }
}
