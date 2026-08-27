'use client'

import { Badge, Empty, Panel, Table, Tag, TR, TH, TD } from '../ui'
import { cn } from '@/lib/utils'

const CHECKS = [
  ['UNGUARDED_ROUTE', 'API handlers that write without checking who is asking'],
  ['UNGUARDED_PAGE', 'a page under a role-gated section with no guard of its own'],
  ['EXPOSED_SECRET', 'a NEXT_PUBLIC_ variable holding something secret'],
  ['FAKE_HASH', 'passwords stored without hashing'],
  ['QUERY_INJECTION', 'user input reaching a query unchecked'],
  ['UNSAFE_HTML', 'dangerouslySetInnerHTML on something a user supplied'],
]

export default function Security({ qa }) {
  const sec = qa?.report?.security
  if (!sec) {
    return <Empty>The security stage has no record for this project.</Empty>
  }
  const findings = sec.findings || []
  const audit = sec.audit || {}
  const byCode = {}
  for (const f of findings) (byCode[f.code] ||= []).push(f)

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Badge tone={findings.length ? 'bad' : 'ok'}>
          {findings.length ? `${findings.length} finding(s)` : 'nothing found'}
        </Badge>
        <span className="font-mono text-[10px] text-muted">
          {Object.keys(audit).length
            ? 'npm audit: ' + Object.entries(audit).map(([k, n]) => `${n} ${k}`).join(', ')
            : 'no dependency advisories'}
        </span>
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
                       : f.severity === 'major' ? 'warn' : 'mute'}>
                {f.severity}
              </Tag>
              <b className="text-[12px] text-ink">{f.code}</b>
            </div>
            <p className="mb-1 font-mono text-[10.5px] text-muted">{f.path}</p>
            <p className="text-[11.5px] text-ink">{f.message}</p>
            {f.fix && <p className="mt-1 text-[10.5px] text-muted2">Fix: {f.fix}</p>}
          </Panel>
        ))}
      </div>
    </div>
  )
}
