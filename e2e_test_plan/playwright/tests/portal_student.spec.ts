import { test, expect } from '@playwright/test';

// PS-01..PS-04: student portal dashboard, courses, results, fees.
test.describe('student portal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/web/login');
    await page.fill('input[name="login"]', process.env.STUDENT_LOGIN!);
    await page.fill('input[name="password"]', process.env.STUDENT_PASSWORD!);
    await page.click('button[type="submit"]');
    await expect(page).not.toHaveURL(/login/);
  });

  test('PS-01 dashboard counters visible', async ({ page }) => {
    await page.goto('/my/oacis/student');
    await expect(page.locator('body')).toContainText(/Courses|Assignments|Fees|CGPA/i);
  });

  test('PS-03 results show only published grades', async ({ page }) => {
    await page.goto('/my/oacis/student/results');
    // Draft/internal marks must never leak to the portal.
    await expect(page.locator('body')).not.toContainText(/Draft/i);
  });
});
