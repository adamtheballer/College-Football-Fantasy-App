// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("react-router-dom", () => ({
  Navigate: () => null,
  useParams: () => ({ leagueId: "42" }),
}));

vi.mock("@/components/league/LeagueTabs", () => ({ LeagueTabs: () => null }));
vi.mock("@/components/league/SideBySideMatchup", () => ({ SideBySideMatchup: () => null }));
vi.mock("@/components/league/WeekSelector", () => ({ WeekSelector: () => null }));
vi.mock("@/components/league/WinChanceMeter", () => ({ WinChanceMeter: () => null }));

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
      my_team: { fantasy_team_id: 10, fantasy_team_name: "My Team", record: "0-0-0", projected_total: 111.2, win_probability: 54, roster: [] },
      opponent_team: { fantasy_team_id: 11, fantasy_team_name: "My Opponent", record: "0-0-0", projected_total: 106.4, win_probability: 46, roster: [] },
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useLeagueScoreboard: () => ({
    data: {
      data: [
        { matchup_id: 1, week: 1, status: "projected", home_team_name: "My Team", away_team_name: "My Opponent", home_score: 111.2, away_score: 106.4 },
        { matchup_id: 2, week: 1, status: "projected", home_team_name: "League Mate One", away_team_name: "League Mate Two", home_score: 103.1, away_score: 100.8 },
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
  it("reveals every other scheduled league matchup without duplicating the viewer's game", () => {
    render(createElement(LeagueMatchup));

    expect(screen.getByRole("button", { name: "View league matchups" })).toBeTruthy();
    expect(screen.queryByText("League Mate One")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "View league matchups" }));

    expect(screen.getByRole("heading", { name: "Other Week 1 Matchups" })).toBeTruthy();
    expect(screen.getByText("League Mate One")).toBeTruthy();
    expect(screen.getByText("League Mate Two")).toBeTruthy();
    expect(screen.queryByText("No other matchups this week")).toBeNull();
  });
});
