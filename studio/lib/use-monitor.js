'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { TERMINAL } from '@/lib/deploy-constants'


const CADENCE = { vercel: 20000, netlify: 20000, azure: 35000, aws_ec2: 35000, aws_ecs: 40000 }
const REQUEST_DEADLINE = 90000

export function useMonitor(runId, { target, state, active, frozen } = {}) {
  const [snap, setSnap] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [at, setAt] = useState(null)
  const inFlight = useRef(false)
  const abort = useRef(null)
  const alive = useRef(true)
  const currentRun = useRef(runId)
  currentRun.current = runId

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      abort.current?.abort()
    }
  }, [])

  const refresh = useCallback(async () => {
    if (!runId || inFlight.current === runId) return
    inFlight.current = runId
    setBusy(true)
    setError('')
    const ctl = new AbortController()
    abort.current = ctl
    const bell = setTimeout(() => ctl.abort(), REQUEST_DEADLINE)
    try {
      const d = await api.deployRead(`/runs/${runId}/monitor`, { signal: ctl.signal })
      if (alive.current && currentRun.current === runId) { setSnap({ runId, value: d }); setAt(Date.now()) }
    } catch (e) {
      if (alive.current && currentRun.current === runId && e.message !== 'cancelled') setError(e.message)
    } finally {
      clearTimeout(bell)
      if (inFlight.current === runId) inFlight.current = false
      if (alive.current && currentRun.current === runId) setBusy(false)
    }
  }, [runId])

  // A snapshot belongs to the run it was fetched for.
  useEffect(() => {
    abort.current?.abort()
    setSnap(null)
    setError('')
    setAt(null)
  }, [runId])

  const watching = Boolean(
    runId && active &&
    (state === 'VALIDATING' || (state === 'LIVE' && !snap))
  )

  useEffect(() => {
    if (!watching) return
    const every = CADENCE[target] || CADENCE.vercel
    const tick = () => { if (!document.hidden) refresh() }
    tick()
    const id = setInterval(tick, every)
    return () => clearInterval(id)
  }, [watching, target, refresh])

  return {
    snap: (snap?.runId === runId ? snap.value : null) || frozen || null,
    live: snap?.runId === runId,
    busy, error, at,
    refresh,
    canRefresh: Boolean(runId),
  }
}
