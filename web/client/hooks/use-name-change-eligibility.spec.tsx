// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useNameChangeEligibility } from "./use-name-change-eligibility";
import { formatNameChangeWait, type NameChangeEligibility } from "@/lib/name-change";

const mocks = vi.hoisted(() => ({ get: vi.fn(), native: false, listener: vi.fn(), remove: vi.fn() }));
vi.mock("@/lib/api", () => ({ apiGet: mocks.get }));
vi.mock("@/lib/native-session", () => ({ isNativeSessionRuntime: () => mocks.native }));
vi.mock("@capacitor/app", () => ({ App: { addListener: mocks.listener } }));
const timing: NameChangeEligibility = { account_id: 7, current_name: "Server Manager", server_time: "2026-10-13T12:00:00Z", last_successful_change_at: null, next_eligible_at: null, remaining_wait_seconds: 0, can_change_name: true };
beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks(); mocks.native = false; mocks.get.mockResolvedValue(timing); mocks.listener.mockResolvedValue({ remove: mocks.remove }); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });
const tick = (ms = 0) => act(() => vi.advanceTimersByTimeAsync(ms));

describe("server name-change timing", () => {
  it("fetches current eligibility on Settings open without using cached account dates", async () => {
    const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    expect(hook.result.current.phase).toBe("ready"); expect(hook.result.current.timing?.current_name).toBe("Server Manager");
    expect(mocks.get).toHaveBeenCalledWith("/auth/me/name-change-eligibility", undefined, expect.any(AbortSignal));
  });
  it("guests and authentication restoration in progress do not fetch", async () => {
    renderHook(() => useNameChangeEligibility(null, false)); await tick(); expect(mocks.get).not.toHaveBeenCalled();
  });
  it("unlocks while left open only after authoritative server confirmation", async () => {
    mocks.get.mockResolvedValueOnce({ ...timing, next_eligible_at: "2026-10-13T12:00:02Z", remaining_wait_seconds: 2, can_change_name: false });
    const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    expect(hook.result.current.remainingSeconds).toBe(2); await tick(1000); expect(hook.result.current.remainingSeconds).toBe(1);
    await tick(1000); expect(mocks.get).toHaveBeenCalledTimes(2); expect(hook.result.current.timing?.can_change_name).toBe(true);
    await tick(60_000); expect(mocks.get).toHaveBeenCalledTimes(2);
  });
  it("incorrect device clock cannot shorten or extend a server countdown", async () => {
    mocks.get.mockResolvedValue({ ...timing, next_eligible_at: "2026-10-13T12:01:00Z", remaining_wait_seconds: 60, can_change_name: false });
    const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    vi.setSystemTime(new Date("2099-01-01T00:00:00Z")); await tick(1000); expect(hook.result.current.remainingSeconds).toBe(59);
    vi.setSystemTime(new Date("2000-01-01T00:00:00Z")); await tick(1000); expect(hook.result.current.remainingSeconds).toBe(58);
  });
  it("reconfirms a fractional-second deadline without waiting for the next display tick", async () => {
    mocks.get.mockResolvedValueOnce({ ...timing, next_eligible_at: "2026-10-13T12:00:00.250Z", remaining_wait_seconds: 1, can_change_name: false });
    const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    await tick(249); expect(mocks.get).toHaveBeenCalledTimes(1);
    expect(hook.result.current.remainingSeconds).toBe(1);
    await tick(1); expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(hook.result.current.timing?.can_change_name).toBe(true);
  });
  it("background cancels countdown and foreground fetches fresh timing", async () => {
    mocks.native = true; const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    const listener = mocks.listener.mock.calls[0][1]; await act(async () => listener({ isActive: false }));
    await tick(9000); expect(mocks.get).toHaveBeenCalledTimes(1);
    await act(async () => listener({ isActive: true })); await tick(); expect(mocks.get).toHaveBeenCalledTimes(2);
    hook.unmount(); await tick(); expect(mocks.remove).toHaveBeenCalledTimes(1);
  });
  it("browser focus refreshes the current account", async () => {
    renderHook(() => useNameChangeEligibility(7, true)); await tick();
    await act(async () => { window.dispatchEvent(new Event("focus")); }); await tick(); expect(mocks.get).toHaveBeenCalledTimes(2);
  });
  it("offline produces a recoverable error and no polling", async () => {
    mocks.get.mockRejectedValueOnce(new Error("offline")); const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    expect(hook.result.current.phase).toBe("error"); expect(hook.result.current.timing).toBeNull();
    await tick(60_000); expect(mocks.get).toHaveBeenCalledTimes(1);
    await act(async () => hook.result.current.refresh()); expect(hook.result.current.phase).toBe("ready");
  });
  it("malformed or wrong-account response never supplies eligibility", async () => {
    mocks.get.mockResolvedValue({ ...timing, account_id: 22 }); const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick();
    expect(hook.result.current.phase).toBe("error"); expect(hook.result.current.timing).toBeNull();
  });
  it("an account switch aborts and discards an older eligibility response", async () => {
    let resolve!: (value: NameChangeEligibility) => void; mocks.get.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const hook = renderHook(({ id }) => useNameChangeEligibility(id, true), { initialProps: { id: 7 } });
    const firstSignal = mocks.get.mock.calls[0][2]; mocks.get.mockResolvedValue({ ...timing, account_id: 22, current_name: "Second Account" });
    hook.rerender({ id: 22 }); await tick(); await act(async () => resolve(timing));
    expect(firstSignal.aborted).toBe(true); expect(hook.result.current.timing?.account_id).toBe(22);
  });
  it("invalidation during save prevents a slow eligibility result overwriting the newer name", async () => {
    let resolve!: (value: NameChangeEligibility) => void; mocks.get.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const hook = renderHook(() => useNameChangeEligibility(7, true));
    act(() => hook.result.current.invalidate()); mocks.get.mockResolvedValue({ ...timing, current_name: "Saved Manager" });
    await act(async () => hook.result.current.refresh()); await act(async () => resolve(timing));
    expect(hook.result.current.timing?.current_name).toBe("Saved Manager");
  });
  it("closing Settings aborts work and clears its countdown", async () => {
    mocks.get.mockResolvedValue({ ...timing, next_eligible_at: "2026-10-13T12:01:00Z", remaining_wait_seconds: 60, can_change_name: false });
    const hook = renderHook(() => useNameChangeEligibility(7, true)); await tick(); hook.unmount(); await tick(120_000);
    expect(mocks.get).toHaveBeenCalledTimes(1);
  });
  it.each([[2 * 86400 + 4 * 3600 + 12 * 60, "2 days, 4 hours, and 12 minutes"], [59, "less than a minute"], [60, "1 minute"], [3600, "1 hour"], [86400, "1 day"]])("formats %s seconds as %s", (seconds, expected) => {
    expect(formatNameChangeWait(seconds as number)).toBe(expected);
  });
});
