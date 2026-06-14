'use client';
// Deterministic registration - mirrors the login design, real /api/auth/register.
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Check } from 'lucide-react';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
import { Button } from '@/components/ui/button';
import { Input, Label, Select, Checkbox } from '@/components/ui/form';

export default function Register() {
  const router = useRouter();
  const [form, setForm] = React.useState({ name: '', email: '', password: '', role: site.roles[0] || 'User' });
  const [terms, setTerms] = React.useState(false);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim() || !form.email.trim() || !form.password.trim()) { setError('All fields are required.'); return; }
    if (!terms) { setError('Please accept the terms to continue.'); return; }
    setBusy(true);
    try {
      await auth.register(form);
      router.push('/dashboard');
    } catch (err) {
      setError(err.message || 'Registration failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="font-display text-2xl font-bold">Create your account</h1>
          <p className="mb-7 mt-1 text-sm text-muted-foreground">Start using {site.appName} in minutes.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" value={form.name} onChange={(e) => set('name', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={form.password} onChange={(e) => set('password', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="role">Role</Label>
              <Select id="role" value={form.role} onChange={(e) => set('role', e.target.value)}>
                {site.roles.map((r) => <option key={r} value={r}>{r}</option>)}
              </Select>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox checked={terms} onChange={(e) => setTerms(e.target.checked)} /> I accept the terms of service
            </label>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" size="lg" disabled={busy}>{busy ? 'Creating...' : 'Create account'}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">
            Already have an account? <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link>
          </p>
        </div>
      </div>

      <div className="relative hidden md:flex md:w-1/2">
        <img src="/assets/auth.jpg" alt="" className="absolute inset-0 h-full w-full object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-black/20" />
        <div className="relative z-10 mt-auto p-10 text-white">
          <div className="mb-4 flex items-center gap-2.5">
            <img src="/assets/logo.jpg" alt="" className="h-9 w-9 rounded-xl object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
            <span className="font-display text-xl font-bold">{site.appName}</span>
          </div>
          <ul className="space-y-2.5">
            {['Free to get started', 'No credit card required', 'Set up in minutes'].map((b) => (
              <li key={b} className="flex items-center gap-2.5 text-white/90">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20"><Check className="h-3.5 w-3.5" /></span>{b}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
