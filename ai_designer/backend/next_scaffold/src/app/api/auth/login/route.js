// Mock-auth login: checks the users table in the local database and returns
// the user (sans password). The client stores the session in localStorage.
import { NextResponse } from 'next/server';
import { findUser } from '@/lib/db';

export async function POST(req) {
  let body = {};
  try {
    body = await req.json();
  } catch (e) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  const { email, password } = body || {};
  if (!email) return NextResponse.json({ error: 'Email is required' }, { status: 400 });
  const user = await findUser(email, password);
  if (!user) return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
  const { password: _pw, ...safe } = user;
  return NextResponse.json(safe);
}
