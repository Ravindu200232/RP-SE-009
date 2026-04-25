import React from "react";
import {
  Icon,
  Btn,
  Badge,
  Card,
  KPICard,
  PageHeader,
  ProgressBar,
  Table,
  InspectorPanel,
  InspectorSection,
  InspectorRow,
} from "../core/ui";

const DASHBOARD_KPIS = [
  { label: "Active Projects", value: "08", icon: "FolderOpen", color: "default" },
  { label: "SRS Versions", value: "14", icon: "FileText", color: "blue" },
  { label: "Builds Running", value: "03", icon: "Loader2", color: "violet" },
  { label: "QA Pass Rate", value: "92%", icon: "CheckCircle2", color: "green" },
  { label: "Deploy-Ready Builds", value: "05", icon: "Package", color: "amber" },
  { label: "Live Releases", value: "02", icon: "Globe", color: "green" },
];

const STAGE_COLORS = {
  complete: { ring: "border-[#53C062]", text: "text-gray-800", bg: "bg-[#53C062]/15" },
  active: { ring: "border-[#58a6ff]", text: "text-gray-800", bg: "bg-[#eff6ff]" },
  pending: { ring: "border-gray-300", text: "text-gray-800", bg: "bg-white/80" },
};

const DEPLOY_STATUS_COLORS = {
  deployed: { bg: "bg-green-600", text: "text-white" },
  ready: { bg: "bg-blue-600", text: "text-white" },
  staged: { bg: "bg-amber-500", text: "text-white" },
  building: { bg: "bg-purple-600", text: "text-white" },
  failed: { bg: "bg-red-600", text: "text-white" },
  pending: { bg: "bg-gray-500", text: "text-white" },
};

function DeployStatusBadge({ status }) {
  const normalizedStatus = status.toLowerCase().replace(/\s+/g, "-");
  const colors = DEPLOY_STATUS_COLORS[normalizedStatus] || {
    bg: "bg-gray-500",
    text: "text-white",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
    >
      {status}
    </span>
  );
}

export function DashboardHeader({ onNavigate }) {
  return (
    <PageHeader
      title="Dashboard"
      subtitle="Monitor your autonomous software engineering pipeline from idea to deployment."
      breadcrumb={["AgentForge Studio", "Dashboard"]}
      actions={
        <>
          <Btn icon="Plus" onClick={() => onNavigate("new-project")}>
            New Project
          </Btn>
          <Btn icon="Play" variant="primary" onClick={() => onNavigate("agent3")}>
            Resume Latest Build
          </Btn>
          <Btn icon="GitBranch" onClick={() => onNavigate("versions")}>
            View Pipeline
          </Btn>
        </>
      }
    />
  );
}

export function DashboardKpiGrid() {
  return (
    <div className="grid grid-cols-6 gap-3 mb-5">
      {DASHBOARD_KPIS.map((item) => (
        <KPICard
          key={item.label}
          label={item.label}
          value={item.value}
          icon={item.icon}
          color={item.color}
        />
      ))}
    </div>
  );
}

export function CurrentProjectCard({ project, onNavigate }) {
  const rows = [
    ["Project Type", project.type],
    ["Domain", project.domain],
    ["Frontend Style", project.frontendPreset],
    ["Backend Stack", project.backendStack],
    ["Current Stage", project.stage],
    ["Last Updated", project.updatedAt],
  ];

  return (
    <Card className="col-span-2 p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-800">Current Project</p>
        <Badge color="blue" dot>
          Active
        </Badge>
      </div>
      <p className="text-sm font-bold text-gray-800 mb-3">{project.name}</p>
      <div className="space-y-2 mb-4">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between">
            <span className="text-xs text-gray-600">{label}</span>
            <span className="text-xs text-gray-800 font-medium">{value}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Btn size="xs" icon="FolderOpen" onClick={() => onNavigate("agent3")}>
          Open Project
        </Btn>
        <Btn size="xs" icon="Archive" onClick={() => onNavigate("artifacts")}>
          Artifacts
        </Btn>
        <Btn size="xs" icon="Code2" variant="violet" onClick={() => onNavigate("agent2")}>
          Build Studio
        </Btn>
      </div>
    </Card>
  );
}

