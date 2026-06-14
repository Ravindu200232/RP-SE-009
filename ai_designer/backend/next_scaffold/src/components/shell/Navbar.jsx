'use client';
// Deterministic marketing navbar (scaffold-owned): logo + links from site.js,
// login/get-started CTAs, working mobile menu.
import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { site } from '@/lib/site';
import { cn } from '@/lib/utils';

// Navbar style presets (component bank: site.styles.nav picks one per app).
const NAV_STYLES = {
  solid: 'border-b bg-background shadow-sm',
  blur: 'border-b bg-background/70 backdrop-blur supports-[backdrop-filter]:bg-background/55',
  pill: 'mx-auto mt-3 max-w-6xl rounded-full border bg-background/90 shadow-lg backdrop-blur',
  dark: 'border-b border-white/10 bg-zinc-950 text-white [&_a]:text-zinc-300 [&_a:hover]:text-white',
  minimal: 'bg-background',
  'accent-top': 'border-b bg-background shadow-sm border-t-4 border-t-primary',
  underline: 'bg-background border-b-2 border-b-primary/60',
  'accent-solid': 'bg-primary text-primary-foreground [&_a]:text-primary-foreground/85 [&_a:hover]:text-primary-foreground shadow-md',
  floating: 'mx-auto mt-3 max-w-6xl rounded-2xl border bg-background/85 shadow-xl backdrop-blur',
  tinted: 'border-b bg-primary/5 backdrop-blur',
};

export default function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const navStyle = NAV_STYLES[(site.styles && site.styles.nav) || 'blur'] || NAV_STYLES.blur;

  return (
    <header data-component-id="navbar" data-component-label="Navigation bar" className={'sticky top-0 z-40 w-full ' + navStyle}>
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2.5 font-display text-lg font-bold">
          <img
            src="/assets/logo.jpg"
            alt=""
            className="h-8 w-8 rounded-lg object-cover"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
          <span className="truncate max-w-[220px]">{site.appName}</span>
        </Link>

        <div className="hidden items-center gap-6 md:flex">
          {site.marketingLinks.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                'text-sm font-medium transition-colors hover:text-foreground',
                pathname === l.href ? 'text-primary' : 'text-muted-foreground'
              )}
            >
              {l.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {site.auth !== false ? (
            <>
              <Button asChild={false} variant="ghost" className="hidden sm:inline-flex" onClick={() => (window.location.href = '/login')}>
                Login
              </Button>
              <Button className="hidden sm:inline-flex" onClick={() => (window.location.href = '/register')}>
                Get Started
              </Button>
            </>
          ) : (
            <Button className="hidden sm:inline-flex" onClick={() => (window.location.href = '/dashboard')}>
              Open App
            </Button>
          )}
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Menu" onClick={() => setOpen(!open)}>
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </nav>

      {open && (
        <div className="border-t bg-background px-4 py-3 md:hidden">
          {site.marketingLinks.map((l) => (
            <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2 text-sm font-medium hover:bg-accent">
              {l.label}
            </Link>
          ))}
          <div className="mt-2 flex gap-2 border-t pt-3">
            {site.auth !== false ? (
              <>
                <Link href="/login" onClick={() => setOpen(false)} className="flex-1 rounded-md border px-3 py-2 text-center text-sm font-medium">Login</Link>
                <Link href="/register" onClick={() => setOpen(false)} className="flex-1 rounded-md bg-primary px-3 py-2 text-center text-sm font-medium text-primary-foreground">Get Started</Link>
              </>
            ) : (
              <Link href="/dashboard" onClick={() => setOpen(false)} className="flex-1 rounded-md bg-primary px-3 py-2 text-center text-sm font-medium text-primary-foreground">Open App</Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
