// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { PlayerCardModal } from "./PlayerCardModal";

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
          game_status: "final",
          stat_status: "final",
          opponent_name: "UCLA",
          result: "W 24–17",
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

afterEach(cleanup);

describe("PlayerCardModal game log", () => {
  it("treats the card as a labelled tab panel and returns focus through its close action", () => {
    const onClose = vi.fn();
    render(
      <PlayerCardModal
        onClose={onClose}
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

    const close = screen.getByRole("button", { name: "Close player card" });
    expect(document.activeElement).toBe(close);
    expect(screen.getByRole("tab", { name: "Summary" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe("player-card-tab-summary");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
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

    fireEvent.click(screen.getByRole("tab", { name: "Game Log" }));

    const tab = screen.getByTestId("player-game-log-tab");
    const tableContainer = screen.getByTestId("player-game-log-table");
    expect(tab.className).not.toContain("rounded");
    expect(tab.className).not.toContain("border-cfb-border-subtle");
    expect(tableContainer.className).toContain("overflow-x-auto");
    expect(tableContainer.className).not.toContain("rounded");
    expect(tableContainer.querySelector("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Opponent" })).toBeTruthy();
    expect(screen.getByText("vs. UCLA")).toBeTruthy();
    expect(screen.queryByText("Week 1")).toBeNull();
  });
});
