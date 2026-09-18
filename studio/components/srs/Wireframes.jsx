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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft, Check, GripVertical, Layers, Loader2, Move,
  Palette, Plus, RotateCcw, Save, Sparkles, Trash2, X,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Badge, Button, Empty, Input, Modal, TextArea } from '../ui'

// Every block is placed on a 0–100 grid, so one number works at thumbnail size
// and at full size alike.
const pc = n => `${n}%`

const KINDS = [
  'heading', 'title', 'text', 'field', 'button', 'table', 'cards',
  'list', 'image', 'icon', 'divider', 'rating', 'stat', 'panel',
  'tabs', 'chart', 'nav', 'footer',
]

const DEFAULT_SIZES = {
  nav: { w: 96, h: 8, label: 'Navigation Bar' },
  footer: { w: 96, h: 16, label: 'Page Footer' },
  heading: { w: 60, h: 8, label: 'Main Heading' },
  title: { w: 40, h: 6, label: 'Section Title' },
  text: { w: 50, h: 10, label: 'Paragraph text' },
  field: { w: 40, h: 6, label: 'Input Field' },
  button: { w: 24, h: 6, label: 'Button' },
  table: { w: 92, h: 28, label: 'Data Table' },
  cards: { w: 92, h: 24, label: 'Card Grid' },
  list: { w: 46, h: 26, label: 'Item List' },
  image: { w: 44, h: 24, label: 'Image Box' },
  icon: { w: 10, h: 8, label: 'Icon' },
  divider: { w: 92, h: 4, label: 'Divider' },
  rating: { w: 24, h: 5, label: 'Rating' },
  stat: { w: 28, h: 14, label: 'Stat Metric' },
  panel: { w: 44, h: 20, label: 'Panel' },
  tabs: { w: 60, h: 8, label: 'Tabs' },
  chart: { w: 48, h: 22, label: 'Chart' },
}

const CATEGORIES = [
  { name: 'Navigation & Layout', kinds: ['nav', 'footer', 'panel', 'tabs', 'divider'] },
  { name: 'Typography & Media', kinds: ['heading', 'title', 'text', 'image', 'icon'] },
  { name: 'Inputs & Actions', kinds: ['field', 'button'] },
  { name: 'Data & Analytics', kinds: ['table', 'cards', 'list', 'chart', 'stat', 'rating'] },
]


