import type { LeagueSettingsTabResponse } from "@/types/league";

const POST_DRAFT_LEAGUE_STATUSES = new Set(["post_draft", "active", "playoffs", "completed", "archived"]);
const POST_DRAFT_DRAFT_STATUSES = new Set(["completed", "complete"]);

const normalizeStatus = (value: unknown) => String(value ?? "").trim().toLowerCase();

export function draftStatusForLeague(settings?: LeagueSettingsTabResponse | null) {
  return normalizeStatus(settings?.draft_status ?? settings?.league_info?.draft_status);
}

export function leagueStatusForLeague(settings?: LeagueSettingsTabResponse | null) {
  return normalizeStatus(settings?.league_status ?? settings?.league_info?.status);
}

export function isPostDraftLeague(settings?: LeagueSettingsTabResponse | null) {
  const draftStatus = draftStatusForLeague(settings);
  if (draftStatus) return POST_DRAFT_DRAFT_STATUSES.has(draftStatus);

  const leagueStatus = leagueStatusForLeague(settings);
  return POST_DRAFT_LEAGUE_STATUSES.has(leagueStatus);
}

export function isPreDraftLeague(settings?: LeagueSettingsTabResponse | null) {
  if (!settings) return false;
  return !isPostDraftLeague(settings);
}
