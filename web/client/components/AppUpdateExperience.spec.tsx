// @vitest-environment jsdom
import { StrictMode } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ claim: vi.fn(), review: vi.fn() }));
vi.mock("@/lib/api", () => ({ apiReleaseNoticeClaim: mocks.claim }));
vi.mock("@/components/AppReviewCoordinator", async (original) => ({
  ...(await original<typeof import("./AppReviewCoordinator")>()),
  AppReviewCoordinator: (props: unknown) => {
    mocks.review(props);
    return null;
  },
}));
import { AppUpdateExperience, UPDATE_STEPS } from "./AppUpdateExperience";
import { setPendingGuide, clearPendingGuide } from "@/lib/onboarding";
import { withReviewPresentationBlocker } from "@/lib/review-presentation";

let nextId = 100;
const props = () => ({
  accountId: ++nextId,
  managerName: "Alex",
  sessionReady: true,
  onboarding: false,
  pathname: "/",
  screenKey: "home",
});
const grant = (id: number) => ({
  account_id: id,
  release_key: "1.03",
  authorization: "granted",
  claimed_at: "2026-10-15T00:00:00Z",
});
const dialog = () => screen.findByRole("dialog", { name: "1.03 Update" });
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mocks.claim.mockImplementation((id: number) => Promise.resolve(grant(id)));
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  vi.spyOn(HTMLElement.prototype, "getClientRects").mockImplementation(
    function () {
      const rects =
        this.style.display === "none" ? [] : [new DOMRect(0, 0, 100, 100)];
      return Object.assign(rects, { item: (index: number) => rects[index] });
    },
  );
  document.body.innerHTML = "<main><h1>Your fantasy dashboard</h1></main>";
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("1.03 update walkthrough", () => {
  it("opens on the authenticated Home shell while background cards are still loading", async () => {
    document.body.innerHTML = '<main><div data-launch-notice-ready="true"><h1>Your fantasy dashboard</h1><div aria-busy="true">Loading your league matchups</div><div aria-busy="true">Loading your alerts</div></div></main>';
    const p = props();
    render(<AppUpdateExperience {...p} />);
    await dialog();
    expect(document.querySelectorAll('[aria-busy="true"]')).toHaveLength(2);
    expect(mocks.claim).toHaveBeenCalledTimes(1);
  });

  it("greets the manager, stays centered and reveals every update with Next/Back", async () => {
    render(<AppUpdateExperience {...props()} />);
    expect((await dialog()).className).toContain("top-[50%]");
    expect(screen.getByText("Hi, Alex.")).toBeTruthy();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Next" }),
    );
    expect(screen.queryByText("Weekly Challenges")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Weekly Challenges")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("Hi, Alex.")).toBeTruthy();
    for (const step of UPDATE_STEPS.slice(1)) {
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      expect(screen.getByRole("heading", { name: step.title })).toBeTruthy();
    }
    expect(screen.getByText("10 of 10")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(mocks.claim).toHaveBeenCalledTimes(1);
    expect(mocks.review.mock.lastCall?.[0].onboarding).toBe(false);
  });

  it("dismissal survives remount, logout/login and route refresh for the same account", async () => {
    const p = props();
    const view = render(<AppUpdateExperience {...p} />);
    await dialog();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    view.rerender(
      <AppUpdateExperience {...p} accountId={null} sessionReady={false} />,
    );
    view.rerender(<AppUpdateExperience {...p} screenKey="restored" />);
    await act(async () => {});
    expect(screen.queryByRole("dialog")).toBeNull();
    view.unmount();
    render(<AppUpdateExperience {...p} />);
    await act(async () => {});
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mocks.claim).toHaveBeenCalledTimes(1);
  });

  it("does not reopen an unfinished popup after logout and re-login", async () => {
    const p = props();
    const view = render(<AppUpdateExperience {...p} />);
    await dialog();
    view.rerender(
      <AppUpdateExperience {...p} accountId={null} sessionReady={false} />,
    );
    view.rerender(<AppUpdateExperience {...p} />);
    await act(async () => {});
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("StrictMode coalesces the durable claim and admits one presentation", async () => {
    render(
      <StrictMode>
        <AppUpdateExperience {...props()} />
      </StrictMode>,
    );
    await dialog();
    expect(mocks.claim).toHaveBeenCalledTimes(1);
  });

  it("waits for restored auth, onboarding and the pending guide before consuming", async () => {
    const p = props();
    setPendingGuide(p.accountId);
    const view = render(<AppUpdateExperience {...p} sessionReady={false} />);
    view.rerender(<AppUpdateExperience {...p} onboarding />);
    await act(async () => {});
    expect(mocks.claim).not.toHaveBeenCalled();
    view.rerender(<AppUpdateExperience {...p} />);
    await act(async () => {});
    expect(mocks.claim).not.toHaveBeenCalled();
    clearPendingGuide(p.accountId);
    view.rerender(<AppUpdateExperience {...p} screenKey="guide-finished" />);
    await dialog();
    expect(mocks.review.mock.lastCall?.[0].onboarding).toBe(true);
  });

  it("waits on unsafe routes and while another modal is present", async () => {
    const p = props();
    const view = render(<AppUpdateExperience {...p} pathname="/draft/room" />);
    await act(async () => {});
    expect(mocks.claim).not.toHaveBeenCalled();
    const modal = document.createElement("div");
    modal.setAttribute("role", "dialog");
    modal.textContent = "Player card";
    document.body.append(modal);
    view.rerender(<AppUpdateExperience {...p} />);
    await act(async () => {});
    expect(mocks.claim).not.toHaveBeenCalled();
    await act(async () => {
      modal.remove();
    });
    await dialog();
  });

  it("defers a grant if a modal opens while its server request is pending", async () => {
    const p = props();
    let resolve!: (value: ReturnType<typeof grant>) => void;
    mocks.claim.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    render(<AppUpdateExperience {...p} />);
    await waitFor(() => expect(mocks.claim).toHaveBeenCalledTimes(1));
    const modal = document.createElement("div");
    modal.setAttribute("role", "dialog");
    modal.textContent = "Other screen";
    document.body.append(modal);
    await act(async () => {
      resolve(grant(p.accountId));
    });
    expect(screen.queryByRole("dialog", { name: "1.03 Update" })).toBeNull();
    await act(async () => {
      modal.remove();
    });
    await dialog();
  });

  it("defers during a native permission request", async () => {
    const p = props();
    let done!: () => void;
    const permission = withReviewPresentationBlocker(
      () =>
        new Promise<void>((resolve) => {
          done = resolve;
        }),
    );
    render(<AppUpdateExperience {...p} />);
    await act(async () => {});
    expect(mocks.claim).not.toHaveBeenCalled();
    await act(async () => {
      done();
      await permission;
    });
    await dialog();
  });

  it("ignores a stale account response and greets the new signed-in manager", async () => {
    const a = props(),
      b = props();
    let resolve!: (value: ReturnType<typeof grant>) => void;
    mocks.claim.mockImplementation((id) =>
      id === a.accountId
        ? new Promise((done) => {
            resolve = done;
          })
        : Promise.resolve(grant(id)),
    );
    const view = render(<AppUpdateExperience {...a} />);
    await waitFor(() => expect(mocks.claim).toHaveBeenCalledWith(a.accountId));
    view.rerender(<AppUpdateExperience {...b} managerName="Morgan" />);
    await dialog();
    await act(async () => {
      resolve(grant(a.accountId));
    });
    expect(screen.getByText("Hi, Morgan.")).toBeTruthy();
    expect(screen.queryByText("Hi, Alex.")).toBeNull();
  });

  it("server receipts prevent repeat display on a fresh device", async () => {
    const p = props();
    mocks.claim.mockResolvedValue({
      ...grant(p.accountId),
      authorization: "already_seen",
    });
    render(<AppUpdateExperience {...p} />);
    await waitFor(() =>
      expect(mocks.review.mock.lastCall?.[0].onboarding).toBe(false),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("failed claims show no false popup and do not consume App Review eligibility", async () => {
    mocks.claim.mockRejectedValue(new Error("offline"));
    render(<AppUpdateExperience {...props()} />);
    await waitFor(() =>
      expect(mocks.review.mock.lastCall?.[0].onboarding).toBe(false),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("storage errors still keep this session once-only", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const p = props();
    const view = render(<AppUpdateExperience {...p} />);
    await dialog();
    fireEvent.click(screen.getByRole("button", { name: "Skip update" }));
    view.unmount();
    render(<AppUpdateExperience {...p} />);
    await act(async () => {});
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mocks.claim).toHaveBeenCalledTimes(1);
  });
});
