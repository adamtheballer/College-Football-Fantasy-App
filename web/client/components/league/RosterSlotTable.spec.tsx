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

import { finalPregameProjectionDetail, formatRosterGameKickoff, formatRosterPointValue, liveGameStatusLabel, liveProjectionDetail, RosterSlotTable } from "./RosterSlotTable";

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

  it("shows the shared red out marker beside an unavailable player name", () => {
    const outReceiver = { ...projectedReceiver, injury_status: "OUT_FOR_SEASON" };
    render(<RosterSlotTable title="Starters" players={[outReceiver]} />);

    expect(screen.getByLabelText("Out").textContent).toBe("O");
    expect(screen.getByText("0.0")).toBeTruthy();
    expect(formatRosterPointValue(outReceiver, "projected")).toBe("0.0");
  });

  it("uses persisted live points when the caller marks the table as live", () => {
    const liveReceiver = { ...projectedReceiver, live_points: 21.37, live_scoring_status: "live" };
    render(<RosterSlotTable title="Starters" players={[liveReceiver]} pointMode="live" />);

    expect(screen.getByText("21.4")).toBeTruthy();
    expect(screen.queryByText("18.4")).toBeNull();
    expect(formatRosterPointValue(liveReceiver, "live")).toBe("21.4");
  });

  it("uses a zero live total at kickoff, retains the projection as secondary context, and prioritizes red zone styling", () => {
    const liveReceiver = {
      ...projectedReceiver,
      live_game_state: "live" as const,
      live_points: null,
      team_has_possession: true,
      team_in_red_zone: true,
      game_period: 1,
      game_clock: "08:15",
      game_down_distance: "2nd & 7 at MICH 33",
      game_score: "Michigan 10 – Ohio State 14",
    };
    const { container } = render(<RosterSlotTable title="Starters" players={[liveReceiver]} />);

    expect(screen.getByText("0.0")).toBeTruthy();
    expect(screen.getByText("Proj 18.4")).toBeTruthy();
    expect(screen.getByText("Red zone")).toBeTruthy();
    expect(screen.getByText("Q1 08:15 · 2nd & 7 at MICH 33 · Michigan 10 – Ohio State 14")).toBeTruthy();
    expect(screen.getByLabelText("Game in progress — lineup locked")).toBeTruthy();
    expect(container.querySelector('[data-live-game-state="live"]')?.getAttribute("data-in-red-zone")).toBe("true");
    expect(formatRosterPointValue(liveReceiver, "projected")).toBe("0.0");
  });

  it("labels the live predicted final separately from the current score", () => {
    const liveReceiver = {
      ...projectedReceiver,
      live_game_state: "live" as const,
      current_fantasy_points: 4.2,
      live_projected_final_points: 16.7,
    };
    expect(formatRosterPointValue(liveReceiver, "live")).toBe("4.2");
    expect(liveProjectionDetail(liveReceiver)).toBe("Proj 16.7");
  });

  it("shows a current in-progress stat line beneath the live game fixture and updates from the refreshed roster payload", () => {
    const liveReceiver = {
      ...projectedReceiver,
      live_game_state: "live" as const,
      game_stat_line: "4 REC · 67 REC YDS · 1 REC TD",
      game_period: 2,
      game_clock: "04:32",
      game_score: "Michigan 14 – Ohio State 10",
    };
    render(<RosterSlotTable title="Bench" players={[liveReceiver]} pointMode="live" />);

    const statLine = screen.getByText("4 REC · 67 REC YDS · 1 REC TD");
    expect(statLine.getAttribute("data-player-game-stat-line")).not.toBeNull();
    expect(statLine.getAttribute("data-player-final-stat-line")).toBeNull();
    expect(statLine.className).toContain("truncate");
  });

  it("keeps the published date and kickoff time below every non-final desktop roster player", () => {
    const scheduledReceiver = {
      ...projectedReceiver,
      game_start_at: "2026-09-05T23:30:00Z",
    };
    render(<RosterSlotTable title="Starters" players={[scheduledReceiver]} />);

    const gameTime = screen.getByText(/Sep 5.*at.*PM/);
    expect(gameTime.getAttribute("data-player-game-time")).not.toBeNull();
    expect(formatRosterGameKickoff("2026-09-05T23:30:00Z")).toMatch(/Sep 5.*at.*PM/);
  });

  it("uses a halftime label instead of a stale clock or down", () => {
    const halftimeReceiver = {
      ...projectedReceiver,
      live_game_state: "live" as const,
      game_period: 2,
      game_clock: "00:00",
      game_down_distance: "4th & 3",
      game_score: "Michigan 10 – Ohio State 14",
      game_is_halftime: true,
    };

    expect(liveGameStatusLabel(halftimeReceiver)).toBe("Halftime · Michigan 10 – Ohio State 14");
  });

  it("marks a finalized player game with a compact lock and clear blue final scoring", () => {
    const finalReceiver = {
      ...projectedReceiver,
      live_game_state: "final" as const,
      current_fantasy_points: 17.8,
      pregame_projected_points: 15.3,
      final_game_stat_line: "6 REC · 104 REC YDS · 1 REC TD",
      game_start_at: "2026-08-29T23:00:00Z",
    };
    render(<RosterSlotTable title="Starters" players={[finalReceiver]} pointMode="live" />);

    expect(screen.getByLabelText("Game final")).toBeTruthy();
    expect(screen.getByText("17.8").parentElement?.className).toContain("text-cfb-brand");
    expect(screen.getByText("Final").className).toContain("text-cfb-brand");
    expect(screen.getByText("Final").className).toContain("text-[10px]");
    const pregameProjection = screen.getByText("Proj 15.3");
    expect(pregameProjection.getAttribute("data-player-final-pregame-projection")).not.toBeNull();
    expect(pregameProjection.className).toContain("text-cfb-brand");
    expect(finalPregameProjectionDetail(finalReceiver)).toBe("Proj 15.3");
    const statLine = screen.getByText("6 REC · 104 REC YDS · 1 REC TD");
    expect(statLine.getAttribute("data-player-final-stat-line")).not.toBeNull();
    expect(statLine.className).toContain("truncate");
    expect(statLine.className).toContain("text-cfb-text-muted");
    expect(screen.queryByText(/Aug 29.*at.*PM/)).toBeNull();
  });

  it("preserves stale live values and explicitly labels the delayed data", () => {
    const staleReceiver = {
      ...projectedReceiver,
      live_game_state: "live" as const,
      current_fantasy_points: 12.6,
      live_projected_final_points: 24.1,
      live_projection_status: "STALE" as const,
    };
    expect(formatRosterPointValue(staleReceiver, "live")).toBe("12.6");
    expect(liveProjectionDetail(staleReceiver)).toBe("Proj 24.1 · Data delayed");
  });

  it("keeps a scheduled player's projection visible while another game is live", () => {
    const scheduledReceiver = { ...projectedReceiver, live_game_state: "scheduled" as const, live_points: null };

    expect(formatRosterPointValue(scheduledReceiver, "live")).toBe("18.4");
  });

  it("starts a roster row at its published kickoff even before provider play data arrives", () => {
    const justStartedReceiver = {
      ...projectedReceiver,
      live_game_state: "scheduled" as const,
      game_start_at: new Date(Date.now() - 1_000).toISOString(),
    };

    render(<RosterSlotTable title="Starters" players={[justStartedReceiver]} />);

    expect(formatRosterPointValue(justStartedReceiver, "projected")).toBe("0.0");
    expect(liveProjectionDetail(justStartedReceiver)).toBe("Proj 18.4");
    expect(liveGameStatusLabel(justStartedReceiver)).toBe("In progress");
    expect(screen.getByText("0.0")).toBeTruthy();
    expect(screen.getByText("Proj 18.4")).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
  });

  it("uses the neutral possession treatment when the offense is outside the red zone", () => {
    const possessionReceiver = {
      ...projectedReceiver,
      live_game_state: "live" as const,
      team_has_possession: true,
      team_in_red_zone: false,
    };
    const { container } = render(<RosterSlotTable title="Starters" players={[possessionReceiver]} />);
    const row = container.querySelector('[data-has-possession="true"]');

    expect(row?.className).toContain("bg-slate-100/[0.10]");
    expect(screen.getByLabelText("Team has possession")).toBeTruthy();
    expect(screen.queryByText("Possession")).toBeNull();
  });
});
