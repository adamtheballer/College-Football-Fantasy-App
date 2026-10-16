import { expect, test } from "@playwright/test";

const formats = [
  ["upset", 3],
  ["slate12", 12],
  ["duels", 5],
  ["lock", 1],
  ["fantasy5", 5],
] as const;
for (const [kind, required] of formats) {
  test(`${kind} enforces the published pick count before an official network write`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      localStorage.setItem(
        "cfb_user",
        JSON.stringify({
          id: 999993,
          firstName: "Challenge QA",
          email: "challenge@example.invalid",
        }),
      );
      localStorage.setItem("cfb_access_token", "synthetic-challenge-session");
      localStorage.setItem(
        "cfb_access_token_expires_at",
        "2030-01-01T00:00:00Z",
      );
      localStorage.setItem("cfb_completed_guide_999993", "true");
    });
    const games = Array.from(
      { length: kind === "slate12" ? 12 : kind === "duels" ? 5 : 6 },
      (_, i) => ({
        id: i + 1,
        home_team: `Home ${i + 1}`,
        away_team: `Away ${i + 1}`,
        start_date: "2026-10-17T16:00:00Z",
        status: "scheduled",
        home_points: null,
        away_points: null,
      }),
    );
    const players = ["QB", "RB", "WR", "TE", "RB"].map((position, i) => ({
      id: i + 1,
      game_id: 1,
      position,
      name: `Player ${i + 1}`,
      school: "School",
      image_url: null,
    }));
    let writes = 0;
    let entry: unknown = null;
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname.replace(
        /^\/api/,
        "",
      );
      let body: unknown = { data: [], total: 0 };
      if (path === "/auth/me")
        body = {
          id: 999993,
          first_name: "Challenge QA",
          email: "challenge@example.invalid",
        };
      else if (path === "/health/runtime")
        body = {
          git_sha: "challenge-qa",
          web_git_sha: "challenge-qa",
          worker_git_sha: "challenge-qa",
          api_process_instance_uuid: "challenge-qa",
          runtime_mode: "development",
          environment: "development",
          readiness_status: "ready",
          scoring_mode: "standard",
          sportsdata_enabled: false,
          ios_app_review_enabled: false,
        };
      else if (path.includes("unread")) body = { total_unread: 0, data: [] };
      else if (path.endsWith("/entry") && route.request().method() === "PUT") {
        const payload = route.request().postDataJSON();
        expect(payload.submit).toBe(true);
        expect(payload.selections).toHaveLength(required);
        if (kind === "slate12") expect(payload.tiebreaker).toBe(45);
        writes++;
        entry = body = {
          id: 77,
          user_id: 999993,
          challenge_id: 13,
          ...payload,
          revision: 1,
          status: "submitted",
          submitted_at: "2026-10-16T05:00:00Z",
        };
      } else if (path === "/weekly-challenges/challenges/13")
        body = {
          id: 13,
          round_id: 2,
          kind,
          name: `QA ${kind}`,
          state: "Open",
          settlement_status: "published",
          version: 1,
          rules_version: "weekly-v1",
          rules: `Pick ${required}.`,
          lock_at: "2026-10-17T15:55:00Z",
          server_now: "2026-10-16T05:00:00Z",
          published_at: "2026-10-14T00:00:00Z",
          scoring_rules: null,
          scoring_version: null,
          games,
          players: kind === "fantasy5" ? players : [],
          underdogs:
            kind === "upset"
              ? games.map((g) => ({
                  game_id: g.id,
                  team: g.away_team,
                  points: 2,
                }))
              : [],
          featured_game_id: kind === "slate12" ? 1 : null,
          entry,
          cancellation_reason: null,
          draft_config: null,
        };
      else if (path.endsWith("/duels")) body = [];
      await route.fulfill({ status: 200, json: body });
    });
    await page.goto("/weekly-challenges/13");
    const form = page.getByRole("form", { name: `QA ${kind} entry` });
    const submit = form.getByRole("button", { name: "Submit Official Entry" });
    await expect(submit).toBeDisabled();
    if (kind === "fantasy5") {
      for (const [i, slot] of ["QB", "RB", "WR", "TE", "FLEX"].entries())
        await form
          .getByRole("combobox", { name: `${slot} player` })
          .selectOption(String(i + 1));
    } else {
      for (let i = 1; i <= required; i++)
        await form
          .getByRole("button", {
            name: kind === "upset" ? `Away ${i} · 2 points` : `Home ${i}`,
            exact: true,
          })
          .click();
      if (kind === "upset") {
        const extra = form.getByRole("button", {
          name: "Away 4 · 2 points",
          exact: true,
        });
        await expect(extra).toBeDisabled();
        await expect(form.getByRole("button", { pressed: true })).toHaveCount(
          3,
        );
        await form
          .getByRole("button", { name: "✓ Away 2 · 2 points", exact: true })
          .click();
        await expect(submit).toBeDisabled();
        await expect(extra).toBeEnabled();
        await extra.click();
      }
      if (kind === "slate12") {
        await expect(submit).toBeDisabled();
        await form
          .getByRole("spinbutton", { name: "Featured game total score" })
          .fill("45");
      }
    }
    expect(writes).toBe(0);
    await expect(submit).toBeEnabled();
    await page.screenshot({
      path: info.outputPath(`${kind}-valid-selection.png`),
      animations: "disabled",
    });
    await submit.click();
    await expect(form.getByRole("status")).toHaveText(
      "Your official entry is submitted.",
    );
    expect(writes).toBe(1);
  });
}
