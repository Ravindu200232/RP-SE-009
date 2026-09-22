'use client'

/** Renders and edits in-place HTML wireframes and their associated user journeys. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Loader2,
  Move,
  ArrowUpDown,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Maximize2,
  RotateCcw,
  Copy,
  Trash2,
  Type,
  Layers,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  RotateCcw as ResetIcon,
  Sparkles,
  Check,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button, Empty, Modal } from '../ui'

/** The `prj_…` id the drawings live under, whichever way the owner is named. */
function useSrsId(owner) {
  const [srsId, setSrsId] = useState(() => (/^prj_/.test(owner || '') ? owner : ''))
  useEffect(() => {
    if (!owner) return
    if (/^prj_/.test(owner)) { setSrsId(owner); return }
    // A built project owns its pages by name; `link.json` is the only thing
    // that knows both names, and the studio reads it through `srs-results`.
    let live = true
    api.srsResults(owner)
      .then(found => { if (live) setSrsId(found?.link?.srs_id || '') })
      .catch(() => {})
    return () => { live = false }
  }, [owner])
  return srsId
}

/** One page, rendered small and not interactive, with generation animation when drawing. */
function Thumbnail({ srsId, page, waiting }) {
  const isGenerating = waiting || page.drawing
  if (!srsId || !page.has_html) {
    return (
      <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden bg-[#0d1322]">
        <div className="absolute inset-0 opacity-15 bg-[radial-gradient(#1877F2_1px,transparent_1px)] [background-size:12px_12px]" />
        {isGenerating ? (
          <div className="relative z-10 flex flex-col items-center gap-2 text-center p-3">
            <div className="relative flex size-9 items-center justify-center rounded-xl bg-accent/20 border border-accent/40 shadow-[0_0_20px_rgba(24,119,242,0.3)]">
              <Sparkles className="size-4 text-accent animate-spin" style={{ animationDuration: '6s' }} />
              <div className="absolute inset-0 rounded-xl border border-accent/40 animate-ping opacity-30" />
            </div>
            <span className="text-[11px] font-semibold text-white tracking-wide">Drawing wireframe…</span>
            <span className="text-[9px] text-white/50">Synthesizing blueprint layout</span>
            <div className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-accent to-transparent animate-pulse" />
          </div>
        ) : (
          <span className="relative z-10 text-[11px] text-muted2">not drawn yet</span>
        )}
      </div>
    )
  }
  return (
    <div className="relative h-full w-full overflow-hidden bg-white">
      <iframe
        title={page.page_name || page.route}
        src={api.wireframeHtmlUrl(srsId, page.route)}
        loading="lazy"
        tabIndex={-1}
        aria-hidden="true"
        className={cn(
          "pointer-events-none origin-top-left border-0 transition-all duration-500",
          isGenerating && "filter blur-[4px] opacity-40 scale-[0.98]"
        )}
        style={{ width: '1280px', height: '1000px', transform: 'scale(0.23)' }}
      />
      {isGenerating && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0d1322]/75 backdrop-blur-[2px] z-10 transition-all">
          <div className="relative flex size-9 items-center justify-center rounded-xl bg-accent/25 border border-accent/50 shadow-[0_0_20px_rgba(24,119,242,0.4)]">
            <Sparkles className="size-4 text-accent animate-spin" style={{ animationDuration: '6s' }} />
            <div className="absolute inset-0 rounded-xl border border-accent/40 animate-ping opacity-30" />
          </div>
          <span className="mt-2 text-[11px] font-semibold text-white tracking-wide">Updating…</span>
          <span className="text-[9px] text-white/60 font-mono">Redrawing wireframe</span>
          <div className="absolute inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-accent to-transparent animate-pulse" />
        </div>
      )}
    </div>
  )
}

