import { expect, test } from "@playwright/test";

const runtime = {
  git_sha: "e2e-sha",
  git_branch: "release/beta-stabilization",
  runtime_id: "e2e-runtime",
  runtime_mode: "test",
  environment: "test",
  api_process_instance_uuid: "e2e-api",
  web_git_sha: "e2e-sha",
  worker_git_sha: "e2e-sha",
  database_instance_uuid: "e2e-db",
  alembic_revision: "0088_beta_scoring_lock",
  readiness_status: "ready",
  scoring_mode: "disabled",
  sportsdata_enabled: false,
  email_enabled: false,
  support_email: "support@example.test",
};

const user = { id: 42, first_name: "Mobile", email: "mobile@example.test", is_admin: false };

const comingSoonContest = {
  id: 1,
  season: 2026,
  week_number: 1,
  title: "Saturday Pick 6",
  contest_position: "RB",
  status: "SCHEDULED",
  lock_at: "2026-09-05T16:00:00Z",
  winning_player_ids: [],
  entry: null,
  sponsor: null,
  players: [],
};

async function seedMobileShell(page: Parameters<typeof test>[0]["page"]) {
  await page.addInitScript((storedUser) => {
    localStorage.setItem("cfb_user", JSON.stringify({
      id: storedUser.id,
      firstName: storedUser.first_name,
      email: storedUser.email,
      isAdmin: false,
    }));
    localStorage.setItem("cfb_access_token", "mobile-e2e-token");
    localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    localStorage.setItem(`cfb_completed_guide_${storedUser.id}`, "true");
  }, user);

  await page.route("**/api/**", (route) => route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({ detail: "not mocked" }),
  }));
  await page.route("**/api/health/runtime", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(runtime),
  }));
  await page.route("**/api/auth/me", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(user),
  }));
  await page.route("**/api/chats/unread-summary", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ total_unread: 0 }),
  }));
  await page.route("**/api/leagues?**", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ data: [], total: 0, limit: 20, offset: 0 }),
  }));
  await page.route("**/api/notifications/alerts?**", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ data: [] }),
  }));
  await page.route("**/api/saturday-pick-6/current?**", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(comingSoonContest),
  }));
}

const routes = [
  { path: "/", name: "dashboard" },
  { path: "/leagues", name: "leagues" },
  { path: "/league/1/matchup", name: "matchup" },
  { path: "/draft", name: "draft" },
  { path: "/saturday-pick-6", name: "saturday-pick-6" },
  { path: "/report-bug", name: "report-bug" },
];

const mobileViewports = [
  { width: 320, height: 568, name: "320x568" },
  { width: 375, height: 667, name: "375x667" },
  { width: 390, height: 844, name: "390x844" },
  { width: 430, height: 932, name: "430x932" },
];

test.describe("responsive app shell", () => {
  test("keeps key routes within the viewport and exposes the intended primary navigation", async ({ page }, testInfo) => {
    test.setTimeout(120_000);
    await seedMobileShell(page);

    const viewports = testInfo.project.name.startsWith("mobile")
      ? mobileViewports
      : [{ width: 1440, height: 900, name: "desktop" }];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      for (const route of routes) {
        await page.goto(route.path, { waitUntil: "domcontentloaded" });
        await expect(page.locator("#app-header")).toBeVisible();
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        if (testInfo.project.name.startsWith("mobile")) {
          const navigation = page.getByRole("navigation", { name: "Primary mobile navigation" });
          await expect(navigation).toBeVisible();
          await expect(navigation.getByRole("link", { name: "REPORT BUG" })).toBeVisible();
          await expect(navigation.getByRole("link", { name: "SATURDAY PICK 6" })).toHaveCount(0);
        }

        if (viewport.name === "390x844" || viewport.name === "desktop") {
          await testInfo.attach(`${route.name}-${viewport.name}-${testInfo.project.name}`, {
            body: await page.screenshot({ fullPage: true }),
            contentType: "image/png",
          });
        }
      }
    }
  });
});
