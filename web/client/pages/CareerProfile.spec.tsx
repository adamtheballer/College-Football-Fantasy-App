// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/hooks/use-leagues", () => ({
  useCareerProfile: () => ({
    isLoading: false,
    isError: false,
    data: {
      display_name: "Adam",
      username: "adam",
      member_since: "2026-08-01T00:00:00Z",
      record: { wins: 8, losses: 3, ties: 0, win_pct: 8 / 11 },
      leagues: { joined: 2 },
      scoring: { points_for: 1543.2, average_points: 140.3, high_week: 188.4, low_week: 104.2 },
      drafts: { official_completed: 2, mock_completed: 3 },
      trades: { completed: 4 },
      waivers: { won: 6 },
      streaks: { longest_win: 4, current_win: 2 },
      postseason: { appearances: 1, championships: 0, regular_season_first_place: 1 },
      matchups: { completed: 11 },
      rivalry: { wins: 1, losses: 0 },
    },
  }),
  useCareerEvents: () => ({
    isLoading: false,
    data: { data: [{ id: 1, title: "Completed a league draft", season: 2026, week: null, occurred_at: "2026-08-10T00:00:00Z" }] },
  }),
  useCareerLeagues: () => ({
    data: [{ league_id: 7, name: "Saturday League", season: 2026, status: "ACTIVE", record: { wins: 8, losses: 3, ties: 0 }, points_for: 1543.2, rival_team_name: "Mary's Team" }],
  }),
  useCareerTrophies: () => ({ data: [] }),
}));

import CareerProfile from "./CareerProfile";

describe("CareerProfile", () => {
  it("renders verified career metrics and navigable career sections without third-party branding", () => {
    render(<MemoryRouter><CareerProfile /></MemoryRouter>);

    expect(screen.getByRole("heading", { name: "Adam" })).toBeTruthy();
    expect(screen.getByText("Completed matchups")).toBeTruthy();
    expect(screen.getByText("Regular-season #1")).toBeTruthy();
    expect(screen.queryByText(/ESPN/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "History" }));
    expect(screen.getByText("Completed a league draft")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Leagues" }));
    expect(screen.getByText("Saturday League")).toBeTruthy();
    expect(screen.getByText("Rival: Mary's Team")).toBeTruthy();
  });
});
