'use client';
// App shell: client-side auth guard + deterministic Sidebar. Generated pages
// under (app)/ never re-implement navigation or the guard.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/shell/Sidebar';
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

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-x-hidden">{children}</main>
    </div>
  );
}
