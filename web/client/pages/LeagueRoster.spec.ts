import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import {
  formatLineupLockMessage,
  formatRosterLoadError,
  getLeagueRosterTeams,
} from "./LeagueRoster";

describe("formatRosterLoadError", () => {
  it("keeps the backend detail instead of rendering an empty roster", () => {
    expect(
      formatRosterLoadError(
        new ApiError(503, "Roster service is unavailable."),
        "Fallback",
      ),
    ).toBe("Roster service is unavailable.");
  });

  it("uses a safe fallback for unknown errors", () => {
    expect(formatRosterLoadError(null, "Fallback")).toBe("Fallback");
  });

  it("labels a locked player without exposing a stale editable lineup control", () => {
    expect(
      formatLineupLockMessage({
        id: 1,
        fantasy_team_id: 1,
        fantasy_team_name: "Team One",
        player_id: 10,
        player_name: "Runner One",
        slot: "RB",
        status: "active",
        opponent: null,
        weekly_projected_fantasy_points: 0,
        is_locked: true,
        game_start_at: "2026-08-20T18:00:00Z",
      }),
    ).toContain("Locked at kickoff");
  });

  it("uses the league-wide roster payload so every team can be viewed", () => {
    expect(
      getLeagueRosterTeams({
        league_id: 1,
        season: 2026,
        fantasy_team_id: 1,
        fantasy_team_name: "My Team",
        week: 1,
        data: [],
        team_rosters: [
          {
            team: {
              id: 1,
              name: "My Team",
              owner_user_id: 42,
              record: "0-0-0",
            },
            roster: [],
          },
          {
            team: {
              id: 2,
              name: "Rival Team",
              owner_user_id: 43,
              record: "0-0-0",
            },
            roster: [],
          },
        ],
      }),
    ).toHaveLength(2);
  });
});
