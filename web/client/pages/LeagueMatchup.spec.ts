// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const routerMocks = vi.hoisted(() => ({ setSearchParams: vi.fn(), navigate: vi.fn() }));

vi.mock("react-router-dom", () => ({
  Navigate: () => null,
  useParams: () => ({ leagueId: "42" }),
  useSearchParams: () => [new URLSearchParams(), routerMocks.setSearchParams],
  useNavigate: () => routerMocks.navigate,
}));

vi.mock("@/components/league/LeagueTabs", () => ({ LeagueTabs: () => null }));
vi.mock("@/components/league/SideBySideMatchup", () => ({ SideBySideMatchup: () => null }));
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
      my_team: { fantasy_team_id: 10, fantasy_team_name: "My Team", owner_avatar_url: "https://images.example.com/my-team.jpg", record: "0-0-0", projected_total: 111.2, win_probability: 54, roster: [] },
      opponent_team: { fantasy_team_id: 11, fantasy_team_name: "My Opponent", owner_avatar_url: "https://images.example.com/my-opponent.jpg", record: "0-0-0", projected_total: 106.4, win_probability: 46, roster: [] },
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useLeagueScoreboard: () => ({
    data: {
      data: [
        { matchup_id: 1, week: 1, status: "projected", home_team_name: "My Team", home_owner_avatar_url: "https://images.example.com/my-team.jpg", away_team_name: "My Opponent", away_owner_avatar_url: "https://images.example.com/my-opponent.jpg", home_score: 111.2, away_score: 106.4 },
        { matchup_id: 2, week: 1, status: "projected", home_team_name: "League Mate One", away_team_name: "League Mate Two", home_score: 103.1, away_score: 100.8 },
      ],
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useLeagueRivalry: () => ({ data: { eligible: false, incoming_invites: [], candidates: [] }, isLoading: false }),
  useRivalryActions: () => ({
    invite: { mutate: vi.fn(), isPending: false },
    accept: { mutate: vi.fn(), isPending: false },
    decline: { mutate: vi.fn(), isPending: false },
    cancel: { mutate: vi.fn(), isPending: false },
  }),
}));

import {
  default as LeagueMatchup,
  freshnessText,
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

  it("explains persisted provider freshness without claiming stale data is current", () => {
    expect(
      freshnessText({
        league_id: 42,
        matchup_id: 1,
        week: 1,
        status: "live",
        user_team: null,
        opponent_team: null,
        live_scoring_freshness: { state: "fresh", data_age_seconds: 31, relevant_game_count: 2 },
      }),
    ).toContain("current");
    expect(
      freshnessText({
        league_id: 42,
        matchup_id: 1,
        week: 1,
        status: "live",
        user_team: null,
        opponent_team: null,
        live_scoring_freshness: { state: "stale", relevant_game_count: 2 },
      }),
    ).toContain("stale");
  });
});

describe("league matchup scoreboard", () => {
  it("renders the mobile scoreboard with truthful pregame scores, projections, and win chances", () => {
    render(createElement(LeagueMatchup));

    expect(screen.getByText("Week 1 matchup")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "My Team vs My Opponent" })).toBeTruthy();
    expect(
      screen
        .queryAllByText("Projected", { exact: true })
        .every((element) => element.classList.contains("sr-only")),
    ).toBe(true);
    expect(screen.getByLabelText("Projected 111.2")).toBeTruthy();
    expect(screen.getByLabelText("Projected 106.4")).toBeTruthy();
    expect(screen.getAllByText("54.0%")).toHaveLength(2);
    expect(screen.getAllByText("46.0%")).toHaveLength(2);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText("CFB Scores available once games begin")).toBeNull();
    expect(screen.getAllByAltText("My Team profile picture").every((image) => image.getAttribute("src") === "https://images.example.com/my-team.jpg")).toBe(true);
    expect(screen.getAllByAltText("My Opponent profile picture").every((image) => image.getAttribute("src") === "https://images.example.com/my-opponent.jpg")).toBe(true);
  });

  it("lets a member swipe or tap through same-league matchups through the canonical detail query", () => {
    render(createElement(LeagueMatchup));

    expect(screen.getByRole("region", { name: "League matchups" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "View My Opponent at My Team" }).getAttribute("aria-pressed")).toBe("true");
    const otherMatchup = screen.getByRole("button", { name: "View League Mate Two at League Mate One" });
    expect(otherMatchup).toBeTruthy();

    fireEvent.click(otherMatchup);

    expect(routerMocks.setSearchParams).toHaveBeenCalledTimes(1);
    const nextParams = routerMocks.setSearchParams.mock.calls[0][0] as URLSearchParams;
    expect(nextParams.toString()).toBe("week=1&matchup=2");
  });
});
