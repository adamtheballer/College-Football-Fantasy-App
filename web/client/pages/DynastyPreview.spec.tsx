// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DynastyPreview from "./DynastyPreview";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "@/lib/api";
import { dynastyApi, type DynastyState } from "@/lib/dynasty";

vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: { id: 11 } }) }));
vi.mock("@/lib/dynasty", () => ({
  dynastyApi: {
    capability: vi.fn(),
    list: vi.fn(),
    detail: vi.fn(),
    pool: vi.fn(),
    create: vi.fn(),
    join: vi.fn(),
    start: vi.fn(),
    pick: vi.fn(),
    drop: vi.fn(),
    trade: vi.fn(),
    settle: vi.fn(),
    close: vi.fn(),
    rollover: vi.fn(),
    history: vi.fn(),
  },
}));
export const state: DynastyState = {
  team_count: 2,
  server_time: "2026-10-27T05:00:00Z",
  draft_picks: [],
  league_id: 1,
  name: "Future league",
  commissioner_user_id: 11,
  invite_code: "PREVIEW",
  startup_season: 2027,
  current_season: 2027,
  roster_limit: 8,
  startup_rounds: 2,
  freshman_rounds: 1,
  future_pick_years: 2,
  draft_kind: "startup",
  status: "drafting",
  pick_cursor: 0,
  order: [1, 2],
  next_pick_id: 5,
  teams: [
    { id: 1, name: "My franchise", owner_user_id: 11 },
    { id: 2, name: "Rivals", owner_user_id: 12 },
  ],
  rosters: [],
  picks: [
    {
      id: 5,
      season: 2027,
      round_number: 1,
      original_team_id: 1,
      owner_team_id: 1,
      overall_pick: 1,
      player_id: null,
    },
  ],
  trades: [],
  departures: [],
};
let cache: QueryClient;
function open() {
  cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <DynastyPreview />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(dynastyApi.capability).mockResolvedValue({
    enabled: true,
    earliest_season: 2027,
    preview: true,
  });
  vi.mocked(dynastyApi.list).mockResolvedValue({ data: [state] });
  vi.mocked(dynastyApi.detail).mockResolvedValue(state);
});
afterEach(() => {
  cleanup();
  cache?.clear();
});

describe("isolated dynasty preview", () => {
  it("enables the trade partner when another manager joins an open league", async () => {
    vi.mocked(dynastyApi.detail).mockResolvedValue({
      ...state,
      teams: state.teams.slice(0, 1),
    });
    open();
    await screen.findByRole("combobox", { name: "Trade partner" });
    await act(async () => {
      cache.setQueryData(["dynasty", 1], state);
    });
    await waitFor(() =>
      expect(
        (
          screen.getByRole("combobox", {
            name: "Trade partner",
          }) as HTMLSelectElement
        ).value,
      ).toBe("2"),
    );
  });
  it("honestly denies a disabled server without fetching league data", async () => {
    vi.mocked(dynastyApi.capability).mockRejectedValue(
      new ApiError(404, "not found"),
    );
    open();
    expect(
      await screen.findByText("This preview is disabled in this environment."),
    ).toBeTruthy();
    expect(dynastyApi.list).not.toHaveBeenCalled();
    expect(screen.queryByText("Create preview league")).toBeNull();
  });
  it("opens the existing draft room and has no alternate table or pick controls", async () => {
    open();
    const entry = await screen.findByRole("link", { name: "Enter draft room" });
    expect(entry.getAttribute("href")).toBe("/labs/dynasty/1/draft");
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("button", { name: /^Draft / })).toBeNull();
    expect(dynastyApi.pool).not.toHaveBeenCalled();
    expect(dynastyApi.pick).not.toHaveBeenCalled();
    expect(dynastyApi.start).not.toHaveBeenCalled();
  });
});
