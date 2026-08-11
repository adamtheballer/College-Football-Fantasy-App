import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, AlertTriangle, BarChart3, CalendarDays, History, Info, Loader2 } from "lucide-react";

import { useLeaguePlayerHistory, usePlayerGameLog, usePlayerTradeValues, usePlayerTrajectory, type PlayerCardResponse } from "@/hooks/use-players";
import {
  getHistoricalStatColumnsForPosition,
  historicalStatValuesForSeason,
  historicalStatsTablePosition,
} from "@/lib/historicalStatColumns";
import { buildProjectedStats, formatStat, statRowsForPosition, statValue } from "@/lib/playerProjectionStats";
import { cn } from "@/lib/utils";
import type { PlayerStats } from "@/types/player";

import { PlayerCardHeader, resolvePlayerCardStatus } from "./PlayerCardHeader";
import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

type PlayerCardTab = "summary" | "stats" | "game-log" | "alerts" | "projections" | "history" | "value";

export type PlayerCardModalPlayer = {
  id: number;
  name: string;
  school?: string | null;
  position?: string | null;
  rankLabel?: string | null;
  projectedPoints?: number | null;
  opponent?: string | null;
  playerClass?: string | null;
  status?: string | null;
  projection?: PlayerStats | null;
  sheetProjectionStats?: Record<string, number | null | undefined> | null;
  cfb27Overall?: number | null;
};

export type PlayerCardAction = {
  label: string;
  onClick: () => void;
};

type HistoricalSeason = NonNullable<PlayerCardResponse["historical_stats"]>["seasons"][number];
type HistoricalStatTableRow = {
  category: string;
  label: string;
  value: number | string | null;
};
const tabConfig: Array<{ id: PlayerCardTab; label: string; icon: typeof Info }> = [
  { id: "summary", label: "Summary", icon: Info },
  { id: "stats", label: "Stats", icon: BarChart3 },
  { id: "game-log", label: "Game Log", icon: CalendarDays },
  { id: "alerts", label: "Alerts", icon: AlertTriangle },
  { id: "projections", label: "Projections", icon: Activity },
  { id: "history", label: "History", icon: History },
  { id: "value", label: "Value", icon: Activity },
];

export const visiblePlayerCardTabs = (_hasLeagueContext: boolean) => tabConfig;

const positionPalettes: Record<
  string,
  {
    headerBase: string;
    markerA: string;
    markerB: string;
    markerC: string;
    glow: string;
    accent: string;
    pill: string;
    silhouette: string;
  }
> = {
  QB: {
    headerBase: "bg-blue-950",
    markerA: "rgba(96,165,250,0.28)",
    markerB: "rgba(14,165,233,0.22)",
    markerC: "rgba(15,23,42,0.34)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-blue-100",
    pill: "border-blue-200/45 bg-blue-200/15 text-blue-50",
    silhouette: "from-blue-200/35 via-blue-100/20 to-transparent",
  },
  RB: {
    headerBase: "bg-emerald-950",
    markerA: "rgba(52,211,153,0.24)",
    markerB: "rgba(20,184,166,0.20)",
    markerC: "rgba(6,78,59,0.42)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-emerald-100",
    pill: "border-emerald-200/45 bg-emerald-200/15 text-emerald-50",
    silhouette: "from-emerald-200/35 via-emerald-100/20 to-transparent",
  },
  WR: {
    headerBase: "bg-violet-950",
    markerA: "rgba(167,139,250,0.28)",
    markerB: "rgba(217,70,239,0.18)",
    markerC: "rgba(76,29,149,0.42)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-violet-100",
    pill: "border-violet-200/45 bg-violet-200/15 text-violet-50",
    silhouette: "from-violet-200/35 via-violet-100/20 to-transparent",
  },
  TE: {
    headerBase: "bg-amber-950",
    markerA: "rgba(251,191,36,0.26)",
    markerB: "rgba(249,115,22,0.24)",
    markerC: "rgba(120,53,15,0.42)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-amber-100",
    pill: "border-amber-200/45 bg-amber-200/15 text-amber-50",
    silhouette: "from-amber-200/35 via-amber-100/20 to-transparent",
  },
  K: {
    headerBase: "bg-slate-900",
    markerA: "rgba(203,213,225,0.18)",
    markerB: "rgba(100,116,139,0.22)",
    markerC: "rgba(15,23,42,0.45)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-slate-100",
    pill: "border-slate-200/40 bg-slate-200/15 text-slate-50",
    silhouette: "from-slate-200/30 via-slate-100/18 to-transparent",
  },
};

