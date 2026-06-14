'use client';
// Deterministic app sidebar (scaffold-owned): logo + links from site.js with
// lucide icons, active highlight, user block + logout.
import * as React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import * as Icons from 'lucide-react';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/extras';
import { Button } from '@/components/ui/button';

function Icon({ name, className }) {
  const Cmp = Icons[name] || Icons.Circle;
  return <Cmp className={className} />;
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = React.useState(null);
  React.useEffect(() => { setUser(auth.currentUser()); }, []);

  const logout = () => {
    auth.logout();
    router.replace('/login');
  };

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r bg-card sticky top-0">
      <Link href="/dashboard" className="flex items-center gap-2.5 px-5 py-5 font-display text-lg font-bold">
        <img
          src="/assets/logo.jpg"
          alt=""
          className="h-9 w-9 rounded-xl object-cover"
          onError={(e) => { e.currentTarget.style.display = 'none'; }}
        />
        <span className="truncate leading-tight">{site.appName}</span>
      </Link>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-4">
        {site.sidebarLinks.filter((l) => {
          // Role-based access: a link with a `roles` list is visible ONLY to
          // those roles. The signed-in user's role comes from the session.
          if (!Array.isArray(l.roles) || l.roles.length === 0) return true;
          return user && l.roles.includes(user.role);
        }).map((l) => {
          const active = pathname === l.href || (l.href !== '/dashboard' && pathname.startsWith(l.href + '/'));
          return (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              )}
            >
              <Icon name={l.icon} className="h-4 w-4 shrink-0" />
              <span className="truncate">{l.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-4">
        <div className="mb-3 flex items-center gap-3">
          <Avatar name={user?.name || user?.email || '?'} />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user?.name || user?.email || 'Guest'}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.role || ''}</p>
          </div>
        </div>
        <Button variant="outline" className="w-full" onClick={logout}>
          <Icons.LogOut /> Logout
        </Button>
      </div>
    </aside>
  );
}
