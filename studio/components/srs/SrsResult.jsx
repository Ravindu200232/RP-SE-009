'use client'

import { useEffect, useState } from 'react'
import { FileDown, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Badge, Button, Empty } from '../ui'
import { cn } from '@/lib/utils'
import { VIEWS, badgeFor } from './views'


export default function SrsResult() {
  const project = useStore(s => s.project)
  const [srs, setSrs] = useState(null)
  const [sub, setSub] = useState('document')
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')

  async function load() {
    if (!project) return
    setState('loading')
    let last
    for (let i = 0; i < 4; i++) {
      try {
        setSrs(await api.srsResults(project))
        setState('ready')
        return
      } catch (e) {
        last = e
        await new Promise(r => setTimeout(r, 700))
      }
    }
    setError(last?.message || 'unknown error')
    setState('error')
  }

  useEffect(() => { load()  }, [project])

  if (!project) return <Empty>Open a project to see the SRS it was built from.</Empty>

  const have = srs?.have || {}
  const anything = Object.values(have).some(Boolean)
  const View = (VIEWS.find(v => v.id === sub) || VIEWS[0]).C

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-1 border-b
                      border-line bg-panel px-3 py-2">
        {VIEWS.map(v => (
          <button key={v.id} onClick={() => setSub(v.id)}
                  className={cn('flex items-center gap-1.5 rounded-ctl px-3 py-1.5',
                    'text-[11.5px] font-medium transition-colors',
                    sub === v.id ? 'bg-accent/12 text-accent'
                                 : 'text-muted hover:bg-panel2 hover:text-ink')}>
            {v.label}
            {badgeFor(v.id, srs) != null && (
              <Badge tone={badgeFor(v.id, srs).bad ? 'warn' : 'mute'}>
                {badgeFor(v.id, srs).n}
              </Badge>
            )}
          </button>
        ))}
        <span className="flex-1" />
        {have.pdf && (
          <a href={api.srsPdfUrl(project)} target="_blank" rel="noreferrer"
             className="flex items-center gap-1.5 rounded-ctl border border-line
                        px-2.5 py-1 text-[11px] text-muted hover:text-ink">
            <FileDown className="size-3" /> PDF
          </a>
        )}
        <Button variant="outline" onClick={load}>
          <RefreshCw className="size-3" /> Refresh
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {state === 'loading' && <Empty>Reading the SRS…</Empty>}
        {state === 'error' && <Empty bad>Could not read it — {error}</Empty>}
        {state === 'ready' && !anything && (
          <Empty>
            This project has no SRS. It was built straight from a prompt —
            start one with “Plan it first” on the home screen.
          </Empty>
        )}
        {state === 'ready' && anything && <View srs={srs} />}
      </div>
    </div>
  )
}
