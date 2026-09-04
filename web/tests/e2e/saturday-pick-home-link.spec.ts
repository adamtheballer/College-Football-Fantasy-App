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

test("the homepage West Georgia Cornhole event button opens the live Pick 6 player totals", async ({ page }) => {
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

  await page.goto("/");
  const sponsorButton = page.getByRole("link", { name: "Open Saturday Pick 6 event" });
  await expect(sponsorButton).toBeVisible();
  await sponsorButton.click();

  await expect(page).toHaveURL(/\/saturday-pick-6$/);
  await expect(page.getByRole("heading", { name: "Featured Player" })).toBeVisible();
  await expect(page.getByText("Live points")).toBeVisible();
  await expect(page.getByText("10.2")).toBeVisible();
});
