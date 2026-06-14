'use client';
// CRUD layout: KANBAN board - chosen for workflow/status entities. Groups rows
// into swimlane columns by the entity's status (or first select) field. Cards
// expose View/Edit/Delete; "Add" routes to the shared /new form.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Plus } from 'lucide-react';
import { api } from '@/lib/api';
import { statusVariant, fieldLabel } from '@/lib/entities';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/extras';

export default function KanbanBoard({ entity, slug }) {
  const router = useRouter();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try { setRows(await api.list(entity.name)); } catch (e) { setRows([]); } finally { setLoading(false); }
  }, [entity.name]);
  React.useEffect(() => { refresh(); }, [refresh]);

  const fields = entity.fields || [];
  const groupField = fields.find((f) => f.name === 'status') || fields.find((f) => f.type === 'select');
  const titleField = fields.find((f) => f.type !== 'textarea') || fields[0];
  const metaFields = fields.filter((f) => f !== titleField && f !== groupField && f.type !== 'textarea').slice(0, 3);

  const columns = React.useMemo(() => {
    if (!groupField) return ['All'];
    const opts = (groupField.options && groupField.options.length) ? groupField.options : [];
    const present = [...new Set(rows.map((r) => String(r?.[groupField.name] ?? '')).filter(Boolean))];
    const merged = [...new Set([...opts, ...present])];
    return merged.length ? merged : ['Unassigned'];
  }, [groupField, rows]);

  const rowsFor = (c) => {
    if (!groupField || c === 'All') return rows;
    return rows.filter((r) => String(r?.[groupField.name] ?? '') === (c === 'Unassigned' ? '' : c));
  };

  const del = async (id) => { if (window.confirm('Delete this record?')) { await api.remove(entity.name, id); refresh(); } };

  return (
    <div data-component-id={'crud-' + slug} data-component-label={entity.label + ' (Kanban)'} className="mx-auto max-w-[1400px] p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold md:text-3xl">{entity.label}</h1>
          <Badge variant="secondary">{rows.length} total</Badge>
          <span className="hidden text-xs text-muted-foreground sm:inline">Kanban board</span>
        </div>
        <Button onClick={() => router.push(`/e/${slug}/new`)}><Plus /> Add {entity.label}</Button>
      </div>

      {loading ? (
        <p className="py-20 text-center text-muted-foreground">Loading...</p>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {columns.map((c) => {
            const items = rowsFor(c);
            return (
              <div key={c} className="w-80 shrink-0">
                <div className="mb-3 flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
                  <span className="flex items-center gap-2 text-sm font-semibold">
                    <span className="h-2.5 w-2.5 rounded-full bg-primary" />{c}
                  </span>
                  <Badge variant="secondary">{items.length}</Badge>
                </div>
                <div className="space-y-3">
                  {items.length === 0 && (
                    <div className="rounded-xl border border-dashed py-8 text-center text-xs text-muted-foreground">No items</div>
                  )}
                  {items.map((r) => (
                    <div key={r?.id} className="group rounded-xl border bg-card p-4 shadow-sm transition hover:shadow-md">
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <p className="font-semibold leading-tight">{String(r?.[titleField?.name] ?? 'Untitled')}</p>
                        {groupField && String(r?.[groupField.name] ?? '') !== '' && (
                          <Badge variant={statusVariant(r?.[groupField.name])}>{String(r?.[groupField.name])}</Badge>
                        )}
                      </div>
                      {metaFields.map((f) => (
                        <p key={f.name} className="truncate text-xs text-muted-foreground">
                          <span className="font-medium text-foreground/70">{fieldLabel(f)}:</span> {String(r?.[f.name] ?? '-')}
                        </p>
                      ))}
                      <div className="mt-3 flex gap-1.5 opacity-0 transition group-hover:opacity-100">
                        <Button size="sm" variant="outline" onClick={() => router.push(`/e/${slug}/${r?.id}`)}>View</Button>
                        <Button size="sm" variant="outline" onClick={() => router.push(`/e/${slug}/${r?.id}/edit`)}>Edit</Button>
                        <Button size="sm" variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => del(r?.id)}>Delete</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
