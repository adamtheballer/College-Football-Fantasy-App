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

import { formatRosterPointValue, RosterSlotTable } from "./RosterSlotTable";

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

const projectedReceiver: LeagueRosterPlayer = {
  id: 9,
  league_id: 2,
  team_id: 5,
  fantasy_team_id: 5,
  fantasy_team_name: "Adam's Team",
  player_id: 99,
  player_name: "A Very Long Receiver Name That Must Stay Compact",
  school: "Ohio State",
  position: "WR",
  slot: "WR",
  slot_id: "team-5-WR-1",
  slot_index: 1,
  status: "ACTIVE",
  opponent: "Michigan",
  projected_points: 18.4,
  weekly_projected_fantasy_points: 18.4,
};

describe("RosterSlotTable", () => {
  it("renders an empty configured slot instead of removing its roster row", () => {
    render(<RosterSlotTable title="Starters" players={[emptyQuarterbackSlot]} />);

    expect(screen.getByText("QB")).toBeTruthy();
    expect(screen.getByText("N/A")).toBeTruthy();
    expect(screen.getByText("0.0")).toBeTruthy();
    expect(screen.queryByText("No roster players yet.")).toBeNull();
  });

  it("keeps mobile roster data in one compact row with a weekly projection", () => {
    const { container } = render(<RosterSlotTable title="Starters" players={[projectedReceiver]} />);

    expect(container.querySelectorAll("[data-roster-mobile-row]")).toHaveLength(1);
    expect(screen.getByText("A Very Long Receiver Name That Must Stay Compact")).toBeTruthy();
    expect(screen.getByText("Ohio State · vs Michigan")).toBeTruthy();
    expect(screen.getByText("18.4")).toBeTruthy();
  });

  it("uses persisted live points when the caller marks the table as live", () => {
    const liveReceiver = { ...projectedReceiver, live_points: 21.37, live_scoring_status: "live" };
    render(<RosterSlotTable title="Starters" players={[liveReceiver]} pointMode="live" />);

    expect(screen.getByText("21.4")).toBeTruthy();
    expect(screen.queryByText("18.4")).toBeNull();
    expect(formatRosterPointValue(liveReceiver, "live")).toBe("21.4");
  });
});
