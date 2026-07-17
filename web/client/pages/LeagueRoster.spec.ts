import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { formatLineupLockMessage, formatRosterLoadError } from "./LeagueRoster";

describe("formatRosterLoadError", () => {
  it("keeps the backend detail instead of rendering an empty roster", () => {
    expect(formatRosterLoadError(new ApiError(503, "Roster service is unavailable."), "Fallback")).toBe(
      "Roster service is unavailable."
    );
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
});
