// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DynastyPreview from "./DynastyPreview";
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
const state: DynastyState = {
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
      <DynastyPreview />
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
  vi.mocked(dynastyApi.pool).mockResolvedValue({
    total: 1,
    offset: 0,
    limit: 50,
    data: [
      {
        player_id: 77,
        name: "Reviewed prospect",
        school: "Arizona State",
        position: "RB",
        entry_season: 2027,
        source_url: "https://example.edu/roster",
        value: {
          policy_version: "dynasty_preview_v1",
          provisional: true,
          base_value: null,
          academic_class: "FR",
          class_factor: 1.2,
          age: null,
          age_factor: 1,
          estimate: null,
        },
      },
    ],
  });
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
  it("uses nullable age/value honestly and submits the on-clock pick once", async () => {
    vi.mocked(dynastyApi.pick).mockRejectedValue(
      new ApiError(409, "roster is full"),
    );
    open();
    expect(await screen.findByText("FR / Unknown")).toBeTruthy();
    expect(screen.getByText("Unrated")).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "Draft Reviewed prospect" }),
    );
    await waitFor(() => expect(dynastyApi.pick).toHaveBeenCalledWith(1, 5, 77));
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "roster is full",
    );
    expect(dynastyApi.pick).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Saved.")).toBeNull();
    expect(document.body.textContent).not.toContain("recruiting-class rights");
  });
  it("disables selection when another team owns the pick", async () => {
    vi.mocked(dynastyApi.detail).mockResolvedValue({
      ...state,
      picks: [{ ...state.picks[0], owner_team_id: 2 }],
    });
    open();
    const button = await screen.findByRole("button", {
      name: "Draft Reviewed prospect",
    });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button);
    expect(dynastyApi.pick).not.toHaveBeenCalled();
  });
  it("keeps API failure distinct from an empty reviewed player pool", async () => {
    vi.mocked(dynastyApi.pool).mockRejectedValue(
      new ApiError(503, "Catalog unavailable"),
    );
    open();
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Catalog unavailable Retry players",
    );
    expect(
      screen.queryByText(
        "No reviewed eligible players are available for this draft.",
      ),
    ).toBeNull();
  });
});
