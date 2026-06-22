'use client';
// Deterministic marketing navbar (scaffold-owned): logo + primary nav links + right-side
// action links (Cart / Login / Get Started). Links come from site.marketingLinks:
//   - no navGroup or navGroup='primary' → shown in center nav (max 7)
//   - navGroup='right' → shown on right as action buttons (Cart, Checkout, etc.)
import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X, ShoppingCart } from 'lucide-react';
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

const FAMILY_NAV_STYLES = {
  'healthcare-clinical': 'border-sky-100 bg-white/95 text-slate-950 shadow-sm',
  'healthcare-trust-saas': 'border-sky-100 bg-white/95 text-slate-950 shadow-sm',
  'automotive-showroom': 'border-neutral-200 bg-white text-neutral-950',
  'product-commerce': 'border-stone-200 bg-white text-stone-950',
  'ecommerce-product': 'border-neutral-200 bg-white text-neutral-950',
  'developer-console': 'border-slate-800 bg-slate-950 text-slate-50 [&_a]:text-slate-300 [&_a:hover]:text-white',
  'ai-devtools': 'border-slate-800 bg-slate-950 text-slate-50 [&_a]:text-slate-300 [&_a:hover]:text-white',
  'learning-editorial': 'border-amber-200 bg-amber-50/95 text-slate-950',
  'education-media': 'border-amber-200 bg-amber-50/95 text-slate-950',
  'restaurant-reservation': 'border-orange-200 bg-stone-50/95 text-stone-950',
  'travel-destination': 'border-sky-200 bg-cyan-50/90 text-slate-950',
  'real-estate-listings': 'border-emerald-100 bg-white/95 text-stone-950 shadow-sm',
  'fitness-coaching': 'border-lime-200 bg-lime-50/95 text-slate-950',
  'finance-trust': 'border-emerald-100 bg-white/95 text-slate-950 shadow-sm',
  'fintech-trust': 'border-emerald-100 bg-white/95 text-slate-950 shadow-sm',
  'creative-portfolio': 'border-zinc-200 bg-white text-zinc-950',
  'creative-agency': 'border-zinc-200 bg-white text-zinc-950',
  'operations-console': 'border-indigo-100 bg-white text-slate-950 shadow-sm',
  'operational-business': 'border-indigo-100 bg-white text-slate-950 shadow-sm',
};

const FAMILY_BUTTON_STYLES = {
  'healthcare-clinical': 'rounded-xl bg-blue-600 text-white hover:bg-blue-700',
  'healthcare-trust-saas': 'rounded-xl bg-blue-600 text-white hover:bg-blue-700',
  'automotive-showroom': 'rounded-full bg-neutral-950 text-white hover:bg-neutral-800',
  'product-commerce': 'rounded-full bg-stone-950 text-white hover:bg-stone-800',
  'ecommerce-product': 'rounded-full bg-neutral-950 text-white hover:bg-neutral-800',
  'developer-console': 'rounded-lg bg-violet-500 text-white hover:bg-violet-400',
  'ai-devtools': 'rounded-lg bg-violet-500 text-white hover:bg-violet-400',
  'learning-editorial': 'rounded-2xl bg-cyan-700 text-white hover:bg-cyan-800',
  'education-media': 'rounded-2xl bg-cyan-700 text-white hover:bg-cyan-800',
  'restaurant-reservation': 'rounded-full bg-rose-700 text-white hover:bg-rose-800',
  'travel-destination': 'rounded-full bg-teal-700 text-white hover:bg-teal-800',
  'real-estate-listings': 'rounded-xl bg-emerald-700 text-white hover:bg-emerald-800',
  'fitness-coaching': 'rounded-full bg-lime-600 text-slate-950 hover:bg-lime-500',
  'finance-trust': 'rounded-xl bg-emerald-700 text-white hover:bg-emerald-800',
  'fintech-trust': 'rounded-xl bg-emerald-700 text-white hover:bg-emerald-800',
  'creative-portfolio': 'rounded-none bg-fuchsia-600 text-white hover:bg-fuchsia-700',
  'creative-agency': 'rounded-none bg-fuchsia-600 text-white hover:bg-fuchsia-700',
  'operations-console': 'rounded-lg bg-indigo-700 text-white hover:bg-indigo-800',
  'operational-business': 'rounded-lg bg-indigo-700 text-white hover:bg-indigo-800',
};

