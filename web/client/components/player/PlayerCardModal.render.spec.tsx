// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { PlayerCardModal } from "./PlayerCardModal";

const gameLogFixture = vi.hoisted(() => ({ live: false }));

vi.mock("@/hooks/use-players", () => ({
  usePlayerGameLog: () => ({
    data: {
      season: 2026,
      available_seasons: [2026],
      team_name: "California",
      games: [
        {
          schedule_id: 1,
          week: 1,
          location: "home",
          location_label: "Home",
          neutral_site: false,
          conference_game: false,
          game_status: gameLogFixture.live ? "active" : "final",
          stat_status: gameLogFixture.live ? "live" : "final",
          opponent_name: "UCLA",
          result: gameLogFixture.live ? null : "W 24–17",
          stats: {
            source: "espn_final_boxscore",
            updated_at: "2026-09-05T20:00:00Z",
            fantasy_points: 14.4,
            stats: { receptions: 5, receiving_yards: 94 },
          },
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
  useLeaguePlayerHistory: () => ({ data: undefined, isLoading: false, isError: false }),
  usePlayerTradeValues: () => ({ data: undefined, isLoading: false, isError: false }),
  usePlayerTrajectory: () => ({ data: undefined, isLoading: false, isError: false }),
}));

afterEach(() => {
  gameLogFixture.live = false;
  cleanup();
});

describe("PlayerCardModal game log", () => {
  it("uses the expanded player-card viewport and compact Summary core", () => {
    render(
      <PlayerCardModal
        onClose={vi.fn()}
        player={{ id: 1, name: "Ian Strong", position: "WR", school: "California" }}
        card={{
          about: { source: "local", position: "WR", team: "California", height: "6-2", weight: "205" },
          player: { id: 1, name: "Ian Strong", position: "WR", school: "California" },
          injuries: [],
          season_stats: [],
          historical_stats: null,
        } as never}
      />,
    );

    const summary = screen.getByTestId("player-card-summary");
    expect(summary.closest("article")?.className).toContain("h-[86dvh]");
    expect(summary.closest("article")?.className).toContain("max-w-4xl");
    expect(summary.className).toContain("w-full");
    expect(screen.getByTestId("player-card-hero-portrait")).toBeTruthy();
  });

  it("uses the same horizontally scrollable table on mobile instead of game cards", () => {
    render(
      <PlayerCardModal
        onClose={vi.fn()}
        player={{ id: 1, name: "Ian Strong", position: "WR", school: "California" }}
        card={{
          about: { source: "local", position: "WR", team: "California" },
          player: { id: 1, name: "Ian Strong", position: "WR", school: "California" },
          injuries: [],
          season_stats: [],
          historical_stats: null,
        } as never}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Game Log" }));

    const tableContainer = screen.getByTestId("player-game-log-table");
    expect(tableContainer.className).toContain("overflow-x-auto");
    expect(tableContainer.className).toContain("border-y");
    expect(tableContainer.className).not.toContain("rounded");
    expect(tableContainer.querySelector("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Opponent" })).toBeTruthy();
    expect(screen.getByText("vs. UCLA")).toBeTruthy();
    expect(screen.queryByText("Week 1")).toBeNull();
    expect(screen.queryByTestId("live-game-indicator")).toBeNull();
  });

  it("keeps injury updates in News and does not render a separate Alerts tab", () => {
    render(
      <PlayerCardModal
        onClose={vi.fn()}
        player={{ id: 1, name: "Ahmad Hardy", position: "RB", school: "Missouri" }}
        card={{
          about: { source: "local", position: "RB", team: "Missouri" },
          player: { id: 1, name: "Ahmad Hardy", position: "RB", school: "Missouri" },
          injuries: [{
            id: 5,
            season: 2026,
            week: 3,
            status: "OUT",
            injury: "Upper-leg injury rehabilitation",
            is_game_time_decision: false,
            is_returning: false,
            updated_at: "2026-09-20T08:13:19Z",
          }],
          recent_news: [],
          season_stats: [],
          historical_stats: null,
        } as never}
      />,
    );

    expect(screen.queryByRole("button", { name: "Alerts" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "News" }));
    expect(screen.getByText("News & injury updates")).toBeTruthy();
    expect(screen.getByText("Upper-leg injury rehabilitation")).toBeTruthy();
  });

  it("marks only live games with a red dot in the summary and game log", () => {
    gameLogFixture.live = true;
    render(
      <PlayerCardModal
        onClose={vi.fn()}
        player={{ id: 1, name: "Ian Strong", position: "WR", school: "California" }}
        card={{
          about: { source: "local", position: "WR", team: "California" },
          player: { id: 1, name: "Ian Strong", position: "WR", school: "California" },
          current_game: {
            week: 1,
            state: "live",
            opponent_name: "UCLA",
            stats: { stats: { receptions: 2, receiving_yards: 24 }, fantasy_points: 4.4 },
          },
          injuries: [],
          season_stats: [],
          historical_stats: null,
        } as never}
      />,
    );

    expect(screen.getByText("Live game")).toBeTruthy();
    expect(screen.getAllByTestId("live-game-indicator")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Game Log" }));

    expect(screen.getByText("Live")).toBeTruthy();
    expect(screen.getAllByTestId("live-game-indicator")).toHaveLength(1);
  });

  it("does not mark completed games as live", () => {
    render(
      <PlayerCardModal
        onClose={vi.fn()}
        player={{ id: 1, name: "Ian Strong", position: "WR", school: "California" }}
        card={{
          about: { source: "local", position: "WR", team: "California" },
          player: { id: 1, name: "Ian Strong", position: "WR", school: "California" },
          current_game: { week: 1, state: "completed", opponent_name: "UCLA" },
          injuries: [],
          season_stats: [],
          historical_stats: null,
        } as never}
      />,
    );

    expect(screen.getByText("Latest verified game")).toBeTruthy();
    expect(screen.queryByTestId("live-game-indicator")).toBeNull();
  });
});
