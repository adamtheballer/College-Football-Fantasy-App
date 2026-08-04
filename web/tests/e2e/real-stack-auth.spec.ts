import { expect, test } from "@playwright/test";

const realStackEnabled = process.env.REAL_STACK_E2E === "1";
const e2eEmail = "ci-beta-user@example.test";
const e2eCode = "EARLY-CI1234";
const e2ePassword = "RealE2ePass123!";

test.describe("real seeded stack", () => {
  test.skip(!realStackEnabled, "Run this test through npm run test:e2e:real against the isolated Compose stack.");
  test.setTimeout(90_000);

  test("enforces and redeems beta access before account creation, then preserves the returning session", async ({ page }) => {
    const apiResponses: Array<{ url: string; status: number }> = [];
    page.on("response", (response) => {
      const pathname = new URL(response.url()).pathname.replace(/^\/api/, "");
      if (pathname.startsWith("/auth/")) {
        apiResponses.push({ url: response.url(), status: response.status() });
      }
    });

    await page.goto("/signup");
    await expect(page).toHaveURL(/\/login\?flow=beta$/);
    await expect(page.getByRole("heading", { name: /Join the beta/i })).toBeVisible();

    await page.locator("#beta-email").fill(e2eEmail);
    await page.locator("#beta-code").fill("WRONG1");
    await page.getByRole("button", { name: /Verify and continue/i }).click();
    await expect(page.getByRole("alert")).toContainText(/do not match|no longer available/i);

    await page.locator("#beta-code").fill(e2eCode);
    await page.getByRole("button", { name: /Verify and continue/i }).click();
    await expect(page.getByRole("heading", { name: /Create (your )?account/i })).toBeVisible();
    await expect(page.locator("#signup-email")).toHaveValue(e2eEmail);
    await expect(page.locator("#signup-email")).toHaveAttribute("readonly", "");
    await page.locator("#signup-name").fill("Real E2E Manager");
    await page.locator("#signup-password").fill(e2ePassword);
    await page.getByRole("button", { name: /Create (beta )?account/i }).click();
    await expect(page.getByRole("dialog", { name: /Account created/i })).toBeVisible();
    await page.getByRole("button", { name: /Continue to dashboard/i }).click();
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
    await expect(page).toHaveURL(/\/leagues$/);

    expect(apiResponses.some((response) => response.url.includes("/auth/signup") && response.status === 201)).toBe(true);

    await page.locator("button:has(#nav-sign-out)").click();
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .toBeNull();
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
    await page.locator("#login-email").fill(e2eEmail);
    await page.locator("#login-password").fill(e2ePassword);
    await page.getByRole("button", { name: /Sign in to dashboard/i }).click();
    await page.waitForURL("**/");

    await page.goto("/leagues");
    await expect(page).toHaveURL(/\/leagues$/);
    await page.locator("button:has(#nav-sign-out)").click();
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .toBeNull();
    await page.goto("/login?flow=beta");
    await page.locator("#beta-email").fill(e2eEmail);
    await page.locator("#beta-code").fill(e2eCode);
    await page.getByRole("button", { name: /Verify and continue/i }).click();
    await expect(page.getByRole("alert")).toContainText(/do not match|no longer available/i);
  });
});
