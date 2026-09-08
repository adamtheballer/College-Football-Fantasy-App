import { expect, test } from "@playwright/test";

const contest = {
  id: 8,
  season: 2026,
  week_number: 1,
  title: "Saturday Pick 6",
  contest_position: "QB",
  status: "SCORING",
  lock_at: "2026-09-05T16:00:00Z",
  first_game_player: {
    id: 81,
    player_id: 18,
    player_name: "Featured Player",
    opponent: "Opponent",
    game_time: "2026-09-05T16:00:00Z",
  },
  winning_player_ids: [],
  players: [{
    id: 81,
    player_id: 18,
    canonical_position: "QB",
    player_name: "Featured Player",
    school: "West Georgia",
    opponent: "Opponent",
    game_time: "2026-09-05T16:00:00Z",
    image_url: null,
    projected_points: 21.4,
    live_points: 10.2,
    final_points: null,
    scoring_status: "LIVE",
    sort_order: 1,
  }],
  entry: null,
  sponsor: {
    name: "West Georgia Cornhole",
    logo_url: null,
    offer_text: "Partner offer",
    terms: null,
    reward_unlocked: false,
    code: null,
    url: null,
  },
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("cfb_user", JSON.stringify({ id: 42, firstName: "Adam", email: "adam@example.com" }));
    localStorage.setItem("cfb_access_token", "mock-access-token");
    localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
    localStorage.setItem("cfb_completed_guide_42", "true");
  });

  await page.route("**/auth/me", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: 42, first_name: "Adam", email: "adam@example.com" }) }));
  await page.route("**/notifications/preferences", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) }));
  await page.route("**/notifications/alerts**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [] }) }));
  await page.route("**/chats/unread-summary", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ total_unread: 0 }) }));
  await page.route("**/leagues**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }));
  await page.route("**/saturday-pick-6/current", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(contest) }));
  await page.route("**/saturday-pick-6/rewards", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
});

test("the homepage West Georgia Cornhole event button opens the live Pick 6 player totals", async ({ page }) => {
  await page.goto("/");
  const sponsorButton = page.getByRole("link", { name: "Open Saturday Pick 6 event" });
  await expect(sponsorButton).toBeVisible();
  await sponsorButton.click();

  await expect(page).toHaveURL(/\/saturday-pick-6$/);
  await expect(page.getByRole("heading", { name: "Featured Player" })).toBeVisible();
  await expect(page.getByText("Live points")).toBeVisible();
  await expect(page.getByText("10.2")).toBeVisible();
});

for (const width of [390, 1440]) {
  test(`Week 2 WR picks retain prior winner rewards at ${width}px`, async ({ page, context }) => {
    await page.setViewportSize({ width, height: 900 });
    const next = { ...contest, id: 9, week_number: 2, contest_position: "WR", status: "OPEN", lock_at: "2030-09-12T16:00:00Z",
      players: Array.from({ length: 6 }, (_, i) => ({ ...contest.players[0], id: 90 + i, player_id: 90 + i,
        player_name: `Receiver ${i + 1}`, canonical_position: "WR", live_points: null, scoring_status: "NOT_STARTED", sort_order: i + 1 })) };
    const reward = { ...contest, status: "FINAL", contest_position: "RB", entry: { id: 1, is_winner: true, selected_pick_player_id: 81 },
      sponsor: { ...contest.sponsor, reward_unlocked: true, code: "TEST-WINNER", url: null } };
    await page.route("**/saturday-pick-6/current", route => route.fulfill({ json: next }));
    await page.route("**/saturday-pick-6/rewards", route => route.fulfill({ json: [reward] }));
    await page.goto("/saturday-pick-6");
    await expect(page.getByText("Week 2 · WR Week")).toBeVisible();
    await expect(page.getByText(/Which featured wide receiver/)).toBeVisible();
    await expect(page.getByText(/Which featured running back/)).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Congratulations, you won!" })).toBeVisible();
    await expect(page.getByText("TEST-WINNER")).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose player" })).toHaveCount(6);
    await page.getByRole("button", { name: "Choose player" }).first().click();
    await expect(page.getByRole("button", { name: "Your Pick", exact: true })).toBeVisible();
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.getByRole("button", { name: "Copy Code" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("TEST-WINNER");
    await page.screenshot({ path: `/private/tmp/pick-six-week2-${width}.png`, fullPage: true });
  });
}
