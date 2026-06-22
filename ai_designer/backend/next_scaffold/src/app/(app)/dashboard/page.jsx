'use client';
// Rich admin dashboard - driven by the planned data model (@/lib/models) and
// role-filtered via @/lib/access: stat cards with trend pills, 12-month bar
// chart, weekly mini chart, recent-records table, quick actions, notifications.
import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Bell, Plus, TrendingUp, CheckCircle2, UserPlus, FileEdit } from 'lucide-react';
import { auth } from '@/lib/api';
import { site } from '@/lib/site';
import { listColumns, fieldLabel, statusVariant } from '@/lib/entities';
import { Models } from '@/lib/models';
import { canAccess } from '@/lib/access';
import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge, Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/extras';

const CHART = [
  { m: 'Jan', v: 45 }, { m: 'Feb', v: 62 }, { m: 'Mar', v: 38 }, { m: 'Apr', v: 71 },
  { m: 'May', v: 55 }, { m: 'Jun', v: 83 }, { m: 'Jul', v: 64 }, { m: 'Aug', v: 90 },
  { m: 'Sep', v: 58 }, { m: 'Oct', v: 76 }, { m: 'Nov', v: 49 }, { m: 'Dec', v: 88 },
];
const WEEK = [{ d: 'Mon', v: 55 }, { d: 'Tue', v: 80 }, { d: 'Wed', v: 38 }, { d: 'Thu', v: 92 }, { d: 'Fri', v: 66 }];
const TRENDS = ['+12.4%', '+8.1%', '-2.3%', '+5.6%', '+9.9%'];
const NOTIFICATIONS = [
  { t: 'A new record needs review', time: '10m ago' },
  { t: 'Weekly summary is ready', time: '1h ago' },
  { t: 'Backup completed successfully', time: '3h ago' },
];
const ACTIVITY = [
  { icon: Plus, text: 'New record was added', time: '2h ago' },
  { icon: FileEdit, text: 'A record was updated', time: '5h ago' },
  { icon: CheckCircle2, text: 'Weekly report completed', time: '1d ago' },
  { icon: UserPlus, text: 'A new user registered', time: '2d ago' },
];

// Dashboard style presets (component bank: site.styles.dash).
const DASH_STYLES = {
  classic: { card: '', header: '' },
  band: { card: '', header: 'rounded-3xl bg-gradient-to-r from-primary to-primary/70 p-6 text-primary-foreground [&_p]:text-primary-foreground/75' },
  tinted: { card: 'bg-primary/5 border-primary/15', header: '' },
  glass: { card: 'bg-background/60 backdrop-blur border-primary/10 shadow-lg', header: '' },
  outline: { card: 'shadow-none border-2', header: '' },
  bold: { card: 'border-2 border-foreground/15 shadow-[4px_4px_0_0_hsl(var(--primary))]', header: '' },
  'gradient-cards': { card: 'bg-gradient-to-br from-primary/10 to-transparent border-primary/20', header: '' },
  flat: { card: 'shadow-none bg-muted/30 border-0', header: '' },
  ring: { card: 'ring-1 ring-primary/20 border-0 shadow-sm', header: '' },
  mono: { card: 'rounded-md shadow-none', header: 'border-l-4 border-l-primary pl-4' },
};

// Dashboard COMPOSITION (genome dashboard_style -> site.styles.dashLayout): the order of
// the three widget blocks [stats, charts, recent] genuinely changes per app. Literal
// order-* classes (not interpolated) so Tailwind's JIT keeps them.
const DASH_ORDER = {
  'kpi-cards':     ['order-1', 'order-2', 'order-3'],   // stat cards first
  'analytics':     ['order-2', 'order-1', 'order-3'],   // charts first
  'activity-feed': ['order-2', 'order-3', 'order-1'],   // recent/activity first
  'table-first':   ['order-3', 'order-2', 'order-1'],   // records table first
  'operations':    ['order-1', 'order-3', 'order-2'],   // stats, then recent, then charts
};

