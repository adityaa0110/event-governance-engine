# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend/e2e/governance.spec.js >> review queue, AI runs, and payload check are on screen
- Location: frontend/e2e/governance.spec.js:30:1

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/", waiting until "load"

```

# Test source

```ts
  1  | import { expect, test } from '@playwright/test'
  2  | 
  3  | test('draft review and approval stay consistent', async ({ page }) => {
  4  |   const name = `e2e_offer_${Date.now().toString().slice(-6)}`
  5  |   await page.goto('/')
  6  |   await expect(page.getByText('API: connected')).toBeVisible()
  7  |   await page.getByRole('button', { name: 'Catalogue' }).click()
  8  |   await expect(page.getByLabel('Event name')).toBeVisible()
  9  |   await page.getByLabel('Event name').fill(name)
  10 |   await page.getByLabel('Description').fill('E2E offer viewed')
  11 |   await page.getByLabel('Parameter 1 name').fill('offer_id')
  12 |   await page.getByRole('button', { name: 'Create draft contract' }).click()
  13 |   await expect(page.getByRole('heading', { name })).toBeVisible()
  14 |   await page.getByRole('button', { name: 'Submit for review' }).click()
  15 |   const reject = page.getByRole('button', { name: 'Reject' })
  16 |   await expect(reject).toBeDisabled()
  17 |   const detail = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Contract detail' }) })
  18 |   await page.getByPlaceholder('Rejection comment').fill('Needs a clearer trigger')
  19 |   await reject.click()
  20 |   await expect(detail.getByText('DRAFT', { exact: true })).toBeVisible()
  21 |   await detail.getByRole('button', { name: 'Submit for review', exact: true }).click()
  22 |   await detail.getByRole('button', { name: 'Approve', exact: true }).click()
  23 |   await expect(detail.getByText('APPROVED', { exact: true })).toBeVisible()
  24 |   await expect(detail.getByRole('heading', { name: 'Version history' })).toBeVisible()
  25 |   await expect(detail.getByRole('heading', { name: 'Dependencies' })).toBeVisible()
  26 |   await detail.getByRole('button', { name: 'JSON Schema' }).click()
  27 |   await expect(detail.locator('.code')).toContainText(name)
  28 | })
  29 | 
  30 | test('review queue, AI runs, and payload check are on screen', async ({ page }) => {
> 31 |   await page.goto('/')
     |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  32 |   await expect(page.getByText('API: connected')).toBeVisible()
  33 |   await expect(page.getByRole('heading', { name: 'Waiting on you' })).toBeVisible()
  34 |   await page.getByRole('button', { name: 'Analyze PRD' }).click()
  35 |   await expect(page.getByRole('heading', { name: 'AI runs' })).toBeVisible()
  36 |   await page.getByRole('button', { name: 'Validate' }).click()
  37 |   await expect(page.getByRole('heading', { name: 'Tracking wrappers' })).toBeVisible()
  38 |   await page.getByRole('button', { name: 'Check payload' }).click()
  39 |   await expect(page.getByText('EVENT GOVERNANCE: PASSED')).toBeVisible()
  40 | })
  41 | 
```