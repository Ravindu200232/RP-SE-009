"use client";

import React, { useEffect, useState } from "react";
import {
  Btn,
  Card,
  CodeBlock,
  EmptyState,
  InspectorPanel,
  InspectorRow,
  InspectorSection,
  ProgressBar,
  Tabs,
} from "../core/ui";
import { fetchAgent1Session, generateAgent1Srs, getAgent1ArtifactUrl } from "../core/agent1-api";
import { loadAgent1Session, saveAgent1Session } from "../core/agent1-session";

const TABS = [
  { id: "srs", label: "SRS Document" },
  { id: "requirements", label: "Functional Req." },
  { id: "interview", label: "Interview Q&A" },
  { id: "json", label: "JSON Output" },
  { id: "issues", label: "Ambiguities" },
  { id: "risk", label: "Risk & Stack" },
];

function listText(items, formatter) {
  return (items || []).map(formatter).filter(Boolean).join("\n");
}

function hasAnswerValue(value) {
  return Array.isArray(value) ? value.length > 0 : Boolean(String(value || "").trim());
}

function answerText(value) {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return String(value || "").trim();
}

function buildDocumentSections(srs) {
  if (!srs?.sections) {
    return [];
  }

  return [
    { title: "1. Purpose", body: srs.sections.introduction?.purpose || "" },
    { title: "2. Product Scope", body: srs.sections.introduction?.product_scope?.summary || "" },
    {
      title: "3. Business Objectives",
      body: listText(srs.sections.introduction?.product_scope?.business_objectives || [], (item) => `- ${item}`),
    },
    {
      title: "4. Product Functions",
      body: listText(
        srs.sections.overall_description?.product_functions || [],
        (item) => `- ${item.name}: ${item.description}`
      ),
    },
    {
      title: "5. User Classes",
      body: listText(
        srs.sections.overall_description?.user_classes_and_characteristics || [],
        (item) => `- ${item.user_class_name}: ${item.description}`
      ),
    },
    {
      title: "6. Interfaces",
      body: [
        listText(
          srs.sections.external_interface_requirements?.user_interfaces || [],
          (item) => `- User interface ${item.name}: ${item.description}`
        ),
        listText(
          srs.sections.external_interface_requirements?.software_interfaces || [],
          (item) => `- Software interface ${item.component_name}: ${item.description}`
        ),
        listText(
          srs.sections.external_interface_requirements?.communications_interfaces || [],
          (item) => `- Communication ${item.name}: ${item.description}`
        ),
      ]
        .filter(Boolean)
        .join("\n"),
    },
    {
      title: "7. Quality, Security, and Data",
      body: [
        listText(
          srs.sections.other_nonfunctional_requirements?.performance_requirements || [],
          (item) => `- Performance: ${item.description}`
        ),
        listText(
          srs.sections.other_nonfunctional_requirements?.security_requirements || [],
          (item) => `- Security: ${item.description}`
        ),
        listText(
          srs.sections.other_requirements?.database_requirements || [],
          (item) => `- Data: ${item.description}`
        ),
        listText(
          srs.sections.other_requirements?.legal_requirements || [],
          (item) => `- Legal: ${item.description}`
        ),
      ]
        .filter(Boolean)
        .join("\n"),
    },
    {
      title: "8. Services",
      body: listText(srs.services || [], (service) => `- ${service.service_name}: ${service.summary}`),
    },
  ].filter((section) => section.body);
}

