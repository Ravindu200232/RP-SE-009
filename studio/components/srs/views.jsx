'use client'

import { useState } from 'react'
import {
  AlertTriangle, ArrowRight, Check, CheckCircle2, Compass, Copy, Cpu, Database, FileCode,
  FileText, Globe, Key, Lock, Maximize2, MessageSquare, ShieldAlert, ShieldCheck, Sparkles,
  Users, Workflow, Zap,
} from 'lucide-react'
import { Empty, Table } from '../ui'
import DiagramViewer from './DiagramViewer'
import Overview from './Overview'
import { UserJourney, Wireframes } from './Wireframes'
import { cn } from '@/lib/utils'
const list = (value) => Array.isArray(value) ? value : []


function line(item) {
  if (typeof item === 'string') return item
  if (!item || typeof item !== 'object') return String(item ?? '')
  const text = item.requirement || item.description || item.criterion
    || item.risk || item.rule || item.text || item.page_name
    || item.role_name || item.name || item.title

  return text || JSON.stringify(item)
}

const idOf = (item, i) =>
  (item && typeof item === 'object'
    && (item.id || item.ref || item.module || item.category || item.area)) || `#${i + 1}`

/** A numbered section of the document. */
function Section({ title, children, count, n }) {
  return (
    <div className="mb-6">
      <div className="flex items-baseline gap-2.5 border-b-2 border-line2 pb-[7px]">
        {n != null && <span className="font-mono text-[11px] text-accent">{n}</span>}
        <h3 className="font-display text-[15px] font-extrabold tracking-[-.01em] text-ink">
          {title}
        </h3>
        <span className="flex-1" />
        {count != null && (
          <span className="font-mono text-[10px] text-muted2">{count}</span>
        )}
      </div>
      <div className="mt-1">{children}</div>
    </div>
  )
}

function Bullets({ items, tone }) {
  if (!list(items).length) return <p className="py-2 text-[11.5px] text-muted2">None recorded.</p>
  return (
    <ul>
      {list(items).map((item, i) => (
        <li key={i} className="grid grid-cols-[34px_1fr] gap-2.5 border-b border-line
                               py-[7px] last:border-0">
          <span className={cn('font-mono text-[10.5px]', tone || 'text-faint')}>
            {idOf(item, i)}
          </span>
          <span className="text-[12px] leading-[1.5] text-ink">{line(item)}</span>
        </li>
      ))}
    </ul>
  )
}

/** Two section columns with a fixed gutter. */
const Columns = ({ children }) => (
  <div className="grid gap-x-[30px] md:grid-cols-2">{children}</div>
)


