import { expect, test, type Page } from "@playwright/test";

const realStackEnabled = process.env.REAL_STACK_E2E === "1";
const password = "SixManagerE2ePass123!";

const fixtures = [
  { firstName: "Commissioner", email: "ci-beta-six-manager-commissioner@example.test", code: "EARLY-CI1245" },
  { firstName: "Manager One", email: "ci-beta-six-manager-1@example.test", code: "EARLY-CI1239" },
  { firstName: "Manager Two", email: "ci-beta-six-manager-2@example.test", code: "EARLY-CI1240" },
  { firstName: "Manager Three", email: "ci-beta-six-manager-3@example.test", code: "EARLY-CI1241" },
  { firstName: "Manager Four", email: "ci-beta-six-manager-4@example.test", code: "EARLY-CI1242" },
  { firstName: "Manager Five", email: "ci-beta-six-manager-5@example.test", code: "EARLY-CI1243" },
  { firstName: "Manager Six", email: "ci-beta-six-manager-6@example.test", code: "EARLY-CI1244" },
] as const;

type ApiResult<T> = { status: number; body: T };

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
      return {
        status: response.status,
        body: await response.json().catch(() => null),
      };
    },
    { requestPath: path, requestBody: body },
  ) as Promise<ApiResult<T>>;
}

async function signUp(page: Page, fixture: (typeof fixtures)[number]) {
  await page.goto("/signup");
  await expect(page).toHaveURL(/\/login\?flow=signup$/);
  await page.locator("#signup-email").fill(fixture.email);
  await page.locator("#signup-name").fill(fixture.firstName);
  await page.locator("#signup-password").fill(password);
  const [response] = await Promise.all([
    page.waitForResponse((candidate) => candidate.url().includes("/api/auth/signup") && candidate.request().method() === "POST"),
    page.getByRole("button", { name: /Create (beta )?account/i }).click(),
  ]);
  expect(response.status()).toBe(201);
  await page.getByRole("button", { name: /Continue to dashboard/i }).click();
  await page.waitForURL("**/");
  const endGuide = page.getByRole("button", { name: /End Guide/i });
  if (await endGuide.isVisible().catch(() => false)) await endGuide.click();
}

async function joinThroughUi(page: Page, inviteCode: string) {
  await page.goto(`/join/${inviteCode}`);
  await expect(page.getByText(/League Preview/i)).toBeVisible();
  const [response] = await Promise.all([
    page.waitForResponse((candidate) => candidate.url().includes("/join") && candidate.request().method() === "POST"),
    page.getByRole("main").getByRole("button", { name: /^Join League$/i }).click(),
  ]);
  return response.status();
}

test.describe("real six-manager golden-path admission", () => {
  test.skip(!realStackEnabled, "Run only through the disposable real-stack E2E command.");
  test.setTimeout(150_000);

  test("admits exactly one manager to the final seat and retains all six signed-in league members", async ({ browser }) => {
    const contexts = await Promise.all(fixtures.map(() => browser.newContext()));
    const pages = await Promise.all(contexts.map((context) => context.newPage()));

    try {
      for (const [index, page] of pages.entries()) await signUp(page, fixtures[index]!);
      const commissioner = pages[0]!;
      const create = await realApi<{ league: { id: number }; invite_code: string }>(commissioner, "/leagues", {
        basics: {
          name: `Six manager golden path ${Date.now()}`,
          season_year: 2026,
          max_teams: 6,
          is_private: true,
          description: "Disposable alpha CI coverage",
          icon_url: null,
        },
        settings: {
          scoring_json: { ppr: 1 },
          roster_slots_json: { QB: 1 },
          playoff_teams: 4,
          waiver_type: "faab",
          waiver_period_hours: 24,
          trade_review_type: "none",
          superflex_enabled: false,
          kicker_enabled: false,
          defense_enabled: false,
        },
        draft: {
          draft_datetime_utc: new Date(Date.now() + 86_400_000).toISOString(),
          timezone: "America/New_York",
          draft_type: "snake",
          pick_timer_seconds: 60,
        },
      });
      expect(create.status).toBe(201);

      for (const page of pages.slice(1, 5)) {
        expect(await joinThroughUi(page, create.body.invite_code)).toBe(200);
      }

      const finalSeatStatuses = await Promise.all(
        pages.slice(5).map((page) => joinThroughUi(page, create.body.invite_code)),
      );
      expect(finalSeatStatuses.filter((status) => status === 200)).toHaveLength(1);
      expect(finalSeatStatuses.filter((status) => status !== 200)).toHaveLength(1);

      const teams = await realApi<{ data: Array<{ id: number; owner_user_id: number | null }> }>(
        commissioner,
        `/leagues/${create.body.league.id}/teams`,
      );
      expect(teams.status).toBe(200);
      expect(teams.body.data).toHaveLength(6);
      const ownerIds = teams.body.data.map((team) => team.owner_user_id);
      expect(ownerIds.every((ownerId) => ownerId !== null)).toBe(true);
      expect(new Set(ownerIds).size).toBe(6);

      const admittedFinalManager = pages[5 + finalSeatStatuses.findIndex((status) => status === 200)]!;
      await admittedFinalManager.goto(`/league/${create.body.league.id}/lobby`);
      await expect(admittedFinalManager).not.toHaveURL(/\/login$/);
      await admittedFinalManager.reload();
      await expect(admittedFinalManager).not.toHaveURL(/\/login$/);
    } finally {
      await Promise.all(contexts.map((context) => context.close()));
    }
  });
});
