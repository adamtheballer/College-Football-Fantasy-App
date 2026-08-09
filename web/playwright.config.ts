import { defineConfig, devices } from "@playwright/test";

const realStack = process.env.REAL_STACK_E2E === "1" || process.env.E2E_REAL_STACK === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // The disposable real-stack suite shares one seeded database. Its draft
  // scenario still opens two browser contexts, but separate specs must start
  // serially so each waits for the runtime-provenance gate independently.
  workers: realStack ? 1 : process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: realStack ? undefined : {
    command: "VITE_BETA_ACCESS_ENABLED=true npm run dev:vite -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "desktop-chrome",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chrome",
      testMatch: "**/mobile-shell.spec.ts",
      use: {
        ...devices["Pixel 5"],
        viewport: { width: 375, height: 667 },
        screen: { width: 375, height: 667 },
      },
    },
    {
      name: "mobile-safari",
      testMatch: "**/mobile-shell.spec.ts",
      use: {
        ...devices["iPhone 13"],
        viewport: { width: 390, height: 844 },
        screen: { width: 390, height: 844 },
      },
    },
  ],
});
