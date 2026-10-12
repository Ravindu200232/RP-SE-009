// UI and screenshot check: every public page, at the desktop and the mobile size.
import { test, expect, expectMatchesBaseline } from './fixtures.js'
import { publicRoutes, slug } from './routes.js'

test.describe('@visual', () => {
  for (const { route, name } of publicRoutes()) {
    test(`${name || route} looks as approved`, async ({ page }, testInfo) => {
      await test.step(`open ${route}`, async () => {
        await page.goto(route)
        await page.waitForLoadState('networkidle')
      })
      await test.step('nothing overflows the viewport', async () => {
        const overflow = await page.evaluate(() =>
          document.documentElement.scrollWidth - document.documentElement.clientWidth)
        expect(overflow, 'horizontal overflow in px').toBeLessThanOrEqual(1)
      })
      await test.step('it matches its screenshot', async () => {
        await expectMatchesBaseline(page, testInfo, slug(route))
      })
    })
  }
})