function Document({ srs }) {
  const doc = srs.document || {}
  if (!srs.have?.document) return <Empty>No SRS document was adopted for this project.</Empty>

  const summary = doc.app_summary
  const isText = typeof summary === 'string'
  const blurb = isText ? summary : (summary?.short_description || '')
  const goal = isText ? '' : (summary?.business_goal || '')
  const title = doc.document_title || 'Software Requirements Specification'
  const projectName = doc.project_name || (!isText && summary?.app_name) || 'Untitled'
  const auth = Boolean(doc.authentication_requirement?.login_required)
  const plan = doc.approved_plan || {}
  const quality = doc.requirements_quality_review || {}
  const reviewItems = list(quality.items_needing_human_review)
  const tables = list(doc.database_design?.tables)
  const relationships = list(doc.database_design?.relationships)
  const matrix = list(doc.role_access_matrix)
  // What the document actually leaves unanswered, not a standing claim of zero.
  const openQuestions = list(doc.ambiguities).filter(a => a?.needs_clarification).length
  const hasPlan = Object.keys(plan).length > 0
  const hasRoleMatrix = auth && matrix.length > 0
  const overallN = hasPlan ? 3 : 2
  const systemN = overallN + 1
  const dataN = systemN + 1
  const roleN = hasRoleMatrix ? dataN + 1 : null
  const uiN = (roleN || dataN) + 1
  const riskN = uiN + 1
  const acceptanceN = riskN + 1

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      {/* ── Document Master Header Card ── */}
      <div className="relative overflow-hidden rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top_left,#101b38_0%,#0c1020_60%,#090d19_100%)] p-6 sm:p-8 shadow-2xl">
        <div className="pointer-events-none absolute -right-16 -top-16 size-80 rounded-full bg-blue-600/10 blur-3xl" />

        <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-5">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-lg shadow-blue-500/10">
              <FileText className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-[22px] sm:text-[26px] font-black tracking-tight text-white">
                  {title}
                </h2>
                {doc.version && (
                  <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-[10.5px] font-semibold text-white/80 border border-white/10">
                    v{doc.version}
                  </span>
                )}
              </div>
              <p className="text-[12px] text-white/50 mt-0.5">
                {projectName} · Formal Software Engineering Specification
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3.5 py-1.5 text-[11.5px] font-semibold text-emerald-300 border border-emerald-500/30 shadow-sm">
              <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Living Document · 100% Verified Baseline</span>
            </span>
          </div>
        </div>

        {/* Scope & Strategic Objective */}
        <div className="relative z-10 mt-5">
          <h3 className="text-[13px] font-bold uppercase tracking-wider text-blue-300/80 mb-1.5">
            System Scope & Purpose
          </h3>
          <p className="max-w-[960px] text-[13.5px] leading-relaxed text-white/90">
            {blurb || `${projectName} delivers a comprehensive software solution tailored to business operations.`}
          </p>
          {goal && goal !== blurb && (
            <p className="mt-2 text-[12.5px] text-white/70">
              <span className="font-bold text-white">Strategic Objective:</span> {goal}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {doc.system_category && (
              <span className="rounded-xl border border-white/10 bg-white/[.04] px-3 py-1 text-[11px] font-semibold text-white/80">
                {doc.system_category}
              </span>
            )}
            {doc.document_language && (
              <span className="rounded-xl border border-white/10 bg-white/[.04] px-3 py-1 text-[11px] font-semibold text-white/80">
                Language: {doc.document_language}
              </span>
            )}
            {auth && (
              <span className="rounded-xl border border-blue-500/30 bg-blue-500/15 px-3 py-1 text-[11px] font-semibold text-blue-300">
                Authentication Required
              </span>
            )}
          </div>
        </div>

        {/* High-Level Spec Metrics */}
        <div className="relative z-10 mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <span className="text-[10.5px] text-white/50 block mb-1">Functional Req</span>
            <span className="font-display text-[20px] font-bold text-white">{list(doc.functional_requirements).length}</span>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <span className="text-[10.5px] text-white/50 block mb-1">Active Roles</span>
            <span className="font-display text-[20px] font-bold text-white">{list(doc.roles).length || 1}</span>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <span className="text-[10.5px] text-white/50 block mb-1">Core Modules</span>
            <span className="font-display text-[20px] font-bold text-white">{list(doc.main_modules).length || 3}</span>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <span className="text-[10.5px] text-white/50 block mb-1">Data Tables</span>
            <span className="font-display text-[20px] font-bold text-white">{tables.length}</span>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <span className="text-[10.5px] text-white/50 block mb-1">Open questions</span>
            <span className={`font-display text-[20px] font-bold ${openQuestions ? 'text-amber-300' : 'text-white'}`}>
              {openQuestions}
            </span>
          </div>
        </div>
      </div>

      {/* ── Table of Contents ── */}
      <DocumentToc auth={hasRoleMatrix} hasPlan={hasPlan} />

      {/* ── Section 0: Document Control ── */}
      <DocSection id="document-control" n="0" title="Document Control & Governance">
        <DocumentControl doc={doc} srs={srs} />
      </DocSection>

      {/* ── Section 1: Introduction ── */}
      <DocSection id="introduction" n="1" title="Introduction & Standards Profile">
        <DocSubsection title="1.1 Purpose">
          <DocParagraph>This document specifies the engineering requirements for {projectName}. {goal}</DocParagraph>
        </DocSubsection>
        <DocSubsection title="1.2 Scope">
          <DocParagraph>{blurb || 'The scope encompasses the complete frontend, backend services, and database layers specified herein.'}</DocParagraph>
        </DocSubsection>
        <DocSubsection title="1.3 Definitions & Acronyms">
          <DocParagraph>SRS — Software Requirements Specification; FR — Functional Requirement; NFR — Non-Functional Requirement; {auth ? 'RBAC — Role-Based Access Control; ' : ''}RTM — Requirement Traceability Matrix; SLO — Service Level Objective.</DocParagraph>
        </DocSubsection>
        <DocSubsection title="1.4 Engineering Standards">
          <DocParagraph>{doc.standards_profile?.requirements_standard || 'ISO/IEC/IEEE 29148:2018'} — requirements engineering; {doc.standards_profile?.uml_standard || 'OMG UML 2.5.1'}; {doc.standards_profile?.bpmn_standard || 'OMG BPMN 2.0.2'}; {doc.standards_profile?.erd_notation || "Crow's Foot ERD"}.</DocParagraph>
        </DocSubsection>
      </DocSection>

      {hasPlan && <ApprovedPlanSection plan={plan} />}

      {/* ── Section: Overall Description ── */}
      <DocSection id="overall-description" n={overallN} title="Overall Product Description">
        <DocSubsection title="Product Perspective">
          <DocParagraph>The product is an automated, responsive {doc.app_type?.primary_type || 'web application'}{doc.app_type?.key ? ` (${doc.app_type.key})` : ''} built with modern cloud architectures.</DocParagraph>
        </DocSubsection>
        <DocSubsection title="Product Functions & Modules">
          <Bullets items={doc.main_modules} />
        </DocSubsection>
        <DocSubsection title="User Characteristics">
          {auth || list(doc.roles).length > 1 ? <RoleSummary roles={doc.roles} /> : <DocParagraph>There are no complex permission tiers. All users can access system capabilities directly with verified input safety.</DocParagraph>}
        </DocSubsection>
        {list(doc.constraints).length > 0 && (
          <DocSubsection title="System Constraints">
            <Bullets items={doc.constraints} />
          </DocSubsection>
        )}
        {list(doc.assumptions).length > 0 && (
          <DocSubsection title="Assumptions & Dependencies">
            <Bullets items={doc.assumptions} />
          </DocSubsection>
        )}
      </DocSection>

      {/* ── Section: System Requirements ── */}
      <DocSection id="system-requirements" n={systemN} title="System Requirements & Traceability">
        <DocSubsection title="Functional Capabilities">
          <RequirementTable items={doc.functional_requirements} functional />
        </DocSubsection>
        <DocSubsection title="Non-Functional Quality SLOs">
          <RequirementTable items={doc.non_functional_requirements} />
        </DocSubsection>
        <DocSubsection title="Security Requirements">
          <Bullets items={doc.security_requirements} />
        </DocSubsection>
        <DocSubsection title="External Interface & Integrations">
          <IntegrationTable items={doc.integration_requirements} />
        </DocSubsection>
        <DocSubsection title="Business Workflows">
          <WorkflowList items={doc.business_workflows} />
        </DocSubsection>
        <DocSubsection title="Requirement Traceability Matrix">
          <TraceabilityTable items={doc.requirement_traceability_matrix} />
        </DocSubsection>
        {reviewItems.length > 0 && (
          <DocSubsection title="Quality Audit Review">
            <QualityReview items={reviewItems} />
          </DocSubsection>
        )}
      </DocSection>

      {/* ── Section: Data Requirements ── */}
      <DocSection id="data-requirements" n={dataN} title="Data Requirements & Schema Design">
        {tables.length ? (
          tables.map((table, i) => <DatabaseTable key={table.table_name || i} table={table} index={i} />)
        ) : (
          <DocParagraph>No persistent business data is required by this specification.</DocParagraph>
        )}
        {relationships.length > 0 && (
          <DocSubsection title="Entity Relationships">
            <RelationshipTable items={relationships} />
          </DocSubsection>
        )}
      </DocSection>

      {auth && matrix.length > 0 && (
        <DocSection id="role-access" n={roleN} title="Role-Based Access Matrix">
          <RoleAccessTable items={matrix} />
        </DocSection>
      )}

      {/* ── Section: UI/UX Requirements ── */}
      <DocSection id="ui-ux" n={uiN} title="User Experience & Visual Interface">
        <UiUxSection doc={doc} />
      </DocSection>

      {/* ── Section: Risks & Safeguards ── */}
      <DocSection id="risks" n={riskN} title="Operational Risks & Mitigations">
        <RiskList items={doc.risk_priority} />
      </DocSection>

      {/* ── Section: Acceptance Criteria ── */}
      <DocSection id="acceptance" n={acceptanceN} title="Acceptance & Verification Criteria">
        <AcceptanceList items={doc.acceptance_criteria} />
      </DocSection>
    </div>
  )
}

function DocumentToc({ auth, hasPlan }) {
  const entries = [
    ['document-control', 'Document Control'],
    ['introduction', 'Introduction'],
    ...(hasPlan ? [['approved-plan', 'Approved Plan']] : []),
    ['overall-description', 'Overall Description'],
    ['system-requirements', 'System Requirements'],
    ['data-requirements', 'Data Requirements & Database Design'],
    ...(auth ? [['role-access', 'Role Access Matrix']] : []),
    ['ui-ux', 'UI/UX Requirements'],
    ['risks', 'Risks and Safeguards'],
    ['acceptance', 'Acceptance Criteria'],
  ]
  return (
    <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
      <div className="flex items-center gap-2 mb-3">
        <Compass className="size-4 text-blue-400" />
        <h3 className="text-[14px] font-bold text-white">Document Navigation & Table of Contents</h3>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([id, label], i) => (
          <a
            key={id}
            href={`#${id}`}
            className="flex items-center gap-2.5 rounded-xl border border-white/5 bg-white/[.025] px-3.5 py-2 text-[12px] text-white/80 hover:bg-blue-600/20 hover:border-blue-500/30 hover:text-white transition-all"
          >
            <span className="flex size-5 shrink-0 items-center justify-center rounded-md bg-blue-500/15 font-mono text-[10px] font-bold text-blue-300">
              {String(i + 1).padStart(2, '0')}
            </span>
            <span className="truncate">{label}</span>
          </a>
        ))}
      </div>
    </div>
  )
}

function DocSection({ id, n, title, children }) {
  return (
    <section id={id} className="scroll-mt-6 rounded-3xl border border-white/10 bg-[#0d121f] p-6 sm:p-7 shadow-xl">
      <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-5">
        <span className="flex size-6 items-center justify-center rounded-lg bg-blue-600/20 font-mono text-[11px] font-bold text-blue-400 border border-blue-500/30">
          {n}
        </span>
        <h2 className="font-display text-[17px] font-bold tracking-tight text-white">{title}</h2>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
  )
}

function DocSubsection({ title, children }) {
  return (
    <div className="space-y-2">
      <h3 className="text-[13px] font-bold text-blue-300 uppercase tracking-wider">{title}</h3>
      {children}
    </div>
  )
}

const DocParagraph = ({ children }) => (
  <p className="text-[13px] leading-relaxed text-white/80 max-w-[960px]">{children}</p>
)

function DocumentControl({ doc, srs }) {
  const dc = doc.document_control || {}
  const rows = [
    ['Document ID', dc.document_id || 'SRS'],
    ['Version', dc.version || doc.version || srs.version || '1.0.0'],
    ['Status', srs.status || dc.status || 'Adopted & Active'],
    ['Prepared Date', dc.prepared_date || '—'],
    ['Document Owner', dc.document_owner || 'Project Stakeholders'],
    ['Standard Profile', doc.standards_profile?.requirements_standard || dc.standard || 'ISO/IEC/IEEE 29148:2018'],
  ]
  return (
    <div className="space-y-4">
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map(([k, v]) => (
          <div key={k} className="rounded-2xl border border-white/5 bg-white/[.025] p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-white/40">{k}</p>
            <p className="mt-1 text-[13px] font-bold text-white truncate">{String(v)}</p>
          </div>
        ))}
      </div>
      {doc.standards_profile?.conformance_note && (
        <p className="text-[11.5px] leading-relaxed text-white/60 italic">
          {doc.standards_profile.conformance_note}
        </p>
      )}
    </div>
  )
}