function flattenRequirements(srs) {
  const featureRequirements = (srs?.sections?.system_features || []).flatMap((feature) =>
    (feature.functional_requirements || []).map((requirement) => ({
      id: requirement.requirement_id,
      title: requirement.title,
      text: requirement.description,
      priority: requirement.priority || "High",
      type: "Functional",
    }))
  );

  const performanceRequirements = (srs?.sections?.other_nonfunctional_requirements?.performance_requirements || []).map(
    (requirement) => ({
      id: requirement.requirement_id,
      title: "Performance",
      text: requirement.description,
      priority: "High",
      type: "Non-Functional",
    })
  );

  const securityRequirements = (srs?.sections?.other_nonfunctional_requirements?.security_requirements || []).map(
    (requirement) => ({
      id: requirement.requirement_id,
      title: "Security",
      text: requirement.description,
      priority: "High",
      type: "Security",
    })
  );

  const dataRequirements = (srs?.sections?.other_requirements?.database_requirements || []).map((requirement) => ({
    id: requirement.requirement_id,
    title: "Database",
    text: requirement.description,
    priority: "Medium",
    type: "Data",
  }));

  return [...featureRequirements, ...performanceRequirements, ...securityRequirements, ...dataRequirements];
}

function buildInterviewItems(session, srs) {
  const workspace = srs?.analyst_workspace;
  if (workspace?.interview_questions?.length) {
    return workspace.interview_questions;
  }

  const questions = session?.question_plan?.questions || [];
  const answers = session?.answers || {};
  return questions.map((question) => ({
    key: question.key,
    section: question.section,
    question: question.question,
    answered: hasAnswerValue(answers[question.key]),
    answer_text: answerText(answers[question.key]),
  }));
}

function buildIssueItems(session, srs) {
  const validatorIssues = (session?.validation?.issues || []).map((issue, index) => ({
    id: `validator-${index}`,
    source: "Validator",
    title: issue.path,
    text: issue.message,
  }));
  const tbdIssues = (srs?.appendices?.to_be_determined_list || []).map((item) => ({
    id: item.tbd_id,
    source: "Template Gap",
    title: item.tbd_id,
    text: item.description,
  }));

  return [...validatorIssues, ...tbdIssues];
}

