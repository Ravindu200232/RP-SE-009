'use client'

import { Empty, Table, TR, TH, TD } from '../ui'
import { cn } from '@/lib/utils'

export default function Performance({ qa }) {
  const p = qa?.performance
  if (!p || !Object.keys(p.scores || {}).length) {
    return <Empty>Lighthouse has not run for this project.</Empty>
  }
  if (p.runtimeError) {
    return <Empty bad>Lighthouse could not measure this app — {p.runtimeError}</Empty>
  }
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-3">
        {Object.entries(p.scores).map(([k, n]) => (
          <div key={k}
               className={cn('min-w-[110px] rounded-panel border-2 px-4 py-3 text-center',
                 n >= 90 ? 'border-ok/50' : n >= 50 ? 'border-warn/50' : 'border-bad/50')}>
            <div className={cn('font-display text-[26px] font-bold leading-none',
              n >= 90 ? 'text-ok' : n >= 50 ? 'text-warn' : 'text-bad')}>
              {n}
            </div>
            <div className="mt-1 text-[9.5px] capitalize text-muted2">
              {k.replace(/-/g, ' ')}
            </div>
          </div>
        ))}
      </div>

      {Object.keys(p.metrics || {}).length > 0 && (
        <Table>
          <thead><TR><TH>metric</TH><TH>value</TH></TR></thead>
          <tbody>
            {Object.entries(p.metrics).map(([k, v]) => (
              <TR key={k}>
                <TD className="capitalize text-muted">{k.replace(/-/g, ' ')}</TD>
                <TD><b className="font-mono text-ink">{v}</b></TD>
              </TR>
            ))}
          </tbody>
        </Table>
      )}

      <p className="mt-3 text-[10.5px] text-muted2">
        Measured against the development server, which compiles each route on
        first request. The performance score is not a production figure.
        {p.fetchTime && ` Run at ${new Date(p.fetchTime).toLocaleString()}.`}
      </p>
    </div>
  )
}
