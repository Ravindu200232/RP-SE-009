/** Which address this browser can actually load a project's app from. */
export function previewHref(runtime) {
  if (!runtime?.previewUrl) return ''
  if (typeof location === 'undefined') return runtime.previewUrl
  if (onThisMachine()) return sameSite(runtime.previewUrl)
  return runtime.publicUrl || ''
}

const LOOPBACK = new Set(['localhost', '127.0.0.1', '[::1]', '::1'])
// The desktop app shows the Studio at agentforge://app/..., a name no browser could reach from another computer.
const DESKTOP = 'agentforge:'

export function onThisMachine() {
  if (typeof location === 'undefined') return true
  return LOOPBACK.has(location.hostname) || location.protocol === DESKTOP
}

/** The app on the same host name the Studio was opened on. */
function sameSite(url) {
  if (location.protocol === DESKTOP) return url          // there is no host name of the Studio's own to match
  try {
    const target = new URL(url)
    if (!LOOPBACK.has(target.hostname) || target.hostname === location.hostname) return url
    target.hostname = location.hostname
    return target.href
  } catch {
    return url
  }
}

/** Does this app still need an address of its own before it can be shown? */
export function needsAddress(runtime) {
  return Boolean(runtime?.previewUrl) && !previewHref(runtime)
}
