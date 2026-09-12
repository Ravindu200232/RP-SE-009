'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft, ArrowRight, ArrowUp, Check, FileDown, History, ListTree, Loader2,
  RotateCcw, Square,
} from 'lucide-react'
import { api, API } from '@/lib/api'
import { useStore } from '@/lib/store'
import { loadSrsView, srsViewFromVersion } from '@/lib/srs-view'
import { Badge, Button, Empty, Modal, SubTab, SubTabs, Tag, TextArea } from '../ui'
import { VIEWS, badgeFor } from './views'
import { cn } from '@/lib/utils'

export default function SrsReview({ projectId, onApproved, onKept, onBack }) {
  const addLog = useStore(s => s.addLog)
  const [srs, setSrs] = useState(null)
  const [state, setState] = useState('loading')
  const [error, setError] = useState('')
  const [sub, setSub] = useState('overview')
  const [specOpen, setSpecOpen] = useState(false)
  const [asking, setAsking] = useState(false)

  const [prompt, setPrompt] = useState('')
  const [thread, setThread] = useState([])
  // The approved handoff, held while we ask whether to build it now.
  const [approvedPrompt, setApprovedPrompt] = useState('')
  const [busy, setBusy] = useState('')
  const [waited, setWaited] = useState(0)
  const [viewing, setViewing] = useState(null)
  const box = useRef(null)

  /** Throw this specification away and leave. */
  async function discard() {
    setBusy('discarding')
    try {
      await api.discardSrs(projectId)
      addLog('WARN', 'the specification was discarded')
      onBack?.()
    } catch (e) {
      addLog('WARN', `could not discard — ${e.message}`)
      setBusy('')
      setAsking(false)
    }
  }

  async function load() {
    setState('loading')
    try {
      setSrs(await loadSrsView(projectId))
      setState('ready')
    } catch (e) {
      setError(e.message)
      setState('error')
    }
  }

  useEffect(() => { load()  }, [projectId])

  useEffect(() => {
    if (!busy) return
    setWaited(0)
    const t = setInterval(() => setWaited(w => w + 1), 1000)
    return () => clearInterval(t)
  }, [busy])

  async function revise() {
    const text = prompt.trim()
    if (!text || busy) return
    setPrompt('')
    setViewing(null)
    setThread(t => [...t, { role: 'you', text }])
    setBusy('revising')
    setError('')
    try {
      const r = await api.srs(`/projects/${projectId}/customize`, { prompt: text })
      const said = r?.diff_summary || []
      setThread(t => [...t, {
        role: 'srs',
        text: said.length ? said.join('\n') : 'The specification was updated.',
        version: r?.version,
      }])
      addLog('INFO', `SRS revised — v${r?.version || '?'}`)
      await load()
    } catch (e) {
      setThread(t => [...t, { role: 'error', text: e.message }])
    } finally {
      setBusy('')
    }
  }

  /** Approve the specification, then ask what to do with it. */
  async function approve() {
    setBusy('approving')
    setError('')
    try {
      await api.srs(`/projects/${projectId}/approve`, {})
      const handoff = await api.srs(`/projects/${projectId}/builder-handoff`)
      const text = (handoff?.prompt || '').trim()
      if (!text) throw new Error('the SRS produced no builder prompt')
      addLog('INFO', `SRS approved — ${(handoff.requirements || []).length} requirements`)
      setBusy('')
      setApprovedPrompt(text)
    } catch (e) {
      setError(e.message)
      setBusy('')
    }
  }

  /** Keep the specification as a project, and build nothing. */
  async function keepOnly() {
    setBusy('keeping')
    setError('')
    try {
      const r = await api.keepSrs(projectId)
      if (r?.error) throw new Error(r.error)
      addLog('SUCCESS', `Kept as ${r.project} — nothing was built`)
      setApprovedPrompt('')
      onKept?.(r.project)
    } catch (e) {
      setError(e.message)
      setBusy('')
    }
  }

  if (state === 'loading' && !srs) {
    return <Centered><Loader2 className="mx-auto mb-3 size-5 animate-spin text-accent" />
      Reading the specification…</Centered>
  }
  if (state === 'error') {
    return <Centered bad>Could not read the specification — {error}</Centered>
  }

  const shown = viewing || srs
  const View = (VIEWS.find(v => v.id === sub) || VIEWS[0]).C

  const counts = viewing ? countOf(viewing.document) : (srs?.summary || {})
  const versions = srs?.versions || []

  const approved = srs?.status === 'approved'

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[radial-gradient(circle_at_top_right,rgba(37,99,235,.12),transparent_35%)] text-white">
      {/* Approving a specification used to start a build in the same breath. */}
      {approvedPrompt && (
        <Modal onClose={() => { }}>
          <section role="dialog" aria-modal="true" aria-labelledby="build-now-title" className="p-6 text-white">
            <h2 id="build-now-title" className="font-display text-[18px] font-bold text-white">
              Build {srs?.document?.project_name || 'this app'} now?
            </h2>
            <p className="mt-2 text-[12.5px] leading-relaxed text-white/60">
              The specification is approved either way. Building starts the
              agent on it now — planning, writing, testing and serving the app.
              Keeping it saves the specification as a project on its own, and
              you can build it whenever you like.
            </p>
            <footer className="mt-6 flex justify-end gap-2.5 border-t border-white/10 pt-4">
              <Button variant="outline" className="rounded-xl border-white/10 bg-white/[.04] text-white/80 hover:bg-white/[.08] hover:text-white" disabled={Boolean(busy)} onClick={keepOnly}>
                {busy === 'keeping'
                  ? <><Loader2 className="size-3 animate-spin" /> Keeping…</>
                  : 'No — keep the specification'}
              </Button>
              <Button variant="solid" className="rounded-xl bg-blue-600 px-4 text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500" disabled={Boolean(busy)}
                      onClick={() => onApproved?.(approvedPrompt, projectId)}>
                Yes — build it <ArrowRight className="size-3.5" />
              </Button>
            </footer>
          </section>
        </Modal>
      )}

      <div className="flex shrink-0 items-center gap-3 border-b border-white/10 px-6 py-3.5 backdrop-blur-md">
        <button onClick={onBack}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[.04] px-2.5 py-1 text-[11.5px] font-medium text-white/70 hover:bg-white/[.08] hover:text-white transition">
          <ArrowLeft className="size-3" /> Plan
        </button>
        <div className="min-w-0">
          <p className="truncate font-display text-[14px] font-bold text-white">
            {srs?.document?.project_name || srs?.document?.document_title || 'Specification'}
          </p>
        </div>
        {srs?.version && <Tag tone="accent">v{srs.version}</Tag>}
        {approved && <Tag tone="solid">approved</Tag>}
        <span className="flex-1" />
        {viewing ? (
          <span title="The PDF is only produced for the current version"
                className="flex h-[32px] cursor-not-allowed items-center gap-1.5
                           rounded-xl border border-white/10 px-3 font-display text-[11.5px]
                           font-semibold text-white/40 opacity-50">
            <FileDown className="size-3.5" /> PDF
          </span>
        ) : (
          <a href={`${API}/srs/projects/${encodeURIComponent(projectId)}/download/pdf`}
             target="_blank" rel="noreferrer"
             className="flex h-[32px] items-center gap-1.5 rounded-xl border border-white/10 bg-white/[.04] px-3.5
                        text-[11.5px] font-semibold text-white/90 shadow-sm
                        transition hover:bg-white/[.08] hover:text-white">
            <FileDown className="size-3.5 text-blue-400" /> PDF
          </a>
        )}

        <Button variant="solid" className="h-[32px] rounded-xl bg-blue-600 px-4 text-[12px] font-semibold text-white shadow-md shadow-blue-500/25 hover:bg-blue-500"
                disabled={Boolean(busy) || Boolean(viewing)}
                title={viewing ? 'Go back to the latest revision to approve it.'
                               : 'You will be asked whether to build it.'}
                onClick={approve}>
          {busy === 'approving'
            ? <><Loader2 className="size-3.5 animate-spin" /> Approving…</>
            : <><Check className="size-3.5" /> Approve</>}
        </Button>

        {asking ? (
          <span className="flex items-center gap-1.5">
            <span className="text-[11px] text-white/60">Discard it?</span>
            <Button variant="solid" className="h-[32px] rounded-xl bg-bad px-3.5 hover:brightness-110"
                    disabled={busy === 'discarding'} onClick={discard}>
              {busy === 'discarding'
                ? <><Loader2 className="size-3.5 animate-spin" /> Discarding…</>
                : 'Yes'}
            </Button>
            <Button variant="outline" className="h-[32px] rounded-xl border-white/10 bg-white/[.04] px-3 text-white/80 hover:bg-white/[.08]"
                    disabled={busy === 'discarding'} onClick={() => setAsking(false)}>
              Keep it
            </Button>
          </span>
        ) : (
          <Button variant="outline" className="h-[32px] rounded-xl border-white/10 bg-white/[.04] px-3 text-white/80 hover:bg-white/[.08] hover:text-white"
                  disabled={Boolean(busy)} onClick={() => setAsking(true)}
                  title="Throw this specification away and start over">
            <Square className="size-3 text-red-400" /> Cancel
          </Button>
        )}

        <button onClick={() => setSpecOpen(v => !v)}
                title="The specification at a glance"
                className={cn('flex h-[32px] items-center gap-1.5 rounded-xl px-3.5 text-[11.5px] font-semibold transition',
                  specOpen ? 'bg-blue-600 text-white shadow-md shadow-blue-500/25'
                           : 'border border-white/10 bg-white/[.04] text-white/80 hover:bg-white/[.08] hover:text-white')}>
          <ListTree className="size-3.5" /> Specification
        </button>
      </div>

      <div className="flex min-h-0 flex-1 gap-4 p-5">
        <aside className="flex w-[270px] shrink-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#121622]/90 shadow-xl backdrop-blur-xl">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
            <History className="size-3.5 text-blue-400" />
            <span className="font-display text-[12px] font-bold text-white uppercase tracking-wider">Revisions</span>
            <span className="flex-1" />
            <span className="rounded-full bg-white/10 px-2 py-0.5 font-mono text-[10px] text-white/60">{versions.length}</span>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {versions.map((v, i) => (
              <button key={v.id || i}
                      onClick={() => setViewing(
                        i === versions.length - 1 ? null
                          : srsViewFromVersion(v, projectId))}
                      className={cn('mb-1.5 w-full rounded-xl border px-3 py-2 text-left transition-all',
                        (viewing?.version || srs?.version) === v.version
                          ? 'border-blue-500/40 bg-blue-500/15 text-white shadow-sm'
                          : 'border-transparent bg-white/[.02] text-white/70 hover:bg-white/[.05] hover:text-white')}>
                <span className="font-mono text-[10.5px] font-semibold text-blue-400">v{v.version}</span>
                <span className="mt-0.5 block text-[11.5px] leading-snug">
                  {v.label || 'Revision'}
                </span>
              </button>
            ))}

            {thread.map((m, i) => (
              <div key={`t${i}`}
                   className={cn('mb-2 rounded-xl p-3 text-[11.5px] leading-relaxed',
                     m.role === 'you' ? 'ml-6 border border-accent/30 bg-accent/20 text-white font-medium'
                       : m.role === 'error'
                         ? 'border border-red-500/30 bg-red-500/10 text-red-300'
                         : 'border border-white/5 bg-white/[.03] text-white/80')}>
                {m.role === 'you' && <span className="text-accent text-[10px] font-bold uppercase tracking-wider block mb-1">you</span>}
                {m.text}
              </div>
            ))}

            {busy === 'revising' && (
              <div className="flex items-center gap-2 px-2.5 py-2 text-[11.5px] text-white/60">
                <Loader2 className="size-3 animate-spin text-blue-400" />
                Rewriting specification… {waited}s
              </div>
            )}
          </div>

          <div className="border-t border-white/10 p-3 bg-black/20">
            <TextArea value={prompt} rows={3} ref={box} disabled={Boolean(busy)}
                      placeholder="Describe a change — “add a refunds page only the manager can open”…"
                      onChange={e => setPrompt(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) revise()
                      }}
                      className="w-full resize-none rounded-xl border border-white/10 bg-white/[.04] p-2.5 text-[12px]
                                 leading-relaxed text-white outline-none focus:border-blue-500/50
                                 placeholder:text-white/40 disabled:opacity-50 caret-blue-400" />
            <div className="mt-2 flex items-center gap-2">
              <span className="flex-1 font-mono text-[9.5px] text-white/40">
                diagrams update too
              </span>
              <Button variant="solid" size="icon" className="size-7 rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow"
                      disabled={!prompt.trim() || Boolean(busy)} onClick={revise}>
                <ArrowUp className="size-3.5" />
              </Button>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#121622]/90 shadow-2xl backdrop-blur-xl">
          <SubTabs>
            {VIEWS.map(v => {
              const badge = badgeFor(v.id, shown)
              return (
                <SubTab key={v.id} on={sub === v.id} onClick={() => setSub(v.id)}>
                  {v.label}
                  {badge && <Badge tone={badge.bad ? 'bad' : 'mute'}>{badge.n}</Badge>}
                </SubTab>
              )
            })}
          </SubTabs>

          {viewing && (
            <div className="mx-4 mt-3 flex shrink-0 items-center gap-2 rounded-[16px] bg-accent/[.08] px-4 py-2">
              <span className="text-[11px] text-deep">
                Showing v{viewing.version} — an earlier revision, read only.
              </span>
              <span className="flex-1" />
              <Button variant="outline" onClick={() => setViewing(null)}>
                <RotateCcw className="size-3" /> Back to the latest
              </Button>
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {shown?.have && Object.values(shown.have).some(Boolean)
              ? <View srs={shown} />
              : <Empty>Nothing was written for this version.</Empty>}
          </div>
        </div>

        <aside className={cn('flex shrink-0 flex-col overflow-hidden rounded-[24px]',
          'bg-white/62 shadow-[0_16px_42px_rgba(15,23,42,.06)] ring-1 ring-line/70',
          'backdrop-blur-xl transition-[width,opacity] duration-300 dark:bg-white/[.035]',
          specOpen ? 'w-[280px] opacity-100' : 'pointer-events-none w-0 opacity-0 ring-0')}>
          <div className="min-h-0 w-[280px] flex-1 overflow-y-auto p-3">
            <p className="label-xs mb-3 text-ink">
              The specification
            </p>
            <div>
              {[['requirements', counts.functional],
                ['qualities', counts.non_functional],
                ['roles', counts.roles],
                ['tables', counts.tables],
                ['modules', counts.modules],
                ['workflows', counts.use_cases],
                ['pages', pageCount(shown?.document)],
                ['diagrams', (shown?.diagrams || []).length]]
                .filter(([, n]) => n != null)
                .map(([label, n]) => (
                  <div key={label} className="mb-1 flex items-baseline justify-between rounded-xl bg-black/[.025] px-2.5 py-2 dark:bg-white/[.035]">
                    <span className="text-[11.5px] capitalize text-muted">{label}</span>
                    <span className="font-mono text-[12px] text-ink">{n}</span>
                  </div>
                ))}
              {counts.open_ambiguities > 0 && (
                <div className="mt-1.5 flex items-baseline justify-between
                                border-l-[3px] border-accent bg-tint px-2 py-1">
                  <span className="text-[11.5px] text-deep">still unclear</span>
                  <span className="font-mono text-[12px] text-deep">
                    {counts.open_ambiguities}
                  </span>
                </div>
              )}
            </div>

            {thread.filter(m => m.role === 'srs').slice(-1).map((m, i) => (
              <div key={i} className="mt-5">
                <p className="label-xs mb-2 text-ink">
                  What changed, as the editor described it
                </p>
                <p className="whitespace-pre-wrap text-[11.5px] leading-relaxed text-muted">
                  {m.text}
                </p>
              </div>
            ))}

            <p className="mt-4 text-[10.5px] leading-relaxed text-muted2">
              The “Approved Plan” pane shows the plan you signed off. It stays
              as it was on purpose — it is the record of what was agreed. The
              specification here is the current one.
            </p>
          </div>

          {error && (
            <div className="w-[280px] p-3 pt-0">
              <p className="border-l-[3px] border-accent bg-tint px-2 py-1.5
                            text-[11px] text-deep">
                {error}
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

function pageCount(doc) {
  const n = (v) => (Array.isArray(v) ? v.length : 0)
  return n(doc?.public_pages) + n(doc?.protected_pages)
}

function countOf(doc) {
  const n = (v) => (Array.isArray(v) ? v.length : 0)
  return {
    functional: n(doc?.functional_requirements),
    non_functional: n(doc?.non_functional_requirements),
    roles: n(doc?.roles),
    tables: n(doc?.database_design?.tables),
    modules: n(doc?.main_modules),
    use_cases: n(doc?.business_workflows),
    open_ambiguities: (doc?.ambiguities || []).filter(a => a?.needs_clarification).length,
  }
}

function Centered({ children, bad }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center p-8">
      <p className={cn('text-center text-[12.5px]', bad ? 'text-bad' : 'text-muted')}>
        {children}
      </p>
    </div>
  )
}
