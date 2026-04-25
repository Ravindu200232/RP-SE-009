import React from "react";
import { AF_DATA } from "../core/data";
import { Icon, Btn, Card, Tabs } from "../core/ui";

const ARCH_PATTERNS = [
  { id: "PAT-001", name: "Booking Platform Architecture", desc: "Modular FastAPI monolith with domain-split service modules. Auth, booking, and payment as separate routers sharing a single DB pool.", confidence: 96, uses: 3 },
  { id: "PAT-002", name: "Auth + Admin Pattern", desc: "JWT-based auth with role-based access control. Admin middleware applied at router level, not individual endpoints.", confidence: 94, uses: 5 },
  { id: "PAT-003", name: "Notification Service Pattern", desc: "Async notification dispatch via background tasks. Channel abstraction for email, SMS, and push with provider swap capability.", confidence: 91, uses: 4 },
  { id: "PAT-004", name: "Report Module Pattern", desc: "Nightly aggregation job populates report cache table. Read-heavy endpoints query cache rather than raw transactional data.", confidence: 89, uses: 2 },
];

const PROMPT_HISTORY = [
  { id: "PH-001", title: "Generate SRS from project idea", agent: "Agent 1", timestamp: "Today 10:01 AM", result: "SRS v1.2 generated - 14 requirements" },
  { id: "PH-002", title: "Extract ambiguities from requirements", agent: "Agent 1", timestamp: "Today 10:03 AM", result: "4 ambiguities detected" },
  { id: "PH-003", title: "Generate page scaffold from design preset", agent: "Agent 2", timestamp: "Today 10:45 AM", result: "10 pages generated" },
  { id: "PH-004", title: "Generate FastAPI service from SRS module", agent: "Agent 2", timestamp: "Today 11:00 AM", result: "6 services generated" },
  { id: "PH-005", title: "Run contract validation on API output", agent: "Agent 3", timestamp: "Today 11:30 AM", result: "3 contract violations found" },
  { id: "PH-006", title: "Generate Docker compose from service map", agent: "Agent 4", timestamp: "Today 11:55 AM", result: "docker-compose.yml generated" },
];

const AGENT_EVENTS = [
  { time: "12:01:22", agent: "Agent 3", type: "test_run", msg: "Integration test suite completed - 2 failures" },
  { time: "12:01:20", agent: "Agent 3", type: "bug_report", msg: "Bug reports BUG-013, BUG-014 generated" },
  { time: "11:55:10", agent: "Agent 4", type: "artifact_gen", msg: "docker-compose.yml generated successfully" },
  { time: "11:50:30", agent: "Agent 4", type: "artifact_gen", msg: "GitHub Actions workflow YAML generated" },
  { time: "11:30:00", agent: "Agent 2", type: "fix_loop", msg: "Fix iteration 1 applied - booking-service schema patch" },
  { time: "11:00:00", agent: "Agent 2", type: "build", msg: "6 backend services generated from SRS module map" },
  { time: "10:45:00", agent: "Agent 2", type: "build", msg: "10 frontend pages scaffolded from Enterprise Dashboard preset" },
  { time: "10:03:00", agent: "Agent 1", type: "analysis", msg: "Ambiguity detection complete - 4 issues found" },
  { time: "10:01:00", agent: "Agent 1", type: "analysis", msg: "SRS v1.2 generated from project intake" },
];

export function MemoryHeader({ onExport }) {
  return (
    <div className="px-5 pt-4 pb-3 border-b border-gray-200 flex-shrink-0">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
            <span>AgentForge</span>
            <Icon name="ChevronRight" size={10} />
            <span className="text-gray-500">Memory & Logs</span>
          </div>
          <h1 className="text-xl font-bold text-gray-800">Memory & Logs</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Review prior fixes, reusable patterns, prompt traces, execution history, and decision memory.
          </p>
        </div>
        <div className="flex gap-2 pt-1">
          <Btn icon="Search">Search Logs</Btn>
          <Btn icon="Download">Download Logs</Btn>
          <Btn icon="FileOutput" variant="primary" onClick={onExport}>Export Memory Report</Btn>
        </div>
      </div>
    </div>
  );
}

export function MemoryTabs({ tab, memoryCount, onChange }) {
  const tabs = [
    { id: "failures", label: "Failure Memory", count: memoryCount },
    { id: "patterns", label: "Architecture Patterns", count: ARCH_PATTERNS.length },
    { id: "prompts", label: "Prompt History", count: PROMPT_HISTORY.length },
    { id: "events", label: "Agent Events", count: AGENT_EVENTS.length },
    { id: "logs", label: "Execution Logs" },
  ];

  return <Tabs tabs={tabs} active={tab} onChange={onChange} className="px-5 flex-shrink-0" />;
}

