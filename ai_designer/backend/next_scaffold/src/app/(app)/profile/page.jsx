'use client';
// Deterministic profile page (session user + read-only details).
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Settings } from 'lucide-react';
import { auth } from '@/lib/api';
import { Avatar, Badge, Separator } from '@/components/ui/extras';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function Profile() {
  const router = useRouter();
  const [user, setUser] = React.useState(null);
  React.useEffect(() => { setUser(auth.currentUser()); }, []);

  const rows = [
    ['Name', user?.name || '-'],
    ['Email', user?.email || '-'],
    ['Role', user?.role || '-'],
    ['Member since', '2026'],
  ];

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div className="flex items-center gap-4">
            <Avatar name={user?.name || user?.email || '?'} className="h-14 w-14 text-lg" />
            <div>
              <CardTitle className="font-display text-2xl">{user?.name || 'Guest'}</CardTitle>
              <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                {user?.email} {user?.role && <Badge variant="secondary">{user.role}</Badge>}
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={() => router.push('/settings')}><Settings /> Settings</Button>
        </CardHeader>
        <CardContent>
          <Separator className="mb-5" />
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {rows.map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{k}</dt>
                <dd className="mt-1 text-sm">{v}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
