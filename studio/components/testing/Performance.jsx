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
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        {Object.entries(p.scores).map(([k, n]) => (
          <div key={k}
               className={cn('min-w-[120px] rounded-2xl border bg-[#121622]/80 px-5 py-3.5 text-center shadow-xl backdrop-blur-xl transition-all duration-200 hover:border-white/20',
                 n >= 90 ? 'border-emerald-500/30' : n >= 50 ? 'border-amber-500/30' : 'border-rose-500/30')}>
            <div className={cn('font-display text-[28px] font-black leading-none tracking-tight',
              n >= 90 ? 'text-emerald-400' : n >= 50 ? 'text-amber-400' : 'text-rose-400')}>
              {n}
            </div>
            <div className="mt-1.5 text-[11px] font-medium capitalize text-slate-400">
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
