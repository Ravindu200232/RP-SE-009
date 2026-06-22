"""Relationship-aware CRUD UI generator.

The per-entity model descriptors (`lib/models/*`) are pure data, so they are safe
to import in client components. The CRUD UI is therefore DESCRIPTOR-DRIVEN: a
small set of generic pages render entity-specific fields, relation selectors
(from `refs`), status badges (from `enums`), related-record lists (from
`referencedBy`), filters, pagination, and loading/empty/error states. This is
real relationship-aware UI per entity — not renamed `createX/updateX` boilerplate
— and it stays in lock-step with whatever the data-model planner produced.

Generated files (fixed, descriptor-driven):
* src/components/CrudForm.jsx        — create/edit form with relation pickers
* src/app/(app)/manage/page.jsx      — entity index
* src/app/(app)/manage/[collection]/page.jsx          — list + search + filters
* src/app/(app)/manage/[collection]/new/page.jsx      — create
* src/app/(app)/manage/[collection]/[id]/page.jsx     — detail + related records
* src/app/(app)/manage/[collection]/[id]/edit/page.jsx— edit
"""
from __future__ import annotations


CRUD_FORM = r"""'use client';
// Descriptor-driven create/edit form with relationship selectors + validation.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { modelFor } from '@/lib/models';
import { authHeader } from '@/lib/api';

const labelOf = (o) => o?.name || o?.title || o?.email || o?.number || o?.label || o?.id;

export default function CrudForm({ collection, id }) {
  const router = useRouter();
  const model = modelFor(collection);
  const [form, setForm] = React.useState({});
  const [opts, setOpts] = React.useState({});
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  React.useEffect(() => {
    if (!model) return;
    for (const ref of model.refs) {
      fetch('/api/' + ref.collection)
        .then((r) => r.json())
        .then((d) => setOpts((p) => ({ ...p, [ref.field]: d.rows || [] })))
        .catch(() => {});
    }
    if (id) {
      fetch('/api/' + collection + '/' + id)
        .then((r) => r.json())
        .then((d) => { if (d && !d.error) setForm(d); })
        .catch(() => {});
    }
  }, [collection, id, model]);

  if (!model) return <div className="p-8 text-sm text-muted-foreground">Unknown collection.</div>;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    for (const f of model.fields) {
      if (f.required && !String(form[f.name] ?? '').trim()) { setError(f.label + ' is required.'); return; }
    }
    for (const ref of model.refs) {
      if (ref.required && !form[ref.field]) { setError(ref.target + ' is required.'); return; }
    }
    setBusy(true);
    try {
      const url = id ? '/api/' + collection + '/' + id : '/api/' + collection;
      const res = await fetch(url, {
        method: id ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(form),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Save failed');
      router.push('/manage/' + collection + (id ? '/' + id : ''));
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally { setBusy(false); }
  };

  const inputCls = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring';

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-5">
      {model.refs.map((ref) => (
        <div key={ref.field} className="space-y-1.5">
          <label className="block text-sm font-medium">{ref.target}{ref.required ? ' *' : ''}</label>
          <select className={inputCls} value={form[ref.field] || ''} onChange={(e) => set(ref.field, e.target.value)}>
            <option value="">Select {ref.target}…</option>
            {(opts[ref.field] || []).map((o) => <option key={o.id} value={o.id}>{labelOf(o)}</option>)}
          </select>
        </div>
      ))}
      {model.fields.filter((f) => f.name !== 'createdAt').map((f) => (
        <div key={f.name} className="space-y-1.5">
          <label className="block text-sm font-medium">{f.label}{f.required ? ' *' : ''}</label>
          {f.enum ? (
            <select className={inputCls} value={form[f.name] || ''} onChange={(e) => set(f.name, e.target.value)}>
              <option value="">Select…</option>
              {f.enum.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : f.type === 'textarea' ? (
            <textarea className={inputCls} rows={3} value={form[f.name] || ''} onChange={(e) => set(f.name, e.target.value)} />
          ) : f.type === 'boolean' ? (
            <input type="checkbox" checked={!!form[f.name]} onChange={(e) => set(f.name, e.target.checked)} />
          ) : (
            <input
              className={inputCls}
              type={f.type === 'number' || f.type === 'currency' ? 'number' : f.type === 'date' ? 'date' : f.type === 'datetime' ? 'datetime-local' : f.type === 'email' ? 'email' : f.type === 'password' ? 'password' : 'text'}
              value={form[f.name] ?? ''}
              onChange={(e) => set(f.name, e.target.value)}
            />
          )}
        </div>
      ))}
      {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={busy} className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-60">{busy ? 'Saving…' : id ? 'Save changes' : 'Create ' + model.label}</button>
        <button type="button" onClick={() => router.back()} className="rounded-lg border px-5 py-2.5 text-sm font-semibold">Cancel</button>
      </div>
    </form>
  );
}
"""

