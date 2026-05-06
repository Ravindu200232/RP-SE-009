import React from "react";
import { Icon, Btn, Card, PageHeader, InspectorRow } from "../core/ui";

const CATEGORIES = ["all", "Requirements", "Diagrams", "Design", "Code", "API", "Testing", "DevOps", "CI/CD", "Cloud"];

const STATUS_COLORS = {
  deployed: { bg: "bg-green-600", text: "text-white" },
  ready: { bg: "bg-blue-600", text: "text-white" },
  staged: { bg: "bg-amber-500", text: "text-white" },
  building: { bg: "bg-purple-600", text: "text-white" },
  failed: { bg: "bg-red-600", text: "text-white" },
  pending: { bg: "bg-gray-500", text: "text-white" },
  approved: { bg: "bg-green-600", text: "text-white" },
  "in-progress": { bg: "bg-blue-600", text: "text-white" },
};

function formatIcon(fmt) {
  return {
    PDF: "FileText",
    DOCX: "FileText",
    JSON: "FileCode",
    PNG: "Image",
    ZIP: "Archive",
    YAML: "FileCode",
    DIR: "FolderOpen",
  }[fmt] || "File";
}

function categoryBadgeColor(category) {
  const color = {
    Requirements: "blue",
    Diagrams: "blue",
    Design: "blue",
    Code: "green",
    API: "blue",
    Testing: "green",
    DevOps: "green",
    "CI/CD": "blue",
    Cloud: "blue",
  }[category] || "default";

  switch (color) {
    case "blue":
      return { bg: "bg-[#1f6feb]/15", text: "text-[#1f6feb]", border: "border-[#1f6feb]/30" };
    case "green":
      return { bg: "bg-[#53C062]/15", text: "text-[#53C062]", border: "border-[#53C062]/30" };
    default:
      return { bg: "bg-gray-100", text: "text-gray-500", border: "border-gray-200" };
  }
}

function statusBadge(status) {
  const normalizedStatus = status.toLowerCase().replace(/\s+/g, "-");
  const colors = STATUS_COLORS[normalizedStatus] || { bg: "bg-gray-500", text: "text-white" };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}>
      {status}
    </span>
  );
}

function statusIconPalette(status) {
  switch (status) {
    case "approved":
      return { bg: "bg-[#53C062]/15", color: "text-[#53C062]" };
    case "in-progress":
      return { bg: "bg-[#1f6feb]/15", color: "text-[#1f6feb]" };
    default:
      return { bg: "bg-gray-100", color: "text-gray-400" };
  }
}

export function ArtifactsHeader({ selectedCount, onDownloadAll, onCompareVersions }) {
  return (
    <PageHeader
      title="Artifacts & Exports"
      subtitle="Browse, filter, preview, and export all generated documents, code bundles, reports, and deployment files."
      breadcrumb={["AgentForge Studio", "Artifacts & Exports"]}
      actions={
        <>
          <Btn icon="Download">Export Selected {selectedCount > 0 && `(${selectedCount})`}</Btn>
          <Btn icon="Download" variant="primary" onClick={onDownloadAll}>
            Download All
          </Btn>
          <Btn icon="GitCompare" onClick={onCompareVersions}>
            Compare Versions
          </Btn>
        </>
      }
    />
  );
}

export function ArtifactFilters({ filter, artifactsCount, onSelectFilter }) {
  return (
    <div className="flex items-center gap-2 mb-5 flex-wrap">
      {CATEGORIES.map((category) => (
        <button
          key={category}
          onClick={() => onSelectFilter(category)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all capitalize ${
            filter === category
              ? "bg-[#1f6feb] text-white border-[#1f6feb]"
              : "bg-gray-50 text-gray-600 border-gray-200 hover:border-gray-300 hover:text-gray-800"
          }`}
        >
          {category === "all" ? `All (${artifactsCount})` : category}
        </button>
      ))}
    </div>
  );
}

export function ArtifactBulkActions({ selectedCount, onClearSelection }) {
  if (!selectedCount) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-xl border border-[#1f6feb]/30 mb-4">
      <span className="text-xs text-[#1f6feb] font-medium">
        {selectedCount} artifact{selectedCount > 1 ? "s" : ""} selected
      </span>
      <Btn size="xs" icon="Download">Export Selected</Btn>
      <Btn size="xs" icon="GitCompare">Compare Versions</Btn>
      <Btn size="xs" icon="Archive">Archive</Btn>
      <button onClick={onClearSelection} className="ml-auto text-xs text-gray-400 hover:text-gray-600">
        Clear selection
      </button>
    </div>
  );
}

export function ArtifactGrid({ artifacts, selectedIds, onToggleSelect, onNavigate, onToast }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {artifacts.map((artifact) => {
        const selected = selectedIds.includes(artifact.id);
        const categoryPalette = categoryBadgeColor(artifact.category);
        const iconPalette = statusIconPalette(artifact.status);

        return (
          <Card
            key={artifact.id}
            className={`p-4 transition-all cursor-pointer ${selected ? "border-[#1f6feb]/50 bg-blue-50/50" : "hover:border-gray-300"}`}
            onClick={() => onToggleSelect(artifact.id)}
          >
            <div className="flex items-start gap-3 mb-3">
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${iconPalette.bg}`}>
                <Icon name={formatIcon(artifact.format)} size={16} className={iconPalette.color} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-gray-800 truncate">{artifact.name}</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${categoryPalette.bg} ${categoryPalette.text} ${categoryPalette.border}`}>
                    {artifact.category}
                  </span>
                  <span className="font-mono text-[9px] text-gray-400">{artifact.format}</span>
                </div>
              </div>
              {selected && <Icon name="CheckCircle2" size={14} className="text-[#1f6feb] flex-shrink-0" />}
            </div>

            <div className="space-y-1 mb-3">
              <InspectorRow label="Generated by" value={artifact.agent} />
              <InspectorRow label="Version" value={artifact.version} />
              <InspectorRow label="Updated" value={artifact.updatedAt} />
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Status</span>
                {statusBadge(artifact.status)}
              </div>
            </div>

            <div className="flex gap-1" onClick={(event) => event.stopPropagation()}>
              <Btn size="xs" icon="Eye" disabled={artifact.status === "pending"}>Preview</Btn>
              <Btn
                size="xs"
                icon="Download"
                disabled={artifact.status === "pending"}
                onClick={() => onToast(`Downloading ${artifact.name}...`, "success")}
              >
                Download
              </Btn>
              {artifact.status === "pending" ? (
                <Btn
                  size="xs"
                  icon="RefreshCw"
                  className="bg-green-600 hover:bg-green-700 text-[#1f6feb]"
                  onClick={() => onToast(`Generating ${artifact.name}...`, "success")}
                >
                  Generate
                </Btn>
              ) : (
                <Btn
                  size="xs"
                  icon="ExternalLink"
                  onClick={() => {
                    const page =
                      artifact.agent === "Agent 1"
                        ? "agent1"
                        : artifact.agent === "Agent 2"
                          ? "agent2"
                          : artifact.agent === "Agent 3"
                            ? "agent3"
                            : artifact.agent === "Agent 4"
                              ? "agent4"
                              : "dashboard";
                    onNavigate(page);
                  }}
                >
                  Open
                </Btn>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
