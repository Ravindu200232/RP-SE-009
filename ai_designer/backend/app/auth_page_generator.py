"""Domain-aware Login + Register page generator.

Login and Register are deliberately DIFFERENT layouts (login = split brand/trust
panel + sign-in form; register = centered onboarding with role-selection cards,
benefit strip, and a multi-field form) and domain-aware (copy, role descriptions,
extra fields). They build against the scaffold runtime (`@/lib/api`, `@/lib/site`)
using plain Tailwind so no extra dependencies are needed.
"""
from __future__ import annotations

import json
import os


_AUTH_COPY = {
    "healthcare": {
        "label": "care", "tagline": "Secure access to care, in one place.",
        "points": ["Book and manage appointments", "Message your care team", "View lab results and prescriptions"],
        "role_hint": "For patients, providers, and clinic staff.",
        "benefits": ["Same-week appointments", "Encrypted health records", "24/7 patient portal"],
        "role_desc": {"Patient": "Book visits and view your records", "Doctor": "Manage your schedule and patients",
                      "Provider": "Clinical tools and patient access", "Admin": "Run the clinic and staff"},
        "extra_label": "Phone", "extra_field": "phone",
    },
    "real-estate": {
        "label": "property", "tagline": "Find your next home, faster.",
        "points": ["Save and compare listings", "Book property tours", "Talk directly to agents"],
        "role_hint": "For buyers, sellers, and agents.",
        "benefits": ["Smart saved searches", "Instant tour booking", "Verified agents"],
        "role_desc": {"Buyer": "Search homes and book tours", "Seller": "List and track interest",
                      "Agent": "Manage listings and leads", "Admin": "Oversee the marketplace"},
        "extra_label": "Phone", "extra_field": "phone",
    },
    "fitness": {
        "label": "training", "tagline": "Train with a plan that works.",
        "points": ["Book classes in seconds", "Track your progress", "Work with expert coaches"],
        "role_hint": "For members, trainers, and admins.",
        "benefits": ["Flexible class booking", "Progress tracking", "Personal coaching"],
        "role_desc": {"Member": "Book classes and track results", "Trainer": "Manage programs and clients",
                      "Coach": "Coach members and classes", "Admin": "Run the studio"},
        "extra_label": "Phone", "extra_field": "phone",
    },
    "restaurant": {
        "label": "dining", "tagline": "Your table, ready when you are.",
        "points": ["Reserve tables instantly", "Browse the latest menu", "Save your favourites"],
        "role_hint": "For guests, staff, and managers.",
        "benefits": ["Instant reservations", "Live table availability", "Member perks"],
        "role_desc": {"Customer": "Reserve tables and order", "Staff": "Manage service and tables",
                      "Admin": "Run the restaurant"},
        "extra_label": "Phone", "extra_field": "phone",
    },
    "education": {
        "label": "learning", "tagline": "Learn skills that move you forward.",
        "points": ["Enroll in courses", "Follow a learning path", "Track your progress"],
        "role_hint": "For students, instructors, and admins.",
        "benefits": ["Guided learning paths", "Expert instructors", "Progress tracking"],
        "role_desc": {"Student": "Enroll and learn", "Instructor": "Create and teach courses",
                      "Admin": "Manage the academy"},
        "extra_label": "Phone", "extra_field": "phone",
    },
    "vehicle": {
        "label": "vehicle", "tagline": "Find the vehicle that fits your life.",
        "points": ["Browse certified inventory", "Calculate financing", "Book a test drive"],
        "role_hint": "For buyers, sales, and admins.",
        "benefits": ["Certified inventory", "Instant finance quotes", "Easy test drives"],
        "role_desc": {"Buyer": "Browse and book test drives", "Sales": "Manage inventory and leads",
                      "Admin": "Run the dealership"},
        "extra_label": "Phone", "extra_field": "phone",
    },
    "pos-erp": {
        "label": "operations", "tagline": "Run operations without the chaos.",
        "points": ["Track stock across branches", "Issue invoices in seconds", "See every stock movement"],
        "role_hint": "For managers, cashiers, and warehouse staff.",
        "benefits": ["Real-time stock", "Fast invoicing", "Full audit trail"],
        "role_desc": {"Manager": "Oversee branches and reports", "Cashier": "Ring up sales",
                      "Warehouse": "Manage stock and GRNs", "Admin": "Configure the system"},
        "extra_label": "Phone", "extra_field": "phone",
    },
}
_DEFAULT_COPY = {
    "label": "account", "tagline": "The faster way to run your work.",
    "points": ["Everything in one workspace", "Set up in minutes", "Built for your team"],
    "role_hint": "For your whole team.",
    "benefits": ["Quick setup", "Role-based access", "Made for production"],
    "role_desc": {}, "extra_label": "Phone", "extra_field": "phone",
}


