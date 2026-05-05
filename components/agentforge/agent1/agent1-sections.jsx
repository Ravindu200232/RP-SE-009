import React from "react";
import {
  Icon,
  Btn,
  Card,
  Tabs,
  CodeBlock,
  InspectorPanel,
  InspectorSection,
  InspectorRow,
  ProgressBar,
} from "../core/ui";

const SRS_SECTIONS = [
  {
    id: "problem",
    title: "1. Problem Statement",
    content:
      "Hotel guests face difficulty discovering, comparing, and booking rooms online without an integrated platform. Property managers lack real-time visibility into occupancy and revenue. StayEase solves this by providing a unified booking, management, and analytics platform for both guests and hotel operators.",
  },
  {
    id: "background",
    title: "2. Background & Context",
    content:
      "The hospitality industry increasingly relies on digital booking channels. Existing solutions are fragmented or expensive. StayEase is designed as a modern, API-first SaaS platform built on FastAPI and PostgreSQL with a React dashboard frontend.",
  },
  {
    id: "stakeholders",
    title: "3. Stakeholders",
    content:
      "- Guest / End-user: Searches and books rooms, manages reservations\n- Hotel Admin: Manages inventory, pricing, staff, and reports\n- System Administrator: Manages platform configuration and integrations\n- Payment Provider: Stripe integration for secure transactions",
  },
  {
    id: "functional",
    title: "4. Functional Requirements",
    content:
      "REQ-001 through REQ-008 cover room search, secure checkout, email and SMS notifications, admin inventory management, multi-language support, and monthly reporting. See the Functional Requirements tab for the full list.",
  },
  {
    id: "nfr",
    title: "5. Non-Functional Requirements",
    content:
      "Performance: < 2s page load under normal load. Availability: 99.5% uptime SLA. Security: PCI-DSS for payment flows, GDPR compliance for EU users. Scalability: Horizontal scaling via containerized microservices.",
  },
  {
    id: "stories",
    title: "6. User Stories",
    content:
      "US-01: As a guest, I want to search rooms by date and type so I can find the best option.\nUS-02: As a guest, I want to pay securely online so I can complete my booking without friction.\nUS-03: As an admin, I want to view occupancy dashboards so I can make pricing decisions.",
  },
  {
    id: "arch",
    title: "7. Recommended Architecture",
    content:
      "Modular monolith transitioning to microservices. FastAPI backend with domain-separated service modules. PostgreSQL for transactional data. React frontend with Tailwind. JWT + OAuth2 authentication. Docker containerization with AWS ECS deployment.",
  },
];

const AMBIGUITIES = [
  {
    id: "AMB-01",
    text: '"Fast loading" is vague',
    suggestion: "Define measurable threshold: < 2 seconds at P95 under 500 concurrent users",
    status: "open",
  },
  {
    id: "AMB-02",
    text: '"Easy to use" needs measurable usability target',
    suggestion: "Add SUS score target (>= 75) or task completion rate (>= 90%) in NFR section",
    status: "open",
  },
  {
    id: "AMB-03",
    text: '"Secure payments" needs specification',
    suggestion: "Specify PCI-DSS Level 1 compliance and Stripe as payment processor",
    status: "resolved",
  },
  {
    id: "AMB-04",
    text: '"Multi-language" scope is unclear',
    suggestion: "Confirm languages: English (primary), Arabic (RTL support needed), French",
    status: "open",
  },
];

const JSON_OUTPUT = `{
  "metadata": {
    "project": "StayEase Hotel Booking System",
    "version": "1.2",
    "domain": "hospitality",
    "agent": "Agent 1",
    "generatedAt": "2025-04-23T12:01:00Z"
  },
  "modules": [
    "auth",
    "room-catalog",
    "booking",
    "payment",
    "notification",
    "reporting",
    "admin"
  ],
  "stakeholders": ["guest", "hotel-admin", "system-admin"],
  "dataEntities": [
    "User",
    "Role",
    "Room",
    "RoomType",
    "Booking",
    "Payment",
    "Notification",
    "Report"
  ],
  "apis": {
    "auth": ["POST /auth/login", "POST /auth/register", "POST /auth/refresh"],
    "rooms": ["GET /rooms", "GET /rooms/:id", "POST /rooms"],
    "bookings": ["POST /bookings", "GET /bookings/:id", "PATCH /bookings/:id/cancel"],
    "payments": ["POST /payments/checkout", "POST /payments/webhook"]
  },
  "constraints": {
    "performance": "p95 < 2000ms",
    "compliance": ["PCI-DSS", "GDPR"],
    "auth": "JWT + OAuth2"
  }
}`;

