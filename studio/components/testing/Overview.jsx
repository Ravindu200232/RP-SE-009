'use client'

import { Empty, Panel } from '../ui'
import { Stat } from './TestingResult'
import { cn } from '@/lib/utils'

export default function Overview({ qa, live }) {
  const last = (qa?.history || []).slice(-1)[0]
  const r = qa?.report
  const v = qa?.vitest
  if (!last && !r && !v) {
    return <Empty>Nothing has been recorded for this project yet.</Empty>
  }

  const perf = qa?.performance?.scores || {}
  const sec = r?.security?.findings || []
  const unresolved = r?.suite?.unresolved || []

  return (
    <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(290px,1fr))]">
      <Card title="Round one" hint="what the generated tests did before any repair">
        {last ? (
          <>
            <div className={cn('font-display text-[34px] font-bold leading-none',
              last.rate < last.floor ? 'text-bad' : 'text-ok')}>
              {last.rate}%
            </div>
            <div className="mt-1.5 text-[11px] text-muted">
              {last.passed}/{last.cases} passing · floor {last.floor}%
              {last.rate < last.floor && <b className="text-bad"> — below the floor</b>}
            </div>
            {(last.top || []).length > 0 && (
              <ul className="mt-2.5 space-y-1 text-[11px] text-muted">
                {last.top.map((t, i) => (
                  <li key={i}>
                    <b className="font-mono text-ink">{t.count}</b> × {t.class}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : <Empty>No round-one record.</Empty>}
      </Card>

      <Card title="The suite now" hint="the last full run">
        {v ? (
          <div className="flex flex-col gap-1.5">
            <Stat n={v.numPassedTests} label="passing" tone="text-ok" />
            <Stat n={v.numFailedTests} label="failing"
                  tone={v.numFailedTests ? 'text-bad' : undefined} />
            <Stat n={(v.testResults || []).length} label="files" />
            {r?.unit?.deleted ? (
              <p className="mt-1 text-[11px] text-bad">
                <b>{r.unit.deleted}</b> case(s) that existed when the stage
                started are gone from the suite — this is not 100%.
              </p>
            ) : null}
            {r?.unit?.skipped ? (
              <p className="mt-1 text-[11px] text-warn">
                <b>{r.unit.skipped}</b> case(s) are marked <code>it.skip</code>{' '}
                and never ran.
              </p>
            ) : null}
          </div>
        ) : <Empty>The suite has not run.</Empty>}
      </Card>

      <Card title="Left unresolved" hint="cases repair could not make pass">
        {r ? (
          unresolved.length ? (
            <ul className="space-y-1.5 text-[11px] text-muted">
              {unresolved.slice(0, 6).map((u, i) => (
                <li key={i}>
                  <code className="font-mono text-ink">{shortFile(u.file)}</code>
                  {' — '}{u.case}
                  {u.diagnosis && (
                    <span className="ml-1 rounded bg-line px-1.5 py-px text-[9px]">
                      {u.diagnosis}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : <p className="text-[11.5px] text-ok">None. Nothing was set aside.</p>
        ) : <Empty>No report — this project was built before results were kept.</Empty>}
      </Card>

      <Card title="Security" hint="six checks over the generated source">
        {r?.security ? (
          sec.length ? (
            <ul className="space-y-1.5 text-[11px] text-muted">
              {sec.slice(0, 6).map((f, i) => (
                <li key={i} className="flex items-center gap-1.5">
                  <span className={cn('rounded px-1.5 py-px text-[8.5px] font-bold uppercase',
                    f.severity === 'blocker' ? 'bg-bad/20 text-bad'
                      : f.severity === 'major' ? 'bg-warn/20 text-warn'
                      : 'bg-line text-muted2')}>
                    {f.severity}
                  </span>
                  <code className="truncate font-mono text-ink">{f.path}</code>
                </li>
              ))}
            </ul>
          ) : <p className="text-[11.5px] text-ok">Nothing found.</p>
        ) : <Empty>The security stage has no record here.</Empty>}
      </Card>

      <Card title="Performance" hint="Lighthouse, against the dev server">
        {Object.keys(perf).length ? (
          <div className="flex flex-col gap-1.5">
            {Object.entries(perf).map(([k, n]) => (
              <Stat key={k} n={n} label={k.replace(/-/g, ' ')}
                    tone={n >= 90 ? 'text-ok' : n >= 50 ? 'text-warn' : 'text-bad'} />
            ))}
          </div>
        ) : <Empty>Lighthouse has not run.</Empty>}
      </Card>

      <Card title="Runtime" hint="what the browser probe saw">
        {r ? (
          (r.runtime || []).length ? (
            <ul className="space-y-1 text-[11px] text-bad">
              {r.runtime.slice(0, 6).map((e, i) => (
                <li key={i} className="truncate">{String(e).split('\n')[0]}</li>
              ))}
            </ul>
          ) : <p className="text-[11.5px] text-ok">No runtime errors.</p>
        ) : <Empty>No record.</Empty>}
      </Card>
    </div>
  )
}

const Card = ({ title, hint, children }) => (
  <Panel className="p-4">
    <h3 className="text-[12px] font-semibold text-ink">{title}</h3>
    {hint && <p className="mb-3 mt-0.5 text-[10px] text-muted2">{hint}</p>}
    {children}
  </Panel>
)

const shortFile = (p) => String(p || '').split('/').pop()
