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
  await page.route("**/chats/unread-summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ total_unread: 0 }),
    });
  });
};

test.describe("critical browser workflows", () => {
  test("Saturday Pick 6 dashboard action opens the contest instead of league creation", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 20, offset: 0 }),
      });
    });
    await page.route("**/notifications/alerts?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [] }),
      });
    });
    await page.route("**/saturday-pick-6/current?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          season: 2026,
          week_number: 1,
          title: "Saturday Pick 6",
          contest_position: "RB",
          status: "OPEN",
          lock_at: "2026-09-05T16:00:00Z",
          winning_player_ids: [],
          entry: null,
          sponsor: null,
          players: [
            {
              id: 1,
              player_id: 101,
              canonical_position: "RB",
              player_name: "Ahmad Hardy",
              school: "Missouri",
              opponent: "Arkansas-Pine Bluff",
              game_time: "2026-09-05T16:00:00Z",
              image_url: null,
              projected_points: 20.9,
              live_points: null,
              final_points: null,
              scoring_status: "NOT_STARTED",
              sort_order: 1,
            },
          ],
        }),
      });
    });

    await page.goto("/");
    await page.getByRole("link", { name: "Make Your Pick", exact: true }).click();

    await expect(page).toHaveURL(/\/saturday-pick-6$/);
    await expect(page.getByRole("heading", { name: "MAKE YOUR PICK", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "BUILD YOUR LEAGUE", exact: true })).not.toBeVisible();
  });

  test("locking a Saturday Pick 6 selection stays in the contest and confirms the pick", async ({ page }) => {
    await seedAuthenticatedSession(page);
    let entry: Record<string, unknown> | null = null;
    const contest = {
      id: 1,
      season: 2026,
      week_number: 1,
      title: "Saturday Pick 6",
      contest_position: "RB",
      status: "OPEN",
      lock_at: "2026-09-05T16:00:00Z",
      first_game_player: {
        id: 1,
        player_id: 101,
        player_name: "Ahmad Hardy",
        opponent: "Arkansas-Pine Bluff",
        game_time: "2026-09-05T16:00:00Z",
      },
      winning_player_ids: [],
      sponsor: null,
      players: [{
        id: 1,
        player_id: 101,
        canonical_position: "RB",
        player_name: "Ahmad Hardy",
        school: "Missouri",
        opponent: "Arkansas-Pine Bluff",
        game_time: "2026-09-05T16:00:00Z",
        image_url: null,
        projected_points: 20.9,
        live_points: null,
        final_points: null,
        scoring_status: "NOT_STARTED",
        sort_order: 1,
      }],
    };
    await page.route("**/saturday-pick-6/current?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...contest, entry }),
      });
    });
    await page.route("**/saturday-pick-6/1/entry", async (route) => {
      expect(route.request().method()).toBe("PUT");
      entry = {
        id: 88,
        selected_pick_player_id: 1,
        submitted_at: "2026-09-01T12:00:00Z",
        is_winner: false,
        reward_unlocked_at: null,
      };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(entry) });
    });

    await page.goto("/saturday-pick-6");
    await page.getByRole("button", { name: "Choose player", exact: true }).click();
    await page.getByRole("button", { name: "Lock In Pick", exact: true }).click();

    await expect(page).toHaveURL(/\/saturday-pick-6$/);
    await expect(page.getByText("Your pick is in", { exact: true })).toBeVisible();
    await expect(page.getByText("Your pick is in. Follow Ahmad Hardy this Saturday.", { exact: true })).toBeVisible();
    await expect(page.getByText(/Your pick can be changed until Ahmad Hardy's game starts at/).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "BUILD YOUR LEAGUE", exact: true })).not.toBeVisible();
  });

  test("Saturday Pick 6 finalization marks a losing pick and shows the winner reward state", async ({ page }) => {
    await seedAuthenticatedSession(page);
    let winner = false;
    const baseContest = {
      id: 1,
      season: 2026,
      week_number: 1,
      title: "Saturday Pick 6",
      contest_position: "RB",
      status: "FINAL",
      lock_at: "2026-09-05T16:00:00Z",
      first_game_player: { id: 1, player_id: 101, player_name: "Ahmad Hardy", opponent: "Arkansas-Pine Bluff", game_time: "2026-09-05T16:00:00Z" },
      sponsor: { name: "West Georgia Cornhole", logo_url: null, offer_text: null, terms: null, reward_unlocked: false, code: null, url: null },
      players: [
        { id: 1, player_id: 101, canonical_position: "RB", player_name: "Ahmad Hardy", school: "Missouri", opponent: "Arkansas-Pine Bluff", game_time: "2026-09-05T16:00:00Z", image_url: null, projected_points: 20.9, live_points: 14.2, final_points: 14.2, scoring_status: "FINAL", sort_order: 1 },
        { id: 2, player_id: 102, canonical_position: "RB", player_name: "Rival Runner", school: "Texas", opponent: "Ohio State", game_time: "2026-09-05T17:00:00Z", image_url: null, projected_points: 18.4, live_points: 22.3, final_points: 22.3, scoring_status: "FINAL", sort_order: 2 },
      ],
    };
    await page.route("**/saturday-pick-6/current?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...baseContest,
          winning_player_ids: winner ? [101] : [102],
          entry: { id: 88, selected_pick_player_id: 1, submitted_at: "2026-09-01T12:00:00Z", is_winner: winner, reward_unlocked_at: winner ? "2026-09-05T21:00:00Z" : null },
          sponsor: { ...baseContest.sponsor, reward_unlocked: winner },
        }),
      });
    });

    await page.goto("/saturday-pick-6");
    await expect(page.getByRole("heading", { name: "Not this week", exact: true })).toBeVisible();
    await expect(page.getByText("Ahmad Hardy did not finish first. Try again next week.")).toBeVisible();
    await expect(page.getByLabel("Your pick did not win")).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).first().click();

    winner = true;
    await page.reload();
    await expect(page.getByRole("heading", { name: "You got it right", exact: true })).toBeVisible();
    await expect(page.getByText("Your reward code is being prepared.")).toBeVisible();
  });

  test("mobile dashboard retains the normal page scroller outside draft rooms", async ({ page }, testInfo) => {
    await seedAuthenticatedSession(page);
    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 20, offset: 0 }),
      });
    });
    await page.route("**/notifications/alerts?**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [] }) });
    });
    await page.route("**/saturday-pick-6/current?**", async (route) => {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No active contest" }) });
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Good to see you, Codex/i })).toBeVisible();
    if (process.env.CAPTURE_MOBILE_UI === "1") {
      await page.screenshot({ path: testInfo.outputPath("mobile-home-390x844.png"), fullPage: false });
    }

    const scrollResult = await page.locator("main[data-app-scroll='true']").evaluate((element) => {
      const area = element as HTMLElement;
      area.scrollTop = area.scrollHeight;
      return {
        owner: area.dataset.scrollOwner,
        overflowY: getComputedStyle(area).overflowY,
        touchAction: getComputedStyle(area).touchAction,
        canScroll: area.scrollHeight > area.clientHeight,
        scrolled: area.scrollTop > 0,
        bodyOverflow: document.body.style.overflow,
      };
    });

    expect(scrollResult).toEqual({
      owner: "page",
      overflowY: "auto",
      touchAction: "pan-y",
      canScroll: true,
      scrolled: true,
      bodyOverflow: "",
    });
    await expect(page.getByText("Deadline and lock warnings should always be checked before kickoff.")).toBeVisible();

    await page.getByRole("navigation", { name: "Primary mobile navigation" }).getByRole("link", { name: "Leagues" }).click();
    await expect(page).toHaveURL(/\/leagues$/);
    await expect(page.getByRole("heading", { name: "Leagues", exact: true })).toBeVisible();
    await page.waitForTimeout(350);
    if (process.env.CAPTURE_MOBILE_UI === "1") {
      await page.screenshot({ path: testInfo.outputPath("mobile-leagues-390x844.png"), fullPage: false });
    }

    const leagueRouteResult = await page.locator("main[data-app-scroll='true']").evaluate((element) => {
      const area = element as HTMLElement;
      const heading = document.querySelector("h1");
      return {
        owner: area.dataset.scrollOwner,
        scrollTop: area.scrollTop,
        headingHeight: heading?.getBoundingClientRect().height ?? 0,
      };
    });
    expect(leagueRouteResult).toEqual({ owner: "page", scrollTop: 0, headingHeight: expect.any(Number) });
    expect(leagueRouteResult.headingHeight).toBeLessThan(48);

    await page.goto("/draft/mock/single-player?new=1&teams=8&timer=15");
    await expect(page.locator("main[data-app-scroll='true']")).toHaveAttribute("data-scroll-owner", "page");

    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Good to see you, Codex/i })).toBeVisible();
    const postDraftScrollResult = await page.locator("main[data-app-scroll='true']").evaluate((element) => {
      const area = element as HTMLElement;
      area.scrollTop = area.scrollHeight;
      return {
        owner: area.dataset.scrollOwner,
        scrollTop: area.scrollTop,
        bodyOverflow: document.body.style.overflow,
      };
    });
    expect(postDraftScrollResult).toEqual({ owner: "page", scrollTop: expect.any(Number), bodyOverflow: "" });
    expect(postDraftScrollResult.scrollTop).toBeGreaterThan(0);
  });

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
    await expect(page.getByRole("heading", { name: /^Sign in$/i })).toBeVisible();
    await page.getByPlaceholder("coach@saturday.com").fill("coach@example.com");
    await page.getByPlaceholder("••••••••").fill("password123");
    await page.getByRole("button", { name: /Sign In to Dashboard/i }).click();

    await page.waitForURL("**/");
    await expect(page.getByRole("heading", { name: /Good to see you, Codex/i })).toBeVisible();

    const token = await page.evaluate(() => window.localStorage.getItem("cfb_access_token"));
    const user = await page.evaluate(() => window.localStorage.getItem("cfb_user"));
    expect(token).toBe("mock-access-token");
    expect(user).toContain("coach@example.com");
  });

  test("signup is open without a beta code and preserves the authenticated session", async ({ page }) => {
    const readyUser = {
      ...mockAuthPayload.user,
      first_name: "Adam",
      email: "ci-beta-user@example.test",
      email_verified_at: "2026-07-10T20:00:00Z",
    };
    const signupPayload = {
      ...mockAuthPayload,
      access_token: "signup-access-token",
      user: readyUser,
    };

    await page.route("**/auth/signup", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(signupPayload),
      });
    });
    await page.route("**/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(readyUser),
      });
    });
    await page.route("**/auth/refresh", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "signup-access-token",
          access_token_expires_at: "2030-01-01T00:00:00Z",
        }),
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
    await page.route("**/notifications/alerts?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [] }),
      });
    });

    await page.goto("/signup");
    await expect(page).toHaveURL(/\/login\?flow=signup$/);
    await expect(page.getByRole("heading", { name: /Create account/i })).toBeVisible();
    await expect(page.locator("#signup-email")).not.toHaveAttribute("readonly", "");
    await page.locator("#signup-name").fill("Adam");
    await page.locator("#signup-email").fill("ci-beta-user@example.test");
    await page.locator("#signup-password").fill("StrongPass123!");
    await page.getByRole("button", { name: /Create (beta )?account/i }).click();
    await expect(page.getByRole("dialog", { name: /Account created/i })).toBeVisible();
    await expect(page.getByText("Save this password somewhere secure before continuing.")).toBeVisible();
    await page.getByRole("button", { name: /Continue to dashboard/i }).click();
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .toBe("signup-access-token");
    await page.waitForURL("**/");
    const endGuideButton = page.getByRole("button", { name: /End Guide/i });
    if (await endGuideButton.isVisible().catch(() => false)) {
      await endGuideButton.click();
    }
    await page.evaluate((userId) => {
      window.localStorage.setItem(`cfb_completed_guide_${userId}`, "true");
      window.localStorage.removeItem(`cfb_pending_guide_${userId}`);
    }, readyUser.id);

    await page.goto("/leagues");
    await expect(page.getByRole("heading", { name: /^Leagues$/i })).toBeVisible();
    const storedUser = await page.evaluate(() => window.localStorage.getItem("cfb_user"));
    expect(storedUser).toContain("ci-beta-user@example.test");
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
    await expect(page.getByRole("heading", { name: /^Draft Countdown$/i })).toBeVisible();
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
    await page.route("**/auth/refresh", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "invalid refresh token" }),
      });
    });

    await page.goto("/rosters");
    await page.waitForURL(/\/login$/);
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();

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
    await expect(page.getByRole("heading", { name: /Build your league/i })).toBeVisible();
    await page.getByRole("button", { name: "Continue to Settings", exact: true }).click();
    await expect(page.getByRole("heading", { name: "League Settings", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Continue to Draft", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Draft Schedule", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Continue to Review", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Review", exact: true })).toBeVisible();
    const scoringAcknowledgment = page.getByRole("checkbox", {
      name: "I understand that standard scoring and roster rules cannot be changed during the beta.",
    });
    const createLeagueButton = page.getByRole("button", { name: /Create League/i });
    await expect(scoringAcknowledgment).not.toBeChecked();
    await expect(createLeagueButton).toBeDisabled();
    await scoringAcknowledgment.check();
    await expect(scoringAcknowledgment).toBeChecked();
    await expect(createLeagueButton).toBeEnabled();
    await createLeagueButton.click();
    await expect(page.getByRole("heading", { name: /Invite managers/i })).toBeVisible();
    await page.getByRole("button", { name: /Open League Hub/i }).click();

    await page.waitForURL("**/league/1");
    await expect(page.getByRole("heading", { name: /^Draft Countdown$/i })).toBeVisible();
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
    await expect(page.getByRole("heading", { name: /^Draft Countdown$/i })).toBeVisible();
    await expect(page.getByText(/Draft room access stays locked/i)).toBeVisible();
  });

  test("draft-room pick mutation updates persisted draft state in UI", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagueDetail = {
      id: 1,
      name: "Draft Test League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
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
      members: Array.from({ length: 2 }, (_, index) => ({
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
      {
        id: 502,
        name: "Quinn Ewers",
        position: "QB",
        school: "Texas",
        image_url: null,
        board_rank: 2,
        sheet_adp: 2,
        sheet_projected_season_points: 294,
        sheet_projection_stats: null,
        player_class: "JR",
        external_id: "quinn-ewers",
      },
    ];

    let draftRoom = {
      league_id: 1,
      draft_id: 21,
      status: "on_clock",
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
    for (const viewport of [
      { width: 320, height: 568 },
      { width: 375, height: 667 },
      { width: 390, height: 844 },
      { width: 393, height: 852 },
      { width: 414, height: 896 },
      { width: 430, height: 932 },
    ]) {
      await page.setViewportSize(viewport);
      const row = page.getByTestId("draft-player-row").filter({ hasText: "Arch Manning" });
      await expect(row).toBeVisible();
      const draftButton = row.getByRole("button", { name: /^Draft Arch Manning$/i });
      await expect(draftButton).toBeVisible();
      await expect(row.getByRole("button", { name: /^Queue Arch Manning$/i })).toHaveCount(0);
      const geometry = await row.evaluate((element) => ({
        rowRight: element.getBoundingClientRect().right,
        documentWidth: document.documentElement.scrollWidth,
      }));
      const draftHeight = await draftButton.evaluate((element) => element.offsetHeight);
      expect(geometry.documentWidth).toBeLessThanOrEqual(viewport.width);
      expect(geometry.rowRight).toBeLessThanOrEqual(viewport.width);
      expect(draftHeight).toBeGreaterThanOrEqual(34);
      await expect(draftButton).toHaveClass(/min-h-\[44px\]/);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    const desktopRow = page.getByTestId("draft-player-row").filter({ hasText: "Arch Manning" });
    await expect(desktopRow.getByRole("button", { name: /^Draft Arch Manning$/i })).toBeVisible();
    await expect(desktopRow.getByRole("button", { name: /^Queue Arch Manning$/i })).toHaveCount(0);
    await page.setViewportSize({ width: 430, height: 932 });
    const draftScrollContract = await page.evaluate(() => {
      const appScroller = document.querySelector<HTMLElement>("main[data-app-scroll='true']");
      const playerList = document.querySelector<HTMLElement>("[data-testid='draft-player-list']");
      const tabs = document.querySelector<HTMLElement>("[data-testid='draft-room-tabs']");
      const filterButtons = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-testid='draft-player-filters'] button"));
      const viewportHeight = window.innerHeight;

      return {
        owner: appScroller?.getAttribute("data-scroll-owner"),
        outerScrollable: appScroller ? appScroller.scrollHeight > appScroller.clientHeight : null,
        listScrollable: playerList ? /auto|scroll/.test(getComputedStyle(playerList).overflowY) : null,
        tabsInViewport: tabs ? tabs.getBoundingClientRect().bottom <= viewportHeight : null,
        filtersOnOneLine: new Set(filterButtons.map((button) => Math.round(button.getBoundingClientRect().top))).size === 1,
        tabLabelsDoNotWrap: Array.from(document.querySelectorAll("[data-testid='draft-room-tabs'] button")).every(
          (button) => getComputedStyle(button).whiteSpace === "nowrap",
        ),
      };
    });
    expect(draftScrollContract).toEqual({
      owner: "page",
      outerScrollable: false,
      listScrollable: false,
      tabsInViewport: true,
      filtersOnOneLine: true,
      tabLabelsDoNotWrap: true,
    });
    await page
      .getByTestId("draft-player-row")
      .filter({ hasText: "Arch Manning" })
      .getByRole("button", { name: /^Draft Arch Manning$/i })
      .click();
    await expect(page.getByText(/Last pick/i)).toBeVisible();
    await expect(page.getByText(/Arch Manning/i).first()).toBeVisible();
    await expect(page.getByText(/^By Codex$/i)).toBeVisible();
    await expect(page.getByText(/Other Team/i).first()).toBeVisible();
    const queuedRow = page.getByTestId("draft-player-row").filter({ hasText: "Quinn Ewers" });
    await expect(page.getByTestId("draft-player-row").filter({ hasText: "Arch Manning" })).toHaveCount(0);
    await expect(queuedRow).toHaveText(/^2/);
    await expect(page.getByText(/^Draft Complete$/i)).toHaveCount(0);
    await expect(queuedRow.getByRole("button", { name: /^Draft Quinn Ewers$/i })).toHaveCount(0);
    await queuedRow.getByRole("button", { name: /^Queue Quinn Ewers$/i }).click();
    await expect(queuedRow.getByRole("button", { name: /Remove Quinn Ewers from queue/i })).toBeVisible();
  });

  test("a completed draft stops the timer and offers one clear roster exit", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagueDetail = {
      id: 1,
      name: "Completed Draft League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: "COMPLETEDDRAFTCODE",
      description: null,
      icon_url: null,
      status: "post_draft",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: { QB: 1, IR: 1 },
        playoff_teams: 4,
        waiver_type: "rolling",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        id: 22,
        league_id: 1,
        draft_datetime_utc: "2026-08-30T23:00:00Z",
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
        status: "completed",
      },
      members: [
        { id: 701, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
        { id: 702, user_id: 99, role: "manager", joined_at: "2026-03-01T10:01:00Z" },
      ],
    };

    const completedDraftRoom = {
      league_id: 1,
      draft_id: 22,
      status: "completed",
      pick_timer_seconds: 90,
      roster_slots: { QB: 1, IR: 1 },
      teams: [
        { id: 11, name: "Codex Team", owner_user_id: 42, owner_name: "Codex" },
        { id: 12, name: "Other Team", owner_user_id: 99, owner_name: "Other" },
      ],
      picks: [
        {
          id: 1,
          overall_pick: 1,
          round_number: 1,
          round_pick: 1,
          team_id: 11,
          team_name: "Codex Team",
          player_id: 501,
          player_name: "Arch Manning",
          player_position: "QB",
          player_school: "Texas",
          made_by_user_id: 42,
          created_at: "2026-03-21T10:00:00Z",
        },
        {
          id: 2,
          overall_pick: 2,
          round_number: 1,
          round_pick: 2,
          team_id: 12,
          team_name: "Other Team",
          player_id: 502,
          player_name: "Drew Allar",
          player_position: "QB",
          player_school: "Penn State",
          made_by_user_id: 99,
          created_at: "2026-03-21T10:01:00Z",
        },
      ],
      current_pick: 2,
      current_round: 1,
      current_round_pick: 2,
      current_team_id: null,
      current_team_name: null,
      user_team_id: 11,
      can_make_pick: false,
      can_start_draft: false,
      current_pick_started_at: null,
      current_pick_deadline: null,
      transition_ends_at: null,
      seconds_remaining: 0,
      draft_version: 3,
      server_time: "2026-03-21T10:01:00Z",
    };

    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagueDetail) });
    });
    await page.route("**/leagues/1/draft-room", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(completedDraftRoom) });
    });
    await page.route("**/players?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 250, offset: 0 }),
      });
    });
    await page.route("**/stats/teams?**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [] }) });
    });
    await page.route("**/leagues/1/roster?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          week: 1,
          owned_team: { id: 11, name: "Codex Team", owner_user_id: 42, record: null },
          team_rosters: [],
          slots: [],
          roster_slot_limits: { QB: 1, IR: 1 },
          ir_slots: 1,
        }),
      });
    });

    await page.goto("/league/1/draft");
    const completionDialog = page.getByRole("dialog", { name: /Draft Complete/i });
    await expect(completionDialog).toBeVisible();
    await expect(completionDialog.getByText(/Rosters finalized/i)).toBeVisible();
    await expect(page.getByText("Pick Timer", { exact: true })).toHaveCount(0);

    await completionDialog.getByRole("button", { name: "Stay in Draft Room" }).click();
    await expect(completionDialog).toHaveCount(0);

    await page.reload();
    await expect(completionDialog).toBeVisible();
    await completionDialog.getByRole("button", { name: "View Your Roster" }).click();
    await expect(page).toHaveURL(/\/league\/1\/roster$/);

    // A completed league must never reopen the pre-draft lobby through a
    // stale card link, browser history, or a copied lobby URL.
    await page.goto("/league/1/lobby");
    await expect(page).toHaveURL(/\/league\/1\/roster$/);
    await expect(page.getByText("Loading draft lobby...", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^Draft$/i })).toHaveCount(0);
  });

  test("league matchup page renders projected teams and honest empty state", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const leagueDetail = {
      id: 1,
      name: "Matchup Test League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: "MATCHUPTESTCODE",
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
        { id: 1, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
        { id: 2, user_id: 43, role: "manager", joined_at: "2026-03-01T10:01:00Z" },
      ],
    };

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
      rosterRow(1, 11, "Emily's Team", "Arch Manning", 133.1),
      rosterRow(2, 11, "Codex Team", "Bench Reserve", 11.5, "BENCH"),
    ];
    const opponentRoster = [
      rosterRow(3, 12, "Adam 2's Team", "Rival QB", 137.0),
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
        name: "Emily's Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Emily's Team",
        record: "0-0-0",
        projected_points: 133.1,
        projected_total: 133.1,
        win_probability: 48.05,
        roster: myRoster,
      },
      user_team: {
        id: 11,
        name: "Emily's Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Emily's Team",
        record: "0-0-0",
        projected_points: 133.1,
        projected_total: 133.1,
        win_probability: 48.05,
        roster: myRoster,
      },
      opponent_team: {
        id: 12,
        name: "Adam 2's Team",
        fantasy_team_id: 12,
        fantasy_team_name: "Adam 2's Team",
        record: "0-0-0",
        projected_points: 137.0,
        projected_total: 137.0,
        win_probability: 51.95,
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
        projected_points: 133.1,
        projected_total: 133.1,
        win_probability: null,
        roster: myRoster,
      },
      user_team: {
        id: 11,
        name: "Codex Team",
        fantasy_team_id: 11,
        fantasy_team_name: "Codex Team",
        record: "0-0-0",
        projected_points: 133.1,
        projected_total: 133.1,
        win_probability: null,
        roster: myRoster,
      },
      opponent_team: null,
      my_roster: myRoster,
      opponent_roster: [],
      projection_source: "weekly_projections",
      message: "No matchup generated yet.",
    };
    const alternatePayload = {
      ...scheduledPayload,
      matchup_id: 102,
      my_team: { ...scheduledPayload.my_team, projected_points: 120.0, projected_total: 120.0, win_probability: 70.0 },
      user_team: { ...scheduledPayload.user_team, projected_points: 120.0, projected_total: 120.0, win_probability: 70.0 },
      opponent_team: { ...scheduledPayload.opponent_team, projected_points: 100.0, projected_total: 100.0, win_probability: 30.0 },
    };
    let matchupPayload: unknown = scheduledPayload;

    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagueDetail) });
    });

    await page.route("**/leagues/1/matchup**", async (route) => {
      const url = new URL(route.request().url());
      const isScoreboardRequest = url.pathname.endsWith("/matchups");
      const isAlternateMatchup = url.searchParams.get("matchup_id") === "102";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          isScoreboardRequest
            ? {
                data: [
                  { matchup_id: 101, week: 1, status: "projected", home_team_name: "Emily's Team", away_team_name: "Adam 2's Team", home_score: 133.1, away_score: 137.0 },
                  { matchup_id: 102, week: 1, status: "projected", home_team_name: "League Mate One", away_team_name: "League Mate Two", home_score: 120.0, away_score: 100.0 },
                ],
                total: 2,
              }
            : isAlternateMatchup
              ? alternatePayload
              : matchupPayload,
        ),
      });
    });

    await page.goto("/league/1/matchup");
    await expect(page.getByRole("heading", { name: /^Matchup$/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Emily's Team vs Adam 2's Team" })).toBeVisible();
    await expect(page.getByText("133.1 - 137.0")).toHaveCount(0);
    await expect(page.getByText("My Projection")).toBeVisible();
    await expect(page.getByText("Their Projection")).toBeVisible();
    await expect(page.getByText("133.1").first()).toBeVisible();
    await expect(page.getByText("137.0").first()).toBeVisible();
    await expect(page.getByText("48.1% / 51.9%")).toBeVisible();
    await expect(page.getByText("Projected Leader").locator("..").getByText("Adam 2's Team")).toBeVisible();
    await expect(page.getByTestId("win-chance-left-bar")).toHaveAttribute("style", /width: 48\.05%/);
    await expect(page.getByTestId("win-chance-right-bar")).toHaveAttribute("style", /width: 51\.95%/);
    // The responsive matchup view keeps a compact mobile lineup mounted alongside
    // the desktop tables. Assert against the visible desktop player controls here
    // rather than an ambiguous text locator shared by both representations.
    await expect(page.getByRole("button", { name: /Arch Manning/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Rival QB/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Previous week" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Next week" })).toBeVisible();
    await expect(page.getByText("Prev", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Next", { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByText("48.1% / 51.9%")).toBeVisible();
    await page.getByRole("combobox", { name: "League matchup" }).selectOption("102");
    await expect(page.getByText("70.0% / 30.0%")).toBeVisible();
    await expect(page.getByTestId("win-chance-left-bar")).toHaveAttribute("style", /width: 70%/);

    await page.getByRole("button", { name: "Next week" }).click();
    await expect(page.getByTestId("matchup-week-label")).toHaveText("Week 2");
    await page.getByRole("button", { name: "Previous week" }).click();
    await expect(page.getByTestId("matchup-week-label")).toHaveText("Week 1");

    matchupPayload = emptyPayload;
    await page.reload();
    await expect(page.getByText(/No matchup scheduled/i)).toBeVisible();
    await expect(page.getByText(/No matchup generated yet/i)).toBeVisible();
    await expect(page.getByText("Rival Team")).toHaveCount(0);
  });

  test("league settings show every pre-scoring team at 0-0", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.addInitScript(() => {
      window.localStorage.setItem("cfb_active_league_id", "1");
    });

    const leagueDetail = {
      id: 1,
      name: "Preseason Standings League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: null,
      description: null,
      icon_url: null,
      status: "post_draft",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BENCH: 4 },
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
    await page.route("**/leagues/1/settings-view", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          league_name: leagueDetail.name,
          league_info: { name: leagueDetail.name, season: 2026, status: "post_draft", max_teams: 2 },
          members: leagueDetail.members,
          teams: [
            { id: 11, league_id: 1, name: "Codex Team", owner_user_id: 42 },
            { id: 12, league_id: 1, name: "Rival Team", owner_user_id: 43 },
          ],
          scoring_settings: {},
          roster_settings: leagueDetail.settings.roster_slots_json,
          waiver_rules: { waiver_type: "faab", waiver_period_hours: 24, trade_review_type: "commissioner" },
          standings: [],
          schedule: Array.from({ length: 13 }, (_, index) => ({
            matchup_id: index + 1,
            week: index + 1,
            home_team_id: 11,
            home_team_name: "Codex Team",
            away_team_id: 12,
            away_team_name: "Rival Team",
            home_projected_total: 100,
            away_projected_total: 96,
            home_win_probability: 56,
            away_win_probability: 44,
          })),
          rosters: [],
          trade_history: [
            {
              id: 77,
              status: "processed",
              proposing_party: { team_id: 11, team_name: "Codex Team", manager_name: "Adam" },
              receiving_party: { team_id: 12, team_name: "Rival Team", manager_name: "Guy" },
              proposing_team_sends: [{ player_id: 201, name: "Arch Manning", position: "QB", school: "Texas" }],
              receiving_team_sends: [{ player_id: 301, name: "Rival QB", position: "QB", school: "Oklahoma" }],
              created_at: "2026-08-21T16:00:00Z",
              accepted_at: "2026-08-21T17:00:00Z",
              processed_at: "2026-08-21T17:05:00Z",
            },
          ],
          draft_results: [],
          commissioner_controls: [],
        }),
      });
    });
    await page.route("**/leagues/1/transactions", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: [], total: 0, limit: 50, offset: 0 }),
      });
    });

    await page.goto("/league/1/settings");

    await expect(page.getByText("Codex Team", { exact: true })).toBeVisible();
    await expect(page.getByText("Rival Team", { exact: true })).toBeVisible();
    await expect(page.getByText("0-0", { exact: true })).toHaveCount(2);
    await expect(page.getByText("Standings are not available yet.", { exact: true })).toHaveCount(0);

    await page.getByRole("button", { name: "Point System", exact: true }).click();
    await expect(page.getByText("Roster System", { exact: true })).toBeVisible();
    await expect(page.getByText("Waiver System", { exact: true })).toBeVisible();
    await expect(page.getByText("FAAB", { exact: true })).toBeVisible();
    await expect(page.getByText("Waiver Type", { exact: true })).toHaveCount(0);

    await page.getByRole("button", { name: "Schedules", exact: true }).click();
    await expect(page.getByText("Weeks 1–13 · every team has one matchup each week.")).toBeVisible();
    const weekSelector = page.getByRole("group", { name: "Regular season week" });
    const weekThirteen = weekSelector.getByRole("button", { name: "Week 13", exact: true });
    await expect(weekThirteen).toBeVisible();
    await weekThirteen.click();
    await expect(weekThirteen).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Trade History", exact: true }).click();
    await expect(page.getByText("Managers: Adam and Guy", { exact: true })).toBeVisible();
    await expect(page.getByText("Codex Team sent", { exact: true })).toBeVisible();
    await expect(page.getByText("Arch Manning · QB · Texas", { exact: true })).toBeVisible();
    const viewTrade = page.getByRole("link", { name: "View trade", exact: true });
    await expect(viewTrade).toHaveAttribute("href", "/leagues/1/trades/77");
    await viewTrade.click();
    await expect(page).toHaveURL(/\/leagues\/1\/trades\/77$/);
  });

  test("league settings keeps draft results available before the draft begins", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.addInitScript(() => {
      window.localStorage.setItem("cfb_active_league_id", "1");
    });

    const leagueDetail = {
      id: 1,
      name: "Scheduled Draft League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: null,
      description: null,
      icon_url: null,
      status: "draft_scheduled",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: { QB: 1, BENCH: 4 },
        playoff_teams: 2,
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
      members: [{ id: 101, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" }],
    };

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [leagueDetail], total: 1, limit: 50, offset: 0 }) });
    });
    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagueDetail) });
    });
    await page.route("**/leagues/1/settings-view", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          league_name: leagueDetail.name,
          league_info: { name: leagueDetail.name, season: 2026, status: "draft_scheduled", max_teams: 2 },
          members: leagueDetail.members,
          teams: [{ id: 11, league_id: 1, name: "Codex Team", owner_user_id: 42 }],
          scoring_settings: {},
          roster_settings: leagueDetail.settings.roster_slots_json,
          waiver_rules: { waiver_type: "faab", waiver_period_hours: 24, trade_review_type: "commissioner" },
          standings: [],
          schedule: [],
          rosters: [],
          trade_history: [],
          draft_results: [],
          commissioner_controls: [],
        }),
      });
    });

    await page.goto("/league/1/settings");
    await expect(page).toHaveURL(/\/league\/1\/settings$/);
    await page.getByRole("button", { name: "Draft Results", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Draft Results", exact: true })).toBeVisible();
    await expect(page.getByText("No completed draft picks yet. Results will appear here as soon as the draft begins.")).toBeVisible();
  });

  test("manage roster can view every league team while only the owner can manage their lineup", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.addInitScript(() => {
      window.localStorage.setItem("cfb_active_league_id", "1");
    });

    const leagueDetail = {
      id: 1,
      name: "Roster Directory League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: null,
      description: null,
      icon_url: null,
      status: "post_draft",
      created_at: "2026-03-01T10:00:00Z",
      updated_at: "2026-03-05T10:00:00Z",
      settings: {
        id: 1,
        league_id: 1,
        scoring_json: {},
        roster_slots_json: { QB: 1, BENCH: 1 },
        playoff_teams: 2,
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
    const rosterPlayer = (teamId: number, teamName: string, playerId: number, playerName: string) => ({
      id: playerId,
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
      slot_id: `QB-${teamId}`,
      slot_index: 1,
      display_label: "QB",
      roster_slot: "QB",
      status: "active",
      is_starter: true,
      is_ir: false,
      opponent: "Oklahoma",
      projected_points: 22,
      weekly_projected_fantasy_points: 22,
      floor: 12,
      ceiling: 30,
      boom_prob: 0.3,
      bust_prob: 0.1,
      game_start_at: null,
      is_locked: false,
    });
    const myRoster = [rosterPlayer(11, "My Team", 201, "My QB")];
    const rivalRoster = [rosterPlayer(12, "Rival Team", 301, "Rival QB")];

    await page.route("**/leagues?**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [leagueDetail], total: 1, limit: 50, offset: 0 }) });
    });
    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagueDetail) });
    });
    await page.route("**/leagues/1/roster**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          league_id: 1,
          season: 2026,
          week: 1,
          owned_team: { id: 11, name: "My Team", owner_user_id: 42, record: "0-0-0" },
          fantasy_team_id: 11,
          fantasy_team_name: "My Team",
          roster: myRoster,
          data: myRoster,
          slots: myRoster,
          roster_slot_limits: { QB: 1, BENCH: 1 },
          ir_slots: 0,
          team_rosters: [
            { team: { id: 11, name: "My Team", owner_user_id: 42, record: "0-0-0" }, roster: myRoster },
            { team: { id: 12, name: "Rival Team", owner_user_id: 43, record: "0-0-0" }, roster: rivalRoster },
          ],
          message: null,
        }),
      });
    });

    await page.goto("/league/1/roster");
    await expect(page.getByText("My QB", { exact: true })).toBeVisible();
    await expect(page.getByText("Managing your roster", { exact: true })).toBeVisible();

    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "Rival Team", exact: true }).click();
    await expect(page.getByText("Rival QB", { exact: true })).toBeVisible();
    await expect(page.getByText("Viewing league roster", { exact: true })).toBeVisible();
    await expect(page.getByText("Rival Team · 0-0-0 · Read-only", { exact: true })).toBeVisible();
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
      const pathname = new URL(route.request().url()).pathname.replace(/^\/api/, "");
      if (pathname !== "/leagues/1/trades") {
        await route.fallback();
        return;
      }
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
    await expect(page.getByRole("button", { name: /^Analyze Trade$/i })).toBeDisabled();

    await page.getByRole("button", { name: /Arch Manning/i }).click();
    await page.getByRole("button", { name: /Rival QB/i }).click();
    await expect(page.getByRole("button", { name: /^Analyze Trade$/i })).toBeEnabled();
    await page.getByRole("button", { name: /Analyze Trade/i }).click();

    const reviewDialog = page.getByRole("dialog", { name: /Review Trade Offer/i });
    await expect(reviewDialog).toBeVisible();
    await expect(reviewDialog.getByText("Strong Loss")).toBeVisible();
    await expect(reviewDialog.getByText("-6.00")).toBeVisible();
    await expect.poll(() => analyzePayload).not.toBeNull();
    expect(analyzePayload).toMatchObject({
      give_ids: [201],
      receive_ids: [301],
      season: 2026,
      week: 1,
      league_id: 1,
      league_size: 2,
    });

    await expect(reviewDialog.getByRole("button", { name: /^Send Final Trade$/i })).toBeEnabled();
    await reviewDialog.getByRole("button", { name: /^Send Final Trade$/i }).click();
    await expect.poll(() => proposalPayload).not.toBeNull();
    expect(proposalPayload).toMatchObject({
      proposing_team_id: 11,
      receiving_team_id: 12,
      give_items: [{ team_id: 11, player_id: 201 }],
      receive_items: [{ team_id: 12, player_id: 301 }],
    });

    await page.route("**/leagues/1/trades/77", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 77,
          league_id: 1,
          proposing_team_id: 11,
          receiving_team_id: 12,
          created_by_user_id: 42,
          status: "processed",
          message: "Good luck this week.",
          accepted_at: "2026-09-01T12:00:00Z",
          process_after: null,
          processed_at: "2026-09-01T12:01:00Z",
          failure_reason: null,
          countered_from_trade_id: null,
          items: [
            { id: 1, trade_offer_id: 77, team_id: 11, player_id: 201, draft_pick_id: null, item_type: "player", player_name: "Arch Manning", player_position: "QB", player_school: "Texas" },
            { id: 2, trade_offer_id: 77, team_id: 12, player_id: 301, draft_pick_id: null, item_type: "player", player_name: "Rival QB", player_position: "QB", player_school: "Oregon" },
          ],
        }),
      });
    });

    await page.goto("/leagues/1/trades/77?returnTo=%2Fchats%3FleagueId%3D1%26threadId%3D9");
    const focusedOffer = page.getByRole("dialog", { name: /Review Trade Offer/i });
    await expect(focusedOffer).toBeVisible();
    await expect(focusedOffer.getByText("Arch Manning", { exact: true })).toBeVisible();
    await focusedOffer.getByRole("button", { name: "Back to league chat", exact: true }).click();
    await expect(page).toHaveURL(/\/chats\?leagueId=1&threadId=9$/);
  });

  test("single-player mock draft stays local and resets without real roster mutation", async ({ page }, testInfo) => {
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
    const playerRequests: Array<{ limit: number; offset: number; draftEligible: string | null }> = [];

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
      playerRequests.push({
        limit,
        offset,
        draftEligible: url.searchParams.get("draft_eligible"),
      });
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
    for (const viewport of [
      { width: 320, height: 568 },
      { width: 375, height: 667 },
      { width: 390, height: 844 },
      { width: 393, height: 852 },
      { width: 414, height: 896 },
      { width: 430, height: 932 },
    ]) {
      await page.setViewportSize(viewport);
      const row = page.getByTestId("draft-player-row").filter({ hasText: "Jeremiah Smith" });
      await expect(row).toBeVisible();
      const queueButton = row.getByRole("button", { name: /^Queue Jeremiah Smith$/i });
      await expect(queueButton).toBeVisible();
      await expect(row.getByRole("button", { name: /^Draft Jeremiah Smith$/i })).toHaveCount(0);
      const geometry = await row.evaluate((element) => ({
        rowRight: element.getBoundingClientRect().right,
        documentWidth: document.documentElement.scrollWidth,
      }));
      const queueHeight = await queueButton.evaluate((element) => element.offsetHeight);
      expect(geometry.documentWidth).toBeLessThanOrEqual(viewport.width);
      expect(geometry.rowRight).toBeLessThanOrEqual(viewport.width);
      expect(queueHeight).toBeGreaterThanOrEqual(34);
      await expect(queueButton).toHaveClass(/min-h-\[44px\]/);
      if (process.env.CAPTURE_MOBILE_UI === "1") {
        await page.screenshot({ path: testInfo.outputPath(`mobile-mock-draft-${viewport.width}x${viewport.height}.png`), fullPage: false });
      }
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    const desktopRow = page.getByTestId("draft-player-row").filter({ hasText: "Jeremiah Smith" });
    await expect(desktopRow.getByRole("button", { name: /^Queue Jeremiah Smith$/i })).toBeVisible();
    await expect(desktopRow.getByRole("button", { name: /^Draft Jeremiah Smith$/i })).toHaveCount(0);
    await page.setViewportSize({ width: 430, height: 932 });
    const scrollContract = await page.evaluate(() => {
      const appScroller = document.querySelector<HTMLElement>("main[data-app-scroll='true']");
      const playerList = document.querySelector<HTMLElement>("[data-testid='draft-player-list']");
      const tabs = document.querySelector<HTMLElement>("[data-testid='draft-room-tabs']");
      const filterButtons = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-testid='draft-player-filters'] button"));
      appScroller?.scrollTo({ top: 800, behavior: "auto" });

      return {
        owner: appScroller?.getAttribute("data-scroll-owner"),
        outerScrollable: appScroller ? appScroller.scrollHeight > appScroller.clientHeight : null,
        listScrollable: playerList ? /auto|scroll/.test(getComputedStyle(playerList).overflowY) : null,
        tabsInViewport: tabs ? tabs.getBoundingClientRect().bottom <= window.innerHeight : null,
        appScrollTop: appScroller?.scrollTop ?? 0,
        filtersOnOneLine: new Set(filterButtons.map((button) => Math.round(button.getBoundingClientRect().top))).size === 1,
        tabLabelsDoNotWrap: Array.from(document.querySelectorAll("[data-testid='draft-room-tabs'] button")).every(
          (button) => getComputedStyle(button).whiteSpace === "nowrap",
        ),
      };
    });
    expect(scrollContract).toEqual({
      owner: "page",
      outerScrollable: true,
      listScrollable: false,
      tabsInViewport: true,
      appScrollTop: expect.any(Number),
      filtersOnOneLine: true,
      tabLabelsDoNotWrap: true,
    });
    expect(scrollContract.appScrollTop).toBeGreaterThan(0);
    await page.evaluate(() => document.querySelector<HTMLElement>("main[data-app-scroll='true']")?.scrollTo({ top: 0, behavior: "auto" }));
    expect(playerRequests.some((request) => request.limit > 100)).toBe(false);
    expect(playerRequests).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ limit: 100, offset: 0, draftEligible: "true" }),
        expect.objectContaining({ limit: 100, offset: 100, draftEligible: "true" }),
      ])
    );
    expect(playerRequests.every((request) => request.draftEligible === "true")).toBe(true);

    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const raw = window.localStorage.getItem("cfb_single_player_mock_draft");
            const draft = raw ? JSON.parse(raw) : null;
            return draft?.currentPick === draft?.userTeamId;
          }),
        { timeout: 25_000 }
      )
      .toBe(true);

    const beforeUserPick = await page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}"));
    expect(beforeUserPick.picks).toHaveLength(beforeUserPick.userTeamId - 1);
    expect(beforeUserPick.picks.every((pick: { pickedBy: string }) => pick.pickedBy === "bot")).toBe(true);

    await page.getByRole("button", { name: /^Draft / }).first().click();

    await expect
      .poll(() => page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}").picks?.some((pick: { pickedBy: string }) => pick.pickedBy === "user") ?? false))
      .toBe(true);

    const afterUserPick = await page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}"));
    const userPickIndex = afterUserPick.picks.findIndex((pick: { pickedBy: string }) => pick.pickedBy === "user");
    expect(userPickIndex).toBe(beforeUserPick.userTeamId - 1);
    expect(afterUserPick.picks[userPickIndex].pickedBy).toBe("user");

    await expect
      .poll(() => page.evaluate((index) => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}").picks?.[index + 1]?.pickedBy ?? null, userPickIndex), {
        timeout: 5_000,
      })
      .toBe("bot");

    const afterCpuPick = await page.evaluate(() => JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}"));
    expect(afterCpuPick.picks[userPickIndex + 1].pickedBy).toBe("bot");

    const rosterPlayerName = afterUserPick.picks[userPickIndex].playerName;
    await page.getByRole("button", { name: /^Roster$/ }).click();
    await page.getByRole("button", { name: `Open ${rosterPlayerName} player card` }).click();
    await expect(page.getByRole("dialog", { name: `${rosterPlayerName} player card` })).toBeVisible();
    await page.getByRole("button", { name: "Close player card" }).click();

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

  test("mock draft reconciles a legacy alias so a drafted player cannot remain on the board", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.addInitScript(() => {
      const now = Date.now();
      const teams = Array.from({ length: 8 }, (_, index) => ({
        id: index + 1,
        name: index === 3 ? "Your Team" : `Bot Team ${index + 1}`,
        managerType: index === 3 ? "user" : "bot",
      }));
      window.localStorage.setItem(
        "cfb_single_player_mock_draft",
        JSON.stringify({
          id: "legacy-mock",
          settings: { leagueSize: 8, rounds: 13, pickTimerSeconds: 30 },
          status: "intermission",
          createdAt: now,
          intermissionEndsAt: now + 30_000,
          currentPick: 2,
          pickStartedAt: null,
          pickExpiresAt: null,
          userTeamId: 4,
          teams,
          queuedPlayerIds: [],
          picks: [
            {
              overallPick: 1,
              round: 1,
              roundPick: 1,
              teamId: 1,
              teamName: "Bot Team 1",
              playerId: -101,
              playerName: "Ian Strong",
              position: "WR",
              school: "Cal",
              projectedPoints: 191,
              draftRank: 15,
              masterDraftRank: 15,
              assignedSlot: "WR",
              pickedBy: "bot",
              madeAt: now,
            },
          ],
        })
      );
    });

    await page.route("**/players?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: [
            {
              id: 101,
              name: "Ian Strong",
              position: "WR",
              school: "California",
              image_url: null,
              board_rank: 136,
              sheet_adp: 136,
              sheet_projected_season_points: 190.2,
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      });
    });
    await page.route("**/stats/teams?**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [] }) });
    });

    await page.goto("/draft/mock/single-player");
    await expect
      .poll(() =>
        page.evaluate(() => {
          const stored = JSON.parse(window.localStorage.getItem("cfb_single_player_mock_draft") ?? "{}");
          return stored.picks?.map((pick: { playerId: number; school: string }) => [pick.playerId, pick.school]);
        })
      )
      .toEqual([[101, "California"]]);

    // Ian remains in historical pick UI only; the live available board is empty.
    await expect(page.getByTestId("draft-player-row")).toHaveCount(0);
    await expect(page.getByText("Cal", { exact: true })).toHaveCount(0);
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
        status: "post_draft",
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
          status: "completed",
        },
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

    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagues[0]) });
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
      const path = url.pathname.replace(/^\/api/, "");

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
          roster: [],
          waiver_rules: { waiver_type: "rolling" },
          total_available: players.length,
          message: null,
        }),
      });
    });

    await page.goto("/league/1/waivers");
    await expect(page.getByRole("heading", { level: 1, name: /^Available Players$/i })).toBeVisible();

    const archManningRow = page.getByText("Arch Manning").locator("xpath=ancestor::tr");
    await archManningRow.getByRole("button", { name: /^Watch$/i }).click();
    await expect(archManningRow.getByRole("button", { name: /^Watching$/i })).toBeVisible();

    await page.goto("/league/1/watchlist");
    await expect(page.getByRole("heading", { name: /^Watchlist$/i })).toBeVisible();
    await expect(page.getByText("Arch Manning").first()).toBeVisible();

    await page.getByRole("button", { name: /Remove Arch Manning from watchlist/i }).evaluate((button) => {
      (button as HTMLButtonElement).click();
    });

    await expect(page.getByText(/No watched players yet/i)).toBeVisible();
  });

  test("available players page submits a waiver claim without using the legacy add-drop endpoint", async ({ page }) => {
    await seedAuthenticatedSession(page);

    const addDropCalls: string[] = [];
    let claimPayload: unknown = null;
    const leagueDetail = {
      id: 1,
      name: "Waiver Test League",
      commissioner_user_id: 42,
      season_year: 2026,
      max_teams: 2,
      is_private: true,
      invite_code: "WAIVERTESTCODE",
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
        { id: 1, user_id: 42, role: "commissioner", joined_at: "2026-03-01T10:01:00Z" },
        { id: 2, user_id: 43, role: "manager", joined_at: "2026-03-01T10:01:00Z" },
      ],
    };
    const availablePlayers = [
      { id: 901, name: "Arch Manning", position: "QB", school: "Texas", board_rank: 1, sheet_adp: 1 },
      { id: 902, name: "Ryan Wingo", position: "WR", school: "Texas", board_rank: 2, sheet_adp: 2 },
    ];
    await page.route("**/leagues/1", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(leagueDetail) });
    });
    await page.route("**/players?**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: availablePlayers, total: availablePlayers.length, limit: 100, offset: 0 }),
      });
    });
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
          roster: [],
          waiver_rules: { waiver_type: "faab" },
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
    await page.route("**/leagues/1/waivers/claims", async (route) => {
      claimPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: 301,
          league_id: 1,
          team_id: 11,
          add_player_id: 901,
          add_player_name: "Arch Manning",
          drop_roster_entry_id: null,
          faab_bid: 0,
          status: "pending",
          process_after: "2026-08-31T12:00:00Z",
        }),
      });
    });
    await page.route("**/teams/**/add-drop", async (route) => {
      addDropCalls.push(route.request().url());
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "add/drop disabled" }) });
    });

    await page.goto("/league/1/waivers");
    await expect(page.getByRole("heading", { level: 1, name: /^Available Players$/i })).toBeVisible();
    await expect(page.getByText(/No active or recent waiver claims/i)).toBeVisible();
    await expect(page.getByText("Arch Manning")).toBeVisible();
    await expect(page.getByRole("button", { name: /^Add$/i })).toHaveCount(0);
    const archManningRow = page.getByText("Arch Manning").locator("xpath=ancestor::tr");
    await archManningRow.getByRole("button", { name: /^Claim$/i }).click();
    const claimDialog = page.getByRole("dialog", { name: /Submit Waiver Claim/i });
    await expect(claimDialog).toBeVisible();
    await claimDialog.getByRole("button", { name: /Confirm Waiver Claim/i }).click();
    await expect.poll(() => claimPayload).not.toBeNull();
    expect(claimPayload).toMatchObject({
      team_id: 11,
      add_player_id: 901,
      faab_bid: 0,
    });
    expect(addDropCalls).toEqual([]);
  });
});
