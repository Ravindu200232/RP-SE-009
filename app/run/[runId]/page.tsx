"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  CheckCircle2, XCircle, Clock, Loader2, Terminal,
  Activity, AlertTriangle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Header } from "@/components/layout/Header";
import type { RunRecord, Phase, ProgressEvent } from "@/types";

const PHASE_ORDER = [
  "intake", "inventory", "srs_parse", "traceability",
  "unit_gen", "unit_exec", "integration_gen", "integration_exec",
  "quality", "security", "performance", "report_gen", "pdf_gen",
];

export default function ProgressPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const logsRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<EventSource | null>(null);

  // Fetch initial run state
  useEffect(() => {
    const fetchRun = async () => {
      try {
        const res = await fetch(`/api/run/${runId}`);
        const data = await res.json();
        if (data.run) setRun(data.run);
        if (data.run?.status === "completed" || data.run?.status === "failed") {
          setDone(true);
        }
      } catch {}
    };
    fetchRun();
  }, [runId]);

  // SSE connection
  useEffect(() => {
    const es = new EventSource(`/api/progress/${runId}`);
    sseRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as ProgressEvent;
        const time = new Date(event.timestamp).toLocaleTimeString();

        if (event.message) {
          setLogs((prev) => [...prev.slice(-500), `[${time}] [${event.phase || event.type}] ${event.message}`]);
        }

        if (event.type === "complete" || event.type === "error") {
          setDone(true);
          es.close();
          // Refetch final run state
          setTimeout(() => {
            fetch(`/api/run/${runId}`)
              .then((r) => r.json())
              .then((d) => { if (d.run) setRun(d.run); });
          }, 500);
        }

        // Update phases on events
        if (event.type === "phase_start" || event.type === "phase_progress" || event.type === "phase_complete" || event.type === "phase_error") {
          fetch(`/api/run/${runId}`)
            .then((r) => r.json())
            .then((d) => { if (d.run) setRun(d.run); })
            .catch(() => {});
        }
      } catch {}
    };

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
    };
  }, [runId]);

  // Auto-scroll logs
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  // Poll run state while running
  useEffect(() => {
    if (done) return;
    const interval = setInterval(() => {
      fetch(`/api/run/${runId}`)
        .then((r) => r.json())
        .then((d) => { if (d.run) setRun(d.run); })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [runId, done]);

  const phases: Phase[] = run?.phases || PHASE_ORDER.map((id) => ({
    id, name: id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    status: "pending" as const, progress: 0,
  }));

  const completedPhases = phases.filter((p) => p.status === "completed").length;
  const totalPhases = phases.length;
  const overallProgress = Math.round((completedPhases / totalPhases) * 100);

  const PhaseIcon = ({ status }: { status: Phase["status"] }) => {
    if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-green-400" />;
    if (status === "failed") return <XCircle className="h-4 w-4 text-red-400" />;
    if (status === "running") return <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />;
    if (status === "skipped") return <Clock className="h-4 w-4 text-gray-600" />;
    return <div className="h-4 w-4 rounded-full border border-gray-700" />;
  };

  return (
    <div className="min-h-screen bg-gray-950">
      <Header runId={runId} />
      <div className="fixed inset-0 bg-grid opacity-20 pointer-events-none" />

      <main className="relative max-w-7xl mx-auto px-4 py-6">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Activity className="h-5 w-5 text-blue-400" />
              Live Progress
            </h1>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">{runId}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`h-2 w-2 rounded-full ${connected ? "bg-green-500 animate-pulse" : "bg-gray-600"}`} />
            <span className="text-xs text-gray-400">{connected ? "Live" : "Disconnected"}</span>
            {done && (
              <Badge variant={run?.status === "completed" ? "completed" : "failed"}>
                {run?.status}
              </Badge>
            )}
          </div>
        </div>

        {/* Overall Progress */}
        <Card className="border-gray-800 mb-6">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-300 font-medium">Overall Progress</span>
              <span className="text-sm font-bold text-white">{overallProgress}%</span>
            </div>
            <Progress value={overallProgress} variant="gradient" className="h-3" />
            <div className="flex justify-between mt-2 text-xs text-gray-500">
              <span>{completedPhases} of {totalPhases} phases complete</span>
              <span>{run?.status || "pending"}</span>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* Phases List */}
          <div className="lg:col-span-2">
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Pipeline Phases</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-gray-800/50">
                  {phases.map((phase) => (
                    <div key={phase.id} className="flex items-start gap-3 p-3 hover:bg-gray-900/40 transition-colors">
                      <PhaseIcon status={phase.status} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-200">{phase.name}</p>
                        {phase.detail && (
                          <p className="text-xs text-gray-500 truncate mt-0.5">{phase.detail}</p>
                        )}
                        {phase.status === "running" && (
                          <Progress value={phase.progress} className="mt-1 h-1" variant="gradient" />
                        )}
                        {phase.error && (
                          <p className="text-xs text-red-400 mt-0.5 truncate">{phase.error}</p>
                        )}
                      </div>
                      <Badge
                        variant={phase.status}
                        className="text-xs flex-shrink-0"
                      >
                        {phase.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right column */}
          <div className="lg:col-span-3 space-y-5">
            {/* Live Metrics */}
            {run && (
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Files", value: run.metrics.totalFiles },
                  { label: "Requirements", value: run.metrics.totalRequirements },
                  { label: "Unit Tests", value: run.metrics.unitTestsGenerated },
                  { label: "Passed", value: run.metrics.unitTestsPassed, color: "text-green-400" },
                  { label: "Failed", value: run.metrics.unitTestsFailed, color: "text-red-400" },
                  { label: "Security", value: run.metrics.securityIssues, color: run.metrics.securityIssues > 0 ? "text-orange-400" : "text-green-400" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className={`text-xl font-bold mt-0.5 ${color || "text-white"}`}>{value}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Live Logs */}
            <Card className="border-gray-800">
              <CardHeader className="pb-2 flex-row items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-green-400" />
                  Live Logs
                </CardTitle>
                <span className="text-xs text-gray-500">{logs.length} lines</span>
              </CardHeader>
              <CardContent className="p-0">
                <div
                  ref={logsRef}
                  className="h-72 overflow-y-auto p-3 font-mono text-xs text-green-300 bg-gray-950 rounded-b-xl space-y-0.5 log-output scrollbar-hide"
                >
                  {logs.length === 0 ? (
                    <p className="text-gray-600">Waiting for analysis to start...</p>
                  ) : (
                    logs.map((log, i) => (
                      <div key={i} className={`${log.includes("ERROR") || log.includes("failed") ? "text-red-400" : log.includes("Warning") ? "text-yellow-400" : "text-green-300"}`}>
                        {log}
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Action buttons when done */}
            {done && run?.status === "completed" && (
              <div className="flex gap-3">
                <button
                  onClick={() => router.push(`/results/${runId}`)}
                  className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  View Results →
                </button>
                <button
                  onClick={() => router.push(`/findings/${runId}`)}
                  className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Explore Findings →
                </button>
              </div>
            )}

            {done && run?.status === "failed" && (
              <div className="p-3 bg-red-900/20 border border-red-800/50 rounded-lg flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0" />
                <p className="text-sm text-red-300">Analysis failed. Check logs above for details.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
