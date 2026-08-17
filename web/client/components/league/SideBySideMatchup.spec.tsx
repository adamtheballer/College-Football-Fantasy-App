// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LeagueMatchupTeam, LeagueRosterPlayer } from "@/types/league";

vi.mock("@/components/league/RosterSlotTable", () => ({
  RosterSlotTable: () => <div data-testid="desktop-roster-table" />,
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
    expect(starters.textContent).toMatch(/Sat.*12:00 PM|Sat.*4:00 PM|Sat.*11:00 AM/);
  });

  it("uses a first-name initial and preserves multi-word last names for compact matchup rows", () => {
    expect(compactMatchupPlayerName("Amon-Ra St. Brown")).toBe("A. St. Brown");
    expect(compactMatchupPlayerName("Cher")).toBe("Cher");
  });

  it("keeps bench rows collapsed until a user chooses to inspect them", () => {
    const { container } = render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} />);

    expect(screen.getByText("Bench depth")).toBeTruthy();
    expect(screen.getByTestId("mobile-bench-lineup")).toBeTruthy();
    expect(container.querySelector("details")?.open).toBe(false);
  });
});
