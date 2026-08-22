'use client'

import { useState } from 'react'
import { Badge, Empty, Panel, Table, TD, TH, TR } from '../ui'
import { Summary, Stat } from '../testing/TestingResult'
import { cn } from '@/lib/utils'


const list = (value) => Array.isArray(value) ? value : []


function line(item) {
  if (typeof item === 'string') return item
  if (!item || typeof item !== 'object') return String(item ?? '')
  const text = item.requirement || item.description || item.criterion
    || item.risk || item.rule || item.text || item.page_name
    || item.role_name || item.name || item.title

  return text || JSON.stringify(item)
}

const idOf = (item, i) =>
  (item && typeof item === 'object'
    && (item.id || item.ref || item.module || item.category || item.area)) || `#${i + 1}`

function Section({ title, children, count }) {
  return (
    <div className="mb-6">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="font-display text-[13px] font-bold text-ink">{title}</h3>
        {count != null && <Badge tone="mute">{count}</Badge>}
      </div>
      {children}
    </div>
  )
}

function Bullets({ items, tone }) {
  if (!list(items).length) return <p className="text-[11.5px] text-muted2">None recorded.</p>
  return (
    <ul className="space-y-1.5">
      {list(items).map((item, i) => (
        <li key={i} className="flex gap-2 text-[11.5px] leading-relaxed text-ink">
          <span className={cn('shrink-0 font-mono text-[10px]', tone || 'text-muted2')}>
            {idOf(item, i)}
          </span>
          <span>{line(item)}</span>
        </li>
      ))}
    </ul>
  )
}


