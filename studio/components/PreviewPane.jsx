'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Monitor, Tablet, Smartphone, MousePointerClick, Pencil, Undo2, RotateCw,
  Image as ImageIcon, ChevronLeft, ChevronRight, Upload, Loader2,
} from 'lucide-react'
import { useStore } from '@/lib/store'
import { send } from '@/lib/ws'
import { api } from '@/lib/api'
import {
  attachPicker, frameDoc, elementInfo, pickedFrom, pickLabel, previewPath,
} from '@/lib/picker'
import { consoleReport, forgetConsole, watchFrame } from '@/lib/console-log'
import { Button, Input, Tip } from './ui'
import { useEditAttachments } from '@/lib/use-edit-attachments'
import EditAttach from './EditAttach'
import BuildOverlay from './BuildOverlay'
import { cn } from '@/lib/utils'

const ACCEPT_PICTURE = '.png,.jpg,.jpeg,.webp,.gif,.bmp,image/*'

const VIEWPORTS = [
  { id: 'desktop', label: 'Desktop', w: null, Icon: Monitor },
  { id: 'tablet', label: 'Tablet', w: 834, Icon: Tablet },
  { id: 'mobile', label: 'Mobile', w: 390, Icon: Smartphone },
]


export default function PreviewPane({ hidden }) {
  const frameRef = useRef(null)
  const canvasRef = useRef(null)
  const detachRef = useRef(null)
  const strokesRef = useRef([])
  const drawingRef = useRef(false)
  const swapRef = useRef(null)
  const files = useEditAttachments()
  const [reading, setReading] = useState(false)

  const project = useStore(s => s.project)
  const busy = useStore(s => s.busy)
  const addLog = useStore(s => s.addLog)
  const setBusy = useStore(s => s.setBusy)
  const setPreviewRoute = useStore(s => s.setPreviewRoute)
  const models = useStore(s => s.models)
  const think = useStore(s => s.think)
  const undo = useStore(s => s.undo)
  const setUndo = useStore(s => s.setUndo)

  const [vp, setVp] = useState('desktop')
  const [pickOn, setPickOn] = useState(false)
  const [pencilOn, setPencilOn] = useState(false)
  const [imageOn, setImageOn] = useState(false)
  const [picked, setPicked] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [path, setPath] = useState('/')
  // The preview's own history, kept here rather than driven through
  // `contentWindow.history`. An iframe shares the joint session history with
  // the page holding it, so `history.back()` on a preview that has not
  // navigated yet steps the STUDIO backwards and takes the whole workspace
  // with it. Tracking the paths and setting `src` cannot do that.
  const trail = useRef(['/'])
  const at = useRef(0)
  const jumping = useRef(false)
  const [nav, setNav] = useState({ back: false, forward: false })

  const attach = useCallback(() => {
    detachRef.current?.()
    detachRef.current = attachPicker(frameRef.current, (el) => {
      setPicked(pickedFrom(frameRef.current, el, vp))
      setPrompt('')
    })
    if (!detachRef.current) addLog('WARN', 'The preview is not loaded yet')
  }, [vp, addLog])

  useEffect(() => {
    if (pickOn || imageOn) attach()
    else { detachRef.current?.(); detachRef.current = null }
    return () => { detachRef.current?.(); detachRef.current = null }
  }, [pickOn, imageOn, attach])

  useEffect(() => {
    const f = frameRef.current
    if (!f) return
    const onLoad = () => {
      // Before anything else: a navigation replaces the frame's window, and
      // the first error of the new page can arrive during its first render.
      watchFrame(f)
      const here = previewPath(f)
      setPath(here)
      setPreviewRoute(here)
      if (jumping.current) {
        // Our own back/forward landing; the trail already knows about it.
        jumping.current = false
      } else if (trail.current[at.current] !== here) {
        // A click inside the app. Anything ahead of here is a branch nobody
        // can return to, which is what a browser does too.
        trail.current = trail.current.slice(0, at.current + 1).concat(here)
        at.current = trail.current.length - 1
      }
      setNav({ back: at.current > 0,
               forward: at.current < trail.current.length - 1 })
      if (pickOn || imageOn) attach()
    }
    f.addEventListener('load', onLoad)
    return () => f.removeEventListener('load', onLoad)
  }, [pickOn, imageOn, attach])

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
    } catch {  }
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

      try {
        const d = frameDoc(frameRef.current)
        const el = d && d.elementFromPoint(pt.cx, pt.cy)
        if (el) setPicked(elementInfo(frameRef.current, el, vp))
      } catch {  }
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
      if (strokesRef.current.reduce((a, s) => a + s.length, 0) < 3) return
      setPrompt('')
      setPicked(p => p || { tag: '', route: path })
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
  }, [pencilOn, point, syncCanvas, vp, path])

  function togglePick() {
    if (!project) return addLog('WARN', 'Open a project first')
    if (!pickOn) { setPencilOn(false); setImageOn(false) }
    setPickOn(v => !v)
    setPicked(null)
  }

  function togglePencil() {
    if (!project) return addLog('WARN', 'Open a project first')
    if (!pencilOn) { setPickOn(false); setImageOn(false) }
    setPencilOn(v => { if (v) clearStrokes(); return !v })
    setPicked(null)
  }

  /**
   * Redraw a picture, rather than the markup around it.
   *
   * The backend has always been able to do this — clicking an `<img>` with the
   * select tool routed to `image_edit`. Nobody could tell: the tool that
   * redraws a photograph and the tool that edits a heading were the same
   * button, and which one you got depended on what you happened to hit. This
   * makes it a tool you choose, and while it is on, only pictures respond.
   */
  function toggleImage() {
    if (!project) return addLog('WARN', 'Open a project first')
    if (!imageOn) { setPickOn(false); setPencilOn(false); clearStrokes() }
    setImageOn(v => !v)
    setPicked(null)
  }

  async function undoLast() {
    if (!project || !undo) return
    try {
      const r = await api.undo(project, undo.id || '')
      addLog('SUCCESS', 'Restored ' + (r.restored || []).join(', '))
      setUndo(null)
      const f = frameRef.current
      if (f) f.src = previewPath(f)
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
    f.src = trail.current[next]
    setNav({ back: next > 0, forward: next < trail.current.length - 1 })
  }

  function reloadPreview() {
    const f = frameRef.current
    if (!f) return
    try {
      f.contentWindow.location.reload()
    } catch {
      f.src = previewPath(f)
    }
  }

  // What the overlay lifts to reveal has to be the finished app.
  //
  // Nothing reloads the preview at the end of a run: the generated app's own
  // Fast Refresh patches each file into the frame AS it is written, so by the
  // time the work stops the frame is holding a page assembled out of however
  // many half-applied refreshes happened on the way — a component that imports
  // one that had not been written yet, a page mid-rewrite, an error boundary
  // from three files ago. Reloading once on the falling edge of `busy` means
  // the first thing seen is the app as it actually stands on disk.
  const wasBusy = useRef(false)
  useEffect(() => {
    if (wasBusy.current && !busy) reloadPreview()
    wasBusy.current = busy
  }, [busy])

  async function submit() {
    const v = prompt.trim()
    if (!v || !picked) return

    // The image tool always redraws; the select tool still falls through to
    // it when what was clicked happens to be a picture.
    const kind = pencilOn ? 'pencil_edit'
      : (imageOn || picked.isImage) ? 'image_edit' : 'element_edit'

    // Read anything attached first: it becomes part of the instruction, so it
    // has to be in hand before the message goes. `picked` is captured because
    // the reads are awaited and the bar clears itself below.
    let full = v
    if (files.items.length) {
      setReading(true)
      try {
        full = v + await files.collect(project)
      } catch (e) {
        addLog('WARN', `⚠ ${e.message}`)
      }
      setReading(false)
    }

    send({
      type: kind, project, prompt: full, element: picked,
      model: models.agent || models.build, think,
      route: picked.route || path, scroll: picked.scroll, viewport: picked.viewport,
      strokes: pencilOn ? strokesRef.current : undefined,
      console: consoleReport(),
    })
    forgetConsole()
    files.reset()
    addLog('INFO', (pencilOn ? 'Redesign: '
      : kind === 'image_edit' ? 'New picture: ' : 'Edit: ') + v)
    setBusy(true)
    setPicked(null)
    setPrompt('')
    if (pencilOn) clearStrokes(); else if (!imageOn) setPickOn(false)
  }

  async function swapPicture(file) {
    if (!file || !picked) return
    const target = picked
    setBusy(true)
    setPicked(null)
    setPrompt('')
    addLog('INFO', `Your picture: ${file.name}`)
    try {
      await api.imageSwap(file, { project, element: target })
    } catch (e) {
      // The generated path reports failure over the websocket, which only
      // starts once the work does. A file rejected before that — too large,
      // unreadable — has no other way to be heard.
      setBusy(false)
      addLog('WARN', `⚠ ${e.message}`)
    }
  }

  const width = VIEWPORTS.find(x => x.id === vp)?.w

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col', hidden && 'hidden')}>
      <div className="flex shrink-0 items-center gap-2 border-b border-line
                      bg-panel px-3 py-2">
        <span className="flex gap-[5px]">
          {['bg-bad/60', 'bg-warn/60', 'bg-ok/60'].map(c => (
            <i key={c} className={cn('size-[9px] rounded-full', c)} />
          ))}
        </span>
        <Tip text={nav.back ? 'Back' : 'Nothing to go back to'}>
          <Button size="icon-sm" disabled={!nav.back} onClick={() => step(-1)}>
            <ChevronLeft className="size-3.5" />
          </Button>
        </Tip>
        <Tip text={nav.forward ? 'Forward' : 'Nothing to go forward to'}>
          <Button size="icon-sm" disabled={!nav.forward} onClick={() => step(1)}>
            <ChevronRight className="size-3.5" />
          </Button>
        </Tip>
        <Tip text="Load the preview again">
          <Button size="icon-sm" onClick={reloadPreview}>
            <RotateCw className="size-3" />
          </Button>
        </Tip>
        <span className="truncate rounded-ctl border border-line bg-bg px-2.5 py-1
                         font-mono text-[10px] text-muted">
          localhost:5173{path === '/' ? '' : path}
        </span>
        <span className="flex-1" />
        <div className="flex gap-[3px]">
          {VIEWPORTS.map(({ id, label, Icon }) => (
            <Tip key={id} text={label}>
              <Button size="icon-sm" onClick={() => setVp(id)}
                      className={cn(vp === id && 'bg-accent/15 text-accent')}>
                <Icon className="size-3" />
              </Button>
            </Tip>
          ))}
          <span className="mx-1 w-px bg-line" />
          <Tip text="Click an element in the preview to edit it">
            <Button size="icon-sm" onClick={togglePick}
                    className={cn(pickOn && 'bg-accent/15 text-accent')}>
              <MousePointerClick className="size-3" />
            </Button>
          </Tip>
          <Tip text="Draw over a region and describe the redesign">
            <Button size="icon-sm" onClick={togglePencil}
                    className={cn(pencilOn && 'bg-accent/15 text-accent')}>
              <Pencil className="size-3" />
            </Button>
          </Tip>
          <Tip text="Click a picture and describe the one you want instead">
            <Button size="icon-sm" onClick={toggleImage}
                    className={cn(imageOn && 'bg-accent/15 text-accent')}>
              <ImageIcon className="size-3" />
            </Button>
          </Tip>
          <Tip text={undo ? `Undo the last edit (${undo.files.join(', ')})`
                          : 'Nothing to undo yet'}>
            <Button size="icon-sm" disabled={!undo} onClick={undoLast}>
              <Undo2 className="size-3" />
            </Button>
          </Tip>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-bg">
        <BuildOverlay />

        <canvas ref={canvasRef}
                className={cn('absolute z-[5]', pencilOn ? 'block' : 'hidden')}
                style={{ pointerEvents: pencilOn ? 'auto' : 'none' }} />

        {picked && (
          <div className="absolute inset-x-0 bottom-0 z-[6] border-t border-accent/40
                          bg-panel px-3 py-2.5">
            <div className="mb-1.5 truncate font-mono text-[10px] text-muted">
              {pencilOn
                ? `Redesign the drawn region Â· ${picked.tag ? '<' + picked.tag + '>' : ''} Â· ${path}`
                : imageOn && !picked.isImage
                ? `That is not a picture Â· ${picked.tag ? '<' + picked.tag + '>' : ''} Â· click an image`
                : pickLabel(picked)}
            </div>
            <div className="flex gap-1.5">
              <Input autoFocus value={prompt}
                     placeholder={pencilOn ? 'How should this part look?'
                       : (imageOn || picked.isImage)
                         ? 'Describe the picture you want instead — or upload your own'
                       : 'What should change?'}
                     onChange={e => setPrompt(e.target.value)}
                     onKeyDown={e => {
                       if (e.key === 'Enter') submit()
                       if (e.key === 'Escape') setPicked(null)
                     }} />

              {/* Only for a real picture: the swap works by finding this
                  element's src written in the source, and something with no
                  src has nothing to rewrite. */}
              {picked.isImage && (
                <>
                  <input ref={swapRef} type="file" hidden accept={ACCEPT_PICTURE}
                         onChange={e => {
                           const chosen = e.target.files?.[0]
                           e.target.value = ''
                           swapPicture(chosen)
                         }} />
                  <Tip text="Use a picture of your own instead of drawing one">
                    <Button variant="outline" onClick={() => swapRef.current?.click()}>
                      <Upload className="size-3" /> Upload
                    </Button>
                  </Tip>
                </>
              )}

              <Button variant="solid" onClick={submit} disabled={reading}>
                {reading ? <Loader2 className="size-3 animate-spin" /> : 'Send'}
              </Button>
              <Button variant="outline" onClick={() => { files.reset(); setPicked(null) }}>
                Cancel
              </Button>
            </div>

            <EditAttach attach={files} disabled={reading} className="mt-1.5" />
          </div>
        )}

        <iframe ref={frameRef} id="frame" title="preview" src="/"
                className="block h-full border-0 bg-white"
                style={{ width: width ? width + 'px' : '100%',
                         margin: width ? '0 auto' : undefined }} />
      </div>
    </div>
  )
}
