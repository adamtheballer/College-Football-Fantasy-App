import { describe, expect, it } from "vitest";

import { statValue } from "@/lib/playerProjectionStats";

import {
  formatGameLogDate,
  gameLogColumnsForPosition,
  gameLogOpponentLabel,
  buildHistoricalSeasonSummaryColumns,
  buildHistoricalStatsTableRows,
  draftHistorySummary,
  formatPlayerCardValue,
  getPlayerCardPalette,
  historicalSeasonSummaryValue,
  resolvePlayerCardCfb27Rating,
  resolvePlayerCardProjectionStats,
  visiblePlayerCardAboutMessage,
  visiblePlayerCardTabs,
} from "./PlayerCardModal";
import { CURRENT_VALUE_RATING_LABEL, formatCurrentValueRating } from "./PlayerCardHeader";

describe("PlayerCardModal helpers", () => {
  it("always shows the History tab, with league context controlling its contents", () => {
    expect(visiblePlayerCardTabs(false).map((tab) => tab.label)).toEqual([
      "Summary", "Stats", "Game Log", "Alerts", "Projections", "History", "Value",
    ]);
    expect(visiblePlayerCardTabs(true).map((tab) => tab.label)).toEqual([
      "Summary", "Stats", "Game Log", "Alerts", "Projections", "History", "Value",
    ]);
  });
  it("uses position-specific Game Log columns and full school names", () => {
    expect(gameLogColumnsForPosition("TE").map(([label]) => label)).toEqual([
      "FPTS", "REC", "TAR", "REC YDS", "REC TD",
    ]);
    expect(gameLogOpponentLabel({ location: "away", opponent_name: "Ohio State" })).toBe("at Ohio State");
    expect(formatGameLogDate("2026-09-05")).toBe("Sep 5, 2026");
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

  it("uses sheet projection stats from the loaded card when the selected row has none", () => {
    const projectedStats = resolvePlayerCardProjectionStats(
      {
        id: 5278,
        name: "Ian Strong",
        school: "California",
        position: "WR",
        projectedPoints: 294.9,
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
    expect(statValue(projectedStats, ["fpts"])).toBe(294.9);
  });

  it("keeps weekly matchup projection ranges on roster player cards", () => {
    const projectedStats = resolvePlayerCardProjectionStats({
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

    expect(statValue(projectedStats, ["fpts"])).toBe(23.4);
    expect(statValue(projectedStats, ["floor"])).toBe(14.2);
    expect(statValue(projectedStats, ["ceiling"])).toBe(34.8);
    expect(statValue(projectedStats, ["boomProb"])).toBe(0.31);
    expect(statValue(projectedStats, ["bustProb"])).toBe(0.16);
  });

  it("flattens ESPN historical categories into organized table rows", () => {
    const rows = buildHistoricalStatsTableRows({
      season: 2025,
      season_type: "regular",
      summary: [],
      categories: [
        {
          key: "rushing",
          label: "Rushing",
          stats: [
            { label: "Attempts", value: 173 },
            { label: "Yards", value: 947 },
          ],
        },
        {
          key: "receiving",
          label: "Receiving",
          stats: [{ label: "Receptions", value: 16 }],
        },
      ],
      freshness: { provider: "espn", is_final: false },
      scoring_context: {},
    });

    expect(rows).toEqual([
      { category: "Rushing", label: "Attempts", value: 173 },
      { category: "Rushing", label: "Yards", value: 947 },
      { category: "Receiving", label: "Receptions", value: 16 },
    ]);
  });

  it("builds one consistent set of stat-table columns for every historical season", () => {
    const seasons = [
      {
        season: 2025,
        season_type: "regular",
        summary: [{ label: "Fantasy Pts", value: 212.3 }, { label: "Rush Yds", value: 1047 }],
        categories: [],
        freshness: { provider: "verified_import", is_final: true },
        scoring_context: {},
      },
      {
        season: 2024,
        season_type: "regular",
        summary: [{ label: "Fantasy Pts", value: 164.1 }, { label: "Rec Yds", value: 812 }],
        categories: [],
        freshness: { provider: "verified_import", is_final: true },
        scoring_context: {},
      },
    ] as never;

    expect(buildHistoricalSeasonSummaryColumns(seasons)).toEqual(["Fantasy Points", "Rush Yds", "Rec Yds"]);
    expect(historicalSeasonSummaryValue(seasons[0], "Fantasy Points")).toBe(212.3);
    expect(historicalSeasonSummaryValue(seasons[1], "Rec Yds")).toBe(812);
    expect(historicalSeasonSummaryValue(seasons[1], "Rush Yds")).toBeNull();
  });
});