def _copy(domain):
    return _AUTH_COPY.get(domain, _DEFAULT_COPY)


_LOGIN = r"""'use client';
// AUTO-GENERATED domain-aware login (split brand/trust panel + sign-in form).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';

const POINTS = __POINTS__;
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = React.useState('admin@example.com');
  const [password, setPassword] = React.useState('password123');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim() || !password.trim()) { setError('Email and password are required.'); return; }
    setBusy(true);
    try { await auth.login(email.trim(), password); router.push('/dashboard'); }
    catch (err) { setError(err.message || 'Login failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <div className="text-lg font-bold">{site.appName}</div>
        <div>
          <h2 className="text-3xl font-bold leading-tight">__TAGLINE__</h2>
          <ul className="mt-6 space-y-3">
            {POINTS.map((p) => (
              <li key={p} className="flex items-center gap-2.5 text-primary-foreground/90">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20 text-xs">✓</span>{p}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-primary-foreground/70">__ROLE_HINT__</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
          <p className="mb-7 mt-1 text-sm text-muted-foreground">Sign in to your {site.appName} __LABEL__ account.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5"><label htmlFor="email" className="block text-sm font-medium">Email</label>
              <input id="email" type="email" className={INPUT} value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div className="space-y-1.5"><label htmlFor="password" className="block text-sm font-medium">Password</label>
              <input id="password" type="password" className={INPUT} value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-muted-foreground"><input type="checkbox" /> Remember me</label>
              <a href="#" className="font-medium text-primary hover:underline">Forgot password?</a>
            </div>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">New to {site.appName}? <Link href="/register" className="font-medium text-primary hover:underline">Create an account</Link></p>
          <p className="mt-3 text-center text-xs text-muted-foreground/70">Demo: admin@example.com / password123</p>
        </div>
      </div>
    </div>
  );
}
"""

_REGISTER = r"""'use client';
// AUTO-GENERATED domain-aware registration (role-selection onboarding — distinct from login).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';

const BENEFITS = __BENEFITS__;
const ROLE_DESC = __ROLE_DESC__;
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';

function Field({ label, value, onChange, type }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium">{label}</label>
      <input type={type || 'text'} value={value} onChange={(e) => onChange(e.target.value)} className={INPUT} />
    </div>
  );
}

export default function Register() {
  const router = useRouter();
  const roles = (site.roles && site.roles.length) ? site.roles : ['User'];
  const [form, setForm] = React.useState({ name: '', email: '', password: '', __EXTRA__: '', role: roles[0] });
  const [terms, setTerms] = React.useState(false);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim() || !form.email.trim() || !form.password.trim()) { setError('Name, email, and password are required.'); return; }
    if (!terms) { setError('Please accept the terms to continue.'); return; }
    setBusy(true);
    try { await auth.register(form); router.push('/dashboard'); }
    catch (err) { setError(err.message || 'Registration failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-muted/30 py-10">
      <div className="mx-auto max-w-3xl px-6">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Create your {site.appName} __LABEL__ account</h1>
          <p className="mt-1 text-sm text-muted-foreground">A few details and you're in — set up in under a minute.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {BENEFITS.map((b) => <div key={b} className="rounded-xl border bg-card p-4 text-sm font-medium">{b}</div>)}
        </div>
        <form onSubmit={submit} className="mt-6 space-y-5 rounded-2xl border bg-card p-6 sm:p-8">
          <div>
            <p className="mb-2 text-sm font-medium">I am a…</p>
            <div className="grid gap-3 sm:grid-cols-3">
              {roles.map((r) => (
                <button type="button" key={r} onClick={() => set('role', r)}
                  className={'rounded-xl border p-4 text-left transition ' + (form.role === r ? 'border-primary ring-2 ring-primary/30' : 'hover:border-primary/40')}>
                  <span className="block text-sm font-semibold">{r}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{ROLE_DESC[r] || ('Access tailored to ' + r + 's')}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" value={form.name} onChange={(v) => set('name', v)} />
            <Field label="Email" type="email" value={form.email} onChange={(v) => set('email', v)} />
            <Field label="Password" type="password" value={form.password} onChange={(v) => set('password', v)} />
            <Field label="__EXTRA_LABEL__" value={form.__EXTRA__} onChange={(v) => set('__EXTRA__', v)} />
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} /> I agree to the terms of service and privacy policy.
          </label>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy ? 'Creating…' : 'Create account'}</button>
          <p className="text-center text-sm text-muted-foreground">Already have an account? <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link></p>
        </form>
      </div>
    </div>
  );
}
"""


