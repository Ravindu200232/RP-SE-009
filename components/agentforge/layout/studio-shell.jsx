// Shell.jsx ? App Shell: Sidebar + Header (light theme, renamed nav)
import React, { useCallback, useEffect, useState } from "react";
import { AF_DATA } from "../core/data";
import { Icon, ToastContainer } from "../core/ui";
import { clearActiveSession, loadActiveSession } from "../core/auth-storage";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "LayoutDashboard" },
  { id: "new-project", label: "New Project", icon: "Plus" },
  { divider: true },
  { id: "agent1", label: "Analyser", icon: "Brain", color: "blue" },
  { id: "design-selector", label: "Design Selector", icon: "Palette", color: "violet" },
  { id: "agent2", label: "Builder Studio", icon: "Code2", color: "violet" },
  { id: "agent3", label: "QA Center", icon: "FlaskConical", color: "amber" },
  { id: "agent4", label: "DevOps Center", icon: "Rocket", color: "green" },
  { divider: true },
  { id: "artifacts", label: "Artifacts & Exports", icon: "Archive" },
  { id: "versions", label: "Versions & Releases", icon: "GitBranch" },
  { id: "memory", label: "Memory & Logs", icon: "Database" },
  { divider: true },
  { id: "project-history", label: "Project History", icon: "FolderOpen" },
  { id: "settings", label: "Settings", icon: "Settings" },
];

const colorMap = {
  blue:   { dot: "bg-blue-500",   text: "text-blue-600",  active: "bg-blue-50 text-blue-700" },
  violet: { dot: "bg-violet-500", text: "text-violet-600",active: "bg-violet-50 text-violet-700" },
  amber:  { dot: "bg-amber-500",  text: "text-amber-600", active: "bg-amber-50 text-amber-700" },
  green:  { dot: "bg-green-500",  text: "text-green-600", active: "bg-green-50 text-green-700" },
};

const LOG_TABS = ["Live Logs", "Agent Events", "Terminal", "Prompt Trace", "Errors"];