export const AGENT1_TABS = [
  { id: "srs", label: "SRS Document" },
  { id: "functional", label: "Functional Req." },
  { id: "json", label: "JSON Output" },
  { id: "diagrams", label: "Diagrams" },
  { id: "ambiguities", label: "Ambiguities", count: AMBIGUITIES.filter((item) => item.status === "open").length },
  { id: "risk", label: "Risk & Priority" },
];

export function Agent1Header({ running, onRunAnalysis, onApprove, onNavigate }) {
  return (
    <div className="flex items-start justify-between px-5 pt-5 pb-3 border-b border-gray-200 flex-shrink-0">
      <div>
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
          <span>AgentForge Studio</span>
          <Icon name="ChevronRight" size={10} />
          <span className="text-gray-500">Agent 1 - Analyzer</span>
        </div>
        <h1 className="text-xl font-bold text-gray-800">Agent 1 - Requirement Analyzer</h1>
        <p className="text-sm text-gray-500 mt-1">
          Convert raw software ideas into SRS, diagrams, structured JSON, and requirement intelligence.
        </p>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <Btn
          icon={running ? "Loader2" : "Play"}
          onClick={onRunAnalysis}
          disabled={running}
          variant="primary"
        >
          {running ? "Analyzing..." : "Run Analysis"}
        </Btn>
        <Btn icon="RefreshCw">Re-Analyze</Btn>
        <Btn icon="CheckCircle2" className="bg-[#53C062] hover:bg-[#45a854] text-white" onClick={onApprove}>
          Approve Requirements
        </Btn>
        <Btn icon="Download">Export SRS</Btn>
        <Btn icon="ArrowRight" variant="primary" onClick={() => onNavigate("design-selector")}>
          Send to Design Selection
        </Btn>
      </div>
    </div>
  );
}

export function Agent1Tabs({ tab, onChange }) {
  return <Tabs tabs={AGENT1_TABS} active={tab} onChange={onChange} className="px-5 flex-shrink-0" />;
}

