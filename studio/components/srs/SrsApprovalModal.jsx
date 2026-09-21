'use client'

/** Explicit approval gate between an SRS draft and changes to built artifacts. */
import { useState } from 'react'
import { Button, Modal } from '../ui'

const WHAT = {
  designer: ['Prototype', 'the wireframes and UI design'],
  developer: ['Builder', 'the frontend code and its tests'],
}

/**
 * A revised SRS is safe to keep as a draft. This dialog is the deliberate
 * hand-off that allows it to change a prototype or the application.
 */
export default function SrsApprovalModal({
  targets,
  version,
  changed,
  busy,
  defaultTargets = targets,
  onApprove,
  onKeepDraft,
}) {
  const [picked, setPicked] = useState(() => new Set(defaultTargets))
  const firstTarget = WHAT[[...picked][0]]?.[0].toLowerCase() || 'selected work'
  const toggle = role => setPicked(was => {
    const next = new Set(was)
    next.has(role) ? next.delete(role) : next.add(role)
    return next
  })

  return (
    <Modal onClose={busy ? () => { } : onKeepDraft} className="max-w-[460px]">
      <div role="dialog" aria-modal="true" aria-label="Approve this SRS update">
        <p className="text-[10px] font-bold uppercase tracking-wider text-accent">Plan review</p>
        <h3 className="mt-1 text-sm font-semibold text-ink">
          Review SRS update{version ? ` · v${version}` : ''}
        </h3>
        <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
          This SRS revision is a draft. No prototype or Builder files change until
          you approve the deliverables below.
        </p>
        {changed ? (
          <p className="mt-3 whitespace-pre-wrap rounded-xl border border-line bg-panel2 px-3 py-2.5 text-[11.5px] leading-relaxed text-muted">
            {changed}
          </p>
        ) : (
          <p className="mt-3 rounded-xl border border-line bg-panel2 px-3 py-2.5 text-[11.5px] text-muted">
            The SRS was revised. Review its version history for the full document change.
          </p>
        )}
        <p className="mt-3 text-[11.5px] text-muted">
          Apply this approved plan to:
        </p>

        <div className="mt-3 space-y-1.5">
          {targets.map(role => (
            <label key={role}
              className="flex cursor-pointer items-start gap-2.5 rounded-panel border
                         border-line bg-panel2 px-3 py-2.5 hover:border-accent">
              <input type="checkbox" checked={picked.has(role)} disabled={busy}
                onChange={() => toggle(role)} className="mt-0.5 accent-[#1877F2]" />
              <span className="min-w-0">
                <span className="block text-[12px] font-medium text-ink">{WHAT[role][0]}</span>
                <span className="block text-[10.5px] text-muted2">{WHAT[role][1]}</span>
              </span>
            </label>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="outline" disabled={busy} onClick={onKeepDraft}>Keep SRS draft</Button>
          <Button disabled={busy || !picked.size} onClick={() => onApprove([...picked])}>
            {busy ? 'Starting…' : `Approve & update ${picked.size === 2 ? 'both' : firstTarget}`}
          </Button>
        </div>
        <p className="mt-2.5 text-[10px] leading-relaxed text-muted2">
          The Prototype runs before the Builder when both are selected, so the code
          is updated from the approved design rather than a stale screen.
        </p>
      </div>
    </Modal>
  )
}
