import { useEffect, useState } from 'react'
import { api } from './api'

const NONE = { vision: new Set(), known: new Set(), pending: 0 }

/** Which models can look at pictures, from what Ollama says of each (`/models/capabilities`). */
export function useVisionModels(active = true) {
  const [state, setState] = useState(NONE)
  useEffect(() => {
    if (!active) return undefined
    let alive = true
    let timer = null
    let rounds = 0
    const look = () => api.modelCapabilities().then(answer => {
      if (!alive) return
      const found = answer?.capabilities || {}
      setState({
        vision: new Set(Object.keys(found).filter(id => found[id]?.vision)),
        known: new Set(Object.keys(found)),
        pending: Number(answer?.pending || 0),
      })
      if (Number(answer?.pending || 0) > 0 && ++rounds < 25) timer = setTimeout(look, 1500)
    }).catch(() => {})
    look()
    return () => { alive = false; clearTimeout(timer) }
  }, [active])
  return state
}
