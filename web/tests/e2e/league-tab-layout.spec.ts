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

for (const width of [320, 390, 1280]) {
  test(`roster hides Start metadata for starters bench and IR only at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    await leagueShell(page);
    await page.route("**/api/leagues/42/roster**", async (route) => {
      const slots = ["WR", "BENCH", "IR"].map((slot, index) => ({
        id: index + 1, player_id: index + 1, player_name: `Roster ${slot} Player`,
        league_id: 42, team_id: 1, fantasy_team_id: 1, fantasy_team_name: "QA Team",
        position: "WR", slot, slot_index: 1, slot_id: `team-1-${slot}-1`, status: "ACTIVE",
        school: "USC", opponent: "UCLA", projected_points: 18.4, weekly_projected_fantasy_points: 18.4,
        popularity: { start_percent: 72.5, rostered_percent: 90 },
      }));
      await route.fulfill({ json: { league_id: 42, season: 2026, week: 7, owned_team: { id: 1, name: "QA Team" }, slots, team_rosters: [], ir_slots: 1 } });
    });
    await page.goto("/league/42/roster");
    for (const slot of ["WR", "BENCH", "IR"]) await expect(page.getByText(`Roster ${slot} Player`, { exact: true })).toBeVisible();
    await expect(page.locator("[data-player-popularity]")).toHaveCount(0);
    await expect(page.getByText(/^Start (?:—|[0-9.]+%)$/)).toHaveCount(0);
    await expect(page.getByText("Starters", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`roster-without-start-${width}.png`), fullPage: true });
  });
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
        page.getByRole("button", { name: "Notifications", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Messages", exact: true }),
      ).toBeVisible();
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

for (const width of [390, 1280]) {
  test(`league tabs remain at the same level while scrolling and switching at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 700 });
    await leagueShell(page);
    await page.goto("/league/42/waivers");
    const rail = page.getByRole("navigation", { name: "League sections" });
    await expect(page.getByTestId("league-player-board")).toBeVisible();
    const initial = (await rail.boundingBox())!;
    const scroller = page.locator("[data-app-scroll]");
    await scroller.evaluate((el) => {
      el.scrollTop = 350;
    });
    await expect
      .poll(() => scroller.evaluate((el) => el.scrollTop))
      .toBeGreaterThan(0);
    await expect
      .poll(async () => (await rail.boundingBox())!.y)
      .toBe(initial.y);
    for (const [label, path] of sections) {
      await rail.getByRole("link", { name: label, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/league/42/${path}$`));
      await expect
        .poll(async () => (await rail.boundingBox())!.y)
        .toBe(initial.y);
      await scroller.evaluate((el) => {
        el.scrollTop = 350;
      });
      await expect
        .poll(async () => (await rail.boundingBox())!.y)
        .toBe(initial.y);
    }
    await page.screenshot({
      path: info.outputPath(`pinned-league-tabs-${width}.png`),
    });
  });
}

for (const width of [320, 390, 1280]) {
  test(`compact league pages and single-line settings labels at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 844 });
    await leagueShell(page);
    await page.goto("/league/42/waivers");
    await expect(
      page.getByRole("heading", { level: 1, name: "Waiver Wire", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(/Players are instant adds before their own kickoff/),
    ).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Available Players", exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: info.outputPath(`compact-waivers-${width}.png`),
    });
    await page.goto("/league/42/watchlist");
    await expect(
      page.getByRole("heading", { level: 1, name: "Watchlist", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Saved Targets", exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: info.outputPath(`compact-watchlist-${width}.png`),
    });
    await page.goto("/league/42/settings");
    const sections = page.locator('[aria-label="League settings sections"]');
    await expect(sections).toBeVisible();
    await expect(sections.getByRole("button")).toHaveCount(7);
    const labels = await sections
      .locator("button span")
      .evaluateAll((elements) =>
        elements.map((el) => {
          const range = document.createRange();
          range.selectNodeContents(el);
          return {
            text: el.textContent,
            lines: range.getClientRects().length,
            clipped: el.scrollWidth > el.clientWidth,
          };
        }),
      );
    expect(labels).toHaveLength(7);
    expect(labels.every((l) => l.lines === 1 && !l.clipped)).toBe(true);
    for (const label of [
      "Standings",
      "Schedules",
      "Manager Rosters",
      "Draft Results",
    ]) {
      const button = sections.getByRole("button", { name: label, exact: true });
      await button.scrollIntoViewIfNeeded();
      await expect(button).toBeInViewport();
      await button.click();
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`single-line-settings-${width}.png`),
    });
  });
}

