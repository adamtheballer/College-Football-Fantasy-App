// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  routeUniversalLink,
  registerNativeDeepLinks,
} from "./native-deep-links";
const app = vi.hoisted(() => ({ addListener: vi.fn(), getLaunchUrl: vi.fn() }));
vi.mock("@capacitor/core", () => ({
  Capacitor: { isNativePlatform: () => true },
}));
vi.mock("@capacitor/app", () => ({ App: app }));
afterEach(() => {
  window.history.replaceState(null, "", "/");
  vi.clearAllMocks();
});
describe("challenge universal links", () => {
  it("keeps protected challenge destinations and creator attribution intact", () => {
    routeUniversalLink(
      "https://collegefantasyfootball.org/weekly-challenges/experiences/12?ref=qa-creator",
    );
    expect(location.pathname + location.search).toBe(
      "/weekly-challenges/experiences/12?ref=qa-creator",
    );
    routeUniversalLink(
      "https://www.collegefantasyfootball.org/challenges/creator/qa-creator?ref=qa-creator",
    );
    expect(location.pathname).toBe("/challenges/creator/qa-creator");
  });
  it("rejects other hosts, credentials and unsupported paths", () => {
    for (const url of [
      "https://evil.test/weekly-challenges",
      "javascript:alert(1)",
      "https://attacker@collegefantasyfootball.org/weekly-challenges",
      "https://collegefantasyfootball.org/admin/challenge-experiences",
    ]) {
      routeUniversalLink(url);
      expect(location.pathname).toBe("/");
    }
  });
  it("handles an already-running app and a cold launch", async () => {
    app.addListener.mockResolvedValue({ remove: vi.fn() });
    app.getLaunchUrl.mockResolvedValue({
      url: "https://collegefantasyfootball.org/weekly-challenges/modes/survivor",
    });
    await registerNativeDeepLinks();
    expect(app.addListener).toHaveBeenCalledWith(
      "appUrlOpen",
      expect.any(Function),
    );
    expect(location.pathname).toBe("/weekly-challenges/modes/survivor");
    const listener = app.addListener.mock.calls[0][1];
    listener({ url: "https://collegefantasyfootball.org/weekly-challenges/8" });
    expect(location.pathname).toBe("/weekly-challenges/8");
  });
});
