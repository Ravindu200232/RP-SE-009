import React from "react";
import { Icon, Btn, Badge, Card, PageHeader, SectionHeader, Table, InspectorRow } from "../core/ui";

function statusBadge(status) {
  const config = {
    Ready: { bg: "bg-[#53C062]", text: "text-white" },
    Live: { bg: "bg-[#53C062]", text: "text-white" },
    Current: { bg: "bg-[#1f6feb]", text: "text-white" },
    Pending: { bg: "bg-amber-500", text: "text-white" },
    Blocked: { bg: "bg-red-500", text: "text-white" },
  }[status] || { bg: "bg-gray-400", text: "text-white" };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-white" />
      {status}
    </span>
  );
}

function timelineIcon(version, isCurrent) {
  if (isCurrent && version.deploy !== "Live") {
    return { border: "border-[#1f6feb]", bg: "bg-[#1f6feb]/15", icon: "Clock", color: "text-[#1f6feb]" };
  }
  if (version.deploy === "Live") {
    return { border: "border-[#53C062]", bg: "bg-[#53C062]/15", icon: "Check", color: "text-[#53C062]" };
  }
  if (version.deploy === "Blocked") {
    return { border: "border-red-500", bg: "bg-red-50", icon: "X", color: "text-red-500" };
  }
  return { border: "border-gray-300", bg: "bg-gray-50", icon: "Circle", color: "text-gray-400" };
}

export function VersionsHeader({ selectedCount, onCreateRelease }) {
  return (
    <PageHeader
      title="Versions & Releases"
      subtitle="Track every design choice, build iteration, QA result, and deployment package across the project lifecycle."
      breadcrumb={["AgentForge Studio", "Versions & Releases"]}
      actions={
        <>
          <Btn icon="Camera">Create Snapshot</Btn>
          <Btn icon="GitCompare" disabled={selectedCount < 2}>Compare Selected</Btn>
          <Btn icon="Tag" variant="primary" onClick={onCreateRelease}>Promote to Release</Btn>
        </>
      }
    />
  );
}

export function ReleaseTimeline({ versions, selectedIds, onToggleSelect }) {
  return (
    <div className="mb-6">
      <SectionHeader title="Release Timeline" className="mb-4" />
      <div className="space-y-4">
        {versions.map((version, index) => {
          const isCurrent = index === versions.length - 1;
          const iconPalette = timelineIcon(version, isCurrent);
          const selected = selectedIds.includes(version.version);

          return (
            <div key={version.version} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 flex-shrink-0 ${iconPalette.border} ${iconPalette.bg}`}>
                  <Icon name={iconPalette.icon} size={14} className={iconPalette.color} />
                </div>
                {index < versions.length - 1 && <div className="w-px flex-1 bg-gray-200 my-1" style={{ minHeight: 24 }} />}
              </div>
              <Card className={`flex-1 p-4 mb-4 bg-white border-gray-200 ${selected ? "border-[#1f6feb]/50 bg-blue-50/30" : ""}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-mono text-base font-bold text-gray-800">{version.version}</span>
                      {isCurrent && <Badge color="blue" dot>Current</Badge>}
                      {version.deploy === "Live" && statusBadge("Live")}
                      {version.deploy === "Blocked" && statusBadge("Blocked")}
                      {version.deploy === "Pending" && statusBadge("Pending")}
                    </div>
                    <p className="text-xs font-medium text-gray-700 mb-1">{version.summary}</p>
                    <div className="grid grid-cols-4 gap-x-6 gap-y-1 mt-2 mb-2">
                      <InspectorRow label="Date" value={version.date} />
                      <InspectorRow label="Preset" value={version.preset} />
                      <InspectorRow label="Build" value={version.build} />
                      <InspectorRow label="QA Score" value={version.qa ? `${version.qa}%` : "--"} />
                    </div>
                    <p className="text-xs text-gray-400 italic">{version.notes}</p>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <button
                      onClick={() => onToggleSelect(version.version)}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-all ${selected ? "bg-[#1f6feb]/10 text-[#1f6feb] border-[#1f6feb]/30" : "bg-white text-gray-500 border-gray-200 hover:border-gray-300 hover:text-gray-700"}`}
                    >
                      <Icon name={selected ? "CheckSquare" : "Square"} size={11} />
                      Select
                    </button>
                    <Btn size="xs" icon="Download">Bundle</Btn>
                    <Btn size="xs" icon="RotateCcw">Rollback</Btn>
                  </div>
                </div>
              </Card>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function VersionComparisonCard({ versions }) {
  return (
    <Card className="mb-6 bg-white border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200">
        <p className="text-xs font-semibold text-gray-800">Version Comparison</p>
      </div>
      <Table
        cols={["Version", "SRS Revision", "Design Preset", "Build Modules", "QA Score", "DevOps Package", "Release Status"]}
        rows={versions.map((version) => [
          <span key={`${version.version}-label`} className="font-mono font-bold text-gray-800">{version.version}</span>,
          "v1.2",
          version.preset,
          "16 modules",
          version.qa ? <span key={`${version.version}-qa`} className={version.qa >= 85 ? "text-[#53C062]" : "text-[#f0883e]"}>{version.qa}%</span> : "--",
          version.deploy === "Pending" ? statusBadge("Pending") : version.deploy === "Live" ? statusBadge("Ready") : statusBadge("Blocked"),
          statusBadge(version.deploy === "Live" ? "Live" : version.deploy === "Pending" ? "Pending" : version.deploy === "Blocked" ? "Blocked" : "Ready"),
        ])}
      />
    </Card>
  );
}

export function ReleaseNotesCard() {
  const notes = [
    "Fixed booking-service response schema mismatch (BUG-014)",
    "Fixed payment webhook idempotency key validation (BUG-013)",
    "Switched to Enterprise Dashboard design preset",
    "Added reporting-service with monthly aggregation",
    "Improved static analysis - 0 errors, 3 warnings",
    "Docker and CI/CD pipeline generation ready",
  ];

  return (
    <Card className="p-4 bg-white border-gray-200">
      <SectionHeader title="Release Notes - v0.3.0-rc" subtitle="Current working release candidate." className="mb-3" />
      <div className="space-y-2">
        {notes.map((note) => (
          <div key={note} className="flex items-start gap-2">
            <span className="text-[#53C062] mt-0.5">•</span>
            <span className="text-xs text-gray-600">{note}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-4">
        <Btn size="xs" icon="Edit2">Edit Notes</Btn>
        <Btn size="xs" icon="Tag" variant="primary">Promote to v1.0.0</Btn>
        <Btn size="xs" icon="Download">Download Bundle</Btn>
      </div>
    </Card>
  );
}
