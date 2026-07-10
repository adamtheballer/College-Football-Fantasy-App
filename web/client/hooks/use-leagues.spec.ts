import { describe, expect, it } from "vitest";

import { mergeDraftIntoLeagueDetail } from "./use-leagues";
import type { DraftInfo, LeagueDetail } from "@/types/league";

const leagueDetail: LeagueDetail = {
  id: 7,
  name: "Saturday League",
  commissioner_user_id: 1,
  season_year: 2026,
  max_teams: 4,
  is_private: true,
  invite_code: "INVITE",
  status: "scheduled",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  settings: {
    id: 1,
    league_id: 7,
    scoring_json: {},
    roster_slots_json: {},
    playoff_teams: 2,
    waiver_type: "rolling",
    trade_review_type: "commissioner",
    superflex_enabled: false,
    kicker_enabled: true,
    defense_enabled: false,
  },
  draft: {
    id: 3,
    league_id: 7,
    draft_datetime_utc: "2026-07-10T00:00:00Z",
    timezone: "America/New_York",
    draft_type: "snake",
    pick_timer_seconds: 90,
    status: "scheduled",
  },
  members: [],
};

const updatedDraft: DraftInfo = {
  id: 3,
  league_id: 7,
  draft_datetime_utc: "2026-07-20T01:15:00Z",
  timezone: "America/New_York",
  draft_type: "snake",
  pick_timer_seconds: 120,
  status: "scheduled",
};

describe("mergeDraftIntoLeagueDetail", () => {
  it("replaces the cached draft after rescheduling without dropping league data", () => {
    const merged = mergeDraftIntoLeagueDetail(leagueDetail, updatedDraft);

    expect(merged?.draft).toEqual(updatedDraft);
    expect(merged?.id).toBe(leagueDetail.id);
    expect(merged?.settings).toBe(leagueDetail.settings);
    expect(merged?.members).toBe(leagueDetail.members);
  });

  it("leaves an empty cache entry empty", () => {
    expect(mergeDraftIntoLeagueDetail(undefined, updatedDraft)).toBeUndefined();
  });
});
