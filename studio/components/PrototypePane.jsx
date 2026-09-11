'use client'

/**
 * HTML Prototype Viewer with Element Selection and Pencil Annotation tools.
 *
 * Just like in the Preview pane, clicking an element or drawing with the red pen
 * on the prototype attaches it to the chat composer with a photographed screenshot.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Monitor, Tablet, Smartphone, MousePointerClick, Pencil, RotateCw,
  ExternalLink, Globe, Layers, Eraser, Undo2, ChevronLeft, ChevronRight,
  Sparkles, Rocket, FlaskConical, Loader2,
} from 'lucide-react'
import { useStore } from '@/lib/store'
import { api, API } from '@/lib/api'
import { attachPicker, pickedFrom, pickLabel } from '@/lib/picker'
import { Tip } from './ui'
import { cn } from '@/lib/utils'

const VIEWPORTS = [
  { id: 'desktop', label: 'Desktop', w: null, Icon: Monitor },
  { id: 'tablet', label: 'Tablet', w: 834, Icon: Tablet },
  { id: 'mobile', label: 'Mobile', w: 390, Icon: Smartphone },
]

const MIN_INK = 3
let seq = 0

function currentPath(frame) {
  try {
    const loc = frame?.contentWindow?.location
    if (!loc) return 'index.html'
    const name = (loc.pathname || '').split('/').filter(Boolean).pop()
    return name && name.endsWith('.html') ? name : 'index.html'
  } catch {
    return 'index.html'
  }
}

export default function PrototypePane({ project, hidden, onBuild }) {
  const frameRef = useRef(null)
  const canvasRef = useRef(null)
  const detachRef = useRef(null)
  const strokesRef = useRef([])
  const drawingRef = useRef(false)
  const lastFileRef = useRef('index.html')

  const [vp, setVp] = useState('desktop')
  const [pickOn, setPickOn] = useState(false)
  const [pencilOn, setPencilOn] = useState(false)
  const [currentFile, setCurrentFile] = useState('index.html')
  const [protoReady, setProtoReady] = useState(false)
  const [iframeLoading, setIframeLoading] = useState(true)

  const trail = useRef(['index.html'])
  const at = useRef(0)
  const jumping = useRef(false)
  const [nav, setNav] = useState({ back: false, forward: false })

  const addLog = useStore(s => s.addLog)
  const busy = useStore(s => s.busy)
  const busyProject = useStore(s => s.busyProject)
  const progress = useStore(s => s.progress)
  const statusText = useStore(s => s.statusText)
  const isBusy = busy && (!busyProject || busyProject === project)
  const drawing = useStore(s => s.drawing)
  const setDrawing = useStore(s => s.setDrawing)
  const selection = useStore(s => s.selection)
  const addSelection = useStore(s => s.addSelection)
  const patchSelection = useStore(s => s.patchSelection)
  const clearSelection = useStore(s => s.clearSelection)
  const undo = useStore(s => s.undo)
  const setUndo = useStore(s => s.setUndo)

  const prototypeUrl = `${API}/prototype/${encodeURIComponent(project || '')}/${currentFile}`
  const width = VIEWPORTS.find(x => x.id === vp)?.w

  const checkPrototypeReady = useCallback(async () => {
    if (!project) return false
    try {
      const url = `${API}/prototype/${encodeURIComponent(project)}/${currentFile || 'index.html'}?check=${Date.now()}`
      const res = await fetch(url)
      if (res.ok) {
        const text = await res.text()
        if (text.includes('Generating HTML Prototype') || text.includes('no index.html in this drawing')) {
          setProtoReady(false)
          return false
        }
        setProtoReady(true)
        setIframeLoading(false)
        return true
      }
      setProtoReady(false)
      return false
    } catch {
      setProtoReady(false)
      return false
    }
  }, [project, currentFile])

  useEffect(() => {
    let active = true
    checkPrototypeReady()

    const interval = setInterval(async () => {
      if (!active) return
      const ready = await checkPrototypeReady()
      if (ready && frameRef.current) {
        if (!frameRef.current.dataset.loaded) {
          frameRef.current.dataset.loaded = 'true'
          const page = currentPath(frameRef.current)
          frameRef.current.src = `${API}/prototype/${encodeURIComponent(project)}/${page}?t=${Date.now()}`
        }
      }
    }, isBusy ? 1500 : 2500)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [project, isBusy, checkPrototypeReady])

  const syncPath = useCallback(() => {
    const here = currentPath(frameRef.current)
    if (!here) return
    if (lastFileRef.current === here) return
    lastFileRef.current = here
    setCurrentFile(here)

    if (jumping.current) {
      jumping.current = false
    } else if (trail.current[at.current] !== here) {
      trail.current = trail.current.slice(0, at.current + 1).concat(here)
      at.current = trail.current.length - 1
    }
    setNav({ back: at.current > 0, forward: at.current < trail.current.length - 1 })
  }, [])

  function step(by) {
    const f = frameRef.current
    const next = at.current + by
    if (!f || next < 0 || next >= trail.current.length) return
    at.current = next
    jumping.current = true
    const targetFile = trail.current[next]
    lastFileRef.current = targetFile
    setCurrentFile(targetFile)
    f.src = `${API}/prototype/${encodeURIComponent(project || '')}/${targetFile}`
    setNav({ back: next > 0, forward: next < trail.current.length - 1 })
  }

  function reload() {
    const f = frameRef.current
    if (f) {
      const page = currentPath(f)
      setIframeLoading(true)
      checkPrototypeReady()
      f.src = `${API}/prototype/${encodeURIComponent(project || '')}/${page}?t=${Date.now()}`
    }
  }

  const prevBusyRef = useRef(busy)
  useEffect(() => {
    if (prevBusyRef.current && !busy) {
      checkPrototypeReady()
      reload()
    }
    prevBusyRef.current = busy
  }, [busy])

  const viewportOf = useCallback(() => {
    const f = frameRef.current
    return { w: f?.clientWidth || 1280, h: f?.clientHeight || 800, mode: vp }
  }, [vp])

  const attachShot = useCallback(async (item, body) => {
    addSelection(item)
    try {
      const r = await api.shot({ ...body, project })
      patchSelection(item.key, r?.image
        ? { shot: r.image, state: 'ready' }
        : { state: 'blank' })
    } catch (e) {
      patchSelection(item.key, { state: 'blank' })
      addLog('WARN', `could not photograph prototype — ${e.message}`)
    }
  }, [addSelection, patchSelection, addLog, project])

  const attach = useCallback(() => {
    detachRef.current?.()
    if (!frameRef.current) return
    detachRef.current = attachPicker(frameRef.current, (el) => {
      const info = pickedFrom(frameRef.current, el, vp)
      const pageFile = currentPath(frameRef.current)
      const shotRoute = `/api/prototype/${encodeURIComponent(project)}/${pageFile}`
      attachShot(
        {
          key: `sel-${++seq}`,
          kind: 'element',
          info,
          state: 'shooting',
          label: pickLabel(info),
          route: shotRoute,
        },
        {
          route: shotRoute,
          viewport: info.viewport || viewportOf(),
          scroll: info.scroll,
          rect: info.rect,
        }
      )
    })
    if (!detachRef.current) addLog('WARN', 'The prototype is not loaded yet')
  }, [vp, addLog, attachShot, viewportOf, project])

  useEffect(() => {
    if (pickOn) attach()
    else { detachRef.current?.(); detachRef.current = null }
    return () => { detachRef.current?.(); detachRef.current = null }
  }, [pickOn, attach])

  useEffect(() => {
    const f = frameRef.current
    if (!f) return
    const onLoad = () => {
      syncPath()
      if (pickOn) attach()
    }
    f.addEventListener('load', onLoad)
    return () => f.removeEventListener('load', onLoad)
  }, [pickOn, attach, syncPath])

  useEffect(() => {
    const id = setInterval(syncPath, 500)
    return () => clearInterval(id)
  }, [syncPath])

  const syncCanvas = useCallback(() => {
    const f = frameRef.current, c = canvasRef.current
    if (!f || !c) return
    c.style.left = f.offsetLeft + 'px'
    c.style.top = f.offsetTop + 'px'
    c.style.width = f.clientWidth + 'px'
    c.style.height = f.clientHeight + 'px'
    const dpr = window.devicePixelRatio || 1
    const want = Math.round(f.clientWidth * dpr)
    if (c.width !== want) {
      c.width = want
      c.height = Math.round(f.clientHeight * dpr)
      const ctx = c.getContext('2d')
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.strokeStyle = '#ff2d55'
      ctx.lineWidth = 3
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
    }
  }, [])

  const clearStrokes = useCallback(() => {
    strokesRef.current = []
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, c.width, c.height); ctx.restore()
  }, [])

  const point = useCallback((e) => {
    const c = canvasRef.current
    const r = c.getBoundingClientRect()
    let sx = 0, sy = 0
    try {
      const w = frameRef.current.contentWindow
      sx = w.scrollX; sy = w.scrollY
    } catch { }
    return {
      cx: e.clientX - r.left, cy: e.clientY - r.top,
      x: Math.round(e.clientX - r.left + sx),
      y: Math.round(e.clientY - r.top + sy),
    }
  }, [])

  useEffect(() => {
    const c = canvasRef.current
    if (!c || !pencilOn) return
    syncCanvas()

    const down = (e) => {
      drawingRef.current = true
      const pt = point(e)
      strokesRef.current.push([{ x: pt.x, y: pt.y }])
      const ctx = c.getContext('2d')
      ctx.beginPath(); ctx.moveTo(pt.cx, pt.cy)
    }
    const move = (e) => {
      if (!drawingRef.current) return
      const pt = point(e)
      strokesRef.current[strokesRef.current.length - 1].push({ x: pt.x, y: pt.y })
      const ctx = c.getContext('2d')
      ctx.lineTo(pt.cx, pt.cy); ctx.stroke()
    }
    const up = () => {
      if (!drawingRef.current) return
      drawingRef.current = false
      const strokes = strokesRef.current
      if (strokes.reduce((a, s) => a + s.length, 0) < MIN_INK) return clearStrokes()
      const pageFile = currentPath(frameRef.current)
      const shotRoute = `/api/prototype/${encodeURIComponent(project)}/${pageFile}`
      attachShot(
        {
          key: `sel-${++seq}`,
          kind: 'drawing',
          strokes,
          route: shotRoute,
          state: 'shooting',
          label: `Drawing on ${pageFile}`,
        },
        { route: shotRoute, viewport: viewportOf(), strokes }
      )
      clearStrokes()
    }

    c.addEventListener('pointerdown', down)
    c.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    const onResize = () => syncCanvas()
    window.addEventListener('resize', onResize)
    return () => {
      c.removeEventListener('pointerdown', down)
      c.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('resize', onResize)
    }
  }, [pencilOn, point, syncCanvas, clearStrokes, attachShot, viewportOf, project])

  function togglePick() {
    if (!project) return addLog('WARN', 'Open a project first')
    if (!pickOn) setPencilOn(false)
    setPickOn(v => !v)
  }

  function togglePencil() {
    if (!project) return addLog('WARN', 'Open a project first')
    if (!pencilOn) setPickOn(false)
    setPencilOn(v => { if (v) clearStrokes(); return !v })
  }

  async function undoLast() {
    if (!project || !undo) return
    try {
      const r = await api.undo(project, undo.id || '')
      addLog('SUCCESS', 'Restored ' + (r.restored || []).join(', '))
      setUndo(null)
      reload()
    } catch (e) {
      addLog('WARN', 'Undo failed: ' + e.message)
    }
  }

  async function handleBuildAppNow() {
    if (isBusy) return
    const id = drawing?.id
    if (id) {
      setDrawing(null)
      try {
        await api.decide({ id, decision: 'approve' })
        addLog('INFO', `Starting full application build for ${project} from approved prototype…`)
      } catch (e) {
        addLog('WARN', `Could not accept prototype — ${e.message}`)
        if (onBuild) onBuild()
      }
    } else if (onBuild) {
      onBuild()
    }
  }

  // Reload when project changes or when drawing becomes active
  useEffect(() => {
    if (frameRef.current && project) {
      const firstPage = drawing?.pages?.[0]?.file || 'index.html'
      setCurrentFile(firstPage)
      lastFileRef.current = firstPage
      frameRef.current.src = `${API}/prototype/${encodeURIComponent(project)}/${firstPage}`
    }
  }, [project, drawing?.id])

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col bg-transparent', hidden && 'hidden')}>
      {/* Top Navbar */}
      <div className="flex h-[54px] shrink-0 items-center gap-3 border-b border-line/70 bg-white/72 px-4 backdrop-blur-2xl dark:bg-white/[.03]">
        {/* Navigation buttons */}
        <div className="flex items-center gap-1 rounded-full border border-line/80 bg-panel/90 p-1 shadow-sm">
          <Cell tip={nav.back ? 'Back' : 'Nothing to go back to'}
                disabled={!nav.back} onClick={() => step(-1)} className="rounded-full px-3">
            <ChevronLeft className="size-3.5" />
          </Cell>
          <Cell tip={nav.forward ? 'Forward' : 'Nothing to go forward to'}
                disabled={!nav.forward} onClick={() => step(1)} className="rounded-full px-3">
            <ChevronRight className="size-3.5" />
          </Cell>
          <Cell tip="Reload prototype" onClick={reload} className="rounded-full px-3">
            <RotateCw className="size-3.5" />
          </Cell>
        </div>

        {/* Prototype tag & current file */}
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-[14px] bg-black/[.035] px-4 py-2 text-[12px] text-muted ring-1 ring-black/[.045] dark:bg-white/[.045] dark:ring-white/[.06]">
          <Layers className="size-3.5 shrink-0 text-purple-500" />
          <span className="truncate font-mono text-[11.5px] text-ink font-medium">
            {project} / {currentFile}
          </span>
        </div>

        {/* Action: Build app from prototype */}
        {(onBuild || drawing?.id) && (
          <button
            onClick={handleBuildAppNow}
            disabled={isBusy}
            title="Build full application from this prototype"
            className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3.5 py-1.5 text-[11.5px] font-semibold text-white shadow-md shadow-blue-500/20 transition-all hover:bg-blue-500 active:scale-95 disabled:pointer-events-none disabled:opacity-50"
          >
            <Rocket className="size-3" /> {isBusy ? 'Building…' : 'Build App Now'}
          </button>
        )}

        <a
          href={prototypeUrl}
          target="_blank"
          rel="noreferrer"
          title="Open prototype in full browser window"
          className="grid size-8 place-items-center rounded-lg border border-line/80 bg-panel text-ink hover:bg-ink/[.06]"
        >
          <ExternalLink className="size-3.5" />
        </a>

        {/* Viewports */}
        <div className="hidden items-center gap-1 rounded-full border border-line/80 bg-panel/80 p-1 shadow-sm md:flex">
          {VIEWPORTS.map(({ id, label, Icon }) => (
            <Cell key={id} tip={label} side="left" on={vp === id}
                  onClick={() => setVp(id)} className="rounded-full px-3">
              <Icon className="size-3.5" />
            </Cell>
          ))}
        </div>

        {/* Select & Pencil Tools */}
        <div className="flex items-center gap-1 rounded-full border border-line/80 bg-panel/80 p-1 shadow-sm">
          <Cell tip="Click prototype elements to attach them to chat"
                side="left" on={pickOn} onClick={togglePick} className="rounded-full">
            <MousePointerClick className="size-3.5" />
          </Cell>
          <Cell tip="Draw on prototype to attach a marked-up screenshot"
                side="left" on={pencilOn} onClick={togglePencil} className="rounded-full">
            <Pencil className="size-3.5" />
          </Cell>
          <Cell tip={selection.length
                       ? `Clear ${selection.length} attachment${selection.length === 1 ? '' : 's'}`
                       : 'Nothing attached yet'}
                side="left" disabled={!selection.length}
                onClick={() => { clearSelection(); clearStrokes() }} className="rounded-full">
            <Eraser className="size-3.5" />
          </Cell>
          <Cell tip={undo ? `Undo the last edit (${undo.files.join(', ')})`
                          : 'Nothing to undo yet'}
                side="left" disabled={!undo} onClick={undoLast} className="rounded-full">
            <Undo2 className="size-3.5" />
          </Cell>
        </div>
      </div>

      {/* Frame Container */}
      <div className="relative min-h-0 flex-1 overflow-hidden bg-canvas">
        <canvas ref={canvasRef}
                className={cn('absolute z-[8]', pencilOn ? 'block' : 'hidden')}
                style={{ pointerEvents: pencilOn ? 'auto' : 'none',
                         cursor: pencilOn ? 'crosshair' : 'default' }} />

        {(pickOn || pencilOn) && (
          <p className="pointer-events-none absolute inset-x-0 bottom-7 z-[9] mx-auto w-fit rounded-full bg-ink/85 px-3.5 py-1.5 text-[11px] font-medium text-white shadow-lg">
            {pencilOn ? 'Draw around what you mean — it attaches to the chat'
                      : 'Click anything on the prototype — it attaches to the chat'}
          </p>
        )}


        <div className="relative flex min-h-0 h-full w-full items-start justify-center overflow-hidden bg-[#0c0f17]">
          <div
            className={cn("relative h-full w-full max-w-full overflow-hidden bg-[#0c0f17]", width && "border-x border-white/10 shadow-2xl")}
            style={{ width: width ? width + 'px' : '100%' }}
          >
            <iframe
              ref={frameRef}
              title="prototype-preview"
              src={prototypeUrl}
              onLoad={() => {
                checkPrototypeReady()
              }}
              className={cn(
                "absolute inset-0 block h-full w-full border-0 bg-white transition-opacity duration-300",
                (!protoReady || isBusy) ? "opacity-0 pointer-events-none" : "opacity-100"
              )}
            />

            {(!protoReady || isBusy) && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0c0f17] p-6 text-center select-none">
                {/* Glowing top line */}
                <div className="absolute inset-x-0 top-0 h-[2px] overflow-hidden bg-white/5">
                  <div className="h-full w-full bg-gradient-to-r from-purple-500 via-blue-500 to-indigo-400 animate-pulse" />
                </div>

                <div className="relative mb-5 grid size-16 place-items-center rounded-2xl border border-purple-500/25 bg-purple-500/10 shadow-[0_0_35px_rgba(168,85,247,0.2)]">
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-purple-600/20 to-indigo-600/20 animate-pulse" />
                  <FlaskConical className="size-7 text-purple-400 animate-pulse" />
                  <Loader2 className="absolute size-10 animate-spin text-purple-400/40" />
                </div>

                <h3 className="font-display text-[16px] font-bold tracking-tight text-white">
                  {isBusy ? 'Generating HTML Prototype…' : 'Loading prototype preview…'}
                </h3>
                <p className="mt-1.5 max-w-sm text-center text-[12px] text-slate-400 leading-relaxed">
                  {isBusy
                    ? 'The AI agent is crafting interactive wireframes, layouts, and responsive components.'
                    : 'Connecting to prototype canvas and mounting UI assets.'}
                </p>

                <div className="mt-4 flex items-center gap-2 rounded-full border border-purple-500/20 bg-purple-500/[0.06] px-4 py-1.5 font-mono text-[11px] text-purple-300 shadow-sm">
                  <span className="size-2 rounded-full bg-purple-400 animate-ping" />
                  <span className="truncate max-w-[280px]">
                    {statusText || (typeof progress === 'string' ? progress : '') || (isBusy ? 'Designing pages…' : `${project || 'project'} / ${currentFile}`)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Cell({ tip, on, className, children, ...rest }) {
  return (
    <Tip text={tip}>
      <button {...rest}
              aria-label={tip} aria-pressed={typeof on === 'boolean' ? on : undefined}
              className={cn('grid h-9 place-items-center px-2 text-ink transition-colors',
                on ? 'bg-accent text-white shadow-sm'
                   : 'hover:bg-ink/[.06] dark:hover:bg-white/[.06]',
                'disabled:pointer-events-none disabled:text-faint', className)}>
        {children}
      </button>
    </Tip>
  )
}
