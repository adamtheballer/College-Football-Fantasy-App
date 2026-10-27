// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Draft from "./Draft";
import type { DraftDataSource } from "@/types/draft-data-source";
import type { DraftRoom } from "@/types/draft";
import { toDynastyDraftPlayer } from "@/hooks/use-dynasty-draft";
vi.mock("@/hooks/use-players", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/use-players")>()),
  usePlayerCard: () => ({ data: undefined }),
}));
const pick = vi.fn();
let cache: QueryClient;
beforeEach(() => {
  vi.resetAllMocks();
  cache = new QueryClient();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
  Element.prototype.scrollTo = vi.fn();
});
afterEach(() => {
  cleanup();
  cache.clear();
  vi.unstubAllGlobals();
});
const room: DraftRoom = {
  league_id: 9,
  draft_id: -92028,
  status: "on_clock",
  pick_timer_seconds: 0,
  roster_slots: { BENCH: 1 },
  roster_capacity: { BENCH: 8 },
  teams: [
    {
      id: 1,
      name: "Manager",
      owner_user_id: 11,
      owner_name: null,
      is_cpu: false,
    },
    {
      id: 2,
      name: "Rival",
      owner_user_id: 22,
      owner_name: null,
      is_cpu: false,
    },
  ],
  picks: [],
  current_pick: 1,
  current_round: 1,
  current_round_pick: 1,
  current_team_id: 1,
  current_team_name: "Manager",
  user_team_id: 1,
  can_make_pick: true,
  can_start_draft: false,
  pre_draft_starts_at: null,
  draft_starts_at: null,
  current_pick_started_at: null,
  current_pick_deadline: null,
  transition_ends_at: null,
  seconds_remaining: 0,
  draft_version: 1,
  pick_started_at: null,
  pick_expires_at: null,
  server_time: "2026-10-27T05:00:00Z",
};
function open(untimed: boolean, overrides: Partial<DraftRoom> = {}) {
  const source: DraftDataSource = {
    untimed,
    isolated: true,
    paths: () => ({
      home: "/labs/dynasty",
      lobby: "/labs/dynasty",
      roster: "/labs/dynasty",
    }),
    useLeague: () => ({
      data: { name: "Freshman league", max_teams: 2, members: [], draft: null },
    }),
    useRoom: () => ({
      data: { ...room, ...overrides },
      isLoading: false,
      error: null,
      failureCount: 0,
      isPaused: false,
      refetch: vi.fn(),
    }),
    usePick: () => ({ mutateAsync: pick, isPending: false, error: null }),
    useStart: () => ({ mutate: vi.fn(), isPending: false, error: null }),
    usePool: () => ({
      data: {
        total: 1,
        data: [
          toDynastyDraftPlayer({
            draft_rank: 1,
            player_id: 77,
            name: "Incoming freshman",
            position: "RB",
            school: "Arizona State",
            entry_season: 2028,
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
          }),
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
    }),
  };
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/labs/dynasty/9/draft"]}>
        <Routes>
          <Route
            path="/labs/dynasty/:leagueId/draft"
            element={<Draft source={source} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("uses the normal draft controls to submit an untimed freshman pick", async () => {
  open(true);
  expect(screen.getByRole("button", { name: "Roster" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Board" })).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Draft Incoming freshman" }),
  );
  await waitFor(() =>
    expect(pick).toHaveBeenCalledWith({
      playerId: 77,
      pickNumber: 1,
      draftVersion: 1,
    }),
  );
  expect(
    screen.queryByText("Time expired. Waiting for the confirmed auto-pick."),
  ).toBeNull();
});
it("preserves the timed draft expiry guard when no authoritative deadline exists", () => {
  open(false);
  const button = screen.getByRole("button", {
    name: "Draft Incoming freshman",
  });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(button);
  expect(pick).not.toHaveBeenCalled();
});

it("keeps every board cell when a manager owns two picks in one round", () => {
  open(true, { pick_owners: { 1: 1, 2: 1 } });
  fireEvent.click(screen.getByRole("button", { name: "Board" }));
  expect(screen.getByText("1.1")).toBeTruthy();
  expect(screen.getByText("1.2")).toBeTruthy();
});