for (const path of ["/league/42/chat", "/chats?leagueId=42"]) {
  test(`chat opens newest first and appends older pages at ${path}`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await leagueShell(page);
    const receipts: number[] = [];
    const message = (id: number) => ({
      id,
      thread_id: 420,
      league_id: 42,
      sender_user_id: 2,
      message_type: "user",
      body: `Message ${id}`,
      metadata: {},
      client_message_id: null,
      reply_to_message_id: null,
      edited_at: null,
      deleted_at: null,
      created_at: new Date(Date.UTC(2026, 9, 16, 0, id)).toISOString(),
      updated_at: new Date(Date.UTC(2026, 9, 16, 0, id)).toISOString(),
      sender_display_name: "Other manager",
      sender_fantasy_team_name: null,
      reply_to_message: null,
    });
    await page.route("**/api/leagues**", async (route) => {
      const url = new URL(route.request().url());
      const p = url.pathname.replace(/^\/api/, "");
      if (p === "/leagues")
        return route.fulfill({
          json: {
            data: [{ id: 42, name: "Chat QA", status: "post_draft" }],
            total: 1,
          },
        });
      if (p === "/leagues/42/chats")
        return route.fulfill({
          json: {
            data: [
              {
                id: 420,
                league_id: 42,
                thread_type: "league",
                title: "General",
                participants: [],
                unread_count: 20,
                last_message_at: "2026-10-16T01:40:00Z",
              },
            ],
            total: 1,
          },
        });
      if (p === "/leagues/42/chats/420/messages") {
        const before = Number(url.searchParams.get("before_message_id"));
        const after = Number(url.searchParams.get("after_message_id"));
        return route.fulfill({
          json: {
            data: after
              ? []
              : Array.from({ length: 50 }, (_, i) =>
                  message((before ? 1 : 51) + i),
                ),
            next_before_message_id: before || after ? null : 51,
            next_after_message_id: null,
          },
        });
      }
      if (p === "/leagues/42/chats/420/read") {
        receipts.push(route.request().postDataJSON().last_read_message_id);
        return route.fulfill({
          json: { thread_id: 420, last_read_message_id: 100 },
        });
      }
      await route.fallback();
    });
    await page.goto(path);
    const messages = page.getByLabel("Messages, newest first");
    await expect(messages.locator("[data-message-id]").first()).toHaveAttribute(
      "data-message-id",
      "100",
    );
    await expect.poll(() => receipts).toContain(100);
    await expect(messages.locator("[data-message-id]")).toHaveCount(50);
    const composer = page.getByPlaceholder("Message your league…");
    const firstMessage = messages.locator("[data-message-id]").first();
    await expect(composer).toBeInViewport();
    expect((await composer.boundingBox())!.y).toBeLessThan(
      (await firstMessage.boundingBox())!.y,
    );
    await page.screenshot({
      path: info.outputPath("chat-initial-newest-and-composer.png"),
    });
    await messages.getByRole("button", { name: "Load older messages" }).click();
    await expect(messages.locator("[data-message-id]")).toHaveCount(100);
    await expect(messages.locator("[data-message-id]").first()).toHaveAttribute(
      "data-message-id",
      "100",
    );
    await expect(messages.locator("[data-message-id]").last()).toHaveAttribute(
      "data-message-id",
      "1",
    );
    await expect(
      messages.getByRole("button", { name: "Load older messages" }),
    ).toHaveCount(0);
    expect(
      await messages
        .locator("[data-message-id]")
        .evaluateAll((els) =>
          els.map((el) => Number(el.getAttribute("data-message-id"))),
        ),
    ).toEqual(Array.from({ length: 100 }, (_, i) => 100 - i));
    await page.screenshot({ path: info.outputPath("newest-first-chat.png") });
  });
}

