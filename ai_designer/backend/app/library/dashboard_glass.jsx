function Dashboard() {
  const { useState } = React;
  const { Link, useNavigate } = ReactRouterDOM;
  const { Icon } = window;
  const navigate = useNavigate();
  const [notifOpen, setNotifOpen] = useState(false);
  const [tasks, setTasks] = useState([
    { id: 1, t: 'Review the latest records', done: false },
    { id: 2, t: 'Approve pending requests', done: true },
    { id: 3, t: 'Prepare the weekly summary', done: false },
    { id: 4, t: 'Update profile settings', done: false },
  ]);
  const user = window.AppDB ? window.AppDB.getCurrentUser() : null;

  /* EDIT HERE: one entry PER REAL ENTITY - { label, key, route, icon } */
  const entities = [
    { label: '__ENTITY1__', key: '__KEY1__', route: '__ROUTE1__', icon: 'users' },
    { label: '__ENTITY2__', key: '__KEY2__', route: '__ROUTE2__', icon: 'chart' },
  ];
  const chart = [
    { m: 'Jan', v: 52 }, { m: 'Feb', v: 38 }, { m: 'Mar', v: 70 }, { m: 'Apr', v: 46 },
    { m: 'May', v: 84 }, { m: 'Jun', v: 61 }, { m: 'Jul', v: 92 }, { m: 'Aug', v: 57 },
    { m: 'Sep', v: 74 }, { m: 'Oct', v: 43 }, { m: 'Nov', v: 80 }, { m: 'Dec', v: 66 },
  ];
  const timeline = [
    { icon: 'plus', text: 'New record created', time: '09:20' },
    { icon: 'edit', text: 'Details updated', time: '11:05' },
    { icon: 'check', text: 'Task marked complete', time: '13:40' },
    { icon: 'users', text: 'New member joined', time: '16:15' },
  ];
  const count = (k) => { try { return (window.AppDB.getRecords(k) || []).length; } catch (e) { return 0; } };
  const recent = (() => { try { return (window.AppDB.getRecords(entities[0].key) || []).slice(0, 5); } catch (e) { return []; } })();
  const toggleTask = (id) => setTasks(tasks.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      {/* gradient header band */}
      <div className="relative rounded-3xl bg-gradient-to-r from-ACCENT-700 via-ACCENT-600 to-ACCENT-500 p-8 text-white mb-8 overflow-hidden">
        <div className="absolute -top-16 -right-16 w-56 h-56 rounded-full bg-white/10 blur-2xl pointer-events-none"></div>
        <div className="relative flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Welcome back, {String(user?.name || user?.email || 'there')}</h1>
            <p className="text-white/75 text-sm">{new Date().toDateString()} - here's what's happening today.</p>
            <div className="flex gap-3 mt-5 flex-wrap">
              {entities.slice(0, 2).map((e) => (
                <div key={e.key} className="rounded-xl bg-white/15 backdrop-blur px-4 py-2">
                  <p className="text-xs text-white/70">{e.label}</p>
                  <p className="font-display text-xl font-bold">{count(e.key)}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="relative">
            <button onClick={() => setNotifOpen(!notifOpen)} aria-label="Notifications" className="w-11 h-11 rounded-xl bg-white/15 hover:bg-white/25 backdrop-blur flex items-center justify-center transition">
              <Icon name="bell" className="w-5 h-5" />
            </button>
            {notifOpen && (
              <div className="absolute right-0 mt-2 w-72 rounded-2xl bg-white text-slate-800 shadow-2xl z-20 p-2">
                {[['A new record needs review', '10m'], ['Weekly summary is ready', '1h'], ['Backup completed successfully', '3h']].map(([t, ti]) => (
                  <div key={t} className="px-3 py-2.5 rounded-xl hover:bg-slate-50"><p className="text-sm font-medium">{t}</p><p className="text-xs text-slate-400">{ti} ago</p></div>
                ))}
                <Link to="/notifications" onClick={() => setNotifOpen(false)} className="block text-center text-xs font-semibold text-ACCENT-600 py-2">View all</Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* stat tiles */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {entities.map((e) => (
          <Link key={e.key} to={e.route} className="rounded-2xl border border-slate-200/40 bg-white/5 p-5 hover:shadow-lg transition block">
            <div className="flex items-center justify-between">
              <div><p className="text-sm opacity-70 mb-1">{e.label}</p><p className="font-display text-3xl font-bold">{count(e.key)}</p></div>
              <span className="w-11 h-11 rounded-2xl bg-ACCENT-500/15 text-ACCENT-500 flex items-center justify-center"><Icon name={e.icon} className="w-5 h-5" /></span>
            </div>
          </Link>
        ))}
      </div>

      {/* chart + tasks */}
      <div className="grid lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 rounded-2xl border border-slate-200/40 bg-white/5 p-6">
          <h2 className="font-semibold mb-6">Activity overview</h2>
          <div className="flex items-end gap-2 h-40">
            {chart.map((c) => (
              <div key={c.m} className="flex-1 flex flex-col items-center justify-end h-full">
                <div className="w-full rounded-t bg-ACCENT-500/80 hover:bg-ACCENT-400 transition" style={{ height: c.v + '%' }} title={c.m + ': ' + c.v}></div>
                <span className="text-[10px] mt-1 opacity-60">{c.m}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200/40 bg-white/5 p-6">
          <h2 className="font-semibold mb-4">Today's tasks</h2>
          <div className="space-y-2.5">
            {tasks.map((t) => (
              <button key={t.id} onClick={() => toggleTask(t.id)} className="w-full flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-white/5 transition text-left">
                <span className={'w-5 h-5 rounded-md border flex items-center justify-center shrink-0 ' + (t.done ? 'bg-ACCENT-600 border-ACCENT-600 text-white' : 'border-slate-400/50')}>
                  {t.done && <Icon name="check" className="w-3 h-3" />}
                </span>
                <span className={'text-sm min-w-0 truncate ' + (t.done ? 'line-through opacity-50' : '')}>{t.t}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* recent + timeline */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-2xl border border-slate-200/40 bg-white/5 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Recent {entities[0].label}</h2>
            <Link to={entities[0].route} className="text-xs font-semibold text-ACCENT-500 hover:opacity-80">View all</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left opacity-60"><th className="px-3 py-2 font-medium">__COL1__</th><th className="px-3 py-2 font-medium">__COL2__</th><th className="px-3 py-2 font-medium">Status</th></tr></thead>
              <tbody className="divide-y divide-slate-200/20">
                {recent.length === 0 && <tr><td colSpan="3" className="px-3 py-6 text-center opacity-60">No records yet</td></tr>}
                {recent.map((r) => (
                  <tr key={r?.id} className="hover:bg-white/5">
                    <td className="px-3 py-2.5">{String(r?.__FIELD1__ ?? '-')}</td>
                    <td className="px-3 py-2.5 opacity-80">{String(r?.__FIELD2__ ?? '-')}</td>
                    <td className="px-3 py-2.5"><span className="rounded-full bg-ACCENT-500/10 text-ACCENT-500 px-2 py-0.5 text-xs font-semibold">{String(r?.status ?? 'Active')}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200/40 bg-white/5 p-6">
          <h2 className="font-semibold mb-5">Timeline</h2>
          <div className="relative pl-5 space-y-5 before:absolute before:left-[7px] before:top-1 before:bottom-1 before:w-px before:bg-slate-400/30">
            {timeline.map((ev) => (
              <div key={ev.text} className="relative">
                <span className="absolute -left-5 top-1 w-3.5 h-3.5 rounded-full bg-ACCENT-500 border-2 border-white/40"></span>
                <p className="text-sm">{ev.text}</p>
                <p className="text-xs opacity-50">{ev.time}</p>
              </div>
            ))}
          </div>
          <button onClick={() => navigate(entities[0].route + '/new')} className="mt-6 w-full rounded-xl bg-ACCENT-600 hover:bg-ACCENT-500 text-white px-4 py-2.5 text-sm font-semibold transition">Add {entities[0].label}</button>
        </div>
      </div>
    </div>
  );
}
window.Dashboard = Dashboard;