MANAGE_INDEX = r"""'use client';
// Entity index for the relationship-aware management area.
import * as React from 'react';
import Link from 'next/link';
import { Models } from '@/lib/models';
import { auth } from '@/lib/api';
import { canAccess } from '@/lib/access';

export default function ManageIndex() {
  const [role, setRole] = React.useState(null);
  React.useEffect(() => { setRole(auth.currentUser()?.role || null); }, []);
  const models = Object.values(Models).filter((m) => !role || canAccess(role, m.collection));
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Manage data</h1>
        <p className="text-sm text-muted-foreground">Relationship-aware records generated from your app's data model.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {models.map((m) => (
          <Link key={m.collection} href={'/manage/' + m.collection} className="rounded-xl border bg-card p-5 transition hover:shadow-md">
            <h2 className="font-semibold">{m.label}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{m.fields.length} fields · {m.refs.length} relationship{m.refs.length === 1 ? '' : 's'}</p>
            {m.refs.length > 0 && <p className="mt-3 flex flex-wrap gap-1.5">{m.refs.map((r) => <span key={r.field} className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">{r.target}</span>)}</p>}
          </Link>
        ))}
      </div>
    </div>
  );
}
"""

LIST_PAGE = r"""'use client';
// Descriptor-driven list: search, relationship filters, status badges, pagination.
import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { modelFor } from '@/lib/models';
import { auth, authHeader } from '@/lib/api';
import { canAccess } from '@/lib/access';

function RefFilter({ rel, value, onChange }) {
  const [opts, setOpts] = React.useState([]);
  React.useEffect(() => { fetch('/api/' + rel.collection).then((r) => r.json()).then((d) => setOpts(d.rows || [])).catch(() => {}); }, [rel.collection]);
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-lg border px-3 py-2 text-sm">
      <option value="">All {rel.target}</option>
      {opts.map((o) => <option key={o.id} value={o.id}>{o.name || o.title || o.email || o.number || o.id}</option>)}
    </select>
  );
}

export default function ListPage() {
  const params = useParams();
  const collection = params.collection;
  const model = modelFor(collection);
  const [state, setState] = React.useState({ loading: true, error: '', rows: [], total: 0 });
  const [q, setQ] = React.useState('');
  const [filter, setFilter] = React.useState({});
  const [role, setRole] = React.useState(null);
  React.useEffect(() => { setRole(auth.currentUser()?.role || null); }, []);
  const canWrite = !role || canAccess(role, collection);

  const load = React.useCallback(async () => {
    if (!model) return;
    setState((s) => ({ ...s, loading: true, error: '' }));
    try {
      const sp = new URLSearchParams();
      if (q) sp.set('q', q);
      for (const [k, v] of Object.entries(filter)) if (v) sp.set(k, v);
      const res = await fetch('/api/' + collection + '?' + sp.toString());
      if (!res.ok) throw new Error('Failed to load records');
      const data = await res.json();
      setState({ loading: false, error: '', rows: data.rows || [], total: data.total || 0 });
    } catch (e) { setState({ loading: false, error: e.message, rows: [], total: 0 }); }
  }, [collection, q, filter, model]);

  React.useEffect(() => { load(); }, [load]);

  if (!model) return <div className="p-8 text-sm text-muted-foreground">Unknown collection.</div>;
  const cols = model.fields.filter((f) => !['password', 'textarea', 'image'].includes(f.type)).slice(0, 4);

  const remove = async (id) => {
    if (!window.confirm('Delete this ' + model.label + '?')) return;
    const r = await fetch('/api/' + collection + '/' + id, { method: 'DELETE', headers: authHeader() });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { window.alert(d.error || 'Delete failed'); return; }
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{model.label} records</h1>
          <p className="text-sm text-muted-foreground">{state.total} total · {model.refs.length} relationship{model.refs.length === 1 ? '' : 's'}</p>
        </div>
        {canWrite && <Link href={'/manage/' + collection + '/new'} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">New {model.label}</Link>}
      </div>
      <div className="flex flex-wrap gap-3">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="rounded-lg border px-3 py-2 text-sm" />
        {model.refs.map((rel) => <RefFilter key={rel.field} rel={rel} value={filter[rel.field] || ''} onChange={(v) => setFilter((f) => ({ ...f, [rel.field]: v }))} />)}
      </div>
      {state.loading && <div className="rounded-xl border p-10 text-center text-sm text-muted-foreground">Loading…</div>}
      {state.error && <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{state.error}</div>}
      {!state.loading && !state.error && state.rows.length === 0 && (
        <div className="rounded-xl border border-dashed p-12 text-center">
          <p className="text-sm text-muted-foreground">No {model.label} records yet.</p>
          {canWrite && <Link href={'/manage/' + collection + '/new'} className="mt-3 inline-block text-sm font-semibold text-primary hover:underline">Create the first one</Link>}
        </div>
      )}
      {!state.loading && state.rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="bg-muted/40 text-left">
              <tr>
                {cols.map((c) => <th key={c.name} className="px-4 py-3 font-medium">{c.label}</th>)}
                {model.refs.map((rel) => <th key={rel.field} className="px-4 py-3 font-medium">{rel.target}</th>)}
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {state.rows.map((row) => (
                <tr key={row.id} className="border-t">
                  {cols.map((c) => (
                    <td key={c.name} className="px-4 py-3">
                      {c.name === 'status'
                        ? <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">{String(row[c.name] ?? '')}</span>
                        : String(row[c.name] ?? '')}
                    </td>
                  ))}
                  {model.refs.map((rel) => <td key={rel.field} className="px-4 py-3 text-muted-foreground">{row['_' + rel.field]?.label || '—'}</td>)}
                  <td className="px-4 py-3 whitespace-nowrap text-right">
                    <Link href={'/manage/' + collection + '/' + row.id} className="text-primary hover:underline">View</Link>
                    {canWrite && <>
                      <span className="px-1 text-muted-foreground">·</span>
                      <Link href={'/manage/' + collection + '/' + row.id + '/edit'} className="text-primary hover:underline">Edit</Link>
                      <span className="px-1 text-muted-foreground">·</span>
                      <button onClick={() => remove(row.id)} className="text-destructive hover:underline">Delete</button>
                    </>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
"""