export function SrsDocumentTab() {
  return (
    <div className="max-w-3xl space-y-3">
      <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-xl border border-[#1f6feb]/20 mb-4">
        <Icon name="FileText" size={16} className="text-[#1f6feb]" />
        <div>
          <p className="text-xs font-semibold text-gray-800">SRS v1.2 - StayEase Hotel Booking System</p>
          <p className="text-xs text-gray-400">
            Generated by Agent 1 - 14 functional - 6 non-functional - 3 open ambiguities
          </p>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#53C062] text-white ml-auto">
          Approved
        </span>
      </div>
      {SRS_SECTIONS.map((section) => (
        <Card key={section.id} className="p-4 bg-white border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-800">{section.title}</p>
            <div className="flex gap-1.5">
              <Btn size="xs" icon="Edit2">
                Edit
              </Btn>
              <Btn size="xs" icon="CheckCircle2" className="bg-[#53C062] hover:bg-[#45a854] text-white">
                Approve
              </Btn>
              <Btn size="xs" icon="Lock">
                Lock
              </Btn>
            </div>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-line">{section.content}</p>
        </Card>
      ))}
    </div>
  );
}

export function FunctionalRequirementsTab({ requirements }) {
  return (
    <div className="space-y-2.5 max-w-3xl">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs text-gray-400">{requirements.length} requirements extracted</p>
        <div className="flex gap-2">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#1f6feb] text-white">
            {requirements.filter((item) => item.type === "Functional").length} Functional
          </span>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#1f6feb] text-white">
            {requirements.filter((item) => item.type === "Non-Functional").length} Non-Functional
          </span>
        </div>
      </div>
      {requirements.map((requirement) => (
        <Card key={requirement.id} className="p-4 hover:border-gray-300 transition-all bg-white border-gray-200">
          <div className="flex items-start gap-3">
            <span className="font-mono text-[10px] text-[#1f6feb] bg-blue-50 px-2 py-1 rounded flex-shrink-0 mt-0.5">
              {requirement.id}
            </span>
            <div className="flex-1">
              <p className="text-xs text-gray-800 leading-relaxed mb-2">{requirement.text}</p>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#1f6feb] text-white">
                  {requirement.type}
                </span>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${
                    requirement.priority === "Critical"
                      ? "bg-red-500 text-white"
                      : requirement.priority === "High"
                        ? "bg-amber-500 text-white"
                        : "bg-gray-500 text-white"
                  }`}
                >
                  {requirement.priority}
                </span>
                <span className="text-[10px] text-gray-400">
                  Confidence:{" "}
                  <span className={requirement.confidence >= 90 ? "text-[#53C062]" : "text-[#f0883e]"}>
                    {requirement.confidence}%
                  </span>
                </span>
                {requirement.deps > 0 && (
                  <span className="text-[10px] text-gray-400">
                    {requirement.deps} dep{requirement.deps > 1 ? "s" : ""}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <Btn size="xs" icon="Edit2">
                Edit
              </Btn>
              <Btn size="xs" icon="CheckCircle2" className="bg-[#53C062] hover:bg-[#45a854] text-white">
                Approve
              </Btn>
              <Btn size="xs" icon="AlertCircle" className="bg-amber-500 hover:bg-amber-600 text-white">
                Ambiguous
              </Btn>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function JsonOutputTab() {
  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500">Machine-readable structured output for downstream agent consumption.</p>
        <div className="flex gap-2">
          <Btn size="xs" icon="Copy">
            Copy JSON
          </Btn>
          <Btn size="xs" icon="Download">
            Download
          </Btn>
          <Btn size="xs" icon="ShieldCheck">
            Validate Schema
          </Btn>
        </div>
      </div>
      <CodeBlock code={JSON_OUTPUT} lang="json" />
    </div>
  );
}

export function DiagramsTab() {
  const diagrams = [
    "Use Case Diagram",
    "Architecture Overview",
    "Activity Flow",
    "Service Breakdown",
    "Entity Relationship Diagram",
  ];

  return (
    <div className="grid grid-cols-2 gap-4 max-w-3xl">
      {diagrams.map((diagram) => (
        <Card key={diagram} className="p-4 bg-white border-gray-200">
          <div className="aspect-video bg-gray-50 rounded-lg border border-gray-200 flex flex-col items-center justify-center mb-3">
            <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center mb-2">
              <Icon name="GitBranch" size={20} className="text-gray-400" />
            </div>
            <p className="text-[10px] font-mono text-gray-400">{diagram}</p>
          </div>
          <p className="text-xs font-medium text-gray-800 mb-2">{diagram}</p>
          <div className="flex gap-1">
            <Btn size="xs" icon="Maximize2">
              Fullscreen
            </Btn>
            <Btn size="xs" icon="Download">
              Download
            </Btn>
            <Btn size="xs" icon="RefreshCw">
              Regenerate
            </Btn>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function AmbiguitiesTab() {
  return (
    <div className="max-w-2xl space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <Icon name="AlertTriangle" size={14} className="text-amber-500" />
        <p className="text-xs text-gray-500">
          {AMBIGUITIES.filter((item) => item.status === "open").length} ambiguities detected requiring clarification before generation.
        </p>
      </div>
      {AMBIGUITIES.map((item) => (
        <Card
          key={item.id}
          className={`p-4 border-l-2 bg-white ${item.status === "open" ? "border-l-amber-500" : "border-l-[#53C062]"}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-[10px] text-gray-400">{item.id}</span>
                {item.status === "open" ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500 text-white">
                    Open
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#53C062] text-white">
                    Resolved
                  </span>
                )}
              </div>
              <p className="text-xs font-medium text-gray-800 mb-1">Warning: {item.text}</p>
              <p className="text-xs text-gray-600 leading-relaxed">Suggestion: {item.suggestion}</p>
            </div>
            {item.status === "open" && (
              <div className="flex flex-col gap-1">
                <Btn size="xs" icon="Sparkles" variant="primary">
                  Auto Clarify
                </Btn>
                <Btn size="xs" icon="MessageSquare">
                  Ask User
                </Btn>
                <Btn size="xs">Ignore</Btn>
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}

export function RiskTab() {
  const risks = [
    {
      req: "Payment Processing",
      risk: "High",
      reason: "PCI-DSS compliance complexity",
      mitigation: "Use Stripe-hosted checkout to reduce scope",
    },
    {
      req: "Multi-language RTL",
      risk: "Medium",
      reason: "Arabic requires full RTL layout support",
      mitigation: "Use i18next with CSS logical properties",
    },
    {
      req: "Real-time Availability",
      risk: "Medium",
      reason: "Race conditions on concurrent bookings",
      mitigation: "Implement optimistic locking on room availability",
    },
    {
      req: "Reporting & Analytics",
      risk: "Low",
      reason: "Data aggregation performance at scale",
      mitigation: "Pre-aggregate nightly report snapshots",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 max-w-3xl">
      {risks.map((risk) => (
        <Card key={risk.req} className="p-4 bg-white border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-800">{risk.req}</p>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                risk.risk === "High"
                  ? "bg-red-500 text-white"
                  : risk.risk === "Medium"
                    ? "bg-amber-500 text-white"
                    : "bg-[#53C062] text-white"
              }`}
            >
              {risk.risk} Risk
            </span>
          </div>
          <p className="text-xs text-gray-400 mb-1">Reason: {risk.reason}</p>
          <p className="text-xs text-gray-600">Mitigation: {risk.mitigation}</p>
        </Card>
      ))}
    </div>
  );
}

export function AnalysisInspector({ onApprove, onNavigate }) {
  return (
    <InspectorPanel title="Analysis Inspector">
      <InspectorSection title="Requirement Summary">
        <InspectorRow label="Total" value="14" />
        <InspectorRow label="Functional" value="8" />
        <InspectorRow label="Non-Functional" value="6" />
        <InspectorRow label="Approved" value="11" />
        <InspectorRow label="Ambiguous" value="3" />
      </InspectorSection>
      <InspectorSection title="Complexity Estimate">
        <InspectorRow label="Overall" value="Medium-High" />
        <InspectorRow label="Backend" value="High" />
        <InspectorRow label="Frontend" value="Medium" />
        <InspectorRow label="DevOps" value="Medium" />
        <ProgressBar value={68} color="amber" className="mt-2" />
      </InspectorSection>
      <InspectorSection title="Suggested Stack">
        <InspectorRow label="Frontend" value="React + Tailwind" />
        <InspectorRow label="Backend" value="FastAPI" />
        <InspectorRow label="Database" value="PostgreSQL" />
        <InspectorRow label="Auth" value="JWT + OAuth2" />
        <InspectorRow label="Deploy" value="AWS ECS" />
      </InspectorSection>
      <InspectorSection title="Detected Domain">
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#1f6feb] text-white">
          Hospitality SaaS
        </span>
        <p className="text-xs text-gray-500 mt-2">Similar to 2 patterns in memory.</p>
      </InspectorSection>
      <InspectorSection title="Actions">
        <div className="flex flex-col gap-2">
          <Btn
            size="xs"
            className="bg-[#53C062] hover:bg-[#45a854] text-white w-full justify-center"
            icon="CheckCircle2"
            onClick={onApprove}
          >
            Approve Agent 1
          </Btn>
          <Btn
            size="xs"
            variant="primary"
            icon="Palette"
            onClick={() => onNavigate("design-selector")}
            className="w-full justify-center"
          >
            Design Selector
          </Btn>
          <Btn
            size="xs"
            icon="ArrowLeft"
            onClick={() => onNavigate("new-project")}
            className="w-full justify-center"
          >
            Back to Intake
          </Btn>
        </div>
      </InspectorSection>
    </InspectorPanel>
  );
}
