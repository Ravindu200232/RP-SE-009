"use client";

import { Download, Lock, ChevronRight } from "lucide-react";
import type { Project, SrsSummary } from "@agentforge/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-border px-4 py-3">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</div>
      {children}
    </div>
  );
}

function Row({ label, value, valueClass }: { label: string; value: React.ReactNode; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={valueClass || "font-medium"}>{value}</span>
    </div>
  );
}

export function Inspector({
  project,
  summary,
  onApprove,
  onDownloadPdf,
}: {
  project: Project;
  summary?: SrsSummary;
  onApprove: () => void;
  onDownloadPdf: () => void;
}) {
  const cx = project.complexity;
  const stack = project.suggested_stack;
  const cls = project.classification;
  const status = project.status;

  return (
    <aside className="hidden w-72 shrink-0 overflow-y-auto border-l border-border bg-card lg:block">
      <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Analysis Inspector
      </div>

      <Section title="Document">
        <Row label="Standard" value="IEEE 830" />
        <Row label="Version" value={`v${project.current_version}`} />
        <Row
          label="Status"
          value={
            <Badge variant={status === "approved" ? "success" : "neutral"} className="capitalize">
              {status}
            </Badge>
          }
        />
        <Row label="Edits" value={status === "customized" ? "Yes" : "None"} />
      </Section>

      {summary && (
        <Section title="Requirement Summary">
          <Row label="Functional" value={summary.functional} />
          <Row label="Non-Functional" value={summary.non_functional} />
          <Row label="Use cases" value={summary.use_cases} />
          <Row label="Open ambiguities" value={summary.open_ambiguities} />
        </Section>
      )}

      {cx && (
        <Section title="Complexity Estimate">
          <Row label="Overall" value={cx.overall} />
          <Row label="Backend" value={cx.backend} />
          <Row label="Frontend" value={cx.frontend} />
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-secondary">
            <div className="h-full rounded-full bg-warning" style={{ width: complexityWidth(cx.overall) }} />
          </div>
        </Section>
      )}

      {stack && (
        <Section title={"Suggested Stack" + (stack.locked ? "  (locked)" : "")}>
          <Row label="Frontend" value={stack.frontend} />
          <Row label="Backend" value={stack.backend} />
          <Row label="Database" value={stack.database} />
          <Row label="Architecture" value={stack.architecture} />
          {stack.locked && (
            <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
              <Lock className="h-3 w-3" /> Locked until approval
            </div>
          )}
        </Section>
      )}

      <Section title="Detected Domain">
        <Badge variant="default">{cls?.detected_domain || project.detected_domain}</Badge>
        <p className="mt-1.5 text-[11px] text-muted-foreground">
          {cls ? `${Math.round((cls.confidence || 0) * 100)}% confidence · ${cls.app_type}` : ""}
        </p>
      </Section>

      <Section title="Next Step">
        <Button onClick={onApprove} className="w-full" size="sm">
          {status === "approved" ? "Approved" : "Approve & Open Design Selector"}
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button onClick={onDownloadPdf} variant="outline" className="mt-2 w-full" size="sm">
          <Download className="h-4 w-4" /> Download SRS PDF
        </Button>
      </Section>
    </aside>
  );
}

function complexityWidth(overall: string): string {
  const v = overall.toLowerCase();
  if (v.includes("high") && !v.includes("medium")) return "90%";
  if (v.includes("medium-high")) return "75%";
  if (v.includes("medium")) return "55%";
  if (v.includes("low")) return "30%";
  return "60%";
}