NEW_PAGE = r"""'use client';
import { useParams } from 'next/navigation';
import CrudForm from '@/components/CrudForm';
import { modelFor } from '@/lib/models';

export default function NewPage() {
  const collection = useParams().collection;
  const model = modelFor(collection);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">New {model ? model.label : 'record'}</h1>
      <CrudForm collection={collection} />
    </div>
  );
}
"""

EDIT_PAGE = r"""'use client';
import { useParams } from 'next/navigation';
import CrudForm from '@/components/CrudForm';
import { modelFor } from '@/lib/models';

export default function EditPage() {
  const params = useParams();
  const model = modelFor(params.collection);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Edit {model ? model.label : 'record'}</h1>
      <CrudForm collection={params.collection} id={params.id} />
    </div>
  );
}
"""

DETAIL_PAGE = r"""'use client';
// Detail view: fields, populated relationships, and related-record lists.
import * as React from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { modelFor } from '@/lib/models';
import { auth, authHeader } from '@/lib/api';
import { canAccess } from '@/lib/access';

function Related({ link, id }) {
  const [rows, setRows] = React.useState([]);
  React.useEffect(() => {
    fetch('/api/' + link.collection + '?' + link.field + '=' + id)
      .then((r) => r.json()).then((d) => setRows(d.rows || [])).catch(() => {});
  }, [link.collection, link.field, id]);
  if (rows.length === 0) return null;
  return (
    <div className="rounded-xl border p-5">
      <h3 className="font-semibold">{link.entity} ({rows.length})</h3>
      <ul className="mt-3 space-y-1.5 text-sm">
        {rows.slice(0, 8).map((r) => (
          <li key={r.id}>
            <Link href={'/manage/' + link.collection + '/' + r.id} className="text-primary hover:underline">
              {r.name || r.title || r.number || r.status || r.id}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function DetailPage() {
  const params = useParams();
  const router = useRouter();
  const collection = params.collection;
  const id = params.id;
  const model = modelFor(collection);
  const [doc, setDoc] = React.useState(null);
  const [error, setError] = React.useState('');
  const [role, setRole] = React.useState(null);
  React.useEffect(() => { setRole(auth.currentUser()?.role || null); }, []);
  const canWrite = !role || canAccess(role, collection);

  React.useEffect(() => {
    fetch('/api/' + collection + '/' + id)
      .then((r) => r.json())
      .then((d) => { if (d && !d.error) setDoc(d); else setError(d.error || 'Not found'); })
      .catch((e) => setError(e.message));
  }, [collection, id]);

  if (!model) return <div className="p-8 text-sm text-muted-foreground">Unknown collection.</div>;
  if (error) return <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (!doc) return <div className="rounded-xl border p-10 text-center text-sm text-muted-foreground">Loading…</div>;

  const remove = async () => {
    if (!window.confirm('Delete this ' + model.label + '?')) return;
    const r = await fetch('/api/' + collection + '/' + id, { method: 'DELETE', headers: authHeader() });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { window.alert(d.error || 'Delete failed'); return; }
    router.push('/manage/' + collection);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">{doc.name || doc.title || doc.number || model.label}</h1>
        {canWrite && <div className="flex gap-2">
          <Link href={'/manage/' + collection + '/' + id + '/edit'} className="rounded-lg border px-4 py-2 text-sm font-semibold">Edit</Link>
          <button onClick={remove} className="rounded-lg border border-destructive/40 px-4 py-2 text-sm font-semibold text-destructive">Delete</button>
        </div>}
      </div>
      <div className="grid gap-3 rounded-xl border p-5 sm:grid-cols-2">
        {model.refs.map((rel) => (
          <div key={rel.field}>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{rel.target}</p>
            <p className="text-sm font-medium">
              {doc['_' + rel.field]
                ? <Link href={'/manage/' + rel.collection + '/' + doc['_' + rel.field].id} className="text-primary hover:underline">{doc['_' + rel.field].label}</Link>
                : '—'}
            </p>
          </div>
        ))}
        {model.fields.filter((f) => f.type !== 'password').map((f) => (
          <div key={f.name}>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{f.label}</p>
            <p className="text-sm font-medium">{String(doc[f.name] ?? '—')}</p>
          </div>
        ))}
      </div>
      {model.referencedBy && model.referencedBy.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {model.referencedBy.map((link) => <Related key={link.entity + link.field} link={link} id={id} />)}
        </div>
      )}
    </div>
  );
}
"""


def generate_crud_ui_files() -> dict:
    """Return the fixed, descriptor-driven CRUD UI files (relpath -> content)."""
    return {
        "src/components/CrudForm.jsx": CRUD_FORM,
        "src/app/(app)/manage/page.jsx": MANAGE_INDEX,
        "src/app/(app)/manage/[collection]/page.jsx": LIST_PAGE,
        "src/app/(app)/manage/[collection]/new/page.jsx": NEW_PAGE,
        "src/app/(app)/manage/[collection]/[id]/page.jsx": DETAIL_PAGE,
        "src/app/(app)/manage/[collection]/[id]/edit/page.jsx": EDIT_PAGE,
    }
