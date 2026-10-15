import type { LeagueMatchupTabResponse, LeagueMatchupTeam } from "@/types/league";

export function currentRecordHighlight(
  data: LeagueMatchupTabResponse,
  team: LeagueMatchupTeam | null,
  leagueId: number,
  season: number | undefined,
  now = Date.now(),
): "win" | "loss" | null {
  if (!team || data.league_id !== leagueId || season === undefined || data.season !== season ||
      !data.matchup_id || data.week !== data.current_matchup_week ||
      !["final", "stat_corrected"].includes((data.status ?? "").toLowerCase())) return null;
  if (data.matchup_week_rollover_at != null) {
    const rollover = Date.parse(data.matchup_week_rollover_at);
    if (!Number.isFinite(rollover) || now >= rollover) return null;
  }
  const counts = typeof team.record === "string" ? /^(\d+)-(\d+)-(\d+)$/.exec(team.record) : null;
  if (!counts) return null;
  const result = team.record_highlight;
  if (result !== "win" && result !== "loss") return null;
  const updatedCount = Number(counts[result === "win" ? 1 : 2]);
  return Number.isSafeInteger(updatedCount) && updatedCount > 0 ? result : null;
}

// Used only by the Matchup page. Keep the original inline record/spacing.
export function MatchupRecord({ record, highlight }: { record: string; highlight: "win" | "loss" | null }) {
  const parts = /^(\d+)-(\d+)-(\d+)$/.exec(record);
  if (!parts) return <>{record}</>;
  return <><span data-record-count="wins" className={highlight === "win" ? "text-emerald-300" : undefined}>{parts[1]}</span>-<span data-record-count="losses" className={highlight === "loss" ? "text-red-400" : undefined}>{parts[2]}</span>-<span data-record-count="ties">{parts[3]}</span></>;
}
