import { expect, test, type Page } from "@playwright/test";
const context = {
  season: 2026,
  period: "week",
  week: 7,
  through_week: 7,
  available_weeks: [6, 7],
  league_id: null,
  scoring_label: "Standard scoring",
  verified_players: 5,
  pending_players: 1,
  updated_at: "2026-10-19T12:00:00Z",
};
const players = ["QB", "RB", "WR", "TE", "K"].map((position, i) => ({
  id: i + 1,
  name: `Verified ${position}`,
  position,
  school: "Texas",
  image_url: null,
  fantasy_points: i === 4 ? 0 : 30 - i,
  position_rank: 1,
  games: 1,
  missing_games: 0,
  status: "final",
  stats: { rush_yards: 100, receptions: 3, rec_yards: 50, xp_made: 0 },
  updated_at: context.updated_at,
  on_my_roster: i === 1,
}));
async function shell(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      "cfb_user",
      JSON.stringify({
        id: 999993,
        firstName: "Rank QA",
        email: "rank@example.invalid",
        isAdmin: false,
      }),
    );
    localStorage.setItem("cfb_access_token", "synthetic-ranking-session");
    localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    localStorage.setItem("cfb_completed_guide_999993", "true");
  });
  let failure = false;
  let latestWeek = 7;
  let noLeagues = false;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace(/^\/api/, "");
    let body: unknown = { data: [], total: 0 };
    if (path === "/auth/me")
      body = {
        id: 999993,
        first_name: "Rank QA",
        email: "rank@example.invalid",
      };
    else if (path === "/health/runtime")
      body = {
        git_sha: "rank-qa",
        web_git_sha: "rank-qa",
        worker_git_sha: "rank-qa",
        api_process_instance_uuid: "rank-qa",
        environment: "development",
        runtime_mode: "development",
        readiness_status: "ready",
        scoring_mode: "standard",
        sportsdata_enabled: false,
        ios_app_review_enabled: false,
      };
    else if (path === "/release-notes/1.03/claim")
      body = {
        account_id: 999993,
        release_key: "1.03",
        authorization: "already_seen",
        claimed_at: "2026-10-19T00:00:00Z",
      };
    else if (path === "/leagues")
      body = {
        data: noLeagues ? [] : [
          {
            id: 101,
            name: "Custom scoring league",
            season_year: 2026,
            team_count: 2,
            max_teams: 12,
            scoring_type: "custom",
            status: "active",
            updated_at: "2026-10-19T00:00:00Z",
          },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      };
    else if (path === "/weekly-challenges/current")
      body = {
        id: 88,
        season: 2026,
        week: 8,
        state: "Open",
        next_rollover_at: "2026-10-28T12:00:00Z",
        server_now: "2026-10-20T12:00:00Z",
        challenges: [
          {
            id: 17,
            kind: "lock",
            name: "Lock of the Week",
            state: "Open",
            entry: null,
            lock_at: "2026-10-24T15:55:00Z",
            server_now: "2026-10-20T12:00:00Z",
          },
        ],
      };
    else if (path === "/player-rankings/leaders")
      body = {
        ...context,
        period: url.searchParams.get("period") ?? "week",
        week: url.searchParams.get("period") === "season" ? null : latestWeek,
        through_week: latestWeek,
        available_weeks: Array.from({length:latestWeek},(_,i)=>i+1),
        data: players.map((p) => ({ position: p.position, player: p })),
      };
    else if (path === "/player-rankings") {
      if (failure) {
        await route.fulfill({
          status: 503,
          json: { detail: "Synthetic provider outage" },
        });
        return;
      }
      const mine = url.searchParams.get("mine") === "true",
        pos = url.searchParams.get("position");
      const rows = players
        .filter(
          (p) => (!pos || p.position === pos) && (!mine || p.on_my_roster),
        )
        .map((p) => ({
          ...p,
          ...(mine
            ? { position_rank: 13, fantasy_points: 18, on_my_roster: true }
            : {}),
        }));
      body = {
        ...context,
        period: url.searchParams.get("period") ?? "week",
        week:
          url.searchParams.get("period") === "season"
            ? null
            : Number(url.searchParams.get("week")) || 7,
        scoring_label: mine
          ? "Custom scoring league scoring"
          : "Standard scoring",
        data: rows,
        total: rows.length,
        limit: 50,
        offset: 0,
      };
    } else if (path.includes("unread")) body = { total_unread: 0, data: [] };
    else if (path.includes("/workspace"))
      body = { teams: [], roster: [], draft: null };
    else if (path === "/product/home-actions")
      body = { data: [], checked_at: context.updated_at };
    await route.fulfill({ json: body });
  });
  return {
    rollover: () => { latestWeek = 8; },
    withoutLeagues: () => { noLeagues = true; },
    fail: (v: boolean) => {
      failure = v;
    },
  };
}
for (const width of [390, 1280])
  test(`Home leaders, table and league-specific ranks ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await shell(page);
    await page.goto("/");
    const leaders = page.getByRole("region", { name: "Positional leaders" });
    await expect(leaders).toContainText("Verified QB");
    await expect(leaders).toContainText("0.0");
    const challenges = page.getByLabel("Weekly Challenges", { exact: true });
    expect((await challenges.boundingBox())!.y).toBeLessThan(
      (await leaders.boundingBox())!.y,
    );
    await expect(
      page.getByRole("link", { name: "Make your first pick", exact: true }),
    ).toHaveAttribute("href", "/weekly-challenges/17");
    await leaders.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: info.outputPath(`home-leaders-${width}.png`),
      animations: "disabled",
    });
    await leaders.getByRole("link", { name: /View RB rankings/ }).click();
    await expect(page.getByRole("table")).toContainText("Verified RB");
    await expect(page.getByRole("table")).not.toContainText("Verified QB");
    await page
      .getByRole("button", { name: "My players by league", exact: true })
      .click();
    await expect(page.getByRole("table")).toContainText("RB 13");
    await expect(page.getByRole("table")).toContainText("18.0");
    await expect(
      page.getByRole("heading", { name: "Player rankings", exact: true }),
    ).toBeVisible();
    await page.getByLabel("Rankings period").selectOption("season");
    await expect(page).not.toHaveURL(/week=/);
    await expect(page.getByRole("table")).toContainText("RB 13");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`league-ranks-${width}.png`),
      animations: "disabled",
    });
  });
test("rankings errors stay errors and offer a working retry", async ({
  page,
}) => {
  const control = await shell(page);
  control.fail(true);
  await page.goto("/player-rankings");
  await expect(
    page.getByRole("alert").filter({ hasText: "Rankings could not load" }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole("table")).toHaveCount(0);
  control.fail(false);
  await page.getByRole("button", { name: "Retry rankings" }).click();
  await expect(page.getByRole("table")).toContainText("Verified QB");
});


test("Home picks up the new completed week while it stays open",async({page})=>{
  await page.clock.install();
  const control=await shell(page);await page.goto("/");
  const leaders=page.getByRole("region",{name:"Positional leaders"});
  await expect(leaders).toContainText("Week 7");
  control.rollover();await page.clock.runFor(180_100);
  await expect(leaders).toContainText("Week 8");
  await expect(leaders.getByRole("link",{name:"All player rankings"})).toHaveAttribute("href",/week=8/);
});

test("a new account without a league can enter its first challenge directly",async({page})=>{
  const control=await shell(page);control.withoutLeagues();await page.goto("/");
  await expect(page.getByText("No leagues joined yet")).toBeVisible();
  await expect(page.getByRole("link",{name:"Make your first pick",exact:true})).toHaveAttribute("href","/weekly-challenges/17");
  await expect(page.getByRole("region",{name:"Positional leaders"})).toContainText("Verified QB");
});
