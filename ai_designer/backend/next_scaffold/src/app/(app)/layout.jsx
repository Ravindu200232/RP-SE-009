'use client';
// App shell: client-side auth guard + deterministic navigation. The Design Genome's
// navigation_pattern picks the orientation (site.styles.appNav): a left Sidebar or a
// horizontal TopNav. Generated pages under (app)/ never re-implement nav or the guard.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/shell/Sidebar';
import TopNav from '@/components/shell/TopNav';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';

export default function AppLayout({ children }) {
  const router = useRouter();
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    if (site.auth === false) {        // auth disabled in the interview -> open app
      setReady(true);
    } else if (!auth.currentUser()) {
      router.replace('/login');
    } else {
      setReady(true);
    }
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (((site.styles && site.styles.appNav) || 'sidebar') === 'topnav') {
    return (
      <div className="flex min-h-screen flex-col">
        <TopNav />
        <main className="min-w-0 flex-1 overflow-x-hidden">{children}</main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-x-hidden">{children}</main>
    </div>
  );
}
