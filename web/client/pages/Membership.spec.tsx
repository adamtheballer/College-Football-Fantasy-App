// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Membership } from "@/lib/membership";
import MembershipPage from "./Membership";
import { MembershipGate } from "@/components/MembershipGate";
import { matchupRefreshInterval } from "@/hooks/use-leagues";
import type { LeagueMatchupTabResponse } from "@/types/league";

const state = vi.hoisted(() => ({
  data: undefined as Membership | undefined,
  native: false,
  refresh: vi.fn(),
  sync: vi.fn(),
  verifyApple: vi.fn(),
  checkout: vi.fn(),
  portal: vi.fn(),
  choose: vi.fn(),
  product: vi.fn(),
  purchase: vi.fn(),
  restore: vi.fn(),
  finish: vi.fn(),
  manage: vi.fn(),
}));
vi.mock("@/hooks/use-membership", () => ({
  useMembership: () => ({
    enabled: true,
    data: state.data,
    loading: false,
    error: null,
    refresh: state.refresh,
  }),
}));
vi.mock("@/lib/membership", () => ({
  membershipApi: {
    sync: state.sync,
    verifyApple: state.verifyApple,
    checkout: state.checkout,
    portal: state.portal,
    chooseFreeLeagues: state.choose,
  },
}));
vi.mock("@/lib/native-membership", () => ({
  isNativeMembership: () => state.native,
  nativeMembership: {
    product: state.product,
    purchase: state.purchase,
    restore: state.restore,
    finish: state.finish,
    manage: state.manage,
  },
}));

function free(): Membership {
  return {
    plan: "free",
    active: false,
    enforcement_active: true,
    launch_at: "2027-08-01T00:00:00Z",
    amount_cents: 1000,
    currency: "usd",
    interval: "year",
    expires_at: null,
    source: null,
    cancel_at_period_end: false,
    league_limit: 2,
    league_count: 0,
    free_leagues: [],
    free_league_choice_locked: false,
    features: {
      unlimited_leagues: false,
      dynasty: false,
      player_pictures: false,
      weekly_challenges: false,
      live_refresh_seconds: 180,
    },
    web_checkout_ready: false,
    apple_purchase_ready: false,
    apple_product_id: "pro.annual",
    apple_account_token: "account-token",
    has_stripe_customer: false,
  };
}
const mount = (route = "/membership", children = <MembershipPage />) =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
    </QueryClientProvider>,
  );
beforeEach(() => {
  vi.clearAllMocks();
  state.data = free();
  state.native = false;
  state.refresh.mockResolvedValue(undefined);
  state.sync.mockResolvedValue(free());
  state.finish.mockResolvedValue(undefined);
  state.verifyApple.mockResolvedValue({ ...free(), active: true });
  state.product.mockResolvedValue({
    displayPrice: "$10.00",
    displayName: "Pro annual",
  });
});
afterEach(cleanup);

it("keeps current-season access and purchase controls disabled before launch", () => {
  state.data = { ...free(), enforcement_active: false, league_limit: null };
  mount();
  expect(
    screen.getByText(/Current-season access stays unchanged/),
  ).toBeTruthy();
  expect(
    (
      screen.getByRole("button", {
        name: "Subscribe · $10/year",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
it("never grants Pro from a checkout redirect or failed reconciliation", async () => {
  state.sync.mockRejectedValue(new Error("offline"));
  mount("/membership?checkout=complete");
  await screen.findByText(/Payment confirmation is pending/);
  expect(screen.getByText("Your plan: Free")).toBeTruthy();
  expect(state.refresh).not.toHaveBeenCalled();
});
it.each(["cancelled", "pending"])(
  "preserves Free after a native %s purchase",
  async (status) => {
    state.native = true;
    state.data = { ...free(), apple_purchase_ready: true };
    state.purchase.mockResolvedValue({ status });
    mount();
    const buy = await screen.findByRole("button", {
      name: "Subscribe · $10.00/year",
    });
    fireEvent.click(buy);
    await waitFor(() => expect(state.purchase).toHaveBeenCalled());
    await screen.findByText(
      status === "pending"
        ? /pending App Store approval/
        : /Purchase cancelled/,
    );
    expect(state.verifyApple).not.toHaveBeenCalled();
    expect(state.finish).not.toHaveBeenCalled();
    expect(screen.getByText("Your plan: Free")).toBeTruthy();
  },
);
it("finishes native receipts only after server verification succeeds", async () => {
  state.native = true;
  state.data = { ...free(), apple_purchase_ready: true };
  state.purchase.mockResolvedValue({
    status: "purchased",
    transaction: {
      signedTransaction: "signed-jws",
      transactionId: "tx1",
      appAccountToken: "account-token",
    },
  });
  state.verifyApple.mockRejectedValue(
    new Error("Ownership verification failed"),
  );
  mount();
  fireEvent.click(
    await screen.findByRole("button", { name: "Subscribe · $10.00/year" }),
  );
  await screen.findByRole("alert");
  expect(state.finish).not.toHaveBeenCalled();
  state.verifyApple.mockResolvedValue({ ...free(), active: true });
  fireEvent.click(
    screen.getByRole("button", { name: "Subscribe · $10.00/year" }),
  );
  await screen.findByText("Your Pro membership is active.");
  expect(state.finish).toHaveBeenCalledWith({ transactionId: "tx1" });
  expect(state.verifyApple.mock.invocationCallOrder.at(-1)!).toBeLessThan(
    state.finish.mock.invocationCallOrder[0],
  );
});
it("shows an honest empty restore result and never opens web checkout on iPhone", async () => {
  state.native = true;
  state.restore.mockResolvedValue({ transactions: [] });
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Restore purchases" }));
  await screen.findByText(/No matching App Store purchases/);
  expect(state.checkout).not.toHaveBeenCalled();
  expect(state.verifyApple).not.toHaveBeenCalled();
});
it("blocks native purchase when the actual store price cannot load", async () => {
  state.native = true;
  state.data = { ...free(), apple_purchase_ready: true };
  state.product.mockRejectedValue(new Error("store offline"));
  mount();
  await screen.findByText(/App Store price is unavailable/);
  expect(
    (screen.getByRole("button", { name: "Subscribe" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
});
it("gates challenge participation while preserving children before launch", () => {
  const result = mount(
    "/membership",
    <MembershipGate feature="weekly_challenges">
      <button>Submit challenge</button>
    </MembershipGate>,
  );
  expect(screen.queryByText("Submit challenge")).toBeNull();
  expect(screen.getByText("Pro membership required")).toBeTruthy();
  result.unmount();
  state.data = { ...free(), enforcement_active: false };
  mount(
    "/membership",
    <MembershipGate feature="weekly_challenges">
      <button>Submit challenge</button>
    </MembershipGate>,
  );
  expect(screen.getByRole("button", { name: "Submit challenge" })).toBeTruthy();
});
it("uses the server's viewer cadence without fabricating provider freshness", () => {
  const live = {
    status: "live",
    viewer_refresh_seconds: 15,
    next_refresh_at: "2099-01-01T00:00:00Z",
  } as LeagueMatchupTabResponse;
  expect(matchupRefreshInterval(live)).toBe(15_000);
  expect(matchupRefreshInterval({ ...live, viewer_refresh_seconds: 180 })).toBe(
    180_000,
  );
});
