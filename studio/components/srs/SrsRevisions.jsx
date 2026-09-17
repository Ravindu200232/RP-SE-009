'use client'

/**
 * The specification's revision history, and the box that adds to it.
 *
 * This used to be welded into the review screen, which exists only before
 * approval — so the moment a project was built, its specification became
 * read-only. It is the same panel in both places: the versions that have been
 * written, what was said to produce them, and somewhere to ask for the next one.
 *
 * The host decides what a revision means. Before approval nothing else has been
 * built yet, so reloading the screen is the whole of it; in a built project the
 * change still has to reach the prototype and the code, which is why `onRevised`
 * hands the result back rather than acting on it here.
 */
import { useEffect, useRef, useState } from 'react'
import { ArrowUp, History, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { loadSrsView } from '@/lib/srs-view'
import { Button, TextArea } from '../ui'
import { cn } from '@/lib/utils'

export function SrsRevisions({ srsId, onRevised, onPickVersion, current, className }) {
  const addLog = useStore(s => s.addLog)
  const [versions, setVersions] = useState([])
  const [prompt, setPrompt] = useState('')
  const [thread, setThread] = useState([])
  const [busy, setBusy] = useState('')
  const [waited, setWaited] = useState(0)
  const box = useRef(null)

  async function load() {
    if (!srsId) return
    try {
      const spec = await loadSrsView(srsId)
      setVersions(spec?.versions || [])
    } catch {
      // A project whose specification cannot be read still shows its composer;
      // the list is the part that is missing, and it says so by being empty.
    }
  }

  useEffect(() => { load() }, [srsId])

  useEffect(() => {
    if (!busy) return
    setWaited(0)
    const tick = setInterval(() => setWaited(w => w + 1), 1000)
    return () => clearInterval(tick)
  }, [busy])

  async function revise() {
    const text = prompt.trim()
    if (!text || busy || !srsId) return
    setPrompt('')
    onPickVersion?.(null)
    setThread(t => [...t, { role: 'you', text }])
    setBusy('revising')
    try {
      const answer = await api.srs(`/projects/${srsId}/customize`, { prompt: text })
      const said = answer?.diff_summary || []
      setThread(t => [...t, {
        role: 'srs',
        text: said.length ? said.join('\n') : 'The specification was updated.',
        version: answer?.version,
      }])
      addLog('INFO', `SRS revised — v${answer?.version || '?'}`)
      await load()
      await onRevised?.(answer, text)
    } catch (e) {
      setThread(t => [...t, { role: 'error', text: e.message }])
    } finally {
      setBusy('')
    }
  }

  return (
    <aside className={cn('flex min-h-0 flex-col overflow-hidden', className)}>
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <History className="size-3.5 text-accent" />
        <span className="font-display text-[12px] font-bold uppercase tracking-wider text-ink">Revisions</span>
        <span className="flex-1" />
        <span className="rounded-full bg-panel2 px-2 py-0.5 font-mono text-[10px] text-muted">{versions.length}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {versions.map((v, i) => (
          <button key={v.id || i}
            onClick={() => onPickVersion?.(i === versions.length - 1 ? null : v)}
            disabled={!onPickVersion}
            className={cn('mb-1.5 w-full rounded-xl border px-3 py-2 text-left transition-all',
              current === v.version
                ? 'border-blue-500/40 bg-blue-500/15 text-white shadow-sm'
                : 'border-transparent bg-white/[.02] text-white/70',
              onPickVersion && 'hover:bg-white/[.05] hover:text-white')}>
            <span className="font-mono text-[10.5px] font-semibold text-blue-400">v{v.version}</span>
            <span className="mt-0.5 block text-[11.5px] leading-snug">{v.label || 'Revision'}</span>
          </button>
        ))}

        {thread.map((m, i) => (
          <div key={`t${i}`}
            className={cn('mb-2 rounded-xl p-3 text-[11.5px] leading-relaxed',
              m.role === 'you' ? 'ml-6 border border-accent/30 bg-accent/20 font-medium text-white'
                : m.role === 'error' ? 'border border-red-500/30 bg-red-500/10 text-red-300'
                  : 'border border-white/5 bg-white/[.03] text-white/80')}>
            {m.role === 'you' && (
              <span className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-accent">you</span>
            )}
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

      <div className="border-t border-white/10 bg-black/20 p-3">
        <TextArea value={prompt} rows={3} ref={box} disabled={Boolean(busy) || !srsId}
          placeholder="Describe a change — “add a refunds page only the manager can open”…"
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) revise() }}
          className="w-full resize-none rounded-xl border border-white/10 bg-white/[.04] p-2.5 text-[12px]
                     leading-relaxed text-white caret-blue-400 outline-none focus:border-blue-500/50
                     placeholder:text-white/40 disabled:opacity-50" />
        <div className="mt-2 flex items-center gap-2">
          {/* The diagrams really are redrawn on every revision — `customize`
              runs the diagram node after the edit — so this says what happens. */}
          <span className="flex-1 font-mono text-[9.5px] text-white/40">diagrams update too</span>
          <Button variant="solid" size="icon"
            className="size-7 rounded-lg bg-blue-600 text-white shadow hover:bg-blue-500"
            disabled={!prompt.trim() || Boolean(busy) || !srsId} onClick={revise}>
            <ArrowUp className="size-3.5" />
          </Button>
        </div>
      </div>
    </aside>
  )
}

export default SrsRevisions
