'use client';
// Generic ROLE WORKSPACE - personal view for any role (resolved from the URL):
// today cards, my items from the most relevant entity, agenda with toggles.
import * as React from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { CalendarDays, CheckCircle2, ListTodo, Plus } from 'lucide-react';
import { api, auth } from '@/lib/api';
import { site } from '@/lib/site';
import { allEntities, listColumns, fieldLabel, statusVariant } from '@/lib/entities';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge, Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/extras';
import { cn } from '@/lib/utils';

const AGENDA = [
  { id: 1, time: '09:00', text: 'Review new items', done: true },
  { id: 2, time: '11:30', text: 'Team stand-up meeting', done: false },
  { id: 3, time: '14:00', text: 'Process pending requests', done: false },
  { id: 4, time: '16:30', text: 'Prepare tomorrow’s plan', done: false },
];

export default function RoleWorkspace() {
  const { role: slug } = useParams();
  const router = useRouter();
  const role = (site.roles || []).find((r) => r.toLowerCase().replace(/[^a-z0-9]+/g, '-') === slug) || slug;
  const entities = allEntities();
  const main = entities[0];
  const [user, setUser] = React.useState(null);
  const [denied, setDenied] = React.useState(false);
  const [rows, setRows] = React.useState([]);
  const [agenda, setAgenda] = React.useState(AGENDA);

  React.useEffect(() => {
    const u = auth.currentUser();
    setUser(u);
    // Role-based access: a workspace belongs to its role (the primary/admin
    // role may view any). Others get a friendly denial, not someone else's desk.
    const primary = (site.roles || [])[0];
    if (u && u.role !== role && u.role !== primary) {
      setDenied(true);
      return;
    }
    if (main) api.list(main.name).then((r) => setRows(r.slice(0, 6))).catch(() => setRows([]));
  }, []);

  if (denied) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <Card className="max-w-md p-8 text-center">
          <p className="mb-1 font-display text-xl font-bold">No access to this workspace</p>
          <p className="mb-6 text-sm text-muted-foreground">The {String(role)} workspace is only visible to {String(role)}s.</p>
          <Button onClick={() => router.push('/dashboard')}>Back to Dashboard</Button>
        </Card>
      </div>
    );
  }

  const cols = main ? listColumns(main, 3) : [];
  const hasStatus = main && (main.fields || []).some((f) => f.name === 'status');
  const doneCount = agenda.filter((a) => a.done).length;

  return (
    <div className="mx-auto max-w-7xl p-6 md:p-8">
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold md:text-3xl">My Workspace</h1>
        <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
          Good day, {user?.name || 'there'} <Badge variant="secondary">{String(role)}</Badge>
        </p>
      </div>

      <div className="mb-8 grid gap-6 sm:grid-cols-3">
        <Card><CardContent className="flex items-center gap-4 p-5">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><ListTodo className="h-5 w-5" /></span>
          <div><p className="text-sm text-muted-foreground">Assigned to me</p><p className="font-display text-2xl font-bold">{rows.length}</p></div>
        </CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-5">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><CalendarDays className="h-5 w-5" /></span>
          <div><p className="text-sm text-muted-foreground">Today's agenda</p><p className="font-display text-2xl font-bold">{agenda.length}</p></div>
        </CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-5">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><CheckCircle2 className="h-5 w-5" /></span>
          <div><p className="text-sm text-muted-foreground">Completed</p><p className="font-display text-2xl font-bold">{doneCount}/{agenda.length}</p></div>
        </CardContent></Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
            <CardTitle className="text-base">My {main?.label || 'items'}</CardTitle>
            {main && <Link href={`/e/${main.slug}`} className="text-xs font-semibold text-primary hover:underline">View all</Link>}
          </CardHeader>
          <CardContent className="pt-0">
            <Table>
              <TableHeader>
                <TableRow>
                  {cols.map((c) => <TableHead key={c.name}>{fieldLabel(c)}</TableHead>)}
                  {hasStatus && <TableHead>Status</TableHead>}
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.length === 0 && <TableRow><TableCell colSpan={cols.length + 2} className="py-8 text-center text-muted-foreground">Nothing assigned yet</TableCell></TableRow>}
                {rows.map((r) => (
                  <TableRow key={r?.id}>
                    {cols.map((c, i) => <TableCell key={c.name} className={i === 0 ? 'font-medium' : 'text-muted-foreground'}>{String(r?.[c.name] ?? '-')}</TableCell>)}
                    {hasStatus && <TableCell><Badge variant={statusVariant(r?.status)}>{String(r?.status ?? '-')}</Badge></TableCell>}
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => main && router.push(`/e/${main.slug}/${r?.id}`)}>Open</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base">Today's agenda</CardTitle></CardHeader>
            <CardContent className="space-y-2 pt-0">
              {agenda.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setAgenda(agenda.map((x) => (x.id === a.id ? { ...x, done: !x.done } : x)))}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition hover:bg-accent"
                >
                  <span className={cn('flex h-5 w-5 shrink-0 items-center justify-center rounded-md border', a.done ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/40')}>
                    {a.done && <CheckCircle2 className="h-3.5 w-3.5" />}
                  </span>
                  <span className="w-12 shrink-0 text-xs font-semibold text-muted-foreground">{a.time}</span>
                  <span className={cn('min-w-0 truncate text-sm', a.done && 'line-through opacity-50')}>{a.text}</span>
                </button>
              ))}
            </CardContent>
          </Card>
          {main && (
            <Button className="w-full" onClick={() => router.push(`/e/${main.slug}/new`)}><Plus /> Add {main.label}</Button>
          )}
        </div>
      </div>
    </div>
  );
}