export default function Agent1View({ onNavigate, onToast }) {
  const [tab, setTab] = useState("srs");
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    async function loadSession() {
      const saved = loadAgent1Session();
      if (!saved?.session_id) {
        setLoading(false);
        return;
      }

      try {
        const fresh = await fetchAgent1Session(saved.session_id);
        saveAgent1Session(fresh);
        setSession(fresh);
      } catch {
        setSession(saved);
      } finally {
        setLoading(false);
      }
    }

    loadSession();
  }, []);

  async function regenerate() {
    if (!session?.session_id) {
      return;
    }

    setRegenerating(true);
    try {
      const result = await generateAgent1Srs(session.session_id);
      saveAgent1Session(result.session);
      setSession(result.session);
      onToast("SRS rebuilt successfully.", "success");
    } catch (error) {
      onToast(error.message, "error");
    } finally {
      setRegenerating(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-sm text-gray-500">Loading Agent 1 session...</div>;
  }

  if (!session?.session_id) {
    return (
      <div className="h-full p-6">
        <Card className="p-0">
          <EmptyState
            icon="Inbox"
            title="No Agent 1 session found"
            subtitle="Start a new project, answer the guided questions, and the generated SRS will appear here."
            action={
              <Btn icon="Plus" variant="primary" onClick={() => onNavigate("new-project")}>
                New Project
              </Btn>
            }
          />
        </Card>
      </div>
    );
  }

  const srs = session.final_srs || session.draft_srs;
  const workspace = srs?.analyst_workspace || {};
  const documentSections = buildDocumentSections(srs);
  const requirements = flattenRequirements(srs);
  const interviewItems = buildInterviewItems(session, srs);
  const issueItems = buildIssueItems(session, srs);
  const stack = session.recommended_stack || srs?.generated_stack_recommendation || {};
  const progress = session.validation?.completeness_score || workspace.coverage?.completion_percent || 0;
  const openItems = workspace.open_items || interviewItems.filter((item) => !item.answered);

  const tabViews = {
    srs: (
      <div className="space-y-4">
        {documentSections.map((section) => (
          <Card key={section.title} className="p-4">
            <p className="mb-2 text-xs font-semibold text-gray-900">{section.title}</p>
            <p className="whitespace-pre-line text-xs leading-relaxed text-gray-600">{section.body}</p>
          </Card>
        ))}
      </div>
    ),
    requirements: (
      <div className="space-y-3">
        {requirements.map((requirement) => (
          <Card key={requirement.id} className="p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-semibold text-[#1f6feb]">
                {requirement.id}
              </span>
              <span className="text-[10px] text-gray-400">
                {requirement.type} | {requirement.priority}
              </span>
            </div>
            <p className="text-xs font-semibold text-gray-900">{requirement.title}</p>
            <p className="mt-1 text-xs leading-relaxed text-gray-600">{requirement.text}</p>
          </Card>
        ))}
      </div>
    ),
    interview: (
      <div className="space-y-4">
        <Card className="p-4">
          <p className="mb-2 text-xs font-semibold text-gray-900">Analyst Summary</p>
          <p className="text-xs leading-relaxed text-gray-600">
            {workspace.analysis_summary || session.analysis_summary || "No analyst summary is available yet."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-gray-50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-gray-400">Questions</p>
              <p className="mt-2 text-lg font-semibold text-gray-900">
                {workspace.coverage?.total_questions || interviewItems.length}
              </p>
            </div>
            <div className="rounded-xl bg-gray-50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-gray-400">Answered</p>
              <p className="mt-2 text-lg font-semibold text-gray-900">
                {workspace.coverage?.answered_questions || interviewItems.filter((item) => item.answered).length}
              </p>
            </div>
            <div className="rounded-xl bg-gray-50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-gray-400">Open</p>
              <p className="mt-2 text-lg font-semibold text-gray-900">
                {workspace.coverage?.open_questions || openItems.length}
              </p>
            </div>
          </div>
        </Card>

        {interviewItems.map((item, index) => (
          <Card key={item.key || index} className="p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="rounded-full bg-gray-100 px-2 py-1 text-[10px] font-semibold text-gray-500">
                {(item.section || "basics").replace(/_/g, " ")}
              </span>
              <span
                className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                  item.answered ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"
                }`}
              >
                {item.answered ? "Answered" : "Open"}
              </span>
            </div>
            <p className="text-xs font-semibold text-gray-900">{item.question}</p>
            <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-gray-600">
              {item.answer_text || "Waiting for answer."}
            </p>
          </Card>
        ))}
      </div>
    ),
    json: <CodeBlock code={JSON.stringify(srs || {}, null, 2)} lang="json" />,
    issues: (
      <div className="space-y-3">
        {issueItems.length ? (
          issueItems.map((issue) => (
            <Card key={issue.id} className="p-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="text-xs font-semibold text-gray-900">{issue.title}</p>
                <span className="rounded-full bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-700">
                  {issue.source}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-gray-600">{issue.text}</p>
            </Card>
          ))
        ) : (
          <Card className="p-4">
            <p className="text-xs text-gray-600">No open ambiguities were returned by the validator.</p>
          </Card>
        )}
      </div>
    ),
    risk: (
      <div className="space-y-4">
        <Card className="p-4">
          <p className="mb-3 text-xs font-semibold text-gray-900">Recommended Stack</p>
          <div className="space-y-2 text-xs text-gray-600">
            {Object.entries(stack).map(([key, value]) => (
              <p key={key}>
                <span className="font-semibold text-gray-900">{key.replace(/_/g, " ")}:</span> {value}
              </p>
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <p className="mb-3 text-xs font-semibold text-gray-900">Current Build Signals</p>
          <div className="space-y-2 text-xs text-gray-600">
            <p>
              <span className="font-semibold text-gray-900">Template standard:</span>{" "}
              {workspace.template_standard || srs?.standard || "IEEE SRS"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Document type:</span>{" "}
              {workspace.template_document_type || srs?.document_type || "Software Requirements Specification"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Expected scale:</span>{" "}
              {workspace.expected_scale || "Not specified"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Integrations:</span>{" "}
              {(workspace.integrations || []).join(", ") || "None listed"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Reports and notifications:</span>{" "}
              {(workspace.reports_and_notifications || []).join(", ") || "None listed"}
            </p>
            <p>
              <span className="font-semibold text-gray-900">Compliance focus:</span>{" "}
              {(workspace.compliance_focus || []).join(", ") || "None listed"}
            </p>
          </div>
        </Card>

        <Card className="p-4">
          <p className="mb-3 text-xs font-semibold text-gray-900">Service Breakdown</p>
          <div className="space-y-2 text-xs text-gray-600">
            {(srs?.services || []).map((service) => (
              <p key={service.service_name}>
                <span className="font-semibold text-gray-900">{service.service_name}</span>: {service.summary}
              </p>
            ))}
          </div>
        </Card>
      </div>
    ),
  };

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex flex-1 flex-col overflow-hidden bg-white">
        <div className="flex items-start justify-between border-b border-gray-200 px-5 pb-3 pt-5">
          <div>
            <p className="text-xs text-gray-400">AgentForge Studio / Agent 1</p>
            <h1 className="text-xl font-bold text-gray-900">
              {srs?.metadata?.project_name || session.project_name || "Agent 1 Review"}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Review the template-based SRS, the interview answers, the structured JSON, and the export artifacts.
            </p>
          </div>
          <div className="flex gap-2">
            <Btn icon="RefreshCw" onClick={regenerate} disabled={regenerating}>
              {regenerating ? "Rebuilding..." : "Rebuild SRS"}
            </Btn>
            <Btn
              icon="Download"
              onClick={() => window.open(getAgent1ArtifactUrl(session.session_id, "srs.json"), "_blank")}
            >
              Export JSON
            </Btn>
            <Btn
              icon="Download"
              variant="primary"
              onClick={() => window.open(getAgent1ArtifactUrl(session.session_id, "srs.pdf"), "_blank")}
            >
              Export PDF
            </Btn>
          </div>
        </div>

        <Tabs tabs={TABS} active={tab} onChange={setTab} className="px-5" />
        <div className="flex-1 overflow-y-auto p-5">{tabViews[tab]}</div>
      </div>

      <InspectorPanel title="Analysis Inspector">
        <InspectorSection title="Readiness">
          <InspectorRow label="Status" value={session.validation?.status || session.status} />
          <InspectorRow label="Completeness" value={`${progress}%`} />
          <InspectorRow label="Standard" value={workspace.template_standard || srs?.standard || "IEEE SRS"} />
          <ProgressBar value={progress} className="mt-2" />
        </InspectorSection>
        <InspectorSection title="Interview Coverage">
          <InspectorRow label="Questions" value={`${workspace.coverage?.total_questions || interviewItems.length}`} />
          <InspectorRow
            label="Answered"
            value={`${workspace.coverage?.answered_questions || interviewItems.filter((item) => item.answered).length}`}
          />
          <InspectorRow label="Open Items" value={`${workspace.coverage?.open_questions || openItems.length}`} />
        </InspectorSection>
        <InspectorSection title="Payload">
          <InspectorRow label="Sections" value={`${Object.keys(srs?.sections || {}).length}`} />
          <InspectorRow label="Requirements" value={`${requirements.length}`} />
          <InspectorRow label="Services" value={`${srs?.services?.length || 0}`} />
        </InspectorSection>
        <InspectorSection title="Artifacts">
          <InspectorRow label="JSON" value={session.artifacts?.json ? "Ready" : "Pending"} />
          <InspectorRow label="PDF" value={session.artifacts?.pdf ? "Ready" : "Pending"} />
        </InspectorSection>
        <InspectorSection title="Navigation">
          <div className="flex flex-col gap-2">
            <Btn size="xs" variant="primary" onClick={() => onNavigate("new-project")}>
              Back to Intake
            </Btn>
            <Btn size="xs" onClick={() => onNavigate("design-selector")}>
              Design Selector
            </Btn>
          </div>
        </InspectorSection>
      </InspectorPanel>
    </div>
  );
}
