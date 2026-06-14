'use client';
// Deterministic notifications center - mark read / dismiss / filter all WORK.
import * as React from 'react';
import { Bell, BellOff, CheckCheck, X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/extras';
import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';

const SEED = [
  { id: 1, icon: 'plus', title: 'New record created', message: 'A new record was added a moment ago.', time: '10m ago', read: false, type: 'System' },
  { id: 2, icon: 'users', title: 'New user registered', message: 'A teammate just joined the workspace.', time: '1h ago', read: false, type: 'Team' },
  { id: 3, icon: 'chart', title: 'Weekly summary ready', message: 'Your weekly performance report is ready to view.', time: '3h ago', read: false, type: 'System' },
  { id: 4, icon: 'check', title: 'Backup completed', message: 'Tonight’s automatic backup finished successfully.', time: '8h ago', read: true, type: 'System' },
  { id: 5, icon: 'mail', title: 'Message received', message: 'You have a new message waiting in your inbox.', time: '1d ago', read: true, type: 'Team' },
  { id: 6, icon: 'star', title: 'Milestone reached', message: 'Your workspace passed 100 records. Nice work!', time: '2d ago', read: true, type: 'System' },
];

export default function Notifications() {
  const [items, setItems] = React.useState(SEED);
  const [tab, setTab] = React.useState('All');
  const unread = items.filter((n) => !n.read).length;
  const view = items.filter((n) => (tab === 'All' ? true : tab === 'Unread' ? !n.read : n.type === tab));

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold md:text-3xl">Notifications</h1>
          {unread > 0 && <Badge>{unread} unread</Badge>}
        </div>
        <Button variant="outline" onClick={() => setItems(items.map((n) => ({ ...n, read: true })))}>
          <CheckCheck /> Mark all as read
        </Button>
      </div>

      <div className="mb-5 flex gap-1.5">
        {['All', 'Unread', 'System', 'Team'].map((t) => (
          <Button key={t} size="sm" variant={tab === t ? 'default' : 'outline'} onClick={() => setTab(t)}>{t}</Button>
        ))}
      </div>

      <div className="space-y-3">
        {view.length === 0 && (
          <Card><CardContent className="flex flex-col items-center gap-2 p-10 text-muted-foreground"><BellOff className="h-8 w-8 opacity-50" /> You're all caught up.</CardContent></Card>
        )}
        {view.map((n) => (
          <Card key={n.id} className={cn(!n.read && 'border-primary/40')}>
            <CardContent className="flex items-start gap-4 p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={n.icon} className="h-4 w-4" /></span>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  {n.title}
                  {!n.read && <span className="h-2 w-2 rounded-full bg-primary" />}
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">{n.message}</p>
                <p className="mt-1 text-xs text-muted-foreground/70">{n.time} - {n.type}</p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                {!n.read && (
                  <Button size="sm" variant="outline" onClick={() => setItems(items.map((x) => (x.id === n.id ? { ...x, read: true } : x)))}>
                    Mark read
                  </Button>
                )}
                <Button size="icon" variant="ghost" aria-label="Dismiss" onClick={() => setItems(items.filter((x) => x.id !== n.id))}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
