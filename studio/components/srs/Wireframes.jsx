'use client'

/**
 * Black-and-white wireframes, and the journeys that run through them.
 *
 * The layouts are a projection of the specification, so there is nothing to
 * generate here and nothing to wait for — opening this view reads a file the
 * document already wrote. No colour is drawn and no navigation: a wireframe
 * answers "what is on this page", and a navbar repeated on every page answers
 * it once too often.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import { Badge, Button, Empty, Input, Modal } from '../ui'

// Every block is placed on a 0–100 grid, so one number works at thumbnail size
// and at full size alike.
const pc = n => `${n}%`

const KINDS = ['heading', 'title', 'text', 'field', 'button', 'table', 'cards',
               'list', 'image', 'icon', 'divider', 'rating', 'stat', 'panel',
               'tabs', 'chart', 'nav', 'footer']

/** One block, drawn in line and grey only. */
function Block({ block, scale = 1, canvas = 100, selected, onPick }) {
  const { kind, label, w, h } = block
  const line = 'border border-[#8a8a8a]'
  // One grid unit in pixels. The canvas is 100 units wide and `canvas` units
  // tall, and a unit is square, so both come from the measured width.
  const px = scale / 100
  const small = h * px < 9
  const common0 = {
    position: 'absolute', left: pc(block.x), top: pc(100 * block.y / canvas),
    width: pc(w), height: pc(100 * h / canvas),
  }
  const pick = onPick ? e => { e.stopPropagation(); onPick(block.id) } : undefined
  const ring = selected ? 'outline outline-2 outline-[#1877F2]' : ''
  // Sizes are computed per frame, so they go in `style`: a class name built at
  // runtime is not in the stylesheet Tailwind generated and styles nothing.
  // `scale` is the frame's real width in pixels, measured - a guessed
  // multiplier made the same block unreadably small in a card and clipped in
  // the full-screen dialog.
  const size = Math.max(4, Math.min(13, Math.round(scale * 0.011)))
  const text = 'overflow-hidden leading-tight'
  const common = { ...common0, fontSize: `${size}px` }

  if (kind === 'title') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-center font-semibold text-[#111] ${text} ${ring}`}>
      <span className="truncate">{label}</span>
    </div>
  }
  if (kind === 'text') {
    const lines = Array.isArray(block.lines) ? block.lines : null
    if (lines && h * px > 16) {
      return <div style={common} onMouseDown={pick}
        className={`flex flex-col justify-center overflow-hidden ${text} ${ring}`}>
        {lines.slice(0, 4).map((l, i) => (
          <span key={i} className="truncate text-[#555]">{String(l)}</span>
        ))}
      </div>
    }
    return <div style={common} onMouseDown={pick} className={`flex flex-col justify-center gap-[2px] ${ring}`}>
      <span className="block h-[2px] w-full bg-[#c9c9c9]" />
      <span className="block h-[2px] w-4/5 bg-[#c9c9c9]" />
      <span className="block h-[2px] w-3/5 bg-[#c9c9c9]" />
    </div>
  }
  if (kind === 'button') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-center justify-center bg-[#2b2b2b] text-white ${text} ${ring}`}>
      {!small && <span className="truncate px-1">{label}</span>}
    </div>
  }
  if (kind === 'field') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-center gap-1 overflow-hidden bg-white ${line} ${text} ${ring}`}>
      {!small && <span className="shrink-0 truncate px-1 text-[#999]">{label}</span>}
      {!small && block.value && <span className="truncate text-[#333]">{block.value}</span>}
    </div>
  }
  if (kind === 'stat') {
    return <div style={common} onMouseDown={pick}
      className={`flex flex-col justify-center gap-[3px] bg-white px-1 ${line} ${text} ${ring}`}>
      {!small && <span className="truncate text-[#999]">{label}</span>}
      {block.value
        ? <span className="truncate font-semibold text-[#111]"
                style={{ fontSize: `${Math.max(size, Math.min(Math.round(size * 1.9), Math.round(h * px * 0.5)))}px` }}>
            {block.value}
          </span>
        : <span className="block h-[5px] w-2/3 bg-[#2b2b2b]" />}
    </div>
  }
  if (kind === 'chart') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-end gap-[3px] bg-white p-1 ${line} ${ring}`}>
      {[40, 65, 30, 80, 55, 70, 45].map((v, i) => (
        <span key={i} className="flex-1 bg-[#c9c9c9]" style={{ height: `${v}%` }} />
      ))}
    </div>
  }
  if (kind === 'table') {
    // Sample rows are what makes a wireframe reviewable, so they are drawn as
    // text whenever there is room. Below that size the bars are all that fits.
    const columns = block.columns?.length ? block.columns : null
    const sample = Array.isArray(block.sample) ? block.sample : []
    const cols = columns?.length || sample[0]?.length || 4
    const fits = h * px > 26 && w * scale / 100 > 90
    const rows = fits && sample.length
      ? sample.slice(0, Math.max(1, Math.floor((h * px - size * 1.8) / (size * 2.2))))
      : Array.from({ length: Math.max(2, Math.min(block.rows || 5, Math.floor(h * px / 10))) })
    return <div style={common} onMouseDown={pick} className={`flex flex-col bg-white ${line} ${ring}`}>
      <div className="flex shrink-0 border-b border-[#8a8a8a] bg-[#ededed]">
        {Array.from({ length: cols }).map((_, i) => (
          <span key={i} className={`flex-1 overflow-hidden border-r border-[#d6d6d6] px-[2px] py-[2px]
                                    last:border-r-0 ${text}`}>
            {fits && columns
              ? <span className="block truncate font-semibold text-[#4a4a4a]">{columns[i]}</span>
              : <span className="block h-[3px] w-3/4 bg-[#9a9a9a]" />}
          </span>
        ))}
      </div>
      {rows.map((row, r) => (
        <div key={r} className="flex flex-1 border-b border-[#e4e4e4] last:border-b-0">
          {Array.from({ length: cols }).map((_, i) => (
            <span key={i} className={`flex flex-1 items-center overflow-hidden border-r
                                      border-[#efefef] px-[2px] last:border-r-0 ${text}`}>
              {fits && Array.isArray(row)
                ? <span className="block truncate text-[#555]">{String(row[i] ?? '')}</span>
                : <span className="block h-[2px] w-2/3 bg-[#d2d2d2]" />}
            </span>
          ))}
        </div>
      ))}
    </div>
  }
  if (kind === 'cards' || kind === 'list') {
    const items = Array.isArray(block.items) ? block.items : null
    const n = items?.length || (kind === 'cards' ? 3 : 4)
    const room = h * px > 24
    return <div style={common} onMouseDown={pick} className={ring}>
      <div className={kind === 'cards'
        ? 'grid h-full gap-[3px]'
        : 'flex h-full flex-col gap-[3px]'}
        style={kind === 'cards' ? { gridTemplateColumns: `repeat(${Math.min(n, 4)}, 1fr)` } : undefined}>
        {Array.from({ length: Math.min(n, 8) }).map((_, i) => (
          <span key={i} className={`flex flex-1 flex-col justify-center overflow-hidden bg-white px-1 ${line} ${text}`}>
            {room && items?.[i] && <>
              <span className="truncate font-semibold text-[#333]">{items[i].title}</span>
              <span className="truncate text-[#999]">{items[i].meta}</span>
            </>}
          </span>
        ))}
      </div>
    </div>
  }
  if (kind === 'image') {
    // The wireframe convention: an outlined box with both diagonals. It reads
    // as "a picture goes here" at any size, which a grey rectangle does not.
    return <div style={common} onMouseDown={pick} className={ring}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none"
        className="h-full w-full" aria-hidden="true">
        <rect x="0.6" y="0.6" width="98.8" height="98.8" fill="none"
          stroke="#2b2b2b" strokeWidth="0.9" vectorEffect="non-scaling-stroke" />
        <path d="M0.6 0.6 L99.4 99.4 M99.4 0.6 L0.6 99.4" fill="none"
          stroke="#2b2b2b" strokeWidth="0.9" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  }
  if (kind === 'icon') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-center justify-center ${ring}`}>
      <span className="flex aspect-square h-full items-center justify-center rounded-full
                       border border-[#2b2b2b] text-[#2b2b2b]">
        {!small && <span className="truncate px-1">{label || 'Icon'}</span>}
      </span>
    </div>
  }
  if (kind === 'divider') {
    // A rule with the section's name sitting in a box on it.
    return <div style={common} onMouseDown={pick}
      className={`flex items-center justify-center ${ring}`}>
      <span className="absolute left-0 right-0 top-1/2 h-px bg-[#2b2b2b]" />
      {label && <span className="relative truncate border border-[#2b2b2b] bg-white px-2 py-[1px]
                                 text-[#2b2b2b]">{label}</span>}
    </div>
  }
  if (kind === 'rating') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-center gap-[2px] text-[#2b2b2b] ${text} ${ring}`}>
      {'☆☆☆☆☆'.split('').map((s, i) => <span key={i}>{s}</span>)}
    </div>
  }
  if (kind === 'nav') {
    const links = Array.isArray(block.items) ? block.items
      : String(block.label || 'Home, About, Services').split(/\s*,\s*/)
    return <div style={common} onMouseDown={pick}
      className={`flex items-center justify-between gap-2 border-b border-[#2b2b2b] bg-white px-2 ${text} ${ring}`}>
      <span className="shrink-0 font-bold tracking-wide text-[#111]"
        style={{ fontSize: `${Math.round(size * 1.5)}px` }}>
        {block.value || 'LOGO'}
      </span>
      {!small && <span className="flex min-w-0 items-center gap-3 overflow-hidden text-[#555]">
        {links.slice(0, 5).map((l, i) => (
          <span key={i} className="truncate uppercase tracking-wide">{String(l.title || l)}</span>
        ))}
        <span className="shrink-0 border border-[#2b2b2b] px-2 py-[1px] uppercase">Login</span>
      </span>}
    </div>
  }
  if (kind === 'footer') {
    return <div style={common} onMouseDown={pick}
      className={`flex items-start justify-between gap-4 border-t border-[#2b2b2b] bg-white px-2 pt-2 ${text} ${ring}`}>
      <span className="shrink-0">
        <span className="block font-bold tracking-wide text-[#111]"
          style={{ fontSize: `${Math.round(size * 1.6)}px` }}>{block.value || 'LOGO'}</span>
        <span className="mt-1 block h-[2px] w-16 bg-[#c9c9c9]" />
        <span className="mt-1 block h-[2px] w-12 bg-[#c9c9c9]" />
      </span>
      <span className="flex gap-3">
        {[0, 1, 2].map(c => (
          <span key={c} className="flex flex-col gap-1">
            {[0, 1, 2].map(r => (
              <span key={r} className="block h-[6px] w-14 border border-[#c9c9c9]" />
            ))}
          </span>
        ))}
      </span>
    </div>
  }
  if (kind === 'heading') {
    return <div style={common} onMouseDown={pick}
      className={`flex flex-col justify-center overflow-hidden font-bold leading-[1.12] text-[#111] ${ring}`}>
      <span style={{ fontSize: `${Math.max(size, Math.round(h * px * 0.34))}px` }}>
        {label}
      </span>
    </div>
  }
  // panel, tabs and anything unknown: an outlined region with its name.
  return <div style={common} onMouseDown={pick}
    className={`bg-white/40 ${line} ${ring}`}>
    {!small && <span className={`block truncate px-1 pt-[2px] text-[#8a8a8a] ${text}`}>{label}</span>}
  </div>
}

