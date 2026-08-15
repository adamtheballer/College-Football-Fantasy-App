import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

const enabled = process.env.REAL_STACK_E2E === "1";
const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";
const betaFixtures = {
  proposer: {
    email: "ci-beta-trade-proposer@example.test",
    code: "EARLY-CI1237",
  },
  recipient: {
    email: "ci-beta-trade-recipient@example.test",
    code: "EARLY-CI1238",
  },
} as const;
const ciAdminFixture = {
  email: "ci-e2e-admin@example.test",
  password: "E2E-Only-Admin-Pass-2026!",
} as const;

type AuthSession = {
  access_token: string;
  access_token_expires_at: string;
  user: { id: number; first_name: string; email: string };
};

type LeagueTeam = { id: number; owner_user_id: number | null };
type Player = { id: number; name: string; position: string };
type RosterEntry = { slot: string; player: Player | null };

const authHeaders = (session: AuthSession) => ({
  Authorization: `Bearer ${session.access_token}`,
});
const unique = (label: string) =>
  `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

async function signup(
  request: APIRequestContext,
  firstName: string,
  fixture: { email: string; code: string },
): Promise<AuthSession> {
  const betaAccess = await request.post(`${apiBaseUrl}/beta-access/validate`, {
    data: { email: fixture.email, code: fixture.code },
  });
  expect(betaAccess.status()).toBe(200);
  const reservation = (await betaAccess.json()) as {
    reservation_token: string;
  };
  const response = await request.post(`${apiBaseUrl}/auth/signup`, {
    data: {
      first_name: firstName,
      email: fixture.email,
      password: "StrongPass123!",
      beta_access_reservation: reservation.reservation_token,
    },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

async function login(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<AuthSession> {
  const response = await request.post(`${apiBaseUrl}/auth/login`, {
    data: { email, password },
  });
  expect(response.status()).toBe(200);
  return response.json();
}

async function createLeague(
  request: APIRequestContext,
  session: AuthSession,
  name: string,
) {
  const response = await request.post(`${apiBaseUrl}/leagues`, {
    headers: authHeaders(session),
    data: {
      basics: {
        name,
        season_year: 2026,
        max_teams: 2,
        is_private: true,
        description: null,
        icon_url: null,
      },
      settings: {
        scoring_json: { ppr: 1 },
        roster_slots_json: {
          QB: 1,
          RB: 1,
          WR: 1,
          TE: 1,
          BENCH: 4,
          K: 1,
          IR: 1,
        },
        playoff_teams: 2,
        waiver_type: "faab",
        trade_review_type: "none",
        superflex_enabled: false,
        kicker_enabled: true,
        defense_enabled: false,
      },
      draft: {
        draft_datetime_utc: "2026-08-19T18:00:00Z",
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 90,
      },
    },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).league as { id: number; name: string };
}

async function joinLeague(
  request: APIRequestContext,
  session: AuthSession,
  leagueId: number,
) {
  const response = await request.post(
    `${apiBaseUrl}/leagues/${leagueId}/join`,
    { headers: authHeaders(session) },
  );
  expect(response.status()).toBe(200);
}

async function getLeagueTeams(
  request: APIRequestContext,
  session: AuthSession,
  leagueId: number,
): Promise<LeagueTeam[]> {
  const response = await request.get(
    `${apiBaseUrl}/leagues/${leagueId}/teams`,
    { headers: authHeaders(session) },
  );
  expect(response.status()).toBe(200);
  return (await response.json()).data;
}

async function getDraftablePlayers(request: APIRequestContext): Promise<{
  quarterback: Player;
  backupQuarterback: Player;
  runningBack: Player;
  backupRunningBack: Player;
}> {
  const response = await request.get(
    `${apiBaseUrl}/players?limit=100&sort=rank`,
  );
  expect(response.status()).toBe(200);
  const players = (await response.json()).data as Player[];
  const quarterbacks = players.filter((player) => player.position === "QB");
  const runningBacks = players.filter((player) => player.position === "RB");
  expect(quarterbacks.length).toBeGreaterThanOrEqual(2);
  expect(runningBacks.length).toBeGreaterThanOrEqual(2);
  return {
    quarterback: quarterbacks[0]!,
    backupQuarterback: quarterbacks[1]!,
    runningBack: runningBacks[0]!,
    backupRunningBack: runningBacks[1]!,
  };
}

async function addRosterPlayer(
  request: APIRequestContext,
  session: AuthSession,
  teamId: number,
  player: Player,
  slot: string,
) {
  const response = await request.post(`${apiBaseUrl}/teams/${teamId}/roster`, {
    headers: authHeaders(session),
    data: { player_id: player.id, slot, status: "active" },
  });
  expect(response.status()).toBe(201);
}

async function rosterEntries(
  request: APIRequestContext,
  session: AuthSession,
  teamId: number,
): Promise<RosterEntry[]> {
  const response = await request.get(`${apiBaseUrl}/teams/${teamId}/roster`, {
    headers: authHeaders(session),
  });
  expect(response.status()).toBe(200);
  return (await response.json()).data;
}

async function rosterPlayerIds(
  request: APIRequestContext,
  session: AuthSession,
  teamId: number,
): Promise<number[]> {
  return (await rosterEntries(request, session, teamId))
    .map((entry) => entry.player?.id)
    .filter(
      (playerId: number | undefined): playerId is number =>
        playerId !== undefined,
    );
}

function expectRosterCapacityLegal(entries: RosterEntry[]) {
  const populatedEntries = entries.filter(
    (entry): entry is RosterEntry & { player: Player } => entry.player !== null,
  );
  const slotCounts = populatedEntries.reduce<Record<string, number>>(
    (counts, entry) => ({
      ...counts,
      [entry.slot]: (counts[entry.slot] ?? 0) + 1,
    }),
    {},
  );
  expect(slotCounts.QB ?? 0).toBeLessThanOrEqual(1);
  expect(slotCounts.RB ?? 0).toBeLessThanOrEqual(1);
  expect(slotCounts.BENCH ?? 0).toBeLessThanOrEqual(4);
  for (const entry of populatedEntries) {
    const validSlots =
      entry.player.position === "QB" ? ["QB", "BENCH"] : ["RB", "BENCH"];
    expect(validSlots).toContain(entry.slot);
  }
}

async function primeBrowserSession(page: Page, session: AuthSession) {
  await page.addInitScript(
    (payload) => {
      window.localStorage.setItem("cfb_access_token", payload.accessToken);
      window.localStorage.setItem(
        "cfb_access_token_expires_at",
        payload.expiresAt,
      );
      window.localStorage.setItem(
        "cfb_user",
        JSON.stringify({
          id: payload.user.id,
          firstName: payload.user.first_name,
          email: payload.user.email,
          isAdmin: false,
        }),
      );
      window.localStorage.setItem(
        `cfb_completed_guide_${payload.user.id}`,
        "true",
      );
    },
    {
      accessToken: session.access_token,
      expiresAt: session.access_token_expires_at,
      user: session.user,
    },
  );
}

test.describe("real FastAPI/PostgreSQL league chat", () => {
  test.skip(
    !enabled,
    "Set REAL_STACK_E2E=1 after starting FastAPI and PostgreSQL; this suite never mocks chat endpoints.",
  );
  test.setTimeout(90_000);

  test("two league members exchange messages and see a binding trade card without cross-league leakage", async ({
    browser,
    request,
  }) => {
    const userA = await signup(request, "Avery", betaFixtures.proposer);
    const userB = await signup(request, "Blake", betaFixtures.recipient);
    const leagueOne = await createLeague(
      request,
      userA,
      unique("Chat League One"),
    );
    await joinLeague(request, userB, leagueOne.id);

    const contextA = await browser.newContext();
    const pageA = await contextA.newPage();
    await primeBrowserSession(pageA, userA);
    await pageA.goto("/chats");
    await expect(pageA.getByText("# General").first()).toBeVisible();
    await pageA
      .getByPlaceholder("Message your league…")
      .fill("Good luck this week");
    await Promise.all([
      pageA.waitForResponse(
        (response) =>
          response.url().includes(`/leagues/${leagueOne.id}/chats/`) &&
          response.request().method() === "POST",
      ),
      pageA.getByRole("button", { name: /^send$/i }).click(),
    ]);

    const beforeOpen = await request.get(`${apiBaseUrl}/chats/unread-summary`, {
      headers: authHeaders(userB),
    });
    expect(beforeOpen.status()).toBe(200);
    expect((await beforeOpen.json()).total_unread).toBe(1);

    const contextB = await browser.newContext();
    const pageB = await contextB.newPage();
    await primeBrowserSession(pageB, userB);
    await pageB.goto("/chats");
    await expect(pageB.getByText("# General").first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(pageB.getByText("Good luck this week").last()).toBeVisible({
      timeout: 15_000,
    });
    await expect
      .poll(async () => {
        const response = await request.get(
          `${apiBaseUrl}/chats/unread-summary`,
          { headers: authHeaders(userB) },
        );
        return (await response.json()).total_unread;
      })
      .toBe(0);

    await pageA.getByRole("button", { name: /new message/i }).click();
    await pageA.getByRole("button", { name: /Blake/i }).last().click();
    const directThreadRowA = pageA
      .getByRole("button", { name: /Blake/i })
      .last();
    await expect(directThreadRowA).toBeVisible();
    await directThreadRowA.click();
    await expect(
      pageA.getByRole("heading", { name: /Direct message.*Blake/i }),
    ).toBeVisible();
    await pageA
      .getByPlaceholder("Message your league…")
      .fill("Private trade thought");
    await Promise.all([
      pageA.waitForResponse(
        (response) =>
          response.url().includes(`/leagues/${leagueOne.id}/chats/`) &&
          response.request().method() === "POST",
      ),
      pageA.getByRole("button", { name: /^send$/i }).click(),
    ]);

    const directUnread = await request.get(
      `${apiBaseUrl}/chats/unread-summary`,
      { headers: authHeaders(userB) },
    );
    expect((await directUnread.json()).total_unread).toBe(1);
    await pageB.getByRole("button", { name: /Avery/i }).last().click();
    await expect(pageB.getByText("Private trade thought").last()).toBeVisible();

    const teams = await getLeagueTeams(request, userA, leagueOne.id);
    const averyTeam = teams.find(
      (team) => team.owner_user_id === userA.user.id,
    );
    const blakeTeam = teams.find(
      (team) => team.owner_user_id === userB.user.id,
    );
    expect(averyTeam).toBeTruthy();
    expect(blakeTeam).toBeTruthy();
    const { quarterback, backupQuarterback, runningBack, backupRunningBack } =
      await getDraftablePlayers(request);
    await addRosterPlayer(request, userA, averyTeam!.id, quarterback, "QB");
    await addRosterPlayer(
      request,
      userA,
      averyTeam!.id,
      backupQuarterback,
      "BENCH",
    );
    await addRosterPlayer(request, userB, blakeTeam!.id, runningBack, "RB");
    await addRosterPlayer(
      request,
      userB,
      blakeTeam!.id,
      backupRunningBack,
      "BENCH",
    );

    const tradeCreate = await request.post(
      `${apiBaseUrl}/leagues/${leagueOne.id}/trades`,
      {
        headers: authHeaders(userA),
        data: {
          proposing_team_id: averyTeam!.id,
          receiving_team_id: blakeTeam!.id,
          give_items: [{ team_id: averyTeam!.id, player_id: quarterback.id }],
          receive_items: [
            { team_id: blakeTeam!.id, player_id: runningBack.id },
          ],
          message: "Real-stack chat trade",
        },
      },
    );
    expect(tradeCreate.status()).toBe(201);
    const trade = await tradeCreate.json();

    const privateThreadsResponse = await request.get(
      `${apiBaseUrl}/leagues/${leagueOne.id}/chats`,
      { headers: authHeaders(userB) },
    );
    expect(privateThreadsResponse.status()).toBe(200);
    const privateThread = (await privateThreadsResponse.json()).data.find(
      (thread: { thread_type: string }) => thread.thread_type === "direct",
    );
    expect(privateThread).toBeTruthy();
    const privateMessagesResponse = await request.get(
      `${apiBaseUrl}/leagues/${leagueOne.id}/chats/${privateThread.id}/messages`,
      { headers: authHeaders(userB) },
    );
    expect(privateMessagesResponse.status()).toBe(200);
    const pendingPrivateCards = (
      await privateMessagesResponse.json()
    ).data.filter(
      (message: {
        metadata: {
          card_type?: string;
          trade_id?: number;
          trade_status?: string;
        };
      }) =>
        message.metadata.card_type === "private_trade_offer" &&
        message.metadata.trade_id === trade.id &&
        message.metadata.trade_status === "proposed",
    );
    expect(pendingPrivateCards).toHaveLength(1);

    await pageB.reload();
    await pageB.getByRole("button", { name: /Avery/i }).last().click();
    await expect(pageB.getByText("Trade offer pending").last()).toBeVisible();
    await expect(
      pageB.getByRole("link", { name: "Review trade" }).last(),
    ).toBeVisible();

    const tradeAccept = await request.post(
      `${apiBaseUrl}/leagues/${leagueOne.id}/trades/${trade.id}/accept`,
      {
        headers: authHeaders(userB),
        data: {},
      },
    );
    expect(tradeAccept.status()).toBe(200);
    const acceptedTrade = await tradeAccept.json();

    const masterThreads = await request.get(
      `${apiBaseUrl}/leagues/${leagueOne.id}/chats`,
      { headers: authHeaders(userA) },
    );
    const masterThread = (await masterThreads.json()).data.find(
      (thread: { thread_type: string }) => thread.thread_type === "league",
    );
    const masterMessages = await request.get(
      `${apiBaseUrl}/leagues/${leagueOne.id}/chats/${masterThread.id}/messages`,
      { headers: authHeaders(userA) },
    );
    const finalizedTrades = (await masterMessages.json()).data.filter(
      (message: { message_type: string; metadata: { trade_id?: number } }) =>
        message.message_type === "trade_finalized" &&
        message.metadata.trade_id === trade.id,
    );
    // An in-week acceptance is deliberately not announced as finalized until
    // the lifecycle worker has committed the roster transfer. A trade that
    // processes synchronously still produces its one completed card here.
    if (acceptedTrade.status === "accepted_pending") {
      expect(finalizedTrades).toHaveLength(0);
    } else {
      expect(finalizedTrades).toHaveLength(1);
      expect(finalizedTrades[0].metadata.processing_status).toBe("processed");
    }

    const acceptedPrivateMessages = await request.get(
      `${apiBaseUrl}/leagues/${leagueOne.id}/chats/${privateThread.id}/messages`,
      { headers: authHeaders(userA) },
    );
    expect(acceptedPrivateMessages.status()).toBe(200);
    const acceptedPrivateCards = (
      await acceptedPrivateMessages.json()
    ).data.filter(
      (message: {
        metadata: {
          card_type?: string;
          trade_id?: number;
          trade_status?: string;
        };
      }) =>
        message.metadata.card_type === "private_trade_offer" &&
        message.metadata.trade_id === trade.id &&
        message.metadata.trade_status === "accepted",
    );
    expect(acceptedPrivateCards).toHaveLength(1);
    const averyRosterAfterAcceptance = await rosterPlayerIds(
      request,
      userA,
      averyTeam!.id,
    );
    const blakeRosterAfterAcceptance = await rosterPlayerIds(
      request,
      userB,
      blakeTeam!.id,
    );
    if (acceptedTrade.status === "accepted_pending") {
      // During an active game week the accepted offer is intentionally locked
      // for the lifecycle worker. No roster can move before its scheduled,
      // atomic post-window transfer.
      expect(averyRosterAfterAcceptance).toContain(quarterback.id);
      expect(averyRosterAfterAcceptance).not.toContain(runningBack.id);
      expect(blakeRosterAfterAcceptance).toContain(runningBack.id);
      expect(blakeRosterAfterAcceptance).not.toContain(quarterback.id);
    } else {
      expect(averyRosterAfterAcceptance).toContain(runningBack.id);
      expect(blakeRosterAfterAcceptance).toContain(quarterback.id);
    }

    let finalTradeStatus = acceptedTrade.status;
    if (acceptedTrade.status === "accepted_pending") {
      expect(acceptedTrade.process_after).toBeTruthy();
      const ciAdmin = await login(
        request,
        ciAdminFixture.email,
        ciAdminFixture.password,
      );
      const processingUrl = `${apiBaseUrl}/admin/trades/process-due?as_of=${encodeURIComponent(acceptedTrade.process_after)}`;
      const firstProcessing = await request.post(processingUrl, {
        headers: authHeaders(ciAdmin),
      });
      expect(firstProcessing.status()).toBe(200);
      expect(await firstProcessing.json()).toEqual({ processed: 1, failed: 0 });
      const replayProcessing = await request.post(processingUrl, {
        headers: authHeaders(ciAdmin),
      });
      expect(replayProcessing.status()).toBe(200);
      expect(await replayProcessing.json()).toEqual({
        processed: 0,
        failed: 0,
      });

      const processedTradeResponse = await request.get(
        `${apiBaseUrl}/leagues/${leagueOne.id}/trades/${trade.id}`,
        {
          headers: authHeaders(userA),
        },
      );
      expect(processedTradeResponse.status()).toBe(200);
      const processedTrade = await processedTradeResponse.json();
      expect(processedTrade.status).toBe("processed");
      finalTradeStatus = processedTrade.status;
    }

    const averyFinalRoster = await rosterPlayerIds(
      request,
      userA,
      averyTeam!.id,
    );
    const blakeFinalRoster = await rosterPlayerIds(
      request,
      userB,
      blakeTeam!.id,
    );
    expect(new Set(averyFinalRoster).size).toBe(averyFinalRoster.length);
    expect(new Set(blakeFinalRoster).size).toBe(blakeFinalRoster.length);
    expect(averyFinalRoster).toEqual(
      expect.arrayContaining([backupQuarterback.id, runningBack.id]),
    );
    expect(blakeFinalRoster).toEqual(
      expect.arrayContaining([quarterback.id, backupRunningBack.id]),
    );
    expect(averyFinalRoster).not.toContain(quarterback.id);
    expect(blakeFinalRoster).not.toContain(runningBack.id);
    expect(averyFinalRoster).toHaveLength(2);
    expect(blakeFinalRoster).toHaveLength(2);
    expectRosterCapacityLegal(
      await rosterEntries(request, userA, averyTeam!.id),
    );
    expectRosterCapacityLegal(
      await rosterEntries(request, userB, blakeTeam!.id),
    );

    const postProcessingMasterMessages = await request.get(
      `${apiBaseUrl}/leagues/${leagueOne.id}/chats/${masterThread.id}/messages`,
      { headers: authHeaders(userA) },
    );
    expect(postProcessingMasterMessages.status()).toBe(200);
    const postProcessingTradeCards = (
      await postProcessingMasterMessages.json()
    ).data.filter(
      (message: { message_type: string; metadata: { trade_id?: number } }) =>
        message.message_type === "trade_finalized" &&
        message.metadata.trade_id === trade.id,
    );
    expect(postProcessingTradeCards).toHaveLength(1);
    expect(postProcessingTradeCards[0].metadata.processing_status).toBe(
      "processed",
    );
    expect(finalTradeStatus).toBe("processed");

    await pageB.reload();
    await pageB.getByRole("button", { name: /Avery/i }).last().click();
    await expect(pageB.getByText("Trade accepted").last()).toBeVisible();

    await pageB.getByRole("button", { name: "# General" }).click();
    await expect(pageB.getByText("Trade Finalized").last()).toBeVisible();
    await expect(pageB.getByText(quarterback.name)).toBeVisible();
    await expect(pageB.getByText(runningBack.name)).toBeVisible();
    await expect(pageB.getByText("Roster transfer complete")).toBeVisible();

    const leagueTwo = await createLeague(
      request,
      userA,
      unique("Chat League Two"),
    );
    await joinLeague(request, userB, leagueTwo.id);
    const leagueTwoThreads = await request.get(
      `${apiBaseUrl}/leagues/${leagueTwo.id}/chats`,
      { headers: authHeaders(userB) },
    );
    expect(leagueTwoThreads.status()).toBe(200);
    const leagueTwoMasterId = (await leagueTwoThreads.json()).data.find(
      (thread: { thread_type: string }) => thread.thread_type === "league",
    ).id;
    const leagueTwoMessages = await request.get(
      `${apiBaseUrl}/leagues/${leagueTwo.id}/chats/${leagueTwoMasterId}/messages`,
      { headers: authHeaders(userB) },
    );
    expect((await leagueTwoMessages.json()).data).toEqual([]);

    await contextA.close();
    await contextB.close();
  });
});
