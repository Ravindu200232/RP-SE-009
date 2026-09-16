'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Activity, Camera, Check, FolderGit2, GitBranch, Globe,
         Loader2, RefreshCw, Rocket, ScrollText, Server, Settings2, Shield,
         Trash2, Workflow, X } from 'lucide-react'
import { useStore } from '@/lib/store'
import { api } from '@/lib/api'
import { TARGETS, TERMINAL } from '@/lib/deploy-constants'
import { useMonitor } from '@/lib/use-monitor'
import { Button, Empty, SectionLabel, SubTab, SubTabs } from '../ui'
import { cn } from '@/lib/utils'
import DeployProgress from './DeployProgress'
import DeployResult from './DeployResult'
import DeployInterview from './DeployInterview'
import DeployActivity, { DeploymentQuestion } from './DeployActivity'
import { Infrastructure, Logs, Overview, StatusBar, ago } from './MonitorViews'
import { Pipeline } from './MonitorPipeline'
import { CiCd, Repository } from './MonitorRepo'
import { ApiValidation, Security } from './MonitorSecurity'
import { Evidence } from './MonitorEvidence'
import { MonitorConsole } from './MonitorConsole'
import { DeployDanger } from './DeployDanger'
import { useRunData } from '@/lib/use-run-data'
import { projectUnitTestStatus } from '@/lib/test-counts'


