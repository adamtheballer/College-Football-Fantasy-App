import { expect, test, type Page } from "@playwright/test";

const sections = [
  ["Matchup", "matchup"],
  ["Waiver Wire", "waivers"],
  ["Roster", "roster"],
  ["Watchlist", "watchlist"],
  ["Chat", "chat"],
  ["Settings", "settings"],
] as const;

async function leagueShell(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      "cfb_user",
      JSON.stringify({
        id: 999995,
        firstName: "Layout QA",
        email: "layout@example.invalid",
        isAdmin: false,
      }),
    );
    localStorage.setItem("cfb_access_token", "synthetic-layout-session");
    localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    localStorage.setItem("cfb_completed_guide_999995", "true");
  });
  const state = { delayedRoster: false, rosterError: false, live: false };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, "");
    let body: unknown = { data: [], total: 0 };
    if (path === "/auth/me")
      body = {
        id: 999995,
        first_name: "Layout QA",
        email: "layout@example.invalid",
      };
    else if (path === "/health/runtime")
      body = {
        git_sha: "layout-qa",
        web_git_sha: "layout-qa",
        worker_git_sha: "layout-qa",
        api_process_instance_uuid: "layout-qa",
        runtime_mode: "development",
        environment: "development",
        readiness_status: "ready",
        scoring_mode: "standard",
        sportsdata_enabled: false,
        ios_app_review_enabled: false,
      };
    else if (path.includes("unread-count")) body = { total_unread: 0 };
    else if (path.includes("preferences")) body = {};
    else if (path === "/leagues/42")
      body = {
        id: 42,
        name: "Saturday Night Conference With A Very Long League Name",
        season_year: 2026,
        status: "post_draft",
        draft: { status: "completed" },
        teams: [],
        settings: { roster_slots_json: { QB: 1 } },
      };
    else if (path === "/leagues/42/roster") {
      if (state.delayedRoster)
        await new Promise((resolve) => setTimeout(resolve, 1500));
      if (state.rosterError) {
        await route.fulfill({
          status: 403,
          json: { detail: "Roster unavailable for layout verification" },
        });
        return;
      }
      body = {
        league_id: 42,
        week: 7,
        owned_team: { id: 1, name: "QA Team" },
        slots: [],
        team_rosters: [],
      };
    } else if (path === "/leagues/42/matchup") {
      const team = (id: number) => ({
        fantasy_team_id: id,
        fantasy_team_name: `Team ${id}`,
        manager_name: `Manager ${id}`,
        current_points: 0,
        projected_points: 100,
        projected_total: 100,
        win_probability: 50,
        roster: state.live
          ? [
              {
                player_id: id,
                player_name: `Player ${id}`,
                live_game_state: "live",
                slot: "QB",
                position: "QB",
              },
            ]
          : [],
      });
      body = {
        league_id: 42,
        season: 2026,
        week: 7,
        matchup_id: 66,
        status: state.live ? "live" : "projected",
        user_team: team(1),
        my_team: team(1),
        opponent_team: team(2),
      };
    } else if (path === "/leagues/42/waivers")
      body = {
        league_id: 42,
        week: 7,
        available_players: [],
        players: [],
        claims: [],
        roster: [],
        results: [],
        waiver_rules: { waiver_type: "rolling" },
      };
    else if (path === "/leagues/42/settings-view")
      body = {
        league_id: 42,
        league_name: "Layout QA",
        standings: [],
        teams: [],
        schedule: [],
        members: [],
        trade_history: [],
        rosters: [],
        draft_results: [],
      };
    await route.fulfill({ status: 200, json: body });
  });
  return state;
}

for (const width of [320, 390, 440, 1280]) {
  test(`league navigation keeps its geometry across every tab at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await leagueShell(page);
    await page.goto("/league/42/matchup");
    const rail = page.getByRole("navigation", { name: "League sections" });
    await expect(rail).toBeVisible();
    const initial = (await rail.boundingBox())!;
    const geometry: unknown[] = [];
    for (const [label, path] of sections) {
      await rail.getByRole("link", { name: label, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/league/42/${path}$`));
      await expect(rail).toBeVisible();
      await expect(
        rail.getByRole("link", { name: label, exact: true }),
      ).toHaveAttribute("aria-current", "page");
      await expect(
        page.getByTestId("league-section-frame").getByRole("heading").first(),
      ).toBeVisible();
      const box = (await rail.boundingBox())!;
      geometry.push({ section: label, ...box });
      for (const dimension of ["x", "y", "width", "height"] as const) {
        expect(
          Math.abs(box[dimension] - initial[dimension]),
          `${label}: ${dimension}`,
        ).toBeLessThanOrEqual(1);
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: info.outputPath(`${path}-${width}.png`),
        animations: "disabled",
      });
    }
    await info.attach("navigation-geometry.json", {
      body: JSON.stringify(geometry, null, 2),
      contentType: "application/json",
    });
  });
}

test("league rail stays put through loading, errors, live refresh and native safe area", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 440, height: 956 });
  const state = await leagueShell(page);
  state.delayedRoster = true;
  await page.goto("/league/42/matchup");
  const rail = page.getByRole("navigation", { name: "League sections" });
  await expect(rail).toBeVisible();
  // Exercise the same native safe-area CSS used by the installed Capacitor shell.
  await page
    .locator("[data-app-viewport]")
    .evaluate((element) => element.setAttribute("data-native-shell", "true"));
  const initial = (await rail.boundingBox())!;
  const unchanged = async () => {
    await expect(rail).toHaveCount(1);
    expect(await rail.boundingBox()).toEqual(initial);
  };
  await rail.getByRole("link", { name: "Roster", exact: true }).click();
  await expect(
    page.getByLabel("Loading roster", { exact: true }),
  ).toBeVisible();
  await unchanged();
  await expect(
    page.getByRole("heading", { name: "Roster", exact: true }),
  ).toBeVisible();
  await unchanged();
  state.delayedRoster = false;
  state.rosterError = true;
  await page.reload();
  await page
    .locator("[data-app-viewport]")
    .evaluate((element) => element.setAttribute("data-native-shell", "true"));
  await expect(
    page.getByText("Unable to load roster", { exact: true }),
  ).toBeVisible();
  await unchanged();
  state.live = true;
  await rail.getByRole("link", { name: "Matchup", exact: true }).click();
  await expect(page.getByTestId("live-score-refresh-countdown")).toBeVisible();
  await unchanged();
  await page.screenshot({
    path: info.outputPath("native-live-league-tabs.png"),
    animations: "disabled",
  });
  await rail.getByRole("link", { name: "Waiver Wire", exact: true }).click();
  await expect(page.getByTestId("league-player-board")).toBeVisible();
  await unchanged();
  // New tab destinations start at the page top, even after researching below the fold.
  await page.locator("[data-app-scroll]").evaluate((element) => {
    element.scrollTop = 300;
  });
  await page.goto("/league/42/settings/");
  await page
    .locator("[data-app-viewport]")
    .evaluate((element) => element.setAttribute("data-native-shell", "true"));
  await expect(
    rail.getByRole("link", { name: "Settings", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await unchanged();
  expect(
    await page
      .locator("[data-app-scroll]")
      .evaluate((element) => element.scrollTop),
  ).toBe(0);
});
