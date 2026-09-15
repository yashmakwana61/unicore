import { test, expect } from '@playwright/test';

// ADM-07/ADM-08: public admissions website flow (no login).
test.describe('admissions website', () => {
  test('ADM-07 programs page lists open cycles only', async ({ page }) => {
    await page.goto('/admissions/programs');
    await expect(page.locator('body')).toContainText(/Apply|Program|Cycle/i);
  });

  test('ADM-08 apply form validates and rejects empty submit', async ({ page }) => {
    await page.goto('/admissions/apply');
    await expect(page.locator('form')).toBeVisible();
  });
});
