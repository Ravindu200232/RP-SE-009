'use client'

import { Badge, Empty, Panel } from '../ui'

const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const severityTone = value => {
  const level = String(value || '').toLowerCase()
  if (level.includes('high') || level.includes('critical')) return 'bad'
  if (level.includes('medium') || level.includes('low')) return 'warn'
  return 'mute'
}

export default function Security({ qa }) {
  const security = qa?.security || qa?.report?.security
  if (!security) return <Empty>No security scan evidence has been saved for this project.</Empty>
  const zap = security.zap || {}
  const findings = [...(security.findings || []), ...(zap.findings || [])]
  const counts = zap.counts || {}
  const high = number(counts.high) || findings.filter(item => /high|critical/i.test(String(item.severity || item.risk))).length
  const medium = number(counts.medium) || findings.filter(item => /medium/i.test(String(item.severity || item.risk))).length
  const low = number(counts.low) || findings.filter(item => /low/i.test(String(item.severity || item.risk))).length
  const informational = number(counts.informational) || findings.filter(item => /informational/i.test(String(item.severity || item.risk))).length
  const needsAttention = high > 0 || medium > 0 || low > 0

  return <div className="space-y-3">
    <Panel className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-ink">Security baseline</h3>
        <Badge tone={zap.status === 'passed' ? 'ok' : zap.status === 'failed' ? 'bad' : 'warn'}>{zap.status === 'passed' ? 'baseline completed' : zap.status || 'not run'}</Badge>
        {needsAttention && <Badge tone="warn">action needed</Badge>}
      </div>

      <Table>
        <thead>
          <TR><TH>check</TH><TH>what it looks for</TH><TH>result</TH></TR>
        </thead>
        <tbody>
          {CHECKS.map(([code, what]) => {
            const hits = byCode[code] || []
            return (
              <TR key={code} className={hits.length ? 'bg-bad/[0.06]' : ''}>
                <TD><code className="font-mono text-ink">{code}</code></TD>
                <TD className="text-muted">{what}</TD>
                <TD>
                  {hits.length ? <Badge tone="bad">{hits.length}</Badge>
                               : <Badge tone="ok">clean</Badge>}
                </TD>
              </TR>
            )
          })}
        </tbody>
      </Table>

      <div className="mt-3 space-y-2">
        {findings.map((f, i) => (
          <Panel key={i} className="border-l-2 border-l-bad p-3.5">
            <div className="mb-1.5 flex items-center gap-2">
              <Tag tone={f.severity === 'blocker' ? 'bad'
                       : f.severity === 'major' ? 'warn' : 'bad'}>
                {f.severity || 'security'}
              </Tag>
              <b className="text-[12px] text-ink">{f.code}</b>
            </div>
            <p className="mb-1 font-mono text-[10.5px] text-muted">
              {f.file || f.path}{f.line ? `:${f.line}` : ''}
            </p>
            <p className="text-[11.5px] text-ink">{f.what || f.message}</p>
            {f.detail && f.detail !== f.what && (
              <code className="mt-1 block font-mono text-[10.5px] text-muted rounded bg-panel2/60 px-2 py-1 overflow-x-auto">
                {f.detail}
              </code>
            )}
            {f.fix && <p className="mt-1 text-[10.5px] text-muted">Fix: {f.fix}</p>}
          </Panel>
        ))}
      </div>
      <p className="mt-4 text-xs text-muted">{zap.reason || 'The scan is counted only when a local-server report was saved.'}</p>
      {zap.activeScan === false && <p className="mt-2 text-xs text-amber-700">Scope: passive baseline only. No active attack scan was run, so this is not a full security sign-off.</p>}
      {zap.report && <p className="mt-2 break-all font-mono text-[11px] text-muted">Saved report: {zap.report}</p>}
    </Panel>

    {security.audit && <Panel className="p-4"><h3 className="text-sm font-semibold text-ink">Dependency audit</h3>
      <p className="mt-2 text-xs text-muted">{security.audit.summary || 'A dependency audit result was recorded.'}</p></Panel>}

    {findings.map((item, index) => <Panel key={`${item.name || item.code || item.title}-${index}`} className="p-4">
      <div className="flex flex-wrap gap-2"><Badge tone={severityTone(item.severity || item.risk)}>{item.severity || item.risk || 'finding'}</Badge><b className="text-xs text-ink">{item.name || item.code || item.title}</b></div>
      <p className="mt-2 text-xs text-muted">{item.what || item.description || item.detail}</p>
    </Panel>)}
    {!findings.length && <p className="text-xs text-muted">No findings are recorded. This is not proof of a clean scan unless the baseline completed successfully.</p>}
  </div>
}