# ── 4 additional login layout variants ─────────────────────────────────────────

_LOGIN_CENTERED = r"""'use client';
// AUTO-GENERATED login (centered brand card — bold/playful).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = React.useState('admin@example.com');
  const [password, setPassword] = React.useState('password123');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!email.trim()||!password.trim()) { setError('Email and password are required.'); return; }
    setBusy(true);
    try { await auth.login(email.trim(), password); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Login failed'); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-primary/90 via-primary to-primary/70 p-4">
      <div className="w-full max-w-md rounded-2xl bg-background p-8 shadow-2xl">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <img src="/generated/logo.jpg" alt="" className="h-14 w-14 rounded-2xl object-cover shadow" onError={(e)=>{e.currentTarget.style.display='none';}} />
          <div><h1 className="font-display text-2xl font-bold">{site.appName}</h1>
          <p className="mt-1 text-sm text-muted-foreground">__TAGLINE__</p></div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5"><label className="block text-sm font-medium" htmlFor="em">Email</label>
            <input id="em" type="email" className={INPUT} value={email} onChange={(e)=>setEmail(e.target.value)} /></div>
          <div className="space-y-1.5"><label className="block text-sm font-medium" htmlFor="pw">Password</label>
            <input id="pw" type="password" className={INPUT} value={password} onChange={(e)=>setPassword(e.target.value)} /></div>
          {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Signing in…':'Sign in'}</button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">No account? <Link href="/register" className="font-medium text-primary hover:underline">Register</Link></p>
        <p className="mt-2 text-center text-xs text-muted-foreground/60">Demo: admin@example.com / password123</p>
      </div>
    </div>
  );
}
"""

_LOGIN_GLASS = r"""'use client';
// AUTO-GENERATED login (glass card over hero image — glass/premium-dark).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const INPUT = 'w-full rounded-lg border border-white/25 bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-white/40';
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = React.useState('admin@example.com');
  const [password, setPassword] = React.useState('password123');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!email.trim()||!password.trim()) { setError('All fields required.'); return; }
    setBusy(true);
    try { await auth.login(email.trim(), password); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Login failed'); } finally { setBusy(false); }
  };
  return (
    <div className="relative flex min-h-screen items-center justify-center">
      <img src="/assets/auth.jpg" alt="" className="absolute inset-0 h-full w-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
      <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" />
      <div className="relative z-10 w-full max-w-sm rounded-2xl border border-white/20 bg-white/10 p-8 shadow-2xl backdrop-blur-md">
        <div className="mb-6 flex items-center gap-3">
          <img src="/generated/logo.jpg" alt="" className="h-10 w-10 rounded-xl object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
          <div><span className="font-display text-xl font-bold text-white">{site.appName}</span>
          <p className="text-xs text-white/60">__LABEL__ account</p></div>
        </div>
        <h1 className="mb-1 font-display text-2xl font-bold text-white">Welcome back</h1>
        <p className="mb-6 text-sm text-white/70">__TAGLINE__</p>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5"><label className="block text-sm font-medium text-white/90" htmlFor="em">Email</label>
            <input id="em" type="email" className={INPUT} value={email} onChange={(e)=>setEmail(e.target.value)} /></div>
          <div className="space-y-1.5"><label className="block text-sm font-medium text-white/90" htmlFor="pw">Password</label>
            <input id="pw" type="password" className={INPUT} value={password} onChange={(e)=>setPassword(e.target.value)} /></div>
          {error && <p className="rounded-md bg-red-500/20 px-3 py-2 text-sm text-red-200">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Signing in…':'Sign in'}</button>
        </form>
        <p className="mt-5 text-center text-sm text-white/70">No account? <Link href="/register" className="font-medium text-white underline">Register</Link></p>
        <p className="mt-2 text-center text-xs text-white/40">Demo: admin@example.com / password123</p>
      </div>
    </div>
  );
}
"""

