// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LeagueMatchupTeam, LeagueRosterPlayer } from "@/types/league";

vi.mock("@/components/league/RosterSlotTable", () => ({
  RosterSlotTable: ({ title }: { title: string }) => <div data-testid="desktop-roster-table">{title}</div>,
  formatRosterGameKickoff: (value?: string | null) => value ? "Sat, Aug 29 at 7:00 PM" : "Kickoff TBD",
  formatRosterPointValue: (player: LeagueRosterPlayer, pointMode: "projected" | "live") => {
    if (pointMode === "projected" && player.injury_status?.startsWith("OUT")) return "0.0";
    const kickoffStarted = Boolean(
      player.game_start_at && new Date(player.game_start_at).getTime() <= Date.now() && player.live_game_state !== "final" && player.live_game_state !== "post",
    );
    if (kickoffStarted) {
      const current = player.current_fantasy_points ?? player.live_points;
      return typeof current === "number" ? current.toFixed(1) : "0.0";
    }
    const value = player.current_fantasy_points ?? player.live_points ?? player.projected_points;
    return typeof value === "number" ? value.toFixed(1) : "—";
  },
  liveProjectionDetail: (player: LeagueRosterPlayer) => player.live_game_state === "final" || player.live_game_state === "post"
    ? "Final"
    : player.game_start_at && new Date(player.game_start_at).getTime() <= Date.now()
      ? `Proj ${(player.projected_points ?? 0).toFixed(1)}`
    : player.live_projected_final_points ? `Proj ${player.live_projected_final_points.toFixed(1)}` : null,
  finalPregameProjectionDetail: (player: LeagueRosterPlayer) => player.live_game_state === "final" || player.live_game_state === "post"
    ? `Proj ${(player.pregame_projected_points ?? player.projected_points ?? 0).toFixed(1)}`
    : null,
  liveGameStatusLabel: (player: LeagueRosterPlayer) => {
    const kickoffStarted = Boolean(player.game_start_at && new Date(player.game_start_at).getTime() <= Date.now());
    if (player.live_game_state !== "live" && !kickoffStarted) return null;
    const period = player.game_is_halftime ? "Halftime" : player.game_period && player.game_clock ? `Q${player.game_period} ${player.game_clock}` : "In progress";
    return [period, player.game_is_halftime ? null : player.game_down_distance, player.game_score].filter(Boolean).join(" · ");
  },
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
  game_start_at: new Date(Date.now() + 60 * 60 * 1_000).toISOString(),
  projected_points: projection,
  weekly_projected_fantasy_points: projection,
});

const myTeam: LeagueMatchupTeam = {
  fantasy_team_id: 1,
  fantasy_team_name: "Adam's Team",
  manager_name: "An1ski",
  record: "0-0-0",
  projected_total: 119.5,
  roster: [makePlayer(1, "Long Name Quarterback", "QB", 24.1), makePlayer(2, "Bench Running Back", "BENCH", 9.3)],
};

const opponentTeam: LeagueMatchupTeam = {
  fantasy_team_id: 2,
  fantasy_team_name: "Guy's Team",
  manager_name: "Mary",
  record: "0-0-0",
  projected_total: 115.2,
  roster: [makePlayer(10, "Opponent Quarterback", "QB", 22.7), makePlayer(11, "Opponent Bench", "BENCH", 8.8)],
};

describe("SideBySideMatchup", () => {
  it("renders a compact mobile starting lineup with both teams, slot, and weekly projections in each row", () => {
    render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} />);

    const starters = screen.getByTestId("mobile-starting-lineup");
    expect(starters.querySelectorAll("[data-mobile-matchup-row]")).toHaveLength(1);
    expect(within(starters).getByText("L. Name Quarterback")).toBeTruthy();
    expect(within(starters).getByText("O. Quarterback")).toBeTruthy();
    expect(within(starters).getByText("QB")).toBeTruthy();
    expect(within(starters).getByText("24.1")).toBeTruthy();
    expect(within(starters).getByText("22.7")).toBeTruthy();
    expect(starters.textContent).toContain("Week One Opponent @ Ohio State");
    expect(starters.textContent).toContain("Texas @ Week One Opponent");
    expect(starters.textContent).toMatch(/AM|PM/);
    expect(starters.querySelectorAll("[data-player-game-matchup]")).toHaveLength(2);
    expect(starters.querySelectorAll("[data-player-game-time]")).toHaveLength(2);
    expect(starters.querySelector('[data-mobile-matchup-player="right"]')?.className).toContain(
      "grid-cols-[2.75rem_minmax(0,1fr)]",
    );
    expect(starters.querySelector('[data-mobile-matchup-player="right"]')?.className).toContain("text-left");
    expect(within(starters).getByText("22.7").parentElement?.className).toContain("text-cfb-text-primary");
    expect(starters.querySelector('[data-mobile-matchup-player="left"]')?.className).toContain(
      "grid-cols-[minmax(0,1fr)_2.75rem]",
    );
    expect(within(starters).getByText("24.1").parentElement?.className).toContain("text-cfb-text-primary");
    expect(starters.querySelector("[data-mobile-slot-rail]")).toBeTruthy();
    expect(starters.querySelector("[data-mobile-slot-column]")?.className).not.toContain("border-x");
  });

  it("keeps numbered bench slot labels on one line in the wider mobile slot rail", () => {
    const benchTwoMyTeam = {
      ...myTeam,
      roster: [myTeam.roster[0], { ...myTeam.roster[1], display_label: "BENCH 2" }],
    };
    const benchTwoOpponentTeam = {
      ...opponentTeam,
      roster: [opponentTeam.roster[0], { ...opponentTeam.roster[1], display_label: "BENCH 2" }],
    };
    render(<SideBySideMatchup myTeam={benchTwoMyTeam} opponentTeam={benchTwoOpponentTeam} />);
    const bench = screen.getByTestId("mobile-bench-lineup");
    const benchSlot = within(bench).getByText("BENCH 2");

    expect(benchSlot.className).toContain("whitespace-nowrap");
    expect(benchSlot.closest("[data-mobile-matchup-row]")?.className).toContain("_3.5rem_");
    expect(bench.querySelector("[data-mobile-slot-rail]")?.className).toContain("w-14");
  });

  it("opens the existing player card from either side of a mobile matchup row", () => {
    render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} leagueId={42} />);
    const starters = screen.getByTestId("mobile-starting-lineup");

    fireEvent.click(within(starters).getByRole("button", { name: "Open L. Name Quarterback player card" }));
    expect(screen.getByRole("dialog").textContent).toContain("Long Name Quarterback matchup player card");

    fireEvent.click(screen.getByRole("button", { name: "Close player card" }));
    fireEvent.click(within(starters).getByRole("button", { name: "Open O. Quarterback player card" }));
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
    const starters = screen.getByTestId("mobile-starting-lineup");

    expect(within(starters).getByText("7.3")).toBeTruthy();
    expect(within(starters).getByText("13.0")).toBeTruthy();
    expect(within(starters).queryByText("24.1")).toBeNull();
    expect(within(starters).queryByText("22.7")).toBeNull();
  });

  it("highlights every live mobile player row and uses a football icon for team possession", () => {
    const liveMyTeam = {
      ...myTeam,
      roster: [{
        ...myTeam.roster[0],
        live_game_state: "live" as const,
        team_has_possession: true,
        game_period: 1,
        game_clock: "08:15",
        game_down_distance: "2nd & 7 at OHST 33",
        game_score: "Ohio State 10 – Texas 14",
      }],
    };
    const liveOpponentTeam = {
      ...opponentTeam,
      roster: [{
        ...opponentTeam.roster[0],
        live_game_state: "live" as const,
        game_period: 1,
        game_clock: "08:15",
        game_down_distance: "2nd & 7 at OHST 33",
        game_score: "Ohio State 10 – Texas 14",
      }],
    };
    render(<SideBySideMatchup myTeam={liveMyTeam} opponentTeam={liveOpponentTeam} scoringStatus="live" />);
    const starters = screen.getByTestId("mobile-starting-lineup");

    const liveRows = starters.querySelectorAll('[data-mobile-player-live="true"]');
    expect(liveRows).toHaveLength(2);
    expect([...liveRows].every((row) => row.className.includes("bg-slate-100/[0.10]"))).toBe(true);
    expect(within(starters).getByLabelText("Team has possession")).toBeTruthy();
    expect(within(starters).getAllByLabelText("Game in progress — lineup locked")).toHaveLength(2);
    expect(within(starters).getAllByText("Q1 08:15 · 2nd & 7 at OHST 33 · Ohio State 10 – Texas 14")).toHaveLength(2);
  });

  it("shows refreshed current-game stat lines for live starters and bench players", () => {
    const liveMyTeam = {
      ...myTeam,
      roster: [
        {
          ...myTeam.roster[0],
          live_game_state: "live" as const,
          game_stat_line: "184 PASS YDS · 2 PASS TD · 21 RUSH YDS · 1 RUSH TD",
        },
        {
          ...myTeam.roster[1],
          live_game_state: "live" as const,
          game_stat_line: "4 REC · 67 REC YDS · 1 REC TD",
        },
      ],
    };

    render(<SideBySideMatchup myTeam={liveMyTeam} opponentTeam={opponentTeam} scoringStatus="live" />);

    expect(within(screen.getByTestId("mobile-starting-lineup")).getByText("184 PASS YDS · 2 PASS TD · 21 RUSH YDS · 1 RUSH TD").getAttribute("data-player-game-stat-line")).not.toBeNull();
    expect(within(screen.getByTestId("mobile-bench-lineup")).getByText("4 REC · 67 REC YDS · 1 REC TD").getAttribute("data-player-game-stat-line")).not.toBeNull();
  });

  it("starts a scheduled row at kickoff without waiting for a provider play", () => {
    const kickoffStartedMyTeam = {
      ...myTeam,
      roster: [{
        ...myTeam.roster[0],
        live_game_state: "scheduled" as const,
        game_start_at: new Date(Date.now() - 1_000).toISOString(),
      }],
    };

    render(<SideBySideMatchup myTeam={kickoffStartedMyTeam} opponentTeam={opponentTeam} />);
    const starters = screen.getByTestId("mobile-starting-lineup");

    expect(within(starters).getByText("0.0")).toBeTruthy();
    expect(within(starters).getByText("Proj 24.1")).toBeTruthy();
    expect(within(starters).getByText("In progress")).toBeTruthy();
    expect(starters.querySelector('[data-mobile-player-live="true"]')?.className).toContain("bg-slate-100/[0.10]");
  });

  it("marks finalized player games with clear blue totals and removes their obsolete kickoff time", () => {
    const finalMyTeam = {
      ...myTeam,
      roster: [{
        ...myTeam.roster[0],
        live_game_state: "final" as const,
        live_scoring_status: "stale",
        current_fantasy_points: 18.5,
        pregame_projected_points: 24.1,
        final_game_stat_line: "281 PASS YDS · 3 PASS TD · 34 RUSH YDS · 1 RUSH TD",
      }],
    };

    render(<SideBySideMatchup myTeam={finalMyTeam} opponentTeam={opponentTeam} scoringStatus="final" />);
    const starters = screen.getByTestId("mobile-starting-lineup");

    expect(within(starters).getByLabelText("Game final")).toBeTruthy();
    expect(within(starters).getByText("18.5").parentElement?.className).toContain("text-cfb-brand");
    expect(within(starters).getByText("Final").className).toContain("text-cfb-brand");
    expect(within(starters).getByText("Final").className).toContain("text-[9px]");
    const pregameProjection = within(starters).getByText("Proj 24.1");
    expect(pregameProjection.getAttribute("data-player-final-pregame-projection")).not.toBeNull();
    expect(pregameProjection.className).toContain("text-cfb-brand");
    expect(within(starters).getByText("L. Name Quarterback").closest("[data-mobile-matchup-player]")?.querySelector("[data-player-game-time]")).toBeNull();
    const statLine = within(starters).getByText("281 PASS YDS · 3 PASS TD · 34 RUSH YDS · 1 RUSH TD");
    expect(statLine.getAttribute("data-player-final-stat-line")).not.toBeNull();
    expect(statLine.className).toContain("truncate");
    expect(statLine.className).toContain("text-cfb-text-muted");
    const finalizedRow = within(starters).getByText("L. Name Quarterback").closest("[data-mobile-player-live]");
    expect(finalizedRow?.getAttribute("data-mobile-player-live")).toBe("false");
    expect(finalizedRow?.className).not.toContain("bg-slate-100/[0.10]");
  });

  it("keeps an out marker by the player name while rendering a numeric zero projection", () => {
    const unavailableMyTeam = {
      ...myTeam,
      roster: [{ ...myTeam.roster[0], injury_status: "OUT_FOR_SEASON", projection_status: "OUT" }],
    };

    render(<SideBySideMatchup myTeam={unavailableMyTeam} opponentTeam={opponentTeam} />);
    const starters = screen.getByTestId("mobile-starting-lineup");

    expect(within(starters).getByLabelText("Out").textContent).toBe("O");
    expect(within(starters).getByText("0.0")).toBeTruthy();
  });

  it("keeps bench rows collapsed until a user chooses to inspect them", () => {
    const { container } = render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} />);

    expect(screen.getByText("Bench depth")).toBeTruthy();
    expect(screen.getByTestId("mobile-bench-lineup")).toBeTruthy();
    expect(container.querySelector("details")?.open).toBe(false);
  });

  it("uses one shared desktop slot rail and no duplicate player-position badges", () => {
    render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} />);
    const desktopStarters = screen.getByTestId("desktop-starting-lineup");
    const desktopBench = screen.getByTestId("desktop-bench-lineup");

    const myStarterHeading = within(desktopStarters).getByText("An1ski's Team Starters");
    const opponentStarterHeading = within(desktopStarters).getByText("Mary's Team Starters");
    expect(myStarterHeading).toBeTruthy();
    expect(opponentStarterHeading).toBeTruthy();
    expect(myStarterHeading.className).toContain("text-cfb-text-primary");
    expect(opponentStarterHeading.className).toContain("text-cfb-text-primary");
    expect(within(desktopBench).getByText("An1ski's Team Bench")).toBeTruthy();
    expect(within(desktopBench).getByText("Mary's Team Bench")).toBeTruthy();
    expect(within(desktopStarters).queryByText("Adam's Team Starters")).toBeNull();
    expect(desktopStarters.querySelectorAll('[data-desktop-slot-rail="true"]')).toHaveLength(1);
    expect(desktopStarters.querySelectorAll('[data-desktop-slot-column="true"]')).toHaveLength(1);
    expect(desktopStarters.querySelectorAll("[data-roster-slot-swap]")).toHaveLength(0);
    expect(within(desktopStarters).getAllByText("QB")).toHaveLength(1);
  });

  it("keeps desktop matchup players selectable after moving them into the shared layout", () => {
    render(<SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} leagueId={42} />);
    const desktopStarters = screen.getByTestId("desktop-starting-lineup");

    fireEvent.click(within(desktopStarters).getByRole("button", { name: "Open L. Name Quarterback player card" }));

    expect(screen.getByRole("dialog").textContent).toContain("Long Name Quarterback matchup player card");
  });
});
