// Generic CRUD API (item): GET one, PUT update, DELETE remove.
import { NextResponse } from 'next/server';
import { getRecord, updateRecord, deleteRecord } from '@/lib/db';

export async function GET(_req, { params }) {
  const rec = await getRecord(params.entity, params.id);
  if (!rec) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  return NextResponse.json(rec);
}

export async function PUT(req, { params }) {
  let body = {};
  try {
    body = await req.json();
  } catch (e) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  const rec = await updateRecord(params.entity, params.id, body && typeof body === 'object' ? body : {});
  if (!rec) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  return NextResponse.json(rec);
}

export async function DELETE(_req, { params }) {
  const ok = await deleteRecord(params.entity, params.id);
  return NextResponse.json({ ok });
}
