import { expect, test } from '@playwright/test'

test('draft review and approval stay consistent', async ({ page }) => {
  const name = `e2e_offer_${Date.now().toString().slice(-6)}`
  await page.goto('/')
  await expect(page.getByText('API: connected')).toBeVisible()
  await page.getByRole('button', { name: 'Catalogue' }).click()
  await expect(page.getByLabel('Event name')).toBeVisible()
  await page.getByLabel('Event name').fill(name)
  await page.getByLabel('Description').fill('E2E offer viewed')
  await page.getByLabel('Parameter 1 name').fill('offer_id')
  await page.getByRole('button', { name: 'Create draft contract' }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible()
  await page.getByRole('button', { name: 'Submit for review' }).click()
  const reject = page.getByRole('button', { name: 'Reject' })
  await expect(reject).toBeDisabled()
  const detail = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Contract detail' }) })
  await page.getByPlaceholder('Rejection comment').fill('Needs a clearer trigger')
  await reject.click()
  await expect(detail.getByText('DRAFT', { exact: true })).toBeVisible()
  await detail.getByRole('button', { name: 'Submit for review', exact: true }).click()
  await detail.getByRole('button', { name: 'Approve', exact: true }).click()
  await expect(detail.getByText('APPROVED', { exact: true })).toBeVisible()
})
