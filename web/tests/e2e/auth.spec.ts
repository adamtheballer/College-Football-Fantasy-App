import { expect, test } from "@playwright/test";

const authPayload = {
  access_token: "e2e-access-token",
  access_token_expires_at: "2030-01-01T00:00:00Z",
  user: {
    id: 77,
    first_name: "E2E",
    email: "e2e@example.com",
    email_verified_at: "2026-01-01T00:00:00Z",
  },
};

const seedAuth = async (page: Parameters<typeof test>[0]["page"]) => {
  await page.addInitScript((payload) => {
    document.cookie = "cfb_csrf_token=e2e-csrf-token; path=/";
    window.localStorage.setItem(
      "cfb_user",
      JSON.stringify({
        id: payload.user.id,
        firstName: payload.user.first_name,
        email: payload.user.email,
        emailVerifiedAt: payload.user.email_verified_at,
      })
    );
    window.localStorage.setItem("cfb_access_token", payload.access_token);
    window.localStorage.setItem("cfb_access_token_expires_at", payload.access_token_expires_at);
    window.localStorage.setItem(`cfb_completed_guide_${payload.user.id}`, "true");
  }, authPayload);
  await page.route("**/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(authPayload.user),
    });
  });
  await page.route("**/notifications/preferences**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        push_enabled: true,
        email_enabled: true,
        draft_alerts: true,
        injury_alerts: true,
        touchdown_alerts: false,
        usage_alerts: true,
        waiver_alerts: true,
        projection_alerts: true,
        lineup_reminders: true,
      }),
    });
  });
  await page.route("**/notifications/league-preferences", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [] }),
    });
  });
  await page.route("**/leagues?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [], total: 0, limit: 50, offset: 0 }),
    });
  });
};

test.describe("auth security flows", () => {
  test("signup stores an authenticated session", async ({ page }) => {
    await page.route("**/auth/signup", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        headers: { "set-cookie": "cfb_csrf_token=e2e-csrf-token; Path=/" },
        body: JSON.stringify(authPayload),
      });
    });

    await page.goto("/signup");
    await page.getByPlaceholder("Enter your first name").fill("E2E");
    await page.getByPlaceholder("coach@saturday.com").fill("e2e@example.com");
    await page.getByPlaceholder("••••••••").fill("StrongPass123!");
    await page.getByRole("button", { name: /Create Account/i }).click();
    await page.waitForURL("**/");

    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cfb_access_token")))
      .toBe("e2e-access-token");
  });

  test("forgot password and reset password flow complete without leaking auth state", async ({ page }) => {
    let requestedReset = false;
    let confirmedReset = false;
    await page.route("**/auth/password-reset/request", async (route) => {
      requestedReset = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, message: "sent" }),
      });
    });
    await page.route("**/auth/password-reset/confirm", async (route) => {
      confirmedReset = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, message: "reset" }),
      });
    });

    await page.goto("/password-reset");
    await page.getByPlaceholder("coach@saturday.com").fill("e2e@example.com");
    await page.getByRole("button", { name: /Send Reset Link/i }).click();
    await expect(page.getByText(/reset link has been sent/i)).toBeVisible();
    expect(requestedReset).toBe(true);

    await page.goto("/password-reset/confirm?token=reset-token");
    await page.getByPlaceholder("••••••••").fill("NewStrongPass123!");
    await page.getByRole("button", { name: /Save New Password/i }).click();
    await page.waitForURL("**/login");
    expect(confirmedReset).toBe(true);
    expect(await page.evaluate(() => window.localStorage.getItem("cfb_access_token"))).toBeNull();
  });

  test("settings page lists and revokes sessions with csrf header", async ({ page }) => {
    await seedAuth(page);
    let sawCsrfHeader = false;
    await page.route("**/auth/sessions**", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            sessions: [
              {
                id: 10,
                issued_at: "2026-01-01T00:00:00Z",
                expires_at: "2030-01-01T00:00:00Z",
                last_used_at: "2026-01-02T00:00:00Z",
                user_agent: "Desktop Chrome",
                ip_address: "127.0.0.1",
                is_current: true,
              },
            ],
          }),
        });
        return;
      }
      sawCsrfHeader = route.request().headers()["x-csrf-token"] === "e2e-csrf-token";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, message: "session revoked" }),
      });
    });

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Active Sessions" })).toBeVisible();
    await expect(page.getByText("Desktop Chrome")).toBeVisible();
    await page.getByRole("button", { name: /Revoke/i }).click();
    await expect.poll(() => sawCsrfHeader).toBe(true);
  });
});
