"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { AgentEvent } from "@agentforge/shared";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "live_logs", label: "Live Logs" },
  { key: "agent_events", label: "Agent Events" },
  { key: "terminal", label: "Terminal" },
  { key: "prompt_trace", label: "Prompt Trace" },
  { key: "errors", label: "Errors" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const levelColor: Record<string, string> = {
  info: "text-foreground",
  success: "text-success",
  warn: "text-warning",
  error: "text-danger",
  debug: "text-muted-foreground",
};

export function ConsoleBar({ events }: { events: AgentEvent[] }) {
  const [tab, setTab] = useState<TabKey>("live_logs");
  const [open, setOpen] = useState(true);

  const errorCount = useMemo(() => events.filter((e) => e.channel === "errors").length, [events]);

  const rows = useMemo(() => {
    if (tab === "terminal") return events;
    return events.filter((e) => e.channel === tab);
  }, [events, tab]);

  return (
    <div className="border-t border-border bg-card">
      <div className="flex items-center gap-1 px-3">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => {
              setTab(t.key);
              setOpen(true);
            }}
            className={cn(
              "relative px-3 py-2 text-xs font-medium transition-colors",
              tab === t.key ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
            {t.key === "errors" && errorCount > 0 && (
              <span className="ml-1 rounded-full bg-danger/10 px-1.5 text-[10px] text-danger">{errorCount}</span>
            )}
            {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-primary" />}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setOpen((o) => !o)} className="p-1 text-muted-foreground hover:text-foreground">
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        </div>
      </div>
      {open && (
        <div className="h-40 overflow-auto border-t border-border bg-[#0f172a] px-3 py-2 font-mono text-[11px] leading-relaxed text-slate-200">
          {rows.length === 0 ? (
            <div className="text-slate-500">No {TABS.find((t) => t.key === tab)?.label.toLowerCase()} yet.</div>
          ) : (
            rows.map((e) => (
              <div key={e.id} className="flex gap-2">
                <span className="shrink-0 text-slate-500">{new Date(e.created_at).toLocaleTimeString()}</span>
                <span className="shrink-0 text-primary">{e.agent}</span>
                <span className={cn("min-w-0 break-words", levelColor[e.level] || "text-slate-200")}>{e.message}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
