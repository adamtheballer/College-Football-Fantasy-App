// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LeagueRosterPlayer } from "@/types/league";

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/hooks/use-players", () => ({
  usePlayerCard: () => ({ data: null, isLoading: false }),
}));

vi.mock("@/hooks/use-roster-actions", () => ({
  useDropRosterPlayer: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateLineup: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { RosterSlotTable } from "./RosterSlotTable";

afterEach(cleanup);

const emptyQuarterbackSlot: LeagueRosterPlayer = {
  id: null,
  league_id: 2,
  team_id: 5,
  fantasy_team_id: 5,
  fantasy_team_name: "Adam's Team",
  player_id: null,
  player_name: null,
  school: null,
  position: null,
  slot: "QB",
  slot_id: "team-5-QB-1",
  slot_index: 1,
  display_label: "QB",
  status: "EMPTY",
  opponent: null,
  projected_points: 0,
  weekly_projected_fantasy_points: 0,
};

describe("RosterSlotTable", () => {
  it("renders an empty configured slot instead of removing its roster row", () => {
    render(<RosterSlotTable title="Starters" players={[emptyQuarterbackSlot]} />);

    expect(screen.getByText("QB")).toBeTruthy();
    expect(screen.getByText("N/A")).toBeTruthy();
    expect(screen.getByText("0.0")).toBeTruthy();
    expect(screen.queryByText("No roster players yet.")).toBeNull();
  });
});
