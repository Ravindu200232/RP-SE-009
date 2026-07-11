"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Download, Loader2, Sparkles } from "lucide-react";
import type { Project, SrsEnvelope, SrsSummary } from "@agentforge/shared";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useAgentStream } from "@/lib/use-agent-stream";
import { cn } from "@/lib/utils";
import { AnalyzerSidebar } from "./sidebar";
import { Inspector } from "./inspector";
import { ConsoleBar } from "./console-bar";
import {
  TAB_DEFS,
  type TabKey,
  SrsDocumentTab,
  FunctionalReqTab,
  JsonOutputTab,
  DiagramsTab,
  AmbiguitiesTab,
  RiskPriorityTab,
} from "./tabs";

export function AnalyzerClient({ id, initialTab }: { id: string; initialTab: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [srs, setSrs] = useState<SrsEnvelope | null>(null);
  const [summary, setSummary] = useState<SrsSummary | undefined>();
  const [tab, setTab] = useState<TabKey>((TAB_DEFS.find((t) => t.key === initialTab)?.key as TabKey) || "srs");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { events } = useAgentStream(id);

  const reload = useCallback(async () => {
    const d = await api.getProject(id);
    setProject(d.project);
    setSrs(d.srs || null);
    setSummary(d.summary);
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  function selectTab(t: TabKey) {
    setTab(t);
    window.history.replaceState(null, "", `?tab=${t}`);
  }

  async function customize(prompt: string) {
    setBusy(true);
    setToast(null);
    try {
      const res = await api.customize(id, prompt);
      await reload();
      setToast(`v${res.version}: ${res.diff_summary.join(" · ")}`);
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    setBusy(true);
    try {
      await api.approve(id);
      await reload();
      setToast("Project approved.");
    } finally {
      setBusy(false);
    }
  }

  const downloadPdf = () => window.open(api.downloadPdfUrl(id), "_blank");
  const downloadJson = () => window.open(api.downloadJsonUrl(id), "_blank");

  if (!project) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading analyzer…
        </div>
      </div>
    );
  }

  const doc = srs?.srs_document;

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header />
      <div className="flex min-h-0 flex-1">
        <AnalyzerSidebar
          project={project}
          busy={busy}
          onCustomize={customize}
          onDownload={downloadJson}
          onApprove={approve}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Top bar */}
          <div className="flex items-center justify-between gap-3 border-b border-border bg-card px-5 py-2.5">
            <div className="min-w-0">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                AgentForge Studio <ChevronRight className="h-3 w-3" /> Agent 1 <ChevronRight className="h-3 w-3" />
                Analyzer
              </div>
              <h1 className="truncate text-lg font-semibold">Agent 1 — Requirement Analyzer</h1>
              <p className="hidden text-xs text-muted-foreground sm:block">
                Convert raw software ideas into an IEEE SRS, diagrams, structured JSON, and requirement
                intelligence.
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => document.getElementById("afs-prompt")?.focus()}>
                <Sparkles className="h-4 w-4" /> Customize
              </Button>
              <Button variant="outline" size="sm" onClick={downloadPdf}>
                <Download className="h-4 w-4" /> Download SRS PDF
              </Button>
              <Button size="sm" onClick={approve} variant={project.status === "approved" ? "success" : "default"}>
                {project.status === "approved" ? "Approved" : "Approve & Open Design Selector"}
              </Button>
            </div>
          </div>

          {/* Tab nav */}
          <div className="flex items-center gap-1 border-b border-border bg-card px-4">
            {TAB_DEFS.map((t) => {
              const count =
                t.key === "ambiguities" ? summary?.open_ambiguities : undefined;
              return (
                <button
                  key={t.key}
                  onClick={() => selectTab(t.key)}
                  className={cn(
                    "relative px-3 py-2.5 text-sm font-medium transition-colors",
                    tab === t.key ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                  {count ? <span className="ml-1 text-xs text-warning">{count}</span> : null}
                  {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-primary" />}
                </button>
              );
            })}
          </div>

          {toast && (
            <div className="flex items-center gap-2 border-b border-border bg-primary/5 px-5 py-1.5 text-xs text-primary">
              <Badge variant="success">updated</Badge> {toast}
            </div>
          )}

          {/* Content */}
          <main className="min-h-0 flex-1 overflow-auto px-5 py-4">
            {!doc ? (
              <p className="text-sm text-muted-foreground">No SRS yet.</p>
            ) : tab === "srs" ? (
              <SrsDocumentTab doc={doc} status={project.status} />
            ) : tab === "requirements" ? (
              <FunctionalReqTab doc={doc} />
            ) : tab === "json" ? (
              <JsonOutputTab srs={srs!} projectId={id} />
            ) : tab === "diagrams" ? (
              <DiagramsTab doc={doc} />
            ) : tab === "ambiguities" ? (
              <AmbiguitiesTab doc={doc} />
            ) : (
              <RiskPriorityTab doc={doc} />
            )}
          </main>
        </div>

        <Inspector project={project} summary={summary} onApprove={approve} onDownloadPdf={downloadPdf} />
      </div>

      <ConsoleBar events={events} />
    </div>
  );
}