/** One block, drawn in line and grey only. Supports direct canvas drag & resize. */
function Block({
  block,
  scale = 1,
  canvas = 100,
  selected,
  onPick,
  isEditable = false,
  dragging = false,
  placingKind = null,
  onBlockMouseDown,
  onResizeMouseDown,
}) {
  const { kind, label, w, h } = block
  const line = 'border border-[#8a8a8a]'
  const px = scale / 100
  const small = h * px < 9
  const common0 = {
    position: 'absolute',
    left: pc(block.x),
    top: pc(100 * block.y / canvas),
    width: pc(w),
    height: pc(100 * h / canvas),
  }
  const size = Math.max(4, Math.min(13, Math.round(scale * 0.011)))
  const text = 'overflow-hidden leading-tight'
  const common = { width: '100%', height: '100%', fontSize: `${size}px` }

  const renderContent = () => {
    if (kind === 'title') {
      return (
        <div style={common} className={`flex items-center font-semibold text-[#111] ${text}`}>
          <span className="truncate">{label}</span>
        </div>
      )
    }
    if (kind === 'text') {
      const lines = Array.isArray(block.lines) ? block.lines : null
      if (lines && h * px > 16) {
        return (
          <div style={common} className={`flex flex-col justify-center overflow-hidden ${text}`}>
            {lines.slice(0, 4).map((l, i) => (
              <span key={i} className="truncate text-[#555]">{String(l)}</span>
            ))}
          </div>
        )
      }
      return (
        <div style={common} className="flex flex-col justify-center gap-[2px]">
          <span className="block h-[2px] w-full bg-[#c9c9c9]" />
          <span className="block h-[2px] w-4/5 bg-[#c9c9c9]" />
          <span className="block h-[2px] w-3/5 bg-[#c9c9c9]" />
        </div>
      )
    }
    if (kind === 'button') {
      return (
        <div style={common} className={`flex items-center justify-center bg-[#2b2b2b] text-white shadow-sm ${text}`}>
          {!small && <span className="truncate px-1 font-medium">{label}</span>}
        </div>
      )
    }
    if (kind === 'field') {
      return (
        <div style={common} className={`flex items-center gap-1 overflow-hidden bg-white ${line} ${text}`}>
          {!small && <span className="shrink-0 truncate px-1 text-[#999]">{label}</span>}
          {!small && block.value && <span className="truncate text-[#333]">{block.value}</span>}
        </div>
      )
    }
    if (kind === 'stat') {
      return (
        <div style={common} className={`flex flex-col justify-center gap-[3px] bg-white px-1 ${line} ${text}`}>
          {!small && <span className="truncate text-[#999]">{label}</span>}
          {block.value
            ? <span className="truncate font-semibold text-[#111]"
                    style={{ fontSize: `${Math.max(size, Math.min(Math.round(size * 1.9), Math.round(h * px * 0.5)))}px` }}>
                {block.value}
              </span>
            : <span className="block h-[5px] w-2/3 bg-[#2b2b2b]" />}
        </div>
      )
    }
    if (kind === 'chart') {
      return (
        <div style={common} className={`flex items-end gap-[3px] bg-white p-1 ${line}`}>
          {[40, 65, 30, 80, 55, 70, 45].map((v, i) => (
            <span key={i} className="flex-1 bg-[#c9c9c9]" style={{ height: `${v}%` }} />
          ))}
        </div>
      )
    }
    if (kind === 'table') {
      const columns = block.columns?.length ? block.columns : null
      const sample = Array.isArray(block.sample) ? block.sample : []
      const cols = columns?.length || sample[0]?.length || 4
      const fits = h * px > 26 && w * scale / 100 > 90
      const rows = fits && sample.length
        ? sample.slice(0, Math.max(1, Math.floor((h * px - size * 1.8) / (size * 2.2))))
        : Array.from({ length: Math.max(2, Math.min(block.rows || 5, Math.floor(h * px / 10))) })
      return (
        <div style={common} className={`flex flex-col bg-white ${line}`}>
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
      )
    }
    if (kind === 'cards' || kind === 'list') {
      const items = Array.isArray(block.items) ? block.items : null
      const n = items?.length || (kind === 'cards' ? 3 : 4)
      const room = h * px > 24
      return (
        <div style={common}>
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
      )
    }
    if (kind === 'image') {
      return (
        <div style={common}>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none"
            className="h-full w-full" aria-hidden="true">
            <rect x="0.6" y="0.6" width="98.8" height="98.8" fill="none"
              stroke="#2b2b2b" strokeWidth="0.9" vectorEffect="non-scaling-stroke" />
            <path d="M0.6 0.6 L99.4 99.4 M99.4 0.6 L0.6 99.4" fill="none"
              stroke="#2b2b2b" strokeWidth="0.9" vectorEffect="non-scaling-stroke" />
          </svg>
        </div>
      )
    }
    if (kind === 'icon') {
      return (
        <div style={common} className="flex items-center justify-center">
          <span className="flex aspect-square h-full items-center justify-center rounded-full
                           border border-[#2b2b2b] text-[#2b2b2b]">
            {!small && <span className="truncate px-1">{label || 'Icon'}</span>}
          </span>
        </div>
      )
    }
    if (kind === 'divider') {
      return (
        <div style={common} className="flex items-center justify-center relative">
          <span className="absolute left-0 right-0 top-1/2 h-px bg-[#2b2b2b]" />
          {label && <span className="relative truncate border border-[#2b2b2b] bg-white px-2 py-[1px]
                                     text-[#2b2b2b]">{label}</span>}
        </div>
      )
    }
    if (kind === 'rating') {
      return (
        <div style={common} className={`flex items-center gap-[2px] text-[#2b2b2b] ${text}`}>
          {'☆☆☆☆☆'.split('').map((s, i) => <span key={i}>{s}</span>)}
        </div>
      )
    }
    if (kind === 'nav') {
      const links = Array.isArray(block.items) ? block.items
        : String(block.label || 'Home, About, Services').split(/\s*,\s*/)
      return (
        <div style={common} className={`flex items-center justify-between gap-2 border-b border-[#2b2b2b] bg-white px-2 ${text}`}>
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
      )
    }
    if (kind === 'footer') {
      return (
        <div style={common} className={`flex items-start justify-between gap-4 border-t border-[#2b2b2b] bg-white px-2 pt-2 ${text}`}>
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
      )
    }
    if (kind === 'tabs') {
      const tabs = Array.isArray(block.items) ? block.items : ['Overview', 'Details', 'Settings']
      return (
        <div style={common} className={`flex items-center gap-2 border-b border-[#2b2b2b] bg-white px-2 ${text}`}>
          {tabs.map((t, i) => (
            <span key={i} className={`px-2 py-1 text-[11px] ${i === 0 ? 'border-b-2 border-black font-semibold text-black' : 'text-gray-500'}`}>
              {String(t.title || t)}
            </span>
          ))}
        </div>
      )
    }
    if (kind === 'heading') {
      return (
        <div style={common} className={`flex flex-col justify-center overflow-hidden font-bold leading-[1.12] text-[#111]`}>
          <span style={{ fontSize: `${Math.max(size, Math.round(h * px * 0.34))}px` }}>
            {label}
          </span>
        </div>
      )
    }
    return (
      <div style={common} className={`bg-white/40 ${line}`}>
        {!small && <span className={`block truncate px-1 pt-[2px] text-[#8a8a8a] ${text}`}>{label}</span>}
      </div>
    )
  }

  return (
    <div
      style={common0}
      onMouseDown={e => {
        if (placingKind) return
        if (isEditable) {
          onBlockMouseDown?.(e, block)
        } else if (onPick) {
          e.stopPropagation()
          onPick(block.id)
        }
      }}
      className={cn(
        'group absolute select-none transition-[box-shadow]',
        isEditable
          ? (placingKind ? 'cursor-crosshair' : (dragging ? 'cursor-grabbing z-30' : 'cursor-grab hover:z-20'))
          : (onPick ? 'cursor-pointer' : ''),
        selected && !placingKind ? 'outline outline-2 outline-[#1877F2] z-30 shadow-md ring-1 ring-blue-400/50' : 'hover:outline hover:outline-1 hover:outline-[#1877F2]/40'
      )}
    >
      {renderContent()}

      {selected && isEditable && !placingKind && (
        <>
          <div className="pointer-events-none absolute -top-5 left-0 z-40 flex items-center gap-1 rounded bg-[#1877F2] px-1.5 py-0.5 font-mono text-[9px] font-medium text-white shadow-md">
            <span>{kind}</span>
            <span className="opacity-75">({w}×{h})</span>
          </div>
          <div
            onMouseDown={e => {
              e.stopPropagation()
              onResizeMouseDown?.(e, block)
            }}
            title="Drag to resize"
            className="absolute -bottom-1.5 -right-1.5 z-40 size-3 rounded-sm bg-[#1877F2] ring-2 ring-white cursor-se-resize shadow-md hover:scale-125 transition-transform"
          />
        </>
      )}
    </div>
  )
}

/**
 * One page's frame. The same renderer for a thumbnail and for the editor.
 */
function Frame({
  page,
  selected,
  onPick,
  onBackground,
  fit,
  isEditable = false,
  draggingId = null,
  onBlockMouseDown = null,
  onResizeMouseDown = null,
  onDropKind = null,
  placingKind = null,
  onCanvasPlace = null,
}) {
  const [width, setWidth] = useState(0)
  const frameRef = useRef(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [ghostCoords, setGhostCoords] = useState(null)

  const box = useCallback(node => {
    frameRef.current = node
    if (!node) return
    setWidth(node.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const watch = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    watch.observe(node)
    return () => watch.disconnect()
  }, [])

  const blocks = page?.blocks || []
  const canvas = Math.max(100, page?.canvas || 0,
                          ...blocks.map(b => (b.y || 0) + (b.h || 0) + 4))
  const height = fit ? null : Math.round(width * canvas / 100)

  const handleDragOver = e => {
    if (!isEditable) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    if (!isDragOver) setIsDragOver(true)
  }

  const handleDragLeave = e => {
    if (!isEditable) return
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragOver(false)
    }
  }

  const handleDrop = e => {
    if (!isEditable) return
    e.preventDefault()
    setIsDragOver(false)
    if (!frameRef.current) return
    const rect = frameRef.current.getBoundingClientRect()
    onDropKind?.(e, rect, canvas)
  }

  // Live mouse hover for Figma-style placement ghost preview
  const handleMouseMove = e => {
    if (!isEditable || !placingKind || !frameRef.current) return
    const rect = frameRef.current.getBoundingClientRect()
    const pixelX = e.clientX - rect.left
    const pixelY = e.clientY - rect.top
    const scale = rect.width
    const gridX = (pixelX / scale) * 100
    const gridY = (pixelY / scale) * 100
    const def = DEFAULT_SIZES[placingKind] || { w: 40, h: 10 }
    const x = Math.max(0, Math.min(100 - def.w, Math.round(gridX - def.w / 2)))
    const y = Math.max(0, Math.round(gridY - def.h / 2))
    setGhostCoords({ x, y, w: def.w, h: def.h, kind: placingKind, label: def.label || placingKind })
  }

  const handleMouseLeave = () => {
    if (placingKind) setGhostCoords(null)
  }

  const handleCanvasMouseDown = e => {
    if (isEditable && placingKind && frameRef.current) {
      e.stopPropagation()
      e.preventDefault()
      const rect = frameRef.current.getBoundingClientRect()
      const pixelX = e.clientX - rect.left
      const pixelY = e.clientY - rect.top
      const scale = rect.width
      const gridX = (pixelX / scale) * 100
      const gridY = (pixelY / scale) * 100
      const def = DEFAULT_SIZES[placingKind] || { w: 40, h: 10 }
      const x = Math.max(0, Math.min(100 - def.w, Math.round(gridX - def.w / 2)))
      const y = Math.max(0, Math.round(gridY - def.h / 2))
      onCanvasPlace?.(placingKind, { x, y })
      setGhostCoords(null)
      return
    }
    onBackground?.(e)
  }

  return (
    <div
      ref={box}
      onMouseDown={handleCanvasMouseDown}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'relative w-full bg-white transition-all',
        fit ? 'h-full overflow-hidden' : '',
        isEditable && placingKind ? 'cursor-crosshair' : '',
        isEditable && isDragOver ? 'ring-2 ring-[#1877F2] ring-offset-2' : ''
      )}
      style={{ contain: 'paint', height: height ?? undefined }}
    >
      {isEditable && isDragOver && (
        <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-[#1877F2]/10 backdrop-blur-[1px]">
          <span className="rounded-xl border border-blue-500/40 bg-[#1877F2] px-4 py-2 text-xs font-semibold text-white shadow-xl">
            Drop component here
          </span>
        </div>
      )}

      {/* Figma-style Live Ghost Preview */}
      {isEditable && placingKind && ghostCoords && (
        <div
          style={{
            position: 'absolute',
            left: pc(ghostCoords.x),
            top: pc(100 * ghostCoords.y / canvas),
            width: pc(ghostCoords.w),
            height: pc(100 * ghostCoords.h / canvas),
            pointerEvents: 'none',
            zIndex: 50,
          }}
          className="rounded-lg border-2 border-dashed border-[#1877F2] bg-[#1877F2]/15 backdrop-blur-[1px] flex flex-col justify-between p-1.5 select-none shadow-2xl transition-[left,top] duration-75"
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1 rounded bg-[#1877F2] px-1.5 py-0.5 font-mono text-[9.5px] font-bold text-white shadow">
              <span>+</span>
              <span className="capitalize">{ghostCoords.kind}</span>
            </span>
            <span className="rounded bg-black/75 px-1.5 py-0.5 font-mono text-[9px] font-medium text-white shadow">
              X: {ghostCoords.x}% · Y: {ghostCoords.y}%
            </span>
          </div>
          <div className="text-center font-semibold text-[11px] text-[#1877F2] bg-white/90 py-0.5 rounded shadow-sm">
            Click to place here
          </div>
        </div>
      )}

      {width > 0 && blocks.map(block => (
        <Block
          key={block.id}
          block={block}
          scale={width}
          canvas={canvas}
          selected={selected === block.id}
          onPick={onPick}
          isEditable={isEditable}
          dragging={draggingId === block.id}
          placingKind={placingKind}
          onBlockMouseDown={(e, b) => onBlockMouseDown?.(e, b, frameRef.current?.getBoundingClientRect())}
          onResizeMouseDown={(e, b) => onResizeMouseDown?.(e, b, frameRef.current?.getBoundingClientRect())}
        />
      ))}
    </div>
  )
}


const STEP = 2

function Quick({ label, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className="rounded border border-line bg-panel2 px-2 py-1 text-[10.5px] text-muted hover:text-ink hover:bg-raised transition">
      {label}
    </button>
  )
}

function Pad({ label, onMove }) {
  const arrow = 'rounded border border-line px-2 py-1 text-[11px] text-muted hover:text-ink hover:bg-raised transition'
  return (
    <div>
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-[1px] text-muted2">{label}</p>
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

/**
 * 2-column full layout Wireframe Editor.
 * Replaces the Revisions aside on the left and the main subtabs viewer on the right.
 */
export function WireframeEditor({ owner, page, onClose, onSaved }) {
  // The full drawing lives with the specification agent, so it is offered only
  // where that agent is the owner. A project reading its mirrored copy has the
  // blocks and nothing to draw with.
  //
  // The switch belongs here rather than in a wrapper: `SrsReview` renders this
  // editor directly instead of going through `PageEditor`, so a wrapper is the
  // one place it would never be seen.
  const canDrawFull = /^prj_/.test(String(owner || ''))
  const [view, setView] = useState('layout')
  const [blocks, setBlocks] = useState(page.blocks || [])
  const [picked, setPicked] = useState('')
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState('')
  const [ask, setAsk] = useState('')
  const [asking, setAsking] = useState(false)
  const [draggingId, setDraggingId] = useState(null)
  const [resizingId, setResizingId] = useState(null)
  const [placingKind, setPlacingKind] = useState(null)

  const block = blocks.find(b => b.id === picked) || null
  const dirty = JSON.stringify(blocks) !== JSON.stringify(page.blocks || [])

  const changeBlock = useCallback(next => {
    setBlocks(list => list.map(b => (b.id === next.id ? next : b)))
  }, [])

  const addBlock = useCallback((kind, coords = null) => {
    const def = DEFAULT_SIZES[kind] || { w: 40, h: 10, label: kind }
    const id = `b${Date.now().toString(36)}`
    let x = 4
    let y = 40
    if (coords) {
      x = coords.x
      y = coords.y
    } else {
      const maxY = blocks.length ? Math.max(...blocks.map(b => (b.y || 0) + (b.h || 0))) : 10
      y = Math.min(maxY + 4, 180)
    }
    const newBlock = {
      id,
      kind,
      label: def.label || kind,
      x,
      y,
      w: def.w,
      h: def.h,
    }
    setBlocks(list => [...list, newBlock])
    setPicked(id)
  }, [blocks])

  const removeBlock = useCallback(() => {
    setBlocks(list => list.filter(b => b.id !== picked))
    setPicked('')
  }, [picked])

  // Mouse Drag-to-Move handler on canvas
  const handleBlockMouseDown = useCallback((e, b, frameRect) => {
    if (e.button !== 0) return
    e.stopPropagation()
    setPicked(b.id)
    setDraggingId(b.id)

    const startClientX = e.clientX
    const startClientY = e.clientY
    const origX = b.x
    const origY = b.y
    const widthPx = frameRect?.width || 800

    const handleMouseMove = moveEvent => {
      moveEvent.preventDefault()
      const deltaXPx = moveEvent.clientX - startClientX
      const deltaYPx = moveEvent.clientY - startClientY
      const deltaGridX = (deltaXPx / widthPx) * 100
      const deltaGridY = (deltaYPx / widthPx) * 100

      const newX = Math.max(0, Math.min(100 - b.w, Math.round(origX + deltaGridX)))
      const newY = Math.max(0, Math.round(origY + deltaGridY))

      setBlocks(prev => prev.map(item =>
        item.id === b.id ? { ...item, x: newX, y: newY } : item
      ))
    }

    const handleMouseUp = () => {
      setDraggingId(null)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }, [])

  // Mouse Drag-to-Resize handler on canvas
  const handleResizeMouseDown = useCallback((e, b, frameRect) => {
    if (e.button !== 0) return
    e.stopPropagation()
    e.preventDefault()
    setResizingId(b.id)

    const startClientX = e.clientX
    const startClientY = e.clientY
    const origW = b.w
    const origH = b.h
    const widthPx = frameRect?.width || 800

    const handleMouseMove = moveEvent => {
      moveEvent.preventDefault()
      const deltaXPx = moveEvent.clientX - startClientX
      const deltaYPx = moveEvent.clientY - startClientY
      const deltaGridW = (deltaXPx / widthPx) * 100
      const deltaGridH = (deltaYPx / widthPx) * 100

      const newW = Math.max(4, Math.min(100 - b.x, Math.round(origW + deltaGridW)))
      const newH = Math.max(3, Math.round(origH + deltaGridH))

      setBlocks(prev => prev.map(item =>
        item.id === b.id ? { ...item, w: newW, h: newH } : item
      ))
    }

    const handleMouseUp = () => {
      setResizingId(null)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }, [])

  // Drop component from palette directly onto canvas
  const handleDropKind = useCallback((e, frameRect, canvasHeight) => {
    e.preventDefault()
    const kind = e.dataTransfer.getData('text/plain')
    if (!kind || !KINDS.includes(kind)) return

    const pixelX = e.clientX - frameRect.left
    const pixelY = e.clientY - frameRect.top
    const widthPx = frameRect.width

    const dropGridX = (pixelX / widthPx) * 100
    const dropGridY = (pixelY / widthPx) * 100

    const def = DEFAULT_SIZES[kind] || { w: 40, h: 10 }
    const x = Math.max(0, Math.min(100 - def.w, Math.round(dropGridX - def.w / 2)))
    const y = Math.max(0, Math.round(dropGridY - def.h / 2))

    addBlock(kind, { x, y })
  }, [addBlock])

  const handleCanvasPlace = useCallback((kind, coords) => {
    addBlock(kind, coords)
    setPlacingKind(null)
  }, [addBlock])

  // Keyboard navigation & deletion
  useEffect(() => {
    const handleKeyDown = e => {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if (e.key === 'Escape') {
        if (placingKind) {
          setPlacingKind(null)
        } else {
          setPicked('')
        }
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && picked) {
        removeBlock()
      } else if (picked && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault()
        const dx = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0
        const dy = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0
        setBlocks(list => list.map(b => {
          if (b.id !== picked) return b
          return {
            ...b,
            x: Math.max(0, Math.min(100 - b.w, b.x + dx * STEP)),
            y: Math.max(0, b.y + dy * STEP),
          }
        }))
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [picked, removeBlock, placingKind])

  async function save() {
    setSaving(true)
    setProblem('')
    try {
      const answer = await api.editWireframe(owner, page.route, blocks)
      onSaved?.(answer)
    } catch (failure) {
      setProblem(failure?.message || 'That layout could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function request() {
    const text = ask.trim()
    if (!text) return
    setAsking(true)
    setProblem('')
    try {
      await api.srs(`/projects/${owner}/changes`, {
        change_id: `wireframe-${Date.now().toString(36)}`,
        source: 'design-customizer',
        summary: `For the ${page.page_name} page (${page.route}): ${text}`,
      })
      setAsk('')
      onSaved?.(null)
    } catch (failure) {
      setProblem(failure?.message || 'That request could not be sent.')
    } finally {
      setAsking(false)
    }
  }

  return (
    <>
      {/* Left Column: Edit Tools (Replaces the Revisions Sidebar).
          Hidden on the full drawing, which has nothing the tools can move. */}
      <aside className={cn('flex w-[290px] shrink-0 flex-col overflow-hidden rounded-2xl',
        'border border-line bg-panel shadow-xl backdrop-blur-xl',
        view === 'full' && canDrawFull && 'hidden')}>
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <Palette className="size-3.5 text-accent" />
          <span className="font-display text-[12px] font-bold uppercase tracking-wider text-ink">
            Wireframe Tools
          </span>
          <span className="flex-1" />
          <span className="rounded-full bg-panel2 px-2 py-0.5 font-mono text-[10px] text-muted">
            {blocks.length}
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3 space-y-4">
          {/* Selected Component Inspector */}
          {block ? (
            <div className="rounded-xl border border-blue-500/30 bg-blue-500/[.06] p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-semibold uppercase text-blue-400">
                  {block.kind}
                </span>
                <button
                  type="button"
                  onClick={removeBlock}
                  className="flex items-center gap-1 text-[11px] text-bad hover:underline cursor-pointer"
                >
                  <Trash2 className="size-3" /> Remove
                </button>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <label className="text-[10px] text-muted2 w-10 shrink-0">Type</label>
                  <select
                    value={block.kind}
                    onChange={e => changeBlock({ ...block, kind: e.target.value })}
                    className="min-w-0 flex-1 rounded-lg border border-line bg-panel2 px-2 py-1 text-[11px] text-ink outline-none"
                  >
                    {KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-[10px] text-muted2 w-10 shrink-0">Label</label>
                  <Input
                    value={block.label || ''}
                    onChange={e => changeBlock({ ...block, label: e.target.value })}
                    placeholder="Block label"
                    className="min-w-0 flex-1 rounded-lg border border-line bg-panel2 px-2 py-1 text-[11px]"
                  />
                </div>

                {['stat', 'field', 'nav', 'footer'].includes(block.kind) && (
                  <div className="flex items-center gap-2">
                    <label className="text-[10px] text-muted2 w-10 shrink-0">Value</label>
                    <Input
                      value={block.value || ''}
                      onChange={e => changeBlock({ ...block, value: e.target.value })}
                      placeholder="Value or logo text"
                      className="min-w-0 flex-1 rounded-lg border border-line bg-panel2 px-2 py-1 text-[11px]"
                    />
                  </div>
                )}
              </div>

              {/* Quick Alignments */}
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted2">Alignment</p>
                <div className="flex flex-wrap gap-1">
                  <Quick label="Full Width" onClick={() => changeBlock({ ...block, x: 4, w: 92 })} />
                  <Quick label="Center" onClick={() => changeBlock({ ...block, x: Math.max(0, Math.round((100 - block.w) / 2)) })} />
                  <Quick label="Left 50%" onClick={() => changeBlock({ ...block, x: 4, w: 44 })} />
                  <Quick label="Right 50%" onClick={() => changeBlock({ ...block, x: 52, w: 44 })} />
                  <Quick label="To Top" onClick={() => changeBlock({ ...block, y: 4 })} />
                </div>
              </div>

              {/* Nudge Pads */}
              <div className="grid grid-cols-2 gap-2 pt-1">
                <Pad label="Position" onMove={(dx, dy) => {
                  changeBlock({
                    ...block,
                    x: Math.max(0, Math.min(100 - block.w, block.x + dx * STEP)),
                    y: Math.max(0, block.y + dy * STEP),
                  })
                }} />
                <Pad label="Size" onMove={(dx, dy) => {
                  changeBlock({
                    ...block,
                    w: Math.max(4, Math.min(100 - block.x, block.w + dx * STEP)),
                    h: Math.max(3, block.h + dy * STEP),
                  })
                }} />
              </div>

              <div className="flex items-center justify-between border-t border-line/60 pt-2 font-mono text-[9.5px] text-muted2">
                <span>X: {block.x}% · Y: {block.y}%</span>
                <span>W: {block.w}% · H: {block.h}%</span>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-line/80 bg-panel2/30 p-3 text-center">
              <p className="text-[11px] text-muted">
                Click any block to edit its properties, or drag components from below onto the canvas.
              </p>
            </div>
          )}

          {/* Component Palette */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wider text-ink">
                Add Components
              </p>
              <span className="text-[9.5px] text-muted2">Click or drag</span>
            </div>

            {CATEGORIES.map(cat => (
              <div key={cat.name} className="space-y-1.5">
                <p className="text-[9.5px] font-semibold uppercase tracking-wider text-muted2">
                  {cat.name}
                </p>
                <div className="grid grid-cols-2 gap-1.5">
                  {cat.kinds.map(kind => {
                    const isPlacing = placingKind === kind
                    return (
                      <div
                        key={kind}
                        draggable
                        onDragStart={e => {
                          e.dataTransfer.setData('text/plain', kind)
                          e.dataTransfer.effectAllowed = 'copy'
                        }}
                        onClick={() => {
                          if (isPlacing) {
                            setPlacingKind(null)
                          } else {
                            setPlacingKind(kind)
                            setPicked('')
                          }
                        }}
                        className={cn(
                          'group flex cursor-pointer items-center justify-between rounded-lg border px-2 py-1.5 text-[11px] transition select-none',
                          isPlacing
                            ? 'border-blue-500 bg-blue-500/25 text-white ring-2 ring-blue-500/60 shadow-[0_0_12px_rgba(24,119,242,0.35)]'
                            : 'border-line bg-panel2/60 text-ink hover:border-accent hover:bg-raised active:cursor-grabbing'
                        )}
                        title={isPlacing ? 'Click canvas to place, or click here to cancel' : `Click to place ${kind} on canvas (Figma style), or drag`}
                      >
                        <div className="flex min-w-0 items-center gap-1.5">
                          <GripVertical className={cn('size-3 shrink-0', isPlacing ? 'text-blue-400' : 'text-muted2 group-hover:text-accent')} />
                          <span className="truncate capitalize font-medium">{kind}</span>
                        </div>
                        {isPlacing ? (
                          <span className="size-2 rounded-full bg-blue-400 animate-ping shrink-0" />
                        ) : (
                          <button
                            type="button"
                            onClick={e => {
                              e.stopPropagation()
                              addBlock(kind)
                            }}
                            title={`Add ${kind} at bottom`}
                            className="rounded p-0.5 text-muted hover:text-ink hover:bg-white/10 shrink-0"
                          >
                            <Plus className="size-3" />
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom AI Change Assistant */}
        <div className="border-t border-line bg-black/20 p-3">
          <p className="mb-1.5 flex items-center gap-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted2">
            <Sparkles className="size-3 text-accent" />
            <span>Ask for complex changes</span>
          </p>
          <TextArea
            value={ask}
            rows={2}
            disabled={asking}
            onChange={e => setAsk(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) request()
            }}
            placeholder="e.g. split into two steps, add a cancel confirmation…"
            className="w-full resize-none rounded-xl border border-white/10 bg-white/[.04] p-2 text-[11.5px] text-white outline-none focus:border-blue-500/50 placeholder:text-white/40 caret-blue-400"
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-[9.5px] text-muted2">Goes to SRS spec</span>
            <Button
              variant="solid"
              size="sm"
              className="h-7 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[11px]"
              disabled={!ask.trim() || asking}
              onClick={request}
            >
              {asking ? <Loader2 className="size-3 animate-spin" /> : 'Send'}
            </Button>
          </div>
          {problem && <p role="alert" className="mt-2 text-[11px] text-bad">{problem}</p>}
        </div>
      </aside>

      {/* Right Column: Wireframe Canvas Viewport (Replaces Main Viewer) */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#121622]/90 shadow-2xl backdrop-blur-xl">
        {/* Top Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-white/10 px-5 py-3 bg-black/30 backdrop-blur-md">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/80 hover:bg-white/[.1] hover:text-white text-[11.5px]"
            >
              <ArrowLeft className="size-3.5 mr-1" />
              Wireframes
            </Button>
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-white flex items-center gap-2">
                <span>{page.page_name}</span>
                {dirty && (
                  <span className="rounded-full bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] text-amber-300 border border-amber-500/30">
                    Unsaved
                  </span>
                )}
              </h3>
              <p className="font-mono text-[11px] text-white/50 truncate">
                {page.route} · {page.roles?.length ? page.roles.join(', ') : 'public'}
                {page.edited && ' · edited by hand'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {dirty && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setBlocks(page.blocks || [])
                  setPicked('')
                }}
                className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/70 hover:bg-white/[.1] hover:text-white text-[11.5px]"
              >
                <RotateCcw className="size-3 mr-1" /> Reset
              </Button>
            )}
            {canDrawFull && (
              <div className="mr-1 flex items-center rounded-xl border border-white/10 bg-white/[.05] p-0.5">
                {[['layout', 'Layout'], ['full', 'Full page']].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setView(key)}
                    aria-pressed={view === key}
                    className={cn('rounded-[10px] px-2.5 py-1 text-[11.5px] font-medium transition',
                      view === key ? 'bg-white/15 text-white' : 'text-white/60 hover:text-white')}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/80 hover:bg-white/[.1] hover:text-white text-[11.5px]"
            >
              Close
            </Button>
            <Button
              variant="solid"
              size="sm"
              disabled={!dirty || saving}
              onClick={save}
              className="h-8 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-[11.5px] shadow-sm disabled:opacity-50"
            >
              {saving ? (
                <><Loader2 className="size-3 animate-spin mr-1" /> Saving…</>
              ) : (
                <><Save className="size-3 mr-1" /> Save layout</>
              )}
            </Button>
          </div>
        </div>

        {view === 'full' && canDrawFull ? (
          <div className="flex min-h-0 flex-1 flex-col bg-[#0a0d14] p-5">
            <FullPage owner={owner} page={page} />
          </div>
        ) : (
        /* Scrollable Canvas Viewport */
        <div
          className="flex w-full min-h-0 flex-1 flex-col items-center overflow-y-auto bg-[#0a0d14] p-6 overscroll-contain"
          onMouseDown={() => setPicked('')}
        >
          {/* Active Placement Hint Banner */}
          {placingKind && (
            <div className="sticky top-0 z-50 mb-3 flex w-full max-w-[960px] shrink-0 items-center justify-between rounded-xl border border-blue-500/40 bg-blue-600 px-4 py-2 text-white shadow-xl shadow-blue-500/20 backdrop-blur-md">
              <div className="flex items-center gap-2 text-xs font-semibold">
                <span className="flex size-2 rounded-full bg-white animate-ping" />
                <span>Placement Mode: Click anywhere on canvas to place <strong className="underline underline-offset-2 capitalize">{placingKind}</strong></span>
              </div>
              <button
                type="button"
                onClick={() => setPlacingKind(null)}
                className="rounded-lg bg-black/25 px-2.5 py-1 text-[11px] font-medium text-white/90 hover:bg-black/40 hover:text-white transition cursor-pointer"
              >
                Press <kbd className="font-mono bg-white/20 px-1.5 py-0.5 rounded text-[10px] font-bold">Esc</kbd> to cancel
              </button>
            </div>
          )}

          <div
            className="w-full max-w-[960px] shrink-0 mb-12 overflow-hidden rounded-xl border border-white/15 bg-white shadow-2xl transition-all"
            onClick={e => e.stopPropagation()}
          >
            {/* Browser Frame Mockup Chrome */}
            <div className="flex select-none items-center justify-between border-b border-[#e5e5e5] bg-[#f5f5f5] px-4 py-2">
              <div className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full bg-[#ff5f56]" />
                <span className="size-2.5 rounded-full bg-[#ffbd2e]" />
                <span className="size-2.5 rounded-full bg-[#27c93f]" />
              </div>
              <div className="mx-auto flex w-1/2 max-w-sm items-center justify-center rounded-md border border-[#e0e0e0] bg-white px-2 py-0.5 font-mono text-[11px] text-[#666]">
                {page.route}
              </div>
              <div className="font-mono text-[10.5px] text-[#999]">
                {blocks.length} blocks
              </div>
            </div>

            {/* Interactive Frame with Drag & Drop */}
            <Frame
              page={{ ...page, blocks }}
              selected={picked}
              onPick={setPicked}
              onBackground={() => setPicked('')}
              isEditable={true}
              draggingId={draggingId}
              onBlockMouseDown={handleBlockMouseDown}
              onResizeMouseDown={handleResizeMouseDown}
              onDropKind={handleDropKind}
              placingKind={placingKind}
              onCanvasPlace={handleCanvasPlace}
            />
          </div>
        </div>
        )}
      </div>
    </>
  )
}

/** Fallback modal editor when used in isolation. */
/* The full drawing of one page: a finished HTML screen in a frame.
 *
 * Read-only on purpose. The blocks are what the tools move, and there is no
 * way to drag a box in generated HTML - so this view offers the one thing it
 * can honestly offer, which is to draw the page again. */
function FullPage({ owner, page }) {
  const [drawing, setDrawing] = useState(false)
  const [problem, setProblem] = useState('')
  const [stamp, setStamp] = useState(page.has_html ? 1 : 0)
  // Cleared by a successful redraw rather than re-read, so the notice goes
  // away when the thing it is about is fixed.
  const [stale, setStale] = useState(Boolean(page.html_stale))

  async function draw() {
    setDrawing(true); setProblem('')
    try {
      await api.drawWireframeHtml(owner, page.route)
      setStamp(n => n + 1)
      setStale(false)
    } catch (failure) {
      setProblem(failure?.message || 'The page could not be drawn.')
    } finally {
      setDrawing(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11.5px] text-muted">
          {stamp
            ? 'The page drawn in full, from the specification. Read only — use Layout to move things.'
            : 'This page has not been drawn in full yet.'}
        </p>
        <Button onClick={draw} disabled={drawing}>
          {drawing ? 'Drawing…' : stamp ? 'Draw again' : 'Draw this page'}
        </Button>
      </div>
      {stale && stamp ? (
        <p className="rounded-md border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11.5px] text-amber-200">
          The specification has changed since this page was drawn. What is shown
          below is the older version — draw it again to bring it up to date.
        </p>
      ) : null}
      {problem ? <p className="text-[11.5px] text-rose-300">{problem}</p> : null}
      {stamp ? (
        <iframe
          key={stamp}
          title={`${page.page_name || page.route} wireframe`}
          src={api.wireframeHtmlUrl(owner, page.route)}
          className="min-h-0 flex-1 w-full rounded-lg border border-white/10 bg-white"
        />
      ) : (
        <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border border-dashed border-white/10 text-[12px] text-muted">
          Nothing drawn for {page.route} yet.
        </div>
      )}
    </div>
  )
}

function PageEditor({ owner, page, onClose, onSaved }) {
  // The Layout / Full page switch lives in `WireframeEditor` itself, because
  // `SrsReview` renders that editor directly and would never see one put here.
  return (
    <Modal
      onClose={onClose}
      overlayClassName="!p-0 backdrop-blur-none"
      style={{ maxWidth: 'none', width: '100%', height: '100%', maxHeight: '100%' }}
      className="overflow-hidden rounded-none border-0 p-0"
    >
      <div className="flex h-full min-h-0 gap-4 p-5 bg-[#0a0d14]">
        <WireframeEditor
          owner={owner}
          page={page}
          onClose={onClose}
          onSaved={onSaved}
        />
      </div>
    </Modal>
  )
}

export function Wireframes({ srs, onEditPage }) {
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
          <button key={page.route} type="button"
            onClick={() => (onEditPage ? onEditPage(page) : setOpen(page))}
            className="group overflow-hidden rounded-xl border border-line text-left transition hover:border-accent cursor-pointer">
            <span className="block aspect-[16/10] overflow-hidden border-b border-line bg-white">
              <Frame page={page} fit />
            </span>
            <span className="block space-y-1 p-3">
              <span className="flex items-baseline justify-between gap-2">
                <span className="truncate text-[12px] font-medium text-ink">{page.page_name}</span>
                {page.html_stale
                  ? <Badge tone="warn">redraw</Badge>
                  : page.edited ? <Badge tone="accent">edited</Badge> : null}
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
          onSaved={answer => {
            if (answer) setData(answer)
            else load()
            setOpen(null)
          }} />
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
