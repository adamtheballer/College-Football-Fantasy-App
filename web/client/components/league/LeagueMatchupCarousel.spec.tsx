// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LeagueDetail } from "@/types/league";

import { LeagueMatchupCarousel } from "./LeagueMatchupCarousel";

const leagues = [
  {
    id: 17,
    name: "Saturday Legends",
    icon_url: null,
    current_user_summary: {
      team_name: "Adam's Team",
      opponent_team_name: "Mary's Team",
      matchup_week: 1,
      wins: 3,
      losses: 1,
      ties: 0,
      projected_points_for: 133.1,
      projected_points_against: 127.6,
      win_probability_for: 55.2,
      win_probability_against: 44.8,
    },
  },
] as LeagueDetail[];

afterEach(cleanup);

describe("LeagueMatchupCarousel", () => {
  it("shows each league's canonical matchup summary in a horizontal swipe rail", () => {
    render(<LeagueMatchupCarousel leagues={leagues} activeLeagueId={17} onOpenLeague={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Matchups at a glance" })).toBeTruthy();
    expect(screen.getByText("Saturday Legends")).toBeTruthy();
    expect(screen.getByText("133.1")).toBeTruthy();
    expect(screen.getByText("127.6")).toBeTruthy();
    expect(screen.getByText("55.2% / 44.8%")).toBeTruthy();
    expect(screen.getByLabelText("Swipe through your league matchups").className).toContain("overflow-x-auto");
  });

  it("opens the selected league matchup from the home carousel", () => {
    const onOpenLeague = vi.fn();
    render(<LeagueMatchupCarousel leagues={leagues} onOpenLeague={onOpenLeague} />);

    fireEvent.click(screen.getByRole("button", { name: /Saturday Legends/i }));

    expect(onOpenLeague).toHaveBeenCalledWith(17);
  });
});