/**
 * One page's frame. The same renderer for a thumbnail and for the editor.
 *
 * It measures itself rather than taking a size hint, because the only honest
 * answer to "is there room for this text" is how many pixels wide the frame
 * actually is — the same block sits in a 230px card and in a 1000px dialog.
 */
function Frame({ page, selected, onPick, onBackground, fit }) {
  const [width, setWidth] = useState(0)
  const box = useCallback(node => {
    if (!node) return
    setWidth(node.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const watch = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    watch.observe(node)
    return () => watch.disconnect()
  }, [])

  // A page is as tall as it needs to be. A landing page runs to several screens
  // and boxing it into one made every section a sliver; `canvas` is that height
  // in grid units, so 100 is a screenful and 260 is a long scrolling page.
  const blocks = page?.blocks || []
  const canvas = Math.max(100, page?.canvas || 0,
                          ...blocks.map(b => (b.y || 0) + (b.h || 0)))
  // In a card the whole page is shown at once; in the dialog it scrolls at a
  // readable width, which is how a wireframe of a long page is actually read.
  const height = fit ? null : Math.round(width * canvas / 100)

  return (
    <div ref={box} onMouseDown={onBackground}
      className={`relative w-full bg-white ${fit ? 'h-full overflow-hidden' : ''}`}
      style={{ contain: 'paint', height: height ?? undefined }}>
      {width > 0 && blocks.map(block => (
        <Block key={block.id} block={block} scale={width} canvas={canvas}
          selected={selected === block.id} onPick={onPick} />
      ))}
    </div>
  )
}

const STEP = 2

/** What the tools can do. Position, size, label, kind — never colour. */
function Tools({ block, onChange, onRemove, onAdd }) {
  if (!block) {
    return (
      <div className="space-y-2">
        <p className="text-[11.5px] text-muted">
          Select a block to move, resize or rename it. Wireframes carry no colour by
          design — the palette belongs to the design screen.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {KINDS.map(kind => (
            <button key={kind} type="button" onClick={() => onAdd(kind)}
              className="rounded-ctl border border-line px-2 py-1 text-[11px] text-muted hover:text-ink">
              + {kind}
            </button>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <select value={block.kind} onChange={e => onChange({ ...block, kind: e.target.value })}
          aria-label="Block kind"
          className="rounded border border-line bg-panel2 px-2 py-1 text-[11px] text-ink">
          {KINDS.map(k => <option key={k}>{k}</option>)}
        </select>
        <Input value={block.label || ''} onChange={e => onChange({ ...block, label: e.target.value })}
          placeholder="Label" aria-label="Block label"
          className="min-w-0 flex-1 rounded border border-line bg-panel2 px-2 py-1 text-[11px]" />
        <button type="button" onClick={onRemove}
          className="shrink-0 text-[11px] text-muted underline hover:text-bad">remove</button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Pad label="Position" onMove={(dx, dy) => {
          onChange({ ...block, x: Math.max(0, Math.min(100 - block.w, block.x + dx * STEP)),
                     y: Math.max(0, Math.min(100 - block.h, block.y + dy * STEP)) })
        }} />
        <Pad label="Size" onMove={(dx, dy) => {
          onChange({ ...block, w: Math.max(4, Math.min(100 - block.x, block.w + dx * STEP)),
                     h: Math.max(3, Math.min(100 - block.y, block.h + dy * STEP)) })
        }} />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Quick label="Full width" onClick={() => onChange({ ...block, x: 4, w: 92 })} />
        <Quick label="Left half" onClick={() => onChange({ ...block, x: 4, w: 44 })} />
        <Quick label="Right half" onClick={() => onChange({ ...block, x: 52, w: 44 })} />
        <Quick label="Centre" onClick={() => onChange({ ...block, x: Math.round((100 - block.w) / 2) })} />
        <Quick label="To top" onClick={() => onChange({ ...block, y: 5 })} />
      </div>
      <p className="font-mono text-[10px] text-muted2">
        x {block.x} · y {block.y} · w {block.w} · h {block.h}
      </p>
    </div>
  )
}

function Quick({ label, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className="rounded-ctl border border-line px-2 py-1 text-[11px] text-muted hover:text-ink">
      {label}
    </button>
  )
}

function Pad({ label, onMove }) {
  const arrow = 'rounded border border-line px-2 py-1 text-[11px] text-muted hover:text-ink'
  return (
    <div>
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[1px] text-muted2">{label}</p>
      <div className="grid w-fit grid-cols-3 gap-1">
        <span />
        <button type="button" className={arrow} onClick={() => onMove(0, -1)} aria-label={`${label} up`}>↑</button>
        <span />
        <button type="button" className={arrow} onClick={() => onMove(-1, 0)} aria-label={`${label} left`}>←</button>
        <span />
        <button type="button" className={arrow} onClick={() => onMove(1, 0)} aria-label={`${label} right`}>→</button>
        <span />
        <button type="button" className={arrow} onClick={() => onMove(0, 1)} aria-label={`${label} down`}>↓</button>
        <span />
      </div>
    </div>
  )
}

/** The one page being edited. Nothing here can reach another page. */
function PageEditor({ owner, page, onClose, onSaved }) {
  const [blocks, setBlocks] = useState(page.blocks || [])
  const [picked, setPicked] = useState('')
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState('')
  const [ask, setAsk] = useState('')
  const [asking, setAsking] = useState(false)
  // The wireframe is the thing being looked at; the tools are only wanted while
  // something is being moved. Hidden, they give the frame the whole window.
  const [showTools, setShowTools] = useState(false)

  const block = blocks.find(b => b.id === picked) || null
  const dirty = JSON.stringify(blocks) !== JSON.stringify(page.blocks || [])

  function change(next) {
    setBlocks(list => list.map(b => (b.id === next.id ? next : b)))
  }
  function add(kind) {
    const id = `b${Date.now().toString(36)}`
    setBlocks(list => [...list, { id, kind, label: kind, x: 4, y: 40, w: 40, h: 10 }])
    setPicked(id)
  }
  function remove() {
    setBlocks(list => list.filter(b => b.id !== picked))
    setPicked('')
  }

  async function save() {
    setSaving(true); setProblem('')
    try {
      const answer = await api.editWireframe(owner, page.route, blocks)
      onSaved?.(answer)
      onClose()
    } catch (failure) {
      setProblem(failure?.message || 'That layout could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  // Everything the tools cannot express goes to the specification as a change,
  // which re-derives this page's wireframe along with the document.
  async function request() {
    const text = ask.trim()
    if (!text) return
    setAsking(true); setProblem('')
    try {
      await api.srs(`/projects/${owner}/changes`, {
        change_id: `wireframe-${Date.now().toString(36)}`,
        source: 'design-customizer',
        summary: `For the ${page.page_name} page (${page.route}): ${text}`,
      })
      setAsk('')
      onSaved?.(null)
      onClose()
    } catch (failure) {
      setProblem(failure?.message || 'That request could not be sent.')
    } finally {
      setAsking(false)
    }
  }

  // Full screen: a wireframe is read at the size the page will be, and a
  // dialog two thirds the width of the window makes every block smaller than
  // the thing it stands for.
  return (
    <Modal onClose={onClose}
      // The whole window: no padding around it and no blur showing past its
      // edges, because a wireframe is read at the size the page will be.
      // Inline, because the dialog's own max-width is a class and whichever of
      // the two lands last in the stylesheet would otherwise decide the size.
      overlayClassName="!p-0 backdrop-blur-none"
      style={{ maxWidth: 'none', width: '100%', height: '100%', maxHeight: '100%' }}
      className="overflow-hidden rounded-none border-0 p-0">
      <div role="dialog" aria-modal="true" aria-label={`${page.page_name} wireframe`}
        className="flex h-full min-h-0 flex-col">
        <div className="flex shrink-0 flex-wrap items-baseline justify-between gap-3 border-b border-line p-4">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-ink">{page.page_name}</h3>
            <p className="mt-0.5 font-mono text-[11px] text-muted2">
              {page.route} · {page.roles?.length ? page.roles.join(', ') : 'public'}
              {page.edited && ' · edited by hand'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setShowTools(v => !v)}>
              {showTools ? 'Hide tools' : 'Edit'}
            </Button>
            <Button variant="outline" onClick={onClose}>Close</Button>
            <Button disabled={!dirty || saving} onClick={save}>
              {saving ? 'Saving…' : 'Save layout'}
            </Button>
          </div>
        </div>

        {/* The frame takes the room that is left and the tools take a fixed
            column, so the wireframe grows with the window instead of being
            sized by its own aspect ratio inside a box of unknown height. */}
        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 lg:flex-row">
          <div className="min-h-0 flex-1 overflow-y-auto rounded border border-line bg-white">
            <Frame page={{ blocks }} selected={picked}
              onPick={id => { setPicked(id); setShowTools(true) }}
              onBackground={() => setPicked('')} />
          </div>
          {showTools && (
          <div className="shrink-0 space-y-4 overflow-y-auto border-t border-line pt-4
                          lg:w-[340px] lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
            <Tools block={block} onChange={change} onRemove={remove} onAdd={add} />
            <div className="border-t border-line pt-3">
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[1px] text-muted2">
                Ask for what the tools cannot do
              </p>
              <Input value={ask} onChange={e => setAsk(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && request()}
                placeholder="e.g. split this into two steps, add a cancel confirmation"
                aria-label="Describe a change to this page"
                className="w-full rounded border border-line bg-panel2 px-2 py-1.5 text-[11.5px]" />
              <div className="mt-2 flex items-center justify-between gap-2">
                <p className="text-[10px] text-muted2">
                  Goes to the specification — this page only.
                </p>
                <Button disabled={!ask.trim() || asking} onClick={request}>
                  {asking ? 'Sending…' : 'Send'}
                </Button>
              </div>
            </div>
            {problem && <p role="alert" className="text-[11px] text-bad">{problem}</p>}
          </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

export function Wireframes({ srs }) {
  const owner = srs?.project || srs?.srs_id || srs?.id || ''
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')
  const [drawing, setDrawing] = useState(false)

  // The projection is instant and always there; this is the slow, good pass.
  // Minutes rather than milliseconds, and worth it: it is what puts real rows
  // and real values into the frames.
  async function redraw() {
    setDrawing(true); setError('')
    try {
      setData(await api.drawWireframes(owner))
    } catch (failure) {
      setError(failure?.message || 'The wireframes could not be redrawn.')
    } finally {
      setDrawing(false)
    }
  }

  const load = useCallback(() => {
    if (!owner) return
    api.wireframes(owner)
      .then(setData)
      .catch(failure => setError(failure?.message || 'The wireframes could not be read.'))
  }, [owner])

  useEffect(() => { load() }, [load])

  const pages = data?.pages || []
  if (error) return <Empty>{error}</Empty>
  if (!data) return <Empty>Reading the wireframes…</Empty>
  if (!pages.length) return <Empty>No pages in the specification yet, so there is nothing to lay out.</Empty>

  const drawn = pages.filter(p => p.drawn).length

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-[11.5px] text-muted">
          {pages.length} page{pages.length === 1 ? '' : 's'}, black and white, no navigation.
          Open one to move things, rename them, or ask for a change.
          {drawn ? ` ${drawn} drawn in full with sample data.`
                 : ' Laid out from the specification — redraw for detail and sample data.'}
        </p>
        <Button variant="outline" disabled={drawing} onClick={redraw}>
          {drawing ? 'Drawing…' : 'Redraw for detail'}
        </Button>
      </div>
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(230px,1fr))]">
        {pages.map(page => (
          <button key={page.route} type="button" onClick={() => setOpen(page)}
            className="group overflow-hidden rounded-xl border border-line text-left transition hover:border-accent">
            <span className="block aspect-[16/10] overflow-hidden border-b border-line bg-white">
              <Frame page={page} fit />
            </span>
            <span className="block space-y-1 p-3">
              <span className="flex items-baseline justify-between gap-2">
                <span className="truncate text-[12px] font-medium text-ink">{page.page_name}</span>
                {page.edited && <Badge tone="accent">edited</Badge>}
              </span>
              <span className="block truncate font-mono text-[10px] text-muted2">{page.route}</span>
              <span className="block truncate text-[10px] text-muted2">
                {page.roles?.length ? page.roles.join(', ') : 'public'} · {page.blocks.length} blocks
              </span>
            </span>
          </button>
        ))}
      </div>
      {open && (
        <PageEditor owner={owner} page={open} onClose={() => setOpen(null)}
          onSaved={answer => (answer ? setData(answer) : load())} />
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