function Shell({ currentPage, onNavigate, toasts, children }) {
  const [logOpen, setLogOpen] = useState(false);
  const [logTab, setLogTab] = useState("Live Logs");
  const [logLines, setLogLines] = useState([...AF_DATA.logLines]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sessionUser, setSessionUser] = useState({
    email: "Not signed in",
    label: "Guest Session",
  });

  useEffect(() => {
    if (!logOpen) return;
    const extra = [
      "[12:01:24] [Agent3] Coverage: 78% line coverage across 6 services",
      "[12:01:26] [System] Forwarding BUG-013, BUG-014 to Agent 2",
      "[12:01:28] [Agent2] Received bug reports — patching...",
    ];
    let i = 0;
    const iv = setInterval(() => {
      if (i < extra.length) setLogLines(prev => [...prev, extra[i++]]);
      else clearInterval(iv);
    }, 2000);
    return () => clearInterval(iv);
  }, [logOpen]);

  useEffect(() => {
    const session = loadActiveSession();
    if (!session?.email) {
      return;
    }

    setSessionUser({
      email: session.email,
      label: session.email.split("@")[0],
    });
  }, []);

  const handleLogout = useCallback(() => {
    clearActiveSession();
    window.location.assign("/login");
  }, []);

  const logLineColor = (line) => {
    if (line.includes("✗") || line.includes("Error")) return "text-red-600";
    if (line.includes("✓") || line.includes("passed")) return "text-green-600";
    if (line.includes("[Agent1]")) return "text-blue-600";
    if (line.includes("[Agent2]")) return "text-violet-600";
    if (line.includes("[Agent3]")) return "text-amber-600";
    if (line.includes("[Agent4]")) return "text-green-600";
    return "text-gray-500";
  };

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className={`flex flex-col bg-white border-r border-gray-200 flex-shrink-0 transition-all duration-200 ${sidebarCollapsed ? "w-14" : "w-56"}`}>
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-3 py-3.5 border-b border-gray-100">
          <img src="/logo.png" alt="AgentForge Studio logo" className="h-7 w-auto flex-shrink-0 object-contain" />
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <p className="text-xs font-bold text-gray-900 leading-none">AgentForge Studio</p>
              <p className="text-[10px] text-gray-400 leading-none mt-0.5">AI Agent Workspace</p>
            </div>
          )}
          <button onClick={() => setSidebarCollapsed(p => !p)} className="ml-auto text-gray-300 hover:text-gray-500 transition-colors">
            <Icon name={sidebarCollapsed ? "ChevronRight" : "ChevronLeft"} size={12} />
          </button>
        </div>

        {/* Workspace */}
        {!sidebarCollapsed && (
          <div className="px-3 py-2 border-b border-gray-100">
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Workspace</p>
            <p className="text-xs text-gray-500 truncate">{sessionUser.label}</p>
            <p className="text-xs text-blue-600 truncate mt-0.5 font-medium">{sessionUser.email}</p>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {NAV_ITEMS.map((item, idx) => {
            if (item.divider) return <div key={idx} className="my-1.5 border-t border-gray-100" />;
            const c = item.color ? colorMap[item.color] : null;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                title={sidebarCollapsed ? item.label : undefined}
                className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-all duration-100 mb-0.5 ${
                  isActive
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                <Icon name={item.icon} size={14} className={isActive ? "text-blue-600" : (c ? c.text : "text-gray-400")} />
                {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        {!sidebarCollapsed && (
          <div className="px-2 py-2 border-t border-gray-100">
            <button className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors mb-0.5">
              <Icon name="HelpCircle" size={14} />
              Help Center
            </button>
            <button className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs text-gray-500 hover:bg-gray-100 transition-colors">
              <div className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex-shrink-0" />
              <span className="truncate">{sessionUser.email}</span>
            </button>
            <button
              onClick={handleLogout}
              className="mt-1 w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs text-gray-500 hover:bg-gray-100 transition-colors"
            >
              <Icon name="ArrowLeft" size={14} />
              Sign Out
            </button>
          </div>
        )}
      </aside>

      {/* Main content column */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top Header */}
        <header className="flex items-center gap-3 px-4 h-12 border-b border-gray-200 bg-white flex-shrink-0">
          {/* Search */}
          <div className="flex-1 max-w-lg">
            <div className="relative">
              <Icon name="Search" size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search projects, requirements, services, artifacts…"
                className="w-full bg-gray-50 border border-gray-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-600 placeholder-gray-400 focus:outline-none focus:border-blue-400 transition-colors"
              />
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-gray-400 font-mono bg-gray-100 px-1 rounded">⌘K</span>
            </div>
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button className="w-7 h-7 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center hover:bg-gray-200 transition-colors relative">
              <Icon name="Bell" size={13} className="text-gray-500" />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-red-500" />
            </button>
            <button className="w-7 h-7 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center hover:bg-gray-200 transition-colors">
              <Icon name="Download" size={13} className="text-gray-500" />
            </button>
            <button
              onClick={() => onNavigate("new-project")}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition-colors"
            >
              <Icon name="Plus" size={12} />
              New Project
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-hidden bg-gray-50" style={{ marginBottom: logOpen ? 220 : 32 }}>
          {children}
        </main>

        {/* Log Drawer */}
        <div
          className="fixed bottom-0 bg-white border-t border-gray-200 z-40 transition-all duration-200"
          style={{ left: sidebarCollapsed ? 56 : 224, right: 0, height: logOpen ? 220 : 32 }}
        >
          <div className="flex items-center justify-between px-3 h-8 border-b border-gray-100">
            <div className="flex items-center gap-1">
              {LOG_TABS.map(t => (
                <button key={t} onClick={() => { setLogTab(t); if (!logOpen) setLogOpen(true); }}
                  className={`px-2.5 py-0.5 rounded text-[10px] font-medium transition-colors ${logTab === t && logOpen ? "bg-gray-100 text-gray-900" : "text-gray-400 hover:text-gray-600"}`}>
                  {t}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1">
              <button className="text-[10px] text-gray-400 hover:text-gray-600 px-2 transition-colors">Clear</button>
              <button onClick={() => setLogOpen(p => !p)} className="w-5 h-5 flex items-center justify-center rounded hover:bg-gray-100 transition-colors">
                <Icon name={logOpen ? "ChevronDown" : "ChevronUp"} size={11} className="text-gray-400" />
              </button>
            </div>
          </div>
          {logOpen && (
            <div className="h-full overflow-y-auto p-2 font-mono bg-white" style={{ height: "calc(100% - 32px)" }}>
              {logLines.map((line, i) => (
                <p key={i} className={`text-[10px] leading-5 ${logLineColor(line)}`}>{line}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      <ToastContainer toasts={toasts} />
    </div>
  );
}

export default Shell;
