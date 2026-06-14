'use client';
// Deterministic login - split brand panel + form, real auth against /api/auth.
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
import { Button } from '@/components/ui/button';
import { Input, Label, Checkbox } from '@/components/ui/form';

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
    try {
      await auth.login(email.trim(), password);
      router.push('/dashboard');
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      <div className="relative hidden md:flex md:w-1/2">
        <img src="/assets/auth.jpg" alt="" className="absolute inset-0 h-full w-full object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-black/20" />
        <div className="relative z-10 mt-auto p-10 text-white">
          <div className="mb-3 flex items-center gap-2.5">
            <img src="/assets/logo.jpg" alt="" className="h-9 w-9 rounded-xl object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
            <span className="font-display text-xl font-bold">{site.appName}</span>
          </div>
          <p className="max-w-sm text-white/85">{site.tagline}</p>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="font-display text-2xl font-bold">Welcome back</h1>
          <p className="mb-7 mt-1 text-sm text-muted-foreground">Please sign in to continue.</p>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-muted-foreground"><Checkbox /> Remember me</label>
              <a href="#" className="font-medium text-primary hover:underline">Forgot password?</a>
            </div>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" size="lg" disabled={busy}>{busy ? 'Signing in...' : 'Login'}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">
            Don't have an account? <Link href="/register" className="font-medium text-primary hover:underline">Register here</Link>
          </p>
          <p className="mt-3 text-center text-xs text-muted-foreground/70">Demo: admin@example.com / password123</p>
        </div>
      </div>
    </div>
  );
}
