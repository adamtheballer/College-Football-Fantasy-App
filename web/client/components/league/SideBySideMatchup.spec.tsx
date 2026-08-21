// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LeagueMatchupTeam, LeagueRosterPlayer } from "@/types/league";

vi.mock("@/components/league/RosterSlotTable", () => ({
  RosterSlotTable: () => <div data-testid="desktop-roster-table" />,
  formatRosterPointValue: (player: LeagueRosterPlayer) => {
    const value = player.current_fantasy_points ?? player.live_points ?? player.projected_points;
    return typeof value === "number" ? value.toFixed(1) : "—";
  },
  liveProjectionDetail: (player: LeagueRosterPlayer) => player.live_projected_final_points ? `Proj ${player.live_projected_final_points.toFixed(1)}` : null,
}));

vi.mock("@/components/player/PlayerCardModal", () => ({
  PlayerCardModal: ({ player, onClose }: { player: { name: string }; onClose: () => void }) => (
    <div role="dialog">
      <span>{player.name} matchup player card</span>
      <button type="button" onClick={onClose}>Close player card</button>
    </div>
  ),
}));

vi.mock("@/hooks/use-players", () => ({
  usePlayerCard: () => ({ data: undefined, isError: false, isLoading: false, refetch: vi.fn() }),
}));

import { compactMatchupPlayerName, SideBySideMatchup } from "./SideBySideMatchup";

afterEach(cleanup);

const makePlayer = (id: number, name: string, slot: string, projection: number): LeagueRosterPlayer => ({
  id,
  fantasy_team_id: id < 10 ? 1 : 2,
  fantasy_team_name: id < 10 ? "Adam's Team" : "Guy's Team",
  player_id: id,
  player_name: name,
  school: id < 10 ? "Ohio State" : "Texas",
  position: slot === "QB" ? "QB" : "RB",
  slot,
  slot_index: 1,
  opponent: "Week One Opponent",
  game_location: id < 10 ? "home" : "away",
  game_start_at: "2026-08-29T16:00:00Z",
  projected_points: projection,
  weekly_projected_fantasy_points: projection,
});

const myTeam: LeagueMatchupTeam = {
  fantasy_team_id: 1,
  fantasy_team_name: "Adam's Team",
  record: "0-0-0",
  projected_total: 119.5,
  roster: [makePlayer(1, "Long Name Quarterback", "QB", 24.1), makePlayer(2, "Bench Running Back", "BENCH", 9.3)],
};

const opponentTeam: LeagueMatchupTeam = {
  fantasy_team_id: 2,
  fantasy_team_name: "Guy's Team",
  record: "0-0-0",
  projected_total: 115.2,
  roster: [makePlayer(10, "Opponent Quarterback", "QB", 22.7), makePlayer(11, "Opponent Bench", "BENCH", 8.8)],
};

describe("SideBySideMatchup", () => {
  it("renders a compact mobile starting lineup with both teams, slot, and weekly projections in each row", () => {
    const { container } = render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} />);

    expect(screen.getByTestId("mobile-starting-lineup")).toBeTruthy();
    expect(screen.getByTestId("mobile-starting-lineup").querySelectorAll("[data-mobile-matchup-row]")).toHaveLength(1);
    expect(screen.getByText("L. Name Quarterback")).toBeTruthy();
    expect(screen.getByText("O. Quarterback")).toBeTruthy();
    expect(screen.getByText("QB")).toBeTruthy();
    expect(screen.getByText("24.1")).toBeTruthy();
    expect(screen.getByText("22.7")).toBeTruthy();
    const starters = screen.getByTestId("mobile-starting-lineup");
    expect(starters.textContent).toContain("Week One Opponent @ Ohio State");
    expect(starters.textContent).toContain("Texas @ Week One Opponent");
    expect(starters.textContent).toMatch(/Sat,? Aug 29.*12:00 PM|Sat,? Aug 29.*4:00 PM|Sat,? Aug 29.*11:00 AM/);
    expect(starters.querySelectorAll("[data-player-game-matchup]")).toHaveLength(2);
    expect(starters.querySelectorAll("[data-player-game-time]")).toHaveLength(2);
    expect(starters.querySelector('[data-mobile-matchup-player="right"]')?.className).toContain(
      "grid-cols-[2.75rem_minmax(0,1fr)]",
    );
    expect(starters.querySelector('[data-mobile-matchup-player="right"]')?.className).toContain("text-left");
    expect(screen.getByText("22.7").parentElement?.className).toContain("text-cfb-text-primary");
    expect(starters.querySelector('[data-mobile-matchup-player="left"]')?.className).toContain(
      "grid-cols-[minmax(0,1fr)_2.75rem]",
    );
    expect(screen.getByText("24.1").parentElement?.className).toContain("text-cfb-text-primary");
    expect(starters.querySelector("[data-mobile-slot-rail]")).toBeTruthy();
    expect(starters.querySelector("[data-mobile-slot-column]")?.className).not.toContain("border-x");
  });

  it("opens the existing player card from either side of a mobile matchup row", () => {
    render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} leagueId={42} />);

    fireEvent.click(screen.getByRole("button", { name: "Open L. Name Quarterback player card" }));
    expect(screen.getByRole("dialog").textContent).toContain("Long Name Quarterback matchup player card");

    fireEvent.click(screen.getByRole("button", { name: "Close player card" }));
    fireEvent.click(screen.getByRole("button", { name: "Open O. Quarterback player card" }));
    expect(screen.getByRole("dialog").textContent).toContain("Opponent Quarterback matchup player card");
  });

  it("uses a first-name initial and preserves multi-word last names for compact matchup rows", () => {
    expect(compactMatchupPlayerName("Amon-Ra St. Brown")).toBe("A. St. Brown");
    expect(compactMatchupPlayerName("Cher")).toBe("Cher");
  });

  it("shows persisted player scores instead of projections once a matchup is live", () => {
    const liveMyTeam = {
      ...myTeam,
      roster: [{ ...myTeam.roster[0], live_points: 7.25, live_scoring_status: "live" }],
    };
    const liveOpponentTeam = {
      ...opponentTeam,
      roster: [{ ...opponentTeam.roster[0], live_points: 13, live_scoring_status: "live" }],
    };

    render(<SideBySideMatchup myTeam={liveMyTeam} opponentTeam={liveOpponentTeam} scoringStatus="live" />);

    expect(screen.getByText("7.3")).toBeTruthy();
    expect(screen.getByText("13.0")).toBeTruthy();
    expect(screen.queryByText("24.1")).toBeNull();
    expect(screen.queryByText("22.7")).toBeNull();
  });

  it("marks finalized player games with a compact lock in the mobile matchup", () => {
    const finalMyTeam = {
      ...myTeam,
      roster: [{ ...myTeam.roster[0], live_game_state: "final" as const, current_fantasy_points: 18.5 }],
    };

    render(<SideBySideMatchup myTeam={finalMyTeam} opponentTeam={opponentTeam} scoringStatus="final" />);

    expect(screen.getByLabelText("Game final")).toBeTruthy();
    expect(screen.getByText("18.5")).toBeTruthy();
  });

  it("keeps bench rows collapsed until a user chooses to inspect them", () => {
    const { container } = render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} />);

    expect(screen.getByText("Bench depth")).toBeTruthy();
    expect(screen.getByTestId("mobile-bench-lineup")).toBeTruthy();
    expect(container.querySelector("details")?.open).toBe(false);
  });
});
