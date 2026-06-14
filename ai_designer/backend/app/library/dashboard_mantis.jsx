function Dashboard() {
  const { useState } = React;
  const { Link, useNavigate } = ReactRouterDOM;
  const { Icon } = window;
  const navigate = useNavigate();
  const [notifOpen, setNotifOpen] = useState(false);
  const user = window.AppDB ? window.AppDB.getCurrentUser() : null;

  /* EDIT HERE: one entry PER REAL ENTITY - { label, key (storage key), route (list route), icon } */
  const entities = [
    { label: '__ENTITY1__', key: '__KEY1__', route: '__ROUTE1__', icon: 'users' },
    { label: '__ENTITY2__', key: '__KEY2__', route: '__ROUTE2__', icon: 'chart' },
  ];
  const trends = ['+12.4%', '+8.1%', '-2.3%', '+5.6%', '+9.9%'];
  const chart = [
    { m: 'Jan', v: 45 }, { m: 'Feb', v: 62 }, { m: 'Mar', v: 38 }, { m: 'Apr', v: 71 },
    { m: 'May', v: 55 }, { m: 'Jun', v: 83 }, { m: 'Jul', v: 64 }, { m: 'Aug', v: 90 },
    { m: 'Sep', v: 58 }, { m: 'Oct', v: 76 }, { m: 'Nov', v: 49 }, { m: 'Dec', v: 88 },
  ];
  const week = [{ d: 'Mon', v: 55 }, { d: 'Tue', v: 80 }, { d: 'Wed', v: 38 }, { d: 'Thu', v: 92 }, { d: 'Fri', v: 66 }];
  const activity = [
    { icon: 'plus', text: 'New record was added', time: '2h ago' },
    { icon: 'edit', text: 'A record was updated', time: '5h ago' },
    { icon: 'check', text: 'Weekly report completed', time: '1d ago' },
    { icon: 'users', text: 'A new user registered', time: '2d ago' },
  ];
  const notifications = [
    { t: 'A new record needs review', time: '10m ago' },
    { t: 'Weekly summary is ready', time: '1h ago' },
    { t: 'Backup completed successfully', time: '3h ago' },
  ];
  const count = (k) => { try { return (window.AppDB.getRecords(k) || []).length; } catch (e) { return 0; } };
  const recent = (() => { try { return (window.AppDB.getRecords(entities[0].key) || []).slice(0, 5); } catch (e) { return []; } })();

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      {/* header */}
      <div className="flex items-start justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="font-display text-2xl md:text-3xl font-bold">Dashboard</h1>
          <p className="text-sm opacity-70 mt-1">Welcome back, {String(user?.name || user?.email || 'there')} - {new Date().toDateString()}</p>
        </div>
        <div className="relative">
          <button onClick={() => setNotifOpen(!notifOpen)} className="relative inline-flex items-center gap-2 rounded-xl border border-slate-200/40 px-4 py-2.5 text-sm font-medium hover:opacity-80 transition">
            <Icon name="bell" className="w-4 h-4" /> Notifications
            <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-ACCENT-600 text-white text-[10px] font-bold flex items-center justify-center">{notifications.length}</span>
          </button>
          {notifOpen && (
            <div className="absolute right-0 mt-2 w-72 rounded-2xl border border-slate-200/40 bg-white text-slate-800 shadow-2xl z-20 p-2">
              {notifications.map((n) => (
                <div key={n.t} className="px-3 py-2.5 rounded-xl hover:bg-slate-50">
                  <p className="text-sm font-medium">{n.t}</p><p className="text-xs text-slate-400">{n.time}</p>
                </div>
              ))}
              <Link to="/notifications" onClick={() => setNotifOpen(false)} className="block text-center text-xs font-semibold text-ACCENT-600 py-2">View all</Link>
            </div>
          )}
        </div>
      </div>

      {/* stat cards - one per entity */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {entities.map((e, i) => (
          <Link key={e.key} to={e.route} className="rounded-2xl border border-slate-200/40 bg-white/5 p-5 hover:shadow-lg hover:-translate-y-0.5 transition block">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm opacity-70">{e.label}</span>
              <span className="w-9 h-9 rounded-xl bg-ACCENT-500/15 text-ACCENT-500 flex items-center justify-center"><Icon name={e.icon} className="w-4 h-4" /></span>
            </div>
            <p className="font-display text-3xl font-bold">{count(e.key)}</p>
            <div className="flex items-center flex-wrap gap-1.5 text-xs mt-2">
              <span className={'rounded-full px-2 py-0.5 font-semibold ' + (trends[i % 5].startsWith('-') ? 'bg-rose-500/10 text-rose-500' : 'bg-ACCENT-500/10 text-ACCENT-500')}>{trends[i % 5]}</span>
              <span className="opacity-60">vs last month</span>
            </div>
          </Link>
        ))}
      </div>

      {/* overview chart + this week */}
      <div className="grid lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 rounded-2xl border border-slate-200/40 bg-white/5 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-semibold">Overview</h2>
            <span className="text-xs opacity-60">Last 12 months</span>
          </div>
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
          <h2 className="font-semibold mb-1">This week</h2>
          <p className="font-display text-3xl font-bold">{Math.max(1, count(entities[0].key))}<span className="text-sm font-normal opacity-60"> new</span></p>
          <p className="text-xs mt-1 mb-6"><span className="rounded-full px-2 py-0.5 font-semibold bg-ACCENT-500/10 text-ACCENT-500">+3.2%</span></p>
          <div className="flex items-end gap-2 h-16">
            {week.map((w) => (
              <div key={w.d} className="flex-1 flex flex-col items-center justify-end h-full">
                <div className="w-full rounded-t bg-ACCENT-500/60" style={{ height: w.v + '%' }} title={w.d}></div>
                <span className="text-[10px] mt-1 opacity-60">{w.d}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* recent table + quick actions */}
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
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200/40 bg-white/5 p-6">
            <h2 className="font-semibold mb-4">Quick actions</h2>
            <div className="space-y-2.5">
              {entities.slice(0, 3).map((e) => (
                <button key={e.key} onClick={() => navigate(e.route + '/new')} className="w-full flex items-center gap-2.5 rounded-xl bg-ACCENT-600 hover:bg-ACCENT-500 text-white px-4 py-2.5 text-sm font-semibold transition">
                  <Icon name="plus" className="w-4 h-4" /> Add {e.label}
                </button>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200/40 bg-white/5 p-6">
            <h2 className="font-semibold mb-4">Activity</h2>
            <div className="space-y-4">
              {activity.map((a) => (
                <div key={a.text} className="flex items-start gap-3">
                  <span className="w-8 h-8 rounded-full bg-ACCENT-500/15 text-ACCENT-500 flex items-center justify-center shrink-0"><Icon name={a.icon} className="w-3.5 h-3.5" /></span>
                  <div className="min-w-0"><p className="text-sm truncate">{a.text}</p><p className="text-xs opacity-50">{a.time}</p></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
window.Dashboard = Dashboard;
