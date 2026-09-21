'use client'

/** SRS revisions panel for already built projects, coordinating document changes with prototypes and code. */
import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Empty } from '../ui'
import { SrsRevisions } from './SrsRevisions'
import SrsApprovalModal from './SrsApprovalModal'

export default function SrsRevisionsPanel() {
  const project = useStore(s => s.project)
  const srsStamp = useStore(s => s.srsStamp[s.project])
  const addLog = useStore(s => s.addLog)
  // Track revision completion via sync_state events until built artifacts reconcile.
  const sync = useStore(s => s.projectSync[s.project])
  const carrying = sync?.status === 'running' && sync?.source === 'srs'
  const [link, setLink] = useState(null)
  const [state, setState] = useState('loading')
  const [ask, setAsk] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!project) return
    setState('loading')
    api.srsResults(project)
      .then(found => {
        setLink({ srsId: found?.link?.srs_id || '', targets: found?.targets || {} })
        setState('ready')
      })
      .catch(() => setState('error'))
  }, [project])

  useEffect(() => { load() }, [load, srsStamp])

  async function carry(roles) {
    setBusy(true)
    try {
      await api.approveChangeRequest(project, ask.requestId, roles)
      addLog('INFO', `Carrying the specification change into ${roles.join(' and ')}`)
      setAsk(null)
    } catch (e) {
      addLog('WARN', `Could not start that update — ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  if (!project) return <Empty>Open a project to see its specification.</Empty>
  if (state === 'loading') return <Empty>Reading the specification…</Empty>
  if (state === 'error' || !link?.srsId) {
    return (
      <Empty>
        This project has no specification to revise — it was built straight from
        a prompt. Ask for changes in the Designer or Developer tab instead.
      </Empty>
    )
  }

  const built = ['designer', 'developer'].filter(role => link.targets?.[role])

  return (
    <>
      <SrsRevisions srsId={link.srsId} className="min-h-0 flex-1" working={carrying}
        onRevised={async (answer, prompt) => {
          const said = answer?.diff_summary || []
          // Nothing was built from this specification yet, so there is nothing
          // to carry the change into and nothing to ask about.
          if (!built.length) return
          try {
            const created = await api.createChangeRequest({
              project, kind: 'srs', prompt, targets: built, srs_version: answer?.version, summary: said,
            })
            setAsk({ requestId: created?.request?.id, prompt, version: answer?.version, changed: said.join('\n') })
          } catch (error) {
            addLog('WARN', `Could not prepare the approval record — ${error.message}`)
          }
        }} />
      {ask && (
        <SrsApprovalModal targets={built} version={ask.version} changed={ask.changed} busy={busy}
          onApprove={carry} onKeepDraft={() => setAsk(null)} />
      )}
    </>
  )
}