export default function DeployPanel({ onSettings, accountsRevision = 0 }) {
  const project = useStore(s => s.project)
  const qa = useStore(s => s.qaReport)
  const setQa = useStore(s => s.setQaReport)

  const [data, setData] = useState(null)
  const [probe, setProbe] = useState(null)
  const [target, setTarget] = useState('vercel')
  const [answers, setAnswers] = useState({})
  const [override, setOverride] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const [view, setView] = useState('deploy')
  const alive = useRef(true)
  const currentProject = useRef(project)
  currentProject.current = project
  const currentAccountsRevision = useRef(accountsRevision)
  currentAccountsRevision.current = accountsRevision

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
      if (alive.current && currentProject.current === project && currentAccountsRevision.current === accountsRevision) setData(d)
    } catch (e) {
      if (alive.current && currentProject.current === project && currentAccountsRevision.current === accountsRevision) setError(e.message)
    }
  }, [project, accountsRevision])

  useEffect(() => {
    alive.current = true
    refresh()
    return () => { alive.current = false }
  }, [refresh])

  useEffect(() => {
    setData(null); setAnswers({}); setError(''); setOverride(false); setView('deploy')
  }, [project])
  useEffect(() => {
    if (mine) { setAnswers(mine.customization || {}); setTarget(mine.last?.target || mine.live?.target || 'vercel') }
  }, [mine?.project])

      // Refresh the deployment state read on mount.
  const FINISHED = ['DESTROYED', 'CANCELLED', 'FAILED', 'ROLLED_BACK']
  const snapAt = monitor.at
  useEffect(() => {
    if (!snapAt) return
    const state = live?.state || mine?.last?.state || ''
    if (state && FINISHED.includes(state)) return
    refresh()
  }, [snapAt])

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
    setProbe(null)
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
  }, [accountsRevision])

  // Vercel runs a Next.js app. A workspace of services goes to AWS, and EC2 is
  // where it starts, because it is the one that stays inside the free tier.
  const targets = mine?.stack === 'mern-microservices'
    ? TARGETS.filter(t => t.id.startsWith('aws_')) : TARGETS
  useEffect(() => {
    if (!targets.some(t => t.id === target)) setTarget('aws_ec2')
  }, [targets, target])
  const where = TARGETS.find(t => t.id === target)?.label || target

  const s = mine?.settings || {}
  const unit = projectUnitTestStatus(qa, project)
  const failures = unit?.failed ?? null
  const tested = Boolean(unit?.tested)
  const green = tested && failures === 0

  const needs = [
    { id: 'github', label:'GitHub',
      ok: Boolean(probe?.github_authenticated),
      unknown: !probe,
      hint: probe?.github_account ? `signed in as ${probe.github_account}`
                                  : 'sign in from Settings — the deploy pushes a repo' },
    target === 'vercel'
      ? { id: 'vercel', label:'Vercel',
          ok: Boolean(s.vercel_token_set) || Boolean(probe?.vercel_connected),
          unknown: !probe && !s.vercel_token_set,

          hint: probe?.vercel_connected
            ? `signed in as ${probe.vercel_user || 'the Vercel CLI'}`
              + (probe.vercel_source ? ` (${probe.vercel_source})` : '')
            : s.vercel_token_set ? `token saved (${s.vercel_token_hint})`
                                 : 'add a token in Settings' }
      : target === 'netlify' || target === 'azure'
        ? { id: target, label: target === 'netlify' ? 'Netlify' : 'Azure',
            ok: Boolean(s[target === 'netlify' ? 'netlify_token_set' : 'azure_credentials_set']), unknown: false,
            hint: s[target === 'netlify' ? 'netlify_token_set' : 'azure_credentials_set'] ? 'credentials saved' : 'add credentials in Settings' }
      : { id: 'aws', label:'AWS',
          ok: Boolean(probe?.aws_identities?.[s.aws_profile]),
          unknown: !probe,
          hint: probe?.aws_identities?.[s.aws_profile]
            ? `profile ${s.aws_profile} · ${probe.aws_identities[s.aws_profile].role_name || 'authenticated'} · ${s.aws_region || 'ap-south-1'}`
            : s.aws_profile
              ? `profile ${s.aws_profile} needs sign-in or has expired`
              : 'sign in to AWS from Settings' },
    ...(mine?.database_required ? [{ id: 'mongo', label:'MongoDB',
      ok: Boolean(s.mongodb_uri_set),
      unknown: false,
      hint: s.mongodb_uri_set ? `saved (${s.mongodb_uri_hint})`
                              : 'the deployed app needs a database it can reach'
                                + 'from the internet — set one in Settings' }] : []),
  ]
  const ready = needs.every(n => n.ok) && (green || override)
  const redeploy = Boolean(mine?.last?.run_id && !mine?.deleted && mine.last.target === target)

  async function deploy() {
    setStarting(true)
    setError('')
    try {
      await api.deployStart({ project, target, validate_container: true, customization: answers })
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
        <div className="rounded-[20px] border border-accent/20 bg-accent/[.055] p-4 shadow-sm">
          <p className="flex items-start gap-2.5 text-[12.5px] text-deep">
            <AlertTriangle className="mt-px size-4 shrink-0 text-accent" />
            <span>
              The deployment agent is not running — {agent.error || agent.state}.
              <span className="mt-1 block text-[11px] text-muted">
                Everything else in AgentForge still works; only this tab needs it.
              </span>
            </span>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_top_right,rgba(24,119,242,.08),transparent_30%)]">
      <MonitorBar view={view} setView={setView} monitor={monitor}
                  hasSnapshot={Boolean(monitor.snap)}
                  runId={runId} running={running}
                  state={live?.state || mine?.last?.state || ''}
                  onDone={() => { refresh(); run.reload() }} />

      {view !== 'deploy' && monitor.snap && (
        <StatusBar snap={monitor.snap}
                   state={live?.state || mine?.last?.state || ''} />
      )}

      <div className="mx-auto max-w-[1180px] space-y-4 p-5">
      {view !== 'deploy' ? (
        <MonitorPane view={view} monitor={monitor} runId={runId} run={run}
                     state={live?.state || mine?.last?.state || ''} />
      ) : (<>
      {mine?.deleted && !live && (
        <div className="rounded-[20px] border border-line/80 bg-white/50 p-4 shadow-sm dark:bg-white/[.025]">
          <div className="flex items-start gap-2.5">
            <Trash2 className="mt-px size-4 shrink-0 text-muted2" />
            <div className="min-w-0">
              <p className="text-[12.5px] font-extrabold text-ink">
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
        </div>
      )}

      {running || live ? <DeployProgress run={live} /> : null}
      <DeploymentQuestion question={run.question} runId={runId} onAnswered={run.reload} />

      {!running && (
        <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] p-6 shadow-[0_0_2px_0_rgba(145,158,171,0.2),0_12px_24px_-4px_rgba(0,0,0,0.16)] backdrop-blur-xl">
          <SectionLabel>Where should it go?</SectionLabel>
          <p className="mt-1 text-[11.5px] text-[#919EAB]">Choose the cloud destination for this reviewed build.</p>
          <div className="mt-3.5 grid gap-3 sm:grid-cols-2">
            {targets.map(t => (
              <button key={t.id} onClick={() => setTarget(t.id)}
                      className={cn('rounded-xl border p-4 text-left shadow-sm transition-all',
                        target === t.id
                          ? 'border-[#1877F2] bg-[#1877F2]/10 ring-1 ring-[#1877F2]/30'
                          : 'border-[rgba(145,158,171,0.16)] bg-[#28323D]/50 hover:-translate-y-0.5 hover:border-[rgba(145,158,171,0.28)] hover:bg-[#333F4D]/50')}>
                <span className="flex items-center gap-2.5 text-[13px] font-bold text-white">
                  <span className={cn('grid size-4 place-items-center rounded-full border',
                    target === t.id ? 'border-[#1877F2] bg-[#1877F2]' : 'border-[rgba(145,158,171,0.32)] bg-[#28323D]')}>
                    {target === t.id && <Check className="size-2.5 text-white" />}
                  </span>
                  {t.label}
                </span>
                <span className="mt-1.5 block text-[11px] leading-relaxed text-[#919EAB]">
                  {t.blurb}
                </span>
              </button>
            ))}
          </div>

          <SectionLabel className="mt-6"
                        right={onSettings && (
                          <Button variant="outline" size="sm" className="rounded-xl border-[rgba(145,158,171,0.2)] bg-[#28323D]/60 text-white/90 hover:bg-[#333F4D]" onClick={onSettings}>
                            <Settings2 className="size-3" /> Settings
                          </Button>
                        )}>
            Accounts
          </SectionLabel>
          <ul className="mt-3 grid gap-2.5 sm:grid-cols-2">
            {needs.map(n => (
              <li key={n.id} className={cn('flex items-start gap-2.5 rounded-xl border px-3.5 py-3',
                n.unknown ? 'border-[rgba(145,158,171,0.16)] bg-[#28323D]/30'
                  : n.ok ? 'border-[#22C55E]/20 bg-[#22C55E]/10' : 'border-[#FF5630]/20 bg-[#FF5630]/10')}>
                <span className="mt-[2px] grid size-3.5 shrink-0 place-items-center">
                  {n.unknown
                    ? <Loader2 className="size-3 animate-spin text-[#919EAB]" />
                    : n.ok ? <Check className="size-3.5 text-[#22C55E]" />
                           : <X className="size-3.5 text-[#FF5630]" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="text-[12px] font-semibold text-white">{n.label}</span>
                  <span className={cn('ml-2 text-[11px]',
                                      n.unknown || n.ok ? 'text-[#919EAB]' : 'text-[#FF5630]')}>
                    {n.hint}
                  </span>
                </span>
              </li>
            ))}
          </ul>

          {!green && (
            <label className={cn('mt-4 flex cursor-pointer items-start gap-2.5 rounded-xl border px-3.5 py-3 text-[12px]',
              override ? 'border-accent/30 bg-accent/10 text-white'
                       : 'border-[rgba(145,158,171,0.16)] bg-[#28323D]/30 text-[#919EAB]')}>
              <input type="checkbox" checked={override} className="mt-0.5 accent-[#1877F2]"
                     onChange={e => setOverride(e.target.checked)} />
              <span>
                {!tested
                  ? 'This project has not been tested in this session. Deploy anyway.'
                  : `${failures} unit test${failures === 1 ? '' : 's'} failing. Deploy anyway.`}
              </span>
            </label>
          )}
          {green && (
            <p className="mt-4 flex items-center gap-2.5 rounded-xl border border-[#22C55E]/20 bg-[#22C55E]/10 px-3.5 py-3 text-[12px] text-[#22C55E]">
              <Check className="size-3.5 text-[#22C55E]" />
              Every unit test passes.
            </p>
          )}

          <DeployInterview project={project} target={target} value={answers} onChange={setAnswers} redeploy={redeploy} />
          <p className="mt-3 text-[11px] text-[#919EAB]">The agent validates the production build and repairs deployment failures before delivery.</p>

          <footer className="mt-6 flex items-center gap-3 border-t border-[rgba(145,158,171,0.16)] pt-4">
            <Button variant="solid" size="lg" className="h-11 rounded-xl bg-[#1877F2] px-6 font-display text-[13px] font-bold text-white shadow-[0_8px_16px_0_rgba(24,119,242,0.24)] hover:bg-[#0C44AE]" disabled={!ready || starting}
                    onClick={deploy}>
              {starting ? <Loader2 className="size-3.5 animate-spin" />
                        : <Rocket className="size-3.5" />}
              {redeploy ? 'Redeploy' : 'Deploy'} to {where}
            </Button>
            {!ready && !starting && (
              <span className="text-[11.5px] text-[#919EAB]">
                {needs.find(n => !n.ok)
                  ? `${needs.find(n => !n.ok).label} is not connected yet`
                  : 'confirm you want to deploy a failing build'}
              </span>
            )}
          </footer>

          {error && (
            <p className="mt-3 flex items-start gap-2.5 rounded-2xl border border-bad/20 bg-bad/[.045] px-3 py-3 text-[11.5px] text-bad">
              <AlertTriangle className="mt-px size-3.5 shrink-0 text-accent" /> {error}
            </p>
          )}
        </div>
      )}

      <DeployResult data={mine} />
      </>)}
      </div>

      <div className="sticky bottom-0 z-10 bg-panel">
        <MonitorConsole key={`console-${runId}`} events={run.events} snapErrors={monitor.snap?.errors} />
        <DeployActivity key={`activity-${runId}`} events={run.events} running={running} />
      </div>
    </div>
  )
}


