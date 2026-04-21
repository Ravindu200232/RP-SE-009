"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  BarChart2, CheckCircle2, XCircle, Shield, Zap, FileText,
  TrendingUp, AlertTriangle, Clock, ChevronRight,
} from "lucide-react";
import {
  RadialBarChart, RadialBar, ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Header } from "@/components/layout/Header";
import type { RunRecord, FinalReport } from "@/types";

const SEVERITY_COLORS = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
};

export default function ResultsPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [runRes, reportRes] = await Promise.all([
          fetch(`/api/run/${runId}`),
          fetch(`/api/run/${runId}/artifacts?file=reports/final_agent3_report.json`),
        ]);
        const runData = await runRes.json();
        if (runData.run) setRun(runData.run);
        if (reportRes.ok) {
          const rData = await reportRes.json();
          setReport(rData as FinalReport);
        }
      } catch {}
      setLoading(false);
    };
    load();
  }, [runId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  const metrics = run?.metrics;
  const qualityScore = report?.qualityScore?.overall ?? metrics?.qualityScore ?? 0;
  const passed = report?.qualityScore?.passed ?? metrics?.passed ?? false;

  const scoreData = [
    { name: "Functional", value: report?.qualityScore?.functionalCorrectness ?? 0, fill: "#3b82f6" },
    { name: "Quality", value: report?.qualityScore?.codeQuality ?? 0, fill: "#8b5cf6" },
    { name: "Security", value: report?.qualityScore?.security ?? 0, fill: "#10b981" },
    { name: "Performance", value: report?.qualityScore?.performance ?? 0, fill: "#f59e0b" },
  ];

  const secData = [
    { name: "Critical", value: report?.securitySummary?.critical ?? 0 },
    { name: "High", value: report?.securitySummary?.high ?? 0 },
    { name: "Medium", value: report?.securitySummary?.medium ?? 0 },
    { name: "Low", value: report?.securitySummary?.low ?? 0 },
  ].filter((d) => d.value > 0);

  const reqCoverage = report?.requirementsSummary?.coveragePercent ?? 0;

  return (
    <div className="min-h-screen bg-gray-950">
      <Header runId={runId} />
      <div className="fixed inset-0 bg-grid opacity-20 pointer-events-none" />

      <main className="relative max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <BarChart2 className="h-5 w-5 text-blue-400" />
              Results Overview
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {report?.projectName || run?.config.projectPath?.split(/[\\/]/).pop()}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={passed ? "pass" : "fail"} className="text-sm px-3 py-1">
              {passed ? "PASS" : "FAIL"}
            </Badge>
            <button
              onClick={() => router.push(`/findings/${runId}`)}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
            >
              Explore Findings <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Top Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: "Total Files", value: metrics?.totalFiles ?? 0, icon: FileText, color: "text-blue-400" },
            { label: "Requirements", value: `${reqCoverage}%`, icon: CheckCircle2, color: "text-emerald-400", sub: `${report?.requirementsSummary?.implemented ?? 0}/${report?.requirementsSummary?.total ?? 0} implemented` },
            { label: "Unit Tests", value: `${metrics?.unitTestsPassed ?? 0}/${metrics?.unitTestsGenerated ?? 0}`, icon: CheckCircle2, color: "text-green-400", sub: `${metrics?.unitTestsFailed ?? 0} failed` },
            { label: "Security Issues", value: report?.securitySummary?.total ?? metrics?.securityIssues ?? 0, icon: Shield, color: (report?.securitySummary?.critical ?? 0) > 0 ? "text-red-400" : "text-emerald-400", sub: `${report?.securitySummary?.critical ?? 0} critical` },
          ].map(({ label, value, icon: Icon, color, sub }) => (
            <Card key={label} className="border-gray-800">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                    {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
                  </div>
                  <Icon className={`h-5 w-5 ${color} opacity-60`} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Quality Score Breakdown */}
          <div className="lg:col-span-2 space-y-5">
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-400" />
                  Quality Score Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6 mb-5">
                  <div className="text-center">
                    <div className="text-5xl font-black" style={{ color: qualityScore >= 80 ? "#22c55e" : qualityScore >= 60 ? "#eab308" : "#ef4444" }}>
                      {qualityScore}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Overall Score</div>
                  </div>
                  <div className="flex-1 space-y-3">
                    {scoreData.map((item) => (
                      <div key={item.name}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-400">{item.name}</span>
                          <span className="font-medium text-gray-200">{item.value}</span>
                        </div>
                        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${item.value}%`, backgroundColor: item.fill }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 text-center">
                  {[
                    { label: "Functional Correctness", weight: "40%", val: report?.qualityScore?.functionalCorrectness ?? 0 },
                    { label: "Code Quality", weight: "25%", val: report?.qualityScore?.codeQuality ?? 0 },
                    { label: "Security", weight: "20%", val: report?.qualityScore?.security ?? 0 },
                  ].map(({ label, weight, val }) => (
                    <div key={label} className="bg-gray-900 rounded-lg p-3">
                      <p className="text-xs text-gray-500">{label}</p>
                      <p className="text-xs text-gray-600">{weight}</p>
                      <p className={`text-lg font-bold mt-1 ${val >= 70 ? "text-green-400" : val >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                        {val}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Requirements Traceability */}
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Requirements Traceability</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-400">Coverage</span>
                    <span className="font-bold text-white">{reqCoverage}%</span>
                  </div>
                  <Progress value={reqCoverage} variant={reqCoverage >= 70 ? "success" : "danger"} className="h-3" />
                </div>
                <div className="grid grid-cols-4 gap-2 mt-4">
                  {[
                    { label: "Implemented", val: report?.requirementsSummary?.implemented ?? 0, color: "text-green-400" },
                    { label: "Partial", val: report?.requirementsSummary?.partiallyImplemented ?? 0, color: "text-yellow-400" },
                    { label: "Missing", val: report?.requirementsSummary?.missing ?? 0, color: "text-red-400" },
                    { label: "Unverifiable", val: report?.requirementsSummary?.unverifiable ?? 0, color: "text-gray-400" },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="text-center bg-gray-900 rounded-lg p-2">
                      <p className={`text-xl font-bold ${color}`}>{val}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Integration Tests */}
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Integration Tests</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Total", val: metrics?.integrationTestsGenerated ?? 0 },
                    { label: "Passed", val: metrics?.integrationTestsPassed ?? 0, color: "text-green-400" },
                    { label: "Failed", val: metrics?.integrationTestsFailed ?? 0, color: "text-red-400" },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="text-center bg-gray-900 rounded-lg p-3">
                      <p className={`text-2xl font-bold ${color || "text-white"}`}>{val}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right column */}
          <div className="space-y-5">
            {/* Security Pie */}
            <Card className="border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4 text-orange-400" />
                  Security Issues
                </CardTitle>
              </CardHeader>
              <CardContent>
                {secData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie data={secData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="value">
                        {secData.map((entry, i) => (
                          <Cell key={i} fill={Object.values(SEVERITY_COLORS)[i] || "#6b7280"} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: "8px", color: "#e5e7eb" }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-40 flex items-center justify-center">
                    <p className="text-sm text-gray-500">No security findings</p>
                  </div>
                )}
                <div className="space-y-1.5 mt-2">
                  {[
                    { label: "Critical", val: report?.securitySummary?.critical ?? 0, color: "text-red-400" },
                    { label: "High", val: report?.securitySummary?.high ?? 0, color: "text-orange-400" },
                    { label: "Medium", val: report?.securitySummary?.medium ?? 0, color: "text-yellow-400" },
                    { label: "Low", val: report?.securitySummary?.low ?? 0, color: "text-green-400" },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="flex justify-between text-xs">
                      <span className="text-gray-400">{label}</span>
                      <span className={`font-bold ${color}`}>{val}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Major Blockers */}
            {report?.majorBlockers && report.majorBlockers.length > 0 && (
              <Card className="border-gray-800 border-red-900/30">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-red-400" />
                    Major Blockers
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {report.majorBlockers.map((b, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <XCircle className="h-3.5 w-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                      <span className="text-red-300">{b}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Recommendations */}
            {report?.recommendations && report.recommendations.length > 0 && (
              <Card className="border-gray-800">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Recommendations</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {report.recommendations.slice(0, 5).map((rec, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <ChevronRight className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" />
                      <span className="text-gray-300">{rec}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Quick Nav */}
            <div className="space-y-2">
              {[
                { label: "Explore Findings", href: `/findings/${runId}`, icon: AlertTriangle },
                { label: "Download Reports", href: `/reports/${runId}`, icon: FileText },
              ].map(({ label, href, icon: Icon }) => (
                <button
                  key={href}
                  onClick={() => router.push(href)}
                  className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-900 border border-gray-800 hover:border-gray-700 transition-all text-sm text-gray-300 hover:text-white"
                >
                  <span className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-gray-400" />
                    {label}
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-600" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