const defaultPalette = {
  headerBase: "bg-cyan-950",
  markerA: "rgba(34,211,238,0.24)",
  markerB: "rgba(59,130,246,0.20)",
  markerC: "rgba(14,116,144,0.42)",
  glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
  accent: "text-cyan-100",
  pill: "border-cyan-200/45 bg-cyan-200/15 text-cyan-50",
  silhouette: "from-cyan-200/35 via-cyan-100/20 to-transparent",
};

export const formatPlayerCardValue = (value: unknown, fallback = "—") => {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : fallback;
  return String(value);
};

export const resolvePlayerCardCfb27Rating = (
  card?: PlayerCardResponse | null,
  contextualRating?: number | null,
) => card?.player.cfb27_overall ?? contextualRating ?? null;

export const draftHistorySummary = (event: { event_type: string; metadata?: Record<string, unknown> | null }) => {
  if (event.event_type !== "DRAFTED" && event.event_type !== "AUTO_DRAFTED") return null;
  const metadata = event.metadata ?? {};
  const round = metadata.round ?? metadata.round_number;
  const pick = metadata.pick_in_round ?? metadata.round_pick;
  const overall = metadata.overall_pick;
  const segments = [
    round !== undefined && round !== null ? `Round ${round}` : null,
    pick !== undefined && pick !== null ? `Pick ${pick}` : null,
    overall !== undefined && overall !== null ? `Overall ${overall}` : null,
  ].filter(Boolean);
  return segments.length ? segments.join(" • ") : null;
};

export const getPlayerCardPalette = (position?: string | null) =>
  positionPalettes[(position ?? "").toUpperCase()] ?? defaultPalette;

const getStatValue = (stats: Record<string, unknown> | null | undefined, keys: readonly string[]) => {
  if (!stats) return null;
  for (const key of keys) {
    const value = stats[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
};

const gameLogStatValue = (stats: Record<string, unknown> | null | undefined, keys: readonly string[]) =>
  getStatValue(stats, keys);

type GameLogColumn = readonly [label: string, keys: readonly string[]];

export const gameLogColumnsForPosition = (position: string): readonly GameLogColumn[] => {
  switch (position.toUpperCase()) {
    case "QB":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["CMP", ["completions", "passing_completions", "PassingCompletions"]],
        ["ATT", ["attempts", "passing_attempts", "PassingAttempts"]],
        ["PASS YDS", ["pass_yards", "passing_yards", "PassingYards"]],
        ["PASS TD", ["pass_tds", "passing_touchdowns", "PassingTouchdowns"]],
        ["INT", ["interceptions", "Interceptions"]],
        ["RUSH ATT", ["rushing_attempts", "rush_attempts", "RushingAttempts"]],
        ["RUSH YDS", ["rush_yards", "rushing_yards", "RushingYards"]],
        ["RUSH TD", ["rush_tds", "rushing_touchdowns", "RushingTouchdowns"]],
      ] as const;
    case "RB":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["RUSH ATT", ["rushing_attempts", "rush_attempts", "RushingAttempts"]],
        ["RUSH YDS", ["rush_yards", "rushing_yards", "RushingYards"]],
        ["RUSH TD", ["rush_tds", "rushing_touchdowns", "RushingTouchdowns"]],
        ["REC", ["receptions", "Receptions"]],
        ["TAR", ["targets", "receiving_targets", "ReceivingTargets"]],
        ["REC YDS", ["rec_yards", "receiving_yards", "ReceivingYards"]],
        ["REC TD", ["rec_tds", "receiving_touchdowns", "ReceivingTouchdowns"]],
      ] as const;
    case "WR":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["REC", ["receptions", "Receptions"]],
        ["TAR", ["targets", "receiving_targets", "ReceivingTargets"]],
        ["REC YDS", ["rec_yards", "receiving_yards", "ReceivingYards"]],
        ["REC TD", ["rec_tds", "receiving_touchdowns", "ReceivingTouchdowns"]],
        ["RUSH ATT", ["rushing_attempts", "rush_attempts", "RushingAttempts"]],
        ["RUSH YDS", ["rush_yards", "rushing_yards", "RushingYards"]],
        ["RUSH TD", ["rush_tds", "rushing_touchdowns", "RushingTouchdowns"]],
      ] as const;
    case "TE":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["REC", ["receptions", "Receptions"]],
        ["TAR", ["targets", "receiving_targets", "ReceivingTargets"]],
        ["REC YDS", ["rec_yards", "receiving_yards", "ReceivingYards"]],
        ["REC TD", ["rec_tds", "receiving_touchdowns", "ReceivingTouchdowns"]],
      ] as const;
    case "K":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["FGM", ["field_goals_made", "fieldGoalsMade", "FieldGoalsMade"]],
        ["FGA", ["field_goals_attempted", "fieldGoalsAttempted", "FieldGoalsAttempted"]],
        ["XPM", ["extra_points_made", "extraPointsMade", "ExtraPointsMade"]],
        ["XPA", ["extra_points_attempted", "extraPointsAttempted", "ExtraPointsAttempted"]],
      ] as const;
    default:
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["RUSH YDS", ["rush_yards", "rushing_yards", "RushingYards"]],
        ["RUSH TD", ["rush_tds", "rushing_touchdowns", "RushingTouchdowns"]],
        ["REC", ["receptions", "Receptions"]],
        ["REC YDS", ["rec_yards", "receiving_yards", "ReceivingYards"]],
        ["REC TD", ["rec_tds", "receiving_touchdowns", "ReceivingTouchdowns"]],
      ] as const;
  }
};