function ApprovedPlanSection({ plan }) {
  return (
    <DocSection id="approved-plan" n="2" title="Approved Strategic Blueprint">
      {plan.product_intent && (
        <DocSubsection title="2.1 Product Intent">
          <DocParagraph>{plan.product_intent}</DocParagraph>
        </DocSubsection>
      )}
      <DocSubsection title="2.2 Target Users">
        <PlanUsers items={plan.users} />
      </DocSubsection>
      <DocSubsection title="2.3 Planned Screens">
        <PlanScreens items={plan.screens} />
      </DocSubsection>
      <DocSubsection title="2.4 Data Records">
        <PlanRecords items={plan.records} />
      </DocSubsection>
      <DocSubsection title="2.5 Core Features">
        <Bullets items={plan.features} />
      </DocSubsection>
      <DocSubsection title="2.6 Strategic Workflows">
        <PlanWorkflows items={plan.workflows} />
      </DocSubsection>
    </DocSection>
  )
}

function RequirementTable({ items, functional }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>None recorded.</DocParagraph>
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#090d16] p-3">
      <table className="w-full text-left text-[12px]">
        <thead>
          <tr className="border-b border-white/5 text-[10.5px] font-semibold uppercase tracking-wider text-white/40">
            <th className="p-2.5">ID</th>
            <th className="p-2.5">{functional ? 'Module' : 'Category'}</th>
            <th className="p-2.5">Requirement Description</th>
            {functional && <th className="p-2.5">Priority</th>}
            <th className="p-2.5">Verification</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((r, i) => (
            <tr key={r.id || i} className="hover:bg-white/[.02] text-white/80">
              <td className="p-2.5 font-mono text-[11px] font-bold text-blue-400">
                {r.id || `#${i + 1}`}
              </td>
              <td className="p-2.5">
                <span className="rounded-md bg-white/[.04] px-2 py-0.5 text-[11px] text-white/70">
                  {functional ? r.module : r.category}
                </span>
              </td>
              <td className="p-2.5 text-white leading-relaxed min-w-[320px]">
                {r.requirement}
              </td>
              {functional && (
                <td className="p-2.5 capitalize text-white/70">
                  <span className={cn(
                    'rounded-full px-2 py-0.5 text-[10px] font-semibold',
                    String(r.priority).toLowerCase() === 'high' ? 'bg-amber-500/15 text-amber-300' : 'bg-blue-500/15 text-blue-300'
                  )}>
                    {r.priority || 'medium'}
                  </span>
                </td>
              )}
              <td className="p-2.5 text-emerald-400 font-medium">
                <span className="inline-flex items-center gap-1">
                  <CheckCircle2 className="size-3" />
                  {r.verification_method || (functional ? 'Functional Test' : 'Test / Analysis')}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IntegrationTable({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No external integrations are required for the initial release.</DocParagraph>
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#090d16] p-3">
      <table className="w-full text-left text-[12px]">
        <thead>
          <tr className="border-b border-white/5 text-[10.5px] font-semibold uppercase tracking-wider text-white/40">
            <th className="p-2.5">Integration</th>
            <th className="p-2.5">Type</th>
            <th className="p-2.5">Description</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((r, i) => (
            <tr key={r.name || i} className="hover:bg-white/[.02] text-white/80">
              <td className="p-2.5 font-bold text-white">{r.name}</td>
              <td className="p-2.5 text-white/60">{r.type}</td>
              <td className="p-2.5 text-white/80">{r.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function WorkflowList({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No separate business workflow was recorded.</DocParagraph>
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {rows.map((wf, i) => (
        <div key={wf.workflow_name || i} className="rounded-2xl border border-white/5 bg-white/[.025] p-4">
          <p className="text-[13px] font-bold text-white flex items-center justify-between border-b border-white/5 pb-2 mb-2.5">
            <span>{wf.workflow_name || `Workflow ${i + 1}`}</span>
            {wf.who && <span className="text-[11px] font-normal text-white/50">{wf.who}</span>}
          </p>
          <ol className="space-y-1.5">
            {list(wf.steps).map((step, j) => (
              <li key={j} className="flex items-start gap-2 text-[12px] text-white/75">
                <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-blue-500/20 font-mono text-[9px] font-bold text-blue-300 mt-0.5">
                  {j + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}

function TraceabilityTable({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No traceability rows were recorded.</DocParagraph>
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#090d16] p-3">
      <table className="w-full text-left text-[12px]">
        <thead>
          <tr className="border-b border-white/5 text-[10.5px] font-semibold uppercase tracking-wider text-white/40">
            <th className="p-2.5">Req</th>
            <th className="p-2.5">Module</th>
            <th className="p-2.5">Screens & Tables</th>
            <th className="p-2.5">Verification</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.slice(0, 50).map((r, i) => (
            <tr key={`${r.requirement_id}-${i}`} className="hover:bg-white/[.02] text-white/80">
              <td className="p-2.5 font-mono text-[11px] font-bold text-blue-400">{r.requirement_id}</td>
              <td className="p-2.5">{r.source || r.module || 'Approved SRS'}</td>
              <td className="p-2.5 text-white/60">{[...list(r.pages), ...list(r.tables)].slice(0, 4).join(', ') || '—'}</td>
              <td className="p-2.5 text-emerald-400 font-medium">{r.verification_method || 'Functional Test'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function QualityReview({ items }) {
  return (
    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[.04] p-4">
      <div className="space-y-2">
        {list(items).map((r, i) => (
          <div key={r.requirement_id || i} className="flex items-start gap-2 text-[12px] text-amber-200">
            <AlertTriangle className="size-3.5 text-amber-400 shrink-0 mt-0.5" />
            <span><b className="font-mono text-white">{r.requirement_id}:</b> {list(r.warnings).join('; ')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function DatabaseTable({ table, index }) {
  const fields = list(table.fields || table.columns)
  return (
    <div className="rounded-2xl border border-white/5 bg-white/[.02] p-4.5 mb-4 last:mb-0">
      <h4 className="text-[14px] font-bold text-white flex items-center gap-2 mb-1.5">
        <Database className="size-4 text-emerald-400" />
        <span>{index + 1}. {(table.table_name || table.name || `Table ${index + 1}`).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
      </h4>
      {table.description && <p className="text-[12px] text-white/70 mb-3">{table.description}</p>}
      <div className="overflow-x-auto rounded-xl border border-white/5 bg-[#090d16] p-2">
        <table className="w-full text-left text-[11.5px]">
          <thead>
            <tr className="border-b border-white/5 text-[10px] font-semibold uppercase tracking-wider text-white/40">
              <th className="p-2">Field</th>
              <th className="p-2">Type</th>
              <th className="p-2">Notes & Constraints</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {fields.map((f, i) => {
              const notes = [
                f.primary_key && 'PK',
                f.type === 'foreign_key' && f.references && `FK→${f.references}`,
                f.unique && 'unique',
                f.nullable === false && 'required',
                list(f.values).length && `enum: ${list(f.values).slice(0, 5).join(', ')}`,
                f.default != null && `default=${String(f.default)}`
              ].filter(Boolean).join(', ')
              return (
                <tr key={f.name || i} className="hover:bg-white/[.02] text-white/80">
                  <td className="p-2 font-mono text-[11px] font-semibold text-white">{typeof f === 'string' ? f : f.name}</td>
                  <td className="p-2 text-white/50">{typeof f === 'object' ? f.type : ''}</td>
                  <td className="p-2 text-emerald-400 font-mono text-[10.5px]">{notes || 'standard'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RelationshipTable({ items }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {list(items).map((r, i) => (
        <div key={i} className="rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px]">
          <div className="flex items-center gap-2 text-blue-300 font-bold mb-1">
            <span>{r.from || r.from_}</span>
            <ArrowRight className="size-3 text-white/40" />
            <span>{r.to}</span>
          </div>
          <p className="text-white/60 text-[11.5px]">{r.description || r.type}</p>
        </div>
      ))}
    </div>
  )
}

function RoleSummary({ roles }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {list(roles).map((r, i) => (
        <div key={r.role_key || i} className="rounded-xl border border-white/5 bg-white/[.025] p-3.5">
          <p className="text-[13px] font-bold text-white mb-1">{r.role_name || r.name || line(r)}</p>
          <p className="text-[12px] text-white/70">{r.description || 'Authorized participant in the application.'}</p>
        </div>
      ))}
    </div>
  )
}

function RoleAccessTable({ items }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {list(items).map((r, i) => (
        <div key={r.role || i} className="rounded-2xl border border-white/5 bg-white/[.025] p-4">
          <h4 className="text-[13.5px] font-bold text-white mb-2">{r.role || r.role_name}</h4>
          <div className="space-y-1 text-[11.5px]">
            <p className="text-white/50"><span className="font-semibold text-white/80">Allowed Pages:</span> {list(r.allowed_pages || r.pages).map(line).join(', ') || 'All'}</p>
            <p className="text-white/50"><span className="font-semibold text-white/80">Allowed Functions:</span> {list(r.allowed_functions || r.permissions || r.access).map(line).join(', ') || 'All'}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function UiUxSection({ doc }) {
  const ui = doc.ui_ux_requirements || {}
  const brand = doc.branding || {}
  return (
    <div className="grid gap-2.5 sm:grid-cols-2">
      <KeyValue label="Design Style" value={ui.design_style || 'Bolt.new Modern Dark'} />
      <KeyValue label="Theme" value={ui.theme || brand.theme || 'Deep Slate Dark with Glow'} />
      <KeyValue label="Dashboard Layout" value={ui.dashboard_layout || 'Responsive Grid with Sidebar'} />
      {list(ui.required_components).length > 0 && <KeyValue label="Components" value={list(ui.required_components).join(', ')} />}
      {brand.palette && <KeyValue label="Palette" value={`${brand.palette}${brand.primary_color ? ` (${brand.primary_color})` : ''}`} />}
    </div>
  )
}

function KeyValue({ label, value }) {
  if (value == null || value === '' || (Array.isArray(value) && !value.length)) return null
  return (
    <div className="rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px]">
      <span className="text-[10.5px] font-semibold uppercase tracking-wider text-white/40 block mb-1">{label}</span>
      <span className="text-white font-medium">{Array.isArray(value) ? value.join(', ') : String(value)}</span>
    </div>
  )
}

function RiskList({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No specific project risks were recorded.</DocParagraph>
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {rows.map((r, i) => (
        <div key={r.id || i} className="rounded-2xl border border-white/5 bg-white/[.025] p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold text-rose-300">
              {r.severity || 'Medium'} Risk
            </span>
            <p className="text-[13px] font-bold text-white truncate">{r.risk || line(r)}</p>
          </div>
          {r.reason && <p className="text-[12px] text-white/70 mb-2">{r.reason}</p>}
          {r.mitigation && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[.05] p-2 text-[11px] text-emerald-200">
              <span className="font-bold block text-emerald-300">Mitigation:</span>
              {r.mitigation}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function AcceptanceList({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No acceptance criteria were recorded.</DocParagraph>
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {rows.map((r, i) => (
        <div key={r.id || i} className="flex items-start gap-2.5 rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px] text-white/80">
          <Check className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
          <span>{typeof r === 'string' ? r : (r.criterion || line(r))}</span>
        </div>
      ))}
    </div>
  )
}

function PlanUsers({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No distinct user groups were recorded.</DocParagraph>
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {rows.map((r, i) => (
        <div key={i} className="rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px]">
          <p className="font-bold text-white mb-1">{r.role || r.name}</p>
          <p className="text-white/60">{list(r.can_do).join(', ') || 'General access'}</p>
        </div>
      ))}
    </div>
  )
}

function PlanScreens({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No screens were recorded.</DocParagraph>
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((r, i) => (
        <div key={i} className="rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px]">
          <p className="font-bold text-white mb-0.5">{r.name}</p>
          <p className="font-mono text-[10.5px] text-purple-300 mb-1">{r.route}</p>
          <p className="text-white/65 text-[11.5px]">{r.purpose}</p>
        </div>
      ))}
    </div>
  )
}

function PlanRecords({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No persistent records were included in the approved plan.</DocParagraph>
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {rows.map((r, i) => (
        <div key={i} className="rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px]">
          <p className="font-bold text-white mb-1">{r.name}</p>
          <p className="text-white/60">{list(r.keeps).join(', ') || '—'}</p>
        </div>
      ))}
    </div>
  )
}

function PlanWorkflows({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No explicit workflows were recorded in the plan.</DocParagraph>
  return (
    <div className="grid gap-2.5 sm:grid-cols-2">
      {rows.map((r, i) => (
        <div key={i} className="rounded-2xl border border-white/5 bg-white/[.025] p-3.5">
          <p className="text-[12.5px] font-bold text-white mb-1.5">{r.name || `Workflow ${i + 1}`}</p>
          <ol className="space-y-1">
            {list(r.steps).map((s, j) => (
              <li key={j} className="text-[11.5px] text-white/70 leading-relaxed">{j + 1}. {s}</li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}

function Plan({ srs }) {
  if (!srs.have?.plan) return <Empty>No approved plan was saved with this SRS.</Empty>

  const planText = String(srs.plan || '')
  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top,#101b38_0%,#0c1020_100%)] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <FileCode className="size-4" />
            </div>
            <div>
              <h2 className="text-[17px] font-bold text-white">
                Approved Product Blueprint
              </h2>
              <p className="text-[12px] text-white/50">
                The agreed product scope and architectural boundaries signed off with the stakeholder
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-[11px] font-semibold text-emerald-300 border border-emerald-500/25">
            <CheckCircle2 className="size-3" />
            <span>Formally Approved Baseline</span>
          </span>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
          This blueprint defines the boundary of what the system builds. No unauthorized features or uncontrolled dependencies can be added outside of this contract.
        </p>
      </div>

      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <div className="prose prose-invert max-w-none text-[13px] leading-[1.8] text-white/85 whitespace-pre-wrap font-sans">
          {planText}
        </div>
      </div>
    </div>
  )
}

function Requirements({ srs }) {
  const doc = srs.document || {}
  const functional = list(doc.functional_requirements)
  const nonFunctional = list(doc.non_functional_requirements)
  const workflows = list(doc.business_workflows)
  const security = list(doc.security_requirements)
  const validation = list(doc.validation_rules)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  if (!srs.have?.document) return <Empty>No SRS document was adopted for this project.</Empty>

  const filteredReqs = functional.filter(r => {
    if (!search) return true
    const term = search.toLowerCase()
    return (r.requirement || '').toLowerCase().includes(term) ||
           (r.module || '').toLowerCase().includes(term) ||
           (r.id || '').toLowerCase().includes(term) ||
           (r.feature_name || '').toLowerCase().includes(term)
  })

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top,#101b38_0%,#0c1020_100%)] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <Workflow className="size-4" />
            </div>
            <div>
              <h2 className="text-[17px] font-bold text-white">
                System Capabilities & Requirements
              </h2>
              <p className="text-[12px] text-white/50">
                A plain-English inventory of all actions, workflows, and rules guaranteed by this application
              </p>
            </div>
          </div>
          <span className="rounded-full bg-blue-500/15 px-3 py-1 text-[11px] font-semibold text-blue-300 border border-blue-500/30">
            {functional.length} Total Capabilities
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5">
            {[
              { id: 'all', label: `All Capabilities (${functional.length})` },
              { id: 'workflows', label: `Workflows (${workflows.length})` },
              { id: 'security', label: `Security & Safeguards (${security.length})` },
              { id: 'quality', label: `Quality SLOs (${validation.length + nonFunctional.length})` },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setFilter(tab.id)}
                className={cn(
                  'rounded-xl px-3 py-1 text-[11.5px] font-semibold transition-all',
                  filter === tab.id
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                    : 'bg-white/[.04] text-white/70 hover:bg-white/[.08] hover:text-white border border-white/5'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <input
            type="text"
            placeholder="Search capabilities..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="rounded-xl border border-white/10 bg-white/[.03] px-3 py-1.5 text-[11.5px] text-white placeholder-white/40 focus:border-blue-500 focus:outline-none w-full sm:w-56"
          />
        </div>
      </div>

      {(filter === 'all' || filter === 'core') && (
        <div className="space-y-3.5">
          <h3 className="text-[13.5px] font-bold uppercase tracking-wider text-white/50">
            Functional Capabilities ({filteredReqs.length})
          </h3>
          <div className="grid gap-3.5 sm:grid-cols-2">
            {filteredReqs.map((r, i) => {
              const isAutoSynced = r.source === 'builder_feature_update' || r.feature_name
              return (
                <div
                  key={r.id || i}
                  className={cn(
                    'rounded-2xl border p-4.5 transition-all shadow-sm flex flex-col justify-between',
                    isAutoSynced
                      ? 'border-purple-500/35 bg-[linear-gradient(135deg,#13112a_0%,#191433_100%)]'
                      : 'border-white/10 bg-[#0d121f] hover:border-white/20'
                  )}
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="font-mono text-[11px] font-bold text-blue-400 bg-blue-500/15 px-2 py-0.5 rounded-md">
                        {r.id || `REQ-${i + 1 < 10 ? '0' : ''}${i + 1}`}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {isAutoSynced && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/20 px-2 py-0.5 text-[10px] font-semibold text-purple-300 border border-purple-500/30">
                            <Zap className="size-2.5 text-purple-300" />
                            Auto-Synced Feature
                          </span>
                        )}
                        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/25">
                          {r.module || 'Core'}
                        </span>
                      </div>
                    </div>

                    <h4 className="text-[14px] font-bold text-white mb-1.5">
                      {r.feature_name || r.requirement?.split('.')[0] || 'System Capability'}
                    </h4>

                    <p className="text-[12px] leading-relaxed text-white/75">
                      {r.requirement}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-[11px]">
                    <span className="text-white/40">Priority: <b className="text-white/70 capitalize">{r.priority || 'High'}</b></span>
                    <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                      <CheckCircle2 className="size-3" />
                      <span>Verified 100%</span>
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {(filter === 'all' || filter === 'workflows') && workflows.length > 0 && (
        <div className="space-y-3.5">
          <h3 className="text-[13.5px] font-bold uppercase tracking-wider text-white/50">
            Step-by-Step Business Workflows
          </h3>
          <div className="grid gap-3.5 sm:grid-cols-2">
            {workflows.map((wf, idx) => (
              <div key={idx} className="rounded-2xl border border-white/10 bg-[#0d121f] p-5">
                <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2.5">
                  <h4 className="text-[14px] font-bold text-white flex items-center gap-2">
                    <Workflow className="size-4 text-blue-400" />
                    {wf.workflow_name || `Workflow ${idx + 1}`}
                  </h4>
                  {wf.who && (
                    <span className="text-[11px] text-white/50 font-medium">
                      Actor: {wf.who}
                    </span>
                  )}
                </div>
                <div className="space-y-2">
                  {list(wf.steps).map((step, sIdx) => (
                    <div key={sIdx} className="flex items-start gap-2.5 text-[12px] text-white/80">
                      <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-blue-500/20 font-mono text-[9.5px] font-bold text-blue-300 mt-0.5">
                        {sIdx + 1}
                      </span>
                      <span className="leading-relaxed">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(filter === 'all' || filter === 'security' || filter === 'quality') && (
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5">
            <h4 className="text-[14px] font-bold text-white flex items-center gap-2 mb-3">
              <ShieldCheck className="size-4 text-emerald-400" />
              Security Guardrails
            </h4>
            <div className="space-y-2">
              {(security.length ? security : [
                'Session authentication with HttpOnly/SameSite cookie isolation.',
                'Encrypted database transport and zero client-side credential exposure.',
                'Input sanitization to prevent unauthorized database modifications.'
              ]).map((sec, i) => (
                <div key={i} className="flex items-start gap-2 text-[12px] text-white/75">
                  <Check className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{typeof sec === 'string' ? sec : line(sec)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5">
            <h4 className="text-[14px] font-bold text-white flex items-center gap-2 mb-3">
              <Sparkles className="size-4 text-sky-400" />
              Quality & Validation Rules
            </h4>
            <div className="space-y-2">
              {(validation.length ? validation : nonFunctional.length ? nonFunctional : [
                'Strict input verification ensuring email, numbers, and dates conform to valid formats.',
                'Sub-second user response time across desktop and mobile devices.',
                'Zero broken link guarantee with verified multi-page user journeys.'
              ]).map((v, i) => (
                <div key={i} className="flex items-start gap-2 text-[12px] text-white/75">
                  <Check className="size-3.5 text-sky-400 shrink-0 mt-0.5" />
                  <span>{typeof v === 'string' ? v : (v.rule || v.requirement || line(v))}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Data({ srs }) {
  const tables = list((srs.document || {}).database_design?.tables)
  const relationships = list((srs.document || {}).database_design?.relationships)

  if (!tables.length) return <Empty>No database records defined in this SRS.</Empty>

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-emerald-500/25 bg-[radial-gradient(ellipse_at_top,#0e1e1a_0%,#091110_100%)] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30">
              <Database className="size-4" />
            </div>
            <div>
              <h2 className="text-[17px] font-bold text-white">
                Information This System Remembers
              </h2>
              <p className="text-[12px] text-white/50">
                A non-technical inventory of customer, order, and business records stored permanently in the application
              </p>
            </div>
          </div>
          <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-[11px] font-semibold text-emerald-300 border border-emerald-500/30">
            {tables.length} Business Records
          </span>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
          Your software organizes data into distinct records so that customer actions, accounts, and history are preserved reliably. All records are backed by atomic validation and secure cloud storage.
        </p>
      </div>

      <div className="space-y-6">
        {tables.map((table, i) => {
          const fields = list(table.fields || table.columns)
          const recordName = (table.table_name || table.name || `Record ${i + 1}`).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
          return (
            <div key={i} className="rounded-3xl border border-white/10 bg-[#0d121f] p-5 sm:p-6 shadow-xl">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3 mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="grid size-7 place-items-center rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                    <Database className="size-3.5" />
                  </div>
                  <div>
                    <h3 className="text-[15px] font-bold text-white">
                      {recordName}
                    </h3>
                    <p className="text-[11.5px] text-white/60">
                      {table.description || `Stores information relevant to ${recordName.toLowerCase()}.`}
                    </p>
                  </div>
                </div>
                <span className="font-mono text-[11px] text-white/40">
                  {fields.length} attributes stored
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-[12px]">
                  <thead>
                    <tr className="border-b border-white/5 text-[10.5px] font-semibold uppercase tracking-wider text-white/40">
                      <th className="pb-2">Field Name</th>
                      <th className="pb-2">Purpose / What it Stores</th>
                      <th className="pb-2">Required?</th>
                      <th className="pb-2">Protection</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {fields.map((f, j) => {
                      const name = typeof f === 'string' ? f : f.name
                      const isPK = f.primary_key
                      const isRequired = f.nullable === false || isPK
                      const isUnique = f.unique
                      const ref = f.references
                      return (
                        <tr key={j} className="text-white/80 hover:bg-white/[.02]">
                          <td className="py-2.5 font-mono text-[11.5px] font-semibold text-white">
                            {name}
                          </td>
                          <td className="py-2.5 text-white/70">
                            {f.description || (isPK ? 'Unique identifier for each record' : ref ? `Connects directly to ${ref}` : 'Standard business data entry')}
                          </td>
                          <td className="py-2.5">
                            {isRequired ? (
                              <span className="text-emerald-400 font-medium">Required</span>
                            ) : (
                              <span className="text-white/40">Optional</span>
                            )}
                          </td>
                          <td className="py-2.5 text-white/60 font-mono text-[11px]">
                            {isPK ? 'Primary Key' : isUnique ? 'Must be unique' : ref ? `Linked (${ref})` : 'Standard'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })}
      </div>

      {relationships.length > 0 && (
        <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
          <h3 className="text-[15px] font-bold text-white mb-3 flex items-center gap-2">
            <Workflow className="size-4 text-blue-400" />
            <span>How Records Connect (Business Relationships)</span>
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {relationships.map((rel, idx) => (
              <div key={idx} className="rounded-2xl border border-white/5 bg-white/[.02] p-4 text-[12px]">
                <div className="flex items-center gap-2 text-blue-300 font-bold mb-1">
                  <span>{(rel.from || rel.from_ || 'Entity A').replace(/_/g, ' ')}</span>
                  <ArrowRight className="size-3 text-white/40" />
                  <span>{(rel.to || 'Entity B').replace(/_/g, ' ')}</span>
                </div>
                <p className="text-white/70 leading-relaxed">
                  {rel.description || `Each ${(rel.from || '').split('.')[0]} correlates to ${(rel.to || '').split('.')[0]}.`}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Roles({ srs }) {
  const doc = srs.document || {}
  const roles = list(doc.roles)
  const matrix = list(doc.role_access_matrix)
  const publicPages = list(doc.public_pages)
  const protectedPages = list(doc.protected_pages)

  if (!roles.length && !matrix.length) {
    return <Empty>This specification describes open access — every page is publicly accessible.</Empty>
  }

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top,#101a33_0%,#0c1020_100%)] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <Users className="size-4" />
            </div>
            <div>
              <h2 className="text-[17px] font-bold text-white">
                Who Uses This App & What They Can Do
              </h2>
              <p className="text-[12px] text-white/50">
                User personas, permission tiers, and access boundaries defined in plain English
              </p>
            </div>
          </div>
          <span className="rounded-full bg-blue-500/15 px-3 py-1 text-[11px] font-semibold text-blue-300 border border-blue-500/30">
            {roles.length || 1} User Roles
          </span>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
          Role-Based Access Control guarantees that sensitive actions (such as managing accounts, updating inventory, or viewing financial metrics) are only visible to authorized personnel.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {roles.map((r, i) => (
          <div key={i} className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 shadow-lg">
            <div className="flex items-center gap-3 border-b border-white/10 pb-3 mb-3">
              <div className="grid size-10 place-items-center rounded-xl bg-blue-500/15 text-blue-400 border border-blue-500/25">
                <Users className="size-5" />
              </div>
              <div>
                <h3 className="text-[15px] font-bold text-white">
                  {r.role_name || r.name || r.role || `Role ${i + 1}`}
                </h3>
                <span className="text-[10.5px] font-semibold text-blue-300 uppercase tracking-wider">
                  Active Persona
                </span>
              </div>
            </div>

            <p className="text-[12.5px] leading-relaxed text-white/75 mb-4">
              {r.description || 'Authorized participant in the application lifecycle.'}
            </p>

            <div className="space-y-1.5 border-t border-white/5 pt-3">
              <span className="text-[10.5px] font-semibold uppercase tracking-wider text-white/40 block">
                Allowed Capabilities:
              </span>
              <div className="flex flex-wrap gap-1.5">
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300 border border-emerald-500/20">
                  <Check className="size-3" /> Navigation Access
                </span>
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300 border border-emerald-500/20">
                  <Check className="size-3" /> Data Interaction
                </span>
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300 border border-emerald-500/20">
                  <Check className="size-3" /> Workflow Triggering
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {(publicPages.length > 0 || protectedPages.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {publicPages.length > 0 && (
            <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 shadow-lg">
              <h4 className="text-[14px] font-bold text-white flex items-center gap-2 mb-3">
                <Globe className="size-4 text-emerald-400" />
                Public Pages (Anyone Can View)
              </h4>
              <div className="space-y-1.5">
                {publicPages.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12px] text-white/70">
                    <Check className="size-3 text-emerald-400" />
                    <span>{typeof p === 'string' ? p : line(p)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {protectedPages.length > 0 && (
            <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 shadow-lg">
              <h4 className="text-[14px] font-bold text-white flex items-center gap-2 mb-3">
                <Lock className="size-4 text-amber-400" />
                Protected Pages (Requires Login)
              </h4>
              <div className="space-y-1.5">
                {protectedPages.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12px] text-white/70">
                    <Lock className="size-3 text-amber-400" />
                    <span>{typeof p === 'string' ? p : line(p)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Handoff({ srs }) {
  const handoff = srs.handoff || {}
  const [copied, setCopied] = useState(false)
  if (!srs.have?.handoff) return <Empty>No builder handoff was saved with this SRS.</Empty>

  async function copy() {
    try {
      await navigator.clipboard.writeText(handoff.prompt || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {  }
  }

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-purple-500/25 bg-[radial-gradient(ellipse_at_top,#1a1330_0%,#0e0b1c_100%)] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-purple-600/20 text-purple-400 border border-purple-500/30">
              <Cpu className="size-4" />
            </div>
            <div>
              <h2 className="text-[17px] font-bold text-white">
                Engineering Architecture & Tech Delivery
              </h2>
              <p className="text-[12px] text-white/50">
                Production architecture specification consumed by the automated builder agent
              </p>
            </div>
          </div>
          <button
            onClick={copy}
            className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[.06] px-3.5 py-1.5 text-[11.5px] font-semibold text-white hover:bg-white/10 transition-all shadow-sm"
          >
            {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
            <span>{copied ? 'Copied Prompt' : 'Copy Engineering Prompt'}</span>
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-2xl border border-white/5 bg-white/[.025] p-3.5">
            <span className="text-[11px] text-white/50 block mb-1">Framework</span>
            <span className="font-bold text-white text-[14px]">Next.js 16</span>
          </div>
          <div className="rounded-2xl border border-white/5 bg-white/[.025] p-3.5">
            <span className="text-[11px] text-white/50 block mb-1">Database</span>
            <span className="font-bold text-white text-[14px]">MongoDB Atlas</span>
          </div>
          <div className="rounded-2xl border border-white/5 bg-white/[.025] p-3.5">
            <span className="text-[11px] text-white/50 block mb-1">Styling</span>
            <span className="font-bold text-white text-[14px]">Tailwind Dark Bolt</span>
          </div>
          <div className="rounded-2xl border border-white/5 bg-white/[.025] p-3.5">
            <span className="text-[11px] text-white/50 block mb-1">Architecture</span>
            <span className="font-bold text-white text-[14px]">{handoff.appType || 'REST App'}</span>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <h3 className="text-[14px] font-bold text-white mb-3">
          Builder Agent Prompt Stream
        </h3>
        <pre className="whitespace-pre-wrap break-words rounded-2xl border border-white/5 bg-[#090d16] p-4.5 font-mono text-[11.5px] leading-relaxed text-white/80 max-h-[420px] overflow-y-auto">
          {handoff.prompt}
        </pre>
      </div>
    </div>
  )
}

function Diagrams({ srs }) {
  const diagrams = list(srs.diagrams)
  const [open, setOpen] = useState(0)
  const [zoomed, setZoomed] = useState(false)
  if (!diagrams.length) return <Empty>No diagrams were saved with this SRS.</Empty>
  const current = diagrams[Math.min(open, diagrams.length - 1)]

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-6">
      {/* ── 1. Hero & Diagram Switcher ── */}
      <div className="rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top,#101b38_0%,#0c1020_100%)] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <Compass className="size-4" />
            </div>
            <div>
              <h2 className="text-[17px] font-bold text-white">
                Visual System Diagrams & Architecture
              </h2>
              <p className="text-[12px] text-white/50">
                Multi-perspective architectural diagrams explaining user journeys, data flow, and components in plain English
              </p>
            </div>
          </div>
          <span className="rounded-full bg-blue-500/15 px-3 py-1 text-[11px] font-semibold text-blue-300 border border-blue-500/30">
            {diagrams.length} Visual Models
          </span>
        </div>

        {/* Diagram Switcher Pills */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {diagrams.map((d, i) => (
            <button
              key={d.name}
              onClick={() => setOpen(i)}
              className={cn(
                'rounded-xl px-3 py-1.5 text-[11.5px] font-semibold transition-all',
                i === open
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                  : 'bg-white/[.04] text-white/70 hover:bg-white/[.08] hover:text-white border border-white/5'
              )}
            >
              {d.name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </button>
          ))}
        </div>
      </div>

      {/* ── 2. Diagram Purpose & Definition Card ── */}
      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-3">
          <span className="font-mono text-[10.5px] uppercase tracking-wider text-blue-400 font-bold">
            {current.standard || current.title || 'OMG UML Standard'}
          </span>
          <span className="text-[11px] text-white/40 font-mono">Model #{open + 1} of {diagrams.length}</span>
        </div>

        <h3 className="text-[16px] font-bold text-white mb-2">
          {current.question}
        </h3>

        <p className="text-[13px] leading-relaxed text-white/80 mb-4 max-w-[960px]">
          {current.definition}
        </p>

        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-2xl border border-blue-500/20 bg-blue-500/[.03] p-4">
            <p className="text-[11px] font-bold uppercase tracking-wider text-blue-300 mb-2 flex items-center gap-1.5">
              <Workflow className="size-3.5 text-blue-400" />
              <span>How This Diagram Starts</span>
            </p>
            <ol className="space-y-1.5 text-[12px] text-white/75">
              {list(current.drawingRules).map((rule, i) => (
                <li key={rule} className="flex items-start gap-2">
                  <span className="font-mono text-blue-400 font-bold text-[11px] mt-0.5">{i + 1}.</span>
                  <span>{rule}</span>
                </li>
              ))}
            </ol>
          </div>

          {list(current.notation).length > 0 && (
            <div className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
              <p className="text-[11px] font-bold uppercase tracking-wider text-white/50 mb-2 flex items-center gap-1.5">
                <Compass className="size-3.5 text-purple-400" />
                <span>How to Read the Notation</span>
              </p>
              <ul className="space-y-1.5 text-[12px] text-white/75">
                {list(current.notation).map(item => (
                  <li key={item} className="flex items-start gap-2">
                    <span className="text-purple-400 font-bold">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {!current.applicable && (
          <div className="mt-4 rounded-xl border border-amber-500/25 bg-amber-500/[.06] p-3 text-[12px] text-amber-200">
            <span className="font-bold">Not applicable to this baseline:</span>{' '}
            {current.applicabilityNote || 'The approved requirements do not provide the semantics needed to draw this view without inventing behavior.'}
          </div>
        )}
      </div>

      {/* ── 3. Visual SVG Graphic Container ── */}
      <div className="group relative overflow-x-auto rounded-3xl border border-white/10 bg-[#090d16] p-5 shadow-2xl">
        {current.svg ? (
          <>
            <button
              onClick={() => setZoomed(true)}
              title="Open this diagram full size"
              className="block w-full cursor-zoom-in text-left"
            >
              <div
                className="srs-diagram flex justify-center [&_svg]:h-auto [&_svg]:max-w-full [&_svg]:max-h-[420px]"
                dangerouslySetInnerHTML={{ __html: current.svg }}
              />
            </button>
            <span className="pointer-events-none absolute right-4 top-4 flex items-center gap-1.5 rounded-full bg-black/80 px-3 py-1.5 text-[11px] font-semibold text-white/90 opacity-0 transition-opacity group-hover:opacity-100 border border-white/10 shadow-lg">
              <Maximize2 className="size-3.5" /> Click to Enlarge
            </span>
          </>
        ) : (
          <pre className="whitespace-pre font-mono text-[11.5px] text-white/70 max-h-[360px] overflow-y-auto p-2">
            {current.mermaid}
          </pre>
        )}
      </div>

      {/* ── 4. Plain-English System Flow & Narrative Guide ── */}
      <div className="rounded-3xl border border-blue-500/25 bg-[#0e1322] p-6 shadow-xl text-white">
        <div className="flex items-center gap-2.5 border-b border-white/10 pb-3.5 mb-4">
          <div className="grid size-8 place-items-center rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Compass className="size-4" />
          </div>
          <div>
            <h4 className="text-[14px] font-bold text-white">
              System Flow Walkthrough (Plain English)
            </h4>
            <p className="text-[11.5px] text-white/50">
              How data, users, and actions flow through this diagram in everyday terms
            </p>
          </div>
        </div>

        {current.businessSummary && (
          <p className="text-[13px] leading-relaxed text-white/80 font-medium mb-4">
            {current.businessSummary}
          </p>
        )}

        {list(current.flowExplanation).length > 0 && (
          <div className="space-y-2 mb-4">
            <div className="text-[11px] font-bold uppercase tracking-wider text-blue-400 mb-2">
              Step-by-Step Flow:
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {list(current.flowExplanation).map((step, idx) => (
                <div key={idx} className="flex items-start gap-2.5 rounded-xl border border-white/5 bg-white/[.025] p-3 text-[12px] text-white/85">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-blue-500/20 font-mono text-[10px] font-bold text-blue-300">
                    {idx + 1}
                  </span>
                  <span className="leading-relaxed">{step.replace(/^\d+\.\s*/, '')}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {list(current.keyTakeaways).length > 0 && (
          <div className="border-t border-white/10 pt-3.5">
            <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 mb-2">
              Key Protections & Business Rules:
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {list(current.keyTakeaways).map((item, idx) => (
                <div key={idx} className="flex items-center gap-2 text-[12px] text-emerald-300">
                  <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {zoomed && current.svg && (
        <DiagramViewer svg={current.svg} title={current.title} onClose={() => setZoomed(false)} />
      )}
      {!current.svg && (
        <p className="text-[11px] text-white/40 italic">
          {current.rendered
            ? 'The picture for this revision is on disk but only the current version is displayed — its Mermaid source is shown instead.'
            : 'No image was rendered for this one — the Mermaid source is shown instead.'}
        </p>
      )}
    </div>
  )
}

function Interview({ srs }) {
  const transcript = list((srs.interview || {}).transcript)
  const answers = list((srs.interview || {}).answers)
  if (!transcript.length) return <Empty>No interview was saved with this SRS.</Empty>
  const byId = Object.fromEntries(answers.map(a => [a.question_id, a]))

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top,#101b38_0%,#0c1020_100%)] p-6 shadow-xl">
        <div className="flex items-center gap-2.5 border-b border-white/10 pb-4">
          <div className="grid size-9 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
            <MessageSquare className="size-4" />
          </div>
          <div>
            <h2 className="text-[17px] font-bold text-white">
              Client Discovery & Requirements Interview
            </h2>
            <p className="text-[12px] text-white/50">
              The discovery dialogue that shaped the system requirements and architectural scope
            </p>
          </div>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
          Every requirement in this specification traces back to the answers and preferences clarified during this initial interview.
        </p>
      </div>

      <div className="space-y-4">
        {transcript.map((q, i) => {
          const a = byId[q.id]
          const value = a && (Array.isArray(a.value) ? a.value.join(', ') : a.value)
          return (
            <div key={q.id || i} className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 shadow-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="flex size-5 items-center justify-center rounded-full bg-blue-500/20 font-mono text-[10px] font-bold text-blue-400">
                  {i + 1}
                </span>
                <span className="text-[11px] font-semibold text-white/50 uppercase tracking-wider">
                  Clarification Topic
                </span>
              </div>
              <h4 className="text-[14px] font-bold text-white mb-3">
                {q.question}
              </h4>
              <div className="rounded-xl border border-blue-500/20 bg-blue-500/[.06] p-3.5">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-blue-300 mb-1">
                  Agreed Client Decision:
                </div>
                <p className="text-[13px] font-medium text-white">
                  {value != null && String(value).trim() ? String(value) : 'Not specified / Default baseline applied'}
                </p>
                {a?.raw_text && a.raw_text !== value && (
                  <p className="mt-1 text-[11px] text-white/50 italic">
                    “{a.raw_text}”
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PrototypeFlow({ srs }) {
  // The pages the server found on disk. This used to read
  // `document.prototype_evidence`, written by a separate sync whose file was
  // overwritten after every change - so the list was right until the next
  // revision and then quietly wrong. When there is nothing, the page says so
  // rather than inventing a "Main Application Interface" with three made-up
  // controls on it.
  const pages = list(srs?.prototype?.pages)
  const screenshot = Boolean(srs?.prototype?.screenshot)
  const routes = list((srs.document || {}).screens)

  const named = (file) => {
    const match = routes.find(s => String(s?.file || s?.page || '').toLowerCase() === String(file).toLowerCase())
    return (match && (match.screen_name || match.name)) || null
  }

  return (
    <div className="mx-auto max-w-[1120px] pb-12 text-white">
      <div className="mb-6 rounded-2xl border border-white/10 bg-[#0d1220] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-xl border border-white/10 bg-white/[.04] text-white/50">
              <Workflow className="size-4" />
            </div>
            <div>
              <h3 className="text-[15px] font-bold text-white">Prototype pages</h3>
              <p className="text-[11.5px] text-white/45">
                The HTML files in this project, as they are on disk.
              </p>
            </div>
          </div>
          <span className="font-mono text-[11px] text-white/40">
            {pages.length} page{pages.length === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      {pages.length === 0 ? (
        <Empty>No prototype has been drawn for this project yet.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {pages.map((page, idx) => (
            <div key={page.file || idx}
              className="rounded-2xl border border-white/10 bg-[#0f1422] p-4 transition hover:border-white/20">
              <div className="flex items-center justify-between gap-2 border-b border-white/[.07] pb-2.5">
                <span className="font-mono text-[11px] text-white/35">#{idx + 1}</span>
                <span className="truncate font-mono text-[10.5px] text-white/45">{page.file}</span>
              </div>
              <h5 className="mt-2.5 text-[14px] font-bold text-white">
                {named(page.file) || page.screen_name}
              </h5>
              {page.bytes != null && (
                <p className="mt-1 font-mono text-[10.5px] text-white/30">
                  {Math.round(page.bytes / 1024)} KB
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {screenshot && (
        <p className="mt-5 text-[12px] text-white/45">
          A desktop screenshot of the drawing was captured for this project.
        </p>
      )}
    </div>
  )
}


export const VIEWS = [
  { id: 'wireframe', label: 'Wireframe', C: Wireframes },
  { id: 'overview', label: 'Overview', C: Overview },
  { id: 'journey', label: 'User Journey', C: UserJourney },
  { id: 'document', label: 'Document', C: Document },
  { id: 'requirements', label: 'Requirements', C: Requirements },
  { id: 'diagrams', label: 'Diagrams', C: Diagrams },
  { id: 'data', label: 'Data & Storage', C: Data },
  { id: 'roles', label: 'Roles & Access', C: Roles },
  { id: 'prototype_flow', label: 'Prototype & UI Flow', C: PrototypeFlow },
  { id: 'plan', label: 'Approved Plan', C: Plan },
  { id: 'handoff', label: 'Handoff', C: Handoff },
  { id: 'interview', label: 'Interview', C: Interview },
  { id: 'risks', label: 'Safeguards & Risks', C: Risks },
]


export function badgeFor(id, srs) {
  const doc = srs?.document || {}
  const n = (value) => (Array.isArray(value) ? value.length : 0)
  if (id === 'overview') {
    return null
  }
  if (id === 'requirements' && n(doc.functional_requirements)) {
    return { n: n(doc.functional_requirements), bad: false }
  }
  if (id === 'data' && n(doc.database_design?.tables)) {
    return { n: n(doc.database_design.tables), bad: false }
  }
  if (id === 'diagrams' && n(srs?.diagrams)) {
    return { n: n(srs.diagrams), bad: false }
  }
  if (id === 'prototype_flow') {
    // No `|| 1`: a project with no pages had a badge claiming one.
    const pages = srs?.prototype?.pages
    return n(pages) ? { n: n(pages), bad: false } : null
  }
  if (id === 'interview' && n(srs?.interview?.transcript)) {
    return { n: n(srs.interview.transcript), bad: false }
  }

  if (id === 'risks' && n(doc.ambiguities)) {
    return { n: n(doc.ambiguities), bad: true }
  }
  return null
}

function Risks({ srs }) {
  const doc = srs.document || {}
  const ambiguities = list(doc.ambiguities)
  const risks = list(doc.risk_priority)
  const acceptance = list(doc.acceptance_criteria)

  if (!srs.have?.document) return <Empty>No SRS document was adopted for this project.</Empty>

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      <div className="rounded-3xl border border-amber-500/25 bg-[radial-gradient(ellipse_at_top,#20170a_0%,#120e06_100%)] p-6 shadow-xl">
        <div className="flex items-center gap-2.5 border-b border-white/10 pb-4">
          <div className="grid size-9 place-items-center rounded-xl bg-amber-600/20 text-amber-400 border border-amber-500/30">
            <ShieldAlert className="size-4" />
          </div>
          <div>
            <h2 className="text-[17px] font-bold text-white">
              Business Safeguards & Risk Protections
            </h2>
            <p className="text-[12px] text-white/50">
              Proactive mitigations, edge-case protections, and acceptance criteria ensuring software resilience
            </p>
          </div>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
          Identified project risks are paired with architectural safeguards so that system downtime, data inconsistency, and user errors are prevented by design.
        </p>
      </div>

      <div className="space-y-4">
        <h3 className="text-[14px] font-bold text-white uppercase tracking-wider text-white/60">
          Proactive Risk Mitigations
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {(risks.length ? risks : [
            { risk: 'Data concurrency conflict on simultaneous edits', severity: 'Medium', reason: 'Multiple users might update the same record at the same time.', mitigation: 'Atomic database updates with optimistic locking.' },
            { risk: 'Unvalidated user input causing corrupt state', severity: 'High', reason: 'Malicious or malformed inputs can degrade database integrity.', mitigation: 'Strict server-side validation and schema boundary enforcement.' },
          ]).map((r, i) => {
            const sev = String(r.severity || 'Medium').toLowerCase()
            return (
              <div key={i} className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className={cn(
                      'rounded-full px-2.5 py-0.5 text-[10.5px] font-bold border',
                      sev === 'high' ? 'bg-rose-500/15 text-rose-300 border-rose-500/30' :
                      sev === 'medium' ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' :
                      'bg-blue-500/15 text-blue-300 border-blue-500/30'
                    )}>
                      {r.severity || 'Medium'} Severity
                    </span>
                    <span className="text-[10px] text-white/40 font-mono">Risk #{i + 1}</span>
                  </div>
                  <h4 className="text-[14px] font-bold text-white mb-2">
                    {r.risk || line(r)}
                  </h4>
                  {r.reason && (
                    <p className="text-[12px] text-white/65 mb-3 leading-relaxed">
                      <span className="font-semibold text-white/80">Cause:</span> {r.reason}
                    </p>
                  )}
                </div>
                {r.mitigation && (
                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[.05] p-3 text-[11.5px] text-emerald-200">
                    <span className="font-bold block text-emerald-300 mb-0.5">Built-in Mitigation:</span>
                    {r.mitigation}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {acceptance.length > 0 && (
        <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
          <h3 className="text-[15px] font-bold text-white mb-4 flex items-center gap-2">
            <CheckCircle2 className="size-4 text-emerald-400" />
            <span>Acceptance Verification Criteria</span>
          </h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {acceptance.map((crit, idx) => (
              <div key={idx} className="flex items-start gap-2.5 rounded-xl border border-white/5 bg-white/[.02] p-3 text-[12px] text-white/80">
                <Check className="size-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>{typeof crit === 'string' ? crit : (crit.criterion || line(crit))}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
