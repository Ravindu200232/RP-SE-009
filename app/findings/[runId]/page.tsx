"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bug, Shield, Zap, FileSearch, List, ChevronDown, ChevronUp, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Header } from "@/components/layout/Header";
import type { BugRecord, SecurityFinding, TraceabilityRecord, Severity } from "@/types";

function SeverityBadge({ severity }: { severity: Severity }) {
  const variants: Record<Severity, "critical" | "high" | "medium" | "low" | "info"> = {
    critical: "critical", high: "high", medium: "medium", low: "low", info: "info",
  };
  return <Badge variant={variants[severity] || "info"}>{severity}</Badge>;
}

function BugCard({ bug, index }: { bug: BugRecord; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 p-3 hover:bg-gray-900/60 text-left transition-colors"
      >
        <span className="text-xs text-gray-600 font-mono mt-0.5 w-12 flex-shrink-0">#{index + 1}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">{bug.title}</p>
          <p className="text-xs text-gray-500 truncate mt-0.5">{bug.description}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <SeverityBadge severity={bug.severity} />
          {open ? <ChevronUp className="h-4 w-4 text-gray-500" /> : <ChevronDown className="h-4 w-4 text-gray-500" />}
        </div>
      </button>
      {open && (
        <div className="p-3 bg-gray-950 border-t border-gray-800 space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-gray-500 font-medium mb-1">Bug ID</p>
              <p className="font-mono text-gray-300">{bug.bugId}</p>
            </div>
            <div>
              <p className="text-gray-500 font-medium mb-1">Phase</p>
              <p className="text-gray-300">{bug.phase}</p>
            </div>
            <div>
              <p className="text-gray-500 font-medium mb-1">Category</p>
              <p className="text-gray-300">{bug.category}</p>
            </div>
            <div>
              <p className="text-gray-500 font-medium mb-1">Confidence</p>
              <p className="text-gray-300">{Math.round(bug.confidenceScore * 100)}%</p>
            </div>
          </div>
          {bug.affectedFiles.length > 0 && (
            <div>
              <p className="text-gray-500 font-medium mb-1">Affected Files</p>
              <div className="space-y-0.5">
                {bug.affectedFiles.map((f, i) => <p key={i} className="font-mono text-blue-300 text-xs">{f}</p>)}
              </div>
            </div>
          )}
          <div>
            <p className="text-gray-500 font-medium mb-1">Expected</p>
            <p className="text-gray-300">{bug.expectedBehavior}</p>
          </div>
          <div>
            <p className="text-gray-500 font-medium mb-1">Actual</p>
            <p className="text-red-300">{bug.actualBehavior}</p>
          </div>
          <div>
            <p className="text-gray-500 font-medium mb-1">Suggested Fix</p>
            <p className="text-emerald-300">{bug.suggestedFix}</p>
          </div>
          {bug.evidence && (
            <div>
              <p className="text-gray-500 font-medium mb-1">Evidence</p>
              <p className="font-mono bg-gray-900 p-2 rounded text-gray-400 text-xs break-all">{bug.evidence}</p>
            </div>
          )}
          {bug.llmSummary && (
            <div>
              <p className="text-gray-500 font-medium mb-1">AI Analysis</p>
              <p className="text-gray-300 italic">{bug.llmSummary}</p>
            </div>
          )}
          <p className="text-gray-600">Source: {bug.sourceTool} | {new Date(bug.timestamp).toLocaleString()}</p>
        </div>
      )}
    </div>
  );
}

function SecurityCard({ finding, index }: { finding: SecurityFinding; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 p-3 hover:bg-gray-900/60 text-left transition-colors"
      >
        <span className="text-xs text-gray-600 font-mono mt-0.5 w-12 flex-shrink-0">#{index + 1}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">{finding.rule}</p>
          <p className="text-xs text-gray-500 font-mono truncate mt-0.5">{finding.file}{finding.line ? `:${finding.line}` : ""}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <SeverityBadge severity={finding.severity} />
          {open ? <ChevronUp className="h-4 w-4 text-gray-500" /> : <ChevronDown className="h-4 w-4 text-gray-500" />}
        </div>
      </button>
      {open && (
        <div className="p-3 bg-gray-950 border-t border-gray-800 space-y-2 text-xs">
          <p className="text-gray-300">{finding.message}</p>
          <div className="flex gap-4">
            {finding.cwe && <span className="text-orange-400">CWE: {finding.cwe}</span>}
            {finding.owasp && <span className="text-purple-400">OWASP: {finding.owasp}</span>}
          </div>
          <p className="text-gray-500">Tool: {finding.tool}</p>
        </div>
      )}
    </div>
  );
}

