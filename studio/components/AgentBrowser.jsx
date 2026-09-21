'use client'

/** Displays a live screencast of the agent's headless browser while active in the preview. */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { MousePointer2 } from 'lucide-react'
import { useStore } from '@/lib/store'

// Fallback timeout to terminate browser stream if disconnected without a close event.
const STALE_MS = 45000

function clamp(value) {
  return Math.max(0, Math.min(1, value))
}

function previewImageBox(stage, image) {
  const parent = stage.getBoundingClientRect()
  const naturalWidth = image.naturalWidth
  const naturalHeight = image.naturalHeight
  if (!parent.width || !parent.height || !naturalWidth || !naturalHeight) return null

  // `object-contain` letterboxes a frame inside the img element. Its DOM box
  // is the full stage, so calculate the actual painted image box before
  // mapping CDP's viewport coordinates into it. `object-top` keeps y at zero.
  const scale = Math.min(parent.width / naturalWidth, parent.height / naturalHeight)
  const width = naturalWidth * scale
  const height = naturalHeight * scale
  return { left: (parent.width - width) / 2, top: 0, width, height }
}

export default function AgentBrowser() {
  const shot = useStore(s => s.browserFrame)
  const [stale, setStale] = useState(false)
  const stageRef = useRef(null)
  const imageRef = useRef(null)
  const [imageBox, setImageBox] = useState(null)

  useLayoutEffect(() => {
    const stage = stageRef.current
    const image = imageRef.current
    if (!stage || !image) return undefined

    const measure = () => {
      const box = previewImageBox(stage, image)
      if (box) setImageBox(box)
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(stage)
    observer.observe(image)
    return () => observer.disconnect()
  }, [shot?.frame])

  useEffect(() => {
    if (!shot?.frame) return
    setStale(false)
    const id = setTimeout(() => setStale(true), STALE_MS)
    return () => clearTimeout(id)
  }, [shot])

  if (!shot?.frame || stale) return null

  const cursor = shot.cursor
  const viewport = shot.viewport
  const canPlaceCursor = cursor && viewport?.width && viewport?.height && imageBox
  const cursorStyle = canPlaceCursor ? {
    left: imageBox.left + clamp(Number(cursor.x) / Number(viewport.width)) * imageBox.width,
    top: imageBox.top + clamp(Number(cursor.y) / Number(viewport.height)) * imageBox.height,
  } : undefined

  return (
    <div className="absolute inset-0 z-[20] flex flex-col bg-[#1f2430] shadow-2xl">
      <div className="flex shrink-0 items-center gap-2 bg-[#2b3140] px-3 py-2">
        {['#ff5f57', '#febc2e', '#28c840'].map(colour => (
          <span key={colour} className="size-2.5 rounded-full"
                style={{ background: colour }} />
        ))}
        <span className="ml-1.5 flex min-w-0 flex-1 items-center gap-2 rounded-full bg-black/25 px-3 py-1">
          <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-[#28c840]" />
          <span className="truncate font-mono text-[10px] text-white/70">
            {shot.url || 'about:blank'}
          </span>
        </span>
        <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-white/70">
          agent
        </span>
      </div>

      <div ref={stageRef} className="relative min-h-0 flex-1 overflow-hidden">
        <img ref={imageRef} src={shot.frame} alt="What the agent's browser is showing"
             onLoad={() => {
               const stage = stageRef.current
               const image = imageRef.current
               if (!stage || !image) return
               const box = previewImageBox(stage, image)
               if (box) setImageBox(box)
             }}
             className="size-full select-none object-contain object-top" />
        {canPlaceCursor ? (
          <div aria-hidden="true" className="pointer-events-none absolute z-10 -translate-x-1 -translate-y-1 transition-[left,top] duration-100 ease-out"
               style={cursorStyle}>
            <span className="absolute left-1 top-1 size-5 animate-ping rounded-full bg-sky-400/45" />
            <MousePointer2 className="relative size-6 fill-sky-300 text-slate-950 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]" strokeWidth={2.5} />
            <span className="absolute left-5 top-5 whitespace-nowrap rounded bg-slate-950/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-sky-100">
              {cursor.action === 'type' ? 'typing' : cursor.action === 'key' ? 'key' : 'click'}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  )
}
