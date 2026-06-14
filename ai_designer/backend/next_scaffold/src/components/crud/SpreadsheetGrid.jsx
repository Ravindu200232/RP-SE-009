'use client';
// CRUD layout: SPREADSHEET grid - chosen for numeric / money entities. Dense
// cell-bordered table, right-aligned monospace numbers, zebra rows, a sticky
// header and a Σ totals row that sums every numeric column over the filter.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { fieldLabel, statusVariant } from '@/lib/entities';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/form';
import { Badge } from '@/components/ui/extras';

const isNum = (f) => f.type === 'number';

export default function SpreadsheetGrid({ entity, slug }) {
  const router = useRouter();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [q, setQ] = React.useState('');

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try { setRows(await api.list(entity.name)); } catch (e) { setRows([]); } finally { setLoading(false); }
  }, [entity.name]);
  React.useEffect(() => { refresh(); }, [refresh]);

  const fields = (entity.fields || []).filter((f) => f.type !== 'textarea');
  const filtered = rows.filter((r) => !q || fields.some((f) => String(r?.[f.name] ?? '').toLowerCase().includes(q.toLowerCase())));
  const totals = {};
  fields.forEach((f) => { if (isNum(f)) totals[f.name] = filtered.reduce((s, r) => s + (Number(r?.[f.name]) || 0), 0); });

  const del = async (id) => { if (window.confirm('Delete this record?')) { await api.remove(entity.name, id); refresh(); } };

  return (
    <div data-component-id={'crud-' + slug} data-component-label={entity.label + ' (Spreadsheet)'} className="mx-auto max-w-[1400px] p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold md:text-3xl">{entity.label}</h1>
          <Badge variant="secondary">{rows.length} rows</Badge>
          <span className="hidden text-xs text-muted-foreground sm:inline">Spreadsheet</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="w-56 pl-9" placeholder="Filter rows..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Button onClick={() => router.push(`/e/${slug}/new`)}><Plus /> Add</Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-muted/70 backdrop-blur">
            <tr>
              <th className="border-b border-r px-3 py-2 text-left text-xs font-semibold text-muted-foreground">#</th>
              {fields.map((f) => (
                <th key={f.name} className={'border-b border-r px-3 py-2 text-xs font-semibold ' + (isNum(f) ? 'text-right' : 'text-left')}>{fieldLabel(f)}</th>
              ))}
              <th className="border-b px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={fields.length + 2} className="py-12 text-center text-muted-foreground">Loading...</td></tr>}
            {!loading && filtered.length === 0 && <tr><td colSpan={fields.length + 2} className="py-12 text-center text-muted-foreground">No rows</td></tr>}
            {!loading && filtered.map((r, i) => (
              <tr key={r?.id} className="odd:bg-muted/20 hover:bg-primary/5">
                <td className="border-r px-3 py-1.5 text-xs text-muted-foreground">{i + 1}</td>
                {fields.map((f) => (
                  <td key={f.name} className={'border-r px-3 py-1.5 ' + (isNum(f) ? 'text-right font-mono tabular-nums' : '')}>
                    {f.name === 'status'
                      ? <Badge variant={statusVariant(r?.[f.name])}>{String(r?.[f.name] ?? '-')}</Badge>
                      : String(r?.[f.name] ?? '-')}
                  </td>
                ))}
                <td className="whitespace-nowrap px-3 py-1.5 text-right">
                  <button onClick={() => router.push(`/e/${slug}/${r?.id}/edit`)} className="mr-3 text-xs font-medium text-primary hover:underline">Edit</button>
                  <button onClick={() => del(r?.id)} className="text-xs font-medium text-destructive hover:underline">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
          {Object.keys(totals).length > 0 && (
            <tfoot>
              <tr className="border-t-2 bg-muted/40 font-semibold">
                <td className="border-r px-3 py-2 text-xs">Total</td>
                {fields.map((f) => (
                  <td key={f.name} className={'border-r px-3 py-2 ' + (isNum(f) ? 'text-right font-mono tabular-nums' : '')}>
                    {isNum(f) ? totals[f.name].toLocaleString() : ''}
                  </td>
                ))}
                <td className="px-3 py-2" />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
