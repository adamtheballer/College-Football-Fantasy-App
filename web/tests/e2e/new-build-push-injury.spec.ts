import { expect, test } from "@playwright/test";

const enabled = process.env.CFF_PUSH_INJURY_E2E === "1";
test.describe("Local New Build announcements and sourced injury UI", () => {
  test.skip(!enabled, "Requires designated accounts in the isolated local API");
  for (const width of [1280, 390]) {
    test(`admin preview and confirmation ${width}px`, async ({ page }, info) => {
      expect(["localhost", "127.0.0.1"]).toContain(new URL(process.env.E2E_BASE_URL!).hostname);
      await page.setViewportSize({ width, height: 900 });
      const response = await page.request.post("/api/auth/login", { data: { email: "push-browser-admin@example.com", password: "BrowserLocalPass123!" } });
      expect(response.status()).toBe(200);
      const auth = await response.json();
      await page.addInitScript((payload) => {
        localStorage.setItem("cfb_user", JSON.stringify({ id: payload.user.id, firstName: payload.user.first_name, email: payload.user.email, isAdmin: true }));
        localStorage.setItem("cfb_access_token", payload.access_token);
        localStorage.setItem("cfb_access_token_expires_at", payload.access_token_expires_at);
        localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
      }, auth);
      await page.goto("/admin/announcements");
      await expect(page.getByRole("heading", { name: "News announcements", exact: true })).toBeVisible();
      const title = `Isolated browser verification ${width} ${crypto.randomUUID()}`;
      await page.getByLabel("Announcement title").fill(title);
      await page.getByLabel("Announcement message").fill("This local-only draft verifies preview and durable confirmation.");
      await page.getByRole("button", { name: "Preview announcement", exact: true }).click();
      const preview = page.getByRole("region", { name: "Announcement preview" });
      await expect(preview).toContainText("1 eligible recipients");
      const status = page.locator("article").filter({ has: page.getByRole("heading", { name: title, exact: true }) });
      await expect(status).toContainText("draft");
      await expect(status).toContainText("No deliveries queued");
      await page.screenshot({ path: info.outputPath("announcement-preview.png"), fullPage: true, animations: "disabled" });
      await preview.getByRole("button", { name: "Confirm and queue announcement" }).click();
      await expect(status).toContainText("confirmed");
      await expect(status).toContainText("pending: 1");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });

    test(`verified injury reports and cached-error state ${width}px`, async ({ page }, info) => {
      expect(["localhost", "127.0.0.1"]).toContain(new URL(process.env.E2E_BASE_URL!).hostname);
      await page.setViewportSize({ width, height: 900 });
      const response = await page.request.post("/api/auth/login", { data: { email: "push-browser-manager@example.com", password: "BrowserLocalPass123!" } });
      expect(response.status()).toBe(200);
      const auth = await response.json();
      // Replay the isolated DB's explicitly dated Week 6 records for UI checks.
      // These are never presented as this week's pending official reports.
      const reports = await (await page.request.get("/api/injuries?season=2026&week=6", { headers: { Authorization: `Bearer ${auth.access_token}` } })).json();
      expect(reports.total).toBe(86);
      await page.route(/\/api\/players\/\d+\/card(?:\?|$)/, async route => {
        const url = new URL(route.request().url()); url.searchParams.set("injury_week", "6");
        await route.fulfill({ response: await route.fetch({ url: url.toString() }) });
      });
      let fail = false;
      await page.route(/\/api\/injuries(?:\?|$)/, route => fail ? route.fulfill({ status: 503, json: { detail: "isolated refresh failure" } }) : route.fulfill({ json: reports }));
      await page.addInitScript((payload) => {
        localStorage.setItem("cfb_user", JSON.stringify({ id: payload.user.id, firstName: payload.user.first_name, email: payload.user.email, isAdmin: false }));
        localStorage.setItem("cfb_access_token", payload.access_token);
        localStorage.setItem("cfb_access_token_expires_at", payload.access_token_expires_at);
        localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
      }, auth);
      await page.goto("/injury-center");
      await expect(page.getByText("2026 • Fantasy Week 6", { exact: true })).toBeVisible();
      const player = reports.data.find((row: { status: string }) => row.status === "OUT");
      const playerButton = page.getByRole("button", { name: new RegExp(player.player_name) });
      await expect(playerButton).toBeVisible();
      await expect(page.getByRole("link", { name: "View source" }).first()).toBeVisible();
      await expect(page.getByText("Impact not reported").first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath("verified-injury-center.png"), fullPage: true, animations: "disabled" });
      await playerButton.click();
      await expect(page.getByRole("dialog")).toContainText(player.player_name);
      await expect(page.getByRole("dialog")).toContainText(/Out/i);
      await page.keyboard.press("Escape");
      fail = true;
      await page.getByRole("button", { name: "Refresh updates" }).click();
      await expect(page.getByRole("alert").filter({ hasText: "Showing the last loaded reports" })).toBeVisible({ timeout: 15000 });
      await expect(playerButton).toBeVisible();
    });
  }
});
