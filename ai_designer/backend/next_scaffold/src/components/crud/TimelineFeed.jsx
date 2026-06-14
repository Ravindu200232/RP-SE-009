'use client';
// CRUD layout: TIMELINE feed - chosen for log / history entities. Orders rows
// by their date field (newest first; falls back to insertion order) along a
// vertical rail. Each node shows the timestamp, title, fields and row actions.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { fieldLabel, statusVariant } from '@/lib/entities';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/extras';

export default function TimelineFeed({ entity, slug }) {
  const router = useRouter();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try { setRows(await api.list(entity.name)); } catch (e) { setRows([]); } finally { setLoading(false); }
  }, [entity.name]);
  React.useEffect(() => { refresh(); }, [refresh]);

  const fields = entity.fields || [];
  const dateField = fields.find((f) => f.type === 'date');
  const titleField = fields.find((f) => f.type !== 'textarea') || fields[0];
  const metaFields = fields.filter((f) => f !== titleField && f !== dateField && f.name !== 'status').slice(0, 4);

  const ordered = React.useMemo(() => {
    const copy = [...rows];
    if (dateField) copy.sort((a, b) => String(b?.[dateField.name] ?? '').localeCompare(String(a?.[dateField.name] ?? '')));
    else copy.reverse();
    return copy;
  }, [rows, dateField]);

  const del = async (id) => { if (window.confirm('Delete this record?')) { await api.remove(entity.name, id); refresh(); } };

  return (
    <div data-component-id={'crud-' + slug} data-component-label={entity.label + ' (Timeline)'} className="mx-auto max-w-3xl p-6 md:p-8">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold md:text-3xl">{entity.label}</h1>
          <Badge variant="secondary">{rows.length}</Badge>
          <span className="hidden text-xs text-muted-foreground sm:inline">Timeline</span>
        </div>
        <Button onClick={() => router.push(`/e/${slug}/new`)}><Plus /> Add {entity.label}</Button>
      </div>

      {loading ? (
        <p className="py-20 text-center text-muted-foreground">Loading...</p>
      ) : ordered.length === 0 ? (
        <p className="py-20 text-center text-muted-foreground">No records yet.</p>
      ) : (
        <ol className="relative ml-3 border-l-2 border-muted">
          {ordered.map((r) => (
            <li key={r?.id} className="mb-8 ml-6">
              <span className="absolute -left-[9px] mt-1.5 h-4 w-4 rounded-full bg-primary ring-4 ring-background" />
              <div className="rounded-2xl border bg-card p-5 shadow-sm">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {dateField ? String(r?.[dateField.name] ?? '-') : 'Recently added'}
                  {String(r?.status ?? '') !== '' && <Badge variant={statusVariant(r?.status)}>{String(r?.status)}</Badge>}
                </div>
                <h3 className="font-display text-lg font-semibold">{String(r?.[titleField?.name] ?? 'Untitled')}</h3>
                <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
                  {metaFields.map((f) => (
                    <span key={f.name}><span className="font-medium text-foreground/70">{fieldLabel(f)}:</span> {String(r?.[f.name] ?? '-')}</span>
                  ))}
                </div>
                <div className="mt-4 flex gap-1.5">
                  <Button size="sm" variant="outline" onClick={() => router.push(`/e/${slug}/${r?.id}`)}>View</Button>
                  <Button size="sm" variant="outline" onClick={() => router.push(`/e/${slug}/${r?.id}/edit`)}>Edit</Button>
                  <Button size="sm" variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => del(r?.id)}>Delete</Button>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
