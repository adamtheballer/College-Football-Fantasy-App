import { expect, test } from "@playwright/test";

const mockAuthPayload = {
  access_token: "mock-access-token",
  access_token_expires_at: "2030-01-01T00:00:00Z",
  user: {
    id: 42,
    first_name: "Adam",
    email: "adam@example.com",
  },
};

const mockPlayer = {
  id: 1,
  external_id: "espn:999001",
  name: "Jeremiah Smith",
  position: "WR",
  school: "Ohio State",
  image_url: null,
  player_class: "Sophomore",
  sheet_adp: 1,
  sheet_projected_season_points: 315.5,
  sheet_projection_stats: {
    receptions: 82,
    rec_yards: 1305,
    rec_tds: 12,
  },
  sheet_source_sheet_id: "test-sheet",
  sheet_synced_at: "2026-07-11T00:00:00Z",
  board_rank: 1,
  created_at: "2026-07-11T00:00:00Z",
  updated_at: "2026-07-11T00:00:00Z",
};

const seedAuthenticatedSession = async (page: Parameters<typeof test>[0]["page"]) => {
  await page.addInitScript((payload) => {
    window.localStorage.setItem(
      "cfb_user",
      JSON.stringify({
        id: payload.user.id,
        firstName: payload.user.first_name,
        email: payload.user.email,
      })
    );
    window.localStorage.setItem("cfb_access_token", payload.access_token);
    window.localStorage.setItem("cfb_access_token_expires_at", payload.access_token_expires_at);
    window.localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
  }, mockAuthPayload);

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockAuthPayload.user),
    });
  });
  await page.route("**/notifications/preferences**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        push_enabled: true,
        email_enabled: true,
        draft_alerts: true,
        injury_alerts: true,
        touchdown_alerts: false,
        usage_alerts: true,
        waiver_alerts: true,
        projection_alerts: true,
        lineup_reminders: true,
        quiet_hours_start: null,
        quiet_hours_end: null,
      }),
    });
  });
};

test.describe("player card modal", () => {
  test("opens centered with ESPN profile details and closes from X or backdrop", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.route("**/stats/teams**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [{ team: "Ohio State", conference: "Big Ten" }] }),
      });
    });
    await page.route("**/players**", async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith("/players/1/card")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            player: mockPlayer,
            about: {
              espn_player_id: "999001",
              height: "6'3\"",
              weight: "215 lbs",
              player_class: "Sophomore",
              birthplace: "Columbus, Ohio",
              status: "Active",
              jersey: "4",
              position: "WR",
              team: "Ohio State Buckeyes",
              headshot_url: null,
              source: "espn",
              message: null,
            },
            injuries: [],
            season_stats: [
              {
                season: 2025,
                week: 0,
                source: "espn",
                stats: {
                  receptions: 82,
                  rec_yards: 1305,
                  rec_tds: 12,
                },
                updated_at: "2026-07-11T00:00:00Z",
              },
            ],
          }),
        });
        return;
      }
      if (url.pathname.endsWith("/players/1")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockPlayer),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [mockPlayer], total: 1, limit: 200, offset: 0 }),
      });
    });
    await page.route("**/projections/1**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          player_id: 1,
          pass_yards: 0,
          pass_tds: 0,
          interceptions: 0,
          rush_yards: 0,
          rush_tds: 0,
          rec_yards: 1305,
          rec_tds: 12,
          receptions: 82,
          fantasy_points: 315.5,
          floor: 250,
          ceiling: 380,
          boom_prob: 0.35,
          bust_prob: 0.1,
          expected_plays: 90,
          expected_rush_per_play: 0,
          expected_td_per_play: 0.12,
        }),
      });
    });
    await page.route("**/stats/injuries**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [] }) });
    });

    await page.goto("/draft/mock/single-player?new=1&teams=4&timer=60");
    await expect(page.getByText("Jeremiah Smith").first()).toBeVisible();

    await page.getByRole("button", { name: /Jeremiah Smith/i }).first().click();
    const dialog = page.getByRole("dialog", { name: /Jeremiah Smith player card/i });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("span").filter({ hasText: "ESPN PROFILE" }).first()).toBeVisible();
    await expect(dialog.getByText("6'3\"")).toBeVisible();
    await expect(dialog.getByText("215 lbs")).toBeVisible();
    await expect(dialog.getByText("Columbus, Ohio")).toBeVisible();

    const viewport = page.viewportSize();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(viewport).not.toBeNull();
    if (box && viewport) {
      const dialogCenter = box.x + box.width / 2;
      expect(Math.abs(dialogCenter - viewport.width / 2)).toBeLessThan(viewport.width * 0.12);
    }

    await page.getByRole("button", { name: /Close player card/i }).click();
    await expect(dialog).toBeHidden();

    await page.getByRole("button", { name: /Jeremiah Smith/i }).first().click();
    await expect(dialog).toBeVisible();
    await page.mouse.click(8, 8);
    await expect(dialog).toBeHidden();
  });
});