/* Interactive full-size wireframe editor canvas with Figma positioning and editing tools. */
export function WireframeEditor({ owner, page, onClose, onSaved, srsId: given = '' }) {
  const resolved = useSrsId(owner)
  const srsId = given || resolved

  const [drawing, setDrawing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState('')
  const [stamp, setStamp] = useState(page.has_html ? 1 : 0)
  const [stale, setStale] = useState(Boolean(page.html_stale))
  const [picked, setPicked] = useState('')
  const [dirty, setDirty] = useState(false)
  const [typing, setTyping] = useState(false)
  const [metrics, setMetrics] = useState(null)
  const [dragMode, setDragMode] = useState('free')
  const frame = useRef(null)
  const editor = useRef(null)

  // Query server directly for current wireframe HTML existence.
  useEffect(() => {
    if (!srsId) return
    let live = true
    fetch(api.wireframeHtmlUrl(srsId, page.route))
      .then(r => { if (live && r.ok) setStamp(n => n || 1) })
      .catch(() => {})
    return () => { live = false }
  }, [srsId, page.route])

  const [parts, setParts] = useState([])

  const attach = useCallback(() => {
    editor.current?.detach?.()
    import('@/lib/wireframe-html-editor').then(({ attachEditor, PARTS }) => {
      editor.current = attachEditor(frame.current, {
        onSelect: setPicked,
        onDirty: setDirty,
        onMetrics: setMetrics,
      })
      setParts(PARTS)
      if (!editor.current) setProblem('This page cannot be edited in place here.')
    })
  }, [])

  useEffect(() => () => editor.current?.detach?.(), [])

  async function draw() {
    setDrawing(true); setProblem('')
    try {
      await api.drawWireframeHtml(srsId, page.route)
      setStamp(n => n + 1)
      setStale(false); setDirty(false); setPicked(''); setTyping(false); setMetrics(null)
    } catch (failure) {
      setProblem(failure?.message || 'The page could not be drawn.')
    } finally {
      setDrawing(false)
    }
  }

  async function save() {
    if (!editor.current) return
    setSaving(true); setProblem('')
    try {
      if (typing) { editor.current.editText(false); setTyping(false) }
      await api.saveWireframeHtml(srsId, page.route, editor.current.serialize())
      editor.current.saved()
      onSaved?.(null)
    } catch (failure) {
      setProblem(failure?.message || 'That layout could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  const act = (name, ...args) => () => {
    editor.current?.[name]?.(...args)
    if (name === 'undo') {
      setStamp(n => n + 1)
      setDirty(false)
      setPicked('')
      setMetrics(null)
    }
  }

  const setMode = mode => {
    setDragMode(mode)
    editor.current?.setDragMode?.(mode)
  }

  const Tool = ({ onClick, children, on = false, always = false, title }) => (
    <button type="button" onClick={onClick} disabled={!picked && !always} title={title}
      className={cn('inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition cursor-pointer',
        'disabled:opacity-30 disabled:cursor-not-allowed',
        on ? 'bg-blue-600 text-white shadow-sm'
           : 'bg-white/[.06] text-white/75 hover:bg-white/[.12] hover:text-white')}>
      {children}
    </button>
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#121622]/90 shadow-2xl backdrop-blur-xl">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-black/30 px-5 py-3 backdrop-blur-md">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="outline" size="sm" onClick={onClose}
            className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/80 text-[11.5px]">
            ← Wireframes
          </Button>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold text-white">
              {page.page_name || page.route}
            </span>
            <span className="block truncate font-mono text-[10.5px] text-white/50">
              {page.route}{page.roles?.length ? ` · ${page.roles.join(', ')}` : ''}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {dirty && (
            <Button variant="solid" size="sm" onClick={save} disabled={saving}
              className="h-8 rounded-xl bg-blue-600 hover:bg-blue-500 text-[11.5px] text-white">
              {saving ? <><Loader2 className="mr-1 size-3 animate-spin" /> Saving…</> : 'Save page'}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={draw} disabled={drawing || !srsId}
            className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/80 text-[11.5px]">
            {drawing ? <><Loader2 className="mr-1 size-3 animate-spin" /> Drawing…</>
                     : stamp ? 'Draw again' : 'Draw this page'}
          </Button>
        </div>
      </div>

      {stamp ? (
        <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-white/10 bg-white/[.03] px-3.5 py-2 select-none">
          {/* Tool Mode: Free Move (Figma Canvas) vs Flow Reorder */}
          <div className="flex items-center rounded-lg bg-black/40 p-0.5 border border-white/10">
            <button
              type="button"
              onClick={() => setMode('free')}
              title="Move Tool (V): Drag with cursor to freely position anywhere"
              className={cn('flex items-center gap-1 rounded-md px-2 py-1 text-[10.5px] font-medium transition cursor-pointer',
                dragMode === 'free' ? 'bg-[#0D99FF] text-white font-semibold shadow-sm' : 'text-white/60 hover:text-white')}
            >
              <Move className="size-3" />
              <span>Move</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('flow')}
              title="Reorder Tool: Drag with cursor to drop between elements"
              className={cn('flex items-center gap-1 rounded-md px-2 py-1 text-[10.5px] font-medium transition cursor-pointer',
                dragMode === 'flow' ? 'bg-[#0D99FF] text-white font-semibold shadow-sm' : 'text-white/60 hover:text-white')}
            >
              <ArrowUpDown className="size-3" />
              <span>Reorder</span>
            </button>
          </div>

          <span className="mx-1 h-4 w-px bg-white/10" />

          {picked ? (
            <>
              {/* Selected Tag & Dimensions */}
              <span className="flex items-center gap-1 rounded-md bg-white/[.07] px-2 py-1 font-mono text-[10.5px] text-white/90 border border-white/10">
                <span className="text-[#0D99FF] font-semibold">&lt;{picked}&gt;</span>
                {metrics && (
                  <span className="text-white/50 text-[10px] ml-1">
                    {metrics.w}×{metrics.h}px
                  </span>
                )}
              </span>

              {/* Position Steppers (X, Y) */}
              <div className="flex items-center gap-1 rounded-md bg-black/30 px-1.5 py-0.5 border border-white/10 font-mono text-[10px]">
                <span className="text-white/40 uppercase font-semibold text-[9.5px]">X:</span>
                <button type="button" onClick={() => editor.current?.nudge?.(-5, 0)} className="px-1 text-white/70 hover:text-white hover:bg-white/10 rounded">-</button>
                <span className="text-white font-medium min-w-[28px] text-center">{metrics?.x ?? 0}px</span>
                <button type="button" onClick={() => editor.current?.nudge?.(5, 0)} className="px-1 text-white/70 hover:text-white hover:bg-white/10 rounded">+</button>
              </div>

              <div className="flex items-center gap-1 rounded-md bg-black/30 px-1.5 py-0.5 border border-white/10 font-mono text-[10px]">
                <span className="text-white/40 uppercase font-semibold text-[9.5px]">Y:</span>
                <button type="button" onClick={() => editor.current?.nudge?.(0, -5)} className="px-1 text-white/70 hover:text-white hover:bg-white/10 rounded">-</button>
                <span className="text-white font-medium min-w-[28px] text-center">{metrics?.y ?? 0}px</span>
                <button type="button" onClick={() => editor.current?.nudge?.(0, 5)} className="px-1 text-white/70 hover:text-white hover:bg-white/10 rounded">+</button>
              </div>

              {metrics?.hasOffset && (
                <button
                  type="button"
                  onClick={() => editor.current?.resetPos?.()}
                  title="Reset Position to 0,0"
                  className="rounded-md bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 px-1.5 py-1 text-[10px] font-medium transition cursor-pointer"
                >
                  Reset Pos
                </button>
              )}

              {/* Nudge D-Pad */}
              <div className="flex items-center rounded-md bg-white/[.05] p-0.5 border border-white/10">
                <button type="button" onClick={() => editor.current?.nudge?.(-1, 0)} title="Nudge Left (1px)" className="p-1 hover:bg-white/10 rounded text-white/70 hover:text-white">
                  <ArrowLeft className="size-2.5" />
                </button>
                <button type="button" onClick={() => editor.current?.nudge?.(0, -1)} title="Nudge Up (1px)" className="p-1 hover:bg-white/10 rounded text-white/70 hover:text-white">
                  <ArrowUp className="size-2.5" />
                </button>
                <button type="button" onClick={() => editor.current?.nudge?.(0, 1)} title="Nudge Down (1px)" className="p-1 hover:bg-white/10 rounded text-white/70 hover:text-white">
                  <ArrowDown className="size-2.5" />
                </button>
                <button type="button" onClick={() => editor.current?.nudge?.(1, 0)} title="Nudge Right (1px)" className="p-1 hover:bg-white/10 rounded text-white/70 hover:text-white">
                  <ArrowRight className="size-2.5" />
                </button>
              </div>

              <span className="mx-1 h-4 w-px bg-white/10" />

              {/* Alignments */}
              <Tool onClick={act('align', 'left')} title="Align Left"><AlignLeft className="size-3" /></Tool>
              <Tool onClick={act('align', 'center')} title="Align Centre"><AlignCenter className="size-3" /></Tool>
              <Tool onClick={act('align', 'right')} title="Align Right"><AlignRight className="size-3" /></Tool>
              <Tool onClick={act('align', 'full')} title="Full Width"><Maximize2 className="size-3" /></Tool>

              <span className="mx-1 h-4 w-px bg-white/10" />

              {/* Hierarchy */}
              <Tool onClick={act('parent')} title="Select Parent Container"><Layers className="size-3 mr-0.5" /> Parent</Tool>
              <Tool onClick={act('move', -1)} title="Move Up in DOM">↑</Tool>
              <Tool onClick={act('move', 1)} title="Move Down in DOM">↓</Tool>

              {/* Size */}
              <Tool onClick={act('wider', -10)} title="Narrower">-10%</Tool>
              <Tool onClick={act('wider', 10)} title="Wider">+10%</Tool>

              <span className="mx-1 h-4 w-px bg-white/10" />

              {/* Actions */}
              <Tool onClick={act('duplicate')} title="Duplicate Element"><Copy className="size-3" /></Tool>
              <Tool onClick={act('remove')} title="Delete Element"><Trash2 className="size-3 text-rose-300" /></Tool>
              <Tool on={typing} onClick={() => { editor.current?.editText(!typing); setTyping(!typing) }} title="Edit Text Directly">
                <Type className="size-3" />
                <span>{typing ? 'Done typing' : 'Text'}</span>
              </Tool>
            </>
          ) : (
            <span className="flex items-center gap-1.5 font-mono text-[11px] text-white/45">
              <Move className="size-3 text-[#0D99FF]" />
              <span>Click any element to drag with cursor · Drag corner handles to resize · Arrow keys to nudge</span>
            </span>
          )}

          <span className="flex-1" />
          <Tool always onClick={act('undo')} title="Undo last change (Ctrl+Z)">
            <RotateCcw className="size-3" />
            <span>Undo</span>
          </Tool>
        </div>
      ) : null}

      {stale && stamp ? (
        <p className="shrink-0 border-b border-amber-400/20 bg-amber-400/10 px-4 py-2 text-[11.5px] text-amber-200">
          The specification has changed since this page was drawn — draw it again to bring it up to date.
        </p>
      ) : null}
      {problem ? (
        <p role="alert" className="shrink-0 border-b border-rose-400/20 bg-rose-500/10 px-4 py-2 text-[11.5px] text-rose-300">
          {problem}
        </p>
      ) : null}

      {stamp ? (
        <div className="flex min-h-0 flex-1">
          {/* The catalogue. A part is inserted after whatever is picked, so
              building a page is: pick the thing it goes under, then add it. */}
          <aside className="w-[188px] shrink-0 overflow-y-auto border-r border-white/10 bg-[#0d111a] p-3">
            <p className="mb-2 font-display text-[10.5px] font-bold uppercase tracking-wider text-white/70">
              Add components
            </p>
            <p className="mb-3 text-[10px] leading-snug text-white/35">
              {picked ? 'Goes in after the part you picked.' : 'Goes in the visible area.'}
            </p>
            {parts.map(([group, items]) => (
              <div key={group} className="mb-3">
                <p className="mb-1.5 text-[9.5px] font-semibold uppercase tracking-wider text-white/35">
                  {group}
                </p>
                <div className="grid grid-cols-2 gap-1">
                  {items.map(([kind, label]) => (
                    <button key={kind} type="button" onClick={act('insert', kind)}
                      className="rounded-md bg-white/[.05] px-2 py-1.5 text-left text-[10.5px]
                                 text-white/70 transition hover:bg-white/[.12] hover:text-white">
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </aside>
          <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden bg-white">
            {drawing && (
              <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-[#0a0f1d]/85 backdrop-blur-md transition-all duration-300">
                <div className="absolute inset-0 opacity-15 bg-[radial-gradient(#1877F2_1px,transparent_1px)] [background-size:20px_20px]" />
                <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-[#0D99FF] to-transparent animate-pulse shadow-[0_0_20px_#0D99FF]" />
                <div className="relative z-10 flex flex-col items-center rounded-2xl border border-white/15 bg-white/[0.04] p-8 shadow-2xl backdrop-blur-2xl text-center max-w-sm">
                  <div className="relative flex size-14 items-center justify-center rounded-2xl bg-blue-500/20 border border-blue-400/40 shadow-[0_0_35px_rgba(13,153,255,0.4)]">
                    <Sparkles className="size-7 text-[#0D99FF] animate-spin" style={{ animationDuration: '7s' }} />
                    <div className="absolute inset-0 rounded-2xl border-2 border-[#0D99FF] animate-ping opacity-30" />
                  </div>
                  <h3 className="mt-4 text-[15px] font-bold tracking-tight text-white">Updating Wireframe…</h3>
                  <p className="mt-1 text-[12px] leading-relaxed text-slate-300">
                    Generating updated layout structure and blueprint components for <span className="font-mono text-blue-400 font-semibold">{page.route}</span>.
                  </p>
                  <div className="mt-4 flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 font-mono text-[10.5px] text-blue-300">
                    <Loader2 className="size-3 animate-spin text-blue-400" />
                    <span>Drawing wireframe…</span>
                  </div>
                </div>
              </div>
            )}
            <iframe
              key={stamp}
              ref={frame}
              onLoad={attach}
              title={`${page.page_name || page.route} wireframe`}
              src={srsId ? api.wireframeHtmlUrl(srsId, page.route) : 'about:blank'}
              className={cn(
                "min-h-0 min-w-0 flex-1 border-0 bg-white transition-all duration-500",
                drawing && "filter blur-[6px] scale-[0.99] opacity-40 pointer-events-none"
              )}
            />
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 items-center justify-center bg-[#0a0d14] text-[12px] text-muted">
          {srsId ? `Nothing drawn for ${page.route} yet.`
                 : 'This project has no specification to draw from.'}
        </div>
      )}
    </div>
  )
}

/** The modal the workspace opens a page in. */
function PageEditor({ owner, page, onClose, onSaved, srsId = '' }) {
  return (
    <Modal
      onClose={onClose}
      overlayClassName="!p-0 backdrop-blur-none"
      style={{ maxWidth: 'none', width: '100%', height: '100%', maxHeight: '100%' }}
      className="overflow-hidden rounded-none border-0 p-0"
    >
      <div className="flex h-full min-h-0 gap-4 bg-[#0a0d14] p-5">
        <WireframeEditor owner={owner} srsId={srsId} page={page}
          onClose={onClose} onSaved={onSaved} />
      </div>
    </Modal>
  )
}

export function Wireframes({ srs, onEditPage }) {
  const owner = srs?.project || srs?.srs_id || srs?.id || ''
  const srsId = useSrsId(owner)
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')
  const [drawing, setDrawing] = useState(false)
  const [selectedForDel, setSelectedForDel] = useState([])
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(() => {
    if (!owner) return
    api.wireframes(owner)
      .then(setData)
      .catch(failure => setError(failure?.message || 'The wireframes could not be read.'))
  }, [owner])

  useEffect(() => { load() }, [load])

  /** Poll wireframes status periodically while page drawings are being generated. */
  const waiting = Boolean(data?.drawing)
  useEffect(() => {
    if (!waiting) return
    const again = setInterval(load, 4000)
    return () => clearInterval(again)
  }, [waiting, load])

  /** Draw every page that has no drawing yet, and redraw the rest. */
  async function drawAll() {
    if (!srsId) return
    setDrawing(true); setError('')
    try {
      await api.drawWireframeHtml(srsId)
      load()
    } catch (failure) {
      setError(failure?.message || 'The pages could not be drawn.')
    } finally {
      setDrawing(false)
    }
  }

  function openDeleteModal(routesToSelect = []) {
    setSelectedForDel(routesToSelect)
    setDeleteModalOpen(true)
  }

  function toggleDelRoute(route) {
    setSelectedForDel(prev =>
      prev.includes(route) ? prev.filter(r => r !== route) : [...prev, route]
    )
  }

  function selectAllForDel() {
    const drawnRoutes = pages.filter(p => p.has_html).map(p => p.route)
    setSelectedForDel(drawnRoutes)
  }

  function deselectAllForDel() {
    setSelectedForDel([])
  }

  /** Delete selected wireframes by clearing their HTML. */
  async function deleteSelectedWireframes() {
    if (!srsId || !selectedForDel.length) return
    setDeleting(true)
    try {
      await Promise.all(
        selectedForDel.map(route => api.saveWireframeHtml(srsId, route, ''))
      )
      load()
      setDeleteModalOpen(false)
      setSelectedForDel([])
    } catch (failure) {
      setError(failure?.message || 'The selected wireframes could not be deleted.')
    } finally {
      setDeleting(false)
    }
  }

  const pages = data?.pages || []
  if (error) return <Empty>{error}</Empty>
  if (!data) return <Empty>Reading the wireframes…</Empty>
  if (!pages.length) return <Empty>No pages in the specification yet, so there is nothing to draw.</Empty>

  const drawn = pages.filter(p => p.has_html).length

  return (
    <div className="space-y-3">
      {/* Visual progress indicator displayed while wireframe pages are being drawn. */}
      {waiting && (
        <p className="flex items-center gap-2.5 rounded-xl border border-accent/30 bg-accent/[.06]
                      px-3.5 py-2.5 text-[11.5px] leading-relaxed text-ink">
          <Loader2 className="size-3.5 shrink-0 animate-spin text-accent" />
          <span>
            Drawing the pages — each one is drawn on its own, so they appear as
            they finish. {drawn} of {pages.length} so far. You can carry on; this
            keeps going without you.
          </span>
        </p>
      )}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-[11.5px] text-muted">
          {pages.length} page{pages.length === 1 ? '' : 's'}, black and white, with sample data.
          Open one to move things, retype them, or ask for a change.
          {drawn === pages.length
            ? ' All drawn.'
            : ` ${drawn} of ${pages.length} drawn so far.`}
        </p>
        <div className="flex items-center gap-2">
          {pages.some(p => p.has_html) && (
            <Button
              variant="outline"
              disabled={drawing || waiting || deleting || !srsId}
              onClick={() => openDeleteModal(pages.filter(p => p.has_html).map(p => p.route))}
              className="border-rose-500/30 text-rose-300 hover:bg-rose-500/10 hover:border-rose-500/50"
            >
              <Trash2 className="mr-1.5 size-3.5 text-rose-400" />
              Delete wireframes…
            </Button>
          )}
          <Button variant="outline" disabled={drawing || waiting || !srsId} onClick={drawAll}>
            {drawing || waiting
              ? <><Loader2 className="mr-1 size-3 animate-spin" /> Drawing…</>
              : drawn ? 'Draw them again' : 'Draw every page'}
          </Button>
        </div>
      </div>
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
        {pages.map((page, index) => (
          <div key={`${page.route || 'wireframe'}-${index}`} className="group relative">
            <button type="button"
              onClick={() => (onEditPage ? onEditPage(page) : setOpen(page))}
              className="w-full overflow-hidden rounded-xl border border-line text-left transition hover:border-accent cursor-pointer">
              <span className="block aspect-[16/11] overflow-hidden border-b border-line bg-white">
                <Thumbnail srsId={srsId} page={page} waiting={waiting} />
              </span>
              <span className="block space-y-1 p-3">
                <span className="truncate block text-[12px] font-medium text-ink">{page.page_name}</span>
                <span className="block truncate font-mono text-[10px] text-muted2">{page.route}</span>
                <span className="block truncate text-[10px] text-muted2">
                  {page.roles?.length ? page.roles.join(', ') : 'public'}
                  {page.html_stale ? ' · out of date' : ''}
                </span>
              </span>
            </button>
            {/* Delete button — visible on hover, opens confirmation dialog with page ticked */}
            {page.has_html && (
              <button
                type="button"
                title="Delete wireframe"
                onClick={e => { e.stopPropagation(); openDeleteModal([page.route]) }}
                className="absolute right-2 top-2 z-10 flex items-center justify-center rounded-lg
                           bg-black/60 p-1.5 text-white/70 opacity-0 transition
                           hover:bg-rose-600 hover:text-white
                           group-hover:opacity-100 cursor-pointer"
              >
                <Trash2 className="size-3.5" />
              </button>
            )}
          </div>
        ))}
      </div>
      {open && (
        <PageEditor owner={owner} srsId={srsId} page={open}
          onClose={() => setOpen(null)}
          onSaved={() => { load(); setOpen(null) }} />
      )}
      {/* Delete confirmation modal with checkboxes (tick marks) */}
      {deleteModalOpen && (
        <Modal onClose={() => !deleting && setDeleteModalOpen(false)}>
          <div className="space-y-4 max-w-lg w-full">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-rose-500/15">
                <Trash2 className="size-4 text-rose-400" />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="text-[15px] font-bold text-ink">Delete wireframe pages?</h3>
                <p className="mt-1 text-[12px] leading-relaxed text-muted">
                  Select which wireframe HTML layouts to delete. Ticked pages will be cleared and reset to ungenerated status. This action cannot be undone.
                </p>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center justify-between border-y border-line py-2 text-[11.5px]">
              <span className="font-medium text-muted">
                {selectedForDel.length} of {pages.filter(p => p.has_html).length} selected
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={selectAllForDel}
                  className="text-accent hover:underline cursor-pointer"
                >
                  Select all
                </button>
                <span className="text-muted2">·</span>
                <button
                  type="button"
                  onClick={deselectAllForDel}
                  className="text-muted hover:text-ink cursor-pointer"
                >
                  Clear selection
                </button>
              </div>
            </div>

            {/* Scrollable list with checkboxes */}
            <div className="max-h-[300px] overflow-y-auto space-y-1.5 pr-1">
              {pages.filter(p => p.has_html).map(p => {
                const checked = selectedForDel.includes(p.route)
                return (
                  <label
                    key={p.route}
                    className={cn(
                      "flex items-center gap-3 rounded-xl border p-2.5 transition cursor-pointer select-none",
                      checked
                        ? "border-rose-500/50 bg-rose-500/10 text-white"
                        : "border-line bg-panel2/40 text-muted hover:bg-panel2 hover:text-ink"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleDelRoute(p.route)}
                      className="size-4 rounded accent-rose-600 cursor-pointer"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-semibold text-[12.5px] truncate text-ink">
                          {p.page_name || p.route}
                        </span>
                        <code className="text-[10px] font-mono text-muted2 shrink-0">
                          {p.route}
                        </code>
                      </div>
                      <span className="text-[10.5px] text-muted2 block truncate">
                        {p.roles?.length ? p.roles.join(', ') : 'public'}
                      </span>
                    </div>
                  </label>
                )
              })}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-line">
              <Button
                variant="outline"
                onClick={() => setDeleteModalOpen(false)}
                disabled={deleting}
              >
                Cancel
              </Button>
              <Button
                variant="solid"
                onClick={deleteSelectedWireframes}
                disabled={deleting || selectedForDel.length === 0}
                className="bg-rose-600 hover:bg-rose-500 text-white shadow-sm"
              >
                {deleting ? (
                  <><Loader2 className="mr-1.5 size-3 animate-spin" />Deleting…</>
                ) : (
                  `Delete ${selectedForDel.length} wireframe${selectedForDel.length === 1 ? '' : 's'}`
                )}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export function UserJourney({ srs }) {
  const owner = srs?.project || srs?.srs_id || srs?.id || ''
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!owner) return
    api.wireframes(owner).then(setData).catch(() => setData({ journeys: [] }))
  }, [owner])

  const journeys = data?.journeys || []
  const routes = useMemo(
    () => new Map((data?.pages || []).map(p => [p.route, p.page_name])), [data])

  if (!data) return <Empty>Reading the journeys…</Empty>
  if (!journeys.length) return <Empty>No workflows in the specification yet.</Empty>

  return (
    <div className="space-y-4">
      <p className="text-[11.5px] text-muted">
        {journeys.length} journey{journeys.length === 1 ? '' : 's'} through the product, each step
        on the screen it happens on. A step marked <span className="text-muted2">carried</span> did
        not name a screen itself — it continues on the one before it.
      </p>
      {journeys.map(flow => (
        <div key={flow.workflow_name} className="rounded-xl border border-line bg-panel p-4">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h3 className="text-[13px] font-semibold text-ink">{flow.workflow_name}</h3>
            {flow.who && <span className="text-[11px] text-muted2">{flow.who}</span>}
          </div>
          <ol className="mt-3 space-y-0">
            {flow.steps.map((step, i) => (
              <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                <span className="relative flex flex-col items-center">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full
                                   border border-line bg-panel2 font-mono text-[10px] text-muted">
                    {i + 1}
                  </span>
                  {i < flow.steps.length - 1 && (
                    <span className="mt-1 w-px flex-1 bg-line" />
                  )}
                </span>
                <span className="min-w-0 flex-1 pb-1">
                  <span className="block text-[11.5px] text-ink">{step.step}</span>
                  {step.route && (
                    <span className="mt-0.5 flex flex-wrap items-baseline gap-2">
                      <code className="font-mono text-[10px] text-accent">{step.route}</code>
                      <span className="text-[10px] text-muted2">
                        {routes.get(step.route) || ''}{step.named === false ? ' · carried' : ''}
                      </span>
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}
