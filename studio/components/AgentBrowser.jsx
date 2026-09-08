'use client'

/**
 * The agent's own Chrome, in the preview.
 *
 * The engine drives a real headless Chrome — it opens pages, fills forms and
 * photographs screens — and headless means none of that is visible. A looping
 * illustration used to sit here instead, which looked like progress without
 * being any of it.
 *
 * So this is the window onto that browser: a screencast of the tab the agent
 * is actually on, streamed frame by frame over the same socket as the chat. It
 * covers the preview only while frames are arriving; the moment the run ends
 * the preview underneath is the interesting thing again.
 */

import { useEffect, useState } from 'react'
import { useStore } from '@/lib/store'

// A cast that has gone quiet for this long is over — the tab closed, or the
// run moved on to work that is not in a browser. Holding a frozen frame on
// top of a working preview is worse than showing nothing.
const STALE_MS = 8000

export default function AgentBrowser() {
  const shot = useStore(s => s.browserFrame)
  const [stale, setStale] = useState(false)

  useEffect(() => {
    if (!shot?.frame) return
    setStale(false)
    const id = setTimeout(() => setStale(true), STALE_MS)
    return () => clearTimeout(id)
  }, [shot])

  if (!shot?.frame || stale) return null

  return (
    <div className="absolute inset-0 z-[6] flex flex-col bg-[#1f2430]">
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

      <img src={shot.frame} alt="What the agent's browser is showing"
           className="min-h-0 w-full flex-1 select-none object-contain object-top" />
    </div>
  )
}
