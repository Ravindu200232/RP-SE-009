"""
agents/auth_scaffold.py — deterministic, fully-typed TypeScript auth + multi-role scaffold.

This is the "crown jewel": everything security-sensitive (password hashing, JWT sessions,
httpOnly cookies, middleware route-gating, role enforcement, ownership, the admin
user-management surface) is emitted as FIXED, correct TypeScript that the LLM never
touches. The model only writes per-page UI against the fixed contract these files define.

Stack: bcryptjs (Node password hashing) + jose (edge-safe JWT) in an httpOnly cookie.
Edge safety: middleware imports ONLY lib/session.ts (jose) — never lib/auth.ts (bcrypt).

Roles are dynamic (2–4, domain-derived by the refiner). Everything here is parameterised
by the normalised role list, so a hotel app gets admin/manager/receptionist/guest and an
ecommerce app gets admin/seller/customer from the same templates.
"""
from __future__ import annotations

import json
import re
import secrets


# ── Role normalisation ────────────────────────────────────────────────────────

_DEFAULT_ROLES = [
    {"name": "user", "label": "User", "rank": 10, "selfSignup": True},
]


def _slug_role(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(name).lower())


def _home_for(name: str) -> str:
    """Route section prefix for a role's dashboard."""
    if name == "admin":
        return "/admin"
    if name in ("user", "customer", "buyer", "member", "reader", "guest"):
        return "/account"
    return f"/{name}"


