// Import `test` and `expect` from here, not from '@playwright/test'.
import fs from 'node:fs'
import path from 'node:path'
import { test as base, expect } from '@playwright/test'
import { startLiveView } from './live-view.js'

export const test = base.extend({
  allowedStatuses: [[], { option: true }],
  page: async ({ page, allowedStatuses }, use, testInfo) => {
    const problems = []
    const allowed = new Set(allowedStatuses)
    page.on('pageerror', error => problems.push(`page error: ${error.message}`))
    page.on('console', message => {
      if (message.type() !== 'error') return
      const text = message.text()
      const status = /status of (\d{3})/.exec(text)?.[1]
      if (status && allowed.has(Number(status))) return
      problems.push(`console error: ${text}`)
    })
    // Every call this test's page made to the app's own API, and what it answered.
    let origin = ''
    try { origin = new URL(testInfo.project.use?.baseURL || process.env.BASE_URL).origin } catch { /* any origin */ }
    const apiCalls = new Set()
    page.on('response', response => {
      const status = response.status()
      if (status >= 500 && !allowed.has(status)) problems.push(`HTTP ${status} ${response.url()}`)
      try {
        const url = new URL(response.url())
        if ((!origin || url.origin === origin) && /^\/api(\/|$)/.test(url.pathname)) {
          apiCalls.add(`${response.request().method()} ${url.pathname} ${status}`)
        }
      } catch { /* not a URL of the app */ }
    })
    // When the Studio started this run, what the browser shows appears in its preview.
    const stopLive = await startLiveView(page, testInfo).catch(() => async () => {})
    try {
      await use(page)
    } finally {
      await stopLive().catch(() => {})
      if (apiCalls.size) {
        await testInfo.attach('api-calls', { body: JSON.stringify([...apiCalls]), contentType: 'application/json' })
          .catch(() => {})
      }
    }
    expect(problems, 'the page reported problems').toEqual([])
  },
})

/** Call the app's own API exactly as the signed-in browser does - same cookies, same origin. */
export function apiFrom(page) {
  const call = async (method, url, body) => {
    if (page.url() === 'about:blank') throw new Error('apiFrom(page): open a page of the app first (page.goto)')
    return page.evaluate(async ({ method, url, body }) => {
      const response = await fetch(url, {
        method,
        credentials: 'include',
        headers: body === undefined ? {} : { 'content-type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      let json = null
      try { json = await response.json() } catch { /* not JSON */ }
      return { status: response.status, body: json }
    }, { method, url, body })
  }
  return {
    get: url => call('GET', url),
    post: (url, body) => call('POST', url, body ?? {}),
    put: (url, body) => call('PUT', url, body ?? {}),
    patch: (url, body) => call('PATCH', url, body ?? {}),
    delete: url => call('DELETE', url),
  }
}

/** Screenshot-match a page against its recorded baseline - the same self-recording check visual.spec.js does for signed-out public routes. */
export async function expectMatchesBaseline(page, testInfo, name) {
  const file = `${name}.png`
  const baseline = testInfo.snapshotPath(file)
  if (!fs.existsSync(baseline) && !process.env.CI && testInfo.config.updateSnapshots !== 'none') {
    fs.mkdirSync(path.dirname(baseline), { recursive: true })
    await page.screenshot({ path: baseline, fullPage: true, animations: 'disabled' })
    testInfo.annotations.push({ type: 'baseline', description: 'first run: baseline recorded, nothing to compare yet' })
    return
  }
  await expect(page).toHaveScreenshot(file, { fullPage: true })
}

export { expect }
