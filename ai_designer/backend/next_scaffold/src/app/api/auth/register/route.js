// Mock-auth register: appends a user to the local database and returns it.
import { NextResponse } from 'next/server';
import { findUser, addUser } from '@/lib/db';

export async function POST(req) {
  let body = {};
  try {
    body = await req.json();
  } catch (e) {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  const { name, email, password, role } = body || {};
  if (!email || !password) return NextResponse.json({ error: 'Email and password are required' }, { status: 400 });
  if (await findUser(email)) return NextResponse.json({ error: 'An account with this email already exists' }, { status: 409 });
  const user = await addUser({ name: name || email.split('@')[0], email, password, role: role || 'User' });
  const { password: _pw, ...safe } = user;
  return NextResponse.json(safe, { status: 201 });
}
