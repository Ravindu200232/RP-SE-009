'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft, ArrowUp, Check, FileDown, History, Loader2, RotateCcw,
} from 'lucide-react'
import { api, API } from '@/lib/api'
import { useStore } from '@/lib/store'
import { loadSrsView, srsViewFromVersion } from '@/lib/srs-view'
import { Badge, Button, Empty, Panel } from '../ui'
import { VIEWS, badgeFor } from './views'
import { cn } from '@/lib/utils'

export default function SrsReview({ projectId, onApproved, onBack }) {
  const addLog = useStore(s => s.addLog)
  const [srs, setSrs] = useState(null)
  const [state, setState] = useState('loading')
  const [error, setError] = useState('')
  const [sub, setSub] = useState('document')

  const [prompt, setPrompt] = useState('')
  const [thread, setThread] = useState([])
  const [busy, setBusy] = useState('')
  const [waited, setWaited] = useState(0)
  const [viewing, setViewing] = useState(null)
  const box = useRef(null)

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
      addLog('INFO', `📄 SRS revised — v${r?.version || '?'}`)
      await load()
    } catch (e) {
      setThread(t => [...t, { role: 'error', text: e.message }])
    } finally {
      setBusy('')
    }
  }

  async function approve() {
    setBusy('approving')
    setError('')
    try {
      await api.srs(`/projects/${projectId}/approve`, {})
      const handoff = await api.srs(`/projects/${projectId}/builder-handoff`)
      const text = (handoff?.prompt || '').trim()
      if (!text) throw new Error('the SRS produced no builder prompt')
      addLog('INFO', `✅ SRS approved — ${(handoff.requirements || []).length} requirements`)
      onApproved?.(text, projectId)
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
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-3 border-b border-line
                      bg-panel px-4 py-2.5">
        <button onClick={onBack}
                className="flex items-center gap-1 text-[11px] text-muted2 hover:text-ink">
          <ArrowLeft className="size-3" /> Plan
        </button>
        <div className="min-w-0">
          <p className="truncate font-display text-[13px] font-bold text-ink">
            {srs?.document?.project_name || srs?.document?.document_title || 'Specification'}
          </p>
        </div>
        {srs?.version && <Badge tone="mute">v{srs.version}</Badge>}
        {approved && <Badge tone="ok">approved</Badge>}
        <span className="flex-1" />
        {viewing ? (
          <span title="The PDF is only produced for the current version"
                className="flex cursor-not-allowed items-center gap-1.5 rounded-ctl
                           border border-line px-2.5 py-1 text-[11px] text-muted2
                           opacity-50">
            <FileDown className="size-3" /> PDF
          </span>
        ) : (
          <a href={`${API}/srs/projects/${encodeURIComponent(projectId)}/download/pdf`}
             target="_blank" rel="noreferrer"
             className="flex items-center gap-1.5 rounded-ctl border border-line
                        px-2.5 py-1 text-[11px] text-muted hover:text-ink">
            <FileDown className="size-3" /> PDF
          </a>
        )}
      </div>

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[260px] shrink-0 flex-col border-r border-line bg-panel">
          <div className="flex items-center gap-1.5 border-b border-line px-3 py-2">
            <History className="size-3 text-muted2" />
            <span className="text-[11px] font-medium text-muted2">REVISIONS</span>
          </div>

          <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
            {versions.map((v, i) => (
              <button key={v.id || i}
                      onClick={() => setViewing(
                        i === versions.length - 1 ? null
                          : srsViewFromVersion(v, projectId))}
                      className={cn('w-full rounded-ctl px-2.5 py-2 text-left transition-colors',
                        (viewing?.version || srs?.version) === v.version
                          ? 'bg-accent/12' : 'hover:bg-panel2')}>
                <span className="font-mono text-[10px] text-accent">v{v.version}</span>
                <span className="mt-0.5 block text-[11px] leading-snug text-muted">
                  {v.label || 'Revision'}
                </span>
              </button>
            ))}

            {thread.map((m, i) => (
              <div key={`t${i}`}
                   className={cn('rounded-ctl px-2.5 py-2 text-[11px] leading-relaxed',
                     m.role === 'you' ? 'bg-panel2 text-ink'
                       : m.role === 'error' ? 'text-bad' : 'text-muted')}>
                {m.role === 'you' && <span className="text-muted2">you — </span>}
                {m.text}
              </div>
            ))}

            {busy === 'revising' && (
              <div className="flex items-center gap-2 px-2.5 py-2 text-[11px] text-muted">
                <Loader2 className="size-3 animate-spin" />
                Rewriting the specification… {waited}s
              </div>
            )}
          </div>

          <div className="border-t border-line p-2">
            <textarea value={prompt} rows={3} ref={box} disabled={Boolean(busy)}
                      placeholder="Describe a change — “add a refunds page only the manager can open”…"
                      onChange={e => setPrompt(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) revise()
                      }}
                      className="w-full resize-none bg-transparent p-2 text-[12px]
                                 leading-relaxed text-ink outline-none
                                 placeholder:text-muted2 disabled:opacity-50" />
            <div className="flex items-center gap-2 px-1">
              <span className="flex-1 font-mono text-[9.5px] text-muted2">
                the diagrams update too
              </span>
              <Button variant="solid" size="icon"
                      disabled={!prompt.trim() || Boolean(busy)} onClick={revise}>
                <ArrowUp className="size-3.5" />
              </Button>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 flex-wrap items-center gap-1 border-b
                          border-line bg-panel px-3 py-2">
            {VIEWS.map(v => {
              const badge = badgeFor(v.id, shown)
              return (
                <button key={v.id} onClick={() => setSub(v.id)}
                        className={cn('flex items-center gap-1.5 rounded-ctl px-3 py-1.5',
                          'text-[11.5px] font-medium transition-colors',
                          sub === v.id ? 'bg-accent/12 text-accent'
                                       : 'text-muted hover:bg-panel2 hover:text-ink')}>
                  {v.label}
                  {badge && <Badge tone={badge.bad ? 'warn' : 'mute'}>{badge.n}</Badge>}
                </button>
              )
            })}
          </div>

          {viewing && (
            <div className="flex shrink-0 items-center gap-2 border-b border-line
                            bg-warn/5 px-4 py-1.5">
              <span className="text-[11px] text-warn">
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

        <aside className="flex w-[280px] shrink-0 flex-col border-l border-line bg-panel">
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <p className="mb-2 text-[11px] font-medium text-muted2">THE SPECIFICATION</p>
            <Panel className="p-3">
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
                  <div key={label} className="flex items-baseline justify-between py-0.5">
                    <span className="text-[11.5px] text-muted">{label}</span>
                    <span className="font-mono text-[12px] text-ink">{n}</span>
                  </div>
                ))}
              {counts.open_ambiguities > 0 && (
                <div className="mt-1.5 flex items-baseline justify-between
                                border-t border-line pt-1.5">
                  <span className="text-[11.5px] text-warn">still unclear</span>
                  <span className="font-mono text-[12px] text-warn">
                    {counts.open_ambiguities}
                  </span>
                </div>
              )}
            </Panel>

            {thread.filter(m => m.role === 'srs').slice(-1).map((m, i) => (
              <div key={i} className="mt-4">
                <p className="mb-1.5 text-[11px] font-medium text-muted2">
                  WHAT CHANGED, AS THE EDITOR DESCRIBED IT
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

          <div className="border-t border-line p-3">
            {error && <p className="mb-2 text-[11px] text-bad">{error}</p>}
            <Button variant="solid" className="w-full justify-center py-2.5"
                    disabled={Boolean(busy) || Boolean(viewing)}
                    onClick={approve}>
              {busy === 'approving'
                ? <><Loader2 className="size-3.5 animate-spin" /> Starting…</>
                : <><Check className="size-3.5" /> Approve and build this</>}
            </Button>
            <p className="mt-2 text-center text-[10px] leading-relaxed text-muted2">
              {viewing
                ? 'Go back to the latest revision to approve it.'
                : 'Nothing is written until you press this.'}
            </p>
          </div>
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
