// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByTestId("league-carousel-pagination").getAttribute("aria-label")).toBe("Showing league 1 of 1");
  });

  it("moves the active pagination dot with the league card centered in the swipe rail", async () => {
    const multipleLeagues = [
      ...leagues,
      {
        ...leagues[0],
        id: 18,
        name: "Midnight Managers",
        current_user_summary: {
          ...leagues[0].current_user_summary!,
          team_name: "Second Team",
          opponent_team_name: "Third Team",
        },
      },
    ];
    render(<LeagueMatchupCarousel leagues={multipleLeagues} activeLeagueId={17} onOpenLeague={vi.fn()} />);

    const rail = screen.getByLabelText("Swipe through your league matchups");
    Object.defineProperty(rail, "clientWidth", { configurable: true, value: 320 });
    Object.defineProperty(rail, "scrollLeft", { configurable: true, writable: true, value: 0 });
    const cards = screen.getAllByRole("button", { name: /Saturday Legends|Midnight Managers/i });
    cards.forEach((card, index) => {
      Object.defineProperty(card, "offsetLeft", { configurable: true, value: index * 340 });
      Object.defineProperty(card, "offsetWidth", { configurable: true, value: 320 });
    });

    fireEvent.scroll(rail);
    await waitFor(() => {
      expect(screen.getByTestId("league-carousel-pagination").getAttribute("aria-label")).toBe("Showing league 1 of 2");
    });

    rail.scrollLeft = 340;
    fireEvent.scroll(rail);
    await waitFor(() => {
      expect(screen.getByTestId("league-carousel-pagination").getAttribute("aria-label")).toBe("Showing league 2 of 2");
    });
    expect(screen.getAllByTestId("league-carousel-pagination").flatMap((pagination) => Array.from(pagination.children)).map((dot) => dot.getAttribute("data-active"))).toEqual(["false", "true"]);
  });

  it("opens the selected league matchup from the home carousel", () => {
    const onOpenLeague = vi.fn();
    render(<LeagueMatchupCarousel leagues={leagues} onOpenLeague={onOpenLeague} />);

    fireEvent.click(screen.getByRole("button", { name: /Saturday Legends/i }));

    expect(onOpenLeague).toHaveBeenCalledWith(17);
  });

  it("replaces a failed league image with the default trophy icon", () => {
    const leagueWithBrokenIcon = [{ ...leagues[0], icon_url: "https://example.invalid/broken-logo.png" }];
    const { container } = render(<LeagueMatchupCarousel leagues={leagueWithBrokenIcon} onOpenLeague={vi.fn()} />);

    const leagueImage = container.querySelector('img[src="https://example.invalid/broken-logo.png"]');
    expect(leagueImage).toBeTruthy();
    fireEvent.error(leagueImage!);

    expect(container.querySelector('img[src="https://example.invalid/broken-logo.png"]')).toBeNull();
    expect(screen.getByTestId("league-icon-fallback-17")).toBeTruthy();
  });
});
