"use client";

import { useState } from "react";
import { ArrowRight, CornerDownLeft, Download, Loader2, Check } from "lucide-react";
import type { Project } from "@agentforge/shared";
import { Button } from "@/components/ui/button";

const SUGGESTED_EDITS = [
  "Make the performance target stricter",
  "Add a multi-currency requirement",
  "Rename booking-service to reservation-service",
  "Add a loyalty programme to system features",
];

export function AnalyzerSidebar({
  project,
  busy,
  onCustomize,
  onDownload,
  onApprove,
}: {
  project: Project;
  busy: boolean;
  onCustomize: (prompt: string) => void;
  onDownload: () => void;
  onApprove: () => void;
}) {
  const [prompt, setPrompt] = useState("");

  function submit() {
    if (!prompt.trim() || busy) return;
    onCustomize(prompt.trim());
    setPrompt("");
  }

  return (
    <aside className="hidden w-72 shrink-0 flex-col border-r border-border bg-card md:flex">
      <div className="border-b border-border px-4 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">SRS Document</div>
        <div className="mt-1 text-sm font-semibold leading-snug">{project.title}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          v{project.current_version} · IEEE 830 format
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Customize via Prompt
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Tell Agent 1 what to change in plain English — requirements, constraints, or diagrams. Examples:
        </p>
        <div className="mt-3 space-y-1.5">
          {SUGGESTED_EDITS.map((s) => (
            <button
              key={s}
              disabled={busy}
              onClick={() => onCustomize(s)}
              className="flex w-full items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-2 text-left text-xs transition-colors hover:border-primary hover:bg-primary/5 disabled:opacity-50"
            >
              <ArrowRight className="h-3 w-3 shrink-0 text-primary" />
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-border p-3">
        <div className="relative">
          <input
            id="afs-prompt"
            value={prompt}
            disabled={busy}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="Ask to edit the SRS or diagrams…"
            className="h-9 w-full rounded-lg border border-border bg-background pl-3 pr-9 text-xs focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
          <button
            onClick={submit}
            disabled={busy || !prompt.trim()}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-primary disabled:opacity-40"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CornerDownLeft className="h-4 w-4" />}
          </button>
        </div>
        <div className="mt-2 flex gap-2">
          <Button variant="outline" size="sm" className="flex-1" onClick={onDownload}>
            <Download className="h-4 w-4" /> Download
          </Button>
          <Button
            size="sm"
            className="flex-1"
            variant={project.status === "approved" ? "success" : "default"}
            onClick={onApprove}
          >
            {project.status === "approved" ? <Check className="h-4 w-4" /> : null} Approve
          </Button>
        </div>
      </div>
    </aside>
  );
}