_LOGIN_MINIMAL = r"""'use client';
// AUTO-GENERATED login (minimal clean form — no image).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = React.useState('admin@example.com');
  const [password, setPassword] = React.useState('password123');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!email.trim()||!password.trim()) { setError('All fields required.'); return; }
    setBusy(true);
    try { await auth.login(email.trim(), password); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Login failed'); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <div className="h-1 w-full bg-primary" />
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3">
            <img src="/generated/logo.jpg" alt="" className="h-8 w-8 rounded-lg object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
            <span className="font-display text-lg font-semibold">{site.appName}</span>
          </div>
          <h1 className="font-display text-2xl font-bold">Sign in</h1>
          <p className="mb-8 mt-1.5 text-sm text-muted-foreground">__TAGLINE__</p>
          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium" htmlFor="em">Email address</label>
              </div>
              <input id="em" type="email" className={INPUT} value={email} onChange={(e)=>setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium" htmlFor="pw">Password</label>
                <a href="#" className="text-xs text-primary hover:underline">Forgot?</a>
              </div>
              <input id="pw" type="password" className={INPUT} value={password} onChange={(e)=>setPassword(e.target.value)} />
            </div>
            {error && <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Signing in…':'Continue'}</button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">New here? <Link href="/register" className="font-medium text-primary hover:underline">Create account</Link></p>
          <p className="mt-3 text-center text-xs text-muted-foreground/50">Demo: admin@example.com / password123</p>
        </div>
      </div>
    </div>
  );
}
"""

_LOGIN_DARK_PANEL = r"""'use client';
// AUTO-GENERATED login (dark editorial side panel).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const POINTS = __POINTS__;
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = React.useState('admin@example.com');
  const [password, setPassword] = React.useState('password123');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!email.trim()||!password.trim()) { setError('All fields required.'); return; }
    setBusy(true);
    try { await auth.login(email.trim(), password); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Login failed'); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen">
      <div className="hidden flex-col justify-between bg-gray-950 p-10 text-white md:flex md:w-5/12">
        <div className="flex items-center gap-3">
          <img src="/generated/logo.jpg" alt="" className="h-9 w-9 rounded-xl object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
          <span className="font-display text-lg font-semibold">{site.appName}</span>
        </div>
        <div>
          <h2 className="font-display text-3xl font-bold leading-snug">__TAGLINE__</h2>
          <ul className="mt-6 space-y-3">
            {POINTS.map((p) => (
              <li key={p} className="flex items-center gap-2.5 text-sm text-gray-300">
                <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />{p}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-gray-500">__ROLE_HINT__</p>
      </div>
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="font-display text-2xl font-bold">Welcome back</h1>
          <p className="mb-7 mt-1 text-sm text-muted-foreground">Sign in to your __LABEL__ account.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5"><label className="block text-sm font-medium" htmlFor="em">Email</label>
              <input id="em" type="email" className={INPUT} value={email} onChange={(e)=>setEmail(e.target.value)} /></div>
            <div className="space-y-1.5"><label className="block text-sm font-medium" htmlFor="pw">Password</label>
              <input id="pw" type="password" className={INPUT} value={password} onChange={(e)=>setPassword(e.target.value)} /></div>
            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-muted-foreground"><input type="checkbox" /> Remember me</label>
              <a href="#" className="text-primary hover:underline">Forgot?</a>
            </div>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Signing in…':'Sign in'}</button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">New here? <Link href="/register" className="font-medium text-primary hover:underline">Create account</Link></p>
          <p className="mt-3 text-center text-xs text-muted-foreground/60">Demo: admin@example.com / password123</p>
        </div>
      </div>
    </div>
  );
}
"""

_LOGIN_VARIANTS = [_LOGIN, _LOGIN_CENTERED, _LOGIN_GLASS, _LOGIN_MINIMAL, _LOGIN_DARK_PANEL]


# ── 4 additional register layout variants ──────────────────────────────────────

