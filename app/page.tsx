"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  ShieldCheck, FolderOpen, FileJson, Play, Clock, CheckCircle2,
  XCircle, ChevronRight, Settings, Zap, Cpu, Globe, ToggleLeft, ToggleRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Header } from "@/components/layout/Header";
import type { RunRecord } from "@/types";

const DEFAULT_PROJECT_PATH = "E:\\final_research_agentic\\output\\stayease-hotel-booking-system";
const DEFAULT_SRS_PATH = "";
const DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b";

export default function SetupPage() {
  const router = useRouter();
  const [projectPath, setProjectPath] = useState(DEFAULT_PROJECT_PATH);
  const [srsPath, setSrsPath] = useState(DEFAULT_SRS_PATH);
  const [runName, setRunName] = useState("");
  const [enableSecurity, setEnableSecurity] = useState(false);
  const [enablePerformance, setEnablePerformance] = useState(false);
  const [enablePlaywright, setEnablePlaywright] = useState(false);
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState("http://localhost:11434");
  const [ollamaModel, setOllamaModel] = useState(DEFAULT_OLLAMA_MODEL);
  const [glmApiKey, setGlmApiKey] = useState("");
  const [glmModel, setGlmModel] = useState("glm-4-flash");
  const [recentRuns, setRecentRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json())
      .then((d) => setRecentRuns(d.runs || []))
      .catch(() => {});
  }, []);

  const handleStart = async () => {
    if (!projectPath.trim()) { setError("Project path is required"); return; }
    if (!srsPath.trim()) { setError("SRS file path is required"); return; }
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          projectPath: projectPath.trim(),
          srsPath: srsPath.trim(),
          runName: runName.trim() || undefined,
          enableSecurity,
          enablePerformance,
          enablePlaywright,
          ollamaBaseUrl,
          ollamaModel,
          glmApiKey: glmApiKey || undefined,
          glmModel,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to start analysis");
      router.push(`/run/${data.runId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  };

  const StatusIcon = ({ status }: { status: string }) => {
    if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-green-400" />;
    if (status === "failed") return <XCircle className="h-4 w-4 text-red-400" />;
    if (status === "running") return <div className="h-4 w-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />;
    return <Clock className="h-4 w-4 text-gray-500" />;
  };

  return (
    <div className="min-h-screen bg-gray-950">
      <Header />

      {/* Background */}
      <div className="fixed inset-0 bg-grid opacity-30 pointer-events-none" />
      <div className="fixed inset-0 bg-gradient-to-br from-blue-950/20 via-transparent to-purple-950/20 pointer-events-none" />

      <main className="relative max-w-6xl mx-auto px-4 py-10">
        {/* Hero */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-1.5 mb-6">
            <ShieldCheck className="h-4 w-4 text-blue-400" />
            <span className="text-blue-400 text-sm font-medium">QA + Review Platform</span>
          </div>
          <h1 className="text-4xl font-bold mb-3">
            <span className="gradient-text">Agent 3</span>
          </h1>
          <p className="text-gray-400 max-w-lg mx-auto text-sm">
            Automated testing, requirement traceability, security scanning, and quality review for Agent 2 generated projects.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Setup Form */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="border-gray-800">
              <CardHeader className="pb-4">
                <CardTitle className="text-base flex items-center gap-2">
                  <FolderOpen className="h-4 w-4 text-blue-400" />
                  Project Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="project-path">Agent 2 Output Path *</Label>
                  <Input
                    id="project-path"
                    value={projectPath}
                    onChange={(e) => setProjectPath(e.target.value)}
                    placeholder="E:\final_research_agentic\output\stayease-hotel-booking-system"
                    className="mt-1.5 font-mono text-xs"
                  />
                  <p className="text-xs text-gray-500 mt-1">Full path to the Agent 2 generated project folder</p>
                </div>

                <div>
                  <Label htmlFor="srs-path">Agent 1 SRS JSON File *</Label>
                  <Input
                    id="srs-path"
                    value={srsPath}
                    onChange={(e) => setSrsPath(e.target.value)}
                    placeholder="E:\path\to\srs.json"
                    className="mt-1.5 font-mono text-xs"
                  />
                  <p className="text-xs text-gray-500 mt-1">Machine-readable SRS JSON from Agent 1</p>
                </div>

                <div>
                  <Label htmlFor="run-name">Run Name (optional)</Label>
                  <Input
                    id="run-name"
                    value={runName}
                    onChange={(e) => setRunName(e.target.value)}
                    placeholder="e.g. stayease-full-analysis-v1"
                    className="mt-1.5"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Feature Toggles */}
            <Card className="border-gray-800">
              <CardHeader className="pb-4">
                <CardTitle className="text-base flex items-center gap-2">
                  <Settings className="h-4 w-4 text-purple-400" />
                  Analysis Options
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { key: "security", label: "Security Scanning", desc: "Semgrep + npm audit + static analysis", val: enableSecurity, set: setEnableSecurity },
                  { key: "perf", label: "Performance Testing", desc: "autocannon endpoint benchmarking", val: enablePerformance, set: setEnablePerformance },
                  { key: "pw", label: "Playwright E2E", desc: "Browser-based E2E tests", val: enablePlaywright, set: setEnablePlaywright },
                ].map(({ key, label, desc, val, set }) => (
                  <div key={key} className="flex items-center justify-between p-3 rounded-lg bg-gray-900 border border-gray-800">
                    <div>
                      <p className="text-sm font-medium text-gray-200">{label}</p>
                      <p className="text-xs text-gray-500">{desc}</p>
                    </div>
                    <button onClick={() => set(!val)} className="flex-shrink-0">
                      {val
                        ? <ToggleRight className="h-6 w-6 text-blue-400" />
                        : <ToggleLeft className="h-6 w-6 text-gray-600" />
                      }
                    </button>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Model Settings */}
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <button
                  className="w-full flex items-center justify-between text-base font-semibold text-gray-100"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  <span className="flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-emerald-400" />
                    Model Settings
                  </span>
                  <ChevronRight className={`h-4 w-4 text-gray-400 transition-transform ${showAdvanced ? "rotate-90" : ""}`} />
                </button>
              </CardHeader>
              {showAdvanced && (
                <CardContent className="space-y-4 pt-0">
                  <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                    <div className="flex items-center gap-2 mb-3">
                      <Globe className="h-4 w-4 text-blue-400" />
                      <span className="text-sm font-medium text-blue-300">Ollama (Local)</span>
                      <Badge variant="info" className="text-xs">Simple tasks</Badge>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <Label className="text-xs">Base URL</Label>
                        <Input value={ollamaBaseUrl} onChange={(e) => setOllamaBaseUrl(e.target.value)} className="mt-1 text-xs" />
                      </div>
                      <div>
                        <Label className="text-xs">Model</Label>
                        <Input value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} className="mt-1 text-xs" />
                      </div>
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
                    <div className="flex items-center gap-2 mb-3">
                      <Zap className="h-4 w-4 text-purple-400" />
                      <span className="text-sm font-medium text-purple-300">GLM Cloud</span>
                      <Badge variant="default" className="text-xs">Complex reasoning</Badge>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <Label className="text-xs">API Key</Label>
                        <Input type="password" value={glmApiKey} onChange={(e) => setGlmApiKey(e.target.value)} placeholder="sk-..." className="mt-1 text-xs" />
                      </div>
                      <div>
                        <Label className="text-xs">Model</Label>
                        <Input value={glmModel} onChange={(e) => setGlmModel(e.target.value)} className="mt-1 text-xs" />
                      </div>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>

            {error && (
              <div className="p-3 rounded-lg bg-red-900/20 border border-red-800/50 text-red-400 text-sm">
                {error}
              </div>
            )}

            <Button
              onClick={handleStart}
              disabled={loading}
              variant="gradient"
              size="lg"
              className="w-full h-11 font-semibold"
            >
              {loading ? (
                <><div className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin mr-2" /> Starting Analysis...</>
              ) : (
                <><Play className="h-4 w-4 mr-2" /> Start Analysis</>
              )}
            </Button>
          </div>

          {/* Recent Runs Sidebar */}
          <div>
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-4 w-4 text-gray-400" />
                  Recent Runs
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {recentRuns.length === 0 ? (
                  <p className="text-xs text-gray-500 p-4 text-center">No runs yet</p>
                ) : (
                  <div className="divide-y divide-gray-800">
                    {recentRuns.slice(0, 8).map((run) => (
                      <button
                        key={run.id}
                        onClick={() => router.push(`/results/${run.id}`)}
                        className="w-full flex items-start gap-3 p-3 hover:bg-gray-800/50 text-left transition-colors"
                      >
                        <StatusIcon status={run.status} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-gray-200 truncate">
                            {run.config.runName || run.projectSlug || run.id.substring(0, 8)}
                          </p>
                          <p className="text-xs text-gray-500 truncate">
                            {new Date(run.createdAt).toLocaleDateString()} {new Date(run.createdAt).toLocaleTimeString()}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <Badge
                              variant={run.status as "running" | "completed" | "failed" | "pending"}
                              className="text-xs py-0"
                            >
                              {run.status}
                            </Badge>
                            {run.metrics.qualityScore > 0 && (
                              <span className="text-xs text-gray-500">
                                Score: {run.metrics.qualityScore}
                              </span>
                            )}
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-gray-600 flex-shrink-0 mt-0.5" />
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Pipeline Preview */}
            <Card className="border-gray-800 mt-4">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Analysis Pipeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                {[
                  "Project Discovery",
                  "SRS Parsing",
                  "Traceability",
                  "Unit Test Gen + Run",
                  "Integration Test Gen + Run",
                  "Quality Review",
                  "Security Scan",
                  "Performance Test",
                  "PDF Report Gen",
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-gray-400">
                    <div className="h-5 w-5 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-500 font-mono text-xs flex-shrink-0">
                      {i + 1}
                    </div>
                    {step}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
