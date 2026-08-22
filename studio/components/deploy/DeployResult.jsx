'use client'

import { ExternalLink, GitBranch, Rocket } from 'lucide-react'
import { STATE_TEXT } from '@/lib/deploy-constants'
import { Badge, Panel, SectionLabel } from '../ui'

export default function DeployResult({ data }) {
  const last = data?.have?.last ? data.last : null
  if (!last) return null

  const [label, tone] = STATE_TEXT[last.state] || [last.state, 'mute']
  const repo = last.repo_state || {}

  const url = repo.application_url || ''
  const slug = typeof repo.repository === 'string' ? repo.repository : ''
  const score = last.readiness?.score

  return (
    <Panel className="p-4">
      <SectionLabel right={<Badge tone={{ pass: 'ok', fail: 'bad', run: 'accent' }[tone] || 'mute'}>
                             {label}
                           </Badge>}>
        Last deployment
      </SectionLabel>

      <dl className="mt-3 space-y-1.5 text-[11.5px]">
        <Row label="Target">
          {last.target === 'vercel' ? 'Vercel' : 'AWS EC2'}
        </Row>
        {url && (
          <Row label="Live at">
            <a href={url} target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-1 text-accent hover:underline">
              <Rocket className="size-3" /> {url}
              <ExternalLink className="size-2.5" />
            </a>
          </Row>
        )}
        {slug && (
          <Row label="Repository">
            <a href={`https://github.com/${slug}`} target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-1 text-accent hover:underline">
              <GitBranch className="size-3" /> {slug}
              {repo.branch ? ` · ${repo.branch}` : ''}
              <ExternalLink className="size-2.5" />
            </a>
          </Row>
        )}
        {typeof score === 'number' && (
          <Row label="Readiness">{score}/100</Row>
        )}
        {last.link?.adopted_at && (
          <Row label="Recorded">
            {new Date(last.link.adopted_at).toLocaleString()}
          </Row>
        )}
        <Row label="Run">
          <span className="font-mono text-[10.5px] text-muted2">
            {String(last.run_id).slice(0, 12)}
          </span>
        </Row>
      </dl>

      {last.error && (
        <p className="mt-3 rounded-ctl border border-bad/40 bg-bad/10 px-2.5 py-2
                      text-[11.5px] text-bad">
          {last.error}
        </p>
      )}
    </Panel>
  )
}

const Row = ({ label, children }) => (
  <div className="flex gap-3">
    <dt className="w-[86px] shrink-0 text-muted2">{label}</dt>
    <dd className="min-w-0 flex-1 break-words text-ink">{children}</dd>
  </div>
)