def normalize_roles(spec: dict) -> list[dict]:
    """Return a clean, sorted (ascending rank) list of role dicts with name/label/rank/
    selfSignup/home. It never invents an admin role; a single internal user role is used only when
    authentication is enabled without distinct product roles."""
    raw = spec.get("roles")
    if not raw:
        a = spec.get("auth") or {}
        raw = [{"name": n} for n in (a.get("roles") or [])]
    roles: list[dict] = []
    seen: set[str] = set()
    for r in raw or []:
        if isinstance(r, str):
            r = {"name": r}
        if not isinstance(r, dict):
            continue
        name = _slug_role(r.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        roles.append({
            "name": name,
            "label": r.get("label") or name.replace("_", " ").title(),
            "rank": int(r.get("rank", 10)),
            "selfSignup": bool(r.get("selfSignup", name != "admin")),
            "home": r.get("home") or _home_for(name),
        })
    if not roles:
        roles = [dict(x, home=_home_for(x["name"])) for x in _DEFAULT_ROLES]
    roles.sort(key=lambda x: x["rank"])
    return roles


def base_role(roles: list[dict]) -> str:
    ss = [r for r in roles if r["selfSignup"]]
    ss.sort(key=lambda x: x["rank"])
    return (ss[0] if ss else roles[0])["name"]


def _has_admin(roles: list[dict]) -> bool:
    return any(role.get("name") == "admin" for role in roles)


def _ts_arr(items: list[str]) -> str:
    return "[" + ", ".join(f"'{i}'" for i in items) + "]"


def _force_dynamic(src: str) -> str:
    """Insert `export const dynamic = 'force-dynamic'` before the first exported handler.
    Auth/session/DB routes must never be statically pre-rendered at build time (that would
    execute a DB connect during `next build`)."""
    idx = src.find("\nexport ")
    stmt = "\nexport const dynamic = 'force-dynamic'\n"
    if idx == -1:
        return stmt + "\n" + src
    return src[:idx] + "\n" + stmt + src[idx:]


# ── Deterministic file templates ──────────────────────────────────────────────

def _user_model(roles: list[dict]) -> str:
    names = [r["name"] for r in roles]
    union = " | ".join(f"'{n}'" for n in names)
    default = base_role(roles)
    return (
        "import mongoose, { Schema, Document, Model } from 'mongoose'\n\n"
        f"export type UserRole = {union}\n\n"
        "export interface IUser extends Document {\n"
        "  email: string\n"
        "  passwordHash: string\n"
        "  name: string\n"
        "  role: UserRole\n"
        "  createdAt: Date\n"
        "  updatedAt: Date\n"
        "}\n\n"
        "const UserSchema = new Schema<IUser>(\n"
        "  {\n"
        "    email: { type: String, required: true, unique: true, lowercase: true, trim: true },\n"
        "    passwordHash: { type: String, required: true },\n"
        "    name: { type: String, default: '' },\n"
        f"    role: {{ type: String, enum: {_ts_arr(names)}, default: '{default}' }},\n"
        "  },\n"
        "  { timestamps: true },\n"
        ")\n\n"
        "const User: Model<IUser> =\n"
        "  (mongoose.models.User as Model<IUser>) || mongoose.model<IUser>('User', UserSchema)\n"
        "export default User\n"
    )


_SESSION_LIB = (
    "import { SignJWT, jwtVerify } from 'jose'\n\n"
    "// Edge-safe session helpers (jose only — no bcrypt, no next/headers). Imported by\n"
    "// BOTH middleware (Edge runtime) and lib/auth.ts (Node runtime).\n"
    "export interface SessionPayload {\n"
    "  userId: string\n"
    "  role: string\n"
    "  email: string\n"
    "}\n\n"
    "export const SESSION_COOKIE = 'session'\n\n"
    "const secret = new TextEncoder().encode(\n"
    "  process.env.AUTH_SECRET || 'dev-insecure-secret-change-me',\n"
    ")\n\n"
    "export async function signSession(payload: SessionPayload): Promise<string> {\n"
    "  return await new SignJWT({ userId: payload.userId, role: payload.role, email: payload.email })\n"
    "    .setProtectedHeader({ alg: 'HS256' })\n"
    "    .setIssuedAt()\n"
    "    .setExpirationTime('7d')\n"
    "    .sign(secret)\n"
    "}\n\n"
    "export async function verifySession(\n"
    "  token: string | undefined | null,\n"
    "): Promise<SessionPayload | null> {\n"
    "  if (!token) return null\n"
    "  try {\n"
    "    const { payload } = await jwtVerify(token, secret)\n"
    "    if (\n"
    "      typeof payload.userId === 'string' &&\n"
    "      typeof payload.role === 'string' &&\n"
    "      typeof payload.email === 'string'\n"
    "    ) {\n"
    "      return { userId: payload.userId, role: payload.role, email: payload.email }\n"
    "    }\n"
    "    return null\n"
    "  } catch {\n"
    "    return null\n"
    "  }\n"
    "}\n"
)


_AUTH_LIB = (
    "import bcrypt from 'bcryptjs'\n"
    "import { cookies } from 'next/headers'\n"
    "import { NextResponse } from 'next/server'\n"
    "import {\n"
    "  signSession,\n"
    "  verifySession,\n"
    "  SESSION_COOKIE,\n"
    "  type SessionPayload,\n"
    "} from '@/lib/session'\n\n"
    "// Node-only auth helpers (bcrypt + cookie access). Never import this from middleware.\n\n"
    "export async function hashPassword(pw: string): Promise<string> {\n"
    "  return bcrypt.hash(pw, 10)\n"
    "}\n\n"
    "export async function verifyPassword(pw: string, hash: string): Promise<boolean> {\n"
    "  return bcrypt.compare(pw, hash)\n"
    "}\n\n"
    "export async function getSession(): Promise<SessionPayload | null> {\n"
    "  const token = (await cookies()).get(SESSION_COOKIE)?.value\n"
    "  return verifySession(token)\n"
    "}\n\n"
    "export async function requireUser(): Promise<SessionPayload> {\n"
    "  const s = await getSession()\n"
    "  if (!s) throw new Error('UNAUTHORIZED')\n"
    "  return s\n"
    "}\n\n"
    "export async function requireRole(role: string): Promise<SessionPayload> {\n"
    "  const s = await requireUser()\n"
    "  if (s.role !== role) throw new Error('FORBIDDEN')\n"
    "  return s\n"
    "}\n\n"
    "export function setSessionCookie(res: NextResponse, token: string): void {\n"
    "  res.cookies.set(SESSION_COOKIE, token, {\n"
    "    httpOnly: true,\n"
    "    sameSite: 'lax',\n"
    "    path: '/',\n"
    "    maxAge: 60 * 60 * 24 * 7,\n"
    "  })\n"
    "}\n\n"
    "export function clearSessionCookie(res: NextResponse): void {\n"
    "  res.cookies.set(SESSION_COOKIE, '', { httpOnly: true, path: '/', maxAge: 0 })\n"
    "}\n\n"
    "export { signSession, verifySession, SESSION_COOKIE }\n"
    "export type { SessionPayload }\n"
)


_SEED_LIB = (
    "import dbConnect from '@/lib/mongodb'\n"
    "import User from '@/models/User'\n"
    "import { hashPassword } from '@/lib/auth'\n\n"
    "// The zero-setup in-memory Mongo starts empty on every boot, so seed a working admin\n"
    "// account deterministically. Idempotent + guarded so it runs at most once per process.\n"
    "let seeded = false\n\n"
    "export async function ensureAdminSeed(): Promise<void> {\n"
    "  if (seeded) return\n"
    "  await dbConnect()\n"
    "  const existing = await User.findOne({ role: 'admin' })\n"
    "  if (!existing) {\n"
    "    const passwordHash = await hashPassword(process.env.SEED_ADMIN_PASSWORD || 'admin1234')\n"
    "    await User.create({\n"
    "      email: (process.env.SEED_ADMIN_EMAIL || 'admin@demo.com').toLowerCase(),\n"
    "      passwordHash,\n"
    "      name: 'Admin',\n"
    "      role: 'admin',\n"
    "    })\n"
    "  }\n"
    "  seeded = true\n"
    "}\n"
)


def _register_route(roles: list[dict]) -> str:
    self_roles = [r["name"] for r in roles if r["selfSignup"]]
    default = base_role(roles)
    return (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        "import User from '@/models/User'\n"
        "import { hashPassword, signSession, setSessionCookie } from '@/lib/auth'\n\n"
        f"const SELF_SIGNUP_ROLES: string[] = {_ts_arr(self_roles)}\n"
        f"const DEFAULT_ROLE = '{default}'\n\n"
        "export async function POST(req: NextRequest) {\n"
        "  try {\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        "    const email = String(body.email || '').toLowerCase().trim()\n"
        "    const password = String(body.password || '')\n"
        "    const name = String(body.name || '')\n"
        "    if (!email || !password) {\n"
        "      return NextResponse.json({ error: 'Email and password are required' }, { status: 400 })\n"
        "    }\n"
        "    const role = SELF_SIGNUP_ROLES.includes(body.role) ? body.role : DEFAULT_ROLE\n"
        "    const existing = await User.findOne({ email })\n"
        "    if (existing) {\n"
        "      return NextResponse.json({ error: 'Email already registered' }, { status: 409 })\n"
        "    }\n"
        "    const passwordHash = await hashPassword(password)\n"
        "    const user = await User.create({ email, passwordHash, name, role })\n"
        "    const token = await signSession({ userId: String(user._id), role: user.role, email: user.email })\n"
        "    const res = NextResponse.json(\n"
        "      { user: { id: String(user._id), email: user.email, name: user.name, role: user.role } },\n"
        "      { status: 201 },\n"
        "    )\n"
        "    setSessionCookie(res, token)\n"
        "    return res\n"
        "  } catch (e: any) {\n"
        "    return NextResponse.json({ error: String(e?.message || e) }, { status: 500 })\n"
        "  }\n"
        "}\n"
    )


_LOGIN_ROUTE = (
    "import { NextRequest, NextResponse } from 'next/server'\n"
    "import dbConnect from '@/lib/mongodb'\n"
    "import User from '@/models/User'\n"
    "import { verifyPassword, signSession, setSessionCookie } from '@/lib/auth'\n"
    "import { ensureAdminSeed } from '@/lib/seed'\n\n"
    "export async function POST(req: NextRequest) {\n"
    "  try {\n"
    "    await dbConnect()\n"
    "    await ensureAdminSeed()\n"
    "    const body = await req.json()\n"
    "    const email = String(body.email || '').toLowerCase().trim()\n"
    "    const password = String(body.password || '')\n"
    "    const user = await User.findOne({ email })\n"
    "    if (!user || !(await verifyPassword(password, user.passwordHash))) {\n"
    "      return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })\n"
    "    }\n"
    "    const token = await signSession({ userId: String(user._id), role: user.role, email: user.email })\n"
    "    const res = NextResponse.json({\n"
    "      user: { id: String(user._id), email: user.email, name: user.name, role: user.role },\n"
    "    })\n"
    "    setSessionCookie(res, token)\n"
    "    return res\n"
    "  } catch (e: any) {\n"
    "    return NextResponse.json({ error: String(e?.message || e) }, { status: 500 })\n"
    "  }\n"
    "}\n"
)


_LOGOUT_ROUTE = (
    "import { NextResponse } from 'next/server'\n"
    "import { clearSessionCookie } from '@/lib/auth'\n\n"
    "export async function POST() {\n"
    "  const res = NextResponse.json({ ok: true })\n"
    "  clearSessionCookie(res)\n"
    "  return res\n"
    "}\n"
)


_ME_ROUTE = (
    "import { NextResponse } from 'next/server'\n"
    "import { getSession } from '@/lib/auth'\n"
    "import { ensureAdminSeed } from '@/lib/seed'\n\n"
    "export async function GET() {\n"
    "  try {\n"
    "    await ensureAdminSeed()\n"
    "  } catch {\n"
    "    // seeding is best-effort; never block the session read\n"
    "  }\n"
    "  const session = await getSession()\n"
    "  return NextResponse.json({ user: session })\n"
    "}\n"
)


def _admin_users_route(roles: list[dict]) -> str:
    """GET (list) + POST (create) for admin user management. The POST is essential: admin
    'create staff' pages POST here, and without it the request 405s → the browser gets an HTML
    error page → `res.json()` throws 'Unexpected token <' and the form shows a generic failure."""
    role_names = [r["name"] for r in roles] or ["admin"]
    default = next((r["name"] for r in roles if r["name"] != "admin"), role_names[0])
    return (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        "import User from '@/models/User'\n"
        "import { requireRole, hashPassword } from '@/lib/auth'\n\n"
        f"const ALLOWED_ROLES: string[] = {_ts_arr(role_names)}\n"
        f"const DEFAULT_ROLE = '{default}'\n\n"
        "function errStatus(e: any): number {\n"
        "  if (e?.message === 'FORBIDDEN') return 403\n"
        "  if (e?.message === 'UNAUTHORIZED') return 401\n"
        "  return 500\n"
        "}\n\n"
        "export async function GET() {\n"
        "  try {\n"
        "    await requireRole('admin')\n"
        "    await dbConnect()\n"
        "    const users = await User.find({}, 'email name role createdAt').sort({ createdAt: -1 }).lean()\n"
        "    return NextResponse.json(users)\n"
        "  } catch (e: any) {\n"
        "    return NextResponse.json({ error: e?.message || 'error' }, { status: errStatus(e) })\n"
        "  }\n"
        "}\n\n"
        "export async function POST(req: NextRequest) {\n"
        "  try {\n"
        "    await requireRole('admin')\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        "    const email = String(body.email || '').toLowerCase().trim()\n"
        "    const password = String(body.password || '')\n"
        "    const name = String(body.name || '')\n"
        "    const role = ALLOWED_ROLES.includes(body.role) ? body.role : DEFAULT_ROLE\n"
        "    if (!email || !password) return NextResponse.json({ success: false, error: 'Email and password are required' }, { status: 400 })\n"
        "    const existing = await User.findOne({ email })\n"
        "    if (existing) return NextResponse.json({ success: false, error: 'Email already registered' }, { status: 409 })\n"
        "    const passwordHash = await hashPassword(password)\n"
        "    const user = await User.create({ email, passwordHash, name, role })\n"
        "    return NextResponse.json({ success: true, data: { id: String(user._id), email: user.email, name: user.name, role: user.role } }, { status: 201 })\n"
        "  } catch (e: any) {\n"
        "    return NextResponse.json({ success: false, error: e?.message || 'error' }, { status: errStatus(e) })\n"
        "  }\n"
        "}\n"
    )


def _admin_user_role_route(roles: list[dict]) -> str:
    names = [r["name"] for r in roles]
    return (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        "import User from '@/models/User'\n"
        "import { requireRole } from '@/lib/auth'\n\n"
        f"const ROLES: string[] = {_ts_arr(names)}\n\n"
        "function errStatus(e: any): number {\n"
        "  if (e?.message === 'FORBIDDEN') return 403\n"
        "  if (e?.message === 'UNAUTHORIZED') return 401\n"
        "  return 500\n"
        "}\n\n"
        "export async function PUT(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await requireRole('admin')\n"
        "    await dbConnect()\n"
        "    const { role } = await req.json()\n"
        "    if (!ROLES.includes(role)) {\n"
        "      return NextResponse.json({ error: 'Invalid role' }, { status: 400 })\n"
        "    }\n"
        "    const user = await User.findByIdAndUpdate(id, { role }, { new: true })\n"
        "      .select('email name role')\n"
        "      .lean()\n"
        "    if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 })\n"
        "    return NextResponse.json(user)\n"
        "  } catch (e: any) {\n"
        "    return NextResponse.json({ error: e?.message || 'error' }, { status: errStatus(e) })\n"
        "  }\n"
        "}\n"
    )


def _middleware(roles: list[dict]) -> str:
    # role -> section prefix (skip roles whose home is a shared /account handled generically)
    sections = {r["name"]: r["home"] for r in roles}
    entries = ",\n".join(f"  {json.dumps(name)}: {json.dumps(home)}"
                         for name, home in sections.items())
    prefixes = sorted({home for home in sections.values()})
    matcher = ", ".join(f"'{p}/:path*'" for p in prefixes)
    return (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import { verifySession, SESSION_COOKIE } from '@/lib/session'\n\n"
        "// Generated from the role access map. Edge-safe: imports only lib/session (jose).\n"
        "const ROLE_SECTIONS: Record<string, string> = {\n"
        f"{entries},\n"
        "}\n\n"
        "export async function proxy(req: NextRequest) {\n"
        "  const { pathname } = req.nextUrl\n"
        "  const token = req.cookies.get(SESSION_COOKIE)?.value\n"
        "  const session = await verifySession(token)\n\n"
        "  for (const [role, prefix] of Object.entries(ROLE_SECTIONS)) {\n"
        "    if (pathname === prefix || pathname.startsWith(prefix + '/')) {\n"
        "      if (!session) return NextResponse.redirect(new URL('/login', req.url))\n"
        "      if (session.role !== role) {\n"
        "        const home = ROLE_SECTIONS[session.role] || '/'\n"
        "        return NextResponse.redirect(new URL(home, req.url))\n"
        "      }\n"
        "      return NextResponse.next()\n"
        "    }\n"
        "  }\n"
        "  return NextResponse.next()\n"
        "}\n\n"
        "export const config = {\n"
        f"  matcher: [{matcher}],\n"
        "}\n"
    )


_SIDEBAR = (
    "'use client'\n"
    "import Link from 'next/link'\n"
    "import { useState } from 'react'\n"
    "import { usePathname, useRouter } from 'next/navigation'\n\n"
    "export interface SidebarLink {\n"
    "  href: string\n"
    "  label: string\n"
    "}\n\n"
    "export default function Sidebar({\n"
    "  role,\n"
    "  label,\n"
    "  links,\n"
    "}: {\n"
    "  role: string\n"
    "  label: string\n"
    "  links: SidebarLink[]\n"
    "}) {\n"
    "  const pathname = usePathname()\n"
    "  const router = useRouter()\n"
    "  const [open, setOpen] = useState(false)\n"
    "  const logout = async () => {\n"
    "    await fetch('/api/auth/logout', { method: 'POST' })\n"
    "    setOpen(false)\n"
    "    router.push('/login')\n"
    "    router.refresh()\n"
    "  }\n"
    "  return (\n"
    "    <>\n"
    "    <aside className='hidden w-64 shrink-0 min-h-screen bg-card border-r border-border p-6 md:flex md:flex-col'>\n"
    "      <div className='mb-8'>\n"
    "        <span className='text-xs uppercase tracking-wider text-muted-foreground'>Workspace</span>\n"
    "        <h2 className='text-lg font-bold text-foreground'>{label}</h2>\n"
    "        <span className='text-xs text-primary'>{role}</span>\n"
    "      </div>\n"
    "      <nav className='flex flex-col gap-1 flex-1'>\n"
    "        {links.map((l) => {\n"
    "          const active = pathname === l.href\n"
    "          return (\n"
    "            <Link\n"
    "              key={l.href}\n"
    "              href={l.href}\n"
    "              className={\n"
    "                'px-3 py-2 rounded-lg text-sm transition ' +\n"
    "                (active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')\n"
    "              }\n"
    "            >\n"
    "              {l.label}\n"
    "            </Link>\n"
    "          )\n"
    "        })}\n"
    "      </nav>\n"
    "      <button\n"
    "        onClick={logout}\n"
    "        className='mt-4 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted text-left'\n"
    "      >\n"
    "        Log out\n"
    "      </button>\n"
    "    </aside>\n"
    "    <button type='button' aria-label='Open role navigation' onClick={() => setOpen(true)} className='fixed bottom-5 right-5 z-50 rounded-full bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-theme md:hidden'>Menu</button>\n"
    "    {open && (\n"
    "      <>\n"
    "        <button type='button' aria-label='Close role navigation' onClick={() => setOpen(false)} className='fixed inset-0 z-[60] bg-background/80 backdrop-blur-sm md:hidden' />\n"
    "        <aside className='fixed inset-y-0 left-0 z-[70] flex w-[min(82vw,20rem)] flex-col border-r border-border bg-card p-6 shadow-theme md:hidden'>\n"
    "          <div className='mb-8 flex items-start justify-between gap-4'>\n"
    "            <div><span className='text-xs uppercase tracking-wider text-muted-foreground'>Workspace</span><h2 className='text-lg font-bold text-foreground'>{label}</h2><span className='text-xs text-primary'>{role}</span></div>\n"
    "            <button type='button' aria-label='Close menu' onClick={() => setOpen(false)} className='rounded-lg border border-border px-3 py-1 text-foreground'>Close</button>\n"
    "          </div>\n"
    "          <nav className='flex flex-1 flex-col gap-1'>\n"
    "            {links.map((link) => <Link key={link.href} href={link.href} onClick={() => setOpen(false)} className={'rounded-lg px-3 py-2 text-sm transition ' + (pathname === link.href ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>{link.label}</Link>)}\n"
    "          </nav>\n"
    "          <button onClick={logout} className='mt-4 rounded-lg px-3 py-2 text-left text-sm text-muted-foreground hover:bg-muted hover:text-foreground'>Log out</button>\n"
    "        </aside>\n"
    "      </>\n"
    "    )}\n"
    "    </>\n"
    "  )\n"
    "}\n"
)


_TOPNAV = (
    "'use client'\n"
    "import Link from 'next/link'\n"
    "import { usePathname, useRouter } from 'next/navigation'\n"
    "import type { SidebarLink } from '@/components/Sidebar'\n\n"
    "export default function TopNav({ label, links }: { label: string; links: SidebarLink[] }) {\n"
    "  const pathname = usePathname()\n"
    "  const router = useRouter()\n"
    "  const logout = async () => { await fetch('/api/auth/logout', { method: 'POST' }); router.push('/login'); router.refresh() }\n"
    "  return (\n"
    "    <header className='sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur'>\n"
    "      <div className='mx-auto flex min-h-16 max-w-7xl flex-wrap items-center gap-4 px-4 py-3 sm:px-6'>\n"
    "        <strong className='mr-auto text-foreground'>{label}</strong>\n"
    "        <nav className='flex flex-wrap items-center gap-1'>\n"
    "          {links.map(link => <Link key={link.href} href={link.href} className={'rounded-[var(--radius)] px-3 py-2 text-sm transition ' + (pathname === link.href ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>{link.label}</Link>)}\n"
    "        </nav>\n"
    "        <button onClick={logout} className='rounded-[var(--radius)] border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground'>Log out</button>\n"
    "      </div>\n"
    "    </header>\n"
    "  )\n"
    "}\n"
)


def _section_layout(role: dict, links: list[dict], nav_style: str = "sidebar") -> str:
    links_ts = ",\n".join(
        f"  {{ href: {json.dumps(l['href'])}, label: {json.dumps(l['label'])} }}"
        for l in links
    )
    comp = re.sub(r"[^A-Za-z0-9]", "", role["label"]) or role["name"].title()
    if nav_style == "topnav":
        nav_import = "import TopNav from '@/components/TopNav'\n"
        shell_open = "    <div className='min-h-screen bg-background'>\n      <TopNav label={'%s'} links={LINKS} />\n" % role["label"]
        content = "      <main className='mx-auto max-w-7xl p-4 sm:p-6 lg:p-8'>{children}</main>\n"
    elif nav_style == "none":
        nav_import = ""
        shell_open = "    <div className='min-h-screen bg-background'>\n"
        content = "      <main className='mx-auto max-w-7xl p-4 sm:p-6 lg:p-8'>{children}</main>\n"
    else:
        nav_import = "import Sidebar, { type SidebarLink } from '@/components/Sidebar'\n"
        shell_open = ("    <div className='flex min-h-screen bg-background'>\n"
                      f"      <Sidebar role={{'{role['name']}'}} label={{'{role['label']}'}} links={{LINKS}} />\n")
        content = "      <main className='min-w-0 flex-1 p-4 sm:p-6 lg:p-8'>{children}</main>\n"
    link_type = ("import type { SidebarLink } from '@/components/Sidebar'\n"
                 if nav_style in ("topnav", "none") else "")
    return (
        "import { redirect } from 'next/navigation'\n"
        "import { getSession } from '@/lib/auth'\n"
        f"{nav_import}{link_type}\n"
        f"const LINKS: SidebarLink[] = [\n{links_ts},\n]\n\n"
        f"export default async function {comp}DashboardLayout({{\n"
        "  children,\n"
        "}: {\n"
        "  children: React.ReactNode\n"
        "}) {\n"
        "  const session = await getSession()\n"
        "  if (!session) redirect('/login')\n"
        f"  if (session.role !== '{role['name']}') redirect('/')\n"
        "  return (\n"
        f"{shell_open}"
        f"{content}"
        "    </div>\n"
        "  )\n"
        "}\n"
    )


def _placeholder_page(title: str, subtitle: str = "") -> str:
    return (
        "export default function Page() {\n"
        "  return (\n"
        "    <section className='max-w-4xl'>\n"
        f"      <h1 className='mb-2 text-3xl font-bold text-foreground'>{title}</h1>\n"
        f"      <p className='text-muted-foreground'>{subtitle}</p>\n"
        "    </section>\n"
        "  )\n"
        "}\n"
    )


_MANAGE_USERS_PAGE = (
    "'use client'\n"
    "import { useEffect, useState } from 'react'\n\n"
    "interface Row {\n"
    "  _id: string\n"
    "  email: string\n"
    "  name: string\n"
    "  role: string\n"
    "}\n\n"
    "export default function ManageUsers() {\n"
    "  const [rows, setRows] = useState<Row[]>([])\n"
    "  const [roles, setRoles] = useState<string[]>([])\n"
    "  const load = async () => {\n"
    "    const r = await fetch('/api/admin/users')\n"
    "    if (r.ok) {\n"
    "      const data: Row[] = await r.json()\n"
    "      setRows(data)\n"
    "      setRoles(Array.from(new Set(data.map((u) => u.role))))\n"
    "    }\n"
    "  }\n"
    "  useEffect(() => {\n"
    "    load()\n"
    "  }, [])\n"
    "  const changeRole = async (id: string, role: string) => {\n"
    "    await fetch('/api/admin/users/' + id + '/role', {\n"
    "      method: 'PUT',\n"
    "      headers: { 'Content-Type': 'application/json' },\n"
    "      body: JSON.stringify({ role }),\n"
    "    })\n"
    "    load()\n"
    "  }\n"
    "  return (\n"
    "    <section className='max-w-4xl'>\n"
    "      <h1 className='text-3xl font-bold text-foreground mb-6'>Manage Users</h1>\n"
    "      <div className='space-y-2'>\n"
    "        {rows.map((u) => (\n"
    "          <div key={u._id} className='flex items-center justify-between bg-card border border-border rounded-[var(--radius)] px-4 py-3'>\n"
    "            <div>\n"
    "              <p className='text-foreground text-sm'>{u.name || u.email}</p>\n"
    "              <p className='text-muted-foreground text-xs'>{u.email}</p>\n"
    "            </div>\n"
    "            <select\n"
    "              value={u.role}\n"
    "              onChange={(e) => changeRole(u._id, e.target.value)}\n"
    "              className='bg-background text-foreground text-sm rounded-[var(--radius)] px-3 py-2 border border-border'\n"
    "            >\n"
    "              {roles.map((r) => (\n"
    "                <option key={r} value={r}>\n"
    "                  {r}\n"
    "                </option>\n"
    "              ))}\n"
    "            </select>\n"
    "          </div>\n"
    "        ))}\n"
    "      </div>\n"
    "    </section>\n"
    "  )\n"
    "}\n"
)


def _login_page(roles: list[dict], signup_enabled: bool = True) -> str:
    role_home = {r["name"]: r["home"] for r in roles}
    link_import = "import Link from 'next/link'\n" if signup_enabled else ""
    signup_prompt = (
        "        <p className='text-muted-foreground text-sm mt-4 text-center'>\n"
        "          No account? <Link href='/signup' className='text-primary'>Sign up</Link>\n"
        "        </p>\n"
        if signup_enabled else ""
    )
    return (
        "'use client'\n"
        "import { useState } from 'react'\n"
        "import { useRouter } from 'next/navigation'\n"
        f"{link_import}\n"
        f"const ROLE_HOME: Record<string, string> = {json.dumps(role_home)}\n\n"
        "export default function LoginPage() {\n"
        "  const router = useRouter()\n"
        "  const [email, setEmail] = useState('')\n"
        "  const [password, setPassword] = useState('')\n"
        "  const [error, setError] = useState('')\n"
        "  const [loading, setLoading] = useState(false)\n"
        "  const submit = async (e: React.FormEvent) => {\n"
        "    e.preventDefault()\n"
        "    setLoading(true)\n"
        "    setError('')\n"
        "    const res = await fetch('/api/auth/login', {\n"
        "      method: 'POST',\n"
        "      headers: { 'Content-Type': 'application/json' },\n"
        "      body: JSON.stringify({ email, password }),\n"
        "    })\n"
        "    const data = await res.json()\n"
        "    setLoading(false)\n"
        "    if (!res.ok) {\n"
        "      setError(data.error || 'Login failed')\n"
        "      return\n"
        "    }\n"
        "    router.push(ROLE_HOME[data.user?.role] || '/')\n"
        "    router.refresh()\n"
        "  }\n"
        "  return (\n"
        "    <main className='min-h-screen flex items-center justify-center bg-background px-6'>\n"
        "      <form onSubmit={submit} className='w-full max-w-md bg-card border border-border rounded-[var(--radius)] p-8 shadow-theme'>\n"
        "        <h1 className='text-2xl font-bold text-foreground mb-6'>Welcome back</h1>\n"
        "        {error && <p className='text-red-400 text-sm mb-4'>{error}</p>}\n"
        "        <label className='block text-sm text-foreground mb-1'>Email</label>\n"
        "        <input type='email' value={email} onChange={(e) => setEmail(e.target.value)} required\n"
        "          className='w-full mb-4 bg-background border border-border rounded-[var(--radius)] px-4 py-3 text-foreground' />\n"
        "        <label className='block text-sm text-foreground mb-1'>Password</label>\n"
        "        <input type='password' value={password} onChange={(e) => setPassword(e.target.value)} required\n"
        "          className='w-full mb-6 bg-background border border-border rounded-[var(--radius)] px-4 py-3 text-foreground' />\n"
        "        <button type='submit' disabled={loading}\n"
        "          className='w-full bg-primary text-primary-foreground rounded-[var(--radius)] py-3 font-medium disabled:opacity-60'>\n"
        "          {loading ? 'Signing in…' : 'Sign in'}\n"
        "        </button>\n"
        f"{signup_prompt}"
        "      </form>\n"
        "    </main>\n"
        "  )\n"
        "}\n"
    )


def _signup_page(roles: list[dict]) -> str:
    self_roles = [{"name": r["name"], "label": r["label"], "home": r["home"]}
                  for r in roles if r["selfSignup"]]
    role_home = {r["name"]: r["home"] for r in roles}
    return (
        "'use client'\n"
        "import { useState } from 'react'\n"
        "import { useRouter } from 'next/navigation'\n"
        "import Link from 'next/link'\n\n"
        f"const SELF_ROLES: {{ name: string; label: string }}[] = {json.dumps([{'name': r['name'], 'label': r['label']} for r in self_roles])}\n"
        f"const ROLE_HOME: Record<string, string> = {json.dumps(role_home)}\n\n"
        "export default function SignupPage() {\n"
        "  const router = useRouter()\n"
        "  const [name, setName] = useState('')\n"
        "  const [email, setEmail] = useState('')\n"
        "  const [password, setPassword] = useState('')\n"
        "  const [role, setRole] = useState(SELF_ROLES[0]?.name || 'user')\n"
        "  const [error, setError] = useState('')\n"
        "  const [loading, setLoading] = useState(false)\n"
        "  const submit = async (e: React.FormEvent) => {\n"
        "    e.preventDefault()\n"
        "    setLoading(true)\n"
        "    setError('')\n"
        "    const res = await fetch('/api/auth/register', {\n"
        "      method: 'POST',\n"
        "      headers: { 'Content-Type': 'application/json' },\n"
        "      body: JSON.stringify({ name, email, password, role }),\n"
        "    })\n"
        "    const data = await res.json()\n"
        "    setLoading(false)\n"
        "    if (!res.ok) {\n"
        "      setError(data.error || 'Sign up failed')\n"
        "      return\n"
        "    }\n"
        "    router.push(ROLE_HOME[data.user?.role] || '/')\n"
        "    router.refresh()\n"
        "  }\n"
        "  return (\n"
        "    <main className='min-h-screen flex items-center justify-center bg-background px-6'>\n"
        "      <form onSubmit={submit} className='w-full max-w-md bg-card border border-border rounded-[var(--radius)] p-8 shadow-theme'>\n"
        "        <h1 className='text-2xl font-bold text-foreground mb-6'>Create your account</h1>\n"
        "        {error && <p className='text-red-400 text-sm mb-4'>{error}</p>}\n"
        "        <label className='block text-sm text-foreground mb-1'>Name</label>\n"
        "        <input value={name} onChange={(e) => setName(e.target.value)}\n"
        "          className='w-full mb-4 bg-background border border-border rounded-[var(--radius)] px-4 py-3 text-foreground' />\n"
        "        <label className='block text-sm text-foreground mb-1'>Email</label>\n"
        "        <input type='email' value={email} onChange={(e) => setEmail(e.target.value)} required\n"
        "          className='w-full mb-4 bg-background border border-border rounded-[var(--radius)] px-4 py-3 text-foreground' />\n"
        "        <label className='block text-sm text-foreground mb-1'>Password</label>\n"
        "        <input type='password' value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}\n"
        "          className='w-full mb-4 bg-background border border-border rounded-[var(--radius)] px-4 py-3 text-foreground' />\n"
        "        {SELF_ROLES.length > 1 && (\n"
        "          <div className='mb-6'>\n"
        "            <label className='block text-sm text-foreground mb-1'>I am a…</label>\n"
        "            <select value={role} onChange={(e) => setRole(e.target.value)}\n"
        "              className='w-full bg-background border border-border rounded-[var(--radius)] px-4 py-3 text-foreground'>\n"
        "              {SELF_ROLES.map((r) => (\n"
        "                <option key={r.name} value={r.name}>{r.label}</option>\n"
        "              ))}\n"
        "            </select>\n"
        "          </div>\n"
        "        )}\n"
        "        <button type='submit' disabled={loading}\n"
        "          className='w-full bg-primary text-primary-foreground rounded-[var(--radius)] py-3 font-medium disabled:opacity-60'>\n"
        "          {loading ? 'Creating…' : 'Create account'}\n"
        "        </button>\n"
        "        <p className='text-muted-foreground text-sm mt-4 text-center'>\n"
        "          Already have an account? <Link href='/login' className='text-primary'>Sign in</Link>\n"
        "        </p>\n"
        "      </form>\n"
        "    </main>\n"
        "  )\n"
        "}\n"
    )


def _env_local() -> str:
    return (
        f"AUTH_SECRET={secrets.token_hex(32)}\n"
        "SEED_ADMIN_EMAIL=admin@demo.com\n"
        "SEED_ADMIN_PASSWORD=admin1234\n"
    )


# ── Per-role dashboard link derivation ────────────────────────────────────────

def _links_for_role(role: dict, spec: dict) -> list[dict]:
    """Sidebar links for a role's section. Prefer spec pages; else derive sensible
    defaults from the (owned) data model."""
    home = role["home"]
    pages = spec.get("pages") or []
    matched = [p for p in pages
               if str(p.get("access", "")) == f"role:{role['name']}" and p.get("path")]
    if matched:
        return [{"href": p["path"], "label": p.get("title") or p["path"].split("/")[-1].title() or "Home"}
                for p in matched]
    # defaults
    links = [{"href": home, "label": "Overview"}]
    from agents.scaffold import pascal, route_name  # lazy import (avoids cycle)
    models = spec.get("data_model") or []
    if role["name"] == "admin":
        for m in models:
            seg = route_name(m.get("name", "Item"))
            links.append({"href": f"{home}/{seg}", "label": f"Manage {pascal(m.get('name','Item'))}s"})
        links.append({"href": f"{home}/users", "label": "Manage Users"})
    else:
        for m in models:
            seg = route_name(m.get("name", "Item"))
            links.append({"href": f"{home}/{seg}", "label": f"My {pascal(m.get('name','Item'))}s"})
    return links


# ── Public entrypoint ─────────────────────────────────────────────────────────

# ── Shared-dashboard (SRS / multi-role) variant ───────────────────────────────

def _shared_dashboard(spec: dict, roles: list[dict]) -> bool:
    """SRS-style apps share one /dashboard gated per-page by multiple roles."""
    homes = {r["home"] for r in roles}
    if len(homes) == 1 and next(iter(homes)) == "/dashboard":
        return True
    for p in spec.get("pages") or []:
        acc = str(p.get("access") or "")
        if acc == "authed" or (acc.startswith("role:") and "|" in acc):
            return True
    return False


def _signup_enabled(spec: dict) -> bool:
    return bool((spec.get("auth") or {}).get("signup"))


def _protected_pages(spec: dict) -> list[dict]:
    out = []
    for p in spec.get("pages") or []:
        acc = str(p.get("access") or "public")
        if acc == "public" or p.get("kind") == "auth" or not p.get("path"):
            continue
        roles_for = None if acc == "authed" else (acc[5:].split("|") if acc.startswith("role:") else None)
        out.append({"prefix": p["path"], "roles": roles_for,
                    "label": p.get("title") or p["path"], "kind": p.get("kind")})
    return out


def _page_access_middleware(spec: dict) -> str:
    prot = _protected_pages(spec)
    rules = [{"prefix": p["prefix"], "roles": p["roles"]} for p in prot]
    rules.sort(key=lambda r: len(r["prefix"]), reverse=True)
    tops = sorted({"/" + p["prefix"].strip("/").split("/")[0] for p in prot if p["prefix"].strip("/")})
    matcher = ", ".join(f"'{t}', '{t}/:path*'" for t in tops)
    return (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import { verifySession, SESSION_COOKIE } from '@/lib/session'\n\n"
        "// Generated from the page access map (multi-role, shared dashboard).\n"
        "// Edge-safe: imports only lib/session (jose).\n"
        "type Rule = { prefix: string; roles: string[] | null }\n"
        f"const RULES: Rule[] = {json.dumps(rules)}\n\n"
        "export async function proxy(req: NextRequest) {\n"
        "  const { pathname } = req.nextUrl\n"
        "  const rule = RULES.find((r) => pathname === r.prefix || pathname.startsWith(r.prefix + '/'))\n"
        "  if (!rule) return NextResponse.next()\n"
        "  const session = await verifySession(req.cookies.get(SESSION_COOKIE)?.value)\n"
        "  if (!session) return NextResponse.redirect(new URL('/login', req.url))\n"
        "  if (rule.roles && !rule.roles.includes(session.role)) {\n"
        "    return NextResponse.redirect(new URL('/dashboard', req.url))\n"
        "  }\n"
        "  return NextResponse.next()\n"
        "}\n\n"
        "export const config = {\n"
        f"  matcher: [{matcher}],\n"
        "}\n"
    )


def _dashboard_sidebar(spec: dict) -> str:
    links = [{"href": p["prefix"], "label": p["label"], "roles": p["roles"]}
             for p in _protected_pages(spec)]
    return (
        "'use client'\n"
        "import NextLink from 'next/link'\n"
        "import { useEffect, useState } from 'react'\n"
        "import { usePathname, useRouter } from 'next/navigation'\n\n"
        "type SidebarLink = { href: string; label: string; roles: string[] | null }\n"
        f"const LINKS: SidebarLink[] = {json.dumps(links)}\n\n"
        "export default function DashboardSidebar() {\n"
        "  const [role, setRole] = useState<string | null>(null)\n"
        "  const pathname = usePathname()\n"
        "  const router = useRouter()\n"
        "  useEffect(() => {\n"
        "    fetch('/api/auth/me', { cache: 'no-store' }).then((r) => r.json())\n"
        "      .then((d) => setRole(d?.user?.role || null))\n"
        "  }, [])\n"
        "  const logout = async () => {\n"
        "    await fetch('/api/auth/logout', { method: 'POST' }); router.push('/login'); router.refresh()\n"
        "  }\n"
        "  const visible = LINKS.filter((l) => !l.roles || (role && l.roles.includes(role)))\n"
        "  return (\n"
        "    <aside className='w-64 shrink-0 min-h-screen bg-card border-r border-border p-5 flex flex-col'>\n"
        "      <span className='text-xs uppercase tracking-wider text-muted-foreground mb-4'>Menu</span>\n"
        "      <nav className='flex flex-col gap-1 flex-1'>\n"
        "        {visible.map((l) => (\n"
        "          <NextLink key={l.href} href={l.href}\n"
        "            className={'px-3 py-2 rounded-lg text-sm ' + (pathname === l.href ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>\n"
        "            {l.label}\n"
        "          </NextLink>\n"
        "        ))}\n"
        "      </nav>\n"
        "      <div className='text-xs text-muted-foreground mt-3'>{role}</div>\n"
        "      <button onClick={logout} className='mt-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground text-left'>Log out</button>\n"
        "    </aside>\n"
        "  )\n"
        "}\n"
    )


_SHARED_DASHBOARD_LAYOUT = (
    "import { redirect } from 'next/navigation'\n"
    "import { getSession } from '@/lib/auth'\n"
    "import DashboardSidebar from '@/components/DashboardSidebar'\n\n"
    "export default async function DashboardLayout({ children }: { children: React.ReactNode }) {\n"
    "  const session = await getSession()\n"
    "  if (!session) redirect('/login')\n"
    "  return (\n"
    "    <div className='flex min-h-screen bg-background'>\n"
    "      <DashboardSidebar />\n"
    "      <main className='flex-1 p-6 md:p-8'>{children}</main>\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)


def _srs_seed_lib(spec: dict, roles: list[dict]) -> str:
    """Seed the SRS's staff accounts (email/password) with inferred roles."""
    role_names = [r["name"] for r in roles]
    accounts = []
    for raw in ((spec.get("seed") or {}).get("staff_accounts") or []):
        m = re.match(r"\s*([^/\s]+)\s*/\s*(\S+)", str(raw))
        if not m:
            continue
        email, pw = m.group(1).strip().lower(), m.group(2).strip()
        prefix = email.split("@")[0]
        role = next((rn for rn in role_names if prefix in rn or rn.split("_")[0] in prefix), None)
        role = role or (role_names[len(accounts) % len(role_names)] if role_names else "admin")
        accounts.append({"email": email, "password": pw, "name": prefix.title(), "role": role})
    seeded_roles = {a.get("role") for a in accounts}
    if accounts:
        for rn in role_names:
            if rn not in seeded_roles:
                accounts.append({"email": f"{rn}@demo.com", "password": f"{rn}1234",
                                 "name": rn.replace("_", " ").title(), "role": rn})
    if not accounts:
        # Deterministic fixtures make every declared role testable without relying
        # on self-signup (staff SRS systems normally disable public signup).
        accounts = [{"email": "admin@demo.com", "password": "admin1234",
                     "name": "Admin", "role": "admin"}]
        for rn in role_names:
            if rn == "admin":
                continue
            accounts.append({"email": f"{rn}@demo.com", "password": f"{rn}1234",
                             "name": rn.replace("_", " ").title(), "role": rn})
            accounts.append({"email": f"{rn}2@demo.com", "password": f"{rn}1234",
                             "name": (rn.replace("_", " ") + " 2").title(), "role": rn})
    return (
        "import dbConnect from '@/lib/mongodb'\n"
        "import User from '@/models/User'\n"
        "import { hashPassword } from '@/lib/auth'\n\n"
        f"const ACCOUNTS = {json.dumps(accounts)}\n\n"
        "let seeded = false\n"
        "export async function ensureAdminSeed(): Promise<void> {\n"
        "  if (seeded) return\n"
        "  await dbConnect()\n"
        "  const count = await User.countDocuments()\n"
        "  if (count === 0) {\n"
        "    for (const a of ACCOUNTS) {\n"
        "      const passwordHash = await hashPassword(a.password)\n"
        "      await User.create({ email: a.email, passwordHash, name: a.name, role: a.role })\n"
        "    }\n"
        "  }\n"
        "  seeded = true\n"
        "}\n"
    )


def auth_files(spec: dict) -> dict:
    """Every deterministic auth/role/dashboard file for a multipage-app spec."""
    roles = normalize_roles(spec)
    nav_style = str((spec.get("design") or {}).get("navStyle") or "sidebar")
    if spec.get("input_schema") == "role-wise-srs/v1":
        return _auth_files_rolewise(spec, roles)
    if _shared_dashboard(spec, roles):
        return _auth_files_shared(spec, roles)
    files: dict[str, str] = {}

    # Data + libs
    files["models/User.ts"] = _user_model(roles)
    files["lib/session.ts"] = _SESSION_LIB
    files["lib/auth.ts"] = _AUTH_LIB
    files["lib/seed.ts"] = _SEED_LIB

    # Auth API (force-dynamic: never statically pre-rendered — they hit the DB/session)
    if _signup_enabled(spec):
        files["app/api/auth/register/route.ts"] = _force_dynamic(_register_route(roles))
    files["app/api/auth/login/route.ts"] = _force_dynamic(_LOGIN_ROUTE)
    files["app/api/auth/logout/route.ts"] = _force_dynamic(_LOGOUT_ROUTE)
    files["app/api/auth/me/route.ts"] = _force_dynamic(_ME_ROUTE)

    # Admin user management API
    if _has_admin(roles):
        files["app/api/admin/users/route.ts"] = _force_dynamic(_admin_users_route(roles))
        files["app/api/admin/users/[id]/role/route.ts"] = _force_dynamic(_admin_user_role_route(roles))

    # Middleware + auth pages + sidebar
    files["proxy.ts"] = _middleware(roles)
    files["components/Sidebar.tsx"] = _SIDEBAR
    if nav_style == "topnav":
        files["components/TopNav.tsx"] = _TOPNAV
    files["app/login/page.tsx"] = _login_page(roles, _signup_enabled(spec))
    if _signup_enabled(spec):
        files["app/signup/page.tsx"] = _signup_page(roles)
    files[".env.local"] = _env_local()

    # Per-role dashboard layout + a placeholder overview page (builder may overwrite the
    # content pages later; the layout/sidebar/gating stay deterministic).
    seen_sections: set[str] = set()
    for role in roles:
        home = role["home"]
        if home in seen_sections:
            continue
        seen_sections.add(home)
        links = _links_for_role(role, spec)
        seg = home.strip("/")
        files[f"app/{seg}/layout.tsx"] = _section_layout(role, links, nav_style)
        files[f"app/{seg}/page.tsx"] = _placeholder_page(
            f"{role['label']} Dashboard", "Welcome to your dashboard.")

    # Deterministic admin Manage Users page
    admin = next((r for r in roles if r["name"] == "admin"), None)
    if admin:
        files[f"app/{admin['home'].strip('/')}/users/page.tsx"] = _MANAGE_USERS_PAGE

    return files


def _auth_files_rolewise(spec: dict, roles: list[dict]) -> dict:
    """Exact page-map RBAC plus per-role top-level layouts for role-wise inputs."""
    files: dict[str, str] = {}
    nav_style = str((spec.get("design") or {}).get("navStyle") or "sidebar")
    files["models/User.ts"] = _user_model(roles)
    files["lib/session.ts"] = _SESSION_LIB
    files["lib/auth.ts"] = _AUTH_LIB
    files["lib/seed.ts"] = _srs_seed_lib(spec, roles)
    if _signup_enabled(spec):
        files["app/api/auth/register/route.ts"] = _force_dynamic(_register_route(roles))
    files["app/api/auth/login/route.ts"] = _force_dynamic(_LOGIN_ROUTE)
    files["app/api/auth/logout/route.ts"] = _force_dynamic(_LOGOUT_ROUTE)
    files["app/api/auth/me/route.ts"] = _force_dynamic(_ME_ROUTE)
    if _has_admin(roles):
        files["app/api/admin/users/route.ts"] = _force_dynamic(_admin_users_route(roles))
        files["app/api/admin/users/[id]/role/route.ts"] = _force_dynamic(_admin_user_role_route(roles))
    files["proxy.ts"] = _page_access_middleware(spec)
    files["components/Sidebar.tsx"] = _SIDEBAR
    if nav_style == "topnav":
        files["components/TopNav.tsx"] = _TOPNAV
    files["app/login/page.tsx"] = _login_page(roles, _signup_enabled(spec))
    if _signup_enabled(spec):
        files["app/signup/page.tsx"] = _signup_page(roles)
    files[".env.local"] = _env_local()

    pages = spec.get("pages") or []
    for role in roles:
        role_pages = [p for p in pages if str(p.get("access")) == f"role:{role['name']}" and p.get("path")]
        if not role_pages:
            continue
        top = str(role_pages[0]["path"]).strip("/").split("/", 1)[0]
        links = _links_for_role(role, spec)
        files[f"app/{top}/layout.tsx"] = _section_layout(role, links, nav_style)
    return files


def _auth_files_shared(spec: dict, roles: list[dict]) -> dict:
    """Auth files for an SRS-style app: ONE /dashboard gated per-page by multiple roles,
    seeded staff accounts, optional signup."""
    files: dict[str, str] = {}
    files["models/User.ts"] = _user_model(roles)
    files["lib/session.ts"] = _SESSION_LIB
    files["lib/auth.ts"] = _AUTH_LIB
    files["lib/seed.ts"] = _srs_seed_lib(spec, roles)

    if _signup_enabled(spec):
        files["app/api/auth/register/route.ts"] = _force_dynamic(_register_route(roles))
    files["app/api/auth/login/route.ts"] = _force_dynamic(_LOGIN_ROUTE)
    files["app/api/auth/logout/route.ts"] = _force_dynamic(_LOGOUT_ROUTE)
    files["app/api/auth/me/route.ts"] = _force_dynamic(_ME_ROUTE)
    if _has_admin(roles):
        files["app/api/admin/users/route.ts"] = _force_dynamic(_admin_users_route(roles))
        files["app/api/admin/users/[id]/role/route.ts"] = _force_dynamic(_admin_user_role_route(roles))

    files["proxy.ts"] = _page_access_middleware(spec)
    files["components/DashboardSidebar.tsx"] = _dashboard_sidebar(spec)
    files["app/dashboard/layout.tsx"] = _SHARED_DASHBOARD_LAYOUT
    # The shared layout must always have a concrete index route; otherwise the
    # seeded admin gate points at a 404 and the auth matrix cannot be verified.
    files["app/dashboard/page.tsx"] = _placeholder_page(
        "Staff Dashboard", "Choose a workspace from the navigation.")
    files["app/login/page.tsx"] = _login_page(roles, _signup_enabled(spec))
    if _signup_enabled(spec):
        files["app/signup/page.tsx"] = _signup_page(roles)
    files[".env.local"] = _env_local()

    # Manage Users page (if the SRS declared one under /dashboard)
    if any(str(p.get("path", "")).rstrip("/").endswith("/users") for p in (spec.get("pages") or [])):
        files["app/dashboard/users/page.tsx"] = _MANAGE_USERS_PAGE
    return files
