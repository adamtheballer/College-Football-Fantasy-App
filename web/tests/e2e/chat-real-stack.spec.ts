import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const enabled = process.env.E2E_REAL_STACK === "1";
const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";

type AuthSession = {
  access_token: string;
  access_token_expires_at: string;
  user: { id: number; first_name: string; email: string };
};

type LeagueTeam = { id: number; owner_user_id: number | null };
type Player = { id: number; name: string; position: string };

const authHeaders = (session: AuthSession) => ({ Authorization: `Bearer ${session.access_token}` });
const unique = (label: string) => `${label}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

async function signup(request: APIRequestContext, firstName: string): Promise<AuthSession> {
  const suffix = unique(firstName.toLowerCase());
  const response = await request.post(`${apiBaseUrl}/auth/signup`, {
    data: { first_name: firstName, email: `${suffix}@example.test`, password: "StrongPass123!" },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

async function createLeague(request: APIRequestContext, session: AuthSession, name: string) {
  const response = await request.post(`${apiBaseUrl}/leagues`, {
    headers: authHeaders(session),
    data: {
      basics: { name, season_year: 2026, max_teams: 2, is_private: true, description: null, icon_url: null },
      settings: { scoring_json: { ppr: 1 }, roster_slots_json: { QB: 1, RB: 1, WR: 1, TE: 1, BENCH: 4, K: 1, IR: 1 }, playoff_teams: 2, waiver_type: "faab", trade_review_type: "none", superflex_enabled: false, kicker_enabled: true, defense_enabled: false },
      draft: { draft_datetime_utc: "2026-08-19T18:00:00Z", timezone: "America/New_York", draft_type: "snake", pick_timer_seconds: 90 },
    },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).league as { id: number; name: string };
}

async function joinLeague(request: APIRequestContext, session: AuthSession, leagueId: number) {
  const response = await request.post(`${apiBaseUrl}/leagues/${leagueId}/join`, { headers: authHeaders(session) });
  expect(response.status()).toBe(200);
}

async function getLeagueTeams(request: APIRequestContext, session: AuthSession, leagueId: number): Promise<LeagueTeam[]> {
  const response = await request.get(`${apiBaseUrl}/leagues/${leagueId}/teams`, { headers: authHeaders(session) });
  expect(response.status()).toBe(200);
  return (await response.json()).data;
}

async function getDraftablePlayers(request: APIRequestContext): Promise<{ quarterback: Player; runningBack: Player }> {
  const response = await request.get(`${apiBaseUrl}/players?limit=100&sort=rank`);
  expect(response.status()).toBe(200);
  const players = (await response.json()).data as Player[];
  const quarterback = players.find((player) => player.position === "QB");
  const runningBack = players.find((player) => player.position === "RB");
  expect(quarterback).toBeTruthy();
  expect(runningBack).toBeTruthy();
  return { quarterback: quarterback!, runningBack: runningBack! };
}

async function addRosterPlayer(request: APIRequestContext, session: AuthSession, teamId: number, player: Player, slot: string) {
  const response = await request.post(`${apiBaseUrl}/teams/${teamId}/roster`, {
    headers: authHeaders(session),
    data: { player_id: player.id, slot, status: "active" },
  });
  expect(response.status()).toBe(201);
}

async function primeBrowserSession(page: Page, session: AuthSession) {
  await page.addInitScript((payload) => {
    window.localStorage.setItem("cfb_access_token", payload.accessToken);
    window.localStorage.setItem("cfb_access_token_expires_at", payload.expiresAt);
    window.localStorage.setItem("cfb_user", JSON.stringify({ id: payload.user.id, firstName: payload.user.first_name, email: payload.user.email, isAdmin: false }));
    window.localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
  }, { accessToken: session.access_token, expiresAt: session.access_token_expires_at, user: session.user });
}

test.describe("real FastAPI/PostgreSQL league chat", () => {
  test.skip(!enabled, "Set E2E_REAL_STACK=1 after starting FastAPI and PostgreSQL; this suite never mocks chat endpoints.");

  test("two league members exchange messages and see a binding trade card without cross-league leakage", async ({ browser, request }) => {
    const userA = await signup(request, "Avery");
    const userB = await signup(request, "Blake");
    const leagueOne = await createLeague(request, userA, unique("Chat League One"));
    await joinLeague(request, userB, leagueOne.id);

    const contextA = await browser.newContext();
    const pageA = await contextA.newPage();
    await primeBrowserSession(pageA, userA);
    await pageA.goto("/chats");
    await expect(pageA.getByText("# General").first()).toBeVisible();
    await pageA.getByPlaceholder("Message your league…").fill("Good luck this week");
    await Promise.all([
      pageA.waitForResponse((response) => response.url().includes(`/leagues/${leagueOne.id}/chats/`) && response.request().method() === "POST"),
      pageA.getByRole("button", { name: /^send$/i }).click(),
    ]);

    const beforeOpen = await request.get(`${apiBaseUrl}/chats/unread-summary`, { headers: authHeaders(userB) });
    expect(beforeOpen.status()).toBe(200);
    expect((await beforeOpen.json()).total_unread).toBe(1);

    const contextB = await browser.newContext();
    const pageB = await contextB.newPage();
    await primeBrowserSession(pageB, userB);
    await pageB.goto("/chats");
    await expect(pageB.getByText("Good luck this week").last()).toBeVisible();
    await expect.poll(async () => {
      const response = await request.get(`${apiBaseUrl}/chats/unread-summary`, { headers: authHeaders(userB) });
      return (await response.json()).total_unread;
    }).toBe(0);

    await pageA.getByRole("button", { name: /new message/i }).click();
    await pageA.getByRole("button", { name: /Blake/i }).last().click();
    const directThreadRowA = pageA.getByRole("button", { name: /Blake/i }).last();
    await expect(directThreadRowA).toBeVisible();
    await directThreadRowA.click();
    await expect(pageA.getByRole("heading", { name: /Direct message.*Blake/i })).toBeVisible();
    await pageA.getByPlaceholder("Message your league…").fill("Private trade thought");
    await Promise.all([
      pageA.waitForResponse((response) => response.url().includes(`/leagues/${leagueOne.id}/chats/`) && response.request().method() === "POST"),
      pageA.getByRole("button", { name: /^send$/i }).click(),
    ]);

    const directUnread = await request.get(`${apiBaseUrl}/chats/unread-summary`, { headers: authHeaders(userB) });
    expect((await directUnread.json()).total_unread).toBe(1);
    await pageB.getByRole("button", { name: /Avery/i }).last().click();
    await expect(pageB.getByText("Private trade thought").last()).toBeVisible();

    const teams = await getLeagueTeams(request, userA, leagueOne.id);
    const averyTeam = teams.find((team) => team.owner_user_id === userA.user.id);
    const blakeTeam = teams.find((team) => team.owner_user_id === userB.user.id);
    expect(averyTeam).toBeTruthy();
    expect(blakeTeam).toBeTruthy();
    const { quarterback, runningBack } = await getDraftablePlayers(request);
    await addRosterPlayer(request, userA, averyTeam!.id, quarterback, "QB");
    await addRosterPlayer(request, userB, blakeTeam!.id, runningBack, "RB");

    const tradeCreate = await request.post(`${apiBaseUrl}/leagues/${leagueOne.id}/trades`, {
      headers: authHeaders(userA),
      data: {
        proposing_team_id: averyTeam!.id,
        receiving_team_id: blakeTeam!.id,
        give_items: [{ team_id: averyTeam!.id, player_id: quarterback.id }],
        receive_items: [{ team_id: blakeTeam!.id, player_id: runningBack.id }],
        message: "Real-stack chat trade",
      },
    });
    expect(tradeCreate.status()).toBe(201);
    const trade = await tradeCreate.json();
    const tradeAccept = await request.post(`${apiBaseUrl}/leagues/${leagueOne.id}/trades/${trade.id}/accept`, {
      headers: authHeaders(userB),
      data: {},
    });
    expect(tradeAccept.status()).toBe(200);
    const acceptedTrade = await tradeAccept.json();

    const masterThreads = await request.get(`${apiBaseUrl}/leagues/${leagueOne.id}/chats`, { headers: authHeaders(userA) });
    const masterThread = (await masterThreads.json()).data.find((thread: { thread_type: string }) => thread.thread_type === "league");
    const masterMessages = await request.get(`${apiBaseUrl}/leagues/${leagueOne.id}/chats/${masterThread.id}/messages`, { headers: authHeaders(userA) });
    const finalizedTrades = (await masterMessages.json()).data.filter((message: { message_type: string; metadata: { trade_id?: number } }) => (
      message.message_type === "trade_finalized" && message.metadata.trade_id === trade.id
    ));
    expect(finalizedTrades).toHaveLength(1);
    expect(finalizedTrades[0].metadata.processing_status).toBe(
      acceptedTrade.status === "accepted_pending" ? "pending_transfer" : "processed",
    );

    await pageB.getByRole("button", { name: "# General" }).click();
    await expect(pageB.getByText("Trade Finalized").last()).toBeVisible();
    await expect(pageB.getByText(quarterback.name)).toBeVisible();
    await expect(pageB.getByText(runningBack.name)).toBeVisible();
    await expect(pageB.getByText(acceptedTrade.status === "accepted_pending" ? /Roster transfer pending/i : "Roster transfer complete")).toBeVisible();

    const leagueTwo = await createLeague(request, userA, unique("Chat League Two"));
    await joinLeague(request, userB, leagueTwo.id);
    const leagueTwoThreads = await request.get(`${apiBaseUrl}/leagues/${leagueTwo.id}/chats`, { headers: authHeaders(userB) });
    expect(leagueTwoThreads.status()).toBe(200);
    const leagueTwoMasterId = (await leagueTwoThreads.json()).data.find((thread: { thread_type: string }) => thread.thread_type === "league").id;
    const leagueTwoMessages = await request.get(`${apiBaseUrl}/leagues/${leagueTwo.id}/chats/${leagueTwoMasterId}/messages`, { headers: authHeaders(userB) });
    expect((await leagueTwoMessages.json()).data).toEqual([]);

    await contextA.close();
    await contextB.close();
  });
});
