import { expect, test } from "@playwright/test";

const mockPlayers = [
  { id: 1, name: "Jeremiah Smith", position: "WR", school: "Ohio State", board_rank: 1, sheet_projected_season_points: 315.5 },
  { id: 2, name: "Arch Manning", position: "QB", school: "Texas", board_rank: 2, sheet_projected_season_points: 304.2 },
  { id: 3, name: "Kewan Lacy", position: "RB", school: "Ole Miss", board_rank: 3, sheet_projected_season_points: 291.2 },
  { id: 4, name: "Eli Stowers", position: "TE", school: "Vanderbilt", board_rank: 4, sheet_projected_season_points: 244.7 },
];

test("centers the active mock-draft manager from pick three onward", async ({ page }) => {
  const now = Date.now();
  await page.addInitScript(({ timestamp }) => {
    localStorage.setItem("cfb_user", JSON.stringify({ id: 42, firstName: "Adam", email: "adam@example.com" }));
    localStorage.setItem("cfb_access_token", "mock-access-token");
    localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    localStorage.setItem("cfb_single_player_mock_draft", JSON.stringify({
      id: "centered-current-pick",
      settings: { leagueSize: 4, rounds: 13, pickTimerSeconds: 60 },
      status: "live",
      createdAt: timestamp,
      intermissionEndsAt: timestamp,
      currentPick: 3,
      pickStartedAt: timestamp,
      pickExpiresAt: timestamp + 60_000,
      userTeamId: 3,
      teams: [
        { id: 1, name: "Bot Team 1", managerType: "bot" },
        { id: 2, name: "Bot Team 2", managerType: "bot" },
        { id: 3, name: "Your Team", managerType: "user" },
        { id: 4, name: "Bot Team 4", managerType: "bot" },
      ],
      picks: [
        { overallPick: 1, round: 1, roundPick: 1, teamId: 1, teamName: "Bot Team 1", playerId: 1, playerName: "Jeremiah Smith", position: "WR", school: "Ohio State", projectedPoints: 315.5, draftRank: 1, masterDraftRank: 1, assignedSlot: "WR 1", pickedBy: "bot", madeAt: timestamp },
        { overallPick: 2, round: 1, roundPick: 2, teamId: 2, teamName: "Bot Team 2", playerId: 2, playerName: "Arch Manning", position: "QB", school: "Texas", projectedPoints: 304.2, draftRank: 2, masterDraftRank: 2, assignedSlot: "QB", pickedBy: "bot", madeAt: timestamp },
      ],
      queuedPlayerIds: [],
    }));
  }, { timestamp: now });
  await page.route("**/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: 42, first_name: "Adam", email: "adam@example.com" }) });
  });
  await page.route("**/notifications/preferences**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });
  await page.route("**/players**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: mockPlayers, total: mockPlayers.length, limit: 200, offset: 0 }),
    });
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/draft/mock/single-player");

  const rail = page.getByTestId("mobile-draft-order-scroll");
  const activeCard = page.getByTestId("mobile-draft-order-card-3");
  await expect(activeCard).toHaveAttribute("aria-current", "step");
  await expect(page.getByLabel("Current pick scope")).toBeVisible();

  await expect.poll(async () => rail.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await expect.poll(async () => rail.evaluate((element) => {
    const current = element.querySelector('[data-testid="mobile-draft-order-card-3"]') as HTMLElement | null;
    if (!current) return Number.POSITIVE_INFINITY;
    const railBox = element.getBoundingClientRect();
    const cardBox = current.getBoundingClientRect();
    return Math.abs((cardBox.left + cardBox.width / 2) - (railBox.left + railBox.width / 2));
  })).toBeLessThan(12);
});