_REGISTER_SPLIT = r"""'use client';
// AUTO-GENERATED register (split — primary panel + two-col form).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const BENEFITS = __BENEFITS__;
const ROLE_DESC = __ROLE_DESC__;
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export default function Register() {
  const router = useRouter();
  const roles = (site.roles&&site.roles.length)?site.roles:['User'];
  const [form,setForm] = React.useState({name:'',email:'',password:'',__EXTRA__:'',role:roles[0]});
  const [terms,setTerms] = React.useState(false);
  const [error,setError] = React.useState('');
  const [busy,setBusy] = React.useState(false);
  const set = (k,v) => setForm((p)=>({...p,[k]:v}));
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!form.name.trim()||!form.email.trim()||!form.password.trim()) { setError('Name, email, and password required.'); return; }
    if (!terms) { setError('Please accept the terms.'); return; }
    setBusy(true);
    try { await auth.register(form); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Registration failed'); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen">
      <div className="hidden flex-col justify-between bg-primary p-10 text-primary-foreground md:flex md:w-5/12">
        <div className="font-display text-xl font-bold">{site.appName}</div>
        <div>
          <h2 className="font-display text-3xl font-bold leading-tight">Join {site.appName}</h2>
          <ul className="mt-6 space-y-3">
            {BENEFITS.map((b)=>(
              <li key={b} className="flex items-center gap-2.5 text-primary-foreground/90">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20 text-xs">✓</span>{b}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-primary-foreground/70">Already registered? <Link href="/login" className="underline">Sign in</Link></p>
      </div>
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md">
          <h1 className="font-display text-2xl font-bold">Create your __LABEL__ account</h1>
          <p className="mb-5 mt-1 text-sm text-muted-foreground">Get started in minutes.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5"><label className="block text-sm font-medium">Full name</label><input type="text" className={INPUT} value={form.name} onChange={(e)=>set('name',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Email</label><input type="email" className={INPUT} value={form.email} onChange={(e)=>set('email',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Password</label><input type="password" className={INPUT} value={form.password} onChange={(e)=>set('password',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">__EXTRA_LABEL__</label><input type="text" className={INPUT} value={form.__EXTRA__} onChange={(e)=>set('__EXTRA__',e.target.value)} /></div>
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium">Role</label>
              <div className="grid gap-2 sm:grid-cols-3">
                {roles.map((r)=>(
                  <button type="button" key={r} onClick={()=>set('role',r)}
                    className={'rounded-lg border p-2.5 text-left text-sm transition '+(form.role===r?'border-primary bg-primary/5 font-semibold':'hover:border-primary/40')}>
                    <span className="block font-medium">{r}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{ROLE_DESC[r]||('Access for '+r)}</span>
                  </button>
                ))}
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={terms} onChange={(e)=>setTerms(e.target.checked)} /> I accept the terms</label>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Creating…':'Create account'}</button>
          </form>
        </div>
      </div>
    </div>
  );
}
"""

_REGISTER_GLASS = r"""'use client';
// AUTO-GENERATED register (glass form over hero image).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const ROLE_DESC = __ROLE_DESC__;
const INPUT = 'w-full rounded-lg border border-white/25 bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-white/40';
export default function Register() {
  const router = useRouter();
  const roles = (site.roles&&site.roles.length)?site.roles:['User'];
  const [form,setForm] = React.useState({name:'',email:'',password:'',__EXTRA__:'',role:roles[0]});
  const [terms,setTerms] = React.useState(false);
  const [error,setError] = React.useState('');
  const [busy,setBusy] = React.useState(false);
  const set = (k,v) => setForm((p)=>({...p,[k]:v}));
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!form.name.trim()||!form.email.trim()||!form.password.trim()) { setError('All fields required.'); return; }
    if (!terms) { setError('Please accept the terms.'); return; }
    setBusy(true);
    try { await auth.register(form); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Registration failed'); } finally { setBusy(false); }
  };
  return (
    <div className="relative flex min-h-screen items-center justify-center">
      <img src="/assets/auth.jpg" alt="" className="absolute inset-0 h-full w-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
      <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-white/20 bg-white/10 p-8 shadow-2xl backdrop-blur-md">
        <div className="mb-5 flex items-center gap-3">
          <img src="/generated/logo.jpg" alt="" className="h-9 w-9 rounded-xl object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
          <span className="font-display text-xl font-bold text-white">{site.appName}</span>
        </div>
        <h1 className="mb-4 font-display text-2xl font-bold text-white">Create __LABEL__ account</h1>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1"><label className="block text-xs font-medium text-white/80">Full name</label><input type="text" className={INPUT} value={form.name} onChange={(e)=>set('name',e.target.value)} /></div>
            <div className="space-y-1"><label className="block text-xs font-medium text-white/80">Role</label>
              <select className={INPUT} value={form.role} onChange={(e)=>set('role',e.target.value)}>{roles.map((r)=><option key={r} value={r}>{r}</option>)}</select></div>
            <div className="space-y-1"><label className="block text-xs font-medium text-white/80">Email</label><input type="email" className={INPUT} value={form.email} onChange={(e)=>set('email',e.target.value)} /></div>
            <div className="space-y-1"><label className="block text-xs font-medium text-white/80">Password</label><input type="password" className={INPUT} value={form.password} onChange={(e)=>set('password',e.target.value)} /></div>
          </div>
          <label className="flex items-center gap-2 text-xs text-white/80"><input type="checkbox" checked={terms} onChange={(e)=>setTerms(e.target.checked)} /> I accept the terms of service</label>
          {error && <p className="rounded-md bg-red-500/20 px-3 py-2 text-sm text-red-200">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Creating…':'Create account'}</button>
        </form>
        <p className="mt-4 text-center text-sm text-white/70">Already registered? <Link href="/login" className="font-medium text-white underline">Sign in</Link></p>
      </div>
    </div>
  );
}
"""

