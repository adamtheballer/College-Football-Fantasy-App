import { expect, test } from "@playwright/test";

const enabled = process.env.CFF_HOME_E2E === "1";
test.describe("Home without outdated Pick 6", () => {
  test.skip(!enabled, "Requires the isolated local API");
  for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
    for (const authenticated of [false, true]) {
      test(`${authenticated ? "authenticated" : "guest"} Home ${viewport.width}px`, async ({ page }, info) => {
        await page.setViewportSize(viewport);
        expect(["localhost", "127.0.0.1"]).toContain(new URL(process.env.E2E_BASE_URL!).hostname);
        if (authenticated) {
          const response = await page.request.post("/api/auth/signup", { data: { first_name: "Home Check Manager", email: `home-e2e-${crypto.randomUUID()}@example.com`, password: "StrongPass123!" } });
          expect(response.status()).toBe(201);
          const auth = await response.json();
          await page.addInitScript((payload) => {
            localStorage.setItem("cfb_user", JSON.stringify({ id: payload.user.id, firstName: payload.user.first_name, email: payload.user.email, isAdmin: false }));
            localStorage.setItem("cfb_access_token", payload.access_token);
            localStorage.setItem("cfb_access_token_expires_at", payload.access_token_expires_at);
            localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
          }, auth);
        }
        const reviewRequests: string[] = [];
        const contestRequests: string[] = [];
        page.on("request", request => {
          if (request.url().includes("/app-review/")) reviewRequests.push(request.url());
          if (request.url().includes("/saturday-pick-6")) contestRequests.push(request.url());
        });
        await page.goto("/");
        if (authenticated) {
          await expect(page.getByRole("heading", { name: "Good to see you, Home Check Manager." })).toBeVisible();
          await expect(page.getByText("Roster Status", { exact: true })).toBeVisible();
        } else {
          await expect(page.getByRole("heading", { name: "Play College Fantasy Football in 2026" })).toBeVisible();
          await expect(page.getByText("Waivers", { exact: true })).toBeVisible();
        }
        await expect(page.locator("main")).not.toContainText(/pick\s*6|make your pick/i);
        await expect(page.locator('main a[href="/saturday-pick-6"]')).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await page.screenshot({ path: info.outputPath("home-without-pick6.png"), fullPage: true });
        if (authenticated) {
          await page.getByRole("button", { name: "Create League", exact: true }).click();
          await expect(page).toHaveURL(/\/leagues\/create$/);
        } else {
          await page.getByRole("link", { name: "Create a League", exact: true }).click();
          await expect(page).toHaveURL(/\/login\?flow=signup$/);
        }
        expect(reviewRequests).toEqual([]);
        expect(contestRequests).toEqual([]);
      });
    }
  }
});
