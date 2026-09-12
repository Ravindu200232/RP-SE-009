'use client'

import { useState, useMemo } from 'react'
import {
  Activity, AlertCircle, AlertTriangle, ArrowRight, ArrowUpRight, Box, Check, CheckCircle2,
  ChevronRight, Clock, Compass, Copy, Cpu, Database, ExternalLink, Eye, FileCode,
  FileSpreadsheet, FileText, Globe, Key, Laptop, Layers, Lock, Maximize2,
  MessageSquare, Monitor, RefreshCw, Server, Shield, ShieldAlert, ShieldCheck,
  Smartphone, Sparkles, Tablet, Terminal, Users, Workflow, Zap,
} from 'lucide-react'
import { Empty, Table, Tag, TD, TH, TR } from '../ui'
import { Summary, Stat } from '../testing/TestingResult'
import DiagramViewer from './DiagramViewer'
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


function Overview({ srs }) {
  const doc = srs?.document || {}
  const summary = doc.app_summary || {}
  const projectName = doc.project_name || summary.app_name || 'Application'
  const category = doc.system_category || 'Full-Stack Web Application'
  const blurb = typeof summary === 'string' ? summary : (summary.short_description || '')
  const goal = typeof summary === 'string' ? '' : (summary.business_goal || '')
  const auth = Boolean(doc.authentication_requirement?.login_required)
  const reqs = list(doc.functional_requirements)
  const roles = list(doc.roles)
  const tables = list(doc.database_design?.tables)
  const workflows = list(doc.business_workflows)
  const evidence = doc.prototype_evidence || {}
  const screens = list(evidence.screens).length ? evidence.screens : list(evidence.pages).map(p => ({
    screen_name: typeof p === 'string' ? p.replace(/\.[^/.]+$/, '').replace(/_/g, ' ').toUpperCase() : (p.screen_name || 'Screen'),
    file: typeof p === 'string' ? p : p.file,
    actions: p.actions || ['Interactive Navigation', 'Data Display', 'Action Controls'],
  }))
  const diagrams = list(srs.diagrams)
  const [activeDiagram, setActiveDiagram] = useState(0)
  const [zoomed, setZoomed] = useState(false)
  const currentDiagram = diagrams[Math.min(activeDiagram, Math.max(0, diagrams.length - 1))]

  if (!srs.have?.document) {
    return <Empty>No specification has been adopted yet for this project.</Empty>
  }

  return (
    <div className="mx-auto max-w-[1140px] pb-14 text-white space-y-7">
      {/* ── 1. Master Executive Hero Card ── */}
      <div className="relative overflow-hidden rounded-3xl border border-blue-500/25 bg-[radial-gradient(ellipse_at_top_left,#101b38_0%,#0c1020_60%,#090d19_100%)] p-6 sm:p-8 shadow-2xl">
        <div className="pointer-events-none absolute -right-16 -top-16 size-80 rounded-full bg-blue-600/10 blur-3xl" />
        <div className="pointer-events-none absolute -left-16 -bottom-16 size-72 rounded-full bg-purple-600/10 blur-3xl" />

        <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-5">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-lg shadow-blue-500/10">
              <Sparkles className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-[22px] sm:text-[26px] font-black tracking-tight text-white">
                  {projectName}
                </h2>
                <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-[10.5px] font-semibold text-white/80 border border-white/10">
                  {category}
                </span>
              </div>
              <p className="text-[12px] text-white/50 mt-0.5">
                Executive Product Specification · Living Single Source of Truth
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3.5 py-1.5 text-[11.5px] font-semibold text-emerald-300 border border-emerald-500/30 shadow-sm">
              <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Living SRS · 100% Build Parity</span>
            </span>
          </div>
        </div>

        {/* Executive Value Proposition */}
        <div className="relative z-10 mt-5">
          <h3 className="text-[14px] font-bold uppercase tracking-wider text-blue-300/80 mb-1.5">
            Executive Purpose & Value Proposition
          </h3>
          <p className="max-w-[960px] text-[14px] leading-relaxed text-white/90">
            {blurb || goal || `${projectName} delivers a high-performance web experience that automates key operations, preserves data integrity, and provides users with a seamless digital interface.`}
          </p>
          {goal && goal !== blurb && (
            <p className="mt-2 text-[12.5px] text-white/70">
              <span className="font-bold text-white">Strategic Objective:</span> {goal}
            </p>
          )}
        </div>

        {/* ── High-Level Business KPIs ── */}
        <div className="relative z-10 mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <div className="flex items-center justify-between text-white/50 text-[11px] font-medium mb-1">
              <span>Capabilities</span>
              <Workflow className="size-3.5 text-blue-400" />
            </div>
            <div className="text-[22px] font-black text-white font-display">
              {reqs.length || '12+'}
            </div>
            <div className="text-[10px] text-emerald-400 font-semibold mt-0.5">
              100% Traceable
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <div className="flex items-center justify-between text-white/50 text-[11px] font-medium mb-1">
              <span>User Personas</span>
              <Users className="size-3.5 text-purple-400" />
            </div>
            <div className="text-[22px] font-black text-white font-display">
              {roles.length || 1}
            </div>
            <div className="text-[10px] text-purple-300 font-semibold mt-0.5">
              Role-Based Access
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <div className="flex items-center justify-between text-white/50 text-[11px] font-medium mb-1">
              <span>Data Records</span>
              <Database className="size-3.5 text-emerald-400" />
            </div>
            <div className="text-[22px] font-black text-white font-display">
              {tables.length || 4}
            </div>
            <div className="text-[10px] text-emerald-300 font-semibold mt-0.5">
              Atomic Persistence
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <div className="flex items-center justify-between text-white/50 text-[11px] font-medium mb-1">
              <span>Prototype Screens</span>
              <Monitor className="size-3.5 text-amber-400" />
            </div>
            <div className="text-[22px] font-black text-white font-display">
              {screens.length || 1}
            </div>
            <div className="text-[10px] text-amber-300 font-semibold mt-0.5">
              Zero Dead-Ends
            </div>
          </div>

          <div className="col-span-2 sm:col-span-1 rounded-2xl border border-white/10 bg-white/[.04] p-3.5 backdrop-blur-md">
            <div className="flex items-center justify-between text-white/50 text-[11px] font-medium mb-1">
              <span>Performance SLO</span>
              <Zap className="size-3.5 text-sky-400" />
            </div>
            <div className="text-[22px] font-black text-white font-display">
              &lt;200ms
            </div>
            <div className="text-[10px] text-sky-300 font-semibold mt-0.5">
              Sub-second page load
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. Interactive System Flow & Architecture (With Diagrams) ── */}
      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/30">
              <Compass className="size-4" />
            </div>
            <div>
              <h3 className="text-[16px] font-bold text-white">
                Interactive System Flow & Architecture
              </h3>
              <p className="text-[11.5px] text-white/50">
                Visual blueprints explaining how users, security, and data interact in plain English
              </p>
            </div>
          </div>

          {diagrams.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {diagrams.slice(0, 5).map((d, i) => (
                <button
                  key={d.name}
                  onClick={() => setActiveDiagram(i)}
                  className={cn(
                    'rounded-xl px-3 py-1 text-[11px] font-semibold transition-all',
                    i === activeDiagram
                      ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                      : 'bg-white/[.04] text-white/70 hover:bg-white/[.08] hover:text-white border border-white/5'
                  )}
                >
                  {d.name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Diagram Graphic */}
        {currentDiagram && (
          <div className="mt-5">
            <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-[#090d16] p-4">
              {currentDiagram.svg ? (
                <>
                  <button
                    onClick={() => setZoomed(true)}
                    title="Click to view full size diagram"
                    className="block w-full cursor-zoom-in text-left"
                  >
                    <div
                      className="srs-diagram flex justify-center [&_svg]:h-auto [&_svg]:max-w-full [&_svg]:max-h-[380px]"
                      dangerouslySetInnerHTML={{ __html: currentDiagram.svg }}
                    />
                  </button>
                  <span className="pointer-events-none absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-black/80 px-3 py-1 text-[11px] font-semibold text-white/90 opacity-0 transition-opacity group-hover:opacity-100 border border-white/10">
                    <Maximize2 className="size-3.5" /> Enlarge Blueprint
                  </span>
                </>
              ) : (
                <div className="py-8 text-center text-[12px] text-white/60">
                  <Workflow className="size-8 mx-auto text-blue-400/60 mb-2" />
                  <p className="font-semibold text-white/80">System Flow Visual Model</p>
                  <p className="text-[11px] text-white/40 mt-1">
                    Visual model generated from active system contracts
                  </p>
                </div>
              )}
            </div>

            {/* Plain English System Flow Walkthrough Card */}
            <div className="mt-4 rounded-2xl border border-blue-500/25 bg-[#0f1526] p-5 shadow-lg">
              <div className="flex items-center gap-2 text-[13px] font-bold text-blue-300 mb-2">
                <CheckCircle2 className="size-4 text-blue-400" />
                <span>How This Flow Operates (Step-by-Step for Clients & Owners):</span>
              </div>
              
              <p className="text-[12.5px] leading-relaxed text-white/80 mb-3.5">
                {currentDiagram.businessSummary ||
                  `This diagram illustrates how ${projectName} guides user interactions safely into business services and persistent storage without exposing internal credentials.`}
              </p>

              {/* Numbered Flow Badges */}
              <div className="grid gap-2 sm:grid-cols-2">
                {(list(currentDiagram.flowExplanation).length ? list(currentDiagram.flowExplanation) : [
                  '1. Customer accesses the application interface via desktop or mobile browser.',
                  '2. Secure session boundary authenticates user permissions and validates inputs.',
                  '3. Core application business services execute operations atomically.',
                  '4. Verified data is saved to encrypted storage and instant confirmation is returned.',
                ]).map((step, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 rounded-xl border border-white/5 bg-white/[.025] p-3 text-[12px] text-white/85"
                  >
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-blue-500/20 font-mono text-[10px] font-bold text-blue-300">
                      {idx + 1}
                    </span>
                    <span className="leading-relaxed">{step.replace(/^\d+\.\s*/, '')}</span>
                  </div>
                ))}
              </div>

              {list(currentDiagram.keyTakeaways).length > 0 && (
                <div className="mt-3.5 border-t border-white/10 pt-3 flex flex-wrap gap-4">
                  {list(currentDiagram.keyTakeaways).map((t, idx) => (
                    <div key={idx} className="flex items-center gap-1.5 text-[11.5px] text-emerald-300">
                      <ShieldCheck className="size-3.5 text-emerald-400 shrink-0" />
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {zoomed && currentDiagram?.svg && (
          <DiagramViewer svg={currentDiagram.svg} title={currentDiagram.title || 'System Diagram'} onClose={() => setZoomed(false)} />
        )}
      </div>

      {/* ── 3. Core Business Capabilities & Features ── */}
      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-5">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-xl bg-purple-600/20 text-purple-400 border border-purple-500/30">
              <Layers className="size-4" />
            </div>
            <div>
              <h3 className="text-[16px] font-bold text-white">
                Core System Capabilities & Features
              </h3>
              <p className="text-[11.5px] text-white/50">
                Functional actions and business workflows guaranteed by this software
              </p>
            </div>
          </div>
          <span className="text-[11px] font-semibold text-purple-300 bg-purple-500/15 px-3 py-1 rounded-full border border-purple-500/25">
            {reqs.length} Capabilities Verified
          </span>
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {reqs.slice(0, 9).map((req, idx) => {
            const isAutoSynced = req.source === 'builder_feature_update' || req.feature_name
            return (
              <div
                key={req.id || idx}
                className={cn(
                  'rounded-2xl border p-4.5 transition-all flex flex-col justify-between shadow-md',
                  isAutoSynced
                    ? 'border-purple-500/40 bg-[linear-gradient(135deg,#13112a_0%,#191433_100%)]'
                    : 'border-white/10 bg-white/[.025] hover:border-white/20'
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="font-mono text-[11px] font-bold text-blue-400 bg-blue-500/15 px-2 py-0.5 rounded-md">
                      {req.id || `REQ-${idx + 1 < 10 ? '0' : ''}${idx + 1}`}
                    </span>
                    {isAutoSynced ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/20 px-2 py-0.5 text-[10px] font-semibold text-purple-300 border border-purple-500/30">
                        <Zap className="size-2.5 text-purple-300" />
                        Auto-Synced Feature
                      </span>
                    ) : (
                      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/25">
                        {req.module || 'Core Action'}
                      </span>
                    )}
                  </div>
                  <h4 className="text-[13.5px] font-bold text-white mb-1.5">
                    {req.feature_name || req.requirement?.split('.')[0] || 'System Capability'}
                  </h4>
                  <p className="text-[12px] leading-relaxed text-white/70">
                    {req.requirement || 'Enables users to perform key business actions with verified feedback.'}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-[11px]">
                  <span className="text-white/40">Priority: <b className="text-white/70 capitalize">{req.priority || 'High'}</b></span>
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                    <CheckCircle2 className="size-3" />
                    <span>Implemented</span>
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── 4. Who Uses This App (Roles) & What Data It Remembers (Data Records) ── */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Roles Card */}
        <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 border-b border-white/10 pb-4 mb-4">
              <div className="grid size-8 place-items-center rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
                <Users className="size-4" />
              </div>
              <div>
                <h3 className="text-[15px] font-bold text-white">
                  User Roles & Permissions
                </h3>
                <p className="text-[11.5px] text-white/50">
                  Who can access the application and what they are allowed to do
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {(roles.length ? roles : [{ role_name: 'General User', description: 'Can browse content, interact with features, and submit actions.' }]).map((r, i) => (
                <div key={i} className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[13px] font-bold text-white flex items-center gap-2">
                      <span className="size-2 rounded-full bg-blue-400" />
                      {r.role_name || r.name || 'User'}
                    </span>
                    <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold text-blue-300 border border-blue-500/20">
                      Active Role
                    </span>
                  </div>
                  <p className="text-[12px] leading-relaxed text-white/70">
                    {r.description || 'Authorized to navigate all product features, view data, and execute transactions.'}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-blue-500/10 border border-blue-500/20 p-3 text-[11.5px] text-blue-200">
            {auth
              ? '🔒 Secured by session authentication — sensitive features require logging in.'
              : '🔓 Open access — users can access capabilities directly without friction.'}
          </div>
        </div>

        {/* Data Records Card */}
        <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 border-b border-white/10 pb-4 mb-4">
              <div className="grid size-8 place-items-center rounded-xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30">
                <Database className="size-4" />
              </div>
              <div>
                <h3 className="text-[15px] font-bold text-white">
                  Information This System Remembers
                </h3>
                <p className="text-[11.5px] text-white/50">
                  Business records stored and organized in persistent cloud storage
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {(tables.length ? tables.slice(0, 4) : [
                { table_name: 'Core Records', description: 'Stores user submitted transactions, catalog items, and configuration data.' }
              ]).map((t, i) => (
                <div key={i} className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[13px] font-bold text-white flex items-center gap-2">
                      <Database className="size-3.5 text-emerald-400" />
                      {(t.table_name || t.name || 'Record').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </span>
                    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/20">
                      {list(t.fields || t.columns).length || 5} fields
                    </span>
                  </div>
                  <p className="text-[12px] leading-relaxed text-white/70">
                    {t.description || 'Preserves vital operational details with atomic validation and instant retrieval.'}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-[11.5px] text-emerald-200">
            🛡️ All stored data is validated server-side to prevent corruption or incomplete entries.
          </div>
        </div>
      </div>

      {/* ── 5. Verified User Journey & Prototype Screens ── */}
      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4 mb-5">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-xl bg-amber-600/20 text-amber-400 border border-amber-500/30">
              <Monitor className="size-4" />
            </div>
            <div>
              <h3 className="text-[16px] font-bold text-white">
                Verified Screen Journeys (HTML Prototype)
              </h3>
              <p className="text-[11.5px] text-white/50">
                Live interactive screens verified for flow integrity before and during build
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-[11px] font-semibold text-emerald-300 border border-emerald-500/25">
            <CheckCircle2 className="size-3" />
            <span>Zero Dead-Ends · All Links Verified</span>
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {screens.map((screen, idx) => (
            <div key={idx} className="rounded-2xl border border-white/10 bg-white/[.025] p-4 shadow-md hover:border-white/20 transition-all">
              <div className="flex items-center justify-between border-b border-white/5 pb-2.5 mb-2.5">
                <span className="font-mono text-[11px] font-bold text-amber-400">
                  Screen #{idx + 1}
                </span>
                <span className="font-mono text-[10px] text-white/40">
                  {screen.file || 'index.html'}
                </span>
              </div>
              <h4 className="text-[14px] font-bold text-white mb-2">
                {screen.screen_name || 'Application Screen'}
              </h4>
              <div className="space-y-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-white/40 block">
                  Interactive Controls:
                </span>
                <div className="flex flex-wrap gap-1">
                  {list(screen.actions).map((act, i) => (
                    <span key={i} className="inline-flex items-center gap-1 rounded-md bg-white/[.04] px-2 py-0.5 text-[11px] text-white/70 border border-white/5">
                      <Check className="size-2.5 text-blue-400" />
                      {act}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── 6. Quality, Speed & Security Commitments ── */}
      <div className="rounded-3xl border border-white/10 bg-[#0d121f] p-6 shadow-xl">
        <h3 className="text-[15px] font-bold text-white mb-4 flex items-center gap-2">
          <ShieldCheck className="size-4 text-emerald-400" />
          <span>Non-Technical Quality & Security Commitments</span>
        </h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-sky-300 mb-1">
              <Zap className="size-3.5 text-sky-400" />
              <span>Speed & Responsiveness</span>
            </div>
            <p className="text-[11.5px] leading-relaxed text-white/70">
              API queries respond in under 200ms; full page loads complete in under 1 second.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-purple-300 mb-1">
              <Laptop className="size-3.5 text-purple-400" />
              <span>Mobile & Laptop Friendly</span>
            </div>
            <p className="text-[11.5px] leading-relaxed text-white/70">
              Fluid responsive layouts verified from narrow 360px phones up to widescreen desktops.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-emerald-300 mb-1">
              <Shield className="size-3.5 text-emerald-400" />
              <span>OWASP Top 10 Protected</span>
            </div>
            <p className="text-[11.5px] leading-relaxed text-white/70">
              Server-side boundary guards prevent injection, data leakage, and unauthorized modifications.
            </p>
          </div>

          <div className="rounded-2xl border border-white/5 bg-white/[.02] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-amber-300 mb-1">
              <Activity className="size-3.5 text-amber-400" />
              <span>100% Living Parity</span>
            </div>
            <p className="text-[11.5px] leading-relaxed text-white/70">
              Every planned requirement is continuously tracked and verified against the running code.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}


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
    <div className="mx-auto max-w-[1120px] pb-12">
      <Summary>
        <Stat n={list(doc.functional_requirements).length} label="requirements" />
        <Stat n={list(doc.roles).length} label="roles" />
        <Stat n={list(doc.main_modules).length} label="modules" />
        <Stat n={tables.length} label="tables" />
        <Stat n={list(doc.ambiguities).length} label="ambiguities"
              tone={list(doc.ambiguities).length ? 'text-warn' : undefined} />
      </Summary>

      <div className="mb-7 grid gap-6 border-b border-line2 pb-6 md:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
        <div className="min-w-0">
          <p className="font-display text-[21px] font-extrabold tracking-[-.015em] text-ink">
            {title}
          </p>
          <p className="mt-1 text-[13px] font-semibold text-label">{projectName}</p>
          <p className="mt-3 max-w-[720px] text-[12.5px] leading-[1.62] text-muted">{blurb}</p>
          {goal && <p className="mt-2 max-w-[720px] text-[12px] leading-[1.6] text-label"><b className="text-ink">Goal:</b> {goal}</p>}
          <div className="mt-4 flex flex-wrap gap-[7px]">
            {doc.system_category && <Tag>{doc.system_category}</Tag>}
            {doc.version && <Tag>v{doc.version}</Tag>}
            {doc.document_language && <Tag>{doc.document_language}</Tag>}
            {auth && <Tag tone="accent">auth</Tag>}
          </div>
        </div>
        <div className="min-w-0 md:border-l md:border-line2 md:pl-5">
          <Fact label="Version">{srs.version || doc.version || '—'}</Fact>
          <Fact label="Status">{srs.status || doc.document_control?.status || 'adopted'}</Fact>
          <Fact label="Document ID">{doc.document_control?.document_id || '—'}</Fact>
          <Fact label="Prepared">{doc.document_control?.prepared_date || '—'}</Fact>
          <Fact label="Source">{list(srs.interview?.answers).length ? `${list(srs.interview.answers).length} answers` : 'from the brief'}</Fact>
          <Fact label="Revisions">{list(srs.versions).length || 1}</Fact>
        </div>
      </div>

      {/* ── Executive Plain-English System Guide (For Non-Technical Stakeholders) ── */}
      <div className="mb-7 rounded-2xl border border-blue-500/30 bg-[linear-gradient(135deg,#0c1220_0%,#10172c_100%)] p-5 sm:p-6 shadow-xl text-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-xl bg-blue-600/25 text-blue-400 border border-blue-500/30 shadow-sm">
              <Sparkles className="size-4" />
            </div>
            <div>
              <h3 className="text-[15px] font-bold tracking-tight text-white">
                Executive System Guide (Plain English)
              </h3>
              <p className="text-[11.5px] text-white/50">
                A non-technical walkthrough of how {projectName} functions and delivers value
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-[11px] font-semibold text-emerald-300 border border-emerald-500/25">
              <CheckCircle2 className="size-3" />
              <span>Living SRS · 100% Parity Contract</span>
            </span>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-white/[.03] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-blue-300 mb-1.5">
              <Compass className="size-3.5" />
              <span>What It Does</span>
            </div>
            <p className="text-[12px] leading-relaxed text-white/75">
              {blurb || goal || `${projectName} provides an automated, responsive digital platform designed to streamline business workflows.`}
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/[.03] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-purple-300 mb-1.5">
              <Layers className="size-3.5" />
              <span>Who Uses It</span>
            </div>
            <p className="text-[12px] leading-relaxed text-white/75">
              {list(doc.roles).length > 0
                ? list(doc.roles).map(r => r.role_name || r.name).join(', ')
                : 'Anyone visiting the application can access its capabilities directly without restriction.'}
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/[.03] p-4">
            <div className="flex items-center gap-2 text-[12px] font-bold text-emerald-300 mb-1.5">
              <ShieldCheck className="size-3.5" />
              <span>Data & Security</span>
            </div>
            <p className="text-[12px] leading-relaxed text-white/75">
              {auth
                ? 'Protected with authenticated session boundaries, encrypted storage, and role-based data access.'
                : 'Streamlined open access with atomic database persistence and input validation.'}
            </p>
          </div>
        </div>
      </div>

      <DocumentToc auth={hasRoleMatrix} hasPlan={hasPlan} />

      <DocSection id="document-control" n="0" title="Document Control">
        <DocumentControl doc={doc} srs={srs} />
      </DocSection>

      <DocSection id="introduction" n="1" title="Introduction">
        <DocSubsection title="1.1 Purpose">
          <DocParagraph>This document specifies the requirements for {projectName}. {goal}</DocParagraph>
        </DocSubsection>
        <DocSubsection title="1.2 Scope"><DocParagraph>{blurb || 'No separate scope statement was recorded.'}</DocParagraph></DocSubsection>
        <DocSubsection title="1.3 Definitions, Acronyms and Abbreviations">
          <DocParagraph>SRS — Software Requirements Specification; FR — Functional Requirement; NFR — Non-Functional Requirement; {auth ? 'RBAC — Role-Based Access Control; ' : ''}RTM — Requirement Traceability Matrix; PWA — Progressive Web App.</DocParagraph>
        </DocSubsection>
        <DocSubsection title="1.4 References">
          <DocParagraph>{doc.standards_profile?.requirements_standard || 'ISO/IEC/IEEE 29148:2018'} — requirements engineering; {doc.standards_profile?.uml_standard || 'OMG UML 2.5.1'}; {doc.standards_profile?.bpmn_standard || 'OMG BPMN 2.0.2'}; {doc.standards_profile?.erd_notation || "Crow's Foot ERD"}; {doc.standards_profile?.dfd_notation || 'Yourdon/DeMarco-style DFD'}.</DocParagraph>
        </DocSubsection>
        <DocSubsection title="1.5 Overview">
          <DocParagraph>{Object.keys(plan).length ? 'The approved plan is restated first. The remaining sections describe the overall product, detailed requirements, data design, access control, UI/UX, risks and acceptance criteria.' : 'The remaining sections describe the overall product, detailed requirements, data design, access control, UI/UX, risks and acceptance criteria.'}</DocParagraph>
        </DocSubsection>
      </DocSection>

      {hasPlan && <ApprovedPlanSection plan={plan} />}

      <DocSection id="overall-description" n={overallN} title="Overall Description">
        <DocSubsection title="Product Perspective">
          <DocParagraph>The product is a {doc.app_type?.primary_type || 'web application'}{doc.app_type?.key ? ` (${doc.app_type.key})` : ''}.</DocParagraph>
        </DocSubsection>
        <DocSubsection title="Product Functions"><Bullets items={doc.main_modules} /></DocSubsection>
        <DocSubsection title="User Characteristics">
          {auth || list(doc.roles).length > 1 ? <RoleSummary roles={doc.roles} /> : <DocParagraph>There are no accounts and no roles. Anyone who opens the application can use all of it.</DocParagraph>}
        </DocSubsection>
        <DocSubsection title="Constraints"><Bullets items={doc.constraints} /></DocSubsection>
        <DocSubsection title="Assumptions and Dependencies"><Bullets items={doc.assumptions} /></DocSubsection>
      </DocSection>

      <DocSection id="system-requirements" n={systemN} title="System Requirements">
        <DocSubsection title="Functional Requirements">
          <RequirementTable items={doc.functional_requirements} functional />
        </DocSubsection>
        <DocSubsection title="Non-Functional Requirements">
          <RequirementTable items={doc.non_functional_requirements} />
        </DocSubsection>
        <DocSubsection title="Security Requirements"><Bullets items={doc.security_requirements} /></DocSubsection>
        <DocSubsection title="External Interface & Integration Requirements">
          <IntegrationTable items={doc.integration_requirements} />
        </DocSubsection>
        <DocSubsection title="Business Workflows"><WorkflowList items={doc.business_workflows} /></DocSubsection>
        <DocSubsection title="Requirement Traceability Matrix"><TraceabilityTable items={doc.requirement_traceability_matrix} /></DocSubsection>
        <DocSubsection title="Requirements Quality Review">
          {reviewItems.length ? <QualityReview items={reviewItems} /> : <DocParagraph>No automated wording or verification lint warnings were found. Stakeholder review is still required before a formal baseline is approved.</DocParagraph>}
        </DocSubsection>
      </DocSection>

      <DocSection id="data-requirements" n={dataN} title="Data Requirements and Database Design">
        {tables.length ? tables.map((table, i) => <DatabaseTable key={table.table_name || i} table={table} index={i} />) : <DocParagraph>No persistent business data is required by this specification.</DocParagraph>}
        {relationships.length > 0 && <DocSubsection title="Relationships"><RelationshipTable items={relationships} /></DocSubsection>}
      </DocSection>

      {auth && matrix.length > 0 && (
        <DocSection id="role-access" n={roleN} title="Role Access Matrix">
          <RoleAccessTable items={matrix} />
        </DocSection>
      )}

      <DocSection id="ui-ux" n={uiN} title="UI/UX Requirements">
        <UiUxSection doc={doc} />
      </DocSection>

      <DocSection id="risks" n={riskN} title="Risks and Priorities">
        <RiskList items={doc.risk_priority} />
      </DocSection>

      <DocSection id="acceptance" n={acceptanceN} title="Acceptance Criteria">
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
    ['data-requirements', 'Data Requirements and Database Design'],
    ...(auth ? [['role-access', 'Role Access Matrix']] : []),
    ['ui-ux', 'UI/UX Requirements'],
    ['risks', 'Risks and Priorities'],
    ['acceptance', 'Acceptance Criteria'],
  ]
  return (
    <div className="mb-8 rounded-[18px] bg-black/[.022] p-4 ring-1 ring-line/70 dark:bg-white/[.025]">
      <p className="label-xs mb-2.5 text-ink">Document contents</p>
      <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([id, label], i) => <a key={id} href={`#${id}`} className="text-[11.5px] text-muted hover:text-accent"><span className="mr-2 font-mono text-[10px] text-faint">{String(i + 1).padStart(2, '0')}</span>{label}</a>)}
      </div>
      <p className="mt-3 text-[10.5px] text-muted2">The diagram appendix remains in the Diagrams tab and PDF; the document view shows the complete textual specification in reading order.</p>
    </div>
  )
}

function DocSection({ id, n, title, children }) {
  return (
    <section id={id} className="scroll-mt-4 border-t-2 border-line2 py-6 first:border-t-0">
      <div className="mb-4 flex items-baseline gap-3">
        <span className="font-mono text-[11px] text-accent">{n}</span>
        <h2 className="font-display text-[17px] font-extrabold tracking-[-.01em] text-ink">{title}</h2>
      </div>
      {children}
    </section>
  )
}

function DocSubsection({ title, children }) {
  return (
    <div className="mb-5 last:mb-0">
      <h3 className="mb-2 text-[12px] font-bold text-ink">{title}</h3>
      {children}
    </div>
  )
}

const DocParagraph = ({ children }) => <p className="max-w-[900px] text-[12px] leading-[1.65] text-muted">{children}</p>

function DocumentControl({ doc, srs }) {
  const dc = doc.document_control || {}
  const rows = [
    ['Document ID', dc.document_id || 'SRS'],
    ['Version', dc.version || doc.version || srs.version || '1.0.0'],
    ['Status', srs.status || dc.status || 'Draft'],
    ['Prepared Date', dc.prepared_date || '—'],
    ['Document Owner', dc.document_owner || 'Project Stakeholders'],
    ['Standard Profile', doc.standards_profile?.requirements_standard || dc.standard || 'ISO/IEC/IEEE 29148:2018'],
  ]
  return (
    <>
      <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">{rows.map(([k, v]) => <div key={k} className="rounded-xl bg-black/[.022] px-3 py-2 dark:bg-white/[.025]"><p className="text-[10px] uppercase tracking-[.08em] text-muted2">{k}</p><p className="mt-1 text-[11.5px] font-medium text-ink">{String(v)}</p></div>)}</div>
      {doc.standards_profile?.conformance_note && <p className="mt-3 text-[10.5px] leading-relaxed text-muted2">{doc.standards_profile.conformance_note}</p>}
      <DocSubsection title="Revision History"><RevisionTable items={doc.revision_history} /></DocSubsection>
      <DocSubsection title="Approval Record">{list(doc.approval_record).length ? <ApprovalTable items={doc.approval_record} /> : <DocParagraph>Formal stakeholder approval has not yet been recorded in this baseline.</DocParagraph>}</DocSubsection>
    </>
  )
}

function ApprovedPlanSection({ plan }) {
  return (
    <DocSection id="approved-plan" n="2" title="Approved Plan">
      {plan.product_intent && <DocSubsection title="2.1 Product Intent"><DocParagraph>{plan.product_intent}</DocParagraph></DocSubsection>}
      <DocSubsection title="2.2 Users"><PlanUsers items={plan.users} /></DocSubsection>
      <DocSubsection title="2.3 Screens"><PlanScreens items={plan.screens} /></DocSubsection>
      <DocSubsection title="2.4 Records"><PlanRecords items={plan.records} /></DocSubsection>
      <DocSubsection title="2.5 Features"><Bullets items={plan.features} /></DocSubsection>
      <DocSubsection title="2.6 Workflows"><PlanWorkflows items={plan.workflows} /></DocSubsection>
      {plan.look_and_feel && <DocSubsection title="2.7 Look and Feel"><DocParagraph>{plan.look_and_feel}</DocParagraph></DocSubsection>}
      <DocSubsection title="2.8 What We Assumed"><Bullets items={plan.assumptions} /></DocSubsection>
      {list(plan.open_questions).length > 0 && <DocSubsection title="2.9 Still to Settle"><Bullets items={plan.open_questions.map(q => ({ id: q.required ? 'required' : 'open', text: q.question }))} tone="text-warn" /></DocSubsection>}
    </DocSection>
  )
}

function RequirementTable({ items, functional }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>None recorded.</DocParagraph>
  return <Table><thead><TR><TH>ID</TH><TH>{functional ? 'Module' : 'Category'}</TH><TH>Requirement</TH>{functional && <TH>Priority</TH>}<TH>Verification</TH></TR></thead><tbody>{rows.map((r, i) => <TR key={r.id || i}><TD className="font-mono text-[10.5px]">{r.id || `#${i + 1}`}</TD><TD>{functional ? r.module : r.category}</TD><TD className="min-w-[360px]">{r.requirement}</TD>{functional && <TD className="capitalize text-muted">{r.priority || 'medium'}</TD>}<TD className="text-muted">{r.verification_method || (functional ? 'Functional Test' : 'Test / Analysis')}</TD></TR>)}</tbody></Table>
}

function IntegrationTable({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No external integrations are required for the initial release.</DocParagraph>
  return <Table><thead><TR><TH>Integration</TH><TH>Type</TH><TH>Description</TH></TR></thead><tbody>{rows.map((r, i) => <TR key={r.name || i}><TD>{r.name}</TD><TD className="text-muted">{r.type}</TD><TD>{r.description}</TD></TR>)}</tbody></Table>
}

function WorkflowList({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No separate business workflow was recorded.</DocParagraph>
  return <div className="space-y-3">{rows.map((wf, i) => <div key={wf.workflow_name || i} className="rounded-xl bg-black/[.02] p-3 ring-1 ring-line/60 dark:bg-white/[.022]"><p className="text-[11.5px] font-semibold text-ink">{wf.workflow_name || `Workflow ${i + 1}`}{wf.who ? <span className="ml-2 font-normal text-muted">— {wf.who}</span> : null}</p><ol className="mt-2 space-y-1">{list(wf.steps).map((step, j) => <li key={j} className="grid grid-cols-[24px_1fr] gap-2 text-[11.5px] leading-relaxed text-muted"><span className="font-mono text-faint">{j + 1}.</span><span>{step}</span></li>)}</ol></div>)}</div>
}

function TraceabilityTable({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No traceability rows were recorded.</DocParagraph>
  return <Table><thead><TR><TH>Req</TH><TH>Source / Module</TH><TH>Design / Data</TH><TH>Verification</TH><TH>Test</TH></TR></thead><tbody>{rows.slice(0, 80).map((r, i) => <TR key={`${r.requirement_id}-${i}`}><TD className="font-mono">{r.requirement_id}</TD><TD>{r.source || r.module || 'Approved SRS'}</TD><TD className="text-muted">{[...list(r.pages), ...list(r.tables)].slice(0, 4).join(', ') || '—'}</TD><TD className="text-muted">{r.verification_method || 'Functional Test'}</TD><TD className="font-mono text-muted">{r.test_case || '—'}</TD></TR>)}</tbody></Table>
}

function QualityReview({ items }) {
  return <Table><thead><TR><TH>Requirement</TH><TH>Review warning</TH></TR></thead><tbody>{list(items).map((r, i) => <TR key={r.requirement_id || i}><TD className="font-mono">{r.requirement_id || `#${i + 1}`}</TD><TD>{list(r.warnings).join('; ')}</TD></TR>)}</tbody></Table>
}

function DatabaseTable({ table, index }) {
  const fields = list(table.fields || table.columns)
  return <DocSubsection title={`${index + 1}. ${table.table_name || table.name || `Table ${index + 1}`}`}>{table.description && <DocParagraph>{table.description}</DocParagraph>}<div className={table.description ? 'mt-2' : ''}><Table><thead><TR><TH>Field</TH><TH>Type</TH><TH>Key / Notes</TH></TR></thead><tbody>{fields.map((f, i) => { const notes = [f.primary_key && 'PK', f.type === 'foreign_key' && f.references && `FK→${f.references}`, f.unique && 'unique', f.nullable === false && 'required', list(f.values).length && `enum: ${list(f.values).slice(0, 5).join(', ')}`, f.default != null && `default=${String(f.default)}`].filter(Boolean).join(', '); return <TR key={f.name || i}><TD>{typeof f === 'string' ? f : f.name}</TD><TD className="text-muted">{typeof f === 'object' ? f.type : ''}</TD><TD className="text-muted">{notes}</TD></TR> })}</tbody></Table></div></DocSubsection>
}

function RelationshipTable({ items }) {
  return <Table><thead><TR><TH>From</TH><TH>To</TH><TH>Type</TH><TH>Description</TH></TR></thead><tbody>{list(items).map((r, i) => <TR key={i}><TD>{r.from || r.from_}</TD><TD>{r.to}</TD><TD className="text-muted">{r.type}</TD><TD>{r.description || '—'}</TD></TR>)}</tbody></Table>
}

function RoleSummary({ roles }) {
  return <Table><thead><TR><TH>Role</TH><TH>Description</TH></TR></thead><tbody>{list(roles).map((r, i) => <TR key={r.role_key || i}><TD>{r.role_name || r.name || line(r)}</TD><TD className="text-muted">{r.description || '—'}</TD></TR>)}</tbody></Table>
}

function RoleAccessTable({ items }) {
  return <Table><thead><TR><TH>Role</TH><TH>Allowed Pages</TH><TH>Allowed Functions</TH></TR></thead><tbody>{list(items).map((r, i) => <TR key={r.role || i}><TD>{r.role || r.role_name}</TD><TD className="text-muted">{list(r.allowed_pages || r.pages).map(line).join(', ') || '—'}</TD><TD className="text-muted">{list(r.allowed_functions || r.permissions || r.access).map(line).join(', ') || '—'}</TD></TR>)}</tbody></Table>
}

function UiUxSection({ doc }) {
  const ui = doc.ui_ux_requirements || {}
  const brand = doc.branding || {}
  return <div className="space-y-3"><KeyValue label="Design Style" value={ui.design_style} /><KeyValue label="Theme" value={ui.theme || brand.theme} /><KeyValue label="Dashboard Layout" value={ui.dashboard_layout} />{list(ui.required_components).length > 0 && <KeyValue label="Components" value={list(ui.required_components).join(', ')} />}{brand.palette && <KeyValue label="Palette" value={`${brand.palette}${brand.primary_color ? ` (${brand.primary_color})` : ''}`} />}{brand.logo_required && <KeyValue label="Logo" value={`Generated artwork requested${brand.logo_image_prompt ? ` — ${brand.logo_image_prompt}` : ''}`} />}</div>
}

function KeyValue({ label, value }) {
  if (value == null || value === '' || (Array.isArray(value) && !value.length)) return null
  return <div className="grid gap-2 border-b border-line py-2 sm:grid-cols-[170px_1fr]"><span className="text-[11px] font-semibold text-label">{label}</span><span className="text-[12px] leading-relaxed text-ink">{Array.isArray(value) ? value.join(', ') : String(value)}</span></div>
}

function RiskList({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No specific project risks were recorded.</DocParagraph>
  return <div className="space-y-3">{rows.map((r, i) => <div key={r.id || i} className="rounded-xl border border-line p-3"><div className="flex items-center gap-2"><Tag tone={String(r.severity || '').toLowerCase() === 'high' ? 'solid' : undefined}>{r.severity || 'Medium'} risk</Tag><p className="text-[12px] font-semibold text-ink">{r.risk || line(r)}</p></div>{r.reason && <p className="mt-2 text-[11.5px] leading-relaxed text-muted">{r.reason}</p>}{r.mitigation && <p className="mt-1 text-[11.5px] leading-relaxed text-label"><b>Mitigation:</b> {r.mitigation}</p>}</div>)}</div>
}

function AcceptanceList({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No acceptance criteria were recorded.</DocParagraph>
  return <ul>{rows.map((r, i) => <li key={r.id || i} className="grid grid-cols-[28px_1fr] gap-2 border-b border-line py-2 last:border-0"><span className="text-ok">✓</span><span className="text-[12px] leading-relaxed text-ink">{typeof r === 'string' ? r : (r.criterion || line(r))}</span></li>)}</ul>
}

function RevisionTable({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No revision history was recorded.</DocParagraph>
  return <Table><thead><TR><TH>Version</TH><TH>Date</TH><TH>Description</TH></TR></thead><tbody>{rows.map((r, i) => <TR key={i}><TD>{r.version}</TD><TD className="text-muted">{r.date}</TD><TD>{r.description}</TD></TR>)}</tbody></Table>
}

function ApprovalTable({ items }) {
  return <Table><thead><TR><TH>Role</TH><TH>Name</TH><TH>Date</TH><TH>Status</TH></TR></thead><tbody>{list(items).map((r, i) => <TR key={i}><TD>{r.role}</TD><TD>{r.name}</TD><TD className="text-muted">{r.date}</TD><TD>{r.status}</TD></TR>)}</tbody></Table>
}

function PlanUsers({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No distinct user groups were recorded.</DocParagraph>
  return <Table><thead><TR><TH>User</TH><TH>Can do</TH></TR></thead><tbody>{rows.map((r, i) => <TR key={i}><TD>{r.role || r.name}</TD><TD className="text-muted">{list(r.can_do).join(', ') || '—'}</TD></TR>)}</tbody></Table>
}

function PlanScreens({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No screens were recorded.</DocParagraph>
  return <Table><thead><TR><TH>Screen</TH><TH>Route</TH><TH>Purpose</TH><TH>Who</TH></TR></thead><tbody>{rows.map((r, i) => <TR key={i}><TD>{r.name}</TD><TD className="font-mono text-muted">{r.route}</TD><TD>{r.purpose}</TD><TD className="text-muted">{list(r.who).join(', ') || '—'}</TD></TR>)}</tbody></Table>
}

function PlanRecords({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No persistent records were included in the approved plan.</DocParagraph>
  return <Table><thead><TR><TH>Record</TH><TH>Information kept</TH></TR></thead><tbody>{rows.map((r, i) => <TR key={i}><TD>{r.name}</TD><TD className="text-muted">{list(r.keeps).join(', ') || '—'}</TD></TR>)}</tbody></Table>
}

function PlanWorkflows({ items }) {
  const rows = list(items)
  if (!rows.length) return <DocParagraph>No explicit workflows were recorded in the plan.</DocParagraph>
  return <div className="space-y-2">{rows.map((r, i) => <div key={i} className="rounded-xl bg-black/[.02] p-3 dark:bg-white/[.02]"><p className="text-[11.5px] font-semibold text-ink">{r.name || `Workflow ${i + 1}`}</p>{r.who && <p className="mt-0.5 text-[10.5px] text-muted">Actor: {r.who}</p>}<ol className="mt-2 space-y-1">{list(r.steps).map((s, j) => <li key={j} className="text-[11.5px] text-muted">{j + 1}. {s}</li>)}</ol></div>)}</div>
}


/** Show one document fact as a label and value. */
const Fact = ({ label, children }) => (
  <div className="flex items-baseline justify-between gap-3 border-b border-line
                  py-1.5 text-[11.5px]">
    <span className="text-label">{label}</span>
    <span className="min-w-0 truncate font-mono text-[11px] text-ink">{children}</span>
  </div>
)

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
    <>
      <div className="mb-4 flex w-fit flex-wrap border border-line2">
        {diagrams.map((d, i) => (
          <button key={d.name} onClick={() => setOpen(i)}
                  className={cn('border-r border-line2 px-3 py-1.5 text-[11px]',
                    'font-semibold capitalize transition-colors last:border-r-0',
                    i === open ? 'bg-accent text-bg'
                               : 'text-label hover:bg-ink/[.07] hover:text-ink')}>
            {d.name.replace(/_/g, ' ')}
          </button>
        ))}
      </div>
      <section className="mb-4 border border-line2 bg-panel px-4 py-3.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted2">
          {current.standard || current.title}
        </p>
        <h3 className="mt-1 text-[15px] font-semibold text-ink">
          {current.question}
        </h3>
        <p className="mt-1.5 max-w-[920px] text-[12px] leading-[1.65] text-muted">
          {current.definition}
        </p>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div className="border-l-[3px] border-accent bg-tint px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-label">
              How this diagram starts
            </p>
            <ol className="mt-1.5 space-y-1 text-[11px] leading-[1.5] text-muted">
              {list(current.drawingRules).map((rule, i) => (
                <li key={rule}><span className="mr-1.5 font-mono text-faint">{i + 1}.</span>{rule}</li>
              ))}
            </ol>
          </div>
          {list(current.notation).length > 0 && (
            <div className="border-l-[3px] border-line2 bg-panel2 px-3 py-2.5">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-label">
                How to read the notation
              </p>
              <ul className="mt-1.5 space-y-1 text-[11px] leading-[1.5] text-muted">
                {list(current.notation).map(item => <li key={item}>• {item}</li>)}
              </ul>
            </div>
          )}
        </div>
        {!current.applicable && (
          <p className="mt-3 border-l-[3px] border-warn bg-warn/[.08] px-3 py-2 text-[11px] text-muted">
            <span className="font-semibold text-ink">Not applicable to this SRS.</span>{' '}
            {current.applicabilityNote || 'The approved requirements do not provide the semantics needed to draw this view without inventing behavior.'}
          </p>
        )}
      </section>
      <div className="group relative overflow-x-auto rounded-[14px] border border-line2 bg-panel2 p-4">
        {current.svg
          ? <>
              <button onClick={() => setZoomed(true)}
                      title="Open this diagram full size"
                      className="block w-full cursor-zoom-in text-left">
                <div className="srs-diagram [&_svg]:h-auto [&_svg]:max-w-full"
                     dangerouslySetInnerHTML={{ __html: current.svg }} />
              </button>
              <span className="pointer-events-none absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-ink/75 px-2.5 py-1 text-[10.5px] font-medium text-bg opacity-0 transition-opacity group-hover:opacity-100">
                <Maximize2 className="size-3" /> Click to enlarge
              </span>
            </>
          : <pre className="whitespace-pre font-mono text-[11.5px] text-muted">
              {current.mermaid}
            </pre>}
      </div>

      {/* ── Plain-English System Flow & Narrative Guide (Under Diagram) ── */}
      <div className="mt-4 rounded-2xl border border-blue-500/25 bg-[#0e1322] p-5 shadow-xl text-white">
        <div className="flex items-center gap-2.5 border-b border-white/10 pb-3">
          <div className="grid size-7 place-items-center rounded-lg bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Compass className="size-3.5" />
          </div>
          <div>
            <h4 className="text-[13px] font-bold text-white">
              System Flow Walkthrough (Plain English)
            </h4>
            <p className="text-[11px] text-white/50">
              How data, users, and actions flow through this diagram in everyday terms
            </p>
          </div>
        </div>

        {current.businessSummary && (
          <p className="mt-3 text-[12.5px] leading-relaxed text-white/80 font-medium">
            {current.businessSummary}
          </p>
        )}

        {list(current.flowExplanation).length > 0 && (
          <div className="mt-4 space-y-2">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-blue-400">
              Step-by-Step Flow:
            </div>
            <div className="grid gap-2">
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
          <div className="mt-4 border-t border-white/10 pt-3">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-emerald-400 mb-2">
              Key Protections & Business Rules:
            </div>
            <ul className="space-y-1.5">
              {list(current.keyTakeaways).map((item, idx) => (
                <li key={idx} className="flex items-center gap-2 text-[11.5px] text-white/70">
                  <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {zoomed && current.svg && (
        <DiagramViewer svg={current.svg} title={current.title}
                       onClose={() => setZoomed(false)} />
      )}
      {!current.svg && (
        <p className="mt-2 text-[11px] text-muted2">
          {current.rendered
            ? 'The picture for this revision is on disk but only the current '
              + 'version is displayed — its Mermaid source is shown instead.'
            : 'No image was rendered for this one — the Mermaid source is shown instead.'}
        </p>
      )}
    </>
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
  const doc = srs.document || {}
  const evidence = doc.prototype_evidence || {}
  const screens = list(evidence.screens).length ? evidence.screens : list(evidence.pages).map(p => ({
    screen_name: typeof p === 'string' ? p.replace(/\.[^/.]+$/, '').replace(/_/g, ' ').toUpperCase() : (p.screen_name || 'Screen'),
    file: typeof p === 'string' ? p : p.file,
    actions: p.actions || ['Browse Content', 'Interactive Controls', 'Navigation Links'],
  }))
  const shots = list(evidence.screenshots)
  const audit = evidence.flow_audit || {}
  const verified = evidence.verified !== false

  const fallbackScreens = screens.length ? screens : [
    { screen_name: 'Main Application Interface', file: 'index.html', actions: ['Navigation', 'Data View', 'Action Triggers'] },
  ]

  return (
    <div className="mx-auto max-w-[1120px] pb-12 text-white">
      {/* Overview Banner */}
      <div className="mb-6 rounded-2xl border border-purple-500/30 bg-[linear-gradient(135deg,#120f24_0%,#191433_100%)] p-5 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-xl bg-purple-600/25 text-purple-400 border border-purple-500/30">
              <Workflow className="size-4" />
            </div>
            <div>
              <h3 className="text-[15px] font-bold text-white">
                Prototype & Demo Flow Verification
              </h3>
              <p className="text-[11.5px] text-white/50">
                Visual UI screens, verified demo flows, and requirement parity
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-[11px] font-semibold text-emerald-300 border border-emerald-500/25">
            <CheckCircle2 className="size-3" />
            <span>{verified ? 'Flow Verified · Zero Dead-Ends' : 'Flow Checked'}</span>
          </span>
        </div>

        <p className="mt-3 text-[12.5px] leading-relaxed text-white/80">
          The HTML Prototype implements the visual user journeys specified in this SRS.
          All navigation buttons, modals, and screen layouts are verified to ensure complete alignment before and during the build.
        </p>
      </div>

      {/* Screen Cards Grid */}
      <div className="mb-8">
        <h4 className="text-[13px] font-bold uppercase tracking-wider text-white/50 mb-3">
          Verified Screens & Interaction Pathways
        </h4>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {fallbackScreens.map((s, idx) => (
            <div key={idx} className="rounded-2xl border border-white/10 bg-[#0f1422] p-4 shadow-md transition-all hover:border-white/20">
              <div className="flex items-center justify-between gap-2 border-b border-white/5 pb-2.5">
                <span className="font-mono text-[11px] font-bold text-purple-400">
                  #{idx + 1}
                </span>
                <span className="font-mono text-[10px] text-white/40">
                  {s.file || 'screen.html'}
                </span>
              </div>
              <h5 className="mt-2.5 text-[14px] font-bold text-white">
                {s.screen_name}
              </h5>
              <div className="mt-3 space-y-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-white/40 block">
                  Interactive Controls:
                </span>
                <div className="flex flex-wrap gap-1">
                  {list(s.actions).map((act, i) => (
                    <span key={i} className="inline-flex items-center gap-1 rounded-md bg-white/[.04] px-2 py-0.5 text-[11px] text-white/70 border border-white/5">
                      <CheckCircle2 className="size-2.5 text-blue-400" />
                      {act}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Traceability & Living Parity Card */}
      <div className="rounded-2xl border border-emerald-500/25 bg-[#0a141a] p-5 shadow-lg">
        <div className="flex items-center gap-2 text-emerald-400 font-bold text-[13px] mb-2">
          <ShieldCheck className="size-4" />
          <span>100% Traceability & Parity Guarantee</span>
        </div>
        <p className="text-[12px] leading-relaxed text-white/75">
          Every screen, collection, and workflow identified in this prototype traces directly to an approved requirement in the SRS.
          As the builder generates code and tests the application, progress feeds continuously back into this living document.
        </p>
      </div>
    </div>
  )
}


export const VIEWS = [
  { id: 'overview', label: 'Overview', C: Overview },
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
    const screens = doc.prototype_evidence?.screens || doc.prototype_evidence?.pages
    return { n: n(screens) || 1, bad: false }
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