_REGISTER_MINIMAL = r"""'use client';
// AUTO-GENERATED register (minimal clean — no image).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const ROLE_DESC = __ROLE_DESC__;
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export default function Register() {
  const router = useRouter();
  const roles = (site.roles&&site.roles.length)?site.roles:['User'];
  const [form,setForm] = React.useState({name:'',email:'',password:'',__EXTRA__:'',role:roles[0]});
  const [terms,setTerms] = React.useState(false);
  const [error,setError] = React.useState('');
  const [busy,setBusy] = React.useState(false);
  const set = (k,v) => setForm((p)=>({...p,[k]:v}));
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!form.name.trim()||!form.email.trim()||!form.password.trim()) { setError('All fields required.'); return; }
    if (!terms) { setError('Please accept the terms.'); return; }
    setBusy(true);
    try { await auth.register(form); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Registration failed'); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <div className="h-1 w-full bg-primary" />
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="mb-7 flex items-center gap-3">
            <img src="/generated/logo.jpg" alt="" className="h-8 w-8 rounded-lg object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
            <span className="font-display text-lg font-semibold">{site.appName}</span>
          </div>
          <h1 className="font-display text-2xl font-bold">Create __LABEL__ account</h1>
          <p className="mb-6 mt-1 text-sm text-muted-foreground">Join {site.appName} — set up in minutes.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5"><label className="block text-sm font-medium">Full name</label><input type="text" className={INPUT} value={form.name} onChange={(e)=>set('name',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Email</label><input type="email" className={INPUT} value={form.email} onChange={(e)=>set('email',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Password</label><input type="password" className={INPUT} value={form.password} onChange={(e)=>set('password',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Role</label>
                <select className={INPUT} value={form.role} onChange={(e)=>set('role',e.target.value)}>{roles.map((r)=><option key={r} value={r}>{r}</option>)}</select></div>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={terms} onChange={(e)=>setTerms(e.target.checked)} /> I accept the terms</label>
            {error && <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Creating…':'Create account'}</button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">Already registered? <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link></p>
        </div>
      </div>
    </div>
  );
}
"""

