'use client';
// Generic LIST page - serves EVERY entity from site.js metadata (pro-table:
// search, status filter, sort, pagination, delete confirmation dialog).
import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Search, Inbox, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { site } from '@/lib/site';
import { entityBySlug, listColumns, fieldLabel, statusVariant } from '@/lib/entities';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/form';
import { Badge, Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Dialog, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/extras';
import { Card } from '@/components/ui/card';
import KanbanBoard from '@/components/crud/KanbanBoard';
import SplitPane from '@/components/crud/SplitPane';
import SpreadsheetGrid from '@/components/crud/SpreadsheetGrid';
import TimelineFeed from '@/components/crud/TimelineFeed';

// PHASE 4: the Deep Research blueprint assigns each entity a CRUD layout by its
// nature; this maps that choice to a layout component. Anything else -> table.
const LAYOUTS = { kanban: KanbanBoard, 'split-pane': SplitPane, spreadsheet: SpreadsheetGrid, timeline: TimelineFeed };

const PER = 8;

// List style presets (component bank: site.styles.list).
const LIST_STYLES = {
  classic: { card: '', row: '' },
  striped: { card: '', row: 'odd:bg-muted/40' },
  cards: { card: 'border-0 shadow-none bg-transparent [&_table]:border-separate [&_table]:border-spacing-y-2', row: 'bg-card shadow-sm [&_td:first-child]:rounded-l-xl [&_td:last-child]:rounded-r-xl' },
  dense: { card: '[&_td]:py-1.5 [&_th]:h-8 text-[13px]', row: '' },
  soft: { card: 'rounded-3xl bg-muted/30 border-0', row: '' },
  'dark-head': { card: '[&_thead]:bg-zinc-900 [&_thead_th]:text-zinc-300', row: '' },
  bordered: { card: 'border-2 [&_td]:border-r [&_td:last-child]:border-r-0', row: '' },
  'pill-rows': { card: 'border-0 shadow-none bg-transparent [&_table]:border-separate [&_table]:border-spacing-y-2', row: 'bg-muted/50 [&_td:first-child]:rounded-l-full [&_td:last-child]:rounded-r-full' },
  airy: { card: 'border-0 shadow-none [&_td]:py-5', row: 'border-b-2 border-muted' },
  'accent-edge': { card: '', row: 'border-l-2 border-l-transparent hover:border-l-primary' },
};

export default function EntityList() {
  const { entity: slug } = useParams();
  const entity = entityBySlug(slug);
  if (!entity) {
    return <div className="p-10 text-center text-muted-foreground">Unknown section.</div>;
  }
  const Custom = LAYOUTS[entity.crud_layout];
  if (Custom) return <Custom entity={entity} slug={slug} />;
  return <TableView entity={entity} slug={slug} />;
}

function TableView({ entity, slug }) {
  const router = useRouter();
  const listStyle = LIST_STYLES[(site.styles && site.styles.list) || 'classic'] || LIST_STYLES.classic;
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [q, setQ] = React.useState('');
  const [status, setStatus] = React.useState('All');
  const [sort, setSort] = React.useState('Newest');
  const [page, setPage] = React.useState(1);
  const [confirmId, setConfirmId] = React.useState(null);

  const refresh = React.useCallback(async () => {
    if (!entity) return;
    setLoading(true);
    try { setRows(await api.list(entity.name)); } catch (e) { setRows([]); } finally { setLoading(false); }
  }, [entity && entity.name]);

  React.useEffect(() => { refresh(); }, [refresh]);

  const cols = listColumns(entity);
  const hasStatus = (entity.fields || []).some((f) => f.name === 'status');
  const statuses = ['All', ...new Set(rows.map((r) => String(r?.status ?? '')).filter(Boolean))].slice(0, 6);

  const filtered = rows
    .filter((r) => !q || cols.some((c) => String(r?.[c.name] ?? '').toLowerCase().includes(q.toLowerCase())))
    .filter((r) => status === 'All' || String(r?.status ?? '') === status);
  const sorted = sort === 'Newest' ? [...filtered].reverse() : filtered;
  const pages = Math.max(1, Math.ceil(sorted.length / PER));
  const view = sorted.slice((page - 1) * PER, page * PER);

  const removeOne = async (id) => {
    setConfirmId(null);
    await api.remove(entity.name, id);
    refresh();
  };

  return (
    <div data-component-id={'crud-' + slug} data-component-label={entity.label + ' (Table)'} className="mx-auto max-w-7xl p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold md:text-3xl">{entity.label}</h1>
          <Badge variant="secondary">{rows.length} total</Badge>
        </div>
        <Button onClick={() => router.push(`/e/${slug}/new`)}><Plus /> Add {entity.label}</Button>
      </div>

      <Card className="mb-6 flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search..." value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        {hasStatus && statuses.length > 1 && (
          <div className="flex gap-1.5">
            {statuses.map((s) => (
              <Button key={s} size="sm" variant={status === s ? 'default' : 'outline'} onClick={() => { setStatus(s); setPage(1); }}>{s}</Button>
            ))}
          </div>
        )}
        <Select className="w-32" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option>Newest</option>
          <option>Oldest</option>
        </Select>
      </Card>

      <Card className={"overflow-hidden " + listStyle.card}>
        <Table>
          <TableHeader>
            <TableRow>
              {cols.map((c) => <TableHead key={c.name}>{fieldLabel(c)}</TableHead>)}
              {hasStatus && <TableHead>Status</TableHead>}
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={cols.length + 2} className="py-12 text-center text-muted-foreground">Loading...</TableCell></TableRow>
            )}
            {!loading && view.length === 0 && (
              <TableRow>
                <TableCell colSpan={cols.length + 2} className="py-14 text-center">
                  <Inbox className="mx-auto mb-2 h-8 w-8 text-muted-foreground/50" />
                  <p className="font-medium text-muted-foreground">No {entity.label} found</p>
                  <p className="mt-1 text-xs text-muted-foreground/70">Try a different search, or add a new record.</p>
                </TableCell>
              </TableRow>
            )}
            {!loading && view.map((r) => (
              <TableRow key={r?.id} className={listStyle.row}>
                {cols.map((c, i) => (
                  <TableCell key={c.name} className={i === 0 ? 'font-medium' : 'text-muted-foreground'}>
                    {String(r?.[c.name] ?? '-')}
                  </TableCell>
                ))}
                {hasStatus && (
                  <TableCell><Badge variant={statusVariant(r?.status)}>{String(r?.status ?? '-')}</Badge></TableCell>
                )}
                <TableCell>
                  <div className="flex items-center justify-end gap-1.5">
                    <Button size="sm" variant="outline" onClick={() => router.push(`/e/${slug}/${r?.id}`)}>View</Button>
                    <Button size="sm" variant="outline" onClick={() => router.push(`/e/${slug}/${r?.id}/edit`)}>Edit</Button>
                    <Button size="sm" variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => setConfirmId(r?.id)}>Delete</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
          <p className="text-muted-foreground">Page {page} of {pages} - {sorted.length} records</p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button size="sm" variant="outline" disabled={page === pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      </Card>

      <Dialog open={!!confirmId} onOpenChange={() => setConfirmId(null)}>
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-destructive/10 text-destructive"><Trash2 className="h-5 w-5" /></div>
        <DialogTitle>Delete this record?</DialogTitle>
        <DialogDescription>This action cannot be undone.</DialogDescription>
        <DialogFooter>
          <Button variant="outline" onClick={() => setConfirmId(null)}>Cancel</Button>
          <Button variant="destructive" onClick={() => removeOne(confirmId)}>Delete</Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
