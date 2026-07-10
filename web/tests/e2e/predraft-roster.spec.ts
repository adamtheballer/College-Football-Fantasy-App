import { expect, test } from "@playwright/test";

const mockUser = {
  id: 42,
  first_name: "Adam",
  email: "adam@example.com",
  email_verified_at: "2026-01-01T00:00:00Z",
};

const seedAuthenticatedSession = async (page: Parameters<typeof test>[0]["page"]) => {
  await page.addInitScript((user) => {
    window.localStorage.setItem(
      "cfb_user",
      JSON.stringify({
        id: user.id,
        firstName: user.first_name,
        email: user.email,
        emailVerifiedAt: user.email_verified_at,
      })
    );
    window.localStorage.setItem("cfb_access_token", "mock-access-token");
    window.localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    window.localStorage.setItem(`cfb_completed_guide_${user.id}`, "true");
    window.localStorage.removeItem(`cfb_pending_guide_${user.id}`);
  }, mockUser);

  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockUser),
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

if (process.env.VITEST) {
  const { test: vitestTest } = await import("vitest");
  vitestTest.skip("Playwright-only pre-draft roster regression", () => {});
} else {
test.describe("pre-draft roster placeholders", () => {
  test("renders blank roster slots without leaked fake projections or player cards", async ({ page }) => {
    await seedAuthenticatedSession(page);

    await page.route("**/leagues/1/settings-view", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          league_name: "Saturday League",
          league_status: "draft_scheduled",
          draft_status: "scheduled",
          league_info: {},
          members: [
            {
              id: 10,
              user_id: 42,
              role: "commissioner",
              joined_at: "2026-01-01T00:00:00Z",
              first_name: "Adam",
              display_name: "Adam",
            },
          ],
          scoring_settings: {},
          roster_settings: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 2 },
          waiver_rules: {},
          standings: [],
          schedule: [],
          rosters: [],
          draft_results: [],
          commissioner_controls: ["reschedule_draft"],
        }),
      });
    });

    await page.route("**/leagues/1/roster**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          season: 2026,
          fantasy_team_id: 11,
          fantasy_team_name: "Adam's Team",
          owned_team: {
            id: 11,
            league_id: 1,
            name: "Adam's Team",
            owner_user_id: 42,
          },
          week: 1,
          roster_slot_limits: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 2 },
          ir_slots: 0,
          message: "Roster is empty. It will populate after the draft.",
          roster: [
            {
              id: 1001,
              league_id: 1,
              fantasy_team_id: 11,
              fantasy_team_name: "Adam's Team",
              player_id: 501,
              player_name: "QB Starter Preview",
              school: "Week 1 Preview",
              position: "QB",
              slot: "QB",
              roster_slot: "QB",
              opponent: "TBD",
              projected_points: 122.8,
              weekly_projected_fantasy_points: 122.8,
            },
            {
              id: 1002,
              league_id: 1,
              fantasy_team_id: 11,
              fantasy_team_name: "Adam's Team",
              player_id: 502,
              player_name: "Bench Preview",
              school: "Week 1 Preview",
              position: "RB",
              slot: "BENCH",
              roster_slot: "BENCH",
              opponent: "TBD",
              projected_points: 34.5,
              weekly_projected_fantasy_points: 34.5,
            },
          ],
          data: [],
        }),
      });
    });

    await page.goto("/league/1/roster");

    await expect(page.getByRole("heading", { name: /^Roster$/i })).toBeVisible();
    await expect(
      page.getByText("No players on this roster yet. Complete the draft to populate your roster.")
    ).toBeVisible();

    await expect(page.locator("div", { hasText: "Starter Projection" }).first()).toContainText("N/A");
    await expect(page.locator("div", { hasText: "Bench Depth" }).first()).toContainText("N/A");
    await expect(page.getByText("122.8")).toHaveCount(0);
    await expect(page.getByText("34.5")).toHaveCount(0);
    await expect(page.getByText("QB Starter Preview")).toHaveCount(0);

    const firstEmptySlot = page.getByRole("button", { name: /QB\s+N\/A\s+N\/A\s+QB\s+N\/A\s+-/ }).first();
    await expect(firstEmptySlot).toBeVisible();
    await firstEmptySlot.click({ force: true });
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
});
}
