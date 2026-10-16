// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  update: vi.fn(),
  state: vi.fn(),
  claim: vi.fn(),
  request: vi.fn(),
  synchronize: vi.fn(),
  consumed: new Set<number>(),
  overlapping: [] as boolean[],
}));
vi.mock("@/lib/api", () => ({ apiReleaseNoticeClaim: mocks.update }));
vi.mock("@/components/RuntimeCompatibilityGate", () => ({
  useRuntimeCapabilities: () => ({ ios_app_review_enabled: true }),
}));
vi.mock("@/lib/native-app-review", () => ({
  isNativeIosReviewRuntime: () => true,
  nativeReviewAdapter: {
    synchronize: mocks.synchronize,
    request: mocks.request,
  },
  observeNativeReviewAvailability: async () => ({ remove: async () => {} }),
  readReviewState: mocks.state,
  claimReview: mocks.claim,
  reviewConsumed: (id: number) => mocks.consumed.has(id),
  rememberReviewClaim: (id: number) => mocks.consumed.add(id),
}));

import { AppUpdateExperience } from "./AppUpdateExperience";

let nextAccount = 8000;
const flush = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  localStorage.clear();
  mocks.consumed.clear();
  mocks.overlapping.length = 0;
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  vi.spyOn(HTMLElement.prototype, "getClientRects").mockImplementation(
    function () {
      const rects =
        this.style.display === "none" ? [] : [new DOMRect(0, 0, 100, 100)];
      return Object.assign(rects, { item: (index: number) => rects[index] });
    },
  );
  document.body.innerHTML =
    '<main><div data-launch-notice-ready="true"><h1>Home</h1><div aria-busy="true">Loading your league matchups</div><div aria-busy="true">Loading your alerts</div></div></main>';
  mocks.update.mockImplementation(async (id: number) => ({
    account_id: id,
    release_key: "1.03",
    authorization: "granted",
    claimed_at: "2026-10-16T00:00:00Z",
  }));
  mocks.state.mockImplementation(async (id: number) => ({
    account_id: id,
    enabled: true,
    review_request_claimed_at: null,
  }));
  mocks.claim.mockImplementation(async (id: number) => ({
    account_id: id,
    enabled: true,
    authorization: "granted",
    review_request_claimed_at: "2026-10-16T00:00:00Z",
  }));
  mocks.synchronize.mockResolvedValue({
    ready: true,
    appVersion: "1.0.3",
    appBuild: "41",
  });
  mocks.request.mockImplementation(async () => {
    mocks.overlapping.push(document.querySelector('[role="dialog"]') !== null);
    return { invoked: true };
  });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("native launch popup sequence", () => {
  it("shows the update on restored Home, immediately requests review after closure, and never repeats for that account", async () => {
    const p = {
      accountId: ++nextAccount,
      managerName: "Launch QA",
      sessionReady: true,
      onboarding: false,
      pathname: "/",
      screenKey: "home",
    };
    const view = render(<AppUpdateExperience {...p} sessionReady={false} />);
    await flush();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.claim).not.toHaveBeenCalled();
    view.rerender(<AppUpdateExperience {...p} />);
    await flush();
    expect(screen.getByRole("dialog", { name: "1.03 Update" })).toBeTruthy();
    expect(document.querySelectorAll('[aria-busy="true"]')).toHaveLength(2);
    expect(mocks.claim).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Skip update" }));
    await flush();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mocks.request).toHaveBeenCalledTimes(1);
    expect(mocks.overlapping).toEqual([false]);
    view.rerender(
      <AppUpdateExperience {...p} accountId={null} sessionReady={false} />,
    );
    view.rerender(<AppUpdateExperience {...p} screenKey="login-again" />);
    await flush();
    view.unmount();
    render(<AppUpdateExperience {...p} screenKey="reopened" />);
    await flush();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mocks.update).toHaveBeenCalledTimes(1);
    expect(mocks.claim).toHaveBeenCalledTimes(1);
    expect(mocks.request).toHaveBeenCalledTimes(1);
  });

  it("does not treat the route fallback or an entirely busy page as a ready Home screen", async () => {
    document.querySelector("main")!.setAttribute("aria-busy", "true");
    render(
      <AppUpdateExperience
        accountId={++nextAccount}
        managerName="QA"
        sessionReady
        onboarding={false}
        pathname="/"
        screenKey="loading"
      />,
    );
    await flush();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.claim).not.toHaveBeenCalled();
  });
});
