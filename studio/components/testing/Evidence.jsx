'use client'

/**
 * The verification ledger, exactly as the engine recorded it.
 *
 * Every other view here is an interpretation — a rate, a chart, a grouping.
 * This one is the raw claim: what the run promised to prove, which command or
 * journey proved it, and what is still unproved. When a number elsewhere looks
 * wrong, this is the page that says why.
 */

import { Badge, Empty, Panel, Table, Tag, TD, TH, TR } from '../ui'
import { cn } from '@/lib/utils'

const STATUS_TONE = {
  passed: 'ok',
  outdated: 'mute',
  failed: 'bad',
  interrupted: 'bad',
  running: 'mute',
}

export default function Evidence({ qa }) {
  const evidence = qa?.report?.evidence
  if (qa?.recovered) return (
    <div className="space-y-4">
      <Panel className="p-4"><Badge>Saved artifacts · partial evidence</Badge><p className="mt-3 text-[11.5px] text-muted">{qa.provenance}</p></Panel>
      <Table><thead><TR><TH>Evidence</TH><TH>Source</TH><TH>What was saved</TH></TR></thead><tbody>
        {qa.vitest && <TR><TD>Unit testing</TD><TD className="font-mono text-muted">{qa.vitest.source === 'vitest-cache' ? 'node_modules/.vite/vitest/results.json' : qa.vitest.source}</TD><TD>{qa.vitest.fileResults ? `${qa.vitest.fileResults.length} file outcomes; assertion details unavailable` : 'Vitest assertion report'}</TD></TR>}
        {(qa.report?.e2e?.recordedOutcomes || []).map((r, i) => <TR key={i}><TD>E2E · {r.suite}</TD><TD className="font-mono text-muted">{r.source}</TD><TD>{r.detail} · step trace unavailable</TD></TR>)}
        {(qa.screenshots || []).map(r => <TR key={r.path}><TD>Screenshot</TD><TD className="break-all font-mono text-muted">{r.path}</TD><TD>{r.width} × {r.height} · {r.status}</TD></TR>)}
      </tbody></Table>
      {qa.report?.unit?.coverage && <Panel className="p-4"><p className="text-[11px] text-muted">Saved source coverage · informational, no percentage requirement</p><p className="mt-2 text-[12px] text-ink">{Object.entries(qa.report.unit.coverage).filter(([, v]) => typeof v?.pct === 'number').map(([k, v]) => `${k}: ${v.pct}%`).join(' · ')}</p></Panel>}
    </div>
  )
  if (!evidence || !Object.keys(evidence).length) {
    return <Empty>This project has no verification ledger yet.</Empty>
  }

  const scope = evidence.scope
  const suites = evidence.suites || []
  const uncovered = evidence.missingRequirements || []
  const limitations = Object.entries(evidence.limitations || {})
  const unit = evidence.coverage?.unit
  const e2e = evidence.coverage?.e2e

  return (
    <div className="space-y-4">
      <Panel className="flex flex-wrap items-center gap-3 p-4">
        <Badge tone={evidence.ready ? 'ok' : 'bad'}>
          {evidence.ready ? 'every required layer proved' : 'evidence incomplete'}
        </Badge>
        <span className="text-[11px] text-muted">
          revision {evidence.revision} · requires {(evidence.requiredKinds || []).join(', ') || 'nothing'}
        </span>
        {evidence.scopeOpen && (
          <Badge tone="bad">scope still open</Badge>
        )}
      </Panel>

      <div className="grid gap-3 sm:grid-cols-2">
        <Panel className="p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted2">
            Unit source coverage
          </p>
          {unit ? (
            <>
              <p className={cn('mt-1 font-display text-[22px] font-semibold',
                unit.required === false ? 'text-muted' : unit.status === 'passed' ? 'text-ok' : 'text-bad')}>
                {unit.status === 'missing' ? 'no report' : unit.status}
              </p>
              <p className="mt-1 text-[11px] text-muted">
                {unit.required === false ? 'Informational · no percentage requirement' : `floor ${unit.target}%`}
                {unit.metrics && ' · ' + Object.entries(unit.metrics)
                  .map(([name, m]) => `${name} ${m.pct}%`).join(', ')}
              </p>
              {(unit.failures || []).map((why, i) => (
                <p key={i} className="mt-1 text-[11px] text-bad">{why}</p>
              ))}
            </>
          ) : <Empty>Not measured.</Empty>}
        </Panel>

        <Panel className="p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted2">
            Requirement coverage (E2E)
          </p>
          {e2e ? (
            <>
              <p className={cn('mt-1 font-display text-[22px] font-semibold',
                e2e.status === 'passed' ? 'text-ok' : 'text-bad')}>
                {e2e.covered}/{e2e.total}
              </p>
              <p className="mt-1 text-[11px] text-muted">
                {e2e.percent}% covered · floor {e2e.target}%
              </p>
            </>
          ) : <Empty>Not measured.</Empty>}
        </Panel>
      </div>

      {scope?.requirements?.length > 0 && (
        <section>
          <h3 className="mb-1 text-[12px] font-semibold text-ink">
            What this run promised to prove
          </h3>
          <p className="mb-2 text-[10.5px] text-muted2">
            Sealed before the tests ran, so the scope cannot be narrowed once a
            flow turns out to be hard.
          </p>
          <Table>
            <thead><TR><TH>id</TH><TH>behaviour</TH><TH>evidence needed</TH></TR></thead>
            <tbody>
              {scope.requirements.map(req => {
                const open = uncovered.filter(u => u.id === req.id).map(u => u.kind)
                return (
                  <TR key={req.id} className={open.length ? 'bg-bad/[0.06]' : ''}>
                    <TD><code className="font-mono text-ink">{req.id}</code></TD>
                    <TD className="text-muted">{req.description}</TD>
                    <TD>
                      <span className="flex flex-wrap gap-1">
                        {req.evidence.map(kind => (
                          <Tag key={kind} tone={open.includes(kind) ? 'bad' : 'mute'}>
                            {kind}
                          </Tag>
                        ))}
                      </span>
                    </TD>
                  </TR>
                )
              })}
            </tbody>
          </Table>
        </section>
      )}

      {suites.length > 0 && (
        <section>
          <h3 className="mb-1 text-[12px] font-semibold text-ink">What actually ran</h3>
          <p className="mb-2 text-[10.5px] text-muted2">
            Command exit status and browser journey outcomes. A pass recorded
            before the last edit shows as <b>outdated</b>, not as missing.
          </p>
          <Table>
            <thead>
              <TR><TH>layer</TH><TH>suite</TH><TH>result</TH><TH>command</TH><TH>covers</TH></TR>
            </thead>
            <tbody>
              {suites.map((s, i) => (
                <TR key={`${s.kind}-${s.suite}-${i}`}>
                  <TD><Tag>{s.kind}</Tag></TD>
                  <TD className="text-ink">{s.suite}</TD>
                  <TD>
                    <Badge tone={STATUS_TONE[s.status] || 'mute'}>{s.status}</Badge>
                    {s.exitCode != null && (
                      <span className="ml-1.5 font-mono text-[10px] text-muted2">
                        exit {s.exitCode}
                      </span>
                    )}
                  </TD>
                  <TD className="max-w-[280px] truncate font-mono text-[10px] text-muted"
                      title={s.command}>
                    {s.command}
                  </TD>
                  <TD className="font-mono text-[10px] text-muted2">
                    {(s.covers || []).join(', ') || '—'}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
          {suites.filter(s => s.reason).map((s, i) => (
            <Panel key={i} className="mt-2 border-l-2 border-l-bad p-3">
              <p className="text-[11.5px] font-medium text-ink">{s.kind} / {s.suite}</p>
              <p className="mt-0.5 text-[11px] text-muted">{s.reason}</p>
            </Panel>
          ))}
        </section>
      )}

      {(evidence.visuals || []).length > 0 && (
        <section>
          <h3 className="mb-2 text-[12px] font-semibold text-ink">Screens reviewed</h3>
          <Table>
            <thead><TR><TH>view</TH><TH>width</TH><TH>result</TH><TH>findings</TH></TR></thead>
            <tbody>
              {evidence.visuals.map((v, i) => (
                <TR key={i}>
                  <TD className="text-ink">{v.view}</TD>
                  <TD className="font-mono text-[10.5px] text-muted">{v.width}px</TD>
                  <TD><Badge tone={STATUS_TONE[v.status] || 'mute'}>{v.status}</Badge></TD>
                  <TD className="text-muted">{v.findings}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </section>
      )}

      {limitations.length > 0 && (
        <section>
          <h3 className="mb-1 text-[12px] font-semibold text-ink">Recorded as unverified</h3>
          <p className="mb-2 text-[10.5px] text-muted2">
            Not passes. These are the things the run could not prove here, with
            the reason it gave.
          </p>
          <div className="space-y-2">
            {limitations.map(([kind, why]) => (
              <Panel key={kind} className="border-l-2 border-l-warn p-3">
                <Tag tone="bad">{kind}</Tag>
                <p className="mt-1 text-[11.5px] text-ink">{why}</p>
              </Panel>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
