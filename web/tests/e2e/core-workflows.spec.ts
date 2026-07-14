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
  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockAuthPayload.user),
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

  test("signup verifies email link then logs in and opens league access", async ({ page }) => {
    const unverifiedPayload = {
      ...mockAuthPayload,
      access_token: "signup-access-token",
      user: {
        ...mockAuthPayload.user,
        first_name: "Adam",
        email: "adam@example.com",
        email_verified_at: null,
      },
    };
    const verifiedUser = {
      ...unverifiedPayload.user,
      email_verified_at: "2026-07-10T20:00:00Z",
    };
    const verifiedPayload = {
      ...mockAuthPayload,
      access_token: "verified-access-token",
      user: verifiedUser,
    };
    let verifyPayload: unknown = null;

    await page.route("**/auth/signup", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(unverifiedPayload),
      });
    });
    await page.route("**/auth/verify-email", async (route) => {
      verifyPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          status: "verified",
          message: "email verified",
        }),
      });
    });
    await page.route("**/auth/login", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(verifiedPayload),
      });
    });
    await page.route("**/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(verifiedUser),
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
    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 20, offset: 0 }),
      });
    });

    await page.goto("/signup");
    await page.getByPlaceholder("Enter your first name").fill("Adam");
    await page.getByPlaceholder("coach@saturday.com").fill("adam@example.com");
    await page.getByPlaceholder("••••••••").fill("StrongPass123!");
    await page.getByRole("button", { name: /Create Account/i }).click();
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .toBe("signup-access-token");

    await page.goto("/verify-email?token=public-token-123");
    await expect(page.getByRole("heading", { name: /Email Verified/i })).toBeVisible();
    await expect(page.getByText(/verified\. You can now create and join leagues/i)).toBeVisible();
    expect(page.url()).not.toContain("public-token-123");
    expect(verifyPayload).toEqual({ token: "public-token-123" });

    await page.getByRole("button", { name: /SIGN OUT/i }).click();
    await page.goto("/login");
    await page.getByPlaceholder("coach@saturday.com").fill("adam@example.com");
    await page.getByPlaceholder("••••••••").fill("StrongPass123!");
    await page.getByRole("button", { name: /Sign In to Dashboard/i }).click();
    await page.waitForURL("**/");
    const endGuideButton = page.getByRole("button", { name: /End Guide/i });
    if (await endGuideButton.isVisible().catch(() => false)) {
      await endGuideButton.click();
    }
    await page.evaluate((userId) => {
      window.localStorage.setItem(`cfb_completed_guide_${userId}`, "true");
      window.localStorage.removeItem(`cfb_pending_guide_${userId}`);
    }, verifiedUser.id);

    await page.goto("/leagues");
    await expect(page.getByRole("heading", { name: /^Leagues$/i })).toBeVisible();
    const storedUser = await page.evaluate(() => window.localStorage.getItem("cfb_user"));
    expect(storedUser).toContain("2026-07-10T20:00:00Z");
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
    await page
      .locator(".cfb-panel", { hasText: "Codex Saturday League" })
      .getByRole("button", { name: /^League Hub$/i })
      .click();
    await page.waitForURL("**/league/1**");
    await expect(page.getByRole("heading", { name: /^Roster$/i })).toBeVisible();
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

    await page.route("**/auth/me", async (route) => {
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
    await page.getByRole("button", { name: /^Continue to /i }).click();
    await page.getByRole("button", { name: /^Continue to /i }).click();
    await page.getByRole("button", { name: /^Continue to /i }).click();
    await page.getByRole("button", { name: /Create League/i }).click();
    await expect(page.getByRole("heading", { name: /Invite managers/i })).toBeVisible();
    await page.getByRole("button", { name: /Open League Hub/i }).click();

    await page.waitForURL("**/league/1");
    await expect(page.getByRole("heading", { name: /^Roster$/i })).toBeVisible();
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

    await page.route("**/leagues/77/roster**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 77,
          roster: [],
          team: { id: 19, league_id: 77, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
          roster_slots: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4, IR: 1 },
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
    await expect(page.getByRole("heading", { name: /^Roster$/i })).toBeVisible();
    await expect(page.getByText(/Week 1 placeholder roster/i)).toBeVisible();
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
      members: Array.from({ length: 12 }, (_, index) => ({
        id: 701 + index,
        user_id: index === 0 ? 42 : 90 + index,
        role: index === 0 ? "commissioner" : "manager",
        joined_at: "2026-03-01T10:01:00Z",
      })),
    };

    const players = [
      {
        id: 501,
        name: "Arch Manning",
        position: "QB",
        school: "Texas",
        image_url: null,
        board_rank: 1,
        sheet_adp: 1,
        sheet_projected_season_points: 300,
        sheet_projection_stats: null,
        player_class: "FR",
        external_id: "arch-manning",
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

    await page.route("**/stats/teams?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [{ team: "Texas", conference: "SEC" }],
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
    await page.getByRole("button", { name: /^Draft$/i }).first().click();
    await expect(page.getByText(/Last pick/i)).toBeVisible();
    await expect(page.getByText(/Arch Manning/i).first()).toBeVisible();
    await expect(page.getByText(/No legal players available/i)).toBeVisible();
  });

  test("league matchup page renders projected teams and honest empty state", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const rosterRow = (
      id: number,
      teamId: number,
      teamName: string,
      playerName: string,
      projectedPoints: number,
      slot = "QB"
    ) => ({
      id,
      league_id: 1,
      team_id: teamId,
      fantasy_team_id: teamId,
      fantasy_team_name: teamName,
      player_id: id + 100,
      player_name: playerName,
      player_school: "Texas",
      player_position: "QB",
      school: "Texas",
      position: "QB",
      slot,
      roster_slot: slot,
      status: "active",
      is_starter: slot !== "BENCH" && slot !== "IR",
      is_ir: slot === "IR",
      opponent: teamId === 11 ? "Rival Team" : "Codex Team",
      projected_points: projectedPoints,
      weekly_projected_fantasy_points: projectedPoints,
    });
    const myRoster = [
      rosterRow(1, 11, "Codex Team", "Arch Manning", 24.0),
      rosterRow(2, 11, "Codex Team", "Bench Reserve", 11.5, "BENCH"),
    ];
    const opponentRoster = [
      rosterRow(3, 12, "Rival Team", "Rival QB", 18.2),
      rosterRow(4, 12, "Rival Team", "Rival Bench", 10.0, "BENCH"),
    ];
    const scheduledPayload = {
      league_id: 1,
      season: 2026,
      matchup_id: 101,
      week: 1,
      status: "projected",
      my_team: {
        id: 11,
        name: "Codex Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Codex Team",
        record: "0-0-0",
        projected_points: 24.0,
        projected_total: 24.0,
        win_probability: 57.3,
        roster: myRoster,
      },
      user_team: {
        id: 11,
        name: "Codex Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Codex Team",
        record: "0-0-0",
        projected_points: 24.0,
        projected_total: 24.0,
        win_probability: 57.3,
        roster: myRoster,
      },
      opponent_team: {
        id: 12,
        name: "Rival Team",
        fantasy_team_id: 12,
        fantasy_team_name: "Rival Team",
        record: "0-0-0",
        projected_points: 18.2,
        projected_total: 18.2,
        win_probability: 42.7,
        roster: opponentRoster,
      },
      my_roster: myRoster,
      opponent_roster: opponentRoster,
      projection_source: "weekly_projections",
      message: "Projection-only alpha matchup.",
    };
    const emptyPayload = {
      league_id: 1,
      season: 2026,
      matchup_id: null,
      week: 1,
      status: null,
      my_team: {
        id: 11,
        name: "Codex Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Codex Team",
        record: "0-0-0",
        projected_points: 24.0,
        projected_total: 24.0,
        win_probability: 50.0,
        roster: myRoster,
      },
      user_team: {
        id: 11,
        name: "Codex Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Codex Team",
        record: "0-0-0",
        projected_points: 24.0,
        projected_total: 24.0,
        win_probability: 50.0,
        roster: myRoster,
      },
      opponent_team: null,
      my_roster: myRoster,
      opponent_roster: [],
      projection_source: "weekly_projections",
      message: "No matchup generated yet.",
    };
    let matchupPayload: unknown = scheduledPayload;

    await page.route("**/leagues/1/matchup**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(matchupPayload),
      });
    });

    await page.goto("/league/1/matchup");
    await expect(page.getByRole("heading", { name: /^Matchup$/i })).toBeVisible();
    await expect(page.getByText("Codex Team").first()).toBeVisible();
    await expect(page.getByText("Rival Team").first()).toBeVisible();
    await expect(page.getByText("24.0 - 18.2")).toHaveCount(0);
    await expect(page.getByText("My Projection")).toBeVisible();
    await expect(page.getByText("Their Projection")).toBeVisible();
    await expect(page.getByText("24.0").first()).toBeVisible();
    await expect(page.getByText("18.2").first()).toBeVisible();
    await expect(page.getByText("57.3% / 42.7%")).toBeVisible();
    await expect(page.getByText("Arch Manning")).toBeVisible();
    await expect(page.getByText("Rival QB")).toBeVisible();

    matchupPayload = emptyPayload;
    await page.reload();
    await expect(page.getByText(/No matchup scheduled/i)).toBeVisible();
    await expect(page.getByText(/No matchup generated yet/i)).toBeVisible();
    await expect(page.getByText("Rival Team")).toHaveCount(0);
  });

  test("trade builder requires fresh analysis before sending an offer", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.addInitScript(() => {
      window.localStorage.setItem("cfb_active_league_id", "1");
    });

    const leagueDetail = {
      id: 1,
      name: "Trade Test League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: "TRADETESTCODE123456",
      description: null,
      icon_url: null,
      status: "post_draft",
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
        status: "completed",
      },
      members: [
        { id: 101, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
        { id: 102, user_id: 43, role: "manager", joined_at: "2026-03-02T10:01:00Z" },
      ],
    };
    const teams = [
      {
        id: 11,
        league_id: 1,
        name: "Codex Team",
        owner_name: "Codex",
        owner_user_id: 42,
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-01T10:00:00Z",
      },
      {
        id: 12,
        league_id: 1,
        name: "Rival Team",
        owner_name: "Rival",
        owner_user_id: 43,
        created_at: "2026-03-01T10:00:00Z",
        updated_at: "2026-03-01T10:00:00Z",
      },
    ];
    const rosterEntry = (id: number, teamId: number, playerId: number, name: string, position = "QB") => ({
      id,
      team_id: teamId,
      player_id: playerId,
      slot: position,
      status: "active",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-01T10:00:00Z",
      player: {
        id: playerId,
        name,
        position,
        school: "Texas",
      },
    });
    const settingsRosterRow = (
      id: number,
      teamId: number,
      teamName: string,
      playerId: number,
      playerName: string,
      projectedPoints: number
    ) => ({
      id,
      league_id: 1,
      team_id: teamId,
      fantasy_team_id: teamId,
      fantasy_team_name: teamName,
      player_id: playerId,
      player_name: playerName,
      player_school: "Texas",
      player_position: "QB",
      school: "Texas",
      position: "QB",
      slot: "QB",
      roster_slot: "QB",
      status: "active",
      is_starter: true,
      is_ir: false,
      opponent: null,
      projected_points: projectedPoints,
      weekly_projected_fantasy_points: projectedPoints,
    });
    let proposalPayload: unknown = null;
    let analyzePayload: unknown = null;

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [leagueDetail], total: 1, limit: 50, offset: 0 }),
      });
    });
    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagueDetail) });
    });
    await page.route("**/leagues/1/workspace", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league: leagueDetail,
          membership: { id: 101, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
          owned_team: { id: 11, league_id: 1, name: "Codex Team", owner_user_id: 42 },
          roster: [],
          matchup_summary: { week: 1, opponent_team_id: 12, opponent_team_name: "Rival Team", status: "projected" },
          standings_summary: [],
          allowed_actions: ["view_roster"],
        }),
      });
    });
    await page.route("**/leagues/1/teams", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: teams, total: teams.length, limit: 50, offset: 0 }),
      });
    });
    await page.route("**/leagues/1/settings-view", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          league_name: "Trade Test League",
          league_info: { name: "Trade Test League", season: 2026, status: "post_draft", max_teams: 2 },
          members: leagueDetail.members,
          scoring_settings: {},
          roster_settings: leagueDetail.settings.roster_slots_json,
          waiver_rules: { waiver_type: "faab", trade_review_type: "commissioner" },
          standings: [],
          schedule: [],
          rosters: [
            settingsRosterRow(1, 11, "Codex Team", 201, "Arch Manning", 24.0),
            settingsRosterRow(2, 12, "Rival Team", 301, "Rival QB", 18.0),
          ],
          draft_results: [],
          commissioner_controls: [],
        }),
      });
    });
    await page.route("**/teams/11/roster**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [rosterEntry(1, 11, 201, "Arch Manning")], total: 1, limit: 50, offset: 0 }),
      });
    });
    await page.route("**/teams/12/roster**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [rosterEntry(2, 12, 301, "Rival QB")], total: 1, limit: 50, offset: 0 }),
      });
    });
    await page.route("**/trade/analyze", async (route) => {
      analyzePayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ give_value: 24.0, receive_value: 18.0, delta: -6.0, verdict: "Strong Loss" }),
      });
    });
    await page.route("**/leagues/1/trades**", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: [], total: 0 }),
        });
        return;
      }
      proposalPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: 700,
          league_id: 1,
          proposing_team_id: 11,
          receiving_team_id: 12,
          created_by_user_id: 42,
          status: "proposed",
          message: null,
          accepted_at: null,
          process_after: null,
          processed_at: null,
          expires_at: null,
          failure_reason: null,
          created_at: "2026-07-10T20:00:00Z",
          updated_at: "2026-07-10T20:00:00Z",
          items: [],
          reviews: [],
        }),
      });
    });

    await page.goto("/trade");
    await expect(page.getByRole("heading", { name: /Trade Builder/i })).toBeVisible();
    await expect(page.getByText("Codex Team").first()).toBeVisible();
    await expect(page.getByText("Rival Team").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /Send Trade Offer/i })).toBeDisabled();

    await page.getByRole("button", { name: /Arch Manning/i }).click();
    await page.getByRole("button", { name: /Rival QB/i }).click();
    await expect(page.getByRole("button", { name: /Send Trade Offer/i })).toBeDisabled();
    await page.getByRole("button", { name: /Analyze Trade/i }).click();

    await expect(page.getByText("Strong Loss")).toBeVisible();
    await expect(page.getByText("-6.00")).toBeVisible();
    expect(analyzePayload).toMatchObject({
      give_ids: [201],
      receive_ids: [301],
      season: 2026,
      week: 1,
      league_size: 2,
    });

    await expect(page.getByText(/Sending is locked until the current offer has a fresh analysis/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Send Trade Offer/i })).toBeEnabled();
    await page.getByRole("button", { name: /Send Trade Offer/i }).click();
    expect(proposalPayload).toMatchObject({
      proposing_team_id: 11,
      receiving_team_id: 12,
      give_items: [{ team_id: 11, player_id: 201 }],
      receive_items: [{ team_id: 12, player_id: 301 }],
    });
  });

  test("single-player mock draft stays local and resets without real roster mutation", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const blockedMutations: string[] = [];
    const positions = ["QB", "RB", "WR", "TE", "K"];
    const players = Array.from({ length: 140 }, (_, index) => {
      const rank = index + 1;
      const position = positions[index % positions.length];
      return {
        id: rank,
        name: rank === 122 ? "Jeremiah Smith" : `Mock ${position} ${String(rank).padStart(3, "0")}`,
        position,
        school: `Mock School ${rank}`,
        image_url: null,
        board_rank: rank,
        sheet_adp: rank,
        sheet_projected_season_points: 300 - rank,
      };
    });
    const playerRequests: Array<{ limit: number; offset: number }> = [];

    await page.route("**/leagues/**/draft-picks", async (route) => {
      blockedMutations.push(route.request().url());
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "real draft mutation blocked" }) });
    });
    await page.route("**/teams/**/roster", async (route) => {
      blockedMutations.push(route.request().url());
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "real roster mutation blocked" }) });
    });
    await page.route("**/mock-drafts**", async (route) => {
      blockedMutations.push(route.request().url());
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "backend mock draft blocked" }) });
    });
    await page.route("**/stats/teams?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: players.map((player) => ({
            team: player.school,
            conference: "SEC",
          })),
        }),
      });
    });
    await page.route("**/players?**", async (route) => {
      const url = new URL(route.request().url());
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const limit = Number(url.searchParams.get("limit") ?? 100);
      playerRequests.push({ limit, offset });
      if (limit > 100) {
        await route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({ detail: "limit must be less than or equal to 100" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: players.slice(offset, offset + limit),
          total: players.length,
          limit,
          offset,
        }),
      });
    });

    await page.goto("/draft/mock/single-player?new=1&teams=8&timer=15");
    await expect(page.getByText(/Draft is about to begin/i)).toBeVisible();
    await expect(page.getByText(/Unable to load players/i)).toHaveCount(0);
    await expect(page.getByText("Jeremiah Smith")).toBeVisible();
    expect(playerRequests.some((request) => request.limit > 100)).toBe(false);
    expect(playerRequests).toEqual(
      expect.arrayContaining([
        { limit: 100, offset: 0 },
        { limit: 100, offset: 100 },
      ])
    );

    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const raw = window.localStorage.getItem("cfb_single_player_mock_draft");
            const draft = raw ? JSON.parse(raw) : null;
            return draft?.currentPick ?? 0;
          }),
        { timeout: 15_000 }
      )
      .toBe(4);

    const beforeUserPick = await page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}"));
    expect(beforeUserPick.picks).toHaveLength(3);
    expect(beforeUserPick.picks.every((pick: { pickedBy: string }) => pick.pickedBy === "bot")).toBe(true);

    await page.getByRole("button", { name: /^Draft$/ }).first().click();

    await expect
      .poll(() => page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}").picks?.length ?? 0))
      .toBe(4);

    const afterUserPick = await page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}"));
    expect(afterUserPick.picks[3].pickedBy).toBe("user");

    await expect
      .poll(() => page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}").picks?.length ?? 0), {
        timeout: 5_000,
      })
      .toBe(5);

    const afterCpuPick = await page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}"));
    expect(afterCpuPick.picks[4].pickedBy).toBe("bot");

    await page.getByRole("button", { name: /Reset/i }).first().click();

    await expect
      .poll(() =>
        page.evaluate(() => {
          const draft = JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}");
          return [draft.status, draft.currentPick, draft.picks?.length ?? -1];
        })
      )
      .toEqual(["intermission", 1, 0]);

    expect(blockedMutations).toEqual([]);
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

    await page.route("**/leagues/1/waivers**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          fantasy_team_id: 11,
          available_players: players.map((player) => ({
            id: player.id,
            name: player.name,
            position: player.position,
            school: player.school,
            weekly_projected_fantasy_points: player.id === 801 ? 24.0 : 18.5,
          })),
          claims: [],
          total_available: players.length,
          message: null,
        }),
      });
    });

    await page.goto("/league/1/waivers");
    await expect(page.getByRole("heading", { level: 1, name: /^Available Players$/i })).toBeVisible();

    await page.getByRole("button", { name: /^Watch$/i }).first().click();
    await expect(page.getByRole("button", { name: /^Watching$/i }).first()).toBeVisible();

    await page.goto("/league/1/watchlist");
    await expect(page.getByRole("heading", { name: /^Watchlist$/i })).toBeVisible();
    await expect(page.getByText("Arch Manning").first()).toBeVisible();

    await page.getByRole("button", { name: /Remove Arch Manning from watchlist/i }).evaluate((button) => {
      (button as HTMLButtonElement).click();
    });

    await expect(page.getByText(/No watched players yet/i)).toBeVisible();
  });

  test("available players page marks claims disabled and avoids add-drop", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const addDropCalls: string[] = [];
    await page.route("**/leagues/1/waivers**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          fantasy_team_id: 11,
          available_players: [
            { id: 901, name: "Arch Manning", position: "QB", school: "Texas", weekly_projected_fantasy_points: 24.0 },
            { id: 902, name: "Ryan Wingo", position: "WR", school: "Texas", weekly_projected_fantasy_points: 18.5 },
          ],
          claims: [],
          total_available: 2,
          message: null,
        }),
      });
    });
    await page.route("**/watchlists**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 50, offset: 0 }),
      });
    });
    await page.route("**/teams/**/add-drop", async (route) => {
      addDropCalls.push(route.request().url());
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "add/drop disabled" }) });
    });

    await page.goto("/league/1/waivers");
    await expect(page.getByRole("heading", { level: 1, name: /^Available Players$/i })).toBeVisible();
    await expect(page.getByText(/Claims are not enabled yet/i)).toBeVisible();
    await expect(page.getByText("Arch Manning")).toBeVisible();
    await expect(page.getByRole("button", { name: /^Add$/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Claims Off/i }).first()).toBeDisabled();
    expect(addDropCalls).toEqual([]);
  });
});
