import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.CFF_NAME_CHANGE_E2E === "1";
test.describe("real API account name changes", () => {
  test.skip(!enabled, "Requires an explicitly enabled isolated local API/PostgreSQL stack");
  test.use({ timezoneId: "America/New_York" });

  async function setup(page: Page, remainingSeconds: number, legacy = false) {
    const target = new URL(process.env.E2E_BASE_URL!);
    expect(["127.0.0.1", "localhost"]).toContain(target.hostname);
    const email = `name-e2e-${crypto.randomUUID()}@example.com`;
    const response = await page.request.post("/api/auth/signup", { data: { first_name: "Old Manager", email, password: "StrongPass123!" } });
    expect(response.status()).toBe(201); const auth = await response.json();
    execFileSync(process.env.CFF_TEST_PYTHON!, [path.resolve("../scripts/seed_name_change_e2e.py"), String(auth.user.id), "--remaining-seconds", String(remainingSeconds), ...(legacy ? ["--legacy-avatar"] : [])], { env: process.env });
    await page.addInitScript((payload) => {
      localStorage.setItem("cfb_user", JSON.stringify({ id: payload.user.id, firstName: payload.user.first_name, email: payload.user.email, avatarUrl: null, isAdmin: false }));
      localStorage.setItem("cfb_access_token", payload.access_token);
      localStorage.setItem("cfb_access_token_expires_at", payload.access_token_expires_at);
      localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
      // Reproduce a wrong device clock. Backend eligibility must still unlock.
      Date.now = () => Date.parse("2000-01-01T00:00:00Z");
    }, auth);
    const reviews: string[] = [];
    page.on("request", (request) => { if (request.url().includes("/app-review/")) reviews.push(request.url()); });
    await page.goto("/settings"); return { auth, reviews };
  }

  test("expired account with legacy avatar saves, persists after reload and reports its new cooldown", async ({ page }, testInfo) => {
    const { auth, reviews } = await setup(page, -86400, true);
    const name = page.getByRole("textbox", { name: "Manager Name", exact: true }); await expect(name).toBeEnabled();
    await name.fill("Saved Browser Manager"); await page.getByRole("button", { name: "Save Changes", exact: true }).click();
    const savedResponse = page.waitForResponse((response) => response.url().endsWith("/auth/me") && response.request().method() === "PATCH");
    await page.getByRole("button", { name: "Confirm name change", exact: true }).click();
    const response = await savedResponse; expect(response.status()).toBe(200);
    expect(response.request().postDataJSON()).toEqual({ first_name: "Saved Browser Manager" });
    expect(response.request().headers()["x-cffb-profile-account"]).toBe(String(auth.user.id));
    await expect(name).toHaveValue("Saved Browser Manager"); await expect(name).toBeDisabled();
    await expect(page.getByTestId("name-change-wait")).toContainText("You can change your name again in 7 days");
    await expect(page.getByTestId("name-change-wait")).toContainText("Available:");
    await page.screenshot({ path: testInfo.outputPath("saved-name-cooldown.png"), fullPage: true });
    await page.reload(); await expect(name).toHaveValue("Saved Browser Manager"); await expect(name).toBeDisabled();
    expect(reviews).toEqual([]);
  });

  test("an open Settings page unlocks at server expiration despite wrong device time", async ({ page }, testInfo) => {
    test.setTimeout(60_000);
    await setup(page, 20);
    const name = page.getByRole("textbox", { name: "Manager Name", exact: true }); await expect(name).toBeDisabled();
    await expect(page.getByTestId("name-change-wait")).toContainText("less than a minute");
    await expect(name).toBeEnabled({ timeout: 30_000 }); await expect(page.getByTestId("name-change-wait")).toHaveCount(0);
    await name.fill("Expiration Manager"); await page.getByRole("button", { name: "Save Changes", exact: true }).click();
    await page.getByRole("button", { name: "Confirm name change", exact: true }).click();
    await expect(name).toHaveValue("Expiration Manager"); await expect(name).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath("expired-window-saved.png"), fullPage: true });
  });
});
