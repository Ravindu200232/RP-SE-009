"use client";

import { useState } from "react";
import { Check, Copy, Download, FileJson } from "lucide-react";
import type {
  SrsDocument,
  SrsEnvelope,
  FunctionalRequirement,
  NonFunctionalRequirement,
} from "@agentforge/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { MermaidDiagram } from "./mermaid";
import { api } from "@/lib/api";

export const TAB_DEFS = [
  { key: "srs", label: "SRS Document" },
  { key: "requirements", label: "Functional Req." },
  { key: "json", label: "JSON Output" },
  { key: "diagrams", label: "Diagrams" },
  { key: "ambiguities", label: "Ambiguities" },
  { key: "risks", label: "Risk & Priority" },
] as const;

export type TabKey = (typeof TAB_DEFS)[number]["key"];

function priorityVariant(p: string) {
  return p === "high" ? "danger" : p === "medium" ? "warning" : "neutral";
}

/* ── SRS Document ───────────────────────────────────────── */
function H({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-2 mt-6 text-base font-semibold text-foreground">{children}</h2>;
}
function Sub({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-1 mt-4 text-sm font-semibold text-foreground">{children}</h3>;
}

export function SrsDocumentTab({ doc, status }: { doc: SrsDocument; status: string }) {
  const summary = doc.app_summary || ({} as SrsDocument["app_summary"]);
  return (
    <div className="mx-auto max-w-3xl pb-10">
      <Card className="mb-4 flex items-center justify-between border-l-4 border-l-success p-4">
        <div>
          <div className="text-sm font-semibold">{doc.project_name}</div>
          <div className="text-xs text-muted-foreground">{doc.document_title} · v{doc.version}</div>
        </div>
        <Badge variant={status === "approved" ? "success" : "neutral"} className="capitalize">
          {status}
        </Badge>
      </Card>

      <article className="prose-sm text-sm leading-relaxed text-foreground">
        <H>1. Introduction</H>
        <Sub>1.1 Purpose</Sub>
        <p className="text-muted-foreground">{summary.business_goal}</p>
        <Sub>1.2 Scope</Sub>
        <p className="text-muted-foreground">{summary.short_description}</p>
        <Sub>1.3 Definitions, Acronyms and Abbreviations</Sub>
        <p className="text-muted-foreground">
          SRS — Software Requirements Specification; FR — Functional Requirement; NFR — Non-Functional
          Requirement; RBAC — Role-Based Access Control; RTM — Requirement Traceability Matrix.
        </p>

        <H>2. Overall Description</H>
        <Sub>2.1 Product Perspective</Sub>
        <p className="text-muted-foreground">
          The product is a {doc.app_type?.primary_type}. System category: {doc.system_category}.
        </p>
        <Sub>2.2 Product Functions (Modules)</Sub>
        <div className="flex flex-wrap gap-1.5">
          {(doc.main_modules || []).map((m) => (
            <Badge key={m} variant="neutral">
              {m}
            </Badge>
          ))}
        </div>
        <Sub>2.3 User Characteristics (Roles)</Sub>
        <ul className="space-y-1">
          {(doc.roles || []).map((r) => (
            <li key={r.role_key} className="text-muted-foreground">
              <span className="font-medium text-foreground">{r.role_name}</span> — {r.description}
            </li>
          ))}
        </ul>

        <H>3. Specific Requirements (summary)</H>
        <p className="text-muted-foreground">
          {(doc.functional_requirements || []).length} functional and {(doc.non_functional_requirements || []).length}{" "}
          non-functional requirements are specified. See the Functional Req. tab for the full list, and the
          JSON Output tab for the machine-readable specification.
        </p>

        <H>4. Assumptions &amp; Constraints</H>
        <ul className="space-y-1">
          {(doc.assumptions || []).map((a, i) => (
            <li key={i} className="text-muted-foreground">• {a}</li>
          ))}
        </ul>
      </article>
    </div>
  );
}

/* ── Functional Requirements ────────────────────────────── */
export function FunctionalReqTab({ doc }: { doc: SrsDocument }) {
  const frs = (doc.functional_requirements || []) as FunctionalRequirement[];
  const nfrs = (doc.non_functional_requirements || []) as NonFunctionalRequirement[];
  return (
    <div className="mx-auto max-w-3xl space-y-2 pb-10">
      {frs.map((fr) => (
        <Card key={fr.id} className="flex items-start gap-3 p-3">
          <Badge variant="default" className="mt-0.5 font-mono">
            {fr.id}
          </Badge>
          <div className="min-w-0 flex-1">
            <div className="text-sm">{fr.requirement}</div>
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="neutral">{fr.module}</Badge>
              <Badge variant={priorityVariant(fr.priority)} className="capitalize">
                {fr.priority}
              </Badge>
            </div>
          </div>
        </Card>
      ))}
      <h3 className="pt-4 text-sm font-semibold">Non-Functional Requirements</h3>
      {nfrs.map((nfr) => (
        <Card key={nfr.id} className="flex items-start gap-3 p-3">
          <Badge variant="neutral" className="mt-0.5 font-mono">
            {nfr.id}
          </Badge>
          <div className="min-w-0 flex-1">
            <div className="text-sm">{nfr.requirement}</div>
            <Badge variant="outline" className="mt-1">
              {nfr.category}
            </Badge>
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── JSON Output ────────────────────────────────────────── */
export function JsonOutputTab({ srs, projectId }: { srs: SrsEnvelope; projectId: string }) {
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(srs, null, 2);
  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col pb-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileJson className="h-4 w-4" /> Machine-readable SRS
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy JSON"}
          </Button>
          <a href={api.downloadJsonUrl(projectId)} download>
            <Button size="sm" variant="outline">
              <Download className="h-3.5 w-3.5" /> Download
            </Button>
          </a>
        </div>
      </div>
      <pre className="afs-json flex-1 overflow-auto rounded-xl border border-border bg-[#0f172a] p-4 text-[11px] leading-relaxed text-slate-200">
        {text}
      </pre>
    </div>
  );
}

/* ── Diagrams ───────────────────────────────────────────── */
export function DiagramsTab({ doc }: { doc: SrsDocument }) {
  const diagrams = doc.diagrams || [];
  if (diagrams.length === 0) {
    return <p className="text-sm text-muted-foreground">No diagrams generated.</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-4 pb-10 xl:grid-cols-2">
      {diagrams.map((d) => (
        <Card key={d.id} className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="text-sm font-medium">{d.title}</span>
            <Badge variant="neutral">{d.format}</Badge>
          </div>
          <div className="max-h-80 overflow-auto bg-secondary/30 p-3">
            <MermaidDiagram source={d.source} />
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── Ambiguities ────────────────────────────────────────── */
export function AmbiguitiesTab({ doc }: { doc: SrsDocument }) {
  const ambiguities = doc.ambiguities || [];
  const assumptions = doc.assumptions || [];
  return (
    <div className="mx-auto max-w-3xl space-y-2 pb-10">
      {ambiguities.map((a) => (
        <Card key={a.id} className="flex items-start gap-3 p-3">
          <Badge variant={a.needs_clarification ? "warning" : "neutral"} className="mt-0.5 font-mono">
            {a.id}
          </Badge>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">{a.area}</div>
            <div className="text-sm text-muted-foreground">{a.description}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Assumption:</span> {a.assumption_made}
            </div>
          </div>
          {a.needs_clarification && <Badge variant="warning">needs clarification</Badge>}
        </Card>
      ))}
      <h3 className="pt-4 text-sm font-semibold">Assumptions</h3>
      <Card className="p-3">
        <ul className="space-y-1 text-sm text-muted-foreground">
          {assumptions.map((a, i) => (
            <li key={i}>• {a}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

/* ── Risk & Priority ────────────────────────────────────── */
export function RiskPriorityTab({ doc }: { doc: SrsDocument }) {
  const risks = doc.risk_priority || [];
  const sev = (s: string) =>
    /high/i.test(s) ? "danger" : /med/i.test(s) ? "warning" : "success";
  return (
    <div className="grid grid-cols-1 gap-3 pb-10 lg:grid-cols-2">
      {risks.map((r) => (
        <Card key={r.id} className="p-4">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-sm font-semibold">{r.risk}</span>
            <Badge variant={sev(r.severity) as "danger" | "warning" | "success"}>{r.severity} Risk</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Reason:</span> {r.reason}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Mitigation:</span> {r.mitigation}
          </p>
        </Card>
      ))}
    </div>
  );
}
