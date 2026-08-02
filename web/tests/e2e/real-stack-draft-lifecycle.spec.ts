import { expect, test, type Page } from "@playwright/test";

const realStackEnabled = process.env.REAL_STACK_E2E === "1";
const password = "RealE2ePass123!";
const betaFixtures = {
  commissioner: { email: "ci-beta-commissioner@example.test", code: "EARLY-CI1235" },
  manager: { email: "ci-beta-manager@example.test", code: "EARLY-CI1236" },
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

async function signUp(page: Page, firstName: string, fixture: { email: string; code: string }) {
  await page.goto("/signup");
  await expect(page).toHaveURL(/\/login\?flow=beta$/);
  await page.locator("#beta-email").fill(fixture.email);
  await page.locator("#beta-code").fill(fixture.code);
  await page.getByRole("button", { name: /Verify and continue/i }).click();
  await expect(page.locator("#signup-email")).toHaveValue(fixture.email);
  await expect(page.locator("#signup-email")).toHaveAttribute("readonly", "");
  await page.locator("#signup-name").fill(firstName);
  await page.locator("#signup-password").fill(password);
  await page.getByRole("button", { name: /Create (beta )?account/i }).click();
  await page.waitForURL("**/");

  const endGuide = page.getByRole("button", { name: /End Guide/i });
  if (await endGuide.isVisible().catch(() => false)) {
    await endGuide.click();
  }
}

test.describe("real two-manager draft lifecycle", () => {
  test.skip(!realStackEnabled, "Run through npm run test:e2e:real against the isolated Compose stack.");
  test.setTimeout(220_000);

  test("keeps two signed-in managers synchronized through countdown and timeout auto-picks", async ({ browser }) => {
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
      await expect(manager).toHaveURL(new RegExp(`/league/${leagueId}/lobby$`));

      await commissioner.goto(`/league/${leagueId}/draft`);
      await expect(commissioner.getByRole("button", { name: /^Start Draft$/i })).toBeVisible();
      await commissioner.getByRole("button", { name: /^Start Draft$/i }).click();
      await expect.poll(async () => {
        const room = await realApi<{ status: string }>(commissioner, `/leagues/${leagueId}/draft-room`);
        return room.body.status;
      }).toBe("pre_draft");
      await expect(commissioner.getByText("Starting Soon")).toBeVisible();

      await manager.goto(`/league/${leagueId}/draft`);
      await expect(manager.getByText("Starting Soon")).toBeVisible();
      await expect(manager).not.toHaveURL(/\/login$/);

      await expect(commissioner.getByText("Pick Timer")).toBeVisible({ timeout: 100_000 });
      await expect(commissioner.getByText("Draft Complete")).toBeVisible({ timeout: 90_000 });
      await expect(manager.getByText("Draft Complete")).toBeVisible({ timeout: 20_000 });

      await expect.poll(async () => {
        const room = await realApi<{ status: string }>(commissioner, `/leagues/${leagueId}/draft-room`);
        return room.body.status;
      }, { timeout: 20_000 }).toBe("completed");

      const room = await realApi<{
        status: string;
        picks: Array<{ player_id: number; auto_pick: boolean }>;
      }>(commissioner, `/leagues/${leagueId}/draft-room`);
      expect(room.status).toBe(200);
      expect(room.body.status).toBe("completed");
      expect(room.body.picks).toHaveLength(2);
      expect(new Set(room.body.picks.map((pick) => pick.player_id)).size).toBe(2);
      expect(room.body.picks.every((pick) => pick.auto_pick)).toBe(true);
    } finally {
      await commissionerContext.close();
      await managerContext.close();
    }
  });
});
