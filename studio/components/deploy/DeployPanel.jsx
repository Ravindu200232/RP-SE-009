'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Activity, Camera, Check, FolderGit2, GitBranch, Globe,
         Loader2, RefreshCw, Rocket, ScrollText, Server, Settings2, Shield,
         Trash2, Workflow, X } from 'lucide-react'
import { useStore } from '@/lib/store'
import { api } from '@/lib/api'
import { TARGETS, TERMINAL } from '@/lib/deploy-constants'
import { useMonitor, providerOf } from '@/lib/use-monitor'
import { Badge, Button, Empty, Panel, SectionLabel } from '../ui'
import { cn } from '@/lib/utils'
import DeployProgress from './DeployProgress'
import DeployResult from './DeployResult'
import { Infrastructure, Logs, Overview, StatusBar, ago } from './MonitorViews'
import { Pipeline } from './MonitorPipeline'
import { CiCd, Repository } from './MonitorRepo'
import { ApiValidation, Security } from './MonitorSecurity'
import { Evidence } from './MonitorEvidence'
import { MonitorConsole } from './MonitorConsole'
import { DeployDanger } from './DeployDanger'
import { useRunData } from '@/lib/use-run-data'


export default function DeployPanel({ onSettings }) {
  const project = useStore(s => s.project)
  const models = useStore(s => s.models)
  const tests = useStore(s => s.tests)
  const qa = useStore(s => s.qaReport)
  const setQa = useStore(s => s.setQaReport)
  const addLog = useStore(s => s.addLog)

  const [data, setData] = useState(null)
  const [probe, setProbe] = useState(null)
  const [target, setTarget] = useState('vercel')
  const [validateBuild, setValidateBuild] = useState(true)
  const [override, setOverride] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const [view, setView] = useState('deploy')
  const alive = useRef(true)

  const mine = data?.project === project ? data : null
  const live = mine?.live
  const running = Boolean(live && !TERMINAL.has(live.state) && !live.error)

  const runId = live?.run_id || mine?.last?.run_id || ''
  const monitor = useMonitor(runId, {
    target: live?.target || mine?.last?.target || 'vercel',
    state: live?.state || mine?.last?.state || '',
    active: true,
    frozen: mine?.last?.monitor,
  })

  const run = useRunData(runId)

  const refresh = useCallback(async () => {
    if (!project) return
    try {
      const d = await api.deployResults(project)
      if (alive.current) setData(d)
    } catch (e) {
      if (alive.current) setError(e.message)
    }
  }, [project])

  useEffect(() => {
    alive.current = true
    refresh()
    return () => { alive.current = false }
  }, [refresh])

  useEffect(() => {
    if (!project || qa?.project === project) return
    let ok = true
    api.qa(project).then(d => { if (ok) setQa(d) }).catch(() => { })
    return () => { ok = false }
  }, [project, qa, setQa])

  useEffect(() => {
    if (view === 'deploy') return
    if (!viewsFor(monitor.snap).some(v => v.id === view)) setView('deploy')
  }, [view, monitor.snap])

  useEffect(() => {
    if (!running) return
    const t = setInterval(refresh, 1400)
    return () => clearInterval(t)
  }, [running, refresh])

  const reloadRun = run.reload
  useEffect(() => {
    if (!running) return
    const t = setInterval(reloadRun, 2500)
    return () => clearInterval(t)
  }, [running, reloadRun])

  useEffect(() => {
    let ok = true
    Promise.all([
      api.deployRead('/onboarding/status').catch(() => ({ error: true })),
      api.deploy('/aws/vercel/status', { token: '' }).catch(() => ({})),
    ]).then(([status, vercel]) => {
      if (ok) setProbe({
        ...status,
        vercel_connected: Boolean(vercel?.connected),
        vercel_source: vercel?.source || '',
        vercel_user: vercel?.username || vercel?.email || vercel?.name || '',
      })
    })
    return () => { ok = false }
  }, [])

  const s = mine?.settings || {}
  const unit = qa?.project === project ? qa.vitest : null

  const failures = tests.rows.length ? tests.fail
    : unit ? (unit.numFailedTests || 0) : null
  const tested = tests.rows.length > 0 || Boolean(unit)
  const green = tested && failures === 0

  const needs = [
    { id: 'github', label: 'GitHub',
      ok: Boolean(probe?.github_authenticated),
      unknown: !probe,
      hint: probe?.github_account ? `signed in as ${probe.github_account}`
                                  : 'sign in from Settings — the deploy pushes a repo' },
    target === 'vercel'
      ? { id: 'vercel', label: 'Vercel',
          ok: Boolean(s.vercel_token_set) || Boolean(probe?.vercel_connected),
          unknown: !probe && !s.vercel_token_set,

          hint: probe?.vercel_connected
            ? `signed in as ${probe.vercel_user || 'the Vercel CLI'}`
              + (probe.vercel_source ? ` (${probe.vercel_source})` : '')
            : s.vercel_token_set ? `token saved (${s.vercel_token_hint})`
                                 : 'add a token in Settings' }
      : { id: 'aws', label: 'AWS',
          ok: Boolean(s.aws_profile),
          unknown: false,
          hint: s.aws_profile ? `profile ${s.aws_profile} · ${s.aws_region || 'ap-south-1'}`
                              : 'sign in to AWS from Settings' },
    { id: 'mongo', label: 'MongoDB',
      ok: Boolean(s.mongodb_uri_set),
      unknown: false,
      hint: s.mongodb_uri_set ? `saved (${s.mongodb_uri_hint})`
                              : 'the deployed app needs a database it can reach '
                                + 'from the internet — set one in Settings' },
  ]
  const ready = needs.every(n => n.ok) && (green || override)

  async function deploy() {
    setStarting(true)
    setError('')
    try {

      await api.saveSettings({ deploy_model: models.deploy || models.agent || '' })
        .catch(() => { })
      await api.deployStart({ project, target, validate_container: validateBuild })
      addLog('INFO', `🚀 Deploying ${project} to ${target === 'vercel' ? 'Vercel' : 'AWS EC2'}`)
      await refresh()
    } catch (e) {
      setError(e.message)
    }
    setStarting(false)
  }

  if (!project) {
    return <div className="min-h-0 flex-1 overflow-auto p-5">
             <Empty>Open a project first.</Empty>
           </div>
  }

  const agent = mine?.agent
  if (agent && !agent.listening) {
    return (
      <div className="min-h-0 flex-1 overflow-auto p-5">
        <Panel className="p-4">
          <p className="flex items-start gap-2 text-[12.5px] text-bad">
            <AlertTriangle className="mt-px size-4 shrink-0" />
            <span>
              The deployment agent is not running — {agent.error || agent.state}.
              <span className="mt-1 block text-[11px] text-muted">
                Everything else in AgentForge still works; only this tab needs it.
              </span>
            </span>
          </p>
        </Panel>
      </div>
    )
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <MonitorBar view={view} setView={setView} monitor={monitor}
                  hasSnapshot={Boolean(monitor.snap)}
                  runId={runId} running={running}
                  state={live?.state || mine?.last?.state || ''}
                  onDone={() => { refresh(); run.reload() }} />

      <div className="space-y-4 p-5">
      {view !== 'deploy' ? (
        <MonitorPane view={view} monitor={monitor} runId={runId} run={run}
                     state={live?.state || mine?.last?.state || ''} />
      ) : (<>
      {mine?.deleted && !live && (
        <Panel className="p-4">
          <div className="flex items-start gap-2.5">
            <Trash2 className="mt-px size-4 shrink-0 text-muted2" />
            <div className="min-w-0">
              <p className="text-[12.5px] font-medium text-ink">
                This deployment was deleted
              </p>
              <p className="mt-0.5 text-[11.5px] text-muted">
                Its cloud resources were destroyed{mine.deleted.deleted_at
                  ? ` ${ago(mine.deleted.deleted_at)}` : ''}. The record and its
                evidence were kept in the project, under{' '}
                <span className="font-mono text-[10.5px]">
                  .agentforge/deploy-archive/{mine.deleted.archive || ''}
                </span>.
              </p>
            </div>
          </div>
        </Panel>
      )}

      {running || live ? <DeployProgress run={live} /> : null}

      {!running && (
        <Panel className="p-4">
          <SectionLabel>Where should it go?</SectionLabel>
          <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
            {TARGETS.map(t => (
              <button key={t.id} onClick={() => setTarget(t.id)}
                      className={cn('rounded-ctl border p-3 text-left transition-colors',
                        target === t.id
                          ? 'border-accent/60 bg-accent/8'
                          : 'border-line bg-bg hover:border-line2')}>
                <span className="flex items-center gap-2 text-[12.5px] font-medium text-ink">
                  <span className={cn('grid size-3.5 place-items-center rounded-full border',
                    target === t.id ? 'border-accent' : 'border-line2')}>
                    {target === t.id && <span className="size-1.5 rounded-full bg-accent" />}
                  </span>
                  {t.label}
                </span>
                <span className="mt-1 block text-[10.5px] leading-snug text-muted">
                  {t.blurb}
                </span>
              </button>
            ))}
          </div>

          <SectionLabel className="mt-4"
                        right={onSettings && (
                          <Button size="sm" onClick={onSettings}>
                            <Settings2 className="size-3" /> Settings
                          </Button>
                        )}>
            Accounts
          </SectionLabel>
          <ul className="mt-2 space-y-1">
            {needs.map(n => (
              <li key={n.id} className="flex items-start gap-2 py-[3px]">
                <span className="mt-[3px] grid size-3.5 shrink-0 place-items-center">
                  {n.unknown
                    ? <Loader2 className="size-3 animate-spin text-muted2" />
                    : n.ok ? <Check className="size-3.5 text-ok" />
                           : <X className="size-3.5 text-bad" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="text-[12px] text-ink">{n.label}</span>
                  <span className="ml-2 text-[10.5px] text-muted">{n.hint}</span>
                </span>
              </li>
            ))}
          </ul>

          {!green && (
            <label className={cn('mt-3 flex cursor-pointer items-start gap-2 rounded-ctl border',
              'px-2.5 py-2 text-[11.5px]',
              override ? 'border-warn/40 bg-warn/10 text-warn'
                       : 'border-line bg-bg text-muted')}>
              <input type="checkbox" checked={override} className="mt-0.5"
                     onChange={e => setOverride(e.target.checked)} />
              <span>
                {!tested
                  ? 'This project has not been tested in this session. Deploy anyway.'
                  : `${failures} unit test${failures === 1 ? '' : 's'} failing. Deploy anyway.`}
              </span>
            </label>
          )}
          {green && (
            <p className="mt-3 flex items-center gap-2 text-[11.5px] text-ok">
              <Check className="size-3.5" />
              Every unit test passes.
            </p>
          )}

          <label className="mt-3 flex cursor-pointer items-start gap-2 text-[11.5px] text-muted">
            <input type="checkbox" checked={validateBuild} className="mt-0.5"
                   onChange={e => setValidateBuild(e.target.checked)} />
            <span>
              Run a production build first.
              <span className="ml-1 text-muted2">
                Slower, and it catches what only fails in a real build.
                {' '}Turning it off also stops the agent from ever scoring the
                deployment as healthy.
              </span>
            </span>
          </label>

          <footer className="mt-4 flex items-center gap-2">
            <Button variant="solid" size="lg" disabled={!ready || starting}
                    onClick={deploy}>
              {starting ? <Loader2 className="size-3.5 animate-spin" />
                        : <Rocket className="size-3.5" />}
              Deploy to {target === 'vercel' ? 'Vercel' : 'AWS EC2'}
            </Button>
            {!ready && !starting && (
              <span className="text-[11px] text-muted2">
                {needs.find(n => !n.ok)
                  ? `${needs.find(n => !n.ok).label} is not connected yet`
                  : 'confirm you want to deploy a failing build'}
              </span>
            )}
          </footer>

          {error && (
            <p className="mt-3 flex items-start gap-2 rounded-ctl border border-bad/40
                          bg-bad/10 px-2.5 py-2 text-[11.5px] text-bad">
              <AlertTriangle className="mt-px size-3.5 shrink-0" /> {error}
            </p>
          )}
        </Panel>
      )}

      <DeployResult data={mine} />
      </>)}
      </div>

      {run.events.length > 0 && (
        <MonitorConsole events={run.events} snapErrors={monitor.snap?.errors} />
      )}
    </div>
  )
}


const MONITOR_VIEWS = [
  { id: 'deploy', label: 'Deploy', Icon: Rocket },
  { id: 'overview', label: 'Overview', Icon: Activity },
  { id: 'pipeline', label: 'Pipeline', Icon: Workflow },
  { id: 'repository', label: 'Repository', Icon: FolderGit2 },
  { id: 'cicd', label: 'CI/CD', Icon: GitBranch },
  { id: 'infra', label: 'Infrastructure', Icon: Server },
  { id: 'security', label: 'IAM & Security', Icon: Shield, aws: true },
  { id: 'logs', label: 'Logs', Icon: ScrollText },
  { id: 'api', label: 'API Validation', Icon: Globe },
  { id: 'evidence', label: 'Evidence', Icon: Camera },
]


function viewsFor(snap) {
  const isAws = Boolean(snap && Object.keys(snap.aws || {}).length)
  return MONITOR_VIEWS.filter(v => !v.aws || isAws)
}

function MonitorBar({ view, setView, monitor, hasSnapshot, runId, running,
                     state, onDone }) {
  const shown = hasSnapshot ? viewsFor(monitor.snap) : MONITOR_VIEWS.slice(0, 1)

  if (shown.length === 1 && !running) return null
  return (
    <div className="sticky top-0 z-10 flex items-center gap-1 border-b border-line
                    bg-panel/95 px-4 py-1.5 backdrop-blur">
      <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto
                      [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {shown.map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setView(id)}
                  className={cn('flex shrink-0 items-center gap-1.5 rounded-ctl px-2.5 py-1',
                    'text-[11px] font-medium transition-colors',
                    view === id ? 'bg-accent/12 text-accent'
                                : 'text-muted hover:bg-panel2 hover:text-ink')}>
            <Icon className="size-3" /> {label}
          </button>
        ))}
      </div>
      <span className="hidden text-[10px] text-muted2 sm:block">
        {monitor.live ? (monitor.at ? `updated ${ago(monitor.at)}` : 'live')
                      : 'from the last deployment'}
      </span>
      <Button size="sm" disabled={monitor.busy || !monitor.canRefresh}
              onClick={monitor.refresh}
              title="Ask the deployment agent for a fresh snapshot — this takes around 25 seconds">
        {monitor.busy ? <Loader2 className="size-3 animate-spin" />
                      : <RefreshCw className="size-3" />}
        Refresh
      </Button>
      <span className="mx-1 h-4 w-px bg-line" />
      <DeployDanger runId={runId} state={state} running={running} onDone={onDone} />
    </div>
  )
}

