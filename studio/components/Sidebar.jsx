'use client'

import { useMemo, useRef, useState } from 'react'
import {
  Moon, Sun, FolderUp, Settings, Download, ExternalLink, Search, Play,
} from 'lucide-react'
import { useStore, KEYS } from '@/lib/store'
import { api } from '@/lib/api'
import { isCloud, hasVision, maxContext, roomyContext } from '@/lib/models'
import ModelPicker from './ModelPicker'
import { Badge, Button, Input, SectionLabel, Tag, Tip } from './ui'
import { cn } from '@/lib/utils'


export default function Sidebar({
  models: cat, projects, onOpen, onImport, onSettings, onZip, onResume,
}) {
  const s = useStore()
  const { models, agentMode, think, images, project, status, statusText, theme } = s
  const folderRef = useRef(null)
  const [q, setQ] = useState('')

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
        <span className="grid size-[34px] shrink-0 place-items-center rounded-[10px]
                         border border-line
                         bg-[radial-gradient(120%_120%_at_20%_0%,rgba(91,124,247,.35),transparent_70%)]
                         font-display text-[15px] font-extrabold text-accent">
          A
        </span>
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
        <Chip on={images} onClick={() => toggle('images', KEYS.images)}
              tip="Generate pictures, and offer a logo before the build">
          Images
        </Chip>
      </div>

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
          return (
            <button key={name} onClick={() => onOpen(name)}
                    className={cn('flex w-full items-center gap-2 rounded-ctl px-2 py-[7px]',
                      'text-left transition-colors',
                      on ? 'bg-accent/12' : 'hover:bg-panel2')}>
              <span className={cn('size-[5px] shrink-0 rounded-full',
                                  on ? 'bg-accent' : 'bg-muted2')} />
              <span className="min-w-0 flex-1">
                <span className={cn('block truncate text-[11.5px] leading-tight',
                                    on ? 'text-accent' : 'text-ink')}>
                  {p.title || name}
                </span>
                <span className="mt-px block truncate font-mono text-[9px] text-muted2">
                  {p.stack || 'next'}{p.file_count ? ` · ${p.file_count}` : ''}
                </span>
              </span>
              <DeployTag deployed={p.deployed} />
              {p.unfinished ? <Badge tone="bad">{p.unfinished}</Badge> : null}
            </button>
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
