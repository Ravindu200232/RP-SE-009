import React from "react";
import { Icon, Btn } from "../core/ui";

const HISTORY_PROJECTS = [
  {
    id: "proj-001",
    name: "StayEase Hotel Booking System",
    code: "STAY-001",
    domain: "Hospitality",
    type: "Full Stack SaaS",
    stage: "QA Testing",
    qaScore: 87,
    preset: "Enterprise Dashboard",
    stack: "FastAPI + PostgreSQL",
    status: "active",
    createdAt: "Apr 20, 2025",
    updatedAt: "12 min ago",
    versions: 3,
    builds: 5,
    agents: ["Agent 1", "Agent 2", "Agent 3"],
    desc: "Hotel booking platform with room search, booking management, payments, admin dashboard and reporting.",
  },
  {
    id: "proj-002",
    name: "MediTrack Clinic Management Platform",
    code: "MEDI-002",
    domain: "Healthcare",
    type: "Web Application",
    stage: "Agent 2 Building",
    qaScore: null,
    preset: "Healthcare Portal",
    stack: "NestJS + PostgreSQL",
    status: "active",
    createdAt: "Apr 18, 2025",
    updatedAt: "2 hrs ago",
    versions: 1,
    builds: 2,
    agents: ["Agent 1", "Agent 2"],
    desc: "Clinic management covering patient records, appointments, prescriptions, billing and staff management.",
  },
  {
    id: "proj-003",
    name: "LearnHub LMS Portal",
    code: "LEARN-003",
    domain: "Education",
    type: "Full Stack SaaS",
    stage: "Design Selection",
    qaScore: null,
    preset: "Education Portal",
    stack: "Node.js + MongoDB",
    status: "active",
    createdAt: "Apr 15, 2025",
    updatedAt: "1 day ago",
    versions: 0,
    builds: 0,
    agents: ["Agent 1"],
    desc: "Learning management system with course creation, enrollment, assessments, progress tracking and certificates.",
  },
  {
    id: "proj-004",
    name: "ShopStream E-commerce Platform",
    code: "SHOP-004",
    domain: "E-commerce",
    type: "Full Stack SaaS",
    stage: "Deployed",
    qaScore: 96,
    preset: "E-commerce Experience",
    stack: "Next.js + FastAPI",
    status: "released",
    createdAt: "Mar 10, 2025",
    updatedAt: "Apr 1, 2025",
    versions: 4,
    builds: 9,
    agents: ["Agent 1", "Agent 2", "Agent 3", "Agent 4"],
    desc: "Full-featured e-commerce platform with product catalog, cart, checkout, order tracking and seller dashboard.",
  },
  {
    id: "proj-005",
    name: "TechHire Recruitment Portal",
    code: "HIRE-005",
    domain: "HR / Recruitment",
    type: "Web Application",
    stage: "Deployed",
    qaScore: 91,
    preset: "SaaS Product",
    stack: "NestJS + PostgreSQL",
    status: "released",
    createdAt: "Feb 22, 2025",
    updatedAt: "Mar 15, 2025",
    versions: 3,
    builds: 7,
    agents: ["Agent 1", "Agent 2", "Agent 3", "Agent 4"],
    desc: "Recruitment platform with job listings, applicant tracking, interview scheduling and HR analytics.",
  },
  {
    id: "proj-006",
    name: "FinDash Analytics Dashboard",
    code: "FIN-006",
    domain: "Finance",
    type: "Admin System",
    stage: "Archived",
    qaScore: 78,
    preset: "Admin Portal",
    stack: "FastAPI + PostgreSQL",
    status: "archived",
    createdAt: "Jan 14, 2025",
    updatedAt: "Feb 5, 2025",
    versions: 2,
    builds: 4,
    agents: ["Agent 1", "Agent 2", "Agent 3"],
    desc: "Financial analytics dashboard for portfolio tracking, budget management and expense reporting.",
  },
];

const AGENT_COLORS = {
  "Agent 1": "bg-blue-100 text-blue-700",
  "Agent 2": "bg-violet-100 text-violet-700",
  "Agent 3": "bg-amber-100 text-amber-700",
  "Agent 4": "bg-green-100 text-green-700",
};

const STATUS_CONFIG = {
  active: { label: "Active", bg: "bg-blue-50 text-blue-700 border-blue-200" },
  released: { label: "Released", bg: "bg-green-50 text-green-700 border-green-200" },
  archived: { label: "Archived", bg: "bg-gray-100 text-gray-500 border-gray-200" },
};

