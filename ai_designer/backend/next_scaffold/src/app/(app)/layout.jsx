'use client';
// App shell: client-side auth guard + role guard + deterministic navigation.
// The Design Genome's navigation_pattern picks the orientation (site.styles.appNav):
// a left Sidebar (default for multi-module apps) or a horizontal TopNav.
// Generated pages under (app)/ never re-implement nav or the guard.
import * as React from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/shell/Sidebar';
import TopNav from '@/components/shell/TopNav';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
import { canAccessPage } from '@/lib/access';

export default function AppLayout({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = React.useState(false);
  const [denied, setDenied] = React.useState(false);

  React.useEffect(() => {
    if (site.auth === false) {
      setReady(true);
      return;
    }
    const user = auth.currentUser();
    if (!user) {
      router.replace('/login?next=' + encodeURIComponent(pathname));
      return;
    }
    // Role guard: if pageAccess specifies roles for this route, enforce them.
    if (!canAccessPage(user.role, pathname)) {
      setDenied(true);
      setReady(true);
      return;
    }
    setReady(true);
  }, [router, pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (denied) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-center px-4">
        <p className="text-6xl font-bold text-muted-foreground/30">403</p>
        <h1 className="text-2xl font-bold">Access Denied</h1>
        <p className="text-sm text-muted-foreground">You don&apos;t have permission to view this page.</p>
        <a href="/dashboard" className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          Go to Dashboard
        </a>
      </div>
    );
  }

  if (((site.styles && site.styles.appNav) || 'sidebar') === 'topnav') {
    return (
      <div className="flex min-h-screen flex-col">
        <TopNav />
        <main className="min-w-0 flex-1 overflow-x-hidden p-6">{children}</main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-x-hidden p-6 lg:p-8">{children}</main>
    </div>
  );
}
