"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  FileText, FolderOpen, Package, FileJson, Eye,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Header } from "@/components/layout/Header";
import type { RunRecord } from "@/types";

export default function ReportsPage() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [artifacts, setArtifacts] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      const [runRes, artRes] = await Promise.all([
        fetch(`/api/run/${runId}`),
        fetch(`/api/run/${runId}/artifacts`),
      ]);
      const runData = await runRes.json();
      if (runData.run) setRun(runData.run);
      if (artRes.ok) {
        const artData = await artRes.json();
        setArtifacts(artData.files || []);
      }
      setLoading(false);
    };
    load();
  }, [runId]);

  const downloadFile = async (type: string) => {
    setDownloading(type);
    try {
      const res = await fetch(`/api/run/${runId}/report?type=${type}`);
      if (!res.ok) { alert("File not available yet"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = getDownloadName(type, runId);
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Download failed");
    }
    setDownloading(null);
  };

  const viewFile = (file: string) => {
    window.open(`/api/run/${runId}/artifacts?file=${encodeURIComponent(file)}`, "_blank", "noopener,noreferrer");
  };

  const openOutputFolder = () => {
    if (run?.outputPath) {
      navigator.clipboard.writeText(run.outputPath).then(() => {
        alert(`Path copied to clipboard:\n${run.outputPath}\n\nOpen this path in File Explorer.`);
      });
    }
  };

  const reportFiles = artifacts.filter((f) =>
    f.startsWith("reports/") || f.startsWith("bugs/") || f.startsWith("pdf/") || f.startsWith("html/")
  );

  const generatedTestFiles = artifacts.filter((f) => f.startsWith("generated-tests/"));
  const hasPdfReport = artifacts.includes("pdf/agent3_report.pdf");
  const hasHtmlReport = artifacts.includes("html/report.html");

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
            <FileText className="h-5 w-5 text-blue-400" />
            Reports & Export
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Run ID: <span className="font-mono">{runId}</span>
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Download actions */}
          <div className="lg:col-span-1 space-y-4">
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Download Options</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  onClick={() => downloadFile("json")}
                  disabled={downloading === "json"}
                  variant="outline"
                  className="w-full justify-start gap-2"
                >
                  <FileJson className="h-4 w-4 text-blue-400" />
                  {downloading === "json" ? "Downloading..." : "Download Final JSON Report"}
                </Button>

                <Button
                  onClick={() => downloadFile("pdf")}
                  disabled={downloading === "pdf" || !hasPdfReport}
                  variant="outline"
                  className="w-full justify-start gap-2"
                >
                  <FileText className="h-4 w-4 text-rose-400" />
                  {downloading === "pdf" ? "Downloading..." : "Download Color PDF QA Report"}
                </Button>

                <Button
                  onClick={() => downloadFile("html")}
                  disabled={downloading === "html" || !hasHtmlReport}
                  variant="outline"
                  className="w-full justify-start gap-2"
                >
                  <FileText className="h-4 w-4 text-cyan-400" />
                  {downloading === "html" ? "Downloading..." : "Download HTML QA Report"}
                </Button>

                <Button
                  onClick={() => downloadFile("zip")}
                  disabled={downloading === "zip"}
                  variant="outline"
                  className="w-full justify-start gap-2"
                >
                  <Package className="h-4 w-4 text-purple-400" />
                  {downloading === "zip" ? "Creating ZIP..." : "Export All Artifacts (ZIP)"}
                </Button>

                <Button
                  onClick={openOutputFolder}
                  variant="secondary"
                  className="w-full justify-start gap-2"
                >
                  <FolderOpen className="h-4 w-4 text-emerald-400" />
                  Copy Output Path
                </Button>
              </CardContent>
            </Card>

            {/* Run Info */}
            {run && (
              <Card className="border-gray-800">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Run Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Status</span>
                    <Badge variant={run.status as "completed" | "failed" | "running" | "pending"}>
                      {run.status}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Quality Score</span>
                    <span className={`font-bold ${run.metrics.qualityScore >= 60 ? "text-green-400" : "text-red-400"}`}>
                      {run.metrics.qualityScore}/100
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Total Files</span>
                    <span className="text-gray-200">{run.metrics.totalFiles}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Security Issues</span>
                    <span className="text-gray-200">{run.metrics.securityIssues}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Created</span>
                    <span className="text-gray-200">{new Date(run.createdAt).toLocaleDateString()}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Output Path</span>
                    <p className="font-mono text-xs text-gray-400 mt-1 break-all">{run.outputPath}</p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Artifact browser */}
          <div className="lg:col-span-2 space-y-4">
            {/* Report files */}
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center justify-between">
                  <span>Report Files ({reportFiles.length})</span>
                  <span className="text-xs text-gray-500 font-normal">Click to view</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {reportFiles.length === 0 ? (
                  <p className="text-xs text-gray-500">No reports generated yet</p>
                ) : (
                  <div className="space-y-1">
                    {reportFiles.map((file) => (
                      <div
                        key={file}
                        className="flex items-center justify-between p-2 rounded hover:bg-gray-800/50 group transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="h-3.5 w-3.5 text-gray-500 flex-shrink-0" />
                          <span className="font-mono text-xs text-gray-300 truncate">{file}</span>
                        </div>
                        <button
                          onClick={() => viewFile(file)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 flex-shrink-0 ml-2"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          View
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Generated Tests */}
            {generatedTestFiles.length > 0 && (
              <Card className="border-gray-800">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Generated Test Files ({generatedTestFiles.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {generatedTestFiles.map((file) => (
                      <div
                        key={file}
                        className="flex items-center justify-between p-2 rounded hover:bg-gray-800/50 group transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0" />
                          <span className="font-mono text-xs text-gray-300 truncate">{file}</span>
                        </div>
                        <button
                          onClick={() => viewFile(file)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 flex-shrink-0 ml-2"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          View
                        </button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* All Artifacts */}
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">All Artifacts ({artifacts.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-64 overflow-y-auto space-y-0.5 scrollbar-hide">
                  {artifacts.map((file) => (
                    <div key={file} className="font-mono text-xs text-gray-500 py-0.5 px-1 hover:text-gray-300 hover:bg-gray-800/40 rounded transition-colors">
                      {file}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}

function getDownloadName(type: string, runId: string): string {
  const suffix = runId.substring(0, 8);
  switch (type) {
    case "pdf":
      return `agent3-report-${suffix}.pdf`;
    case "html":
      return `agent3-report-${suffix}.html`;
    case "zip":
      return `agent3-report-${suffix}.zip`;
    default:
      return `agent3-report-${suffix}.json`;
  }
}