export function AgentPipelineCard({ pipeline, onNavigate }) {
  const activeStage = pipeline.find((stage) => stage.status === "active");

  return (
    <Card className="col-span-3 p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-800">Agent Pipeline</p>
        <Btn size="xs" icon="ExternalLink" onClick={() => onNavigate("versions")}>
          Full View
        </Btn>
      </div>
      <div className="flex items-start gap-1">
        {pipeline.map((stage, index) => {
          const palette = STAGE_COLORS[stage.status];
          const isComplete = stage.status === "complete";
          const isActive = stage.status === "active";

          return (
            <div key={stage.id} className="flex-1 flex flex-col items-center gap-1 min-w-0">
              <div className="flex items-center w-full">
                {index > 0 && (
                  <div
                    className={`h-px flex-1 ${stage.status !== "pending" ? "bg-[#53C062]" : "bg-gray-300"}`}
                  />
                )}
                <div
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${palette.ring} ${palette.bg}`}
                >
                  {isComplete ? (
                    <Icon name="Check" size={12} className="text-[#53C062]" />
                  ) : isActive ? (
                    <span className="w-2 h-2 rounded-full bg-[#58a6ff] animate-pulse" />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-gray-400" />
                  )}
                </div>
                {index < pipeline.length - 1 && (
                  <div className={`h-px flex-1 ${isComplete ? "bg-[#53C062]" : "bg-gray-300"}`} />
                )}
              </div>
              <p className={`text-[10px] text-center leading-tight font-medium ${palette.text}`}>
                {stage.label}
              </p>
              <ProgressBar
                value={stage.pct}
                color={
                  stage.status === "complete"
                    ? "green"
                    : stage.status === "active"
                      ? "blue"
                      : "default"
                }
                className="w-full"
              />
              <p className="text-[9px] text-gray-600 text-center truncate w-full px-1">{stage.pct}%</p>
            </div>
          );
        })}
      </div>
      <div className="mt-3 p-2.5 bg-white/80 backdrop-blur-md rounded-lg border border-[#53C062]/30 shadow-sm">
        <p className="text-[10px] text-gray-700">
          <Icon name="Info" size={10} className="inline mr-1 text-[#53C062]" />
          {activeStage?.note || "All stages complete."}
        </p>
      </div>
    </Card>
  );
}

export function DashboardOverviewGrid({ project, pipeline, onNavigate }) {
  return (
    <div className="grid grid-cols-5 gap-4 mb-5">
      <CurrentProjectCard project={project} onNavigate={onNavigate} />
      <AgentPipelineCard pipeline={pipeline} onNavigate={onNavigate} />
    </div>
  );
}

export function RecentBuildsTable({ builds, onNavigate }) {
  const rows = builds.map((build) => [
    <span key={`${build.id}-id`} className="font-mono text-[#58a6ff]">
      {build.id}
    </span>,
    <span key={`${build.id}-project`} className="text-[#cccccc]">
      {build.project}
    </span>,
    build.preset,
    build.stage,
    build.qaScore ? (
      <span
        key={`${build.id}-qa`}
        className={build.qaScore >= 85 ? "text-[#53C062]" : "text-[#58a6ff]"}
      >
        {build.qaScore}%
      </span>
    ) : (
      <span key={`${build.id}-empty`} className="text-gray-400">
        --
      </span>
    ),
    <DeployStatusBadge key={`${build.id}-status`} status={build.deployStatus} />,
    build.updatedAt,
    <div key={`${build.id}-actions`} className="flex gap-1">
      <Btn size="xs" onClick={() => onNavigate("agent2")}>
        Open
      </Btn>
      <Btn size="xs" icon="Terminal">
        Logs
      </Btn>
      <Btn
        size="xs"
        icon="Tag"
        variant="success"
        className="bg-[#50e61e] hover:bg-[#43c717] text-black"
      >
        Release
      </Btn>
    </div>,
  ]);

  return (
    <Card className="mb-5">
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <p className="text-xs font-semibold text-gray-800">Recent Builds</p>
        <Btn size="xs" icon="RefreshCw">
          Refresh
        </Btn>
      </div>
      <Table
        cols={[
          "Build ID",
          "Project",
          "Design Preset",
          "Agent Stage",
          "QA Score",
          "Deploy Status",
          "Updated",
          "Actions",
        ]}
        rows={rows}
      />
    </Card>
  );
}

export function QuickActionsCard({ onNavigate }) {
  const actions = [
    { label: "Create New Project", icon: "Plus", page: "new-project" },
    { label: "Generate SRS from Idea", icon: "Brain", page: "agent1" },
    { label: "Select Frontend Style", icon: "Palette", page: "design-selector" },
    { label: "Start Build", icon: "Code2", page: "agent2" },
    { label: "Run QA Suite", icon: "FlaskConical", page: "agent3" },
    { label: "Prepare Deployment", icon: "Rocket", page: "agent4" },
    { label: "Export All Artifacts", icon: "Download", page: "artifacts" },
  ];

  return (
    <Card className="p-4">
      <p className="text-xs font-semibold text-gray-800 mb-3">Quick Actions</p>
      <div className="flex flex-col gap-1.5">
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={() => onNavigate(action.page)}
            className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-gray-50 hover:bg-gray-100 text-xs text-gray-600 hover:text-gray-800 transition-all border border-transparent hover:border-gray-200"
          >
            <Icon name={action.icon} size={13} className="text-gray-500" />
            {action.label}
          </button>
        ))}
      </div>
    </Card>
  );
}

export function ActivityFeedCard({ activity }) {
  const agentStyles = {
    "Agent 1": {
      bg: "bg-blue-100",
      icon: "Brain",
      color: "text-[#58a6ff]",
    },
    "Agent 2": {
      bg: "bg-purple-100",
      icon: "Code2",
      color: "text-[#a78bfa]",
    },
    "Agent 3": {
      bg: "bg-amber-100",
      icon: "FlaskConical",
      color: "text-[#f0883e]",
    },
    "Agent 4": {
      bg: "bg-[#53C062]/20",
      icon: "Rocket",
      color: "text-[#53C062]",
    },
  };

  return (
    <Card className="p-4 col-span-2">
      <p className="text-xs font-semibold text-gray-800 mb-3">Activity Feed</p>
      <div className="space-y-2.5">
        {activity.map((item) => {
          const style = agentStyles[item.agent] || {
            bg: "bg-gray-100",
            icon: "Info",
            color: "text-gray-500",
          };

          return (
            <div key={item.id} className="flex items-start gap-3">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${style.bg}`}
              >
                <Icon name={style.icon} size={11} className={style.color} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-600 leading-relaxed">{item.msg}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">{item.time}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function DashboardBottomRow({ activity, onNavigate }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <QuickActionsCard onNavigate={onNavigate} />
      <ActivityFeedCard activity={activity} />
    </div>
  );
}

export function DashboardInspector({ onNavigate }) {
  return (
    <InspectorPanel title="Inspector">
      <InspectorSection title="Active Agent">
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: "#000000", color: "#ffffff", borderColor: "#000000" }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#ffffff" }} />
          Agent 3: Testing
        </span>
        <p className="text-xs text-gray-700 mt-2 leading-relaxed">
          Running integration test suite - 34 cases across 7 modules.
        </p>
      </InspectorSection>
      <InspectorSection title="Build Summary">
        <InspectorRow label="Build ID" value="BLD-0041" />
        <InspectorRow label="Preset" value="Enterprise Dashboard" />
        <InspectorRow label="QA Score" value="87%" />
        <InspectorRow label="Services" value="6 / 6" />
        <InspectorRow label="Pages" value="10 / 10" />
        <ProgressBar value={87} color="green" className="mt-2" />
      </InspectorSection>
      <InspectorSection title="Risk Alerts">
        <div className="space-y-2">
          <div className="p-2.5 bg-white/85 backdrop-blur-md rounded-lg border border-white/70 shadow-sm">
            <p className="text-[10px] text-gray-800 font-semibold">BUG-014 Open</p>
            <p className="text-[10px] text-gray-600 mt-0.5">Booking schema mismatch pending fix</p>
          </div>
          <div className="p-2.5 bg-white/85 backdrop-blur-md rounded-lg border border-white/70 shadow-sm">
            <p className="text-[10px] text-gray-800 font-semibold">BUG-013 Open</p>
            <p className="text-[10px] text-gray-600 mt-0.5">Payment idempotency key missing</p>
          </div>
        </div>
      </InspectorSection>
      <InspectorSection title="Pending Approvals">
        <p className="text-xs text-gray-500 mb-2">QA gate must pass before Agent 4 can proceed.</p>
        <div className="flex flex-col gap-1.5">
          <Btn size="xs" variant="primary" onClick={() => onNavigate("agent3")}>
            Review QA
          </Btn>
          <Btn size="xs" onClick={() => onNavigate("agent4")}>
            Open DevOps
          </Btn>
        </div>
      </InspectorSection>
    </InspectorPanel>
  );
}