const MONITOR_VIEWS = [
  { id: 'deploy', label:'Deploy', Icon: Rocket },
  { id: 'overview', label:'Overview', Icon: Activity },
  { id: 'pipeline', label:'Pipeline', Icon: Workflow },
  { id: 'repository', label:'Repository', Icon: FolderGit2 },
  { id: 'cicd', label:'CI/CD', Icon: GitBranch },
  { id: 'infra', label:'Infrastructure', Icon: Server },
  { id: 'security', label:'IAM & Security', Icon: Shield, aws: true },
  { id: 'logs', label:'Logs', Icon: ScrollText },
  { id: 'api', label:'API Validation', Icon: Globe },
  { id: 'evidence', label:'Evidence', Icon: Camera },
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
    <SubTabs className="sticky top-0 z-10">
      {shown.map(({ id, label, Icon }) => (
        <SubTab key={id} on={view === id} onClick={() => setView(id)}>
          <Icon className="size-3" /> {label}
        </SubTab>
      ))}
      <span className="flex-1" />
      <span className="hidden shrink-0 items-center px-3 font-mono text-[10px]
                       text-muted2 sm:flex">
        {monitor.live ? (monitor.at ? `updated ${ago(monitor.at)}` : 'live')
                      : 'from the last deployment'}
      </span>
      <span className="flex shrink-0 items-center gap-2 px-3">
        <Button variant="outline" size="sm"
                disabled={monitor.busy || !monitor.canRefresh}
                onClick={monitor.refresh}
                title="Ask the deployment agent for a fresh snapshot — this takes around 25 seconds">
          {monitor.busy ? <Loader2 className="size-3 animate-spin" />
                        : <RefreshCw className="size-3" />}
          Refresh
        </Button>
        <DeployDanger runId={runId} state={state} running={running} onDone={onDone} />
      </span>
    </SubTabs>
  )
}

function MonitorPane({ view, monitor, runId, state, run }) {
  const snap = monitor.snap
  if (!snap) return <Empty>Nothing to show until this project has been deployed.</Empty>
  return (
    <div className="space-y-4">
      {monitor.error && (
        <p className="flex items-start gap-2.5 rounded-2xl border border-bad/20 bg-bad/[.045] px-3 py-3 text-[11.5px] text-bad">
          <AlertTriangle className="mt-px size-3.5 shrink-0 text-accent" /> {monitor.error}
        </p>
      )}
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