export const gameLogOpponentLabel = (row: { location: string; opponent_name?: string | null }) => {
  if (row.location === "bye") return "BYE";
  if (!row.opponent_name) return "TBD";
  if (row.location === "away") return `at ${row.opponent_name}`;
  if (row.location === "neutral") return `Neutral vs. ${row.opponent_name}`;
  return `vs. ${row.opponent_name}`;
};

export const formatGameLogDate = (value?: string | null) => {
  if (!value) return "Date TBD";
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isNaN(date.getTime())
    ? "Date TBD"
    : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
};

export const resolvePlayerCardProjectionStats = (
  player: PlayerCardModalPlayer,
  card?: PlayerCardResponse | null
) => {
  const sheetProjectionStats = player.sheetProjectionStats ?? card?.player.sheet_projection_stats ?? undefined;
  const projectedPoints =
    player.projectedPoints ??
    player.projection?.fpts ??
    card?.player.sheet_projected_season_points ??
    statValue(sheetProjectionStats, ["fpts", "fantasy_points", "projected_points", "projectedFantasyPoints"]) ??
    0;
  const projection = player.projection ?? { fpts: projectedPoints };

  if (!player.projection && !sheetProjectionStats && !card?.player.sheet_projected_season_points) return null;

  return buildProjectedStats(
    projection,
    projectedPoints,
    sheetProjectionStats
  );
};

/**
 * The card payload and the value endpoint expose the same canonical field.
 * Prefer the live value response, but retain the value embedded in the card
 * response while that secondary request is revalidating.  This keeps a
 * transient query failure or cold cache from turning a valid rating into N/A.
 */
export const resolvePlayerCardCurrentValueRating = (
  tradeValue?: number | null,
  card?: PlayerCardResponse | null,
) => {
  if (typeof tradeValue === "number" && Number.isFinite(tradeValue)) return tradeValue;
  const cardValue = card?.player.current_value_rating;
  return typeof cardValue === "number" && Number.isFinite(cardValue) ? cardValue : null;
};

export const buildHistoricalStatsTableRows = (season: HistoricalSeason | null): HistoricalStatTableRow[] =>
  season?.categories.flatMap((category) =>
    category.stats.map((stat) => ({
      category: category.label,
      label: stat.label,
      value: stat.value,
    }))
  ) ?? [];

export const buildHistoricalSeasonSummaryColumns = (
  seasons: HistoricalSeason[],
  currentPosition?: string | null,
): string[] => {
  const present = new Set(seasons.flatMap((season) => [...historicalStatValuesForSeason(season).keys()]));
  return getHistoricalStatColumnsForPosition(
    historicalStatsTablePosition(seasons, currentPosition),
    present,
  );
};

export const historicalSeasonSummaryValue = (season: HistoricalSeason, label: string) => {
  return historicalStatValuesForSeason(season).get(label) ?? null;
};

