// @vitest-environment jsdom
import { StrictMode } from "react";
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppReviewCoordinator, isReviewSafeRoute, reviewScreenIsUsable } from "./AppReviewCoordinator";
import { withReviewPresentationBlocker } from "@/lib/review-presentation";

const mocks = vi.hoisted(() => ({ native: true, enabled: true, state: vi.fn(), claim: vi.fn(), request: vi.fn(), synchronize: vi.fn(), observe: vi.fn(), remember: vi.fn(), consumed: vi.fn(), remove: vi.fn() }));
vi.mock("@/components/RuntimeCompatibilityGate", () => ({ useRuntimeCapabilities: () => ({ ios_app_review_enabled: mocks.enabled }) }));
vi.mock("@/lib/native-app-review", () => ({ isNativeIosReviewRuntime: () => mocks.native,
  nativeReviewAdapter: { synchronize: mocks.synchronize, request: mocks.request }, observeNativeReviewAvailability: mocks.observe,
  readReviewState: mocks.state, claimReview: mocks.claim, rememberReviewClaim: mocks.remember, reviewConsumed: mocks.consumed }));

const props = { accountId: 11, sessionReady: true, onboarding: false, pathname: "/", screenKey: "home" };
const tick = async (ms = 3000) => { await act(() => vi.advanceTimersByTimeAsync(ms)); };
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks(); localStorage.clear(); mocks.native = true; mocks.enabled = true;
  mocks.state.mockResolvedValue({ account_id: 11, enabled: true, review_request_claimed_at: null });
  mocks.claim.mockResolvedValue({ account_id: 11, enabled: true, review_request_claimed_at: "2026-10-13T00:00:00Z", authorization: "granted" });
  mocks.synchronize.mockResolvedValue({ ready: true, appVersion: "1", appBuild: "123" }); mocks.request.mockResolvedValue({ invoked: true });
  mocks.consumed.mockReturnValue(false); mocks.observe.mockResolvedValue({ remove: mocks.remove });
  vi.spyOn(HTMLElement.prototype, "getClientRects").mockImplementation(function () {
    const rects = this.style.display === "none" ? [] : [new DOMRect(0, 0, 100, 100)];
    return Object.assign(rects, { item: (index: number) => rects[index] });
  });
  document.body.innerHTML = "<main><h1>Your leagues</h1></main>";
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); document.body.innerHTML = ""; });

describe("Layout review integration", () => {
  it("browser visits install no native listeners or review network checks", async () => {
    mocks.native = false; render(<AppReviewCoordinator {...props} />); await tick();
    expect(mocks.observe).not.toHaveBeenCalled(); expect(mocks.state).not.toHaveBeenCalled(); expect(mocks.request).not.toHaveBeenCalled();
  });
  it("confirmed restored auth qualifies and StrictMode cleans duplicate listeners", async () => {
    const view = render(<StrictMode><AppReviewCoordinator {...props} sessionReady={false} /></StrictMode>);
    await tick(); expect(mocks.claim).not.toHaveBeenCalled();
    view.rerender(<StrictMode><AppReviewCoordinator {...props} /></StrictMode>); await tick();
    expect(mocks.claim).toHaveBeenCalledTimes(1); expect(mocks.request).toHaveBeenCalledTimes(1);
    view.unmount(); await tick(0); expect(mocks.remove).toHaveBeenCalledTimes(2);
  });
  it("new signup defers until onboarding actually closes", async () => {
    const view = render(<AppReviewCoordinator {...props} onboarding />); await tick(6000);
    expect(mocks.claim).not.toHaveBeenCalled(); view.rerender(<AppReviewCoordinator {...props} />); await tick();
    expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it("deep-link modal defers without navigation and resumes after DOM removal", async () => {
    const modal = document.createElement("div"); modal.setAttribute("role", "dialog"); modal.textContent = "Player card"; document.body.append(modal);
    render(<AppReviewCoordinator {...props} pathname="/league/13/matchup" />); await tick(); expect(mocks.state).not.toHaveBeenCalled();
    await act(async () => { modal.remove(); }); await tick(2999); expect(mocks.request).not.toHaveBeenCalled();
    await tick(1); expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it("opening a modal cancels an already scheduled timer", async () => {
    render(<AppReviewCoordinator {...props} />); await tick(2000);
    await act(async () => { const modal = document.createElement("div"); modal.setAttribute("aria-modal", "true"); document.body.append(modal); });
    await tick(6000); expect(mocks.claim).not.toHaveBeenCalled();
  });
  it("permission request blocks before native UI appears", async () => {
    render(<AppReviewCoordinator {...props} />); await tick(2000);
    let resolve!: () => void;
    const permission = new Promise<void>((done) => { resolve = done; });
    let work!: Promise<void>;
    await act(async () => { work = withReviewPresentationBlocker(() => permission); });
    await tick(5000); expect(mocks.claim).not.toHaveBeenCalled();
    await act(async () => { resolve(); await work; }); await tick(); expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it("native foreground lifecycle cancels and safely reschedules", async () => {
    render(<AppReviewCoordinator {...props} />); await tick(2000);
    const listener = mocks.observe.mock.calls[0][0]; await act(async () => { listener({ active: false }); });
    await tick(5000); expect(mocks.claim).not.toHaveBeenCalled();
    await act(async () => { listener({ active: true }); listener({ active: true }); }); await tick();
    expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it("turning off runtime capability cancels a pending timer", async () => {
    const view = render(<AppReviewCoordinator {...props} />); await tick(2000);
    mocks.enabled = false; view.rerender(<AppReviewCoordinator {...props} />); await tick(); expect(mocks.claim).not.toHaveBeenCalled();
  });
  it("loading, pending guide and focused forms are not usable opportunities", async () => {
    localStorage.setItem("cfb_pending_guide_11", "true"); render(<AppReviewCoordinator {...props} />); await tick();
    expect(mocks.state).not.toHaveBeenCalled();
    const main = document.querySelector("main")!; main.setAttribute("aria-busy", "true"); expect(reviewScreenIsUsable(document)).toBe(false);
    main.removeAttribute("aria-busy"); const input = document.createElement("input"); main.append(input); input.focus();
    expect(reviewScreenIsUsable(document)).toBe(false); input.blur(); expect(reviewScreenIsUsable(document)).toBe(true);
  });
  it.each(["/login", "/signup", "/reset-password", "/settings", "/draft", "/draft/mock/single-player", "/league/13/draft", "/payment", "/trade/13/44", "/saturday-pick-6", "/leagues/create"])("excludes conflicting route %s", (path) => {
    expect(isReviewSafeRoute(path)).toBe(false);
  });
});
