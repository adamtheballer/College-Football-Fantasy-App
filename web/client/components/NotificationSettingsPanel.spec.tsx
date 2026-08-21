// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

const deferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
};

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
const push = vi.hoisted(() => ({
  enable: vi.fn(),
  prepare: vi.fn().mockResolvedValue(undefined),
  resolve: vi.fn().mockResolvedValue("default"),
}));

vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: { id: 7 } }) }));
vi.mock("@/lib/api", () => ({ apiGet: api.get, apiPost: api.post }));
vi.mock("@/lib/push-notifications", () => ({
  getBrowserPushState: () => "default",
  enableBrowserPush: push.enable,
  prepareBrowserPush: push.prepare,
  resolvePushState: push.resolve,
}));

import { NotificationSettingsPanel } from "./NotificationSettingsPanel";

const preferences = {
  push_enabled: false, email_enabled: false, draft_alerts: true, injury_alerts: false,
  usage_alerts: false, waiver_alerts: true, projection_alerts: false,
  lineup_reminders: true, trade_alerts: true, chat_alerts: true, matchup_results: true,
  matchup_start_alerts: true, matchup_result_alerts: true, big_play_alerts: false,
  long_rush_alerts: false, long_reception_alerts: false, long_pass_alerts: false,
  quiet_hours_start: null, quiet_hours_end: null, timezone: "America/New_York",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NotificationSettingsPanel async lifecycle", () => {
  it("aborts delayed settings work on unmount without a post-unmount error", async () => {
    const preferencesRequest = deferred<typeof preferences>();
    const leaguesRequest = deferred<{ data: [] }>();
    api.get.mockImplementationOnce(() => preferencesRequest.promise).mockImplementationOnce(() => leaguesRequest.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const view = render(<NotificationSettingsPanel />);
    view.unmount();
    await act(async () => {
      preferencesRequest.reject(new DOMException("aborted", "AbortError"));
      leaguesRequest.resolve({ data: [] });
      await Promise.resolve();
    });

    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("applies a successful initial settings response while it remains mounted", async () => {
    api.get.mockResolvedValueOnce(preferences).mockResolvedValueOnce({ data: [] });
    render(<NotificationSettingsPanel />);

    expect(await screen.findByLabelText("Drafts notifications")).toBeTruthy();
    expect(screen.getByText("Push delivery")).toBeTruthy();
  });

  it("groups long-play alerts beneath their Big Plays master control without a touchdown option", async () => {
    api.get.mockResolvedValueOnce(preferences).mockResolvedValueOnce({ data: [] });
    render(<NotificationSettingsPanel />);

    const group = await screen.findByTestId("big-play-alert-group");
    expect(group.textContent).toContain("Master control for verified live long-play alerts");
    expect(group.textContent).toContain("30+ yard rushing plays");
    expect(group.textContent).toContain("40+ yard receptions");
    expect(group.textContent).toContain("40+ yard completed passes");
    expect(screen.queryByLabelText("Touchdowns notifications")).toBeNull();
  });

  it("aborts a delayed preference update on unmount without reporting an async error", async () => {
    const saveRequest = deferred<typeof preferences>();
    api.get.mockResolvedValueOnce(preferences).mockResolvedValueOnce({ data: [] });
    api.post.mockReturnValueOnce(saveRequest.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const view = render(<NotificationSettingsPanel />);
    const drafts = await screen.findByLabelText("Drafts notifications");
    fireEvent.click(drafts);
    expect(api.post).toHaveBeenCalledTimes(1);
    const signal = api.post.mock.calls[0]?.[3] as AbortSignal;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      saveRequest.resolve({ ...preferences, draft_alerts: false });
      await Promise.resolve();
    });

    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("ignores a late OneSignal permission result after unmount", async () => {
    const permissionRequest = deferred<"granted">();
    api.get.mockResolvedValueOnce(preferences).mockResolvedValueOnce({ data: [] });
    push.enable.mockReturnValueOnce(permissionRequest.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const view = render(<NotificationSettingsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Enable push notifications" }));
    view.unmount();
    await act(async () => {
      permissionRequest.resolve("granted");
      await Promise.resolve();
    });

    expect(api.post).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("shows a persisted enabled check after granting push permission", async () => {
    api.get.mockResolvedValueOnce(preferences).mockResolvedValueOnce({ data: [] });
    push.enable.mockResolvedValueOnce("granted");
    api.post.mockResolvedValueOnce({ ...preferences, push_enabled: true });
    render(<NotificationSettingsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Enable push notifications" }));

    expect((await screen.findByTestId("push-status")).textContent).toContain("Enabled");
    expect(screen.getByTestId("push-status").querySelector("svg")).toBeTruthy();
    expect(api.post).toHaveBeenCalledWith(
      "/notifications/preferences",
      { ...preferences, push_enabled: true },
      undefined,
      expect.any(AbortSignal)
    );
  });
});
