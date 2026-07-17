import { chromium } from "@playwright/test";

const apiBase = process.env.DRAFT_VERIFY_API_BASE_URL ?? "http://127.0.0.1:8000";
const webBase = process.env.DRAFT_VERIFY_WEB_BASE_URL ?? "http://127.0.0.1:8080";
const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const password = "LiveDraftPass123!";

const requestJson = async (path, { token, method = "GET", body } = {}) => {
  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(`${method} ${path} failed (${response.status}): ${JSON.stringify(payload)}`);
  }
  return payload;
};

const signup = async (firstName) =>
  requestJson("/auth/signup", {
    method: "POST",
    body: {
      first_name: firstName,
      email: `${firstName.toLowerCase()}-${suffix}@example.com`,
      password,
    },
  });

const createLeague = async (token) =>
  requestJson("/leagues", {
    token,
    method: "POST",
    body: {
      basics: {
        name: `Live Draft Browser ${suffix}`,
        season_year: 2026,
        max_teams: 2,
        is_private: true,
        description: "Automated live-draft verification",
        icon_url: null,
      },
      settings: {
        scoring_json: { ppr: 1 },
        roster_slots_json: { QB: 1 },
        playoff_teams: 2,
        waiver_type: "faab",
        trade_review_type: "commissioner",
        superflex_enabled: false,
        kicker_enabled: false,
        defense_enabled: false,
      },
      draft: {
        draft_datetime_utc: new Date(Date.now() - 1_000).toISOString(),
        timezone: "America/New_York",
        draft_type: "snake",
        pick_timer_seconds: 30,
      },
    },
  });

const browserSession = async (browser, auth) => {
  const context = await browser.newContext();
  await context.addInitScript(
    ({ accessToken, accessTokenExpiresAt, user }) => {
      localStorage.setItem("cfb_access_token", accessToken);
      localStorage.setItem("cfb_access_token_expires_at", accessTokenExpiresAt);
      localStorage.setItem(
        "cfb_user",
        JSON.stringify({
          id: user.id,
          firstName: user.first_name,
          email: user.email,
          isAdmin: user.is_admin,
        })
      );
      localStorage.setItem(`cfb_completed_guide_${user.id}`, "true");
    },
    {
      accessToken: auth.access_token,
      accessTokenExpiresAt: auth.access_token_expires_at,
      user: auth.user,
    }
  );
  return { context, page: await context.newPage() };
};

const waitForOnClock = (page, teamName) =>
  page.waitForFunction(
    (expectedTeamName) =>
      document.body.innerText.toUpperCase().includes("ON CLOCK") && document.body.innerText.includes(expectedTeamName),
    teamName,
    { timeout: 85_000 }
  );

const draftFirstAvailablePlayer = async (page) => {
  const row = page.getByTestId("draft-player-row").first();
  await row.getByRole("button", { name: "Draft", exact: true }).click();
};

const main = async () => {
  const commissioner = await signup("Commissioner");
  const manager = await signup("Manager");
  const created = await createLeague(commissioner.access_token);
  const leagueId = created.league.id;
  await requestJson(`/leagues/${leagueId}/join`, { token: manager.access_token, method: "POST" });

  const browser = await chromium.launch({ headless: true });
  const commissionerSession = await browserSession(browser, commissioner);
  const managerSession = await browserSession(browser, manager);
  try {
    await Promise.all([
      commissionerSession.page.goto(`${webBase}/league/${leagueId}/draft`, { waitUntil: "networkidle" }),
      managerSession.page.goto(`${webBase}/league/${leagueId}/draft`, { waitUntil: "networkidle" }),
    ]);

    await requestJson(`/leagues/${leagueId}/draft/start`, {
      token: commissioner.access_token,
      method: "POST",
      body: {},
    });
    await Promise.all([
      commissionerSession.page.getByText("Draft Starts In", { exact: true }).waitFor(),
      managerSession.page.getByText("Draft Starts In", { exact: true }).waitFor(),
    ]);

    const initialRoom = await requestJson(`/leagues/${leagueId}/draft-room`, { token: commissioner.access_token });
    const firstTeam = initialRoom.teams[0];
    const secondTeam = initialRoom.teams[1];
    await waitForOnClock(commissionerSession.page, firstTeam.name);
    await draftFirstAvailablePlayer(commissionerSession.page);
    await waitForOnClock(managerSession.page, secondTeam.name);
    await draftFirstAvailablePlayer(managerSession.page);

    await managerSession.page.getByText("Draft Complete", { exact: true }).waitFor({ timeout: 20_000 });
    const completedRoom = await requestJson(`/leagues/${leagueId}/draft-room`, { token: commissioner.access_token });
    if (completedRoom.status !== "completed" || completedRoom.picks.length !== 2) {
      throw new Error(`Draft did not complete correctly: ${JSON.stringify(completedRoom)}`);
    }
    const rosters = await Promise.all(
      completedRoom.teams.map((team) => requestJson(`/teams/${team.id}/roster`, { token: team.id === firstTeam.id ? commissioner.access_token : manager.access_token }))
    );
    if (rosters.some((roster) => roster.total !== 1)) {
      throw new Error(`Final rosters were not persisted: ${JSON.stringify(rosters)}`);
    }
    console.log(JSON.stringify({ leagueId, status: completedRoom.status, picks: completedRoom.picks.length, rosterTotals: rosters.map((roster) => roster.total) }));
  } finally {
    await commissionerSession.context.close();
    await managerSession.context.close();
    await browser.close();
  }
};

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
