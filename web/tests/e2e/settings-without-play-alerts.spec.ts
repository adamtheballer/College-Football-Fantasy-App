import { expect, test } from "@playwright/test";

// Local fixture responses deliberately include retired keys to emulate an old API.
for (const width of [1280, 390]) {
  test(`Settings excludes retired play alerts and saves remaining controls ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(() => {
      localStorage.setItem("cfb_user", JSON.stringify({ id: 999995, firstName: "Settings QA", email: "settings@example.invalid", isAdmin: false }));
      localStorage.setItem("cfb_access_token", "synthetic-settings-qa");
      localStorage.setItem("cfb_access_token_expires_at", "2030-01-01T00:00:00Z");
      localStorage.setItem("cfb_completed_guide_999995", "true");
    });
    const preferences = {
      push_drafts: true, push_matchups: true, push_injuries: true, push_major_news: false,
      push_enabled: false, email_enabled: false, draft_alerts: true, injury_alerts: true,
      injury_alert_scope: "ALL", usage_alerts: false, waiver_alerts: true, projection_alerts: false,
      lineup_reminders: true, trade_alerts: true, chat_alerts: true, matchup_results: true,
      matchup_start_alerts: true, matchup_result_alerts: true, quiet_hours_start: null,
      quiet_hours_end: null, timezone: "America/New_York",
      big_play_alerts: true, touchdown_alerts: true, long_rush_alerts: true,
      long_reception_alerts: true, long_pass_alerts: true,
    };
    const league = { ...preferences, league_id: 42, league_name: "Settings QA League", enabled: true };
    const saves: Record<string, unknown>[] = [];
    await page.route("**/api/**", async route => {
      const path = new URL(route.request().url()).pathname.replace(/^\/api/, "");
      let body: unknown = { data: [], total: 0 };
      if (path === "/auth/me") body = { id: 999995, first_name: "Settings QA", email: "settings@example.invalid" };
      else if (path === "/health/runtime") body = { git_sha: "synthetic-settings", web_git_sha: "synthetic-settings", worker_git_sha: "synthetic-settings", api_process_instance_uuid: "synthetic-settings", runtime_mode: "development", environment: "development", readiness_status: "ready", ios_app_review_enabled: false };
      else if (path.includes("unread-count")) body = { total_unread: 0 };
      else if (path === "/notifications/preferences") {
        if (route.request().method() === "POST") { body = route.request().postDataJSON(); saves.push(body as Record<string, unknown>); }
        else body = preferences;
      } else if (path === "/notifications/league-preferences") {
        if (route.request().method() === "POST") {
          const payload = route.request().postDataJSON(); saves.push(payload.items[0]); body = { data: payload.items };
        } else body = { data: [league] };
      }
      await route.fulfill({ status: 200, json: body });
    });
    await page.goto("/settings");
    await expect(page.getByLabel("Drafts notifications", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Settings QA League Injury updates", { exact: true })).toBeVisible();
    await expect(page.locator("body")).not.toContainText(/Big plays|Long rushes|Long receptions|Long passes|Touchdowns/i);
    await page.getByLabel("Drafts notifications", { exact: true }).click();
    await expect.poll(() => saves.length).toBe(1);
    await expect(page.getByLabel("Drafts notifications", { exact: true })).not.toBeChecked();
    await page.getByLabel("Settings QA League Injury updates", { exact: true }).click();
    await expect.poll(() => saves.length).toBe(2);
    expect(saves[0].draft_alerts).toBe(false);
    expect(saves[1].injury_alerts).toBe(false);
    for (const payload of saves) for (const key of ["big_play_alerts", "touchdown_alerts", "long_rush_alerts", "long_reception_alerts", "long_pass_alerts"]) expect(payload).not.toHaveProperty(key);
    await page.reload();
    await expect(page.getByLabel("Drafts notifications", { exact: true })).toBeVisible();
    await expect(page.locator("body")).not.toContainText(/Big plays|Long rushes|Long receptions|Long passes|Touchdowns/i);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // Settings scrolls inside the app shell; capture the controls themselves.
    await page.getByText("Phone alert categories", { exact: true }).evaluate(element => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: info.outputPath("settings-without-play-alerts.png"), animations: "disabled" });
    await page.getByLabel("Settings QA League notifications", { exact: true }).evaluate(element => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: info.outputPath("league-settings-without-play-alerts.png"), animations: "disabled" });
  });
}
