import { expect, test } from "@playwright/test";

for (const width of [390, 1280]) {
  test(`launch update opens before dashboard requests finish and stays once-only at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(() => {
      localStorage.setItem(
        "cfb_user",
        JSON.stringify({
          id: 999994,
          firstName: "Launch QA",
          email: "launch@example.invalid",
          isAdmin: false,
        }),
      );
      localStorage.setItem("cfb_access_token", "synthetic-launch-session");
      localStorage.setItem(
        "cfb_access_token_expires_at",
        "2030-01-01T00:00:00Z",
      );
      localStorage.setItem("cfb_completed_guide_999994", "true");
    });
    let releaseCards!: () => void;
    const cards = new Promise<void>((resolve) => {
      releaseCards = resolve;
    });
    let claims = 0;
    let waitingCards = 0;
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname.replace(
        /^\/api/,
        "",
      );
      let body: unknown = { data: [], total: 0 };
      if (path === "/auth/me")
        body = {
          id: 999994,
          first_name: "Launch QA",
          email: "launch@example.invalid",
        };
      else if (path === "/health/runtime")
        body = {
          git_sha: "launch-qa",
          web_git_sha: "launch-qa",
          worker_git_sha: "launch-qa",
          api_process_instance_uuid: "launch-qa",
          runtime_mode: "development",
          environment: "development",
          readiness_status: "ready",
          scoring_mode: "standard",
          sportsdata_enabled: false,
          ios_app_review_enabled: true,
        };
      else if (path === "/leagues" || path === "/notifications/alerts") {
        waitingCards++;
        await cards;
        waitingCards--;
        body = path === "/leagues" ? [] : { data: [], unread_count: 0 };
      } else if (path === "/release-notes/1.03/claim") {
        expect(route.request().method()).toBe("POST");
        expect(route.request().headers()["x-cffb-release-account"]).toBe(
          "999994",
        );
        body = {
          account_id: 999994,
          release_key: "1.03",
          authorization: ++claims === 1 ? "granted" : "already_seen",
          claimed_at: "2026-10-16T00:00:00Z",
        };
      } else if (path.includes("unread")) body = { total_unread: 0, data: [] };
      await route.fulfill({ status: 200, json: body });
    });
    try {
      await page.goto("/", { waitUntil: "domcontentloaded" });
      const dialog = page.getByRole("dialog", { name: "1.03 Update" });
      await expect(dialog).toBeVisible();
      expect(waitingCards).toBeGreaterThan(0);
      await expect(
        page.locator('[aria-label="Loading your league matchups"]'),
      ).toHaveAttribute("aria-busy", "true");
      await expect(dialog).toContainText("Hi, Launch QA.");
      const box = (await dialog.boundingBox())!;
      expect(Math.abs(box.x + box.width / 2 - width / 2)).toBeLessThanOrEqual(
        1,
      );
      await page.screenshot({
        path: info.outputPath(`instant-update-${width}.png`),
        animations: "disabled",
      });
      await dialog.getByRole("button", { name: "Next", exact: true }).click();
      await expect(
        dialog.getByRole("heading", { name: "Weekly Challenges" }),
      ).toBeVisible();
      await dialog
        .getByRole("button", { name: "Skip update", exact: true })
        .click();
      await expect(dialog).toHaveCount(0);
      expect(claims).toBe(1);
      releaseCards();
      await page.reload();
      await expect(
        page.getByText("Good to see you, Launch QA.", { exact: true }),
      ).toBeVisible();
      await expect(dialog).toHaveCount(0);
      expect(claims).toBe(1);
      // Losing device storage cannot bypass the authoritative account receipt.
      await page.evaluate(() =>
        localStorage.removeItem("cffb_update_1.03_seen_999994"),
      );
      await page.reload();
      await expect.poll(() => claims).toBe(2);
      await expect(dialog).toHaveCount(0);
    } finally {
      releaseCards();
    }
  });
}
