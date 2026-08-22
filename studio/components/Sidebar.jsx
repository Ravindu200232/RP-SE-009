'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Moon, Sun, FolderUp, Settings, Download, ExternalLink, Search, Play, Trash2,
} from 'lucide-react'
import { useStore, KEYS } from '@/lib/store'
import { api } from '@/lib/api'
import { isCloud, hasVision, maxContext, roomyContext } from '@/lib/models'
import ModelPicker from './ModelPicker'
import { Badge, Button, Input, SectionLabel, Tag, Tip } from './ui'
import { cn } from '@/lib/utils'


export default function Sidebar({
  models: cat, projects, onOpen, onImport, onSettings, onZip, onResume, onDeleted,
}) {
  const s = useStore()
  const { models, agentMode, think, images, project, status, statusText, theme } = s
  const folderRef = useRef(null)
  const [q, setQ] = useState('')
  const [fooocus, setFooocus] = useState(null)
  const [confirming, setConfirming] = useState('')
  const [removing, setRemoving] = useState('')

  async function remove(name) {
    setRemoving(name)
    try {
      await api.deleteProject(name)
      s.addLog('SUCCESS', `🗑 Deleted ${name}`)
    } catch (e) {
      // Reported, not trusted. The request in front of this API is abandoned
      // at 30 seconds and a delete used to run past it, so "the connection
      // died" and "nothing happened" are not the same thing — the project was
      // gone and the studio went on showing it. The list below is what
      // settles it: whatever the server did, this asks it again.
      s.addLog('WARN', `Delete of ${name} did not report back — ${e.message}. `
                     + 'Checking whether it went.')
    }
    // The studio was pointing at a folder that may have stopped existing, so
    // it lets go either way; `onDeleted` re-reads the list from the server.
    if (project === name) useStore.getState().reset(null)
    onDeleted?.(name)
    setRemoving('')
    setConfirming('')
  }

  function pick(role, id) {
    useStore.setState({ models: { ...models, [role]: id } })
    s.persist(KEYS[role], id)
    if (role === 'agent' && isCloud(id) && !cat.cloudEnabled) {
      s.addLog('WARN', '☁️ Cloud model selected but Ollama is not signed in — '
                     + 'run `ollama signin`')
    }
    if (role === 'qa') {
      const eff = id || models.agent
      s.addLog(isCloud(eff) ? 'INFO' : 'WARN', isCloud(eff)
        ? `🧪 QA runs on ${eff}`
        : `⚠ ${eff} is local — QA is cloud-only and will not run.`)
    }
    if (role === 'srs') {

      const eff = id || models.agent
      api.saveSettings({ srs_model: id }).catch(() =>
        s.addLog('WARN', '⚠ Could not save the SRS model — it will not stick.'))
      s.addLog(roomyContext(cat.all, eff) ? 'INFO' : 'WARN',
        roomyContext(cat.all, eff)
          ? `📄 The SRS runs on ${eff}`
          : `⚠ ${eff} has a small context window — the SRS will be truncated.`)
    }
    if (role === 'deploy') {

      const eff = id || models.agent
      api.saveSettings({ deploy_model: id }).catch(() =>
        s.addLog('WARN', '⚠ Could not save the deploy model — it will not stick.'))
      s.addLog(roomyContext(cat.all, eff) ? 'INFO' : 'WARN',
        roomyContext(cat.all, eff)
          ? `🚀 Deployment plans run on ${eff}`

          : `⚠ ${eff} has a small window — a truncated plan cannot be deployed.`)
    }
  }

  function toggle(key, storeKey) {
    const next = !s[key]
    useStore.setState({ [key]: next })
    s.persist(storeKey, next ? '1' : '0')
  }

  // The Images chip is the only switch here that another program has to agree
  // with. Agent and Thinking are settings this browser holds and sends with
  // the next build; images are drawn by Fooocus, which the server reaches over
  // HTTP and which the chip never told anything. So the chip was on, the
  // server's own `image_enabled` was whatever it had been left at, and the
  // build logged "image generation is off" with the switch lit.
  //
  // Two things follow from that. The chip has to write the server's setting,
  // and it has to say whether Fooocus is actually answering — turning it on is
  // exactly the moment somebody wants to know, and it is a separate program
  // that gets started and stopped by hand, so the answer has to be asked for
  // again each time rather than remembered from boot.
  async function checkFooocus() {
    setFooocus(f => ({ ...(f || {}), checking: true }))
    try {
      const r = await api.imageCheck()
      setFooocus({ ...r, checking: false })
      return r
    } catch (e) {
      setFooocus({ error: e.message, checking: false })
      return null
    }
  }

  useEffect(() => {
    api.settings()
      .then(cfg => {
        // The server's setting is the one that decides, so the chip adopts it
        // rather than the other way round — otherwise a switch left on in this
        // browser would claim a capability the build does not have. A server
        // too old to report it leaves the saved chip alone rather than
        // switching it off on the strength of a missing field.
        if (!cfg || !('image_enabled' in cfg)) return
        useStore.setState({ images: !!cfg.image_enabled })
        s.persist(KEYS.images, cfg.image_enabled ? '1' : '0')
        if (cfg.image_enabled) checkFooocus()
      })
      .catch(() => { })
  }, [])

  async function toggleImages() {
    const next = !images
    useStore.setState({ images: next })
    s.persist(KEYS.images, next ? '1' : '0')
    try {
      await api.saveSettings({ image_enabled: next })
    } catch {
      s.addLog('WARN', '⚠ Could not save the images setting — it will not stick.')
    }
    if (!next) return setFooocus(null)

    const r = await checkFooocus()
    if (r?.available) {
      s.addLog('INFO', `🎨 Fooocus is answering at ${r.host} — pictures will be drawn.`)
    } else if (r?.can_start) {
      s.addLog('WARN', '⚠ No Fooocus is answering. Press “start it” in the '
                     + 'sidebar, or run it yourself.')
    } else {
      s.addLog('WARN', '⚠ No Fooocus is answering and none was found on this '
                     + 'machine — start it, or set its address in Settings.')
    }
  }

  async function startFooocus() {
    setFooocus(f => ({ ...(f || {}), checking: true }))
    try {
      const r = await api.imageStart()
      s.addLog('INFO', `🎨 Starting Fooocus — ${r.launcher}. It takes a `
                     + 'minute or two to load its model.')
    } catch (e) {
      s.addLog('WARN', `⚠ Could not start Fooocus — ${e.message}`)
      return setFooocus(f => ({ ...(f || {}), checking: false }))
    }
    // Cold start is minutes, not seconds, and the answer is what the chip
    // shows — so poll rather than ask once and report a failure that is only
    // a model still loading.
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 5000))
      const r = await api.imageCheck().catch(() => null)
      if (r?.available) {
        setFooocus({ ...r, checking: false })
        return s.addLog('INFO', `🎨 Fooocus is up at ${r.host}.`)
      }
    }
    setFooocus(f => ({ ...(f || {}), checking: false }))
    s.addLog('WARN', '⚠ Fooocus did not come up within five minutes — check '
                   + 'its window for what it is waiting on.')
  }

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return projects
    return projects.filter(p =>
      String(p.title || p.name || p).toLowerCase().includes(needle) ||
      String(p.name || '').toLowerCase().includes(needle))
  }, [projects, q])

  const qaEffective = models.qa || models.agent
  const srsEffective = models.srs || models.agent
  const srsRoomy = roomyContext(cat.all, srsEffective)
  const deployEffective = models.deploy || models.agent
  const deployRoomy = roomyContext(cat.all, deployEffective)
  const dot = { live: 'bg-ok', busy: 'bg-warn', connecting: 'bg-muted2' }[status]
    || 'bg-bad'

  return (
    <aside className="flex w-[var(--sidebar-w)] shrink-0 flex-col border-r
                      border-line bg-panel">
      <header className="flex items-center gap-[11px] border-b border-line
                         px-4 pb-3 pt-4">
        {/* The artwork, not a letter standing in for it. `basePath` is
            `/__agentforge`, so a file in `studio/public` is served from under
            it — an absolute `/agentforge-mark.png` would go to the generated
            app's dev server instead, which is a different site entirely. */}
        <img src="/__agentforge/agentforge-mark.png" alt="AgentForge"
             width={34} height={34}
             className="size-[34px] shrink-0 rounded-[10px] object-contain" />
        <div className="min-w-0 flex-1">
          <div className="font-display text-[14px] font-bold leading-none text-ink">
            AgentForge
          </div>
          <div className="mt-[3px] text-[8.5px] font-semibold tracking-[2px] text-muted2">
            STUDIO
          </div>
        </div>
        <Tip text="Toggle theme">
          <Button size="icon"
                  onClick={() => s.setTheme(theme === 'dark' ? 'light' : 'dark')}>
            <Moon className="hidden size-3.5 dark:block" />
            <Sun className="size-3.5 dark:hidden" />
          </Button>
        </Tip>
      </header>

      <div className="mx-3 mt-2.5 flex items-center gap-[7px] rounded-ctl border
                      border-line bg-bg px-[11px] py-[7px]">
        <span className={cn('size-[6px] shrink-0 rounded-full', dot,
                            status === 'live' && 'ring-[3px] ring-ok/20')} />
        <span className="truncate font-mono text-[10px] text-muted">{statusText}</span>
      </div>

      <SectionLabel className="px-4 pb-1.5 pt-3.5">Models</SectionLabel>
      {!agentMode ? (
        <>
          <ModelPicker label="Refine" value={models.refine} options={cat.local}
                       onChange={id => pick('refine', id)} />
          <ModelPicker label="Build" value={models.build} options={cat.local}
                       onChange={id => pick('build', id)} />
        </>
      ) : (
        <>
          <ModelPicker label="Agent" value={models.agent} options={cat.all}
                       onChange={id => pick('agent', id)}
                       hint={hasVision(cat.all, models.agent)
                         ? 'Accepts images — the pencil can send it a capture'
                         : 'No vision: a vision model is borrowed for pencil captures'} />
          <ModelPicker label="QA" value={models.qa} placeholder="same as agent"
                       options={[{ id: '', label: 'same as agent', icon: '↳',
                                   desc: 'Follow whatever the agent model is.' },
                                 ...cat.all]}
                       onChange={id => pick('qa', id)}
                       hint={isCloud(qaEffective)
                         ? `QA runs on ${qaEffective} — unit tests, their repair and the signed-in sweep.`
                         : `${qaEffective} is local and QA is cloud-only, so those stages will not run.`} />
          <ModelPicker label="SRS" value={models.srs} placeholder="same as agent"
                       options={[{ id: '', label: 'same as agent', icon: '↳',
                                   desc: 'Follow whatever the agent model is.' },
                                 ...cat.all]}
                       onChange={id => pick('srs', id)}
                       hint={srsRoomy
                         ? `The interview and the SRS run on ${srsEffective}.`
                         : `${srsEffective} has a ${maxContext(cat.all, srsEffective).toLocaleString()}-token window — the SRS carries the whole interview and will be truncated.`} />
          <ModelPicker label="Deploy" value={models.deploy} placeholder="same as agent"
                       options={[{ id: '', label: 'same as agent', icon: '↳',
                                   desc: 'Follow whatever the agent model is.' },
                                 ...cat.all]}
                       onChange={id => pick('deploy', id)}
                       hint={deployRoomy
                         ? `The deployment plan is written by ${deployEffective}.`
                         : `${deployEffective} has a ${maxContext(cat.all, deployEffective).toLocaleString()}-token window — a plan it cannot finish will not deploy.`} />
        </>
      )}

      <div className="flex flex-wrap gap-1.5 px-3 pb-1 pt-1.5">
        <Chip on={agentMode} onClick={() => toggle('agentMode', KEYS.agentMode)}>
          Agent
        </Chip>
        <Chip on={think} onClick={() => toggle('think', KEYS.think)}
              tip="A reasoning pass costs real time on a twenty-file build">
          Thinking
        </Chip>
        <Chip on={images} onClick={toggleImages}
              tip={fooocusTip(fooocus, images)}>
          Images
          {images && (
            <span className={cn('ml-1.5 inline-block size-[5px] rounded-full align-middle',
              fooocus?.checking ? 'animate-pulse bg-white/70'
                : fooocus?.available ? 'bg-white'
                : 'bg-white/30')} />
          )}
        </Chip>
      </div>

      {images && fooocus && !fooocus.checking && !fooocus.available && (
        <p className="px-3 pb-1 pt-0.5 text-[10px] leading-snug text-muted2">
          No Fooocus is answering
          {fooocus.can_start ? (<>
            {' — '}
            <button onClick={startFooocus}
                    className="text-accent underline underline-offset-2 hover:text-ink">
              start it
            </button>
          </>) : ' — start it, or set its address in Settings'}
        </p>
      )}

      <SectionLabel className="px-4 pb-1.5 pt-3.5"
                    right={<span className="font-mono">{projects.length}</span>}>
        Projects
      </SectionLabel>

      {projects.length > 6 && (
        <div className="relative mx-3 mb-1">
          <Search className="pointer-events-none absolute left-2 top-1/2 size-3
                             -translate-y-1/2 text-muted2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter…"
                 className="pl-7" />
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {shown.map(p => {
          const name = p.name || p
          const on = project === name
          const asking = confirming === name
          const busyHere = removing === name
          return (
            // A row, not a button — the delete control lives inside it and a
            // <button> inside a <button> is invalid HTML that React will not
            // render as written.
            <div key={name}
                 className={cn('group flex w-full items-center gap-2 rounded-ctl',
                   'px-2 py-[7px] transition-colors',
                   asking ? 'bg-bad/10 ring-1 ring-bad/40'
                          : on ? 'bg-accent/12' : 'hover:bg-panel2')}>
              <span className={cn('size-[5px] shrink-0 rounded-full',
                                  on ? 'bg-accent' : 'bg-muted2')} />
              <button onClick={() => onOpen(name)} disabled={asking || busyHere}
                      className="min-w-0 flex-1 text-left">
                <span className={cn('block truncate text-[11.5px] leading-tight',
                                    on ? 'text-accent' : 'text-ink')}>
                  {p.title || name}
                </span>
                <span className="mt-px block truncate font-mono text-[9px] text-muted2">
                  {asking ? 'delete this and its database?'
                          : `${p.stack || 'next'}${p.file_count ? ` · ${p.file_count}` : ''}`}
                </span>
              </button>

              {asking ? (
                <>
                  <button onClick={() => remove(name)} disabled={busyHere}
                          className="shrink-0 rounded border border-bad/50 bg-bad/10
                                     px-1.5 py-0.5 font-mono text-[9px] text-bad
                                     transition-colors hover:bg-bad/20
                                     disabled:opacity-50">
                    {busyHere ? '…' : 'delete'}
                  </button>
                  <button onClick={() => setConfirming('')} disabled={busyHere}
                          className="shrink-0 px-1 font-mono text-[9px] text-muted2
                                     hover:text-ink">
                    keep
                  </button>
                </>
              ) : (<>
                <DeployTag deployed={p.deployed} />
                {p.unfinished ? <Badge tone="bad">{p.unfinished}</Badge> : null}
                {/* Only on hover, and it asks before it acts. This is the one
                    control in the studio that destroys work that cannot be
                    got back, so it does not sit where a mis-click can find
                    it and it never fires on the first press. */}
                <Tip text={`Delete ${name} from disk`}>
                  <button onClick={() => setConfirming(name)}
                          className="shrink-0 rounded p-0.5 text-muted2 opacity-0
                                     transition-opacity hover:text-bad
                                     group-hover:opacity-100">
                    <Trash2 className="size-3" />
                  </button>
                </Tip>
              </>)}
            </div>
          )
        })}
        {!shown.length && (
          <p className="px-2 py-3 text-[11px] text-muted">
            {projects.length ? `Nothing matches “${q}”.` : 'No projects yet.'}
          </p>
        )}
      </div>

      <footer className="flex items-center gap-0.5 border-t border-line px-2.5 py-2">
        <input ref={folderRef} type="file" hidden
               webkitdirectory="" directory="" multiple
               onChange={e => {
                 const list = e.target.files
                 e.target.value = ''
                 if (list?.length) onImport(list)
               }} />
        <Foot icon={FolderUp} tip="Import a project folder"
              onClick={() => folderRef.current?.click()} />
        <Foot icon={Play} tip="Resume this build where it stopped"
              disabled={!project || status === 'busy'} onClick={onResume} />
        <Foot icon={Settings} tip="Settings" onClick={onSettings} />
        <Foot icon={Download} tip="Download this project as a zip"
              disabled={!project} onClick={onZip} />
        <Foot icon={ExternalLink} tip="Open the app in a new tab"
              disabled={!project} onClick={() => window.open('/', '_blank')} />
      </footer>
    </aside>
  )
}


function DeployTag({ deployed }) {
  if (!deployed) return null
  const gone = deployed.state === 'deleted'
  const where = deployed.target?.startsWith('aws') ? 'aws'
              : deployed.target === 'vercel' ? 'vercel'
              : ''
  return (
    <Tip text={gone ? 'Deployed, then deleted'
                    : `Deployed${where ? ` to ${where}` : ''}`}>
      <Tag tone={gone ? 'mute' : 'ok'}>{gone ? 'gone' : (where || 'deployed')}</Tag>
    </Tip>
  )
}

function fooocusTip(state, on) {
  if (!on) return 'Generate pictures, and offer a logo before the build'
  if (!state || state.checking) return 'Looking for Fooocus…'
  if (state.available) return `Fooocus is answering at ${state.host}`
  if (state.error) return `Could not ask the server — ${state.error}`
  return 'No Fooocus is answering — pictures will be skipped'
}

function Chip({ on, tip, children, ...rest }) {
  return (
    <Tip text={tip}>
      <button {...rest}
              className={cn('rounded-full border px-2.5 py-[3px] text-[10px]',
                'transition-colors',
                on ? 'border-accent bg-accent text-white'
                   : 'border-line text-muted hover:border-line2 hover:text-ink')}>
        {children}
      </button>
    </Tip>
  )
}

const Foot = ({ icon: Icon, tip, ...rest }) => (
  <Tip text={tip}>
    <Button size="icon" {...rest}><Icon className="size-3.5" /></Button>
  </Tip>
)
