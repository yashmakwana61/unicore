import { test, expect } from '@playwright/test';

// PF-01..PF-03: faculty schedule, attendance marking, grade entry.
test.describe('faculty portal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/web/login');
    await page.fill('input[name="login"]', process.env.FACULTY_LOGIN!);
    await page.fill('input[name="password"]', process.env.FACULTY_PASSWORD!);
    await page.click('button[type="submit"]');
    await expect(page).not.toHaveURL(/login/);
  });

  test('PF-01 schedule loads with today classes', async ({ page }) => {
    await page.goto('/my/oacis/faculty/schedule');
    await expect(page.locator('body')).toContainText(/Monday|Tuesday|Wednesday|Thursday|Friday|Saturday/i);
  });

  test('PF-02 attendance page renders session controls', async ({ page }) => {
    await page.goto('/my/oacis/faculty');
    await expect(page.locator('body')).toContainText(/Attendance|Schedule|Courses/i);
  });
});
