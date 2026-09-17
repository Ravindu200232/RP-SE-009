'use client'

/**
 * The revisions panel, for a project that has already been built.
 *
 * The workspace knows a project by its folder name; the specification agent
 * knows it by the `prj_…` id it was generated under. `link.json` is the only
 * record joining the two, and `read_srs_results` already surfaces it — so the
 * id is one call away from data this screen fetches anyway.
 *
 * A revision here does not stop at the document. The prototype and the code
 * were built from it, so once the specification changes they disagree with it
 * until someone says otherwise — which is what the dialog asks.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Button, Empty, Modal } from '../ui'
import { SrsRevisions } from './SrsRevisions'

const WHAT = {
  designer: ['Prototype', 'the drawn pages'],
  developer: ['Application', 'the built code and its tests'],
}

/** What the change should be carried into, and whether to carry it. */
function CarryOver({ targets, version, changed, busy, onGo, onSkip }) {
  const [picked, setPicked] = useState(() => new Set(targets))
  const toggle = role => setPicked(was => {
    const next = new Set(was)
    next.has(role) ? next.delete(role) : next.add(role)
    return next
  })

  return (
    <Modal onClose={busy ? () => { } : onSkip} className="max-w-[460px]">
      <div role="dialog" aria-modal="true" aria-label="Carry this change into the project">
        <h3 className="text-sm font-semibold text-ink">
          The specification is now v{version}
        </h3>
        {changed ? (
          <p className="mt-2 whitespace-pre-wrap text-[11.5px] leading-relaxed text-muted">{changed}</p>
        ) : null}
        <p className="mt-3 text-[11.5px] text-muted">
          What was built from it still says the old thing. Carry the change into:
        </p>

        <div className="mt-3 space-y-1.5">
          {targets.map(role => (
            <label key={role}
              className="flex cursor-pointer items-start gap-2.5 rounded-panel border
                         border-line bg-panel2 px-3 py-2.5 hover:border-accent">
              <input type="checkbox" checked={picked.has(role)} disabled={busy}
                onChange={() => toggle(role)} className="mt-0.5 accent-[#1877F2]" />
              <span className="min-w-0">
                <span className="block text-[12px] font-medium text-ink">{WHAT[role][0]}</span>
                <span className="block text-[10.5px] text-muted2">{WHAT[role][1]}</span>
              </span>
            </label>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="outline" disabled={busy} onClick={onSkip}>Not now</Button>
          <Button disabled={busy || !picked.size} onClick={() => onGo([...picked])}>
            {busy ? 'Starting…' : `Update ${picked.size === 2 ? 'both' : picked.size ? WHAT[[...picked][0]][0].toLowerCase() : ''}`}
          </Button>
        </div>
        <p className="mt-2.5 text-[10px] leading-relaxed text-muted2">
          Each one runs as its own agent turn and you can watch it in its tab. The
          specification keeps the change either way.
        </p>
      </div>
    </Modal>
  )
}

export default function SrsRevisionsPanel() {
  const project = useStore(s => s.project)
  const srsStamp = useStore(s => s.srsStamp[s.project])
  const addLog = useStore(s => s.addLog)
  // The change is not finished when the document changes — it is finished when
  // what was built from it agrees again. The server says so on the same
  // `sync_state` events the SRS tab already listens to.
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
      await api.specChange(project, ask.prompt, roles)
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
        onRevised={(answer, prompt) => {
          const said = answer?.diff_summary || []
          // Nothing was built from this specification yet, so there is nothing
          // to carry the change into and nothing to ask about.
          if (!built.length) return
          setAsk({ prompt, version: answer?.version, changed: said.join('\n') })
        }} />
      {ask && (
        <CarryOver targets={built} version={ask.version} changed={ask.changed} busy={busy}
          onGo={carry} onSkip={() => setAsk(null)} />
      )}
    </>
  )
}
