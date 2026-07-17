import { expect, test } from "@playwright/test";

const realStackEnabled = process.env.REAL_STACK_E2E === "1";
const e2eEmail = `real-e2e-manager-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
const e2ePassword = "RealE2ePass123!";

test.describe("real seeded stack", () => {
  test.skip(!realStackEnabled, "Run this test through npm run test:e2e:real against the isolated Compose stack.");
  test.setTimeout(90_000);

  test("signs up through FastAPI, preserves the real session, and loads the seeded draft pool", async ({ page }) => {
    const apiResponses: Array<{ url: string; status: number }> = [];
    page.on("response", (response) => {
      const pathname = new URL(response.url()).pathname.replace(/^\/api/, "");
      if (pathname.startsWith("/auth/") || pathname.startsWith("/players")) {
        apiResponses.push({ url: response.url(), status: response.status() });
      }
    });

    await page.goto("/signup");
    await page.getByPlaceholder("Enter your first name").fill("Real E2E Manager");
    await page.getByPlaceholder("coach@saturday.com").fill(e2eEmail);
    await page.locator("#signup-password").fill(e2ePassword);
    await page.getByRole("button", { name: /Create Account/i }).click();

    await page.waitForURL("**/");
    await expect(page.getByText(/College Football Fantasy/i).first()).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .not.toBeNull();

    const endGuide = page.getByRole("button", { name: /End Guide/i });
    if (await endGuide.isVisible().catch(() => false)) {
      await endGuide.click();
    }

    await page.reload();
    await expect(page).not.toHaveURL(/\/login$/);

    await page.goto("/leagues");
    await expect(page).not.toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: /^Leagues$/i })).toBeVisible();

    await page.goto("/draft/mock/single-player?new=1&teams=4&timer=60");
    await expect(page).not.toHaveURL(/\/login$/);
    await expect(page.getByText("Jeremiah Smith").first()).toBeVisible();

    expect(apiResponses.some((response) => response.url.includes("/auth/signup") && response.status === 201)).toBe(true);
    expect(apiResponses.some((response) => response.url.includes("/auth/me") && response.status === 200)).toBe(true);
    expect(apiResponses.some((response) => response.url.includes("/players") && response.status === 200)).toBe(true);
  });
});