export function Document({ srs }) {
  const doc = srs.document || {}
  if (!srs.have?.document) return <Empty>No SRS document was adopted for this project.</Empty>

  const summary = doc.app_summary
  const isText = typeof summary === 'string'
  const blurb = isText ? summary : (summary?.short_description || '')
  const goal = isText ? '' : (summary?.business_goal || '')
  const title = doc.document_title || (isText ? '' : summary?.app_name)
    || doc.project_name || 'Untitled'
  return (
    <>
      <Summary>
        <Stat n={list(doc.functional_requirements).length} label="requirements" />
        <Stat n={list(doc.roles).length} label="roles" />
        <Stat n={list(doc.main_modules).length} label="modules" />
        <Stat n={list(doc.database_design?.tables).length} label="tables" />
        <Stat n={list(doc.ambiguities).length} label="ambiguities"
              tone={list(doc.ambiguities).length ? 'text-warn' : undefined} />
      </Summary>

      <Panel className="mb-6 p-4">
        <p className="mb-1 font-display text-[15px] font-bold text-ink">{title}</p>
        <p className="text-[11.5px] leading-relaxed text-muted">{blurb}</p>
        {goal && (
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted2">
            Goal: {goal}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {doc.system_category && <Badge tone="mute">{doc.system_category}</Badge>}
          {doc.version && <Badge tone="mute">v{doc.version}</Badge>}
          {doc.document_language && <Badge tone="mute">{doc.document_language}</Badge>}
          {doc.authentication_requirement && <Badge tone="mute">auth</Badge>}
        </div>
      </Panel>

      <Section title="Main modules" count={list(doc.main_modules).length}>
        <Bullets items={doc.main_modules} />
      </Section>
      <Section title="Assumptions" count={list(doc.assumptions).length}>
        <Bullets items={doc.assumptions} />
      </Section>
      <Section title="Constraints" count={list(doc.constraints).length}>
        <Bullets items={doc.constraints} />
      </Section>
    </>
  )
}

export function Plan({ srs }) {
  if (!srs.have?.plan) return <Empty>No approved plan was saved with this SRS.</Empty>
  return (
    <pre className="whitespace-pre-wrap break-words font-mono text-[11.5px]
                    leading-relaxed text-ink">{srs.plan}</pre>
  )
}

export function Requirements({ srs }) {
  const doc = srs.document || {}
  const functional = list(doc.functional_requirements)
  const nonFunctional = list(doc.non_functional_requirements)
  if (!srs.have?.document) return <Empty>No SRS document was adopted for this project.</Empty>
  return (
    <>
      <Section title="Functional" count={functional.length}>
        <Bullets items={functional} tone="text-accent" />
      </Section>
      <Section title="Non-functional" count={nonFunctional.length}>
        <Bullets items={nonFunctional} />
      </Section>
      <Section title="Validation rules" count={list(doc.validation_rules).length}>
        <Bullets items={doc.validation_rules} />
      </Section>
      <Section title="Security" count={list(doc.security_requirements).length}>
        <Bullets items={doc.security_requirements} />
      </Section>
    </>
  )
}

export function Data({ srs }) {
  const tables = list((srs.document || {}).database_design?.tables)
  if (!tables.length) return <Empty>No database design in this SRS.</Empty>
  return (
    <>
      {tables.map((table, i) => {

        const columns = list(table.fields || table.columns)
        return (
          <Section key={i}
                   title={table.table_name || table.name || `Table ${i + 1}`}
                   count={columns.length}>
            {table.description && (
              <p className="mb-2 text-[11.5px] text-muted">{table.description}</p>
            )}
            <Table>
              <thead>
                <TR><TH>Column</TH><TH>Type</TH><TH>Notes</TH></TR>
              </thead>
              <tbody>
                {columns.map((c, j) => (
                  <TR key={j}>
                    <TD>{typeof c === 'string' ? c : (c.name || c.column)}</TD>
                    <TD className="text-muted">{typeof c === 'object' ? (c.type || '') : ''}</TD>
                    <TD className="text-muted">
                      {typeof c === 'object' ? [
                        c.primary_key && 'primary key',
                        c.unique && 'unique',
                        c.nullable === false && 'required',
                        c.references && `→ ${c.references}`,
                        c.description,
                      ].filter(Boolean).join(', ') : ''}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          </Section>
        )
      })}
      {list((srs.document || {}).database_design?.relationships).length > 0 && (
        <Section title="Relationships"
                 count={list(srs.document.database_design.relationships).length}>
          <Bullets items={srs.document.database_design.relationships} />
        </Section>
      )}
    </>
  )
}

export function Roles({ srs }) {
  const doc = srs.document || {}
  const matrix = list(doc.role_access_matrix)
  if (!list(doc.roles).length && !matrix.length) {
    return <Empty>This SRS describes no roles — every page is public.</Empty>
  }
  return (
    <>
      <Section title="Roles" count={list(doc.roles).length}>
        {list(doc.roles).length ? (
          <ul className="space-y-2">
            {list(doc.roles).map((r, i) => (
              <li key={i} className="text-[11.5px] leading-relaxed">
                <b className="font-semibold text-ink">
                  {r.role_name || r.name || r.role || idOf(r, i)}
                </b>
                {r.description && <span className="text-muted"> — {r.description}</span>}
              </li>
            ))}
          </ul>
        ) : <p className="text-[11.5px] text-muted2">None recorded.</p>}
      </Section>
      {matrix.length > 0 && (
        <Section title="Who can reach what" count={matrix.length}>
          <Table>
            <thead><TR><TH>Role</TH><TH>Pages</TH><TH>Can do</TH></TR></thead>
            <tbody>
              {matrix.map((row, i) => (
                <TR key={i}>
                  <TD>{row.role || row.role_name || idOf(row, i)}</TD>
                  <TD className="text-muted">
                    {list(row.allowed_pages || row.pages).map(line).join(', ') || '—'}
                  </TD>
                  <TD className="text-muted">
                    {list(row.allowed_functions || row.permissions || row.access)
                      .map(line).join(', ') || '—'}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </Section>
      )}
      <Section title="Public pages" count={list(doc.public_pages).length}>
        <Bullets items={doc.public_pages} />
      </Section>
      <Section title="Protected pages" count={list(doc.protected_pages).length}>
        <Bullets items={doc.protected_pages} tone="text-warn" />
      </Section>
    </>
  )
}

export function Handoff({ srs }) {
  const handoff = srs.handoff || {}
  const [copied, setCopied] = useState(false)
  if (!srs.have?.handoff) return <Empty>No builder handoff was saved with this SRS.</Empty>

  async function copy() {
    try {
      await navigator.clipboard.writeText(handoff.prompt || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {  }
  }

  return (
    <>
      <Summary>
        <Stat n={list(handoff.requirements).length} label="requirements" />
        <Stat n={list(handoff.pages).length} label="pages" />
        <Stat n={list(handoff.models).length} label="models" />
      </Summary>
      <Section title={`The prompt this app was built from — ${handoff.appType || ''}`}>
        <Panel className="relative p-4">
          <button onClick={copy}
                  className="absolute right-3 top-3 rounded-ctl border border-line
                             bg-panel2 px-2 py-1 text-[10px] text-muted
                             hover:text-ink">
            {copied ? 'Copied' : 'Copy'}
          </button>
          <pre className="whitespace-pre-wrap break-words pr-16 font-mono
                          text-[11.5px] leading-relaxed text-ink">
            {handoff.prompt}
          </pre>
        </Panel>
      </Section>
    </>
  )
}

export function Diagrams({ srs }) {
  const diagrams = list(srs.diagrams)
  const [open, setOpen] = useState(0)
  if (!diagrams.length) return <Empty>No diagrams were saved with this SRS.</Empty>
  const current = diagrams[Math.min(open, diagrams.length - 1)]
  return (
    <>
      <div className="mb-4 flex flex-wrap gap-1">
        {diagrams.map((d, i) => (
          <button key={d.name} onClick={() => setOpen(i)}
                  className={cn('rounded-ctl px-2.5 py-1 text-[11px] transition-colors',
                    i === open ? 'bg-accent/12 text-accent'
                               : 'text-muted hover:bg-panel2 hover:text-ink')}>
            {d.name.replace(/_/g, ' ')}
          </button>
        ))}
      </div>
      <Panel className="overflow-x-auto p-4">
        {current.svg

          ? <div className="srs-diagram [&_svg]:h-auto [&_svg]:max-w-full"
                 dangerouslySetInnerHTML={{ __html: current.svg }} />
          : <pre className="whitespace-pre font-mono text-[11px] text-muted">
              {current.mermaid}
            </pre>}
      </Panel>
      {!current.svg && (
        <p className="mt-2 text-[11px] text-muted2">
          {current.rendered
            ? 'The picture for this revision is on disk but only the current '
              + 'version is displayed — its Mermaid source is shown instead.'
            : 'No image was rendered for this one — the Mermaid source is shown instead.'}
        </p>
      )}
    </>
  )
}

export function Interview({ srs }) {
  const transcript = list((srs.interview || {}).transcript)
  const answers = list((srs.interview || {}).answers)
  if (!transcript.length) return <Empty>No interview was saved with this SRS.</Empty>
  const byId = Object.fromEntries(answers.map(a => [a.question_id, a]))
  return (
    <div className="space-y-3">
      {transcript.map((q, i) => {
        const a = byId[q.id]
        const value = a && (Array.isArray(a.value) ? a.value.join(', ') : a.value)
        return (
          <Panel key={q.id || i} className="p-3">
            <p className="text-[11.5px] leading-relaxed text-ink">
              <span className="mr-2 font-mono text-[10px] text-muted2">
                {String(i + 1).padStart(2, '0')}
              </span>
              {q.question}
            </p>
            <p className="mt-1.5 pl-7 text-[11.5px] text-accent">
              {value != null && String(value).trim()
                ? String(value)
                : <span className="text-muted2">not answered</span>}
            </p>
            {a?.raw_text && a.raw_text !== value && (
              <p className="mt-0.5 pl-7 text-[11px] text-muted">“{a.raw_text}”</p>
            )}
          </Panel>
        )
      })}
    </div>
  )
}


export const VIEWS = [
  { id: 'document', label: 'Document', C: Document },
  { id: 'plan', label: 'Approved Plan', C: Plan },
  { id: 'requirements', label: 'Requirements', C: Requirements },
  { id: 'data', label: 'Data', C: Data },
  { id: 'roles', label: 'Roles & Access', C: Roles },
  { id: 'handoff', label: 'Handoff', C: Handoff },
  { id: 'diagrams', label: 'Diagrams', C: Diagrams },
  { id: 'interview', label: 'Interview', C: Interview },
  { id: 'risks', label: 'Risks', C: Risks },
]


export function badgeFor(id, srs) {
  const doc = srs?.document || {}
  const n = (value) => (Array.isArray(value) ? value.length : 0)
  if (id === 'requirements' && n(doc.functional_requirements)) {
    return { n: n(doc.functional_requirements), bad: false }
  }
  if (id === 'data' && n(doc.database_design?.tables)) {
    return { n: n(doc.database_design.tables), bad: false }
  }
  if (id === 'diagrams' && n(srs?.diagrams)) {
    return { n: n(srs.diagrams), bad: false }
  }
  if (id === 'interview' && n(srs?.interview?.transcript)) {
    return { n: n(srs.interview.transcript), bad: false }
  }

  if (id === 'risks' && n(doc.ambiguities)) {
    return { n: n(doc.ambiguities), bad: true }
  }
  return null
}

export function Risks({ srs }) {
  const doc = srs.document || {}
  const ambiguities = list(doc.ambiguities)
  const risks = list(doc.risk_priority)
  if (!srs.have?.document) return <Empty>No SRS document was adopted for this project.</Empty>
  return (
    <>
      <Section title="Ambiguities" count={ambiguities.length}>
        {ambiguities.length ? (
          <ul className="space-y-2.5">
            {ambiguities.map((a, i) => (
              <li key={i} className="text-[11.5px] leading-relaxed">
                <span className="mr-2 font-mono text-[10px] text-warn">
                  {a.area || `#${i + 1}`}
                </span>
                <span className="text-ink">{a.description || line(a)}</span>
                {a.assumption_made && (
                  <span className="mt-0.5 block pl-1 text-muted">
                    Assumed: {a.assumption_made}
                  </span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[11.5px] text-ok">
            Nothing was left ambiguous — every question the SRS raised was settled.
          </p>
        )}
      </Section>
      <Section title="Risks" count={risks.length}>
        <Bullets items={risks} tone="text-warn" />
      </Section>
      <Section title="Acceptance criteria" count={list(doc.acceptance_criteria).length}>
        <Bullets items={doc.acceptance_criteria} />
      </Section>
    </>
  )
}
