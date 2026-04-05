import { expect, test } from "@playwright/test";

const mockAuthPayload = {
  access_token: "mock-access-token",
  access_token_expires_at: "2030-01-01T00:00:00Z",
  user: {
    id: 42,
    first_name: "Codex",
    email: "coach@example.com",
  },
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
    window.localStorage.removeItem(`cfb_pending_guide_${payload.user.id}`);
  }, mockAuthPayload);

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

test.describe("critical browser workflows", () => {
  test("login flow stores auth session and routes to dashboard", async ({ page }) => {
    await page.route("**/auth/login", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockAuthPayload),
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

    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Welcome Back/i })).toBeVisible();
    await page.getByPlaceholder("coach@saturday.com").fill("coach@example.com");
    await page.getByPlaceholder("••••••••").fill("password123");
    await page.getByRole("button", { name: /Sign In to Dashboard/i }).click();

    await page.waitForURL("**/");
    await expect(page.getByText(/COLLEGE FOOTBALL FANTASY/i).first()).toBeVisible();

    const token = await page.evaluate(() => window.localStorage.getItem("cfb_access_token"));
    const user = await page.evaluate(() => window.localStorage.getItem("cfb_user"));
    expect(token).toBe("mock-access-token");
    expect(user).toContain("coach@example.com");
  });

  test("leagues page renders backend response for authenticated session", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagueRow = {
      id: 1,
      name: "Codex Saturday League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 12,
      is_private: true,
      invite_code: "ABC123",
      description: null,
      icon_url: null,
      status: "draft_scheduled",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: {},
        playoff_teams: 4,
        waiver_type: "rolling",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        id: 1,
        league_id: 1,
        draft_datetime_utc: "2026-08-30T23:00:00Z",
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
        status: "scheduled",
      },
      members: [
        {
          id: 10,
          user_id: 42,
          role: "commissioner",
          joined_at: "2026-03-01T10:01:00Z",
        },
      ],
    };

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [leagueRow],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });
    });

    await page.route("**/leagues/1**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(leagueRow),
      });
    });

    await page.route("**/leagues/1/workspace**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          membership: { id: 10, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
          owned_team: { id: 11, league_id: 1, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
          roster: [],
          standings_summary: [],
          allowed_actions: ["create_team", "view_roster", "join_draft_lobby", "open_draft_room"],
        }),
      });
    });

    await page.goto("/leagues");
    await expect(page.getByRole("heading", { name: /Leagues/i })).toBeVisible();
    await expect(page.getByText("Codex Saturday League")).toBeVisible();
    await page.getByRole("button", { name: /League Hub/i }).click();
    await page.waitForURL("**/league/1");
    await expect(page).toHaveURL(/\/league\/1$/);
  });

  test("invalid bootstrap session forces logout and redirects protected routes to login", async ({ page }) => {
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

    await page.route("**/notifications/preferences**", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "expired access token" }),
      });
    });

    await page.goto("/rosters");
    await page.waitForURL("**/login");
    await expect(page.getByRole("heading", { name: /Welcome Back/i })).toBeVisible();

    const token = await page.evaluate(() => window.localStorage.getItem("cfb_access_token"));
    const user = await page.evaluate(() => window.localStorage.getItem("cfb_user"));
    expect(token).toBeNull();
    expect(user).toBeNull();
  });

  test("create league workflow posts to backend and opens league hub", async ({ page }) => {
    await seedAuthenticatedSession(page);

    let leagueRows: any[] = [];
    const createdLeague = {
      id: 1,
      name: "Saturday League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 12,
      is_private: true,
      invite_code: "ABCDEFGHIJKLMNOPQRST",
      description: null,
      icon_url: null,
      status: "draft_scheduled",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4, IR: 1 },
        playoff_teams: 4,
        waiver_type: "faab",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        id: 1,
        league_id: 1,
        draft_datetime_utc: "2026-08-30T23:00:00Z",
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
        status: "scheduled",
      },
      members: [
        {
          id: 101,
          user_id: 42,
          role: "commissioner",
          joined_at: "2026-03-01T10:01:00Z",
        },
      ],
    };

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: leagueRows,
          total: leagueRows.length,
          limit: 20,
          offset: 0,
        }),
      });
    });

    await page.route("**/leagues", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }
      leagueRows = [createdLeague];
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          league: createdLeague,
          invite_code: createdLeague.invite_code,
          invite_link: `https://example.com/join/${createdLeague.invite_code}`,
        }),
      });
    });

    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(createdLeague),
      });
    });

    await page.route("**/leagues/1/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          membership: { id: 101, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
          owned_team: { id: 11, league_id: 1, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
          roster: [],
          standings_summary: [],
          allowed_actions: ["create_team", "view_roster", "join_draft_lobby"],
        }),
      });
    });

    await page.goto("/leagues/create");
    await expect(page.getByRole("heading", { name: /Create League/i })).toBeVisible();
    await page.getByRole("button", { name: /^Continue$/i }).click();
    await page.getByRole("button", { name: /^Continue$/i }).click();
    await page.getByRole("button", { name: /^Continue$/i }).click();
    await page.getByRole("button", { name: /Create League/i }).click();
    await expect(page.getByRole("heading", { name: /League Created/i })).toBeVisible();
    await page.getByRole("button", { name: /Go to League Home/i }).click();

    await page.waitForURL("**/league/1");
    await expect(page.getByRole("heading", { name: /Saturday League/i })).toBeVisible();
  });

  test("join-by-code flow previews league and joins with backend response", async ({ page }) => {
    await seedAuthenticatedSession(page);

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 20, offset: 0 }),
      });
    });

    const preview = {
      id: 77,
      name: "Invite League",
      commissioner_name: "Theo",
      max_teams: 12,
      member_count: 5,
      is_private: true,
      draft_datetime_utc: "2026-08-30T23:00:00Z",
      timezone: "America/New_York",
      scoring_preset: "standard",
    };

    const leagueDetail = {
      id: 77,
      name: "Invite League",
      commissioner_user_id: 15,
      season_year: 2026,
      max_teams: 12,
      is_private: true,
      invite_code: "ABCDEFGHIJKLMNOPQRST",
      description: null,
      icon_url: null,
      status: "draft_scheduled",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 7,
        league_id: 77,
        scoring_json: {},
        roster_slots_json: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4, IR: 1 },
        playoff_teams: 4,
        waiver_type: "rolling",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        id: 9,
        league_id: 77,
        draft_datetime_utc: "2026-08-30T23:00:00Z",
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
        status: "scheduled",
      },
      members: [
        { id: 401, user_id: 15, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
        { id: 402, user_id: 42, role: "manager", joined_at: "2026-03-02T10:01:00Z" },
      ],
    };

    await page.route("**/leagues/join-by-code", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preview),
      });
    });

    await page.route("**/leagues/77/join", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(leagueDetail),
      });
    });

    await page.route("**/leagues/77", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(leagueDetail),
      });
    });

    await page.route("**/leagues/77/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 77,
          membership: { id: 402, user_id: 42, role: "manager", joined_at: "2026-03-02T10:01:00Z" },
          owned_team: { id: 19, league_id: 77, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
          roster: [],
          standings_summary: [],
          allowed_actions: ["join_draft_lobby", "view_roster"],
        }),
      });
    });

    await page.goto("/leagues/join");
    await page.getByPlaceholder("ENTER INVITE CODE").fill("abcdefghijklmnopqrst");
    await page.getByRole("button", { name: /Preview League/i }).click();
    await expect(page.getByRole("heading", { name: /League Preview/i })).toBeVisible();
    await expect(page.getByText("Invite League")).toBeVisible();
    await page.getByRole("button", { name: /^Join League$/i }).click();
    await page.waitForURL("**/league/77");
    await expect(page.getByRole("heading", { name: /Invite League/i })).toBeVisible();
  });

  test("draft-room pick mutation updates persisted draft state in UI", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagueDetail = {
      id: 1,
      name: "Draft Test League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 12,
      is_private: true,
      invite_code: "ABCDEFGHIJKLMNOPQRST",
      description: null,
      icon_url: null,
      status: "draft_live",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4, IR: 1 },
        playoff_teams: 4,
        waiver_type: "rolling",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        id: 21,
        league_id: 1,
        draft_datetime_utc: "2026-08-30T23:00:00Z",
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
        status: "live",
      },
      members: [
        { id: 701, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
      ],
    };

    const players = [
      {
        id: 501,
        name: "Arch Manning",
        position: "QB",
        school: "Texas",
        image_url: null,
      },
    ];

    let draftRoom = {
      league_id: 1,
      draft_id: 21,
      status: "live",
      pick_timer_seconds: 90,
      roster_slots: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4, IR: 1 },
      teams: [
        { id: 11, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
        { id: 12, name: "Other Team", owner_user_id: 99, owner_name: "Other" },
      ],
      picks: [] as Array<Record<string, unknown>>,
      current_pick: 1,
      current_round: 1,
      current_round_pick: 1,
      current_team_id: 11,
      current_team_name: "Codex Team",
      user_team_id: 11,
      can_make_pick: true,
    };

    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(leagueDetail),
      });
    });

    await page.route("**/leagues/1/draft-room", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(draftRoom),
      });
    });

    await page.route("**/players?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: players,
          total: players.length,
          limit: 250,
          offset: 0,
        }),
      });
    });

    await page.route("**/leagues/1/draft-picks", async (route) => {
      const payload = route.request().postDataJSON() as { player_id: number };
      const selected = players.find((player) => player.id === payload.player_id);
      if (!selected) {
        await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "player not found" }) });
        return;
      }

      draftRoom = {
        ...draftRoom,
        picks: [
          ...draftRoom.picks,
          {
            id: 1,
            overall_pick: 1,
            round_number: 1,
            round_pick: 1,
            team_id: 11,
            team_name: "Codex Team",
            player_id: selected.id,
            player_name: selected.name,
            player_position: selected.position,
            player_school: selected.school,
            made_by_user_id: 42,
            created_at: "2026-03-21T10:00:00Z",
          },
        ],
        current_pick: 2,
        current_round_pick: 2,
        current_team_id: 12,
        current_team_name: "Other Team",
        can_make_pick: false,
      };

      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(draftRoom),
      });
    });

    await page.goto("/league/1/draft");
    await expect(page.getByRole("heading", { name: /Draft Test League/i })).toBeVisible();
    await page.getByRole("button", { name: /^Save Pick$/i }).click();
    await expect(page.getByText("1/12")).toBeVisible();
    await expect(page.getByText(/No available players match this search/i)).toBeVisible();
    await expect(page.getByText(/Codex Team • Pick 1/i)).toBeVisible();
  });

  test("watchlist create/add/remove persists through backend contracts", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagues = [
      {
        id: 1,
        name: "Watchlist League",
        commissioner_user_id: 42,
        season_year: 2026,
        max_teams: 12,
        is_private: true,
        invite_code: "ABCDEFGHIJKLMNOPQRST",
        description: null,
        icon_url: null,
        status: "draft_scheduled",
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-05T10:00:00Z",
        settings: {
          id: 1,
          league_id: 1,
          scoring_json: {},
          roster_slots_json: {},
          playoff_teams: 4,
          waiver_type: "rolling",
          trade_review_type: "commissioner",
          superflex_enabled: false,
          kicker_enabled: true,
          defense_enabled: false,
        },
        draft: null,
        members: [{ id: 1, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" }],
      },
    ];

    const players = [
      { id: 801, name: "Arch Manning", position: "QB", pos: "QB", school: "Texas", image_url: null },
      { id: 802, name: "Ryan Wingo", position: "WR", pos: "WR", school: "Texas", image_url: null },
    ];

    let watchlists: Array<{ id: number; name: string; league_id: number | null; players: typeof players }> = [];

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: leagues, total: leagues.length, limit: 20, offset: 0 }),
      });
    });

    await page.route("**/players?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: players, total: players.length, limit: 100, offset: 0 }),
      });
    });

    await page.route("**/watchlists**", async (route) => {
      const method = route.request().method();
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (url.port !== "8000") {
        await route.fallback();
        return;
      }

      if (method === "GET" && path.endsWith("/watchlists")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: watchlists,
            total: watchlists.length,
            limit: 100,
            offset: 0,
          }),
        });
        return;
      }

      if (method === "POST" && path.endsWith("/watchlists")) {
        const body = route.request().postDataJSON() as { name: string; league_id?: number | null };
        const created = {
          id: 1,
          name: body.name,
          league_id: body.league_id ?? null,
          players: [],
        };
        watchlists = [created];
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(created),
        });
        return;
      }

      if (method === "POST" && path.match(/\/watchlists\/\d+\/players$/)) {
        const body = route.request().postDataJSON() as { player_id: number };
        const target = watchlists[0];
        if (!target) {
          await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "watchlist not found" }) });
          return;
        }
        const found = players.find((player) => player.id === body.player_id);
        if (found && !target.players.some((player) => player.id === found.id)) {
          target.players.push(found);
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(target),
        });
        return;
      }

      if (method === "DELETE" && path.match(/\/watchlists\/\d+\/players\/\d+$/)) {
        const target = watchlists[0];
        if (!target) {
          await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "watchlist not found" }) });
          return;
        }
        const playerId = Number(path.split("/").pop());
        target.players = target.players.filter((player) => player.id !== playerId);
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(target),
        });
        return;
      }

      await route.fallback();
    });

    await page.goto("/watchlists");
    await expect(page.getByRole("heading", { name: /Browse Players/i })).toBeVisible();

    await page.getByRole("button", { name: /Save to watchlist/i }).first().dispatchEvent("click");
    await expect(page.getByRole("heading", { name: /Create Watchlist/i })).toBeVisible();
    await page.getByPlaceholder("e.g. Late-Round Targets").fill("My Targets");
    await page.getByRole("button", { name: /^Create$/i }).click();

    await expect(page.getByRole("heading", { name: "My Targets" })).toBeVisible();
    await expect(page.getByText("Arch Manning").first()).toBeVisible();

    const archCard = page
      .locator("div", { hasText: "Arch Manning" })
      .filter({ has: page.locator("button.h-10.w-10.rounded-xl.border") })
      .first();
    await archCard.locator("button.h-10.w-10.rounded-xl.border").click({ force: true });

    await expect(page.getByText(/Add players from browse mode to build this list/i)).toBeVisible();
  });

  test("waiver add/drop mutation flow persists roster transaction state", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagues = [
      {
        id: 1,
        name: "Waiver League",
        commissioner_user_id: 42,
        season_year: 2026,
        max_teams: 12,
        is_private: true,
        invite_code: "ABCDEFGHIJKLMNOPQRST",
        description: null,
        icon_url: null,
        status: "draft_scheduled",
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-05T10:00:00Z",
        settings: {
          id: 1,
          league_id: 1,
          scoring_json: {},
          roster_slots_json: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4, IR: 1 },
          playoff_teams: 4,
          waiver_type: "rolling",
          trade_review_type: "commissioner",
          superflex_enabled: false,
          kicker_enabled: true,
          defense_enabled: false,
        },
        draft: null,
        members: [{ id: 1, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" }],
      },
    ];

    const players = [
      { id: 901, name: "Arch Manning", position: "QB", school: "Texas", image_url: null },
      { id: 902, name: "Ryan Wingo", position: "WR", school: "Texas", image_url: null },
    ];

    let rosterRows = [
      {
        id: 610,
        league_id: 1,
        team_id: 11,
        slot: "QB",
        status: "active",
        player: { id: 930, name: "Legacy QB", position: "QB", school: "Alabama", image_url: null },
      },
    ];

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: leagues, total: leagues.length, limit: 20, offset: 0 }),
      });
    });

    await page.route("**/leagues/1/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          membership: { id: 1, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
          owned_team: { id: 11, league_id: 1, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
          roster: rosterRows,
          standings_summary: [],
          allowed_actions: ["view_roster", "manage_waivers"],
        }),
      });
    });

    await page.route("**/teams/11/roster**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: rosterRows,
          total: rosterRows.length,
          limit: 100,
          offset: 0,
        }),
      });
    });

    await page.route("**/players?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: players, total: players.length, limit: 100, offset: 0 }),
      });
    });

    await page.route("**/teams/11/add-drop", async (route) => {
      const payload = route.request().postDataJSON() as { add_player_id: number; drop_roster_entry_id: number };
      const adding = players.find((player) => player.id === payload.add_player_id);
      rosterRows = [
        {
          id: 611,
          league_id: 1,
          team_id: 11,
          slot: adding?.position || "QB",
          status: "active",
          player: {
            id: adding?.id || 0,
            name: adding?.name || "Unknown",
            position: adding?.position || "QB",
            school: adding?.school || "Unknown",
            image_url: null,
          },
        },
      ];
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          transaction: {
            id: 501,
            league_id: 1,
            team_id: 11,
            transaction_type: "add_drop",
            player_id: payload.add_player_id,
            related_player_id: 930,
            reason: "waiver upgrade",
            created_at: "2026-03-21T10:00:00Z",
          },
          roster: rosterRows,
        }),
      });
    });

    await page.goto("/waivers");
    await expect(page.getByRole("heading", { name: /Waiver Wire/i })).toBeVisible();
    await page.getByRole("button", { name: /^Add$/i }).first().click();
    await expect(page.getByRole("heading", { name: /Add \/ Drop/i })).toBeVisible();
    await page.getByRole("button", { name: /^Confirm$/i }).click();
    await expect(page.getByRole("heading", { name: /Add \/ Drop/i })).toBeHidden();
  });
});
