// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("react-router-dom", () => ({
  Link: ({ children }: { children: unknown }) => <a>{children as never}</a>,
  useParams: () => ({ leagueId: "42" }),
}));
vi.mock("@/components/league/LeagueTabs", () => ({ LeagueTabs: () => null }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ user: { id: 1 } }) }));
vi.mock("@/hooks/use-leagues", () => ({
  useLeagueDetail: () => ({ data: { commissioner_user_id: 1, draft: { status: "completed" }, status: "in_season" }, isLoading: false, isError: false, refetch: vi.fn() }),
  useLeaguePlayoffSeeding: () => ({ data: { state: "SEEDING_LOCKED", playoff_team_count: 4, entries: [{ seed: 1, team_id: 1, team_name: "Alpha", qualified: true, resolved_by: "points_for", record: { wins: 8, losses: 4, ties: 1 }, tiebreak_group_team_ids: [], trace: [] }] }, error: null }),
  useLeaguePlayoffBracket: () => ({ data: { status: "PLAYOFFS_ACTIVE", rounds: [{ round_number: 1, round_type: "SEMIFINALS", week: 11, slot_number: 1, status: "FINAL", team_a: { team_id: 1, team_name: "Alpha", seed: 1 }, team_b: { team_id: 4, team_name: "Delta", seed: 4 }, advancing_team_id: 1, tiebreaker_used: "higher_original_playoff_seed", fantasy_matchup_id: 88, metadata: {} }] } }),
  useLockLeaguePlayoffSeeding: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useReconcileLeaguePlayoffs: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

import LeaguePlayoffs from "./LeaguePlayoffs";

afterEach(cleanup);

describe("LeaguePlayoffs", () => {
  it("renders tied regular-season records and the playoff tie advancement rule", () => {
    render(createElement(LeaguePlayoffs));
    expect(screen.getByText("8-4-1")).toBeTruthy();
    expect(screen.getByText("Tied playoff: higher original seed advanced.")).toBeTruthy();
    expect(screen.getByText("#1 Alpha")).toBeTruthy();
  });
});
