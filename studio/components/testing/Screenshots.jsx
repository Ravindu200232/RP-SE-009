'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { Badge, Button, Empty, Modal } from '../ui'

/**
 * What the journeys noticed about the pages while they were open.
 *
 * The browser already loaded every page a journey visits, so its usability was
 * read off it there rather than in a pass of its own. The findings travel as
 * journey steps, which is why they are read back out of the stages here instead
 * of from a record of their own.
 */
function UiQuality({ qa }) {
  const rows = []
  for (const flow of (qa?.report?.e2e || {}).flows || []) {
    // Newer runs carry the checks beside the stages; older ones left them
    // inline among the steps, so both are read.
    for (const seen of flow.ui_quality || [])
      rows.push({ journey: flow.title, page: seen.page, note: seen.note })
    for (const stage of flow.stages || []) {
      const found = String(stage.label || stage.name || '').match(/^ui-quality\s+(\S+):\s*(.+)$/)
      if (found) rows.push({ journey: flow.title, page: found[1], note: found[2] })
    }
  }
  // One row per page: a page opened by four journeys was checked four times and
  // is still one page. A finding anywhere outranks a clean reading elsewhere.
  const byPage = new Map()
  for (const row of rows) {
    const held = byPage.get(row.page)
    if (!held || (held.note === 'clean' && row.note !== 'clean')) byPage.set(row.page, row)
  }
  const pages = [...byPage.values()].sort((a, b) => a.page.localeCompare(b.page))
  const flagged = pages.filter(row => row.note !== 'clean')
  if (!pages.length) {
    return (
      <p className="rounded-panel border border-line bg-panel px-4 py-3 text-[11.5px] text-muted">
        No page was read for usability — the journeys recorded no check.
      </p>
    )
  }
  return (
    <div className="space-y-2">
      <p className="text-[11.5px] text-muted">
        {pages.length} page{pages.length === 1 ? '' : 's'} checked while the journeys had them
        open — {flagged.length
          ? `${flagged.length} with findings, ${pages.length - flagged.length} clean`
          : 'all clean: no unnamed control, missing alt text, broken image, dead link or sideways scroll'}.
      </p>
      <div className="space-y-1.5">
        {pages.map((row, i) => (
          <div key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-panel
                                  border border-line bg-panel px-4 py-2.5">
            <Badge tone={row.note === 'clean' ? 'ok' : 'warn'}>
              {row.note === 'clean' ? 'clean' : 'findings'}
            </Badge>
            <code className="font-mono text-[11px] text-ink">{row.page}</code>
            <span className="text-[10px] text-muted2">{row.journey}</span>
            {row.note !== 'clean' && <span className="text-[11.5px] text-[#FFAB00]">{row.note}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Screenshots({ qa }) {
  const [selected, setSelected] = useState(null)
  const shots = qa?.screenshots || []
  const url = shot => api.qaScreenshotUrl(qa.project, shot.path, shot.at)
  if (!shots.length) {
    return (
      <div className="space-y-4">
        <UiQuality qa={qa} />
        <Empty>No saved screenshots for this project yet.</Empty>
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <UiQuality qa={qa} />
      <p className="text-[11.5px] text-muted">{shots.length} saved screenshots · Select a capture to inspect it at full size.</p>
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(230px,1fr))]">
        {shots.map(shot => (
          <button key={shot.path} onClick={() => setSelected(shot)} className="overflow-hidden rounded-panel border border-line bg-panel text-left hover:border-accent">
            {/* Captured local artifacts have dynamic project paths and dimensions. */}
            <img src={url(shot)} alt={shot.name} loading="lazy" className="h-44 w-full border-b border-line bg-panel2 object-contain object-top" />
            <div className="space-y-2 p-3">
              <p className="break-all text-[12px] font-medium text-ink">{shot.name}</p>
              <div className="flex items-center justify-between gap-2 text-[10px] text-muted">
                <span>{shot.width} × {shot.height}</span><Badge tone={shot.status === 'failed' ? 'bad' : 'mute'}>{shot.status}</Badge>
              </div>
              <p className="text-[10px] text-muted2">{new Date(shot.at).toLocaleString()}</p>
            </div>
          </button>
        ))}
      </div>
      {selected && <Modal onClose={() => setSelected(null)} className="max-w-[1100px]">
        <div role="dialog" aria-modal="true" aria-label={selected.name}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="break-all text-sm font-semibold text-ink">{selected.name}</h3>
            <Button onClick={() => setSelected(null)}>Close screenshot</Button>
          </div>
          <p className="mb-3 text-[11px] text-muted">{selected.width} × {selected.height} · {selected.findings}</p>
          <img src={url(selected)} alt={selected.name} className="h-auto w-full" />
        </div>
      </Modal>}
    </div>
  )
}