function MonitorPane({ view, monitor, runId, state, run }) {
  const snap = monitor.snap
  if (!snap) return <Empty>Nothing to show until this project has been deployed.</Empty>
  return (
    <div className="space-y-4">
      {monitor.error && (
        <p className="flex items-start gap-2 rounded-ctl border border-bad/40 bg-bad/10
                      px-2.5 py-2 text-[11.5px] text-bad">
          <AlertTriangle className="mt-px size-3.5 shrink-0" /> {monitor.error}
        </p>
      )}
      <StatusBar snap={snap} state={state} />
      {view === 'overview' && <Overview snap={snap} />}
      {view === 'pipeline' && (
        <Pipeline events={run.events} artifacts={run.artifacts} busy={run.busy} />
      )}
      {view === 'repository' && (
        <Repository snap={snap} artifacts={run.artifacts} busy={run.busy} />
      )}
      {view === 'cicd' && (
        <CiCd snap={snap} artifacts={run.artifacts} runId={runId} />
      )}
      {view === 'infra' && <Infrastructure snap={snap} />}
      {view === 'security' && (
        <Security snap={snap} events={run.events} artifacts={run.artifacts} runId={runId} />
      )}
      {view === 'logs' && <Logs snap={snap} />}
      {view === 'api' && <ApiValidation snap={snap} />}
      {view === 'evidence' && (
        <Evidence evidence={run.evidence} runId={runId} busy={run.busy} />
      )}
    </div>
  )
}
