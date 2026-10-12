// Playwright runs three QA layers against the running app: end-to-end journeys, the visual (screenshot) check and the accessibility check.
import { defineConfig, devices } from '@playwright/test'

const executablePath = process.env.PW_CHROMIUM_EXECUTABLE || undefined

export default defineConfig({
  testDir: './e2e',
  outputDir: 'test-results/artifacts',
  // A journey signs in, fills forms and waits for the server; 45s timed out under load (126 times in one project).
  timeout: 60_000,
  // Missing screenshot baselines are written, never overwritten.
  updateSnapshots: 'missing',
  expect: {
    timeout: 7_000,
    toHaveScreenshot: { maxDiffPixelRatio: 0.02, animations: 'disabled' },
  },
  // Journeys share one server and one seeded database.
  fullyParallel: false,
  workers: 2,
  retries: 1,
  reporter: [
    ['./e2e/live-reporter.js'],
    ['json', { outputFile: 'test-results/results.json' }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  snapshotPathTemplate: '{testDir}/__screenshots__/{projectName}/{arg}{ext}',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    screenshot: 'on',
    trace: 'retain-on-failure',
    // AGENTFORGE_LIVE_SLOWMO=250 slows every browser action by that many ms, to watch a run in the Studio's preview at a human pace (the default is full speed).
    launchOptions: {
      ...(executablePath ? { executablePath } : {}),
      ...(Number(process.env.AGENTFORGE_LIVE_SLOWMO) > 0 ? { slowMo: Number(process.env.AGENTFORGE_LIVE_SLOWMO) } : {}),
    },
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
})