_REGISTER_DARK_PANEL = r"""'use client';
// AUTO-GENERATED register (dark editorial panel + onboarding form).
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
const BENEFITS = __BENEFITS__;
const ROLE_DESC = __ROLE_DESC__;
const INPUT = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export default function Register() {
  const router = useRouter();
  const roles = (site.roles&&site.roles.length)?site.roles:['User'];
  const [form,setForm] = React.useState({name:'',email:'',password:'',__EXTRA__:'',role:roles[0]});
  const [terms,setTerms] = React.useState(false);
  const [error,setError] = React.useState('');
  const [busy,setBusy] = React.useState(false);
  const set = (k,v) => setForm((p)=>({...p,[k]:v}));
  const submit = async (e) => {
    e.preventDefault(); setError('');
    if (!form.name.trim()||!form.email.trim()||!form.password.trim()) { setError('All fields required.'); return; }
    if (!terms) { setError('Please accept the terms.'); return; }
    setBusy(true);
    try { await auth.register(form); router.push('/dashboard'); }
    catch (err) { setError(err.message||'Registration failed'); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen">
      <div className="hidden flex-col justify-between bg-gray-950 p-10 text-white md:flex md:w-5/12">
        <div className="flex items-center gap-3">
          <img src="/generated/logo.jpg" alt="" className="h-9 w-9 rounded-xl object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
          <span className="font-display text-xl font-semibold">{site.appName}</span>
        </div>
        <div>
          <h2 className="font-display text-3xl font-bold">Create your account.</h2>
          <ul className="mt-7 space-y-4">
            {BENEFITS.map((b)=>(
              <li key={b} className="flex items-center gap-3 text-sm text-gray-300">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-[10px] text-white">✓</span>{b}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-gray-500">© {new Date().getFullYear()} {site.appName}</p>
      </div>
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-md">
          <h1 className="font-display text-2xl font-bold">Register as…</h1>
          <div className="my-4 grid gap-2 sm:grid-cols-3">
            {roles.map((r)=>(
              <button type="button" key={r} onClick={()=>set('role',r)}
                className={'rounded-xl border p-3 text-left text-sm transition '+(form.role===r?'border-primary ring-2 ring-primary/20':'hover:border-primary/40')}>
                <span className="block font-semibold">{r}</span>
                <span className="block text-xs text-muted-foreground">{ROLE_DESC[r]||r}</span>
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5"><label className="block text-sm font-medium">Full name</label><input type="text" className={INPUT} value={form.name} onChange={(e)=>set('name',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Email</label><input type="email" className={INPUT} value={form.email} onChange={(e)=>set('email',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">Password</label><input type="password" className={INPUT} value={form.password} onChange={(e)=>set('password',e.target.value)} /></div>
              <div className="space-y-1.5"><label className="block text-sm font-medium">__EXTRA_LABEL__</label><input type="text" className={INPUT} value={form.__EXTRA__} onChange={(e)=>set('__EXTRA__',e.target.value)} /></div>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={terms} onChange={(e)=>setTerms(e.target.checked)} /> I accept the terms</label>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy?'Creating…':'Create account'}</button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">Already registered? <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link></p>
        </div>
      </div>
    </div>
  );
}
"""

_REGISTER_VARIANTS = [_REGISTER, _REGISTER_SPLIT, _REGISTER_GLASS, _REGISTER_MINIMAL, _REGISTER_DARK_PANEL]

# ── Visual-style → variant index ───────────────────────────────────────────────
_STYLE_VARIANT = {
    "enterprise": 0,  "dense-admin": 0,   # feature panel split / original onboarding
    "bold": 1,        "playful": 1,        # centered brand / split+benefits
    "glass": 2,       "premium-dark": 2,   # glass overlay
    "clean": 3,       "minimal": 3,        # minimal
    "editorial": 4,                        # dark editorial panel
}


def _variant_idx(genome: dict) -> int:
    vis = genome.get("visual_style", "clean") if isinstance(genome, dict) else "clean"
    if vis in _STYLE_VARIANT:
        return _STYLE_VARIANT[vis]
    import hashlib
    seed = str(genome.get("app_seed", "x")) if isinstance(genome, dict) else "x"
    return int(hashlib.md5(seed.encode()).hexdigest(), 16) % 5


def _apply_login(template: str, c: dict) -> str:
    return (template
            .replace("__POINTS__", json.dumps(c["points"]))
            .replace("__TAGLINE__", c["tagline"])
            .replace("__ROLE_HINT__", c["role_hint"])
            .replace("__LABEL__", c["label"]))


def _apply_register(template: str, c: dict) -> str:
    extra = c["extra_field"]
    return (template
            .replace("__BENEFITS__", json.dumps(c["benefits"]))
            .replace("__ROLE_DESC__", json.dumps(c["role_desc"]))
            .replace("__EXTRA_LABEL__", c["extra_label"])
            .replace("__EXTRA__", extra)
            .replace("__LABEL__", c["label"]))


def generate_login(domain: str, genome: dict | None = None) -> str:
    c = _copy(domain)
    idx = _variant_idx(genome) if genome else 0
    return _apply_login(_LOGIN_VARIANTS[idx], c)


def generate_register(domain: str, genome: dict | None = None) -> str:
    c = _copy(domain)
    idx = _variant_idx(genome) if genome else 0
    return _apply_register(_REGISTER_VARIANTS[idx], c)


def write_auth_pages(out_dir: str, domain: str, genome: dict | None = None) -> list:
    files = {
        "src/app/login/page.jsx": generate_login(domain, genome),
        "src/app/register/page.jsx": generate_register(domain, genome),
    }
    written = []
    for rel, content in files.items():
        path = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(rel)
    return written