test("weekly leaderboard refresh changes the round and shows current names and points for the top 10", async ({
  page,
}, info) => {
  await leagueShell(page);
  await page.clock.install();
  let week = 7;
  await page.route("**/api/weekly-challenges/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/history")) return route.fulfill({ json: [] });
    if (url.pathname.endsWith("/current"))
      return route.fulfill({
        json: {
          id: week,
          season: 2026,
          week,
          state: "Open",
          challenges: [],
          next_rollover_at: "2026-10-21T04:00:00Z",
          server_now: "2026-10-16T17:00:00Z",
        },
      });
    if (url.pathname.endsWith("/leaderboard")) {
      const round = Number(url.searchParams.get("round_id"));
      return route.fulfill({
        json: {
          season: 2026,
          week: round,
          round_id: round,
          provisional: false,
          your_rank: null,
          data: Array.from({ length: 10 }, (_, i) => ({
            user_id: i + 1,
            rank: i + 1,
            display_name: `Week ${round} manager ${i + 1}`,
            username: null,
            avatar_url: null,
            profile_url: `/managers/${i + 1}`,
            points: 100 - i - round,
          })),
        },
      });
    }
    await route.fallback();
  });
  await page.goto("/weekly-challenges");
  await page
    .getByRole("link", { name: "View Leaderboard", exact: true })
    .click();
  await expect(page).toHaveURL(/\/weekly-challenges\/leaderboard$/);
  await expect(
    page.getByText("Week 7 manager 1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Week 7 manager \d/ }),
  ).toHaveCount(10);
  week = 8;
  await page.clock.fastForward(31_000);
  await expect(
    page.getByText("Week 8 manager 1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Week 8 manager \d/ }),
  ).toHaveCount(10);
  await expect(
    page.getByRole("link", { name: /Week 8 manager 1 92 points/ }),
  ).toBeVisible();
  await expect(page.getByText("Week 7 manager 1", { exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByText(/2026 · Week 8/)).toBeVisible();
  await page.screenshot({ path: info.outputPath("week-8-top-10.png") });
});

for (const width of [320, 390, 1280]) {
  test(`weekly waiver performance and position filters at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    await leagueShell(page);
    const requests: URL[] = [];
    let fail = false;
    await page.route("**/api/leagues/42/waivers**", async (route) => {
      const url = new URL(route.request().url());
      requests.push(url);
      if (fail) { await route.fulfill({ status: 503, json: { detail: "QA unavailable" } }); return; }
      const performance = url.searchParams.get("sort_by") === "weekly_points";
      const week = Number(url.searchParams.get("performance_week") ?? 6);
      const pos = url.searchParams.get("position");
      const pool = [
        { id: 1, name: "Top Receiver", position: "WR", points: week === 6 ? 30 : 5 },
        { id: 2, name: "Second Receiver", position: "WR", points: week === 6 ? 12 : 35 },
        { id: 3, name: "Zero Receiver", position: "WR", points: 0 },
        { id: 4, name: "Missing Receiver", position: "WR", points: null },
        ...["QB", "RB", "TE", "K"].map((position, index) => ({ id: index + 5, name: `${position} Leader`, position, points: 22 })),
      ].filter((p) => !pos || p.position === pos);
      if (performance) pool.sort((a, b) => (a.points === null ? 1 : 0) - (b.points === null ? 1 : 0) || (b.points ?? 0) - (a.points ?? 0));
      await route.fulfill({ json: {
        league_id: 42, week: 7, performance_week: performance ? week : null,
        fantasy_team_id: 1, claims: [], results: [], roster: [], total_available: pool.length,
        waiver_rules: { waiver_type: "rolling" },
        available_players: pool.map((p) => ({ ...p, school: "USC", opponent: "Current opponent", weekly_projected_fantasy_points: 20,
          final_fantasy_points: null, latest_final_fantasy_points: 99, latest_final_week: 4,
          performance_fantasy_points: performance ? p.points : null, projection_status: "ACTIVE",
          injury_status: null, season_positional_rank: 1, season_rank_through_week: 5,
          rostered_by_team_name: null, availability_state: "free_agent", available_at: null,
        })),
      }});
    });
    await page.goto("/league/42/waivers");
    const rowPrefix = width < 1024 ? "waiver-mobile-player-row-" : "waiver-rank-";
    const pointsPrefix = width < 1024 ? "waiver-mobile-week-points-" : "waiver-week-points-";
    const visibleIds = async () => page.locator(`[data-testid^="${rowPrefix}"]:visible`).evaluateAll((els) => els.map((el) => Number(el.getAttribute("data-testid")!.split("-").at(-1))));
    await page.getByRole("combobox", { name: "Waiver player sort" }).click();
    await page.getByRole("option", { name: "Weekly performance", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "Performance week" })).toHaveText("Last week (Week 6)");
    for (const position of ["QB", "RB", "WR", "TE", "K"]) {
      await page.getByRole("button", { name: position, exact: true }).click();
      await expect.poll(() => requests.at(-1)?.searchParams.get("position")).toBe(position);
      await expect(page.getByTestId(`${pointsPrefix}${position === "WR" ? 1 : ["QB", "RB", "TE", "K"].indexOf(position) + 5}`)).toHaveText(position === "WR" ? "30.0" : "22.0");
    }
    await page.getByRole("button", { name: "WR", exact: true }).click();
    await expect.poll(visibleIds).toEqual([1, 2, 3, 4]);
    await expect(page.getByTestId(`${pointsPrefix}3`)).toHaveText("0.0");
    await expect(page.getByTestId(`${pointsPrefix}4`)).toHaveText("—");
    await page.getByRole("combobox", { name: "Performance week" }).click();
    await page.getByRole("option", { name: "Week 5", exact: true }).click();
    await expect.poll(visibleIds).toEqual([2, 1, 3, 4]);
    await expect(page.getByTestId(`${pointsPrefix}2`)).toHaveText("35.0");
    expect(requests.at(-1)?.searchParams.get("week")).toBeNull();
    // Radix restores focus when its closing menu finishes. Wait for that
    // accessibility transition before typing so its delayed focus restore
    // cannot redirect Playwright's immediate clear keystroke to the trigger.
    await expect(page.getByRole("combobox", { name: "Performance week" })).toBeFocused();
    await page.getByPlaceholder("Search players, schools...").fill("Missing");
    await expect.poll(visibleIds).toEqual([4]);
    await expect(page.getByTestId(`${pointsPrefix}4`)).toHaveText("—");
    await page.getByPlaceholder("Search players, schools...").fill("");
    await expect(page.getByPlaceholder("Search players, schools...")).toHaveValue("");
    await expect.poll(visibleIds).toEqual([2, 1, 3, 4]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`weekly-performance-${width}.png`) });
    fail = true;
    await page.getByRole("button", { name: "RB", exact: true }).click();
    await expect(page.getByText("The player board is temporarily unavailable. Try again in a moment.")).toBeVisible({ timeout: 15000 });
    await expect(page.locator(`[data-testid^="${rowPrefix}"]:visible`)).toHaveCount(0);
    fail = false;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await expect.poll(visibleIds).toEqual([6]);
    await page.getByRole("combobox", { name: "Waiver player sort" }).click();
    await page.getByRole("option", { name: "Week 7 projection", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "Performance week" })).toHaveCount(0);
    await expect(page.getByTestId(`${pointsPrefix}6`)).toHaveText("20.0");
  });
}