function TraceCard({ record, index }: { record: TraceabilityRecord; index: number }) {
  const [open, setOpen] = useState(false);
  const statusColors: Record<string, string> = {
    implemented: "completed", partially_implemented: "running", missing: "failed", unverifiable: "skipped",
  };
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 p-3 hover:bg-gray-900/60 text-left transition-colors"
      >
        <span className="text-xs text-gray-600 font-mono mt-0.5 w-12 flex-shrink-0">{record.requirementId}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">{record.requirementTitle}</p>
          <p className="text-xs text-gray-500 mt-0.5">Confidence: {Math.round(record.confidence * 100)}%</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge variant={(statusColors[record.status] as "completed" | "running" | "failed" | "skipped") || "pending"}>
            {record.status.replace(/_/g, " ")}
          </Badge>
          {open ? <ChevronUp className="h-4 w-4 text-gray-500" /> : <ChevronDown className="h-4 w-4 text-gray-500" />}
        </div>
      </button>
      {open && (
        <div className="p-3 bg-gray-950 border-t border-gray-800 space-y-2 text-xs">
          {record.files.length > 0 && (
            <div><p className="text-gray-500 mb-1">Mapped Files</p>
              {record.files.map((f, i) => <p key={i} className="font-mono text-blue-300">{f}</p>)}</div>
          )}
          {record.routes.length > 0 && (
            <div><p className="text-gray-500 mb-1">Routes</p>
              {record.routes.map((r, i) => <p key={i} className="font-mono text-purple-300">{r}</p>)}</div>
          )}
          {record.llmReasoning && (
            <div><p className="text-gray-500 mb-1">AI Reasoning</p>
              <p className="text-gray-300 italic">{record.llmReasoning}</p></div>
          )}
        </div>
      )}
    </div>
  );
}

export default function FindingsPage() {
  const { runId } = useParams<{ runId: string }>();
  const [allBugs, setAllBugs] = useState<BugRecord[]>([]);
  const [secFindings, setSecFindings] = useState<SecurityFinding[]>([]);
  const [traceability, setTraceability] = useState<TraceabilityRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const loadJSON = async (file: string) => {
        try {
          const res = await fetch(`/api/run/${runId}/artifacts?file=${file}`);
          if (!res.ok) return null;
          return res.json();
        } catch { return null; }
      };

      const [bugs, sec, trace] = await Promise.all([
        loadJSON("bugs/all_bugs_merged.json"),
        loadJSON("reports/security_findings.json"),
        loadJSON("reports/requirements_traceability.json"),
      ]);

      if (Array.isArray(bugs)) setAllBugs(bugs);
      if (Array.isArray(sec)) setSecFindings(sec);
      if (trace?.records) setTraceability(trace.records);

      setLoading(false);
    };
    load();
  }, [runId]);

  const unitBugs = allBugs.filter((b) => b.phase === "unit_test");
  const intBugs = allBugs.filter((b) => b.phase === "integration_test");
  const srsGaps = allBugs.filter((b) => b.category === "srs_gap");

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <Header runId={runId} />
      <div className="fixed inset-0 bg-grid opacity-20 pointer-events-none" />

      <main className="relative max-w-7xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Bug className="h-5 w-5 text-red-400" />
            Findings Explorer
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            {allBugs.length} total issues | {secFindings.length} security findings | {traceability.length} requirements traced
          </p>
        </div>

        <Tabs defaultValue="all">
          <TabsList className="mb-4 flex-wrap h-auto gap-1">
            <TabsTrigger value="all">All Bugs ({allBugs.length})</TabsTrigger>
            <TabsTrigger value="unit">Unit ({unitBugs.length})</TabsTrigger>
            <TabsTrigger value="integration">Integration ({intBugs.length})</TabsTrigger>
            <TabsTrigger value="security">Security ({secFindings.length})</TabsTrigger>
            <TabsTrigger value="srs">SRS Gaps ({srsGaps.length})</TabsTrigger>
            <TabsTrigger value="trace">Traceability ({traceability.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <div className="space-y-2">
              {allBugs.length === 0 ? (
                <Card className="border-gray-800"><CardContent className="p-8 text-center text-gray-500">No bugs found</CardContent></Card>
              ) : (
                allBugs.map((bug, i) => <BugCard key={bug.bugId} bug={bug} index={i} />)
              )}
            </div>
          </TabsContent>

          <TabsContent value="unit">
            <div className="space-y-2">
              {unitBugs.length === 0
                ? <Card className="border-gray-800"><CardContent className="p-8 text-center text-gray-500">No unit test failures</CardContent></Card>
                : unitBugs.map((bug, i) => <BugCard key={bug.bugId} bug={bug} index={i} />)}
            </div>
          </TabsContent>

          <TabsContent value="integration">
            <div className="space-y-2">
              {intBugs.length === 0
                ? <Card className="border-gray-800"><CardContent className="p-8 text-center text-gray-500">No integration test failures</CardContent></Card>
                : intBugs.map((bug, i) => <BugCard key={bug.bugId} bug={bug} index={i} />)}
            </div>
          </TabsContent>

          <TabsContent value="security">
            <div className="space-y-2">
              {secFindings.length === 0
                ? <Card className="border-gray-800"><CardContent className="p-8 text-center text-gray-500">No security findings</CardContent></Card>
                : secFindings.map((f, i) => <SecurityCard key={f.id} finding={f} index={i} />)}
            </div>
          </TabsContent>

          <TabsContent value="srs">
            <div className="space-y-2">
              {srsGaps.length === 0
                ? <Card className="border-gray-800"><CardContent className="p-8 text-center text-gray-500">All requirements implemented</CardContent></Card>
                : srsGaps.map((bug, i) => <BugCard key={bug.bugId} bug={bug} index={i} />)}
            </div>
          </TabsContent>

          <TabsContent value="trace">
            <div className="space-y-2">
              {traceability.length === 0
                ? <Card className="border-gray-800"><CardContent className="p-8 text-center text-gray-500">No traceability data</CardContent></Card>
                : traceability.map((r, i) => <TraceCard key={r.requirementId} record={r} index={i} />)}
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
