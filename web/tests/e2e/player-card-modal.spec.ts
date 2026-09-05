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
  test.use({ timezoneId: "America/New_York" });

  test("keeps the live game on mobile and refreshes its stats and local date", async ({ page }, testInfo) => {
    await page.clock.install({ time: new Date("2026-09-05T00:22:00Z") });
    await page.setViewportSize({ width: 390, height: 844 });
    await seedAuthenticatedSession(page);
    const player = { ...mockPlayer, name: "Isaiah Sategna III", school: "Oklahoma" };
    let yards = 42;
    let logRequests = 0;
    await page.route("**/stats/**", (route) => route.fulfill({ json: { data: [] } }));
    await page.route("**/projections/1**", (route) => route.fulfill({ json: { player_id: 1, fantasy_points: 19.7 } }));
    await page.route("**/players**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/players/1/card")) {
        await route.fulfill({ json: {
          player, about: { height: "5'10\"", weight: "190 lbs", player_class: "Senior", position: "WR", team: "Oklahoma", source: "verified_sheet" },
          injuries: [], recent_news: [], season_stats: [],
          current_game: { state: "live", season: 2026, week: 1, game_id: 342, opponent_name: "UTEP",
            kickoff_at: "2026-09-05T00:00:00Z", stats: { Receptions: 3, ReceivingYards: yards }, source: "espn_live_boxscore" },
        } });
      } else if (path.endsWith("/players/1/game-log")) {
        logRequests += 1;
        await route.fulfill({ json: {
          player_id: 1, player_name: player.name, season: 2026, team_name: "Oklahoma", position: "WR", available_seasons: [2026],
          games: [{ schedule_id: 501, game_id: 342, week: 1, date: "2026-09-05", kickoff_at: "2026-09-05T00:00:00Z",
            opponent_name: "UTEP", location: "home", location_label: "Home", neutral_site: false, conference_game: false,
            game_status: "active", stat_status: "active", result: null,
            stats: { source: "espn_live_boxscore", updated_at: "2026-09-05T00:22:00Z", fantasy_points: null,
              stats: { Receptions: 3, ReceivingYards: yards } } }],
        } });
      } else if (path.endsWith("/players/1")) {
        await route.fulfill({ json: player });
      } else {
        await route.fulfill({ json: { data: [player], total: 1, limit: 200, offset: 0 } });
      }
    });
    await page.goto("/draft/mock/single-player?new=1&teams=4&timer=60");
    await page.getByRole("button", { name: /Isaiah Sategna III/i }).first().click();
    const dialog = page.getByRole("dialog", { name: /Isaiah Sategna III player card/i });
    await expect(dialog.getByLabel("Current player game")).toBeVisible();
    await expect(dialog.getByText("Live game", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Week 1 vs. UTEP")).toBeVisible();
    await expect(dialog.getByText("Upcoming game", { exact: true })).toHaveCount(0);
    await expect(dialog.getByText(/Michigan/)).toHaveCount(0);
    await expect(dialog.getByText("42", { exact: true })).toBeVisible();
    await dialog.getByRole("button", { name: "Game Log", exact: true }).click();
    await expect(dialog.getByText("Sep 4, 2026 • Home", { exact: true })).toBeVisible();
    await expect(dialog.getByText(/Sep 5, 2026/)).toHaveCount(0);
    await expect(dialog.getByText("Live", { exact: true }).last()).toBeVisible();
    await expect(dialog.getByText("42", { exact: true }).last()).toBeVisible();
    const previousRequests = logRequests;
    yards = 74;
    await page.clock.runFor(30_100);
    await expect.poll(() => logRequests).toBeGreaterThan(previousRequests);
    await expect(dialog.getByText("74", { exact: true }).last()).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("live-game-log-mobile.png"), fullPage: true });
    await dialog.getByRole("button", { name: "Summary", exact: true }).click();
    await expect(dialog.getByText("74", { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 960 });
    await dialog.getByRole("button", { name: "Game Log", exact: true }).click();
    await expect(dialog.getByRole("cell", { name: "74", exact: true })).toBeVisible();
    await expect(dialog.getByRole("cell", { name: "Live", exact: true })).toBeVisible();
  });

  test("opens centered with canonical bio details and no provider profile control", async ({ page }, testInfo) => {
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
            current_game: {
              state: "completed",
              season: 2026,
              week: 0,
              opponent_name: "San José State",
              stats: { receptions: 3, rec_yards: 50, rec_tds: 0 },
              source: "espn_final_boxscore",
            },
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
            historical_stats: {
              player_id: 1,
              provider: "verified_import",
              status: "available",
              available_seasons: [2025],
              seasons: [
                {
                  season: 2025,
                  season_type: "regular",
                  team_name: "Ohio State",
                  position: "WR",
                  games_played: 15,
                  games_started: 15,
                  summary: [
                    { label: "Games", value: 15 },
                    { label: "Pass Yds", value: 0 },
                    { label: "Rush Yds", value: 45 },
                    { label: "Rush TD", value: 0 },
                    { label: "Rec Yds", value: 1305 },
                    { label: "Rec TD", value: 12 },
                    { label: "Fantasy Points", value: null },
                  ],
                  categories: [
                    {
                      key: "receiving",
                      label: "Receiving",
                      stats: [{ label: "Receptions", value: 82 }, { label: "Yards", value: 1305 }, { label: "TD", value: 12 }],
                    },
                  ],
                  freshness: { provider: "verified_import", is_final: true },
                  scoring_context: {
                    scoring_rules_version: null,
                    fantasy_points: null,
                    fantasy_points_per_game: null,
                  },
                },
              ],
            },
          }),
        });
        return;
      }
      if (url.pathname.endsWith("/players/1/game-log")) {
        const requestedSeason = Number(url.searchParams.get("season") ?? "2026");
        if (requestedSeason === 2025) {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              player_id: 1,
              player_name: "Jeremiah Smith",
              season: 2025,
              team_name: "Ohio State",
              position: "WR",
              available_seasons: [2026, 2025],
              season_summary: {
                teams: ["Ohio State"],
                games_played: 15,
                games_started: 15,
                stats: [
                  { label: "Receptions", value: 82 },
                  { label: "Rec Yds", value: 1305 },
                  { label: "Rec TD", value: 12 },
                ],
                fantasy_points: 214.94,
              },
              message: "No game log is available for 2025; the schedule has not been imported.",
              games: [],
            }),
          });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            player_id: 1,
            player_name: "Jeremiah Smith",
            season: 2026,
            team_name: "Ohio State",
            position: "WR",
            available_seasons: [2026, 2025],
            season_summary: {
              teams: ["Ohio State"],
              games_played: 1,
              games_started: 1,
              stats: [
                { label: "Receptions", value: 3 },
                { label: "Rec Yds", value: 50 },
                { label: "Rec TD", value: 0 },
              ],
              fantasy_points: 8,
            },
            games: [
              {
                schedule_id: 101,
                game_id: 301,
                week: 1,
                date: "2026-08-29",
                kickoff_at: "2026-08-29T19:00:00Z",
                opponent_name: "Texas",
                location: "home",
                location_label: "Home",
                neutral_site: false,
                conference_game: false,
                venue: null,
                tv_network: null,
                game_status: "final",
                stat_status: "final",
                result: "W 31–17",
                stats: {
                  source: "espn_final_boxscore",
                  fantasy_points: 8,
                  updated_at: "2026-08-30T03:00:00Z",
                  stats: {
                    receptions: 3,
                    rec_yards: 50,
                    rec_tds: 0,
                  },
                },
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
    await expect(dialog.getByText("ESPN PROFILE", { exact: true })).toHaveCount(0);
    await expect(dialog.getByText("6'3\"")).toBeVisible();
    await expect(dialog.getByText("215 lbs")).toBeVisible();
    await expect(dialog.getByText("Columbus, Ohio")).toBeVisible();
    await expect(dialog.getByLabel("Current player game result")).toBeVisible();
    await expect(dialog.getByText("Week 0 vs. San José State")).toBeVisible();

    const viewport = page.viewportSize();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(viewport).not.toBeNull();
    if (box && viewport) {
      const dialogCenter = box.x + box.width / 2;
      expect(Math.abs(dialogCenter - viewport.width / 2)).toBeLessThan(viewport.width * 0.12);
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(dialog.getByText("Bio", { exact: true })).toBeVisible();
    await expect(dialog.getByTestId("player-card-metric-rail")).toBeVisible();
    await expect(dialog.getByText("Height", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Status", { exact: true }).last()).toBeVisible();

    const mobileArticle = dialog.locator("article");
    const mobileBox = await mobileArticle.boundingBox();
    expect(mobileBox).not.toBeNull();
    if (mobileBox) {
      // Mobile player cards intentionally use a compact, blurred-backdrop
      // bottom sheet instead of taking over the entire viewport.
      expect(mobileBox.height).toBeGreaterThan(844 * 0.7);
      expect(mobileBox.height).toBeLessThan(844 * 0.85);
      expect(mobileBox.width).toBeGreaterThan(390 * 0.9);
      expect(mobileBox.width).toBeLessThanOrEqual(390);
    }
    if (process.env.PLAYWRIGHT_CAPTURE_SCREENSHOTS === "1") {
      await page.screenshot({ path: testInfo.outputPath("player-card-mobile-390x844.png"), fullPage: true });
    }

    // Game Log is the single historical-performance hub. A separate Stats
    // tab must not be reintroduced, and the selected season owns its summary
    // and position-specific game stats.
    await expect(dialog.getByRole("button", { name: "Stats", exact: true })).toHaveCount(0);
    await dialog.getByRole("button", { name: "Game Log" }).click();
    await expect(dialog.getByLabel("Game log season")).toHaveValue("2026");
    await expect(dialog.getByLabel("2026 season summary")).toBeVisible();
    await expect(dialog.getByText("vs. Texas", { exact: true }).last()).toBeVisible();
    await expect(dialog.getByText("REC", { exact: true }).last()).toBeVisible();
    await expect(dialog.getByText("REC YDS", { exact: true }).last()).toBeVisible();
    await expect(dialog.getByText("REC TD", { exact: true }).last()).toBeVisible();
    const summaryValueStyles = await dialog
      .getByTestId("game-log-season-summary-stat")
      .evaluateAll((rows) => rows.map((row) => {
        const value = row.querySelector("span:last-child");
        return value ? window.getComputedStyle(value).whiteSpace : null;
      }));
    expect(summaryValueStyles).not.toContain(null);
    expect(summaryValueStyles.every((whiteSpace) => whiteSpace === "nowrap")).toBe(true);

    await dialog.getByLabel("Game log season").selectOption("2025");
    await expect(dialog.getByLabel("2025 season summary")).toBeVisible();
    await expect(dialog.getByText(/No game log is available for 2025/i)).toHaveCount(0);
    await expect(dialog.locator("table")).toHaveCount(0);

    await page.setViewportSize({ width: 1440, height: 960 });
    await dialog.getByLabel("Game log season").selectOption("2026");
    await expect(dialog.getByRole("columnheader", { name: "REC", exact: true })).toBeVisible();
    await expect(dialog.getByRole("columnheader", { name: "TAR", exact: true })).toHaveCount(0);

    const gameLogDimensions = await dialog.locator("table").evaluate((table) => {
      const container = table.parentElement;
      if (!container) {
        throw new Error("Game Log table container is missing");
      }

      return {
        tableWidth: table.getBoundingClientRect().width,
        containerWidth: container.getBoundingClientRect().width,
      };
    });
    // The table fills the frame; the 2px allowance is the frame's left/right border.
    expect(Math.abs(gameLogDimensions.tableWidth - gameLogDimensions.containerWidth)).toBeLessThanOrEqual(2);

    await page.getByRole("button", { name: /Close player card/i }).click();
    await expect(dialog).toBeHidden();

    await page.getByRole("button", { name: /Jeremiah Smith/i }).first().click();
    await expect(dialog).toBeVisible();
    await page.getByRole("button", { name: "Close player card" }).click();
    await expect(dialog).toBeHidden();
  });
});