const ENTITY_ICONS = ['Database', 'Users', 'Package', 'CalendarDays', 'Star', 'Layers'];

export default function Dashboard() {
  const router = useRouter();
  const dashStyle = DASH_STYLES[(site.styles && site.styles.dash) || 'classic'] || DASH_STYLES.classic;
  const [user, setUser] = React.useState(null);
  const [counts, setCounts] = React.useState({});
  const [recent, setRecent] = React.useState([]);
  const [notifOpen, setNotifOpen] = React.useState(false);

  // Role-aware: every model is relationship-aware (refs/access from the planned
  // data model); a model with no access rule is open to everyone, otherwise
  // only the roles canAccess() allows for that collection can see it here.
  const entities = Object.values(Models)
    .filter((m) => m.collection !== 'users' && (!user || canAccess(user.role, m.collection)))
    .map((m, i) => ({
      name: m.collection, label: m.label, slug: m.collection,
      icon: ENTITY_ICONS[i % ENTITY_ICONS.length], fields: m.fields,
    }));

  React.useEffect(() => {
    setUser(auth.currentUser());
  }, []);

  React.useEffect(() => {
    let on = true;
    (async () => {
      const out = {};
      for (const e of entities) {
        try {
          const d = await (await fetch('/api/' + e.name)).json();
          out[e.name] = d.total != null ? d.total : (Array.isArray(d.rows) ? d.rows.length : 0);
        } catch (err) { out[e.name] = 0; }
      }
      if (!on) return;
      setCounts(out);
      if (entities[0]) {
        try {
          const d = await (await fetch('/api/' + entities[0].name)).json();
          setRecent((d.rows || []).slice(0, 5));
        } catch (err) { setRecent([]); }
      }
    })();
    return () => { on = false; };
  }, [user]);

  const first = entities[0];
  const cols = first ? listColumns(first, 3) : [];
  const hasStatus = first && (first.fields || []).some((f) => f.name === 'status');
  const dashLayout = (site.styles && site.styles.dashLayout) || 'kpi-cards';
  const [oStats, oCharts, oRecent] = DASH_ORDER[dashLayout] || DASH_ORDER['kpi-cards'];

  return (
    <div data-component-id="dashboard" data-component-label="Dashboard" className="mx-auto max-w-7xl p-6 md:p-8">
      {/* header + notifications */}
      <div className={'mb-8 flex flex-wrap items-start justify-between gap-4 ' + dashStyle.header}>
        <div>
          <h1 className="font-display text-2xl font-bold md:text-3xl">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Welcome back, {user?.name || user?.email || 'there'} - {new Date().toDateString()}
          </p>
        </div>
        <div className="relative">
          <Button variant="outline" onClick={() => setNotifOpen(!notifOpen)} className="relative">
            <Bell /> Notifications
            <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
              {NOTIFICATIONS.length}
            </span>
          </Button>
          {notifOpen && (
            <Card className="absolute right-0 z-20 mt-2 w-72 p-2 shadow-2xl">
              {NOTIFICATIONS.map((n) => (
                <div key={n.t} className="rounded-lg px-3 py-2.5 hover:bg-accent">
                  <p className="text-sm font-medium">{n.t}</p>
                  <p className="text-xs text-muted-foreground">{n.time}</p>
                </div>
              ))}
              <Link href="/notifications" onClick={() => setNotifOpen(false)} className="block py-2 text-center text-xs font-semibold text-primary hover:underline">
                View all
              </Link>
            </Card>
          )}
        </div>
      </div>

      <div className="flex flex-col">
      {/* stat cards */}
      <div className={"mb-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4 " + oStats}>
        {entities.map((e, i) => (
          <Link key={e.name} href={`/manage/${e.slug}`}>
            <Card className={"transition hover:-translate-y-0.5 hover:shadow-md " + dashStyle.card}>
              <CardContent className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{e.label}</span>
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Icon name={e.icon} className="h-4 w-4" />
                  </span>
                </div>
                <p className="font-display text-3xl font-bold">{counts[e.name] ?? 0}</p>
                <p className="mt-2 flex items-center gap-1.5 text-xs">
                  <Badge variant={TRENDS[i % 5].startsWith('-') ? 'destructive' : 'success'}>{TRENDS[i % 5]}</Badge>
                  <span className="text-muted-foreground">vs last month</span>
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* chart row */}
      <div className={"mb-8 grid gap-6 lg:grid-cols-3 " + oCharts}>
        <Card className={"lg:col-span-2 " + dashStyle.card}>
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
            <CardTitle className="text-base">Overview</CardTitle>
            <span className="text-xs text-muted-foreground">Last 12 months</span>
          </CardHeader>
          <CardContent>
            <div className="flex h-40 items-end gap-2">
              {CHART.map((c) => (
                <div key={c.m} className="flex h-full flex-1 flex-col items-center justify-end">
                  <div className="w-full rounded-t bg-primary/80 transition hover:bg-primary" style={{ height: c.v + '%' }} title={`${c.m}: ${c.v}`} />
                  <span className="mt-1 text-[10px] text-muted-foreground">{c.m}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">This week</CardTitle></CardHeader>
          <CardContent>
            <p className="font-display text-3xl font-bold">
              {Math.max(1, counts[first?.name] ?? 1)}<span className="text-sm font-normal text-muted-foreground"> new</span>
            </p>
            <p className="mb-6 mt-1 flex items-center gap-1 text-xs"><Badge variant="success"><TrendingUp className="mr-1 h-3 w-3" />+3.2%</Badge></p>
            <div className="flex h-16 items-end gap-2">
              {WEEK.map((w) => (
                <div key={w.d} className="flex h-full flex-1 flex-col items-center justify-end">
                  <div className="w-full rounded-t bg-primary/60" style={{ height: w.v + '%' }} title={w.d} />
                  <span className="mt-1 text-[10px] text-muted-foreground">{w.d}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* recent + quick actions */}
      <div className={"mb-8 grid gap-6 lg:grid-cols-3 " + oRecent}>
        <Card className={"lg:col-span-2 " + dashStyle.card}>
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
            <CardTitle className="text-base">Recent {first?.label || 'records'}</CardTitle>
            {first && <Link href={`/manage/${first.slug}`} className="text-xs font-semibold text-primary hover:underline">View all</Link>}
          </CardHeader>
          <CardContent className="pt-0">
            <Table>
              <TableHeader>
                <TableRow>
                  {cols.map((c) => <TableHead key={c.name}>{fieldLabel(c)}</TableHead>)}
                  {hasStatus && <TableHead>Status</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {recent.length === 0 && (
                  <TableRow><TableCell colSpan={cols.length + 1} className="py-8 text-center text-muted-foreground">No records yet</TableCell></TableRow>
                )}
                {recent.map((r) => (
                  <TableRow key={r?.id}>
                    {cols.map((c, i) => (
                      <TableCell key={c.name} className={i === 0 ? 'font-medium' : 'text-muted-foreground'}>{String(r?.[c.name] ?? '-')}</TableCell>
                    ))}
                    {hasStatus && <TableCell><Badge variant={statusVariant(r?.status)}>{String(r?.status ?? '-')}</Badge></TableCell>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base">Quick actions</CardTitle></CardHeader>
            <CardContent className="space-y-2.5 pt-0">
              {entities.slice(0, 3).map((e) => (
                <Button key={e.name} className="w-full justify-start" onClick={() => router.push(`/manage/${e.slug}/new`)}>
                  <Plus /> Add {e.label}
                </Button>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base">Activity</CardTitle></CardHeader>
            <CardContent className="space-y-4 pt-0">
              {ACTIVITY.map((a) => (
                <div key={a.text} className="flex items-start gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <a.icon className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm">{a.text}</p>
                    <p className="text-xs text-muted-foreground">{a.time}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
      </div>
    </div>
  );
}