export function getFilteredProjects(filter, search) {
  return HISTORY_PROJECTS.filter((project) => {
    if (filter === "active" && project.status !== "active") return false;
    if (filter === "released" && project.status !== "released") return false;
    if (filter === "archived" && project.status !== "archived") return false;
    if (search && !project.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
}

export function ProjectHistoryHeader({ onNewProject }) {
  return (
    <div className="flex items-start justify-between mb-5">
      <div>
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
          <span>AgentForge</span>
          <Icon name="ChevronRight" size={10} />
          <span>Project History</span>
        </div>
        <h1 className="text-xl font-bold text-gray-900">Project History</h1>
        <p className="text-sm text-gray-500 mt-1">
          All projects built with AgentForge Studio - browse, resume, or archive.
        </p>
      </div>
      <Btn icon="Plus" variant="primary" onClick={onNewProject}>New Project</Btn>
    </div>
  );
}

export function ProjectStatsGrid() {
  const stats = [
    { label: "Total Projects", value: HISTORY_PROJECTS.length, icon: "FolderOpen", color: "blue" },
    { label: "Active Builds", value: HISTORY_PROJECTS.filter((item) => item.status === "active").length, icon: "Code2", color: "violet" },
    { label: "Live Releases", value: HISTORY_PROJECTS.filter((item) => item.status === "released").length, icon: "Globe", color: "green" },
    {
      label: "Avg QA Score",
      value: `${Math.round(HISTORY_PROJECTS.filter((item) => item.qaScore).reduce((sum, item) => sum + item.qaScore, 0) / HISTORY_PROJECTS.filter((item) => item.qaScore).length)}%`,
      icon: "Star",
      color: "amber",
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 mb-5">
      {stats.map((stat) => (
        <div key={stat.label} className="bg-white rounded-xl border border-gray-200 p-4 hover:border-gray-300 transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500">{stat.label}</span>
            <Icon name={stat.icon} size={14} className={stat.color === "blue" ? "text-blue-400" : stat.color === "violet" ? "text-violet-400" : stat.color === "green" ? "text-green-400" : "text-amber-400"} />
          </div>
          <p className={`text-2xl font-bold ${stat.color === "blue" ? "text-blue-600" : stat.color === "violet" ? "text-violet-600" : stat.color === "green" ? "text-green-600" : "text-amber-600"}`}>
            {stat.value}
          </p>
        </div>
      ))}
    </div>
  );
}

export function ProjectHistoryFilters({ search, filter, onSearchChange, onFilterChange }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="relative flex-1 max-w-xs">
        <Icon name="Search" size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search projects..." className="w-full pl-8 pr-3 py-2 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400" />
      </div>
      <div className="flex gap-1">
        {["all", "active", "released", "archived"].map((item) => (
          <button
            key={item}
            onClick={() => onFilterChange(item)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${filter === item ? "bg-blue-600 text-white" : "bg-white text-gray-500 border border-gray-200 hover:border-gray-300"}`}
          >
            {item}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ProjectCards({ projects, selectedId, onSelectProject, onNavigate, onArchive }) {
  return (
    <div className="space-y-3">
      {projects.map((project) => {
        const selected = selectedId === project.id;
        const status = STATUS_CONFIG[project.status];

        return (
          <div
            key={project.id}
            onClick={() => onSelectProject(selected ? null : project.id)}
            className={`bg-white rounded-xl border-2 p-4 cursor-pointer transition-all hover:border-blue-300 hover:shadow-sm ${selected ? "border-blue-500" : "border-gray-200"}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${status.bg}`}>{status.label}</span>
                  <span className="font-mono text-[10px] text-gray-400">{project.code}</span>
                  <span className="text-[10px] text-gray-400">{project.domain}</span>
                </div>
                <p className="text-sm font-bold text-gray-900 mb-1">{project.name}</p>
                <p className="text-xs text-gray-500 mb-2 leading-relaxed">{project.desc}</p>
                <div className="flex items-center gap-4 text-[10px] text-gray-400">
                  <span>Stage: <span className="text-gray-600 font-medium">{project.stage}</span></span>
                  <span>Preset: <span className="text-gray-600">{project.preset}</span></span>
                  <span>Stack: <span className="text-gray-600">{project.stack}</span></span>
                  <span>Updated: <span className="text-gray-600">{project.updatedAt}</span></span>
                </div>
              </div>

              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                {project.qaScore && (
                  <div className="text-right">
                    <p className="text-[10px] text-gray-400">QA Score</p>
                    <p className={`text-lg font-bold ${project.qaScore >= 90 ? "text-green-600" : "text-amber-600"}`}>{project.qaScore}%</p>
                  </div>
                )}
                <div className="flex gap-1">
                  {project.agents.map((agent) => (
                    <span key={agent} className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${AGENT_COLORS[agent]}`}>{agent.replace("Agent ", "A")}</span>
                  ))}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                  <span>{project.versions} versions</span>
                  <span>-</span>
                  <span>{project.builds} builds</span>
                </div>
              </div>
            </div>

            {selected && (
              <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2" style={{ animation: "fadeIn 0.2s ease forwards" }}>
                <Btn size="xs" icon="Play" variant="primary" onClick={(event) => {
                  event.stopPropagation();
                  onNavigate(project.status === "active" ? "agent2" : "dashboard");
                }}>
                  {project.status === "active" ? "Resume Build" : "View Project"}
                </Btn>
                <Btn size="xs" icon="Archive" onClick={(event) => {
                  event.stopPropagation();
                  onNavigate("artifacts");
                }}>
                  Artifacts
                </Btn>
                <Btn size="xs" icon="GitBranch" onClick={(event) => {
                  event.stopPropagation();
                  onNavigate("versions");
                }}>
                  Versions
                </Btn>
                {project.status === "released" && (
                  <Btn size="xs" icon="Globe" variant="success" onClick={(event) => {
                    event.stopPropagation();
                    onArchive(`Opening ${project.name} live deployment...`);
                  }}>
                    View Live
                  </Btn>
                )}
                <Btn size="xs" icon="Trash2" variant="danger" onClick={(event) => {
                  event.stopPropagation();
                  onArchive("Project archived.");
                }}>
                  Archive
                </Btn>
                <span className="ml-auto text-[10px] text-gray-400">Created {project.createdAt}</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
