'use client'

/**
 * The application, drawn, before any of it is built.
 *
 * This is the one moment the look can still be changed cheaply. A layout that
 * is wrong here costs a re-render; the same layout wrong after the build costs
 * the build, its tests and its browser journeys. So it gets the whole pane
 * rather than a dialog: the pages down one side, the drawing at real size, and
 * a box to say what should be different.
 *
 * Nothing here blocks. The question carries its own deadline and approves
 * itself if nobody answers, because a drawing nobody is looking at should not
 * hold a build open.
 */

import { useEffect, useState } from 'react'
import { Check, Loader2, Monitor, RotateCcw, Smartphone, Tablet } from 'lucide-react'

import { API } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Button } from './ui'
import { cn } from '@/lib/utils'

// The widths people actually check, in the order they check them.
const WIDTHS = [
  { id: 'desktop', label: 'Desktop', width: '100%', Icon: Monitor },
  { id: 'tablet', label: 'Tablet', width: '768px', Icon: Tablet },
  { id: 'phone', label: 'Phone', width: '390px', Icon: Smartphone },
]

export default function PrototypeReview({ question, left, sending, onAnswer }) {
  const project = useStore(s => s.project)
  const pages = question.pages || []
  const [showing, setShowing] = useState(pages[0]?.file || 'index.html')
  const [width, setWidth] = useState('desktop')
  const [feedback, setFeedback] = useState('')
  // A redraw writes the same filenames, so the iframe has to be told the bytes
  // changed or it shows the drawing from the round before.
  const [stamp, setStamp] = useState(() => Date.now())

  useEffect(() => {
    setStamp(Date.now())
    if (pages.length && !pages.some(page => page.file === showing)) {
      setShowing(pages[0].file)
    }
  }, [question.round, question.id])

  const src = project
    ? `${API}/prototype/${encodeURIComponent(project)}/${encodeURIComponent(showing)}?v=${stamp}`
    : ''
  const frame = WIDTHS.find(item => item.id === width) || WIDTHS[0]
  const rounds = Number(question.maxRounds || 0)
  const round = Number(question.round || 1)

  return (
    <div className="fixed inset-0 z-[600] flex flex-col bg-slate-950/45 p-4 backdrop-blur-md">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[26px] border border-white/60 bg-panel/95 shadow-[0_28px_80px_rgba(15,23,42,.28)] backdrop-blur-2xl dark:border-white/10">

        <header className="flex shrink-0 items-center gap-3 border-b border-line/60 px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="text-[14px] font-semibold leading-tight text-ink">
              This is what it will look like
            </h2>
            <p className="mt-0.5 truncate text-[11px] text-muted">
              {question.goal || project} — drawn in HTML, no backend yet. Ask for changes
              until it is right; the build copies whatever you approve.
            </p>
          </div>
          <span className="flex-1" />
          <div className="flex items-center rounded-xl border border-line p-0.5">
            {WIDTHS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setWidth(id)} title={label}
                      aria-pressed={width === id}
                      className={cn('grid size-7 place-items-center rounded-[9px] transition-colors',
                        width === id ? 'bg-accent/10 text-accent' : 'text-muted2 hover:text-ink')}>
                <Icon className="size-3.5" />
              </button>
            ))}
          </div>
          <span className="text-[10.5px] text-muted2">
            {left > 0 ? `building anyway in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` : ''}
          </span>
        </header>

        <div className="flex min-h-0 flex-1">
          <aside className="flex w-[248px] shrink-0 flex-col overflow-y-auto border-r border-line/60 py-2">
            <p className="px-4 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-[.14em] text-muted2">
              {pages.length} page{pages.length === 1 ? '' : 's'}
            </p>
            {pages.map(page => (
              <button key={page.file} onClick={() => setShowing(page.file)}
                      aria-pressed={showing === page.file}
                      className={cn('mx-2 mb-0.5 rounded-xl px-3 py-2 text-left transition-colors',
                        showing === page.file
                          ? 'bg-accent/[.08] ring-1 ring-accent/20'
                          : 'hover:bg-black/[.035] dark:hover:bg-white/[.045]')}>
                <span className="flex items-baseline gap-1.5">
                  <span className="truncate text-[12px] font-medium text-ink">{page.label}</span>
                  {page.route && (
                    <code className="shrink-0 font-mono text-[9.5px] text-muted2">{page.route}</code>
                  )}
                </span>
                {page.what && (
                  <span className="mt-0.5 block truncate text-[10.5px] leading-relaxed text-muted2">
                    {page.what}
                  </span>
                )}
              </button>
            ))}
          </aside>

          <div className="flex min-w-0 flex-1 flex-col bg-panel2/40">
            <div className="min-h-0 flex-1 overflow-auto p-4">
              <div className="mx-auto h-full bg-white shadow-[0_10px_40px_rgba(15,23,42,.10)] transition-[width] duration-300"
                   style={{ width: frame.width, maxWidth: '100%' }}>
                {src ? (
                  <iframe key={`${showing}-${stamp}`} src={src} title={`${showing} preview`}
                          sandbox="allow-same-origin"
                          className="h-full w-full border-0" />
                ) : (
                  <p className="p-8 text-center text-[12px] text-muted">
                    No project to show.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        <footer className="shrink-0 border-t border-line/60 px-5 py-3">
          <div className="flex items-end gap-2">
            <textarea value={feedback} rows={2} disabled={Boolean(sending)}
                      placeholder="What should be different? “Make the buttons blue.” “The menu rows are too tall.” “Put the price above the description.”"
                      onChange={event => setFeedback(event.target.value)}
                      onKeyDown={event => {
                        if (event.key === 'Enter' && (event.metaKey || event.ctrlKey) && feedback.trim()) {
                          onAnswer({ decision: 'revise', feedback: feedback.trim() })
                        }
                      }}
                      className="min-h-[44px] flex-1 resize-y rounded-xl border border-line bg-white/70 px-3 py-2 text-[12.5px] leading-relaxed text-ink outline-none transition-colors focus:border-accent disabled:opacity-50 dark:bg-white/5" />
            <Button variant="outline" className="h-[44px]"
                    disabled={Boolean(sending) || !feedback.trim() || round > rounds}
                    onClick={() => onAnswer({ decision: 'revise', feedback: feedback.trim() })}>
              {sending === 'revise' ? <Loader2 className="size-3 animate-spin" />
                                    : <RotateCcw className="size-3" />}
              Redraw it
            </Button>
            <Button variant="solid" className="h-[44px]" disabled={Boolean(sending)}
                    onClick={() => onAnswer({ decision: 'approve' })}>
              {sending === 'approve' ? <Loader2 className="size-3 animate-spin" />
                                     : <Check className="size-3" />}
              Approve and build
            </Button>
          </div>
          <p className="mt-1.5 text-[10.5px] text-muted2">
            {round >= rounds
              ? 'Last round — the build starts after this.'
              : `Round ${round} of ${rounds}. Approving starts the real build from this drawing.`}
          </p>
        </footer>
      </div>
    </div>
  )
}
