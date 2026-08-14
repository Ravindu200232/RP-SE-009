'use client'

import { useState } from 'react'
import { AlertTriangle, Loader2, Square, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button, Modal } from '../ui'


const ACTIVE = new Set(['BOOTSTRAPPING', 'CI_RUNNING', 'DEPLOYING', 'VALIDATING'])

export function DeployDanger({ runId, state, running, onDone }) {
  const [ask, setAsk] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!runId) return null

  if (state === 'DESTROYED') return null

  const active = ACTIVE.has(state)

  const act = async () => {
    setBusy(true)
    setError('')
    try {
      await api.deploy(`/runs/${runId}/${ask === 'cancel' ? 'cancel' : 'teardown'}`,
                       ask === 'cancel' ? { confirm: true }
                                        : { confirm: true, force: active })
      setAsk('')
      onDone?.()
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {running && (
        <Button size="sm" variant="ghost" onClick={() => setAsk('cancel')}
                className="text-muted hover:text-bad"
                title="Stop this deployment. Cloud resources are not deleted.">
          <Square className="size-3" /> Cancel
        </Button>
      )}
      <Button size="sm" variant="ghost" onClick={() => setAsk('teardown')}
              className="text-muted hover:text-bad"
              title={active
                ? 'Stop this deployment and delete every cloud resource it created.'
                : 'Delete every cloud resource this deployment created.'}>
        <Trash2 className="size-3" /> Delete
      </Button>

      {ask && (
        <Modal onClose={() => { if (!busy) { setAsk(''); setError('') } }}>
          <h2 className="flex items-center gap-2 text-[15px] font-semibold text-ink">
            <AlertTriangle className={ask === 'teardown' ? 'size-4 text-bad'
                                                         : 'size-4 text-warn'} />
            {ask === 'cancel' ? 'Cancel this deployment?'
                              : 'Delete this deployment’s cloud resources?'}
          </h2>

          {ask === 'cancel' ? (
            <div className="mt-3 space-y-2 text-[12.5px] leading-relaxed text-muted">
              <p>AgentForge stops advancing this run, and the GitHub Actions run
                 still deploying for it is stopped too.</p>
              <p className="text-ink">
                Nothing in AWS is deleted. Anything this run already created
                keeps running — and keeps billing — until you delete it.
              </p>
              <p>You can deploy this project again afterwards.</p>
            </div>
          ) : (
            <div className="mt-3 space-y-2 text-[12.5px] leading-relaxed text-muted">
              {active && (
                <p className="text-warn">
                  This deployment is still marked as running, so it is stopped
                  first — the GitHub Actions run deploying for it is cancelled,
                  then the resources are deleted.
                </p>
              )}
              <p>This deletes every cloud resource the deployment created — the
                 CloudFormation stack, the instance and its Elastic IP, the
                 artifact bucket and the runtime secret.</p>
              <p className="text-bad">
                It cannot be undone, and the site stops answering immediately.
              </p>
              <p>The repository, the generated files and this run’s record all
                 stay where they are.</p>
            </div>
          )}

          {error && (
            <p className="mt-3 flex items-start gap-2 rounded-ctl border border-bad/40
                          bg-bad/10 px-2.5 py-2 text-[11.5px] text-bad">
              <AlertTriangle className="mt-px size-3.5 shrink-0" /> {error}
            </p>
          )}

          <footer className="mt-4 flex items-center justify-end gap-2">
            <Button variant="outline" onClick={() => { setAsk(''); setError('') }}
                    disabled={busy}>
              Keep it
            </Button>
            <Button variant="solid" onClick={act} disabled={busy}
                    className={ask === 'teardown' ? 'bg-bad hover:brightness-110' : ''}>
              {busy ? <Loader2 className="size-3.5 animate-spin" />
                    : ask === 'cancel' ? <Square className="size-3.5" />
                                       : <Trash2 className="size-3.5" />}
              {busy ? 'Working…'
                    : ask === 'cancel' ? 'Cancel the deployment'
                    : active ? 'Stop it and delete the resources'
                             : 'Delete the resources'}
            </Button>
          </footer>
        </Modal>
      )}
    </>
  )
}
