'use client';
// CRUD layout: SPLIT-PANE master/detail - chosen for dense record entities you
// inspect one at a time. Left = searchable list; right = full field readout of
// the selected record with Edit/Delete. "Add" routes to the shared /new form.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Search, Pencil, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { statusVariant, fieldLabel, listColumns } from '@/lib/entities';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/form';
import { Badge } from '@/components/ui/extras';

export default function SplitPane({ entity, slug }) {
  const router = useRouter();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [q, setQ] = React.useState('');
  const [selId, setSelId] = React.useState(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try { const d = await api.list(entity.name); setRows(d); setSelId((p) => p ?? (d[0] && d[0].id)); }
    catch (e) { setRows([]); } finally { setLoading(false); }
  }, [entity.name]);
  React.useEffect(() => { refresh(); }, [refresh]);

  const fields = entity.fields || [];
  const titleField = fields.find((f) => f.type !== 'textarea') || fields[0];
  const subField = listColumns(entity, 3)[1];
  const filtered = rows.filter((r) => !q || String(r?.[titleField?.name] ?? '').toLowerCase().includes(q.toLowerCase()));
  const selected = rows.find((r) => r?.id === selId) || filtered[0] || null;

  const del = async (id) => { if (window.confirm('Delete this record?')) { await api.remove(entity.name, id); setSelId(null); refresh(); } };

  return (
    <div data-component-id={'crud-' + slug} data-component-label={entity.label + ' (Split-pane)'} className="mx-auto max-w-7xl p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold md:text-3xl">{entity.label}</h1>
          <Badge variant="secondary">{rows.length}</Badge>
          <span className="hidden text-xs text-muted-foreground sm:inline">Master-detail</span>
        </div>
        <Button onClick={() => router.push(`/e/${slug}/new`)}><Plus /> Add {entity.label}</Button>
      </div>

      <div className="grid gap-6 md:grid-cols-[320px_1fr]">
        <div className="rounded-2xl border bg-card">
          <div className="relative border-b p-3">
            <Search className="absolute left-5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="max-h-[60vh] overflow-y-auto p-2">
            {loading && <p className="py-10 text-center text-sm text-muted-foreground">Loading...</p>}
            {!loading && filtered.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">No records</p>}
            {filtered.map((r) => (
              <button key={r?.id} onClick={() => setSelId(r?.id)} className={'mb-1 w-full rounded-xl px-3 py-2.5 text-left transition ' + (selected && selected.id === r?.id ? 'bg-primary/10 ring-1 ring-primary/30' : 'hover:bg-muted')}>
                <p className="truncate text-sm font-medium">{String(r?.[titleField?.name] ?? 'Untitled')}</p>
                {subField && <p className="truncate text-xs text-muted-foreground">{String(r?.[subField.name] ?? '')}</p>}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border bg-card p-6">
          {!selected ? (
            <p className="py-20 text-center text-muted-foreground">Select a record to view details.</p>
          ) : (
            <>
              <div className="mb-6 flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-display text-2xl font-bold">{String(selected?.[titleField?.name] ?? 'Untitled')}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Record #{String(selected?.id ?? '-')}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => router.push(`/e/${slug}/${selected.id}/edit`)}><Pencil className="h-4 w-4" /> Edit</Button>
                  <Button variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={() => del(selected.id)}><Trash2 className="h-4 w-4" /> Delete</Button>
                </div>
              </div>
              <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
                {fields.map((f) => (
                  <div key={f.name} className={f.type === 'textarea' ? 'sm:col-span-2' : ''}>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{fieldLabel(f)}</dt>
                    <dd className="mt-1 text-sm">
                      {f.name === 'status'
                        ? <Badge variant={statusVariant(selected?.[f.name])}>{String(selected?.[f.name] ?? '-')}</Badge>
                        : String(selected?.[f.name] ?? '-')}
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
