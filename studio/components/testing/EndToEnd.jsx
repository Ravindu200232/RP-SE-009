'use client'

import { Badge, Empty } from '../ui'

export default function EndToEnd({ qa }) {
  const e2e = qa?.report?.e2e
  if (!e2e || !Object.keys(e2e).length) {
    return <Empty>The end-to-end stage has no record for this project.</Empty>
  }
  const failures = e2e.failures || []
  const failed = e2e.failed ?? failures.length

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Badge tone={failed ? 'bad' : 'ok'}>
          {failed ? `${failed} failing` : 'passing'}
        </Badge>
        {e2e.flow && <span className="text-[12px] text-ink">{e2e.flow}</span>}
        {e2e.fixed ? <Badge>{e2e.fixed} repair round(s)</Badge> : null}
      </div>

      {!e2e.ran && <p className="mb-3 text-[11.5px] text-muted">The stage did not run.</p>}

      {failures.length > 0 && (
        <ul className="space-y-1.5">
          {failures.map((f, i) => (
            <li key={i} className="rounded-panel border border-line border-l-2
                                   border-l-bad bg-panel px-3 py-2 text-[11.5px]">
              <code className="font-mono text-ink">{f.target || f.file}</code>
              <span className="text-muted"> — {f.case || f.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
