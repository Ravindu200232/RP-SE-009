'use client'

import { ExternalLink, GitBranch, Rocket } from 'lucide-react'
import { STATE_TEXT, TARGETS } from '@/lib/deploy-constants'
import { SectionLabel, Tag } from '../ui'

/**
 * The last finished deployment, in short: what it was, where it is, whether it held up, and (when it stopped part of the way)
 * the way to carry on. Everything else about it is in the navigation, read live from the provider's own command line tool.
 */
export default function DeployResult({ data, onResumed }) {
  const project = useStore(s => s.project)
  const [resuming, setResuming] = useState(false)
  const [problem, setProblem] = useState('')
  // The stopped run this card was resumed from: hidden from the moment it carries on, so its old error is gone and the
  // pipeline shows instead. If the resumed run stops again it finishes at another time, and the card comes back for it.
  const [resumedFrom, setResumedFrom] = useState(null)
  const last = data?.last
  if (!last || !TERMINAL.has(last.state)) return null
  if (resumedFrom && resumedFrom === `${last.run_id}|${last.finished_at}`) return null

  // A run that was stopped part of the way goes on from where it stopped, on the plan that was approved.
  async function resume() {
    setResuming(true)
    setProblem('')
    try {
      const state = useStore.getState()
      const result = await api.changeDecide(project, data.retry.change, {
        decision: 'retry', model: state.models.builder || state.models.agent,
      })
      if (result && result.ok === false) setProblem(result.detail || 'That deployment cannot be resumed.')
      else {
        setResumedFrom(`${last.run_id}|${last.finished_at}`)
        await onResumed?.()
      }
    } catch (e) {
      setProblem(e.message || 'Could not resume it.')
    }
    setResuming(false)
  }

  const [label, tone] = STATE_TEXT[last.state] || [last.state, 'mute']
  const repo = last.repository || {}
  const checks = Array.isArray(last.checks) ? last.checks : []
  const passed = checks.filter(check => check.result === 'pass').length
  const rechecks = (Array.isArray(last.evidence) ? last.evidence : []).filter(row => row.kind === 'studio re-check')

  return (
    <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] p-5 shadow-[0_0_2px_0_rgba(145,158,171,0.2),0_12px_24px_-4px_rgba(0,0,0,0.16)]">
      <SectionLabel className="border-b-2 border-line2 pb-1.5"
                    right={<Tag tone={{ pass: 'ok', fail: 'bad',
                                        run: 'accent' }[tone] || 'mute'}>
                      {label}
                    </Tag>}>
        Last deployment
      </SectionLabel>

      <dl className="mt-1 text-[11.5px]">
        <Row label="Target">
          {TARGETS.find(target => target.id === last.target)?.label || last.target}
        </Row>
        {url && (
          <Row label="Live at">
            <a href={last.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
              <Rocket className="size-3" /> {last.url} <ExternalLink className="size-2.5" />
            </a>
          </Row>
        )}
        {repo.url && (
          <Row label="Repository">
            <a href={repo.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
              <GitBranch className="size-3" /> {repo.url} <ExternalLink className="size-2.5" />
            </a>
          </Row>
        )}
        {(checks.length > 0 || rechecks.length > 0) && (
          <Row label="Checks">
            <span className="inline-flex items-center gap-1">
              <ShieldCheck className="size-3 text-muted2" />
              {checks.length ? `${passed} of ${checks.length} live checks passed` : 'checked by the studio'}
              {rechecks.length ? ` · ${rechecks.length} re-checked by the studio itself` : ''}
            </span>
          </Row>
        )}
      </dl>

      {last.error && (
        <p className="mt-3 border border-line2 border-l-[3px] border-l-accent
                      bg-tint px-3 py-2.5 text-[11.5px] text-deep">
          {last.error}
        </p>
      )}
    </div>
  )
}

const Row = ({ label, children }) => (
  <div className="flex gap-3 border-b border-line py-1.5 last:border-0">
    <dt className="w-[86px] shrink-0 text-label">{label}</dt>
    <dd className="min-w-0 flex-1 break-words text-ink">{children}</dd>
  </div>
)
