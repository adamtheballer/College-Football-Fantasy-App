import { expect, test, type Page } from "@playwright/test";

const realStackEnabled = process.env.REAL_STACK_E2E === "1";
const password = "RealE2ePass123!";
const betaFixtures = {
  commissioner: { email: "ci-beta-commissioner@example.test" },
  manager: { email: "ci-beta-manager@example.test" },
} as const;

type ApiResult<T> = {
  status: number;
  body: T;
};

async function realApi<T>(page: Page, path: string, body?: unknown): Promise<ApiResult<T>> {
  return page.evaluate(
    async ({ requestBody, requestPath }) => {
      const token = window.localStorage.getItem("cfb_access_token");
      const response = await fetch(`/api${requestPath}`, {
        method: requestBody === undefined ? "GET" : "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(requestBody === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
      });
      const responseBody = await response.json().catch(() => null);
      return { status: response.status, body: responseBody };
    },
    { requestPath: path, requestBody: body }
  ) as Promise<ApiResult<T>>;
}

async function signUp(page: Page, firstName: string, fixture: { email: string }) {
  await page.goto("/signup");
  await expect(page).toHaveURL(/\/login\?flow=signup$/);
  await expect(page.locator("#signup-email")).not.toHaveAttribute("readonly", "");
  await page.locator("#signup-email").fill(fixture.email);
  await page.locator("#signup-name").fill(firstName);
  await page.locator("#signup-password").fill(password);
  const [signupResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes("/api/auth/signup") && response.request().method() === "POST"),
    page.getByRole("button", { name: /Create (beta )?account/i }).click(),
  ]);
  expect(signupResponse.status()).toBe(201);
  await expect(page.getByRole("dialog", { name: /Account created/i })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /Continue to dashboard/i }).click();
  await page.waitForURL("**/");

  const endGuide = page.getByRole("button", { name: /End Guide/i });
  if (await endGuide.isVisible().catch(() => false)) {
    await endGuide.click();
  }
}

test.describe("real two-manager draft lifecycle", () => {
  test.skip(!realStackEnabled, "Run through npm run test:e2e:real against the isolated Compose stack.");
  test.setTimeout(220_000);

  test("enforces the standard beta roster and keeps two signed-in managers synchronized through timeout auto-picks", async ({ browser }) => {
    const commissionerContext = await browser.newContext();
    const managerContext = await browser.newContext();
    const commissioner = await commissionerContext.newPage();
    const manager = await managerContext.newPage();

    try {
      await signUp(commissioner, "Commissioner", betaFixtures.commissioner);
      await signUp(manager, "Manager", betaFixtures.manager);

      const createResponse = await realApi<{ league: { id: number }; invite_code: string }>(commissioner, "/leagues", {
        basics: {
          name: "Real lifecycle E2E",
          season_year: 2026,
          max_teams: 2,
          is_private: true,
          description: "Real browser lifecycle coverage",
          icon_url: null,
        },
        settings: {
          scoring_json: { ppr: 1 },
          roster_slots_json: { QB: 1 },
          playoff_teams: 2,
          waiver_type: "faab",
          waiver_period_hours: 24,
          trade_review_type: "none",
          superflex_enabled: false,
          kicker_enabled: false,
          defense_enabled: false,
        },
        draft: {
          draft_datetime_utc: new Date(Date.now() - 60_000).toISOString(),
          timezone: "America/New_York",
          draft_type: "snake",
          pick_timer_seconds: 1,
        },
      });
      expect(createResponse.status).toBe(201);
      const leagueId = createResponse.body.league.id;

      await manager.goto(`/join/${createResponse.body.invite_code}`);
      await expect(manager.getByText(/League Preview/i)).toBeVisible();
      await manager.getByRole("main").getByRole("button", { name: /^Join League$/i }).click();
      await expect(manager).toHaveURL(new RegExp(`/league/${leagueId}$`));

      await commissioner.goto(`/league/${leagueId}/draft`);
      await expect(commissioner.getByRole("button", { name: /^Start Draft$/i })).toBeVisible();
      await manager.goto(`/league/${leagueId}/draft`);
      await expect(manager).not.toHaveURL(/\/login$/);

      await commissioner.bringToFront();
      await commissioner.getByRole("button", { name: /^Start Draft$/i }).click();
      await expect.poll(async () => {
        const room = await realApi<{ status: string; current_pick: number; current_pick_deadline: string | null }>(commissioner, `/leagues/${leagueId}/draft-room`);
        return room.body;
      }).toMatchObject({ status: "on_clock", current_pick: 1 });

      await expect(commissioner.getByText("Pick Timer")).toBeVisible({ timeout: 15_000 });
      await expect(manager.getByText("Pick Timer")).toBeVisible({ timeout: 15_000 });

      await expect.poll(async () => {
        const room = await realApi<{ picks: Array<{ auto_pick: boolean }> }>(commissioner, `/leagues/${leagueId}/draft-room`);
        return room.body.picks.filter((pick) => pick.auto_pick).length;
      }, { timeout: 90_000 }).toBeGreaterThanOrEqual(2);

      const room = await realApi<{
        status: string;
        roster_slots: Record<string, number>;
        picks: Array<{ player_id: number; auto_pick: boolean }>;
      }>(commissioner, `/leagues/${leagueId}/draft-room`);
      const managerRoom = await realApi<{
        picks: Array<{ player_id: number; auto_pick: boolean }>;
      }>(manager, `/leagues/${leagueId}/draft-room`);
      expect(room.status).toBe(200);
      expect(room.body.roster_slots).toEqual({
        QB: 1,
        RB: 2,
        WR: 2,
        TE: 1,
        FLEX: 1,
        SUPERFLEX: 0,
        K: 1,
        BENCH: 5,
        IR: 1,
      });
      expect(room.body.picks).toHaveLength(2);
      expect(managerRoom.body.picks.map((pick) => pick.player_id)).toEqual(room.body.picks.map((pick) => pick.player_id));
      expect(new Set(room.body.picks.map((pick) => pick.player_id)).size).toBe(room.body.picks.length);
      expect(room.body.picks.every((pick) => pick.auto_pick)).toBe(true);
    } finally {
      await commissionerContext.close();
      await managerContext.close();
    }
  });
});
