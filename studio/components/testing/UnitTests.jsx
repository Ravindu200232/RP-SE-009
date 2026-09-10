'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge, Empty } from '../ui'
import { Summary, Stat } from './TestingResult'
import { cn } from '@/lib/utils'
import { unitTestStatus } from '@/lib/test-counts'


export default function UnitTests({ qa }) {
  const [open, setOpen] = useState(() => new Set())

  const v = qa?.vitest || qa?.savedVitest
  if (!v) {
    return <Empty>No saved unit-test report for this project yet.</Empty>
  }

  const suites = (v.testResults || []).map(t => ({
    file: shortPath(t.name),
    cases: t.assertionResults || [],
  })).sort((a, b) => {
    const af = a.cases.some(c => c.status === 'failed')
    const bf = b.cases.some(c => c.status === 'failed')
    return (bf - af) || a.file.localeCompare(b.file)
  })

  const skipped = suites.flatMap(s => s.cases)
    .filter(c => ['skipped', 'pending', 'todo'].includes(c.status))
  const unit = unitTestStatus(v)

  if (v.fileResults) return (
    <div className="space-y-4">
      <Summary><Stat n={`${unit.passed}/${unit.total}`} label="files passed" tone="text-ok" />
        <Stat n={unit.failed} label="files failed" tone={unit.failed ? 'text-bad' : undefined} /></Summary>
      <p className="text-[11.5px] text-muted">{v.note}</p>
      <p className="font-mono text-[10px] text-muted2">Vitest cache · {new Date(v.recordedAt).toLocaleString()}</p>
      <div className="space-y-1.5">{v.fileResults.map(row => (
        <div key={row.file} className="flex items-center gap-3 rounded-panel border border-line bg-panel px-3 py-2.5">
          <code className="min-w-0 flex-1 break-all text-[11px] text-ink">{row.file}</code>
          <span className="text-[10px] text-muted">{row.duration == null ? '—' : `${Math.round(row.duration)}ms`}</span>
          <Badge tone={row.status === 'failed' ? 'bad' : 'ok'}>{row.status}</Badge>
        </div>
      ))}</div>
    </div>
  )

  return (
    <div>
      {qa.unitEvidenceStatus === 'outdated' && <p className="mb-3 text-[11px] text-warn">These saved unit results precede the latest code changes.</p>}
      {/* The last run tested what the last request changed. The suite is
          everything proved so far, and this says how much of it is not from
          the run that just finished. */}
      {v.carriedForward > 0 && (
        <p className="mb-3 text-[11px] text-muted">
          {v.carriedForward} of these {unit.files} files last ran in an earlier
          verification — the newest run covered the rest.
        </p>
      )}
      <Summary>
        <Stat n={unit.passed} label="passing" tone="text-ok" />
        <Stat n={unit.failed} label="failing"
              tone={unit.failed ? 'text-bad' : undefined} />
        {skipped.length > 0 && (
          <Stat n={skipped.length} label="never ran" tone="text-warn" />
        )}
        <Stat n={unit.files} label="files" />
        <span className="ml-auto font-mono text-[10px] text-muted2">
          {v.startTime ? new Date(v.startTime).toLocaleString() : ''}
        </span>
      </Summary>
      {!suites.length && <p className="mb-4 text-[11.5px] text-muted">Saved runner totals. Individual assertion details were not saved.</p>}

      {skipped.length > 0 && (
        <p className="mb-3 text-[11.5px] text-warn">
          {skipped.length} case(s) are marked <code>it.skip</code> and never ran.
          They are not passing.
        </p>
      )}

      {qa?.report?.unit?.deleted ? (
        <p className="mb-3 rounded-ctl border border-bad/30 bg-bad/[0.06] px-3 py-2
                      text-[11.5px] text-bad">
          {qa.report.unit.deleted} case(s) present when the stage started are no
          longer in the suite. The numbers above are over what is left.
        </p>
      ) : null}

      <div className="space-y-1.5">
        {suites.map(s => {
          const failed = s.cases.filter(c => c.status === 'failed').length
          const isOpen = open.has(s.file) || failed > 0
          const passed = s.cases.filter(c => c.status === 'passed').length
          return (
            <section key={s.file}
                     className="overflow-hidden rounded-panel border border-line">
              <button onClick={() => {
                        const next = new Set(open)
                        next.has(s.file) ? next.delete(s.file) : next.add(s.file)
                        setOpen(next)
                      }}
                      className="flex w-full items-center gap-2.5 bg-panel px-3 py-2
                                 text-left transition-colors hover:bg-panel2">
                {isOpen ? <ChevronDown className="size-3 text-muted2" />
                        : <ChevronRight className="size-3 text-muted2" />}
                <span className={cn('size-[6px] rounded-full',
                                    failed ? 'bg-bad' : 'bg-ok')} />
                <span className="flex-1 truncate font-mono text-[11px] text-ink">
                  {s.file}
                </span>
                <Badge tone={failed ? 'bad' : 'mute'}>
                  {passed}/{s.cases.length}
                </Badge>
              </button>
              {isOpen && (
                <ul>
                  {s.cases.map((c, i) => (
                    <li key={i} className="flex flex-wrap items-center gap-2.5
                                           border-t border-line py-1.5 pl-8 pr-3
                                           text-[11.5px]">
                      <span className="flex-1 text-ink">{c.title || c.fullName}</span>
                      <span className={cn('font-mono text-[9px] font-bold uppercase',
                                          TONE[c.status] || 'text-muted2')}>
                        {LABEL[c.status] || c.status}
                      </span>
                      {c.duration != null && (
                        <span className="font-mono text-[9px] text-muted2">
                          {Math.round(c.duration)}ms
                        </span>
                      )}
                      {c.status === 'failed' && (c.failureMessages || []).length > 0 && (
                        <pre className="mt-1.5 w-full overflow-x-auto whitespace-pre-wrap
                                        rounded-ctl bg-bad/[0.08] p-2.5 font-mono
                                        text-[10px] leading-relaxed text-bad">
                          {firstLines(c.failureMessages[0])}
                        </pre>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}


const LABEL = { passed: 'pass', failed: 'fail', pass: 'pass', fail: 'fail',
                warn: 'warn', skipped: 'skipped', pending: 'skipped', todo: 'todo' }
const TONE = { passed: 'text-ok', pass: 'text-ok', failed: 'text-bad',
               fail: 'text-bad', warn: 'text-warn', skipped: 'text-warn',
               pending: 'text-warn' }


const shortPath = (p) => String(p || '').replace(/\\/g, '/').split('/tests/').pop()
const firstLines = (m) => String(m || '').split('\n').slice(0, 6).join('\n')