export function FailureMemoryPane({ memoryPatterns }) {
  return (
    <div className="space-y-3 max-w-2xl">
      <p className="text-xs text-gray-400 mb-3">Failure patterns recorded from previous runs - reusable across similar project types.</p>
      {memoryPatterns.map((pattern) => (
        <Card key={pattern.id} className="p-4 hover:border-gray-300 transition-all bg-white border-gray-200">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-[10px] text-gray-400">{pattern.id}</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#53C062] text-white">Failure Pattern</span>
                <span className="text-[10px] text-[#53C062] font-medium">{pattern.confidence}% confidence</span>
              </div>
              <p className="text-xs font-semibold text-gray-800 mb-1">{pattern.issue}</p>
              <p className="text-xs text-gray-600">Fix applied: {pattern.fix}</p>
              <div className="flex gap-4 mt-2 text-[10px] text-gray-400">
                <span>Project type: {pattern.projectType}</span>
                <span>Outcome: {pattern.outcome}</span>
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <button className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-[#53C062] text-white hover:bg-[#45a854] transition-all">
                <Icon name="RefreshCw" size={11} />
                Reuse
              </button>
              <Btn size="xs" icon="FileText">View Full</Btn>
              <Btn size="xs" icon="Pin">Pin</Btn>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function ArchitecturePatternsPane() {
  return (
    <div className="grid grid-cols-2 gap-3 max-w-3xl">
      {ARCH_PATTERNS.map((pattern) => (
        <Card key={pattern.id} className="p-4 hover:border-gray-300 transition-all bg-white border-gray-200">
          <div className="flex items-start justify-between mb-2">
            <p className="text-xs font-semibold text-gray-800">{pattern.name}</p>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#1f6feb] text-white">
              {pattern.confidence}%
            </span>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed mb-3">{pattern.desc}</p>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-gray-400">Used {pattern.uses}x across projects</span>
            <div className="flex gap-1">
              <Btn size="xs" icon="Copy">Apply</Btn>
              <Btn size="xs" icon="Eye">View</Btn>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function PromptHistoryPane() {
  const agentColor = (agent) =>
    ({ "Agent 1": "text-[#1f6feb]", "Agent 2": "text-[#1f6feb]", "Agent 3": "text-[#1f6feb]", "Agent 4": "text-[#53C062]" }[agent] || "text-gray-500");

  return (
    <div className="space-y-2 max-w-2xl">
      {PROMPT_HISTORY.map((prompt) => (
        <Card key={prompt.id} className="p-3 hover:border-gray-300 transition-all bg-white border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-medium ${agentColor(prompt.agent)}`}>{prompt.agent}</span>
                <span className="text-[10px] text-gray-400">{prompt.timestamp}</span>
              </div>
              <p className="text-xs text-gray-800 truncate">{prompt.title}</p>
              <p className="text-[10px] text-gray-400 mt-0.5">Result: {prompt.result}</p>
            </div>
            <div className="flex gap-1 ml-3">
              <Btn size="xs" icon="Eye">View</Btn>
              <Btn size="xs" icon="Copy">Copy</Btn>
              <Btn size="xs" icon="Play">Re-run</Btn>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function AgentEventsPane() {
  const agentColor = (agent) =>
    ({ "Agent 1": "text-[#1f6feb]", "Agent 2": "text-[#1f6feb]", "Agent 3": "text-[#1f6feb]", "Agent 4": "text-[#53C062]" }[agent] || "text-gray-500");
  const agentBg = (agent) =>
    ({ "Agent 1": "bg-[#1f6feb]/15", "Agent 2": "bg-[#1f6feb]/15", "Agent 3": "bg-[#1f6feb]/15", "Agent 4": "bg-[#53C062]/15" }[agent] || "bg-gray-100");

  return (
    <div className="space-y-1.5 max-w-2xl">
      {AGENT_EVENTS.map((event) => (
        <div key={`${event.time}-${event.msg}`} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-gray-50 transition-colors">
          <span className="font-mono text-[10px] text-gray-400 w-16 flex-shrink-0 mt-0.5">{event.time}</span>
          <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${agentBg(event.agent)}`}>
            <Icon
              name={event.type === "analysis" ? "Brain" : event.type === "build" ? "Code2" : event.type === "test_run" ? "FlaskConical" : event.type === "artifact_gen" ? "Package" : event.type === "bug_report" ? "Bug" : "RefreshCw"}
              size={11}
              className={agentColor(event.agent)}
            />
          </div>
          <div className="flex-1">
            <span className={`text-xs font-medium ${agentColor(event.agent)}`}>{event.agent}</span>
            <span className="text-xs text-gray-600 ml-2">{event.msg}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ExecutionLogsPane() {
  return (
    <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 font-mono">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] text-gray-400">Execution log stream - StayEase - BLD-0041</span>
        <div className="flex gap-2">
          <Btn size="xs" icon="Search">Search</Btn>
          <Btn size="xs" icon="Download">Download</Btn>
          <Btn size="xs" icon="Trash2">Clear View</Btn>
        </div>
      </div>
      {AF_DATA.logLines.map((line, index) => {
        const colorClass =
          line.includes("x") ? "text-red-500" :
          line.includes("passed") ? "text-[#53C062]" :
          line.includes("[Agent4]") ? "text-[#53C062]" :
          line.includes("[Agent") ? "text-[#1f6feb]" :
          "text-gray-500";
        return <p key={`${line}-${index}`} className={`text-[11px] leading-6 ${colorClass}`}>{line}</p>;
      })}
    </div>
  );
}
