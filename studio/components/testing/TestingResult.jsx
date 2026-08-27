'use client'

import { useEffect, useMemo, useState } from 'react'
import { Download, Loader2, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Badge, Button, Empty } from '../ui'
import { cn } from '@/lib/utils'
import Overview from './Overview'
import UnitTests from './UnitTests'
import Timeline from './Timeline'
import EndToEnd from './EndToEnd'
import Routes from './Routes'
import BugReports from './BugReports'
import Security from './Security'
import Performance from './Performance'
import Coder from './Coder'
import E2ELiveLanes from './E2ELiveLanes'
import { e2eStageSummary } from '@/lib/e2e-rate'
import { unitTestStatus } from '@/lib/test-counts'


const VIEWS = [
  { id: 'overview', label: 'Overview', C: Overview },
  { id: 'unit', label: 'Unit Testing', C: UnitTests },
  { id: 'timeline', label: 'Test Timeline', C: Timeline },
  { id: 'e2e', label: 'Integration', C: EndToEnd },
  { id: 'routes', label: 'API Contracts', C: Routes },
  { id: 'bugs', label: 'Bug Reports', C: BugReports },
  { id: 'security', label: 'Security', C: Security },
  { id: 'perf', label: 'Performance', C: Performance },
  { id: 'coder', label: 'Coder', C: Coder },
]

export default function TestingResult() {
  const project = useStore(s => s.project)
  const live = useStore(s => s.tests)
  const e2eLive = useStore(s => s.e2eParallel)
  const qa = useStore(s => s.qaReport)
  const setQa = useStore(s => s.setQaReport)
  const addLog = useStore(s => s.addLog)
  const [sub, setSub] = useState('overview')
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const [pdf, setPdf] = useState(false)

  async function downloadPdf() {
    setPdf(true)
    try {
      // Fetched rather than linked, so a failure arrives as a sentence in the
      // log instead of a page of JSON where the reader expected a document.
      const r = await fetch(api.qaPdfUrl(project))
      if (!r.ok) {
        let why = `HTTP ${r.status}`
        try { why = (await r.json()).error || why } catch { }
        throw new Error(why)
      }
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = `${project}-test-report.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      addLog('INFO', '📄 Test report downloaded')
    } catch (e) {
      addLog('WARN', `⚠ The test report could not be built — ${e.message}`)
    }
    setPdf(false)
  }

  async function load() {
    if (!project) return
    setState('loading')
    let last
    for (let i = 0; i < 4; i++) {
      try {
        setQa(await api.qa(project))
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
  useEffect(() => {
    if (!live.running && project) load()

  }, [live.running])

  const counts = useMemo(() => badges(qa), [qa])
  const View = (VIEWS.find(v => v.id === sub) || VIEWS[0]).C

  if (!project) return <Empty>Open a project to see its test results.</Empty>

  if (live.running) {
    if (e2eLive?.active || e2eLive?.lanes?.some(l => l.title)) {
      return <E2ELiveLanes />
    }
    return (
      <div className="grid h-full place-items-center p-8 text-center">
        <div>
          <div className="mx-auto mb-3 flex size-9 items-center justify-center
                          rounded-full border border-accent/30 bg-accent/10">
            <span className="size-2 animate-pulse rounded-full bg-accent" />
          </div>
          <p className="text-[13px] text-ink">The build is still running.</p>
          <p className="mx-auto mt-1.5 max-w-[380px] text-[11.5px] leading-relaxed text-muted">
            Unit tests and route checks appear here first. The view switches to
            four live browser lanes when the end-to-end stage starts.
          </p>
        </div>
      </div>
    )
  }

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
            {counts[v.id] != null && (
              <Badge tone={counts[v.id].bad ? 'bad' : 'ok'}>{counts[v.id].n}</Badge>
            )}
          </button>
        ))}
        <span className="flex-1" />
        {/* Rendered on demand, so it always matches what is on screen — the
            results keep moving while tests are repaired and re-run. */}
        <Button variant="outline" disabled={!project || state !== 'ready' || pdf}
                onClick={downloadPdf}
                title="Every tab in this report as a PDF — the summary, each test case, the timeline, the bugs, security, performance, and the test sources">
          {pdf ? <Loader2 className="size-3 animate-spin" />
               : <Download className="size-3" />} PDF
        </Button>
        {live.running
          ? <span className="flex items-center gap-1.5 font-mono text-[10px] text-ok">
              <span className="size-1.5 animate-pulse rounded-full bg-ok" /> running
            </span>
          : <Button variant="outline" onClick={load}>
              <RefreshCw className="size-3" /> Refresh
            </Button>}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {state === 'loading' && <Empty>Reading the results…</Empty>}
        {state === 'error' && <Empty bad>Could not read them — {error}</Empty>}
        {(state === 'ready' || state === 'idle') && <View qa={qa} live={live} />}
      </div>
    </div>
  )
}


function badges(qa) {
  const out = {}
  const r = qa?.report
  const v = qa?.vitest
  if (v) {
    const unit = unitTestStatus(v)
    out.unit = { n: `${unit.passed}/${unit.total}`,
                 bad: unit.failed > 0 }
  }
  if (r) {
    const bugs = r.suite?.unresolved?.length || 0
    out.bugs = { n: bugs, bad: bugs > 0 }
  }
  if (r?.e2e) {
    const e = e2eStageSummary(r.e2e)
    if (e.total) out.e2e = { n: `${e.passed}/${e.total}`, bad: e.passed !== e.total }
  }
  if (r?.security) {
    const sec = r.security.findings?.length || 0
    out.security = { n: sec, bad: sec > 0 }
  }
  if (qa?.history?.length) out.timeline = { n: qa.history.length, bad: false }
  return out
}


export const Summary = ({ children }) => (
  <div className="mb-4 flex flex-wrap items-center gap-5">{children}</div>
)

export function Stat({ n, label, tone }) {
  return (
    <span className="text-[11px] text-muted">
      <b className={cn('mr-1.5 font-display text-[20px] font-bold',
                       tone || 'text-ink')}>{n ?? '—'}</b>
      {label}
    </span>
  )
}
