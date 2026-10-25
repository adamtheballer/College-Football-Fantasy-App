import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(
    new URL("../../shared/challenge-experiences.fixture.json", import.meta.url),
    "utf8",
  ),
);
import type { Challenge } from "../../client/hooks/use-weekly-challenges";

async function setup(
  page: Page,
  { locked = false, offline = false, loggedOut = false, topFive = false } = {},
) {
  const challenges = structuredClone(fixture.challenges) as Challenge[];
  let writes = 0;
  await page.addInitScript((signedOut) => {
    if (!signedOut) {
      localStorage.setItem(
        "cfb_user",
        JSON.stringify({
          id: 99112,
          firstName: "Expansion QA",
          email: "expansion@example.invalid",
        }),
      );
      localStorage.setItem("cfb_access_token", "isolated-expansion-session");
      localStorage.setItem(
        "cfb_access_token_expires_at",
        "2030-01-01T00:00:00Z",
      );
    }
    localStorage.setItem("cfb_completed_guide_99112", "true");
  }, loggedOut);
  const oldKinds = ["slate12", "upset", "fantasy5", "lock", "duels"] as const;
  const old = oldKinds.map((kind, i) => ({
    ...challenges[0],
    id: 20 + i,
    kind,
    name: [
      "Slate 12",
      "Upset Hunter",
      "Fantasy Five",
      "Lock of the Week",
      "Rivalry Duels",
    ][i],
    experience: null,
  }));
  if (locked)
    for (const c of challenges) {
      c.state = "Closed — Live";
      c.lock_at = c.server_now;
      c.experience!.locked_game_ids = c.games.map((g) => g.id);
    }
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname.replace(/^\/api/, "");
    let body: unknown = { data: [], total: 0 };
    if (path === "/health/runtime") {
      await route.fulfill({
        status: 503,
        json: { detail: "Isolated fixture" },
      });
      return;
    }
    if (path === "/auth/login")
      body = {
        access_token: "isolated-expansion-session",
        access_token_expires_at: "2030-01-01T00:00:00Z",
        user: {
          id: 99112,
          first_name: "Expansion QA",
          email: "expansion@example.invalid",
        },
      };
    else if (path === "/auth/me")
      body = {
        id: 99112,
        first_name: "Expansion QA",
        email: "expansion@example.invalid",
      };
    else if (path.includes("unread")) body = { data: [], total_unread: 0 };
    else if (path === "/weekly-challenges/current")
      body = {
        id: 8,
        season: 2026,
        week: 8,
        state: "Open",
        server_now: challenges[0].server_now,
        next_rollover_at: "2026-10-28T08:00:00Z",
        sponsor: challenges[0].sponsor,
        challenges: [...old, ...challenges],
      };
    else if (path === "/weekly-challenges/modes") {
      if (offline) {
        await route.fulfill({
          status: 503,
          json: { detail: "Offline mode fixture" },
        });
        return;
      }
      body = challenges.map((c) => ({
        kind: c.kind,
        name: c.name,
        description: "Weekly competition",
        state: locked ? "In Progress" : "Open",
        participants: 0,
        competitions: [c.id],
        server_now: c.server_now,
        lock_at: c.lock_at,
      }));
    } else if (path === "/weekly-challenges/upcoming") body = null;
    else if (
      path === "/weekly-challenges/history" ||
      path === "/weekly-challenges/my-results"
    )
      body = [];
    else if (path === "/weekly-challenges/creators")
      body = [challenges[2].experience!.creator];
    else if (path === "/weekly-challenges/experiences")
      body = challenges.filter((c) => c.kind === url.searchParams.get("kind"));
    else if (path === "/weekly-challenges/analytics-preference")
      body = { enabled: true };
    else if (path === "/weekly-challenges/events") body = { recorded: true };
    else if (path.endsWith("/leaderboard") && path.includes("/experiences/"))
      body = {
        challenge_id: Number(path.split("/")[3]),
        kind: "millionaire",
        unit: "fantasy points",
        provisional: true,
        total: 0,
        data: [],
        your_rank: null,
        school_standings: [],
      };
    else if (path.match(/\/challenges\/\d+$/))
      body = [...old, ...challenges].find((c) => c.id === Number(path.split("/").pop()));
    else if (path.endsWith("/allegiance")) {
      const c = challenges.find((c) => c.id === Number(path.split("/")[3]))!;
      c.experience!.allegiance = c.experience!.schools.find(
        (s) => s.id === route.request().postDataJSON().school_id,
      )!;
      body = c.experience!.allegiance;
    } else if (path.endsWith("/entry") && route.request().method() === "PUT") {
      const c = challenges.find((c) => c.id === Number(path.split("/")[3]))!,
        payload = route.request().postDataJSON();
      expect(payload.selections.length).toBe(
        c.kind === "millionaire" ? 6 : c.kind === "creator" ? 10 : 1,
      );
      writes++;
      body = c.entry = {
        id: 81,
        challenge_id: c.id,
        user_id: 99112,
        revision: 1,
        status: "submitted",
        selections: payload.selections,
        tiebreaker: null,
        submitted_at: c.server_now,
      };
    }
    if (topFive && (path.endsWith("/leaderboard") || path.endsWith("/results"))) {
      const rows = Array.from({ length: 10 }, (_, i) => ({
        user_id: i + 1, display_name: `Point Leader ${i + 1}`, username: null,
        avatar_url: null, profile_url: `/managers/${i + 1}`, rank: i + 1,
        points: 100 - i, status: "final", selections: null,
      }));
      const mine = { ...rows[9], rank: 30, display_name: "Outside cutoff" };
      body = path.endsWith("/results") ? {
        data: rows.map((participant, i) => ({ participant, entry_id: i + 1,
          rank: i + 1, challenge_points: 10 - i, raw_points: 100 - i,
          status: "final", tiebreaker_error: null })),
        total: 30, my_result: { participant: mine },
      } : {
        season: 2026, week: 8, data: rows, your_rank: mine, total: 30,
        unit: "points", provisional: false,
        school_standings: rows.map((r) => ({ school_id: r.user_id, school: `School ${r.user_id}`,
          rank: r.rank, accuracy: 50, fan_points: r.points, active_fans: 5,
          correct_picks: 5, eligible_picks: 10 })),
      };
    }
    await route.fulfill({ status: 200, json: body });
  });
  return { challenges, writes: () => writes };
}
test("top five leaderboards never show extra point leaders or personal-rank rows", async ({ page }, info) => {
  await setup(page, { locked: true, topFive: true });
  for (const mode of ["overall", "millionaire", "fanwars", "existing"]) {
    await page.goto(`/weekly-challenges/leaderboard?mode=${mode}`);
    await expect(page.getByRole("link", { name: /Point Leader 5\b/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Point Leader \d/ })).toHaveCount(5);
    await expect(page.getByText(/Point Leader (6|7|8|9|10)\b|Outside cutoff|Your Rank|Your rank|Your Result|Top 10/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^(Next|Previous)$/ })).toHaveCount(0);
    if (mode === "fanwars") {
      await expect(page.getByRole("cell", { name: /^School 5/ })).toBeVisible();
      await expect(page.getByRole("cell", { name: /^School 6/ })).toHaveCount(0);
    }
    if (mode === "overall") {
      await page.getByRole("button", { name: "Season", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Season Championship" })).toBeVisible();
      await expect(page.getByRole("link", { name: /Point Leader \d/ })).toHaveCount(5);
    }
  }
  await page.screenshot({ path: info.outputPath("top-five-only.png"), fullPage: true });
});
for (const width of [320, 390, 1280]) {
  test(`unified hub preserves all nine challenges and navigation at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 844 });
    await setup(page);
    await page.goto("/weekly-challenges");
    await expect(
      page.getByRole("heading", { name: "Weekly Challenges", exact: true }),
    ).toBeVisible();
    const modes = page.getByRole("region", { name: "Challenge experiences" });
    await expect(modes.getByRole("link")).toHaveCount(4);
    for (const name of [
      "Slate 12",
      "Upset Hunter",
      "Fantasy Five",
      "Lock of the Week",
      "Rivalry Duels",
    ])
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
    if (width < 768) {
      const nav = page.getByRole("navigation", {
        name: "Primary mobile navigation",
      });
      await expect(nav.getByRole("link")).toHaveCount(5);
      await expect(
        nav.getByRole("button", { name: "Open all navigation" }),
      ).toBeVisible();
      expect(await nav.locator("a").allTextContents()).toEqual([
        "Home",
        "Leagues",
        "Chats",
        "Draft",
        "Challenges",
      ]);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`challenges-hub-${width}.png`),
      fullPage: true,
    });
  });
}
for (const kind of ["fanwars", "creator", "survivor"] as const) {
  test(`${kind} only submits a complete eligible entry and preserves server state`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const f = await setup(page);
    const c = f.challenges.find((c) => c.kind === kind)!;
    await page.goto(`/weekly-challenges/experiences/${c.id}`);
    await expect(
      page.getByRole("button", { name: "Submit Entry", exact: true }),
    ).toBeDisabled();
    if (kind === "fanwars")
      await page
        .getByRole("button", { name: "Alabama · SEC", exact: true })
        .click();
    const games = kind === "creator" ? c.games : c.games.slice(0, 1);
    for (const g of games)
      await page
        .getByRole("button", { name: g.home_team, exact: true })
        .click();
    await page
      .getByRole("button", { name: "Submit Entry", exact: true })
      .click();
    await expect(
      page.getByText("Your official entry is submitted.", { exact: true }),
    ).toBeVisible();
    expect(f.writes()).toBe(1);
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Update Official Entry" }),
    ).toBeVisible();
  });
}
test("Millionaire formation uses two distinct receivers and budget before submission", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const f = await setup(page);
  const c = f.challenges.find((c) => c.kind === "millionaire")!;
  await page.goto(`/weekly-challenges/experiences/${c.id}`);
  await expect(
    page.getByRole("button", { name: "Submit Entry", exact: true }),
  ).toBeDisabled();
  const slots = ["QB", "RB", "WR 1", "WR 2", "TE", "FLEX"];
  const ids = [101, 102, 103, 107, 104, 105];
  for (let i = 0; i < slots.length; i++) {
    await page
      .getByRole("button", { name: `Choose ${slots[i]} player`, exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    if (i === 3)
      await expect(
        dialog.getByRole("button", {
          name: new RegExp(
            "^" + c.players.find((p) => p.id === 103)!.name + " ",
          ),
        }),
      ).toBeDisabled();
    await dialog
      .getByRole("button", {
        name: new RegExp(
          "^" + c.players.find((p) => p.id === ids[i])!.name + " ",
        ),
      })
      .click();
  }
  await expect(
    page.getByRole("region", { name: "Virtual salary budget" }),
  ).toContainText("60");
  await page.getByRole("button", { name: "Submit Entry", exact: true }).click();
  await expect(
    page.getByText("Your official entry is submitted.", { exact: true }),
  ).toBeVisible();
  expect(f.writes()).toBe(1);
  await expect(
    page.getByLabel(
      "Include my player choices before lock (hidden by default)",
    ),
  ).not.toBeChecked();
  await page.screenshot({
    path: info.outputPath("millionaire-submitted.png"),
    fullPage: true,
  });
});
test("locked modes cannot send an entry", async ({ page }) => {
  await setup(page, { locked: true });
  await page.goto("/weekly-challenges/experiences/7");
  await expect(page.getByText(/Closed — Live/).first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit Entry", exact: true }),
  ).toHaveCount(0);
});

test("a logged-out challenge deep link survives login and the lazy route transition", async ({
  page,
}) => {
  await setup(page, { loggedOut: true });
  await page.addInitScript(() =>
    localStorage.removeItem("cfb_completed_guide_99112"),
  );
  await page.goto("/weekly-challenges/experiences/7?ref=qa-creator");
  await page
    .getByLabel("Email address", { exact: true })
    .fill("expansion@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill("StrongPass123!");
  await page
    .getByRole("button", { name: "Sign in to dashboard", exact: true })
    .click();
  await expect(page).toHaveURL(
    /\/weekly-challenges\/experiences\/7\?ref=qa-creator$/,
  );
  await expect(
    page.getByRole("heading", { name: "Fantasy Millionaire", exact: true }),
  ).toBeVisible();
});

test("mode fetch failure is visible and offers retry without deleting the old five", async ({
  page,
}) => {
  await setup(page, { offline: true });
  await page.goto("/weekly-challenges");
  await expect(
    page.getByText("Competition modes are unavailable.", { exact: false }),
  ).toBeVisible({ timeout: 15000 });
  await expect(
    page.getByRole("heading", { name: "Upset Hunter", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry modes", exact: true }),
  ).toBeVisible();
});
