function __PAGE__() {
  const { useState, useEffect } = React;
  const { useNavigate } = ReactRouterDOM;
  const { Icon } = window;
  const navigate = useNavigate();
  const KEY = '__KEY1__';
  const ROUTE = '__ROUTE1__';
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [sort, setSort] = useState('Newest');
  const [selected, setSelected] = useState([]);
  const [page, setPage] = useState(1);
  const [confirmId, setConfirmId] = useState(null);
  const PER = 8;

  useEffect(() => { setRows(window.AppDB.getRecords(KEY) || []); }, []);
  const refresh = () => setRows(window.AppDB.getRecords(KEY) || []);

  const filtered = rows
    .filter((r) => String(r?.__FIELD1__ ?? '').toLowerCase().includes(q.toLowerCase()) || String(r?.__FIELD2__ ?? '').toLowerCase().includes(q.toLowerCase()))
    .filter((r) => statusFilter === 'All' || String(r?.status ?? '') === statusFilter);
  const sorted = sort === 'Newest' ? [...filtered].reverse() : filtered;
  const pages = Math.max(1, Math.ceil(sorted.length / PER));
  const view = sorted.slice((page - 1) * PER, page * PER);

  const toggleSel = (id) => setSelected(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  const removeOne = (id) => { window.AppDB.deleteRecord(KEY, id); setConfirmId(null); refresh(); };
  const removeSelected = () => { selected.forEach((id) => window.AppDB.deleteRecord(KEY, id)); setSelected([]); refresh(); };
  const go = (id, where) => { localStorage.setItem('__sel_' + KEY, id); navigate(ROUTE + where); };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      {/* header */}
      <div className="flex items-center justify-between flex-wrap gap-4 mb-6">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl md:text-3xl font-bold">__ENTITY1__</h1>
          <span className="rounded-full bg-ACCENT-500/10 text-ACCENT-500 px-2.5 py-0.5 text-xs font-semibold">{rows.length} total</span>
        </div>
        <button onClick={() => navigate(ROUTE + '/new')} className="inline-flex items-center gap-2 rounded-xl bg-ACCENT-600 hover:bg-ACCENT-500 text-white px-5 py-2.5 text-sm font-semibold shadow transition">
          <Icon name="plus" className="w-4 h-4" /> Add __ENTITY1__
        </button>
      </div>

      {/* filter bar */}
      <div className="rounded-2xl border border-slate-200/40 bg-white/5 p-4 mb-6 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Icon name="search" className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 opacity-50" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search..." className="w-full rounded-xl border border-slate-300/40 bg-transparent pl-10 pr-4 py-2.5 text-sm focus:ring-2 focus:ring-ACCENT-500 focus:outline-none" />
        </div>
        <div className="flex gap-1.5">
          {['All', 'Active', 'Pending', 'Inactive'].map((s) => (
            <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }} className={'rounded-full px-3.5 py-1.5 text-xs font-semibold transition ' + (statusFilter === s ? 'bg-ACCENT-600 text-white' : 'border border-slate-300/40 opacity-70 hover:opacity-100')}>{s}</button>
          ))}
        </div>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-xl border border-slate-300/40 bg-transparent px-3 py-2 text-sm focus:outline-none">
          <option>Newest</option><option>Oldest</option>
        </select>
      </div>

      {/* bulk bar */}
      {selected.length > 0 && (
        <div className="rounded-xl bg-ACCENT-500/10 border border-ACCENT-500/30 px-4 py-2.5 mb-4 flex items-center justify-between">
          <p className="text-sm font-medium text-ACCENT-600">{selected.length} selected</p>
          <button onClick={removeSelected} className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white px-3.5 py-1.5 text-xs font-semibold transition"><Icon name="trash" className="w-3.5 h-3.5" /> Delete selected</button>
        </div>
      )}

      {/* table */}
      <div className="rounded-2xl border border-slate-200/40 bg-white/5 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left opacity-60 border-b border-slate-200/30">
                <th className="px-4 py-3 w-10"><input type="checkbox" checked={view.length > 0 && view.every((r) => selected.includes(r?.id))} onChange={(e) => setSelected(e.target.checked ? [...new Set([...selected, ...view.map((r) => r?.id)])] : selected.filter((id) => !view.some((r) => r?.id === id)))} /></th>
                <th className="px-4 py-3 font-medium">__COL1__</th>
                <th className="px-4 py-3 font-medium">__COL2__</th>
                <th className="px-4 py-3 font-medium">__COL3__</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/20">
              {view.length === 0 && (
                <tr><td colSpan="6" className="px-4 py-14 text-center">
                  <Icon name="inbox" className="w-8 h-8 mx-auto opacity-40 mb-2" />
                  <p className="font-medium opacity-70">No __ENTITY1__ found</p>
                  <p className="text-xs opacity-50 mt-1">Try a different search, or add a new record.</p>
                </td></tr>
              )}
              {view.map((r) => (
                <tr key={r?.id} className="hover:bg-white/5 transition">
                  <td className="px-4 py-3"><input type="checkbox" checked={selected.includes(r?.id)} onChange={() => toggleSel(r?.id)} /></td>
                  <td className="px-4 py-3 font-medium">{String(r?.__FIELD1__ ?? '-')}</td>
                  <td className="px-4 py-3 opacity-80">{String(r?.__FIELD2__ ?? '-')}</td>
                  <td className="px-4 py-3 opacity-80">{String(r?.__FIELD3__ ?? '-')}</td>
                  <td className="px-4 py-3"><span className="rounded-full bg-ACCENT-500/10 text-ACCENT-500 px-2 py-0.5 text-xs font-semibold">{String(r?.status ?? 'Active')}</span></td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => go(r?.id, '/detail')} className="rounded-lg border border-slate-300/40 px-2.5 py-1.5 text-xs font-medium hover:opacity-70 transition">View</button>
                      <button onClick={() => go(r?.id, '/edit')} className="rounded-lg border border-slate-300/40 px-2.5 py-1.5 text-xs font-medium hover:opacity-70 transition">Edit</button>
                      <button onClick={() => setConfirmId(r?.id)} className="rounded-lg border border-rose-400/40 text-rose-500 px-2.5 py-1.5 text-xs font-medium hover:bg-rose-500/10 transition">Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200/30 text-sm">
          <p className="opacity-60">Page {page} of {pages} - {sorted.length} records</p>
          <div className="flex gap-2">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="rounded-lg border border-slate-300/40 px-3 py-1.5 text-xs font-medium disabled:opacity-30 hover:opacity-70 transition">Previous</button>
            <button onClick={() => setPage(Math.min(pages, page + 1))} disabled={page === pages} className="rounded-lg border border-slate-300/40 px-3 py-1.5 text-xs font-medium disabled:opacity-30 hover:opacity-70 transition">Next</button>
          </div>
        </div>
      </div>

      {/* delete confirm modal */}
      {confirmId && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setConfirmId(null)}>
          <div className="bg-white text-slate-800 rounded-2xl shadow-2xl max-w-sm w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="w-11 h-11 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4"><Icon name="trash" className="w-5 h-5" /></div>
            <h3 className="font-semibold text-lg mb-1">Delete this record?</h3>
            <p className="text-sm text-slate-500 mb-6">This action cannot be undone.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setConfirmId(null)} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold hover:bg-slate-50 transition">Cancel</button>
              <button onClick={() => removeOne(confirmId)} className="rounded-xl bg-rose-600 hover:bg-rose-500 text-white px-4 py-2.5 text-sm font-semibold transition">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
window.__PAGE__ = __PAGE__;
