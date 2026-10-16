import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppReviewCoordinator, type ReviewClaim, type ReviewContext, type ReviewDependencies, type ReviewState } from "./app-review";

const ready: ReviewContext = { accountId: 11, enabled: true, native: true, foreground: true, safe: true, screenKey: "home" };
const state: ReviewState = { account_id: 11, enabled: true, review_request_claimed_at: null };
const grant: ReviewClaim = { ...state, review_request_claimed_at: "2026-10-13T00:00:00Z", authorization: "granted" };
const deferred = <T>() => { let resolve!: (value: T) => void; let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

function fixture(overrides: Partial<ReviewDependencies> = {}) {
  const consumed = new Set<number>();
  const adapter = { synchronize: vi.fn().mockResolvedValue({ ready: true, appVersion: "1.0", appBuild: "123" }), request: vi.fn().mockResolvedValue({ invoked: true }) };
  const dependencies = { adapter, state: vi.fn().mockResolvedValue(state), claim: vi.fn().mockResolvedValue(grant),
    consumed: (id: number) => consumed.has(id), remember: vi.fn((id: number) => { consumed.add(id); }), now: Date.now };
  const controller = new AppReviewCoordinator({ ...dependencies, ...overrides });
  controllers.push(controller);
  return { controller, dependencies, adapter, consumed };
}
let controllers: AppReviewCoordinator[];
beforeEach(() => { controllers = []; vi.useFakeTimers(); });
afterEach(() => { controllers.forEach((controller) => controller.dispose()); vi.useRealTimers(); });
const wait = (ms = 3000) => vi.advanceTimersByTimeAsync(ms);

describe("account lifetime review coordinator", () => {
  it("supports immediate presentation after Home becomes usable without a three-second wait", async () => {
    const { controller, adapter, dependencies } = fixture({ presentationDelayMs: 0 });
    controller.update({ ...ready, safe: false }); await wait(0);
    expect(dependencies.claim).not.toHaveBeenCalled();
    controller.update(ready);
    expect(adapter.request).not.toHaveBeenCalled();
    await wait(0);
    expect(adapter.request).toHaveBeenCalledTimes(1);
    controller.update(ready); controller.interrupt(); await wait(10_000);
    expect(adapter.request).toHaveBeenCalledTimes(1);
  });
  it.each(["existing authenticated visit", "new successful login after onboarding", "restored session without manual login"])("qualifies %s after three safe seconds", async () => {
    const { controller, dependencies, adapter } = fixture();
    controller.update({ ...ready, safe: false }); await wait();
    expect(dependencies.state).not.toHaveBeenCalled();
    controller.update(ready); await wait(2999);
    expect(adapter.request).not.toHaveBeenCalled(); await wait(1);
    expect(dependencies.state).toHaveBeenCalledWith(11, expect.any(AbortSignal));
    expect(dependencies.remember).toHaveBeenCalledBefore(adapter.request);
    expect(adapter.request).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["browser", { native: false }], ["guest / failed login", { accountId: null }],
    ["disabled", { enabled: false }], ["background", { foreground: false }],
    ["incomplete verification/onboarding/loading/modal/draft/payment", { safe: false }],
  ] as const)("never claims in %s", async (_, patch) => {
    const { controller, dependencies, adapter } = fixture();
    controller.update({ ...ready, ...patch }); await wait(9000);
    expect(dependencies.claim).not.toHaveBeenCalled(); expect(adapter.request).not.toHaveBeenCalled();
    if ("native" in patch && patch.native === false) expect(adapter.synchronize).not.toHaveBeenCalled();
  });

  it("does not reset the safe timer on repeated auth events and rerenders", async () => {
    const { controller, adapter } = fixture(); controller.update(ready); await wait(1000);
    for (let i = 0; i < 10; i++) controller.update({ ...ready });
    await wait(2000); expect(adapter.request).toHaveBeenCalledTimes(1);
    controller.update({ ...ready, screenKey: "roster" }); controller.interrupt();
    controller.update({ ...ready, foreground: false }); controller.update(ready); await wait(60_000);
    expect(adapter.request).toHaveBeenCalledTimes(1);
  });

  it.each(["modal", "onboarding", "active draft", "deep-linked player card"])("defers for %s and restarts three seconds after closure", async () => {
    const { controller, adapter } = fixture(); controller.update(ready); await wait(2000);
    controller.update({ ...ready, safe: false }); await wait(6000); expect(adapter.request).not.toHaveBeenCalled();
    controller.update(ready); await wait(2999); expect(adapter.request).not.toHaveBeenCalled();
    await wait(1); expect(adapter.request).toHaveBeenCalledTimes(1);
  });

  it("user interaction restarts the unobstructed interval", async () => {
    const { controller, adapter } = fixture(); controller.update(ready); await wait(2500); controller.interrupt();
    await wait(2999); expect(adapter.request).not.toHaveBeenCalled(); await wait(1); expect(adapter.request).toHaveBeenCalledTimes(1);
  });

  it("checks native readiness before any backend claim", async () => {
    const { controller, dependencies, adapter } = fixture(); adapter.synchronize.mockResolvedValue({ ready: false, appVersion: "1", appBuild: "1" });
    controller.update(ready); await wait(); expect(dependencies.state).not.toHaveBeenCalled();
    expect(dependencies.claim).not.toHaveBeenCalled();
  });

  it.each(["dismissal", "Apple suppression", "native failure"])("consumption survives %s, remount, update and reinstall", async (outcome) => {
    const { controller, adapter, dependencies, consumed } = fixture();
    if (outcome === "native failure") adapter.request.mockRejectedValue(new Error("native unavailable"));
    else adapter.request.mockResolvedValue({ invoked: false });
    controller.update(ready); await wait(); controller.dispose();
    const next = fixture({ consumed: (id) => consumed.has(id) }); next.controller.update(ready); await wait();
    expect(adapter.request).toHaveBeenCalledTimes(1); expect(next.dependencies.claim).not.toHaveBeenCalled();
    // Reinstall loses every local cache. The server state still prevents it.
    const reinstall = fixture({ state: vi.fn().mockResolvedValue(grant) }); reinstall.controller.update(ready); await wait();
    expect(reinstall.dependencies.claim).not.toHaveBeenCalled(); expect(reinstall.adapter.request).not.toHaveBeenCalled();
    expect(dependencies.remember).toHaveBeenCalledWith(11);
  });

  it("cancels a pending old account on switch and independently qualifies the next", async () => {
    const { controller, dependencies, adapter } = fixture(); controller.update(ready); await wait(1000);
    dependencies.state.mockResolvedValue({ ...state, account_id: 22 }); dependencies.claim.mockResolvedValue({ ...grant, account_id: 22 });
    controller.update({ ...ready, accountId: 22 }); await wait(2999); expect(adapter.request).not.toHaveBeenCalled();
    await wait(1); expect(dependencies.claim).toHaveBeenCalledWith(22, "1.0", "123", expect.any(AbortSignal));
    expect(adapter.request).toHaveBeenCalledWith(expect.objectContaining({ accountId: "22" }));
  });

  it.each([{ accountId: null }, { accountId: 22 }, { foreground: false }, { safe: false }, { enabled: false }])("never invokes stale grant after context changes: %j", async (patch) => {
    const pending = deferred<ReviewClaim>(); const { controller, dependencies, adapter } = fixture();
    dependencies.claim.mockReturnValue(pending.promise); controller.update(ready); await wait();
    controller.update({ ...ready, ...patch }); pending.resolve(grant); await wait(0);
    expect(dependencies.remember).toHaveBeenCalledWith(11); expect(adapter.request).not.toHaveBeenCalled();
  });

  it("does not claim if the confirmed backend account differs from restored cache", async () => {
    const { controller, dependencies } = fixture(); dependencies.state.mockResolvedValue({ ...state, account_id: 22 });
    controller.update(ready); await wait(); expect(dependencies.claim).not.toHaveBeenCalled();
  });

  it("bounded offline retries require a later safe event and never bypass a claim", async () => {
    const { controller, dependencies, adapter } = fixture(); dependencies.state.mockRejectedValue(new Error("offline"));
    controller.update(ready); await wait(); await wait(60_000); expect(dependencies.state).toHaveBeenCalledTimes(1);
    controller.update({ ...ready, foreground: false }); controller.update(ready); await wait();
    expect(dependencies.state).toHaveBeenCalledTimes(2); await wait(60_000); controller.interrupt(); await wait();
    expect(dependencies.state).toHaveBeenCalledTimes(2); expect(adapter.request).not.toHaveBeenCalled();
  });

  it("recovers an offline eligibility read at a later safe opportunity", async () => {
    const { controller, dependencies, adapter } = fixture(); dependencies.state.mockRejectedValueOnce(new Error("offline"));
    controller.update(ready); await wait(); await wait(30_000); controller.interrupt(); await wait();
    expect(adapter.request).toHaveBeenCalledTimes(1);
  });

  it.each([true, false])("lost claim response only reconciles state, never replays authorization (committed=%s)", async (committed) => {
    const { controller, dependencies, adapter } = fixture(); dependencies.claim.mockRejectedValue(new Error("response lost"));
    controller.update(ready); await wait(); await wait(30_000);
    dependencies.state.mockResolvedValue(committed ? grant : state); controller.interrupt(); await wait();
    expect(dependencies.state).toHaveBeenCalledTimes(2); expect(dependencies.claim).toHaveBeenCalledTimes(1);
    expect(adapter.request).not.toHaveBeenCalled();
  });

  it("two devices only invoke for the unique granted server claim", async () => {
    let claimed = false;
    const claim = vi.fn(async () => { if (claimed) return { ...grant, authorization: "already_claimed" as const }; claimed = true; return grant; });
    const first = fixture({ claim }); const second = fixture({ claim });
    first.controller.update(ready); second.controller.update(ready); await wait();
    expect(first.adapter.request.mock.calls.length + second.adapter.request.mock.calls.length).toBe(1);
  });

  it("flag changes cancel pending work and never reset a consumed account", async () => {
    const { controller, adapter } = fixture(); controller.update(ready); await wait(2000);
    controller.update({ ...ready, enabled: false }); await wait(); expect(adapter.request).not.toHaveBeenCalled();
    controller.update(ready); await wait(); controller.update({ ...ready, enabled: false }); controller.update(ready); await wait();
    expect(adapter.request).toHaveBeenCalledTimes(1);
  });

  it("backend kill switch denies a client with stale runtime capabilities", async () => {
    const { controller, dependencies, adapter } = fixture(); dependencies.state.mockResolvedValue({ ...state, enabled: false });
    controller.update(ready); await wait(); expect(dependencies.claim).not.toHaveBeenCalled(); expect(adapter.request).not.toHaveBeenCalled();
  });

  it("server disabling after the committed grant cancels native presentation", async () => {
    const { controller, dependencies, adapter } = fixture();
    dependencies.state.mockResolvedValueOnce(state).mockResolvedValue({ ...grant, enabled: false });
    controller.update(ready); await wait();
    expect(dependencies.remember).toHaveBeenCalledWith(11); expect(adapter.request).not.toHaveBeenCalled();
  });

  it("failed verification or final session confirmation never invokes", async () => {
    const { controller, dependencies, adapter } = fixture();
    dependencies.state.mockResolvedValueOnce(state).mockRejectedValue(new Error("authentication revoked"));
    controller.update(ready); await wait(); expect(adapter.request).not.toHaveBeenCalled();
    expect(dependencies.remember).toHaveBeenCalledWith(11);
  });

  it("unmount cancels timers and revokes native context", async () => {
    const { controller, dependencies, adapter } = fixture(); controller.update(ready); controller.dispose(); await wait();
    expect(dependencies.claim).not.toHaveBeenCalled(); expect(adapter.synchronize).toHaveBeenLastCalledWith(expect.objectContaining({ safe: false }));
  });

  it("native readiness lost after a committed claim consumes without invoking", async () => {
    const { controller, dependencies, adapter } = fixture(); let safeCalls = 0;
    adapter.synchronize.mockImplementation(async (context) => ({ ready: context.safe && ++safeCalls === 1, appVersion: "1", appBuild: "1" }));
    controller.update(ready); await wait(); expect(dependencies.remember).toHaveBeenCalledWith(11); expect(adapter.request).not.toHaveBeenCalled();
  });
});
