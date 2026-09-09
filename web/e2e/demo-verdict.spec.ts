import { expect, test } from '@playwright/test'

test.describe('demo → verdict smoke', () => {
  test('home load-demo opens experiment verdict stage', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('ink-locale', 'en')
    })

    await page.goto('/')
    await expect(page.getByTestId('load-demo-experiment').first()).toBeVisible({
      timeout: 30_000,
    })
    await page.getByTestId('load-demo-experiment').first().click()

    await expect(page).toHaveURL(/\/experiments\/exp_demo_main/, { timeout: 30_000 })
    await expect(page.locator('#experiment-verdict')).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('#experiment-verdict .ink-verdict-claim')).toBeVisible()
  })
})
