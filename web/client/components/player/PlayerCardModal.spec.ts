import { describe, expect, it } from "vitest";

import { statValue } from "@/lib/playerProjectionStats";

import {
  formatGameLogDate,
  formatPlayerNewsReportTime,
  gameLogColumnsForPosition,
  gameLogOpponentLabel,
  completedSeasonGameTotals,
  draftHistorySummary,
  formatPlayerCardValue,
  getPlayerCardPalette,
  resolvePlayerCardCfb27Rating,
  resolvePlayerCardCurrentValueRating,
  resolvePlayerCardProjectionStats,
  visiblePlayerCardAboutMessage,
  visiblePlayerCardTabs,
} from "./PlayerCardModal";
import { CURRENT_VALUE_RATING_LABEL, formatCurrentValueRating } from "./PlayerCardHeader";

describe("PlayerCardModal helpers", () => {
  it("always shows the History tab, with league context controlling its contents", () => {
    expect(visiblePlayerCardTabs(false).map((tab) => tab.label)).toEqual([
      "Summary", "News", "Game Log", "Alerts", "Projections", "History", "Value",
    ]);
    expect(visiblePlayerCardTabs(true).map((tab) => tab.label)).toEqual([
      "Summary", "News", "Game Log", "Alerts", "Projections", "History", "Value",
    ]);
  });
  it("uses position-specific Game Log columns and full school names", () => {
    expect(gameLogColumnsForPosition("TE").map(([label]) => label)).toEqual([
      "FPTS", "TAR", "REC", "REC YDS", "REC TD",
    ]);
    expect(gameLogOpponentLabel({ location: "away", opponent_name: "Ohio State" })).toBe("at Ohio State");
    expect(formatGameLogDate("2026-09-05")).toBe("Sep 5, 2026");
  });

  it("adds only completed final box scores into the 2026 season totals", () => {
    const totals = completedSeasonGameTotals([
      {
        schedule_id: 1,
        week: 1,
        location: "home",
        location_label: "Home",
        neutral_site: false,
        conference_game: false,
        game_status: "final",
        stat_status: "final",
        stats: { source: "espn_final_boxscore", updated_at: "2026-08-29T20:00:00Z", fantasy_points: 25.4, stats: { pass_yards: 280, pass_tds: 3, completions: 20, passing_attempts: 30 } },
      },
      {
        schedule_id: 2,
        week: 2,
        location: "away",
        location_label: "Away",
        neutral_site: false,
        conference_game: false,
        game_status: "active",
        stat_status: "active",
        stats: { source: "espn", updated_at: "2026-09-05T20:00:00Z", fantasy_points: 30, stats: { pass_yards: 300, pass_tds: 4 } },
      },
    ], "QB");

    expect(totals.gamesPlayed).toBe(1);
    expect(totals.totals).toContainEqual(["FPTS", 25.4]);
    expect(totals.totals).toContainEqual(["PASS YDS", 280]);
    expect(totals.totals).toContainEqual(["PASS TD", 3]);
    expect(totals.totals).not.toContainEqual(["PASS YDS", 580]);
  });

  it("labels player news with its Eastern report date and time", () => {
    expect(formatPlayerNewsReportTime("2026-08-24T16:58:00Z")).toBe("Report · 8/24/26, 12:58 PM ET");
    expect(formatPlayerNewsReportTime(null)).toBe("Report time unavailable");
    expect(formatPlayerNewsReportTime("not-a-date")).toBe("Report time unavailable");
  });
  it("formats empty player-card fields with an em dash fallback", () => {
    expect(formatPlayerCardValue(null)).toBe("—");
    expect(formatPlayerCardValue(undefined)).toBe("—");
    expect(formatPlayerCardValue("")).toBe("—");
  });

  it("formats finite numeric player-card fields for display", () => {
    expect(formatPlayerCardValue(1305)).toBe("1,305");
    expect(formatPlayerCardValue(Number.NaN)).toBe("—");
  });

  it("uses the canonical current-value label and an explicit unavailable state", () => {
    expect(CURRENT_VALUE_RATING_LABEL).toBe("Current Value Rating");
    expect(formatCurrentValueRating(85)).toBe("85");
    expect(formatCurrentValueRating(null)).toBe("N/A");
  });

  it("uses the same loaded CFB 27 rating for every player-card rating display", () => {
    expect(resolvePlayerCardCfb27Rating({ player: { cfb27_overall: 90 } } as never, 73)).toBe(90);
    expect(resolvePlayerCardCfb27Rating(null, 73)).toBe(73);
    expect(resolvePlayerCardCfb27Rating(null, null)).toBeNull();
  });

  it("keeps a canonical card value visible while the trade-value cache revalidates", () => {
    const archCard = {
      player: {
        id: 6,
        name: "Arch Manning",
        position: "QB",
        school: "Texas",
        raw_cfb27_rating: 91,
        current_value_rating: 91,
      },
    } as never;

    expect(resolvePlayerCardCurrentValueRating(undefined, archCard)).toBe(91);
    expect(resolvePlayerCardCurrentValueRating(91, archCard)).toBe(91);
    expect(resolvePlayerCardCurrentValueRating(null, { player: { raw_cfb27_rating: null, current_value_rating: null } } as never)).toBeNull();
  });

  it("shows a drafted player's round, pick, and overall selection in league history", () => {
    expect(draftHistorySummary({ event_type: "AUTO_DRAFTED", metadata: { round: 4, pick_in_round: 4, overall_pick: 16 } })).toBe(
      "Round 4 • Pick 4 • Overall 16"
    );
  });

  it("uses a position-specific palette when available and a default otherwise", () => {
    expect(getPlayerCardPalette("RB").pill).toContain("emerald");
    expect(getPlayerCardPalette("UNKNOWN").pill).toContain("cyan");
  });

  it("suppresses provider-ID placeholder messages but keeps meaningful notes", () => {
    expect(visiblePlayerCardAboutMessage("No ESPN player ID is set for this player.")).toBeNull();
    expect(visiblePlayerCardAboutMessage("No trusted ESPN player match is linked to this player.")).toBeNull();
    expect(visiblePlayerCardAboutMessage("Imported provider stats are still refreshing.")).toBe(
      "Imported provider stats are still refreshing."
    );
  });

  it("uses only season-sheet totals for the season projection section", () => {
    const projectedStats = resolvePlayerCardProjectionStats(
      {
        id: 5278,
        name: "Ian Strong",
        school: "California",
        position: "WR",
        projectedPoints: 294.9,
        hasWeeklyProjection: true,
      },
      {
        player: {
          id: 5278,
          name: "Ian Strong",
          position: "WR",
          school: "California",
          sheet_projected_season_points: 199.5,
          sheet_projection_stats: {
            receptions: 63,
            rec_yds: 925,
            rec_tds: 7,
          },
        } as never,
        about: { source: "local" },
        injuries: [],
        season_stats: [],
        historical_stats: null,
      }
    );

    expect(statValue(projectedStats, ["receptions"])).toBe(63);
    expect(statValue(projectedStats, ["rec_yds"])).toBe(925);
    expect(statValue(projectedStats, ["rec_tds"])).toBe(7);
    expect(statValue(projectedStats, ["fpts"])).toBe(199.5);
  });

  it("does not treat weekly matchup ranges as season totals", () => {
    const seasonProjectionStats = resolvePlayerCardProjectionStats({
      id: 12,
      name: "Lanorris Sellers",
      school: "South Carolina",
      position: "QB",
      projectedPoints: 23.4,
      projection: {
        fpts: 23.4,
        floor: 14.2,
        ceiling: 34.8,
        boomProb: 0.31,
        bustProb: 0.16,
      },
    });

    expect(seasonProjectionStats).toBeNull();
  });

});