export default function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const navStyle = NAV_STYLES[(site.styles && site.styles.nav) || 'blur'] || NAV_STYLES.blur;
  const navVariant = (site.styles && site.styles.navVariant) || 'centered topnav';
  const inspirationFamily = (site.styles && site.styles.inspirationFamily) || '';
  const visualFamily = (site.styles && site.styles.visualFamily) || inspirationFamily;
  const navRecipe = (site.styles && site.styles.navRecipe) || '';
  const familyNavStyle = FAMILY_NAV_STYLES[visualFamily] || FAMILY_NAV_STYLES[inspirationFamily] || '';
  const familyButtonStyle = FAMILY_BUTTON_STYLES[visualFamily] || FAMILY_BUTTON_STYLES[inspirationFamily] || '';
  // The public marketing navbar is ALWAYS a top bar. A fixed left side-rail
  // (navVariant='sidebar') overlaps the landing content, which reserves no left
  // gutter — the app shell has its own Sidebar for logged-in pages instead.
  const isSideNav = false;
  const isUtility = navVariant === 'utility bar';
  const isAction = navVariant === 'action topnav';

  // Split links: primary (center nav) vs right-side action links (Cart, Checkout).
  const allLinks = site.marketingLinks || [];
  const primaryLinks = allLinks.filter((l) => !l.navGroup || l.navGroup === 'primary');
  const actionLinks = allLinks.filter((l) => l.navGroup === 'right');

  return (
    <header
      data-component-id="navbar"
      data-component-label="Navigation bar"
      data-genome-nav-variant={navVariant}
      data-inspiration-family={inspirationFamily}
      data-visual-family={visualFamily}
      data-nav-recipe={navRecipe}
      className={cn(isSideNav ? 'sticky top-0 z-40 w-full md:fixed md:left-4 md:top-4 md:w-60' : 'sticky top-0 z-40 w-full', navStyle, familyNavStyle)}
    >
      {isUtility && (
        <div className="border-b bg-primary/10 px-4 py-2 text-xs font-semibold text-primary">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <span>Priority support</span>
            <span>Emergency contact available 24/7</span>
          </div>
        </div>
      )}
      <nav className={cn(
        'mx-auto flex max-w-7xl items-center justify-between px-4 md:px-6',
        isSideNav ? 'h-auto flex-col items-stretch gap-5 rounded-2xl p-4 shadow-xl' : 'h-16',
        navVariant === 'floating nav' && 'rounded-2xl',
        navVariant === 'centered topnav' && 'grid grid-cols-[1fr_auto_1fr]',
        isAction && 'gap-8'
      )}>
        {/* Logo */}
        <Link href="/" className={cn('flex items-center gap-2.5 font-display text-lg font-bold shrink-0', isSideNav && 'justify-start')}>
          <img
            src="/assets/logo.jpg"
            alt=""
            className="h-8 w-8 rounded-lg object-cover"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
          <span className="truncate max-w-[220px]">{site.appName}</span>
        </Link>

        {/* Primary nav links (desktop) */}
        <div className={cn(
          'hidden md:flex',
          isSideNav ? 'flex-col items-stretch gap-1' : 'items-center gap-5',
          navVariant === 'centered topnav' && 'justify-center',
          isAction && 'gap-4'
        )}>
          {primaryLinks.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                'text-sm font-medium transition-colors hover:text-foreground whitespace-nowrap',
                isSideNav && 'rounded-xl px-3 py-2 hover:bg-accent',
                isAction && 'rounded-full px-3 py-1.5 hover:bg-accent',
                pathname === l.href ? 'text-primary' : 'text-muted-foreground'
              )}
            >
              {l.label}
            </Link>
          ))}
        </div>

        {/* Right side: action links (Cart etc.) + auth buttons */}
        <div className={cn('flex items-center gap-2', navVariant === 'centered topnav' && 'justify-self-end', isSideNav && 'flex-col items-stretch')}>
          {/* Action links (Cart, Checkout, etc.) - compact icon+label */}
          {actionLinks.map((l) => {
            const isCart = l.href.includes('cart');
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  'hidden sm:inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent',
                  pathname === l.href ? 'text-primary border-primary/40' : 'text-muted-foreground'
                )}
              >
                {isCart && <ShoppingCart className="h-4 w-4" />}
                {l.label}
              </Link>
            );
          })}

          {/* Auth buttons */}
          {site.auth !== false ? (
            <>
              <Button asChild={false} variant="ghost" className={cn('hidden sm:inline-flex', isSideNav && 'w-full')} onClick={() => (window.location.href = '/login')}>
                Login
              </Button>
              <Button className={cn('hidden sm:inline-flex', isAction && 'px-6', isSideNav && 'w-full', familyButtonStyle)} onClick={() => (window.location.href = '/register')}>
                {isAction ? 'Start Now' : 'Get Started'}
              </Button>
            </>
          ) : (
            <Button className={cn('hidden sm:inline-flex', isSideNav && 'w-full', familyButtonStyle)} onClick={() => (window.location.href = '/dashboard')}>
              Open App
            </Button>
          )}

          {/* Mobile menu toggle */}
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Menu" onClick={() => setOpen(!open)}>
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </nav>

      {/* Mobile menu */}
      {open && (
        <div className="border-t bg-background px-4 py-3 md:hidden">
          {primaryLinks.map((l) => (
            <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2 text-sm font-medium hover:bg-accent">
              {l.label}
            </Link>
          ))}
          {actionLinks.length > 0 && (
            <div className="mt-2 border-t pt-2">
              {actionLinks.map((l) => (
                <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent">
                  {l.label}
                </Link>
              ))}
            </div>
          )}
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
