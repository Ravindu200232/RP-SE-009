'use client'

import { Empty, Panel } from '../ui'
import { Stat } from './TestingResult'
import { cn } from '@/lib/utils'
import { e2eStageSummary } from '@/lib/e2e-rate'
import { unitTestStatus } from '@/lib/test-counts'

export default function Overview({ qa, live }) {
  const last = (qa?.history || []).slice(-1)[0]
  const r = qa?.report
  const v = qa?.vitest || qa?.savedVitest
  if (!last && !r && !v) {
    return <Empty>Nothing has been recorded for this project yet.</Empty>
  }
  // A record is written as each stage finishes, so what is on screen can be a
  // verification that is still running — or one that was stopped part way. The
  // numbers are real either way; what they do not yet cover is worth saying.
  const partial = qa && qa.complete === false
  const ran = qa?.stages || []

  const perf = qa?.performance?.scores || {}
  const sec = r?.security?.findings || []
  const unresolved = r?.suite?.unresolved || []
  const e2e = e2eStageSummary(r?.e2e)
  const unit = unitTestStatus(v)
  const unitTotal = Number(unit?.total || 0)
  const unitPassed = Number(unit?.passed || 0)
  const unitRate = unitTotal ? Math.round(unitPassed * 100 / unitTotal) : 0
  const history = (qa?.history || []).filter(x => Number.isFinite(Number(x?.rate)))
  const roundAverage = history.length ? Math.round(history.reduce((sum, x) => sum + Number(x.rate || 0), 0) / history.length) : null

  return (
    <div className="space-y-3">
      {partial && (
        <p className="rounded-panel border border-accent/30 bg-accent/5 px-3 py-2 text-[11px] text-muted">
          <b className="text-ink">{live?.running ? 'Verification in progress.' : 'Partial saved report.'}</b>{' '}
          {ran.length
            ? `${ran.join(' and ')} ${ran.length === 1 ? 'has' : 'have'} run so far.`
            : 'No stage has finished yet.'}{' '}
          Only saved evidence is shown below.
        </p>
      )}

    <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(290px,1fr))]">
      <Card title="Saved verification" hint="results already recorded for this project">
        <p className="text-[12px] text-ink">{qa.complete ? 'Verification finished' : live?.running ? 'Verification in progress' : 'Partial saved report'}</p>
        <p className="mt-2 text-[11px] text-muted">{qa.provenance || 'Results are saved as each check finishes.'}</p>
        <div className="mt-3 flex flex-wrap gap-4"><Stat n={qa.timeline?.length || qa.history?.length || 0} label="timeline entries" /><Stat n={qa.screenshots?.length || 0} label="screenshots" /></div>
      </Card>

      {/* "as it stands", not "the last full run": a feature's stage only runs
          the tests for what it changed, and those results are merged into this
          report rather than replacing it — so this is the whole suite, with
          the files that were just re-run showing their new result. */}
      <Card title="The suite now" hint="every test file, at its latest result">
        {qa.unitEvidenceStatus === 'outdated' && <p className="mb-2 text-[11px] text-warn">Saved results precede the latest code changes.</p>}
        {v ? (
          <div className="flex flex-col gap-1.5">
            <div className="mb-2 flex items-center gap-3">
              <div className="grid size-16 place-items-center rounded-full p-[6px] shadow-[0_8px_20px_rgba(15,23,42,.12)]"
                   style={{ background: `conic-gradient(var(--ok) 0deg ${unitRate * 3.6}deg, var(--line) ${unitRate * 3.6}deg 360deg)` }}>
                <div className="grid size-full place-items-center rounded-full bg-panel"><b className={cn('font-display text-[17px]', unitRate === 100 ? 'text-ok' : unitRate >= 80 ? 'text-warn' : 'text-bad')}>{unitRate}%</b></div>
              </div>
              <div className="text-[10.5px] leading-relaxed text-muted">
                <b className="text-ink">{unit.unit === 'files' ? 'Saved file pass rate' : 'Recorded test pass rate'}</b>
                {roundAverage != null && <><br />Round-one average: <b className="text-ink">{roundAverage}%</b> across {history.length} run{history.length === 1 ? '' : 's'}</>}
              </div>
            </div>
            <Stat n={unit.passed} label={unit.unit === 'files' ? 'files passing' : 'cases passing'} tone="text-ok" />
            <Stat n={unit.failed} label={unit.unit === 'files' ? 'files failing' : 'cases failing'}
                  tone={unit.failed ? 'text-bad' : undefined} />
            <Stat n={unit.files} label="files" />
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


      <Card title="End-to-end proof" hint="all final browser journey stages, not repair retries">
        {e2e.total ? (
          <div className="flex items-center gap-4">
            <div className="relative grid size-20 place-items-center rounded-full p-2 shadow-[0_9px_20px_rgba(15,23,42,.14)]"
                 style={{ background: `conic-gradient(var(--ok) 0deg ${e2e.rate * 3.6}deg, var(--line) ${e2e.rate * 3.6}deg 360deg)` }}>
              <div className="grid size-full place-items-center rounded-full bg-panel">
                <b className={cn('font-display text-[21px]', e2e.rate === 100 ? 'text-ok' : e2e.rate >= 80 ? 'text-warn' : 'text-bad')}>{e2e.rate}%</b>
              </div>
            </div>
            <div>
              <Stat n={`${e2e.passed}/${e2e.total}`} label="stages passed" tone={e2e.passed === e2e.total ? 'text-ok' : 'text-warn'} />
              <p className="mt-1 text-[10.5px] text-muted">{e2e.failed} failed · {e2e.notReached} not reached</p>
            </div>
          </div>
        ) : <Empty>No saved step trace. {r?.e2e?.recordedOutcomes?.length || 0} historical journey outcome(s) available in Integration (E2E).</Empty>}
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
          ) : <p className="text-[11.5px] text-ok">No unresolved failures recorded.</p>
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
        {ran.includes('runtime') ? (
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
