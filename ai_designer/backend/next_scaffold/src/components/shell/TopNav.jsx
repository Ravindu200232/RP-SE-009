'use client';
// Deterministic app TOP navigation (scaffold-owned): the horizontal counterpart of
// Sidebar, selected when the Design Genome's navigation_pattern maps to a top-nav app
// shell (site.styles.appNav === 'topnav'). Same links + role filtering + logout.
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

export default function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = React.useState(null);
  React.useEffect(() => { setUser(auth.currentUser()); }, []);

  const logout = () => {
    auth.logout();
    router.replace('/login');
  };

  const links = site.sidebarLinks.filter((l) => {
    if (!Array.isArray(l.roles) || l.roles.length === 0) return true;
    return user && l.roles.includes(user.role);
  });

  return (
    <header className="sticky top-0 z-40 border-b bg-card">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 md:px-6">
        <Link href="/dashboard" className="flex shrink-0 items-center gap-2.5 font-display text-lg font-bold">
          <img
            src="/assets/logo.jpg"
            alt=""
            className="h-8 w-8 rounded-lg object-cover"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
          <span className="truncate max-w-[180px]">{site.appName}</span>
        </Link>

        <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
          {links.map((l) => {
            const active = pathname === l.href || (l.href !== '/dashboard' && pathname.startsWith(l.href + '/'));
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  'flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                )}
              >
                <Icon name={l.icon} className="h-4 w-4 shrink-0" />
                <span className="truncate">{l.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          <Avatar name={user?.name || user?.email || '?'} />
          <Button variant="outline" size="sm" onClick={logout}>
            <Icons.LogOut /> Logout
          </Button>
        </div>
      </div>
    </header>
  );
}
