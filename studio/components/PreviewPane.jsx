'use client'

/**
 * The running app, and the two ways of pointing at it.
 *
 * Everything you can do here ends in the same place: an attachment on the
 * message you are about to send. Clicking an element attaches the element and
 * a photograph of it; drawing attaches the page with your red line still on
 * it. Neither one starts a run on its own, because "this bit" is never the
 * whole request — the sentence in the chat box is the other half.
 *
 * The agent's own headless Chrome covers this pane while it is working, since
 * during a build the preview underneath has nothing in it yet.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Monitor, Tablet, Smartphone, MousePointerClick, Pencil, Undo2, RotateCw,
  ChevronLeft, ChevronRight, Globe, Eraser, Rocket, Layers,
} from 'lucide-react'
import { useStore } from '@/lib/store'
import { api, API } from '@/lib/api'
import { attachPicker, pickedFrom, pickLabel } from '@/lib/picker'
import { watchFrame, recordConsole } from '@/lib/console-log'
import { Tip } from './ui'
import AgentBrowser from './AgentBrowser'
import LiveE2EOverlay from './LiveE2EOverlay'
import { cn } from '@/lib/utils'

const VIEWPORTS = [
  { id: 'desktop', label: 'Desktop', w: null, Icon: Monitor },
  { id: 'tablet', label: 'Tablet', w: 834, Icon: Tablet },
  { id: 'mobile', label: 'Mobile', w: 390, Icon: Smartphone },
]

// Fewer points than this is a stray click, not a drawing.
const MIN_INK = 3

let seq = 0

function currentPath(frame) {
  if (frame?.dataset?.remote === 'true') return frame.dataset.route || '/'
  try {
    const loc = frame?.contentWindow?.location
    if (!loc || !loc.pathname?.startsWith('/') || !/^https?:$/.test(loc.protocol)) return '/'
    return `${loc.pathname || '/'}${loc.search || ''}${loc.hash || ''}`
  } catch {
    return '/'
  }
}

export default function PreviewPane({ hidden, onBuild }) {
  const frameRef = useRef(null)
  const canvasRef = useRef(null)
  const detachRef = useRef(null)
  const strokesRef = useRef([])
  const drawingRef = useRef(false)
  const lastPathRef = useRef('/')

  const project = useStore(s => s.project)
  const files = useStore(s => s.files)
  const hasBuiltApp = Object.keys(files || {}).some(f =>
    f.startsWith('app/') || f.startsWith('src/') || f.startsWith('pages/') || f === 'package.json'
  )
  const busy = useStore(s => s.busy && (!s.busyProject || s.busyProject === s.project))
  const runtime = useStore(s => s.runtimes[s.project])
  const addLog = useStore(s => s.addLog)
  const setPreviewRoute = useStore(s => s.setPreviewRoute)
  const undo = useStore(s => s.undo)
  const setUndo = useStore(s => s.setUndo)
  const tests = useStore(s => s.tests)
  const e2eLive = useStore(s => s.e2eLive)
  const drawing = useStore(s => s.drawing)
  const setDrawing = useStore(s => s.setDrawing)
  const selection = useStore(s => s.selection)
  const addSelection = useStore(s => s.addSelection)
  const patchSelection = useStore(s => s.patchSelection)
  const clearSelection = useStore(s => s.clearSelection)

  const [vp, setVp] = useState('desktop')
  const [pickOn, setPickOn] = useState(false)
  const [pencilOn, setPencilOn] = useState(false)
  const [path, setPath] = useState('/')
  const trail = useRef(['/'])
  const at = useRef(0)
  const jumping = useRef(false)
  const [nav, setNav] = useState({ back: false, forward: false })

  const bridgeSend = useCallback((kind, data = {}) => {
    if (!runtime?.previewUrl || !runtime.runtimeId) return
    frameRef.current?.contentWindow?.postMessage({ type: 'agentforge:command', kind,
      project, runtimeId: runtime.runtimeId, ...data }, new URL(runtime.previewUrl).origin)
  }, [project, runtime?.runtimeId, runtime?.previewUrl])

  const markActivity = useCallback(() => {
    if (runtime?.runtimeId) api.previewActivity(project, runtime.runtimeId).catch(() => {})
  }, [project, runtime?.runtimeId])

  const navigate = useCallback((route = '/') => {
    const f = frameRef.current
    if (!f || !runtime?.previewUrl) return
    f.dataset.remote = 'true'
    f.dataset.route = route
    f.dataset.scrollX = '0'; f.dataset.scrollY = '0'
    f.src = new URL(route, runtime.previewUrl).href
  }, [runtime?.previewUrl])

  // Observing status never keeps an idle app alive. This also recovers missed
  // socket events after a Studio reload or a backend reconnect.
  useEffect(() => {
    if (!project) return
    let active = true
    const read = () => api.runtime(project).then(result => {
      if (active) useStore.getState().setRuntime(result)
    }).catch(() => {})
    read()
    const timer = setInterval(read, 2000)
    return () => { active = false; clearInterval(timer) }
  }, [project])

  useEffect(() => {
    if (!drawing && runtime?.status === 'running') navigate(lastPathRef.current)
  }, [runtime?.runtimeId, runtime?.status, drawing, navigate])

  const syncPath = useCallback((reason = 'navigation') => {
    const here = currentPath(frameRef.current)
    if (!here) return
    if (lastPathRef.current === here && reason !== 'load') return
    lastPathRef.current = here
    setPath(here)
    setPreviewRoute(here)

    if (jumping.current) {
      jumping.current = false
    } else if (trail.current[at.current] !== here) {
      trail.current = trail.current.slice(0, at.current + 1).concat(here)
      at.current = trail.current.length - 1
    }
    setNav({ back: at.current > 0, forward: at.current < trail.current.length - 1 })
  }, [setPreviewRoute])

  /** The viewport a shot has to be taken at, or the box lands on the wrong thing. */
  const viewportOf = useCallback(() => {
    const f = frameRef.current
    return { w: f?.clientWidth || 1280, h: f?.clientHeight || 800, mode: vp }
  }, [vp])

  /**
   * Attach one thing to the message, then go and photograph it.
   *
   * The chip appears immediately and fills in when the picture arrives — a
   * capture takes about a second, and a selection that appears to do nothing
   * for a second gets clicked twice.
   */
  const attachShot = useCallback(async (item, body) => {
    addSelection(item)
    try {
      const r = await api.shot({ ...body, project, runtimeId: runtime?.runtimeId })
      patchSelection(item.key, r?.image
        ? { shot: r.image, state: 'ready' }
        : { state: 'blank' })
    } catch (e) {
      patchSelection(item.key, { state: 'blank' })
      addLog('WARN', `could not photograph that — ${e.message}`)
    }
  }, [addSelection, patchSelection, addLog, project, runtime?.runtimeId])

  const attach = useCallback(() => {
    detachRef.current?.()
    if (frameRef.current?.dataset.remote === 'true') {
      bridgeSend('pick', { enabled: true, mode: vp })
      detachRef.current = () => bridgeSend('pick', { enabled: false })
      return
    }
    detachRef.current = attachPicker(frameRef.current, (el) => {
      const info = pickedFrom(frameRef.current, el, vp)
      attachShot(
        { key: `sel-${++seq}`, kind: 'element', info, state: 'shooting',
          label: pickLabel(info), route: info.route || currentPath(frameRef.current) },
        { route: info.route, viewport: info.viewport || viewportOf(),
          scroll: info.scroll, rect: info.rect })
    })
    if (!detachRef.current) addLog('WARN', 'The preview is not loaded yet')
  }, [vp, addLog, attachShot, viewportOf, bridgeSend])

  useEffect(() => {
    const receive = event => {
      const message = event.data
      if (!runtime?.previewUrl || event.source !== frameRef.current?.contentWindow ||
          event.origin !== new URL(runtime.previewUrl).origin ||
          message?.type !== 'agentforge:preview' || message.project !== project ||
          message.runtimeId !== runtime.runtimeId) return
      if (message.kind === 'route' && typeof message.route === 'string' && message.route.startsWith('/')) {
        const f = frameRef.current
        f.dataset.route = message.route
        f.dataset.scrollX = String(message.scroll?.x || 0)
        f.dataset.scrollY = String(message.scroll?.y || 0)
        syncPath()
      }
      if (message.kind === 'ready' && pickOn) bridgeSend('pick', { enabled: true, mode: vp })
      if (message.kind === 'console') recordConsole(message.level, message.text)
      if (message.kind === 'picked' && pickOn && message.info) {
        const info = message.info
        attachShot({ key: `sel-${++seq}`, kind: 'element', info, state: 'shooting',
          label: pickLabel(info), route: info.route },
          { route: info.route, viewport: info.viewport || viewportOf(), scroll: info.scroll, rect: info.rect })
      }
    }
    window.addEventListener('message', receive)
    return () => window.removeEventListener('message', receive)
  }, [project, runtime?.previewUrl, runtime?.runtimeId, syncPath, pickOn, bridgeSend, vp, attachShot, viewportOf])

  useEffect(() => {
    if (pickOn) attach()
    else { detachRef.current?.(); detachRef.current = null }
    return () => { detachRef.current?.(); detachRef.current = null }
  }, [pickOn, attach])

  useEffect(() => {
    const f = frameRef.current
    if (!f) return
    const onLoad = () => {
      bridgeSend('init')
      watchFrame(f)
      syncPath('load')
      if (pickOn) attach()
    }
    f.addEventListener('load', onLoad)
    return () => f.removeEventListener('load', onLoad)
  }, [pickOn, attach, syncPath, bridgeSend])

  useEffect(() => {
    const id = setInterval(() => syncPath('poll'), 250)
    return () => clearInterval(id)
  }, [syncPath])

  // Mirror the route the agent's journey is on in the visible preview.
  useEffect(() => {
    const route = String(e2eLive?.route || '')
    if (!tests.running || !route.startsWith('/')) return
    const f = frameRef.current
    if (!f || currentPath(f) === route) return
    jumping.current = true
    if (runtime?.status === 'running') navigate(route)
  }, [e2eLive?.route, tests.running, runtime?.status, navigate])

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
    if (frameRef.current?.dataset.remote === 'true') {
      sx = Number(frameRef.current.dataset.scrollX || 0)
      sy = Number(frameRef.current.dataset.scrollY || 0)
    }
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
      markActivity()
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
    // Lifting the pen finishes one annotation: it is photographed as it stands
    // and attached, and the canvas is wiped so the next ring is its own note.
    const up = () => {
      if (!drawingRef.current) return
      drawingRef.current = false
      const strokes = strokesRef.current
      if (strokes.reduce((a, s) => a + s.length, 0) < MIN_INK) return clearStrokes()
      const route = currentPath(frameRef.current)
      attachShot(
        { key: `sel-${++seq}`, kind: 'drawing', strokes, route, state: 'shooting',
          label: `Drawing on ${route}` },
        { route, viewport: viewportOf(), strokes })
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
  }, [pencilOn, point, syncCanvas, clearStrokes, attachShot, viewportOf, markActivity])

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
      const f = frameRef.current
      if (f) navigate(currentPath(f))
    } catch (e) {
      addLog('WARN', 'Undo failed: ' + e.message)
    }
  }

  function step(by) {
    const f = frameRef.current
    const next = at.current + by
    if (!f || next < 0 || next >= trail.current.length) return
    at.current = next
    jumping.current = true
    markActivity()
    navigate(trail.current[next])
    setNav({ back: next > 0, forward: next < trail.current.length - 1 })
  }

  async function reloadPreview(fromRoot = false) {
    const f = frameRef.current
    if (!f) return
    // An iframe mounted before startup may still be about:blank or a browser
    // error document. Reloading that document never reaches the ready app.
    if (drawing) { f.src = currentPath(f); return }
    try {
      const result = await api.open(project)
      useStore.getState().setRuntime(result)
      if (result.status === 'running') navigate(fromRoot === true ? '/' : currentPath(f))
    } catch (error) { addLog('WARN', `Could not reopen app: ${error.message}`) }
  }

  /**
   * Prototype drawings are rendered in their own dedicated Prototype tab.
   * PreviewPane renders the actual running full-stack application.
   * Contract note: prototypes are served under /prototype/ and accepted with Build this.
   */
  useEffect(() => {
    const f = frameRef.current
    if (!f) return
    if (!drawing && runtime?.status === 'running') {
      navigate('/')
    }
  }, [drawing, project, runtime?.status, navigate])

  async function approveDrawing() {
    const id = drawing?.id
    if (!id) return
    setDrawing(null)
    try {
      await api.decide({ id, decision: 'approve' })
    } catch (e) {
      addLog('WARN', `Could not accept the drawing — ${e.message}`)
    }
  }

  const wasBusy = useRef(false)
  const hasReadyPreview = useRef(!busy)
  useEffect(() => {
    if (wasBusy.current && !busy) {
      // The shared public origin may still display the previous project's
      // route while this one starts. Its first ready navigation begins at /.
      reloadPreview(!hasReadyPreview.current)
      hasReadyPreview.current = true
    }
    wasBusy.current = busy
  }, [busy])

  const width = VIEWPORTS.find(x => x.id === vp)?.w
  const shownPath = tests.running && e2eLive?.route ? e2eLive.route : path

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col bg-transparent', hidden && 'hidden')}>
      <div className="flex h-[54px] shrink-0 items-center gap-3 border-b border-line/70 bg-white/72 px-4 backdrop-blur-2xl dark:bg-white/[.03]">
        <div className="flex items-center gap-1 rounded-full border border-line/80 bg-panel/90 p-1 shadow-sm">
          <Cell tip={nav.back ? 'Back' : 'Nothing to go back to'}
                disabled={!nav.back} onClick={() => step(-1)} className="rounded-full px-3">
            <ChevronLeft className="size-3.5" />
          </Cell>
          <Cell tip={nav.forward ? 'Forward' : 'Nothing to go forward to'}
                disabled={!nav.forward} onClick={() => step(1)} className="rounded-full px-3">
            <ChevronRight className="size-3.5" />
          </Cell>
          <Cell tip="Reload the preview" onClick={reloadPreview} className="rounded-full px-3">
            <RotateCw className="size-3.5" />
          </Cell>
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-[14px] bg-black/[.035] px-4 py-2 text-[12px] text-muted ring-1 ring-black/[.045] dark:bg-white/[.045] dark:ring-white/[.06]">
          <Globe className="size-3.5 shrink-0 text-accent" />
          <span className="truncate font-medium text-ink">
            {drawing ? `the drawing — ${shownPath.split('/').pop() || 'index.html'}`
                     : runtime?.previewUrl ? `${new URL(runtime.previewUrl).host}${shownPath === '/' ? '' : shownPath}` : 'App preview'}
          </span>
        </div>

        {!drawing && runtime?.status === 'running' && <span className="text-xs font-medium text-ok">Running</span>}

        {/* The drawing is judged here, in the preview, so this is where it is
            accepted. Sending it back is typed in the chat like anything else. */}
        {drawing && (
          <button onClick={approveDrawing}
                  className="shrink-0 rounded-full bg-accent px-4 py-2 text-[12px] font-semibold text-white shadow-sm transition-opacity hover:opacity-90">
            Build this
          </button>
        )}

        <div className="hidden items-center gap-1 rounded-full border border-line/80 bg-panel/80 p-1 shadow-sm md:flex">
          {VIEWPORTS.map(({ id, label, Icon }) => (
            <Cell key={id} tip={label} side="left" on={vp === id}
                  onClick={() => setVp(id)} className="rounded-full px-3">
              <Icon className="size-3.5" />
            </Cell>
          ))}
        </div>

        <div className="flex items-center gap-1 rounded-full border border-line/80 bg-panel/80 p-1 shadow-sm">
          <Cell tip="Click elements in the preview to attach them to your message"
                side="left" on={pickOn} onClick={togglePick} className="rounded-full">
            <MousePointerClick className="size-3.5" />
          </Cell>
          <Cell tip="Draw on the preview to attach a marked-up screenshot"
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

      <div className="relative min-h-0 flex-1 overflow-hidden bg-[radial-gradient(circle_at_top,#f8fbff_0%,#edf2fb_45%,#dfe7f5_100%)] p-4 dark:bg-[radial-gradient(circle_at_top,#1d2333_0%,#151a26_45%,#0f141d_100%)]">
        <canvas ref={canvasRef}
                className={cn('absolute z-[8]', pencilOn ? 'block' : 'hidden')}
                style={{ pointerEvents: pencilOn ? 'auto' : 'none',
                         cursor: pencilOn ? 'crosshair' : 'default' }} />

        {(pickOn || pencilOn) && (
          <p className="pointer-events-none absolute inset-x-0 bottom-7 z-[9] mx-auto w-fit rounded-full bg-ink/85 px-3.5 py-1.5 text-[11px] font-medium text-white shadow-lg">
            {pencilOn ? 'Draw around what you mean — it attaches to the chat'
                      : 'Click anything — it attaches to the chat'}
          </p>
        )}

        {tests.running && e2eLive && <LiveE2EOverlay event={e2eLive} />}

        <div className="relative flex min-h-0 flex-1 w-full items-start justify-center overflow-hidden bg-canvas">
          <div className={cn("relative h-full w-full max-w-full overflow-hidden bg-white", width && "border-x border-line shadow-lg")}
               style={{ width: width ? width + 'px' : '100%' }}>
            <iframe ref={frameRef} id="frame" title="preview" src="about:blank"
                    className="absolute inset-0 block h-full w-full border-0 bg-white" />
            {!hasBuiltApp && !runtime?.working && runtime?.status !== 'starting' ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-panel p-8 text-center" role="status">
                <div className="grid size-14 place-items-center rounded-2xl bg-accent/10 text-accent">
                  <Rocket className="size-7" />
                </div>
                <div className="max-w-md">
                  <h3 className="text-base font-bold text-ink">This app has not been built yet</h3>
                  <p className="mt-1 text-sm text-muted leading-relaxed">
                    Only the specification or HTML prototype exists so far. Build the full application to preview and interact with it live here.
                  </p>
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <button
                    onClick={() => useStore.getState().setView('prototype')}
                    className="inline-flex items-center gap-2 rounded-full border border-line bg-panel2 px-4 py-2 text-xs font-semibold text-ink shadow-sm transition hover:bg-ink/[.05]"
                  >
                    <Layers className="size-3.5 text-purple-500" /> View Prototype
                  </button>
                  {onBuild && (
                    <button
                      onClick={onBuild}
                      className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-md transition hover:bg-press"
                    >
                      <Rocket className="size-3.5" /> Build App Now
                    </button>
                  )}
                </div>
              </div>
            ) : runtime?.status !== 'running' ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-panel p-8 text-center" role="status">
                <p className="font-semibold text-ink">{runtime?.working ? 'Build in progress' : runtime?.status === 'starting'
                  ? 'Starting app…' : runtime?.status === 'failed' ? 'App could not start' : 'App stopped'}</p>
                <p className="max-w-lg text-sm text-muted">{runtime?.error || (runtime?.reason === 'idle'
                  ? 'Stopped after 10 minutes without activity.' : runtime?.working
                  ? 'The preview will open when the build is ready.' : runtime?.status === 'starting'
                  ? 'Waiting for the app to become ready.' : 'Open the app to continue.')}</p>
                {!runtime?.working && runtime?.status !== 'starting' && (
                  <button onClick={() => reloadPreview()} className="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-white">
                    {runtime?.status === 'failed' ? 'Retry' : 'Open app'}
                  </button>
                )}
              </div>
            ) : null}
            {/* While the agent is driving its own browser, that is the more
                interesting of the two — it is the one being tested. */}
            <AgentBrowser />
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
