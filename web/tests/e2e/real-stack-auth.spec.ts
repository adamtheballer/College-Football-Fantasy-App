import { expect, test } from "@playwright/test";

const realStackEnabled = process.env.REAL_STACK_E2E === "1";
const e2eEmail = process.env.E2E_AUTH_EMAIL ?? "ci-beta-user@example.test";
const e2ePassword = "RealE2ePass123!";

test.describe("real seeded stack", () => {
  test.skip(!realStackEnabled, "Run this test through npm run test:e2e:real against the isolated Compose stack.");
  test.setTimeout(90_000);

  test("allows open signup and preserves the returning session", async ({ page }) => {
    const apiResponses: Array<{ url: string; status: number }> = [];
    page.on("response", (response) => {
      const pathname = new URL(response.url()).pathname.replace(/^\/api/, "");
      if (pathname.startsWith("/auth/")) {
        apiResponses.push({ url: response.url(), status: response.status() });
      }
    });

    await page.goto("/signup");
    await expect(page).toHaveURL(/\/login\?flow=signup$/);
    await expect(page.getByRole("heading", { name: /Create account/i })).toBeVisible();
    await expect(page.locator("#signup-email")).not.toHaveAttribute("readonly", "");
    await page.locator("#signup-email").fill(e2eEmail);
    await page.locator("#signup-name").fill("Real E2E Manager");
    await page.locator("#signup-password").fill(e2ePassword);
    await page.getByRole("button", { name: /Create (beta )?account/i }).click();
    await expect(page.getByRole("dialog", { name: /Account created/i })).toHaveCount(0);
    await page.waitForURL("**/");
    await expect(page.getByRole("heading", { name: /Good to see you, Real E2E/i })).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .not.toBeNull();

    const endGuide = page.getByRole("button", { name: /End Guide/i });
    await expect(endGuide).toBeVisible();
    const updateClaim = page.waitForResponse((response) =>
      new URL(response.url()).pathname.endsWith("/release-notes/1.03/claim") &&
      response.request().method() === "POST",
    );
    await endGuide.click();
    expect((await (await updateClaim).json()).authorization).toBe("granted");
    const update = page.getByRole("dialog", { name: "1.03 Update" });
    await expect(update).toBeVisible();
    await expect(update.getByText("Hi, Real E2E Manager.")).toBeVisible();
    await update.getByRole("button", { name: "Next", exact: true }).click();
    await expect(update.getByRole("heading", { name: "Weekly Challenges", exact: true })).toBeVisible();
    for (let step = 2; step < 10; step += 1) {
      await update.getByRole("button", { name: "Next", exact: true }).click();
    }
    await expect(update.getByText("10 of 10")).toBeVisible();
    await expect(update.getByRole("heading", { name: "Help shape CFFB" })).toBeVisible();
    await update.getByRole("button", { name: "Got it", exact: true }).click();
    await expect(update).toHaveCount(0);

    await page.reload();
    await expect(page).not.toHaveURL(/\/login$/);

    await page.goto("/leagues");
    await expect(page).toHaveURL(/\/leagues$/);
    await expect(update).toHaveCount(0);

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
    await expect(update).toHaveCount(0);
  });
});
