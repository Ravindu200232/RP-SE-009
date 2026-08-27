'use client'

import { useState } from 'react'
import { Empty, Tag } from '../ui'
import { cn } from '@/lib/utils'


export default function Coder({ qa }) {
  const tests = qa?.tests || {}
  const names = Object.keys(tests).sort()
  const [sel, setSel] = useState(null)

  if (!names.length) {
    return <Empty>No test files on disk for this project.</Empty>
  }
  const current = sel && tests[sel] ? sel : names[0]

  return (
    <div className="flex h-full min-h-[420px] gap-3">
      <aside className="w-[240px] shrink-0 overflow-y-auto border-r border-line pr-1">
        {names.map(n => (
          <button key={n} onClick={() => setSel(n)}
                  className={cn('block w-full rounded-ctl px-2 py-1.5 text-left',
                    'transition-colors',
                    n === current ? 'bg-accent/12' : 'hover:bg-panel2')}>
            <span className={cn('block truncate font-mono text-[11px]',
                                n === current ? 'text-accent' : 'text-ink')}>
              {n.split('/').pop()}
            </span>
            <span className="block truncate text-[9px] text-muted2">
              {n.replace(/\/[^/]+$/, '')}
            </span>
            {n.includes('/quarantine/') && <Tag tone="bad">set aside</Tag>}
          </button>
        ))}
      </aside>

      <pre className="min-w-0 flex-1 overflow-auto rounded-panel bg-code p-3.5
                      font-mono text-[11px] leading-[1.7] text-ink">
        {tests[current]}
      </pre>
    </div>
  )
}
