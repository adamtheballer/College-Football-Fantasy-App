// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dynastyApi, type DynastyState, type DynastyPool } from "@/lib/dynasty";
import {
  dynastyDraftSource,
  toDynastyDraftPlayer,
  toDynastyDraftRoom,
} from "./use-dynasty-draft";
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: { id: 11 } }) }));
vi.mock("@/lib/dynasty", () => ({
  dynastyApi: { detail: vi.fn(), pool: vi.fn(), pick: vi.fn(), start: vi.fn() },
}));

const state: DynastyState = {
  league_id: 9,
  name: "Freshman league",
  team_count: 2,
  commissioner_user_id: 11,
  server_time: "2026-10-27T05:00:00Z",
  invite_code: "LOCAL",
  startup_season: 2027,
  current_season: 2028,
  roster_limit: 8,
  startup_rounds: 2,
  freshman_rounds: 1,
  future_pick_years: 2,
  draft_kind: "freshman",
  status: "drafting",
  pick_cursor: 0,
  order: [1, 2],
  next_pick_id: 31,
  teams: [
    { id: 1, name: "Manager", owner_user_id: 11 },
    { id: 2, name: "Rival", owner_user_id: 22 },
  ],
  picks: [
    {
      id: 31,
      season: 2028,
      round_number: 1,
      overall_pick: 1,
      original_team_id: 1,
      owner_team_id: 1,
      player_id: null,
    },
  ],
  rosters: [
    {
      id: 5,
      player_id: 70,
      team_id: 1,
      name: "Retained junior",
      position: "RB",
      school: null,
      value: null,
    },
  ],
  trades: [],
  departures: [],
  draft_picks: [],
};
const prospect: DynastyPool["data"][number] = {
  draft_rank: 17,
  player_id: 77,
  name: "Incoming freshman",
  position: "RB",
  school: "Arizona State",
  entry_season: 2028,
  source_url: "https://example.edu/roster",
  value: {
    policy_version: "dynasty_preview_v1",
    provisional: true,
    academic_class: "FR",
    age: null,
    age_factor: 1,
    class_factor: 1.2,
    base_value: null,
    estimate: null,
  },
};
let cache: QueryClient;
beforeEach(() => {
  vi.resetAllMocks();
  cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  vi.mocked(dynastyApi.detail).mockResolvedValue(state);
  vi.mocked(dynastyApi.pool).mockResolvedValue({
    data: [prospect],
    total: 1,
    limit: 50,
    offset: 0,
  });
});
afterEach(() => {
  cleanup();
  cache.clear();
});
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={cache}>{children}</QueryClientProvider>;
}

describe("dynasty data for the unchanged draft screen", () => {
  it("adapts original-order picks to their current owner and retains roster capacity", () => {
    const room = toDynastyDraftRoom(
      { ...state, picks: [{ ...state.picks[0], owner_team_id: 2 }] },
      22,
    );
    expect(room.current_team_id).toBe(2);
    expect(room.pick_owners?.[1]).toBe(2);
    expect(room.can_make_pick).toBe(true);
    expect(room.roster_slots).toEqual({ BENCH: 1 });
    expect(room.roster_capacity).toEqual({ BENCH: 8 });
    expect(room.roster_entries?.[0].player_name).toBe("Retained junior");
    expect(room.picks).toEqual([]);
    expect(room.draft_id).not.toBe(
      toDynastyDraftRoom({ ...state, current_season: 2029 }, 22).draft_id,
    );
  });
  it("does not pass dynasty value off as a game rating or fabricate freshman projections", () => {
    const player = toDynastyDraftPlayer(prospect);
    expect(player.masterDraftRank).toBe(17);
    expect(player.playerClass).toBe("FR");
    expect(player.cfb27Overall).toBeUndefined();
    expect(player.draftProjectedPoints).toBeNull();
    expect(player.status).toBe("UNREPORTED");
  });
  it("loads the complete dynasty board through its paginated endpoint", async () => {
    vi.mocked(dynastyApi.pool).mockImplementation(async (_id, offset) => ({
      data: offset
        ? [{ ...prospect, player_id: 78, draft_rank: 18 }]
        : [prospect],
      total: 2,
      limit: 1,
      offset,
    }));
    const { result } = renderHook(
      () => dynastyDraftSource.usePool({ league_id: 9 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.data?.data.length).toBe(2));
    expect(dynastyApi.pool).toHaveBeenCalledWith(
      9,
      0,
      false,
      expect.any(AbortSignal),
    );
    expect(dynastyApi.pool).toHaveBeenCalledWith(
      9,
      1,
      false,
      expect.any(AbortSignal),
    );
    expect(result.current.data?.data.map((p) => p.masterDraftRank)).toEqual([
      17, 18,
    ]);
  });
  it("submits the asset on the clock once and prevents an old pick envelope", async () => {
    const next = {
      ...state,
      status: "complete" as const,
      pick_cursor: 1,
      next_pick_id: null,
      server_time: "2026-10-27T05:00:01Z",
    };
    vi.mocked(dynastyApi.pick).mockImplementation(async () => {
      vi.mocked(dynastyApi.detail).mockResolvedValue(next);
      return next;
    });
    const { result } = renderHook(
      () => ({
        room: dynastyDraftSource.useRoom(9),
        pick: dynastyDraftSource.usePick(9),
      }),
      { wrapper },
    );
    await waitFor(() =>
      expect(result.current.room.data?.can_make_pick).toBe(true),
    );
    await act(async () => {
      await result.current.pick.mutateAsync({
        playerId: 77,
        pickNumber: 1,
        draftVersion: 1,
      });
    });
    expect(dynastyApi.pick).toHaveBeenCalledTimes(1);
    expect(dynastyApi.pick).toHaveBeenCalledWith(9, 31, 77);
    await act(async () => {
      await expect(
        result.current.pick.mutateAsync({
          playerId: 78,
          pickNumber: 1,
          draftVersion: 1,
        }),
      ).rejects.toThrow("Draft state changed");
    });
    expect(dynastyApi.pick).toHaveBeenCalledTimes(1);
  });
  it("keeps unavailable data as an error instead of showing the regular player pool", async () => {
    vi.mocked(dynastyApi.pool).mockRejectedValue(
      new Error("Freshman catalog unavailable"),
    );
    const { result } = renderHook(
      () => dynastyDraftSource.usePool({ league_id: 9 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
