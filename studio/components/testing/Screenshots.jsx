'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { Badge, Button, Empty, Modal } from '../ui'

export default function Screenshots({ qa }) {
  const [selected, setSelected] = useState(null)
  const shots = qa?.screenshots || []
  if (!shots.length) return <Empty>No saved screenshots for this project yet.</Empty>
  const url = shot => api.qaScreenshotUrl(qa.project, shot.path, shot.at)
  return (
    <div className="space-y-4">
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