export const visiblePlayerCardAboutMessage = (message?: string | null) => {
  const trimmed = message?.trim();
  if (!trimmed) return null;
  const normalized = trimmed.toLowerCase();
  if (
    normalized.includes("no espn player id") ||
    normalized.includes("no trusted espn player match")
  ) {
    return null;
  }
  return trimmed;
};

export function PlayerCardModal({
  action,
  actions = [],
  card,
  error = false,
  loading = false,
  leagueId,
  onClose,
  onRetry,
  player,
  title = "Player Card",
}: {
  action?: PlayerCardAction | null;
  actions?: PlayerCardAction[];
  card?: PlayerCardResponse | null;
  error?: boolean;
  loading?: boolean;
  leagueId?: number | null;
  onClose: () => void;
  onRetry?: () => void;
  player: PlayerCardModalPlayer;
  title?: string;
}) {
  const [activeTab, setActiveTab] = useState<PlayerCardTab>("summary");
  const historicalStatsScrollRef = useRef<HTMLDivElement>(null);
  const hasLeagueContext = typeof leagueId === "number" && Number.isFinite(leagueId) && leagueId > 0;
  const position = (card?.about.position ?? player.position ?? "").toUpperCase();
  const playerStatus = resolvePlayerCardStatus(card, player.status);
  const gameLogQuery = usePlayerGameLog(player.id, 2026, activeTab === "game-log");
  const historyQuery = useLeaguePlayerHistory(leagueId ?? undefined, player.id, activeTab === "history" && hasLeagueContext);
  const valueQuery = usePlayerTradeValues(player.id, 2026);
  const trajectoryQuery = usePlayerTrajectory(
    player.id,
    2026,
    leagueId,
    activeTab === "projections" || activeTab === "value",
  );
  const palette = getPlayerCardPalette(position);
  const historicalStats = card?.historical_stats;
  const historicalSeasons = historicalStats?.seasons ?? [];
  const historicalTablePosition = historicalStatsTablePosition(historicalSeasons, position);
  const historicalSummaryColumns = buildHistoricalSeasonSummaryColumns(historicalSeasons, historicalTablePosition);
  const projectionStats = useMemo(() => resolvePlayerCardProjectionStats(player, card), [player, card]);
  const currentValueRating = resolvePlayerCardCurrentValueRating(
    valueQuery.data?.current?.current_value_rating,
    card,
  );
  const aboutMessage = visiblePlayerCardAboutMessage(card?.about.message);
  const cardActions = [...(action ? [action] : []), ...actions];

  useEffect(() => {
    if (historicalStatsScrollRef.current) historicalStatsScrollRef.current.scrollLeft = 0;
  }, [player.id, historicalTablePosition]);
  const projectionHighlights = [
    ["Fantasy", projectionStats?.fpts ?? player.projectedPoints],
    ["Floor", projectionStats?.floor],
    ["Ceiling", projectionStats?.ceiling],
    [
      "Boom",
      typeof projectionStats?.boomProb === "number" ? `${Math.round(projectionStats.boomProb * 100)}%` : null,
    ],
    [
      "Bust",
      typeof projectionStats?.bustProb === "number" ? `${Math.round(projectionStats.bustProb * 100)}%` : null,
    ],
    ["Opponent", player.opponent],
  ] as Array<[string, unknown]>;
  const visibleProjectionHighlights = projectionHighlights.filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );
  const projectionRows = statRowsForPosition(position || player.position || "");
  const projectionDetailRows = projectionStats
    ? projectionRows
        .map((row) => [row.label, statValue(projectionStats, row.projectionKeys)] as const)
    .filter(([, value]) => value !== null)
    : [];
  useEffect(() => {
    setActiveTab("summary");
  }, [player.id]);

  return (
    <div
      className="fixed inset-0 z-[1400] flex items-end justify-center bg-slate-950/78 p-3 backdrop-blur-md sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`${player.name} player card`}
      onClick={onClose}
    >
      <article
        className={cn(
          "relative flex h-[82dvh] max-h-[82dvh] w-full max-w-5xl flex-col overflow-hidden rounded-[1.75rem] border border-white/12 bg-[#0b0d10] text-white shadow-[0_28px_80px_rgba(2,6,23,0.62)] sm:h-auto sm:max-h-[92vh] sm:rounded-xl",
          palette.glow
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <PlayerCardHeader
          card={card}
          currentValue={currentValueRating}
          onClose={onClose}
          palette={palette}
          player={player}
          position={position}
          title={title}
        />

        <nav className="flex gap-1 overflow-x-auto border-b border-white/10 bg-black/18 px-3 pt-1 sm:gap-3 sm:flex-wrap sm:overflow-visible sm:px-8 sm:pt-2">
          {visiblePlayerCardTabs(hasLeagueContext).map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "relative inline-flex shrink-0 items-center gap-1.5 px-2 py-2.5 text-[9px] font-bold uppercase tracking-[0.06em] transition after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-transparent sm:gap-2 sm:px-1 sm:text-[10px] sm:font-black sm:tracking-[0.12em]",
                  active
                    ? "text-white after:bg-cfb-brand"
                    : "text-white/55 hover:text-white"
                )}
              >
                <Icon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-8">
          {loading ? (
            <div className="flex min-h-56 items-center justify-center gap-3 rounded-3xl border border-white/10 bg-white/[0.04] text-[10px] font-black uppercase tracking-[0.22em] text-white/55">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading player card
            </div>
          ) : error ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-4 rounded-3xl border border-amber-300/20 bg-amber-400/10 p-6 text-center">
              <p className="text-sm font-black text-amber-50">Player details are unavailable right now.</p>
              <p className="text-xs font-bold leading-5 text-amber-100/75">The player card stayed open. Please try again.</p>
              {onRetry ? (
                <button
                  type="button"
                  onClick={onRetry}
                  className="rounded-2xl border border-amber-100/30 bg-amber-50 px-4 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-amber-950 transition hover:bg-white"
                >
                  Retry
                </button>
              ) : null}
            </div>
          ) : activeTab === "summary" ? (
            <div className="w-full">
              <section className="rounded-2xl border border-white/10 bg-white/[0.045] p-4 sm:rounded-3xl sm:p-5">
                <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Bio</p>
                <div className="mt-3 grid grid-cols-2 gap-2 sm:mt-4 sm:gap-3">
                  {[
                    ["Height", card?.about.height],
                    ["Weight", card?.about.weight],
                    ["Class", card?.about.player_class ?? player.playerClass],
                    ["Born", card?.about.birthplace],
                    ["School", card?.about.team ?? player.school],
                    ["Status", playerStatus],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-white/10 bg-black/20 p-2.5 sm:rounded-2xl sm:p-3">
                      <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                      <p className="mt-1 text-sm font-black text-white sm:mt-2">{formatPlayerCardValue(value)}</p>
                    </div>
                  ))}
                </div>
                {aboutMessage ? (
                  <p className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-400/10 p-3 text-xs font-bold leading-5 text-amber-100">
                    {aboutMessage}
                  </p>
                ) : null}
                {cardActions.length ? (
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {cardActions.map((cardAction) => (
                      <button
                        key={cardAction.label}
                        type="button"
                        onClick={cardAction.onClick}
                        className="inline-flex w-full items-center justify-center rounded-2xl border border-white/15 bg-white px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-950 transition hover:bg-cyan-100"
                      >
                        {cardAction.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </section>
            </div>
          ) : activeTab === "stats" ? (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>
                    Historical Season Stats
                  </p>
                  <p className="mt-2 text-sm font-bold leading-6 text-white/55">
                    Verified season totals, with one row for each year this player has recorded stats.
                  </p>
                </div>
                <p className="w-fit rounded-full border border-white/15 bg-white/[0.05] px-3 py-2 text-[9px] font-black uppercase tracking-[0.16em] text-white/55">
                  {position || "Player"}
                </p>
              </div>

              {historicalSeasons.length ? (
                <div ref={historicalStatsScrollRef} className="mt-5 overflow-x-auto overscroll-x-contain touch-pan-x rounded-3xl border border-white/10 bg-black/20" aria-label="Historical stats table; scroll horizontally for all columns">
                  <table className="min-w-[1050px] w-max border-collapse text-left">
                    <thead className="bg-white/[0.055] text-[9px] font-black uppercase tracking-[0.16em] text-white/45">
                      <tr>
                        <th className="min-w-[5.5rem] whitespace-nowrap px-4 py-4">Year</th>
                        <th className="min-w-36 whitespace-nowrap px-4 py-4">Team</th>
                        <th className="min-w-[4.5rem] whitespace-nowrap px-4 py-4">Pos</th>
                        {historicalSummaryColumns.map((label) => (
                          <th key={label} className="whitespace-nowrap px-4 py-4 text-right">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {historicalSeasons.map((season) => (
                        <tr key={`${season.season}-${season.team_name ?? "team"}-${season.season_type}`} className="text-sm font-bold text-white/75 transition hover:bg-white/[0.035]">
                          <td className="whitespace-nowrap px-4 py-5 text-xl font-black tabular-nums text-white">{season.season}</td>
                          <td className="min-w-36 px-4 py-5"><p className="font-black text-white">{season.team_name ?? card?.about.team ?? player.school}</p><p className="mt-1 text-[9px] font-black uppercase tracking-[0.14em] text-white/45">{season.season_type}</p></td>
                          <td className="px-4 py-5"><span className="rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[9px] font-black uppercase tracking-[0.14em] text-white/70">{season.position ?? position ?? "—"}</span></td>
                          {historicalSummaryColumns.map((label) => (
                            <td key={label} className="px-4 py-5 text-right font-black tabular-nums text-white">
                              {formatPlayerCardValue(historicalSeasonSummaryValue(season, label))}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  {historicalStats?.message ??
                    "No imported historical season stats are linked to this player yet."}
                </p>
              )}
            </section>
          ) : activeTab === "game-log" ? (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>2026 Game Log</p>
                  <p className="mt-2 text-sm font-bold leading-6 text-white/55">
                    {gameLogQuery.data?.team_name ?? card?.about.team ?? player.school} schedule. Completed game stats appear here after they are verified.
                  </p>
                </div>
                <p className="rounded-full border border-white/15 bg-white/[0.05] px-3 py-2 text-[9px] font-black uppercase tracking-[0.16em] text-white/55">
                  {position || "Player"}
                </p>
              </div>
              {gameLogQuery.isLoading ? (
                <div className="mt-5 flex min-h-40 items-center justify-center gap-3 rounded-2xl border border-white/10 bg-black/20 text-[10px] font-black uppercase tracking-[0.18em] text-white/55">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading schedule
                </div>
              ) : gameLogQuery.isError ? (
                <p className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm font-bold leading-6 text-amber-100">
                  The Game Log is unavailable right now. Please try again shortly.
                </p>
              ) : gameLogQuery.data?.games.length ? (
                <>
                <div className="mt-5 hidden overflow-x-auto rounded-2xl border border-white/10 bg-black/20 md:block">
                  <table className="min-w-max border-collapse text-left">
                    <thead className="bg-white/[0.055] text-[9px] font-black uppercase tracking-[0.16em] text-white/45">
                      <tr>
                        <th className="min-w-[4.5rem] whitespace-nowrap px-4 py-3">Week</th>
                        <th className="min-w-[15rem] whitespace-nowrap px-4 py-3">Opponent</th>
                        <th className="min-w-[8rem] whitespace-nowrap px-4 py-3">Location</th>
                        <th className="min-w-[5.5rem] whitespace-nowrap px-4 py-3">Result</th>
                        {gameLogColumnsForPosition(position).map(([label]) => (
                          <th key={label} className="whitespace-nowrap px-4 py-3 text-right">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {gameLogQuery.data.games.map((row) => {
                        const stats = row.stats?.stats;
                        return (
                          <tr key={row.schedule_id} className="text-sm font-bold text-white/75">
                            <td className="px-4 py-4 font-black tabular-nums text-white">{row.week}</td>
                            <td className="px-4 py-4">
                              <p className="font-black text-white">{gameLogOpponentLabel(row)}</p>
                              <p className="mt-1 text-[10px] font-bold text-white/40">{formatGameLogDate(row.date)}</p>
                            </td>
                            <td className="whitespace-nowrap px-4 py-4 text-[10px] font-black uppercase tracking-[0.16em] text-white/55">{row.location_label}</td>
                            <td className="whitespace-nowrap px-4 py-4 text-xs font-black tabular-nums text-white/70">{row.result ?? "—"}</td>
                            {gameLogColumnsForPosition(position).map(([label, keys]) => {
                              const value = row.location === "bye" ? null : gameLogStatValue(stats, keys);
                              return (
                                <td key={label} className="whitespace-nowrap px-4 py-4 text-right font-black tabular-nums text-white">
                                  {formatPlayerCardValue(value)}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-5 space-y-3 md:hidden">
                  {gameLogQuery.data.games.map((row) => {
                    const stats = row.stats?.stats;
                    return (
                      <article key={row.schedule_id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-white/45">Week {row.week}</p>
                            <p className="mt-1 font-black text-white">{gameLogOpponentLabel(row)}</p>
                            <p className="mt-1 text-xs font-bold text-white/45">{formatGameLogDate(row.date)} • {row.location_label}</p>
                          </div>
                          <p className="text-right text-xs font-black tabular-nums text-white/70">{row.result ?? "—"}</p>
                        </div>
                        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
                          {gameLogColumnsForPosition(position).map(([label, keys]) => {
                            const value = row.location === "bye" ? null : gameLogStatValue(stats, keys);
                            return (
                              <div key={label} className="flex items-center justify-between gap-3 text-xs">
                                <span className="font-black uppercase tracking-[0.12em] text-white/45">{label}</span>
                                <span className="font-black tabular-nums text-white">{formatPlayerCardValue(value)}</span>
                              </div>
                            );
                          })}
                        </div>
                      </article>
                    );
                  })}
                </div>
                </>
              ) : (
                <p className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  {gameLogQuery.data?.message ?? "No 2026 schedule has been imported for this player's team yet."}
                </p>
              )}
            </section>
          ) : activeTab === "alerts" ? (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>News / Injury Alerts</p>
              {card?.injuries.length ? (
                <div className="mt-5 space-y-3">
                  {card.injuries.map((injury) => (
                    <div key={injury.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-base font-black text-white">{injury.status}</p>
                        <p className="text-[9px] font-black uppercase tracking-[0.16em] text-white/45">
                          {injury.season} W{injury.week}
                        </p>
                      </div>
                      <p className="mt-2 text-sm font-bold leading-6 text-white/70">
                        {[injury.injury, injury.practice_level, injury.return_timeline].filter(Boolean).join(" • ") ||
                          "No injury detail provided."}
                      </p>
                      {injury.notes ? <p className="mt-2 text-xs leading-5 text-white/50">{injury.notes}</p> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  No verified injury alerts are recorded for this player.
                </p>
              )}
            </section>
          ) : activeTab === "projections" ? (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Fantasy Projection</p>
              <div className="mt-5">
                {trajectoryQuery.isLoading ? (
                  <div className="flex min-h-56 items-center justify-center gap-3 rounded-3xl border border-white/10 bg-black/20 text-[10px] font-black uppercase tracking-[0.18em] text-white/55">
                    <Loader2 className="h-4 w-4 animate-spin" /> Building season trajectory
                  </div>
                ) : trajectoryQuery.data?.projection.length ? (
                  <>
                    {typeof trajectoryQuery.data.preseason_projection_points === "number" ? (
                      <p className="mb-3 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm font-bold text-white/65">
                        Preseason season projection: <span className="font-black text-white">{trajectoryQuery.data.preseason_projection_points.toFixed(1)} pts</span>
                      </p>
                    ) : null}
                    <PlayerTrajectoryChart
                      ariaLabel={`${player.name} projected fantasy points by week`}
                      points={trajectoryQuery.data.projection.map((point) => ({ ...point, value: point.points }))}
                      yLabel="Points"
                      yMax={30}
                      valueFormatter={(value) => `${value.toFixed(1)} pts`}
                      seriesKind="projection"
                    />
                  </>
                ) : trajectoryQuery.data ? (
                  <div className="rounded-3xl border border-white/10 bg-black/20 p-5 text-sm font-bold leading-6 text-white/60">
                    {typeof trajectoryQuery.data.preseason_projection_points === "number" ? (
                      <p>Preseason season projection: <span className="font-black text-white">{trajectoryQuery.data.preseason_projection_points.toFixed(1)} pts</span></p>
                    ) : null}
                    <p className={typeof trajectoryQuery.data.preseason_projection_points === "number" ? "mt-2" : undefined}>Weekly projections have not been published yet.</p>
                  </div>
                ) : (
                  <p className="rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm font-bold text-rose-100">
                    Season projection trajectory is unavailable right now. Please try again shortly.
                  </p>
                )}
              </div>
              {projectionStats ? (
                <div className="mt-5 space-y-4">
                  {visibleProjectionHighlights.length ? (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                      {visibleProjectionHighlights.map(([label, value]) => (
                        <div key={label} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                          <p className="mt-2 truncate text-xl font-black tabular-nums text-white">
                            {typeof value === "number" ? formatStat(value) : formatPlayerCardValue(value)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {projectionDetailRows.length ? (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                      {projectionDetailRows.map(([label, value]) => (
                        <div key={label} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                          <p className="mt-2 text-xl font-black tabular-nums text-white">{formatStat(value)}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="rounded-2xl border border-cyan-300/15 bg-cyan-300/10 p-4 text-sm font-bold leading-6 text-cyan-100">
                      Weekly projection is available from the matchup model. Position stat splits are shown when the projection feed supplies them.
                    </p>
                  )}
                </div>
              ) : (
                <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  No detailed weekly stat split is linked to this card yet.
                </p>
              )}
            </section>
          ) : activeTab === "history" ? (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>League History</p>
              {!hasLeagueContext ? (
                <p className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  Open this player card from a league to view this player&apos;s draft, roster, trade, and waiver history.
                </p>
              ) : historyQuery.isLoading ? (
                <div className="mt-5 flex min-h-40 items-center justify-center gap-3 rounded-2xl border border-white/10 bg-black/20 text-[10px] font-black uppercase tracking-[0.18em] text-white/55"><Loader2 className="h-4 w-4 animate-spin" /> Loading league history</div>
              ) : historyQuery.isError ? (
                <p className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm font-bold text-rose-100">League history is unavailable right now. Please try again shortly.</p>
              ) : historyQuery.data ? (
                <div className="mt-5 space-y-3">
                  <div className="rounded-2xl border border-cyan-200/20 bg-cyan-200/10 p-4">
                    <p className="text-[9px] font-black uppercase tracking-[0.18em] text-cyan-100/70">Current status</p>
                    <p className="mt-1 text-lg font-black text-white">{historyQuery.data.current_status.status.replace(/_/g, " ")}{historyQuery.data.current_status.fantasy_team_name ? ` by ${historyQuery.data.current_status.fantasy_team_name}` : ""}</p>
                  </div>
                  {historyQuery.data.events.length ? historyQuery.data.events.map((event) => (
                    <article key={event.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-black text-white">{event.event_type.replace(/_/g, " ")}</p><p className="mt-1 text-xs font-bold text-white/55">{event.from_team?.name ? `${event.from_team.name} → ` : ""}{event.to_team?.name ?? event.fantasy_team?.name ?? "League transaction"}</p></div><p className="text-[10px] font-black uppercase tracking-[0.14em] text-white/45">{new Date(event.occurred_at).toLocaleString()}</p></div>
                      <p className="mt-2 text-xs font-bold text-white/55">{draftHistorySummary(event) ? `${draftHistorySummary(event)} • ` : ""}{event.position} • {event.school}{event.manager?.name ? ` • ${event.manager.name}` : ""}{typeof event.player_value_at_event === "number" ? ` • Value ${event.player_value_at_event.toFixed(1)}` : ""}</p>
                    </article>
                  )) : <p className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">No league history yet. This player has not been drafted, added, traded, or rostered in this league.</p>}
                </div>
              ) : null}
            </section>
          ) : (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Trade Value</p>
              <div className="mt-5">
                {trajectoryQuery.isLoading ? (
                  <div className="flex min-h-56 items-center justify-center gap-3 rounded-3xl border border-white/10 bg-black/20 text-[10px] font-black uppercase tracking-[0.18em] text-white/55">
                    <Loader2 className="h-4 w-4 animate-spin" /> Building value trajectory
                  </div>
                ) : trajectoryQuery.data ? (
                  <PlayerTrajectoryChart
                    ariaLabel={`${player.name} trade value by week`}
                    points={trajectoryQuery.data.value.map((point) => ({ ...point, value: point.value }))}
                    yLabel="Value"
                    yMax={100}
                    valueFormatter={(value) => value.toFixed(0)}
                    seriesKind="value"
                  />
                ) : (
                  <p className="rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm font-bold text-rose-100">
                    Season value trajectory is unavailable right now. Please try again shortly.
                  </p>
                )}
              </div>
              {!trajectoryQuery.isLoading && trajectoryQuery.data && !trajectoryQuery.data.value.some((point) => point.week > 0) ? <p className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">Player value history will appear as weekly snapshots are published.</p> : null}
            </section>
          )}
        </div>
      </article>
    </div>
  );
}
