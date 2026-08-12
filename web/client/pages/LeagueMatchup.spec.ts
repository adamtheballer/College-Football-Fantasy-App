// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const routerMocks = vi.hoisted(() => ({ setSearchParams: vi.fn() }));

vi.mock("react-router-dom", () => ({
  Navigate: () => null,
  useParams: () => ({ leagueId: "42" }),
  useSearchParams: () => [new URLSearchParams(), routerMocks.setSearchParams],
}));

vi.mock("@/components/league/LeagueTabs", () => ({ LeagueTabs: () => null }));
vi.mock("@/components/league/SideBySideMatchup", () => ({
  SideBySideMatchup: () => null,
}));
vi.mock("@/components/league/WeekSelector", () => ({
  WeekSelector: () => null,
}));
vi.mock("@/components/league/WinChanceMeter", () => ({
  WinChanceMeter: () => null,
  WinChanceBar: () => null,
}));

vi.mock("@/hooks/use-leagues", () => ({
  useLeagueDetail: () => ({
    data: { draft: { status: "completed" }, status: "post_draft" },
    isLoading: false,
    isError: false,
  }),
  useLeagueMatchupTab: () => ({
    data: {
      matchup_id: 1,
      week: 1,
      status: "projected",
      my_team: {
        fantasy_team_id: 10,
        fantasy_team_name: "My Team",
        record: "0-0-0",
        projected_total: 111.2,
        win_probability: 54,
        roster: [],
      },
      opponent_team: {
        fantasy_team_id: 11,
        fantasy_team_name: "My Opponent",
        record: "0-0-0",
        projected_total: 106.4,
        win_probability: 46,
        roster: [],
      },
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useLeagueScoreboard: () => ({
    data: {
      data: [
        {
          matchup_id: 1,
          week: 1,
          status: "projected",
          home_team_name: "My Team",
          away_team_name: "My Opponent",
          home_score: 111.2,
          away_score: 106.4,
        },
        {
          matchup_id: 2,
          week: 1,
          status: "projected",
          home_team_name: "League Mate One",
          away_team_name: "League Mate Two",
          home_score: 103.1,
          away_score: 100.8,
        },
      ],
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}));

import {
  default as LeagueMatchup,
  formatMatchupPoints,
  formatMatchupStatus,
  matchupStatusVariant,
  shouldShowMatchupScorePanels,
} from "./LeagueMatchup";

afterEach(cleanup);

describe("league matchup helpers", () => {
  it("maps backend matchup statuses to honest UI labels", () => {
    expect(formatMatchupStatus("live")).toBe("Live");
    expect(formatMatchupStatus("final")).toBe("Final");
    expect(formatMatchupStatus("stat_corrected")).toBe("Corrected");
    expect(formatMatchupStatus("delayed")).toBe("Delayed");
    expect(formatMatchupStatus("unavailable")).toBe("Unavailable");
    expect(formatMatchupStatus(null)).toBe("Projected");
  });

  it("maps backend matchup statuses to semantic badge variants", () => {
    expect(matchupStatusVariant("live")).toBe("live");
    expect(matchupStatusVariant("final")).toBe("final");
    expect(matchupStatusVariant("stat_corrected")).toBe("corrected");
    expect(matchupStatusVariant("delayed")).toBe("delayed");
    expect(matchupStatusVariant("unavailable")).toBe("unavailable");
    expect(matchupStatusVariant(undefined)).toBe("projected");
  });

  it("formats matchup points with a dash when values are not real numbers", () => {
    expect(formatMatchupPoints(118.44)).toBe("118.4");
    expect(formatMatchupPoints(null)).toBe("—");
    expect(formatMatchupPoints(Number.NaN)).toBe("—");
  });

  it("hides score panels before live scoring begins", () => {
    expect(shouldShowMatchupScorePanels("projected")).toBe(false);
    expect(shouldShowMatchupScorePanels(null)).toBe(false);
    expect(shouldShowMatchupScorePanels("live")).toBe(true);
    expect(shouldShowMatchupScorePanels("final")).toBe(true);
    expect(shouldShowMatchupScorePanels("stat_corrected")).toBe(true);
  });
});

describe("league matchup scoreboard", () => {
  it("renders a compact Week 1 preweek-baseline scoreboard with both projected totals and win chances", () => {
    render(createElement(LeagueMatchup));

    expect(screen.getByText("Week 1 Matchup")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "My Team vs My Opponent" }),
    ).toBeTruthy();
    expect(screen.getByText("Preweek baseline")).toBeTruthy();
    expect(screen.getByText("111.2")).toBeTruthy();
    expect(screen.getByText("106.4")).toBeTruthy();
    expect(screen.getAllByText("54.0%")).toHaveLength(1);
    expect(screen.getAllByText("46.0%")).toHaveLength(1);
    expect(
      screen.getByText("Win chance from weekly lineup totals"),
    ).toBeTruthy();
  });

  it("lets a member load another same-league matchup through the canonical detail query", () => {
    render(createElement(LeagueMatchup));

    const selector = screen.getByRole("combobox", { name: "League matchup" });
    expect(selector).toBeTruthy();
    expect(
      screen.getByRole("option", { name: "My Team vs My Opponent" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("option", {
        name: "League Mate One vs League Mate Two",
      }),
    ).toBeTruthy();

    fireEvent.change(selector, { target: { value: "2" } });

    expect(routerMocks.setSearchParams).toHaveBeenCalledTimes(1);
    const nextParams = routerMocks.setSearchParams.mock
      .calls[0][0] as URLSearchParams;
    expect(nextParams.toString()).toBe("week=1&matchup=2");
  });
});
