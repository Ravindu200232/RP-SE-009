// Generic CRUD API (collection): GET list, POST create.
// One deterministic handler serves EVERY entity - no generated backend code.
import { NextResponse } from 'next/server';
import { listRecords, createRecord } from '@/lib/db';

export async function GET(_req, { params }) {
  return NextResponse.json(await listRecords(params.entity));
}

export async function POST(req, { params }) {
  let body = {};
  try {
    body = await req.json();
  } catch (e) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  const rec = await createRecord(params.entity, body && typeof body === 'object' ? body : {});
  return NextResponse.json(rec, { status: 201 });
}
