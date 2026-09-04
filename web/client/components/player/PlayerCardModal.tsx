import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, CalendarDays, History, Info, Loader2, Newspaper } from "lucide-react";

import { useLeaguePlayerHistory, usePlayerGameLog, usePlayerTradeValues, usePlayerTrajectory, type PlayerCardResponse, type PlayerGameLogResponse } from "@/hooks/use-players";
import { buildProjectedStats, formatStat, statRowsForPosition, statValue } from "@/lib/playerProjectionStats";
import { cn } from "@/lib/utils";
import type { PlayerStats } from "@/types/player";

import { PlayerCardHeader, resolvePlayerCardStatus } from "./PlayerCardHeader";
import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

type PlayerCardTab = "news" | "summary" | "game-log" | "alerts" | "projections" | "history" | "value";

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
  hasWeeklyProjection?: boolean;
  seasonProjectedPoints?: number | null;
  sheetProjectionStats?: Record<string, number | null | undefined> | null;
  cfb27Overall?: number | null;
};

export type PlayerCardAction = {
  label: string;
  onClick: () => void;
};

const tabConfig: Array<{ id: PlayerCardTab; label: string; icon: typeof Info }> = [
  { id: "summary", label: "Summary", icon: Info },
  { id: "news", label: "News", icon: Newspaper },
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
    headerBase: "from-[#262967] via-[#1d4c86] to-[#0a2138]",
    markerA: "rgba(96,165,250,0.28)",
    markerB: "rgba(14,165,233,0.22)",
    markerC: "rgba(15,23,42,0.34)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-blue-100",
    pill: "border-blue-200/45 bg-blue-200/15 text-blue-50",
    silhouette: "from-blue-200/35 via-blue-100/20 to-transparent",
  },
  RB: {
    headerBase: "from-[#064b3c] via-[#0d6552] to-[#092d32]",
    markerA: "rgba(52,211,153,0.24)",
    markerB: "rgba(20,184,166,0.20)",
    markerC: "rgba(6,78,59,0.42)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-emerald-100",
    pill: "border-emerald-200/45 bg-emerald-200/15 text-emerald-50",
    silhouette: "from-emerald-200/35 via-emerald-100/20 to-transparent",
  },
  WR: {
    headerBase: "from-[#42206c] via-[#603791] to-[#211840]",
    markerA: "rgba(167,139,250,0.28)",
    markerB: "rgba(217,70,239,0.18)",
    markerC: "rgba(76,29,149,0.42)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-violet-100",
    pill: "border-violet-200/45 bg-violet-200/15 text-violet-50",
    silhouette: "from-violet-200/35 via-violet-100/20 to-transparent",
  },
  TE: {
    headerBase: "from-[#65410c] via-[#805213] to-[#35220d]",
    markerA: "rgba(251,191,36,0.26)",
    markerB: "rgba(249,115,22,0.24)",
    markerC: "rgba(120,53,15,0.42)",
    glow: "shadow-[0_18px_48px_rgba(0,0,0,0.46)]",
    accent: "text-amber-100",
    pill: "border-amber-200/45 bg-amber-200/15 text-amber-50",
    silhouette: "from-amber-200/35 via-amber-100/20 to-transparent",
  },
  K: {
    headerBase: "from-[#2b3e55] via-[#334e67] to-[#162434]",
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
  headerBase: "from-[#134f64] via-[#1b6681] to-[#0b2b3d]",
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
        ["REC YDS", ["rec_yards", "receiving_yards", "ReceivingYards"]],
        ["REC TD", ["rec_tds", "receiving_touchdowns", "ReceivingTouchdowns"]],
      ] as const;
    case "WR":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["TAR", ["targets", "receiving_targets", "ReceivingTargets"]],
        ["REC", ["receptions", "Receptions"]],
        ["REC YDS", ["rec_yards", "receiving_yards", "ReceivingYards"]],
        ["REC TD", ["rec_tds", "receiving_touchdowns", "ReceivingTouchdowns"]],
        ["RUSH ATT", ["rushing_attempts", "rush_attempts", "RushingAttempts"]],
        ["RUSH YDS", ["rush_yards", "rushing_yards", "RushingYards"]],
        ["RUSH TD", ["rush_tds", "rushing_touchdowns", "RushingTouchdowns"]],
      ] as const;
    case "TE":
      return [
        ["FPTS", ["fantasy_points", "fantasyPoints", "fpts"]],
        ["TAR", ["targets", "receiving_targets", "ReceivingTargets"]],
        ["REC", ["receptions", "Receptions"]],
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

export const completedSeasonGameTotals = (
  games: PlayerGameLogResponse["games"],
  position: string,
) => {
  const completedGames = games.filter(
    (game) => game.game_status === "final" && game.location !== "bye" && game.stats,
  );
  return {
    gamesPlayed: completedGames.length,
    totals: gameLogColumnsForPosition(position).map(([label, keys]) => {
      let total = 0;
      let hasValue = false;
      for (const game of completedGames) {
        const stats = game.stats
          ? { ...game.stats.stats, fantasy_points: game.stats.fantasy_points }
          : undefined;
        const value = gameLogStatValue(stats, keys);
        const numeric = typeof value === "number"
          ? value
          : typeof value === "string" && value.trim() ? Number(value) : Number.NaN;
        if (Number.isFinite(numeric)) {
          total += numeric;
          hasValue = true;
        }
      }
      return [label, hasValue ? Math.round(total * 100) / 100 : null] as const;
    }),
  };
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

/**
 * Availability updates are reported against the product's primary audience in
 * Eastern time.  Do not infer a report date when the source did not provide
 * one: an absent timestamp remains visibly unreported.
 */
export const formatPlayerNewsReportTime = (value?: string | null) => {
  if (!value) return "Report time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Report time unavailable";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "numeric",
    day: "numeric",
    year: "2-digit",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);
  return `Report · ${parts} ET`;
};

export const resolvePlayerCardProjectionStats = (
  player: PlayerCardModalPlayer,
  card?: PlayerCardResponse | null
) => {
  const sheetProjectionStats = player.sheetProjectionStats ?? card?.player.sheet_projection_stats ?? undefined;
  const projectedPoints =
    card?.player.sheet_projected_season_points ??
    player.seasonProjectedPoints ??
    statValue(sheetProjectionStats, ["fpts", "fantasy_points", "projected_points", "projectedFantasyPoints"]) ??
    null;

  if (!sheetProjectionStats && projectedPoints === null) return null;

  return buildProjectedStats(
    { fpts: projectedPoints ?? 0 },
    projectedPoints ?? 0,
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
  const [isOutlookExpanded, setIsOutlookExpanded] = useState(false);
  const [selectedGameLogSeason, setSelectedGameLogSeason] = useState<number | null>(null);
  const hasLeagueContext = typeof leagueId === "number" && Number.isFinite(leagueId) && leagueId > 0;
  const position = (card?.about.position ?? player.position ?? "").toUpperCase();
  const playerStatus = resolvePlayerCardStatus(card, player.status);
  const gameLogQuery = usePlayerGameLog(
    player.id,
    selectedGameLogSeason,
    leagueId,
    activeTab === "game-log",
  );
  const historyQuery = useLeaguePlayerHistory(leagueId ?? undefined, player.id, activeTab === "history" && hasLeagueContext);
  const valueQuery = usePlayerTradeValues(player.id, 2026);
  const trajectoryQuery = usePlayerTrajectory(
    player.id,
    2026,
    leagueId,
    activeTab === "projections" || activeTab === "value",
  );
  const palette = getPlayerCardPalette(position);
  const seasonProjectionStats = useMemo(() => resolvePlayerCardProjectionStats(player, card), [player, card]);
  const currentValueRating = resolvePlayerCardCurrentValueRating(
    valueQuery.data?.current?.current_value_rating,
    card,
  );
  const aboutMessage = visiblePlayerCardAboutMessage(card?.about.message);
  const cardActions = [...(action ? [action] : []), ...actions];
  const currentGame = card?.current_game;
  const currentGameStats = currentGame?.state === "completed" && currentGame.stats
    ? gameLogColumnsForPosition(position)
      .map(([label, keys]) => [label, gameLogStatValue(currentGame.stats, keys)] as const)
      .filter(([, value]) => value !== null && value !== undefined)
    : [];
  const selectedGameLogData = gameLogQuery.data;
  const selectedGameLogColumns = useMemo(() => {
    const games = selectedGameLogData?.games ?? [];
    return gameLogColumnsForPosition(position).filter(([, keys]) => games.some((game) => {
      if (!game.stats || game.location === "bye") return false;
      return gameLogStatValue({ ...game.stats.stats, fantasy_points: game.stats.fantasy_points }, keys) !== null;
    }));
  }, [position, selectedGameLogData?.games]);
  const calculatedGameLogSummary = useMemo(
    () => completedSeasonGameTotals(selectedGameLogData?.games ?? [], position),
    [selectedGameLogData?.games, position],
  );
  // Historical season totals are verified imports, but the app does not have
  // complete historical schedules. Only the current CFB season can surface a
  // schedule/game-by-game section.
  const shouldShowGameLogSchedule = selectedGameLogData?.season === 2026;
  const weeklyProjectionStats = player.hasWeeklyProjection === false ? null : player.projection;
  const weeklyProjectionHighlights = [
    ["Fantasy", weeklyProjectionStats?.fpts ?? player.projectedPoints],
    ["Floor", weeklyProjectionStats?.floor],
    ["Ceiling", weeklyProjectionStats?.ceiling],
    [
      "Boom",
      typeof weeklyProjectionStats?.boomProb === "number" ? `${Math.round(weeklyProjectionStats.boomProb * 100)}%` : null,
    ],
    [
      "Bust",
      typeof weeklyProjectionStats?.bustProb === "number" ? `${Math.round(weeklyProjectionStats.bustProb * 100)}%` : null,
    ],
    ["Opponent", player.opponent],
  ] as Array<[string, unknown]>;
  const visibleWeeklyProjectionHighlights = weeklyProjectionHighlights.filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );
  const projectionRows = statRowsForPosition(position || player.position || "");
  const weeklyProjectionDetailRows = weeklyProjectionStats
    ? projectionRows
        .map((row) => [row.label, statValue(weeklyProjectionStats as unknown as Record<string, unknown>, row.projectionKeys)] as const)
        .filter(([, value]) => value !== null)
    : [];
  const seasonProjectionDetailRows = seasonProjectionStats
    ? projectionRows
        .map((row) => [row.label, statValue(seasonProjectionStats, row.projectionKeys)] as const)
        .filter(([, value]) => value !== null)
    : [];
  useEffect(() => {
    setActiveTab("summary");
    setIsOutlookExpanded(false);
    setSelectedGameLogSeason(null);
  }, [player.id]);

  useEffect(() => {
    // The app shell owns the page scroll in its <main> element. This card is a
    // fixed overlay inside that shell, so locking only document.body still lets
    // touch scrolls move the matchup or roster behind it on mobile Safari.
    const appScroller = document.querySelector<HTMLElement>("main[data-app-scroll='true']");
    const originalAppOverflowY = appScroller?.style.overflowY;
    const originalAppOverscrollBehaviorY = appScroller?.style.overscrollBehaviorY;
    const originalBodyOverflow = document.body.style.overflow;
    const originalDocumentOverflow = document.documentElement.style.overflow;

    if (appScroller) {
      appScroller.style.overflowY = "hidden";
      appScroller.style.overscrollBehaviorY = "none";
    }
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      if (appScroller) {
        appScroller.style.overflowY = originalAppOverflowY ?? "";
        appScroller.style.overscrollBehaviorY = originalAppOverscrollBehaviorY ?? "";
      }
      document.body.style.overflow = originalBodyOverflow;
      document.documentElement.style.overflow = originalDocumentOverflow;
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-[1400] flex items-end justify-center overscroll-none bg-slate-950/78 p-4 backdrop-blur-md sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`${player.name} player card`}
      onClick={onClose}
    >
      <article
        className={cn(
          "relative mb-[max(1rem,env(safe-area-inset-bottom))] flex h-[78dvh] max-h-[calc(100dvh-3rem-env(safe-area-inset-bottom))] w-full max-w-5xl flex-col overflow-hidden rounded-md border border-cfb-border-subtle bg-cfb-surface text-cfb-text-primary shadow-[0_16px_44px_rgba(2,6,23,0.46)] sm:mb-0 sm:h-auto sm:max-h-[calc(100dvh-3rem)] sm:rounded-lg",
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

        <nav className="flex gap-1 overflow-x-auto border-b border-white/10 bg-black/18 px-3 pt-1 sm:gap-3 sm:flex-wrap sm:overflow-visible sm:px-8 sm:pt-2 lg:grid lg:grid-cols-7 lg:gap-0 lg:px-0 lg:pt-0">
          {visiblePlayerCardTabs(hasLeagueContext).map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "relative inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap px-2 py-2.5 text-[9px] font-semibold uppercase tracking-[0.06em] transition after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/80 sm:gap-2 sm:px-1 sm:text-[10px] sm:tracking-[0.12em] lg:justify-center lg:px-2",
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

        <div
          data-testid="player-card-scroll-area"
          tabIndex={0}
          aria-label="Player card details"
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain touch-pan-y [-webkit-overflow-scrolling:touch] p-3 pb-20 scroll-pb-20 sm:p-8 sm:pb-8 sm:scroll-pb-8"
        >
          {loading ? (
            <div className="flex min-h-56 items-center justify-center gap-3 rounded-md border border-cfb-border-subtle bg-cfb-surface-raised text-[10px] font-semibold uppercase tracking-[0.18em] text-cfb-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading player card
            </div>
          ) : error ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-4 rounded-md border border-cfb-warning/30 bg-cfb-warning/[0.08] p-6 text-center">
              <p className="text-sm font-black text-amber-50">Player details are unavailable right now.</p>
              <p className="text-xs font-bold leading-5 text-amber-100/75">The player card stayed open. Please try again.</p>
              {onRetry ? (
                <button
                  type="button"
                  onClick={onRetry}
                  className="rounded-sm border border-cfb-warning/40 bg-cfb-surface px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-cfb-warning transition hover:bg-cfb-surface-hover"
                >
                  Retry
                </button>
              ) : null}
            </div>
          ) : activeTab === "news" ? (
            <section className="rounded-md border border-cfb-border-subtle bg-cfb-surface-raised p-4 sm:p-5">
              <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Recent news</p>
              {card?.recent_news?.length ? (
                <div className="mt-3 space-y-2">
                  {card.recent_news.map((item) => (
                    <article key={item.id} className="rounded-sm border border-cfb-border-subtle bg-cfb-surface p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-black text-white">{item.status ?? item.event_type}</p>
                        <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-white/45">{item.source}</p>
                      </div>
                      <p className="mt-1 text-[9px] font-black uppercase tracking-[0.14em] text-white/55">
                        {formatPlayerNewsReportTime(item.published_at)}
                      </p>
                      <p className="mt-1 text-xs font-semibold leading-5 text-white/70">
                        {[item.detail, item.return_timeline].filter(Boolean).join(" • ") || "Official update"}
                      </p>
                      {item.source_url ? (
                        <a href={item.source_url} target="_blank" rel="noreferrer" className={cn("mt-2 inline-block text-[10px] font-black uppercase tracking-[0.14em]", palette.accent)}>View source</a>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="mt-3 rounded-sm border border-cfb-border-subtle bg-cfb-surface p-3 text-sm font-semibold text-cfb-text-muted">No verified recent news is available.</p>
              )}
            </section>
          ) : activeTab === "summary" ? (
            <div className="w-full">
              {currentGame?.state === "completed" ? (
                <section className="mb-3 rounded-md border border-cfb-border-subtle bg-cfb-surface-raised p-4 sm:p-5" aria-label="Current player game result">
                  <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Latest verified game</p>
                  <p className="mt-2 text-sm font-black text-white">Week {currentGame.week} vs. {currentGame.opponent_name ?? "opponent"}</p>
                  {currentGameStats.length ? (
                    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {currentGameStats.slice(0, 4).map(([label, value]) => (
                        <div key={label} className="rounded-sm border border-cfb-border-subtle bg-cfb-surface p-2.5">
                          <p className="text-[9px] font-black uppercase tracking-[0.16em] text-white/45">{label}</p>
                          <p className="mt-1 text-sm font-black tabular-nums text-white">{formatPlayerCardValue(value)}</p>
                        </div>
                      ))}
                    </div>
                  ) : <p className="mt-2 text-sm font-bold text-white/55">Final team result is verified; individual stats are still pending.</p>}
                </section>
              ) : currentGame?.state === "upcoming" ? (
                <section className="mb-3 rounded-md border border-cfb-border-subtle bg-cfb-surface-raised p-4 sm:p-5" aria-label="Upcoming player game">
                  <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Upcoming game</p>
                  <p className="mt-2 text-sm font-black text-white">Week {currentGame.week} vs. {currentGame.opponent_name ?? "opponent"}</p>
                  {currentGame.kickoff_at ? <p className="mt-1 text-xs font-bold text-white/55">{new Date(currentGame.kickoff_at).toLocaleString()}</p> : null}
                </section>
              ) : null}
              <section className="rounded-md border border-cfb-border-subtle bg-cfb-surface-raised p-4 sm:p-5">
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
                    <div key={label} className="rounded-sm border border-cfb-border-subtle bg-cfb-surface p-2.5 sm:p-3">
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
                {card?.season_outlook?.outlook_text ? (
                  <section
                    aria-label={`${card.season_outlook.season_year} season outlook`}
                    className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-3 sm:p-4"
                  >
                    <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>
                      {card.season_outlook.season_year} Outlook
                    </p>
                    <p className={cn(
                      "mt-2 text-xs font-semibold leading-5 text-white/70 sm:text-sm",
                      !isOutlookExpanded && "line-clamp-3",
                    )}>
                      {card.season_outlook.outlook_text}
                    </p>
                    {card.season_outlook.outlook_text.length > 180 ? (
                      <button
                        type="button"
                        onClick={() => setIsOutlookExpanded((expanded) => !expanded)}
                        className={cn(
                          "mt-2 text-[10px] font-black uppercase tracking-[0.16em] transition hover:text-white",
                          palette.accent,
                        )}
                      >
                        {isOutlookExpanded ? "Show less" : "Show more"}
                      </button>
                    ) : null}
                  </section>
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
          ) : activeTab === "game-log" ? (
            <section className="rounded-md border border-cfb-border-subtle bg-cfb-surface-raised p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Game Log</p>
                  <p className="mt-2 text-sm font-bold leading-6 text-white/55">
                    Verified performance for {selectedGameLogData?.team_name ?? card?.about.team ?? player.school} in {selectedGameLogData?.season ?? "the selected season"}.
                  </p>
                </div>
                <label className="flex shrink-0 flex-col gap-1.5 text-[9px] font-black uppercase tracking-[0.14em] text-white/55">
                  Game log season
                  <select
                    aria-label="Game log season"
                    value={selectedGameLogSeason ?? selectedGameLogData?.season ?? ""}
                    onChange={(event) => setSelectedGameLogSeason(Number(event.target.value))}
                    disabled={!selectedGameLogData?.available_seasons.length}
                    className="min-w-28 rounded-xl border border-white/15 bg-black/30 px-3 py-2 text-sm font-black normal-case tracking-normal text-white outline-none transition focus:border-cfb-brand disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {selectedGameLogData?.available_seasons.map((season) => (
                      <option key={season} value={season}>{season}</option>
                    ))}
                  </select>
                </label>
              </div>
              {gameLogQuery.isLoading ? (
                <div className="mt-5 flex min-h-40 items-center justify-center gap-3 rounded-2xl border border-white/10 bg-black/20 text-[10px] font-black uppercase tracking-[0.18em] text-white/55">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading game log
                </div>
              ) : gameLogQuery.isError ? (
                <p className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm font-bold leading-6 text-amber-100">
                  The Game Log is unavailable right now. Please try again shortly.
                </p>
              ) : selectedGameLogData ? (
                <>
                {selectedGameLogData.season_summary || calculatedGameLogSummary.gamesPlayed > 0 ? (
                  <section className="mt-5 border-y border-cfb-border-subtle bg-cfb-surface px-4 py-4" aria-label={`${selectedGameLogData.season} season summary`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-white/55">Season summary</p>
                      <p className="text-[9px] font-black uppercase tracking-[0.14em] text-white/45">{selectedGameLogData.season}</p>
                    </div>
                    {selectedGameLogData.season_summary?.teams.length ? <p className="mt-1 text-xs font-bold text-white/55">{selectedGameLogData.season_summary.teams.join(" · ")}</p> : null}
                <div className="mt-4 grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
                      {[
                        ...(selectedGameLogData.season_summary?.games_played !== null && selectedGameLogData.season_summary?.games_played !== undefined ? [["Games", selectedGameLogData.season_summary.games_played] as const] : calculatedGameLogSummary.gamesPlayed > 0 ? [["Games", calculatedGameLogSummary.gamesPlayed] as const] : []),
                        ...(selectedGameLogData.season_summary?.games_started !== null && selectedGameLogData.season_summary?.games_started !== undefined ? [["Starts", selectedGameLogData.season_summary.games_started] as const] : []),
                        ...(selectedGameLogData.season_summary?.stats.map((stat) => [stat.label, stat.value] as const) ?? calculatedGameLogSummary.totals.filter(([, value]) => value !== null)),
                        ...(selectedGameLogData.season_summary?.fantasy_points !== null && selectedGameLogData.season_summary?.fantasy_points !== undefined ? [["Fantasy points", selectedGameLogData.season_summary.fantasy_points] as const] : []),
                      ].map(([label, value]) => (
                        <div key={label} data-testid="game-log-season-summary-stat" className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-baseline gap-4 text-xs">
                          <span className="min-w-0 truncate font-black uppercase tracking-[0.12em] text-white/45" title={label}>{label}</span>
                          <span className="shrink-0 whitespace-nowrap font-black tabular-nums text-white">{formatPlayerCardValue(value)}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
                {shouldShowGameLogSchedule && selectedGameLogData.games.length ? (
                <>
                <div className="mt-5 hidden overflow-x-auto rounded-sm border border-cfb-border-subtle bg-cfb-surface md:block">
                  <table className="min-w-full w-full border-collapse text-left">
                    <thead className="bg-white/[0.055] text-[9px] font-black uppercase tracking-[0.16em] text-white/45">
                      <tr>
                        <th className="min-w-[4.5rem] whitespace-nowrap px-4 py-3">Week</th>
                        <th className="min-w-[15rem] whitespace-nowrap px-4 py-3">Opponent</th>
                        <th className="min-w-[8rem] whitespace-nowrap px-4 py-3">Location</th>
                        <th className="min-w-[5.5rem] whitespace-nowrap px-4 py-3">Result</th>
                        {selectedGameLogColumns.map(([label]) => (
                          <th key={label} className="whitespace-nowrap px-4 py-3 text-right">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {selectedGameLogData.games.map((row) => {
                        const stats = row.stats ? { ...row.stats.stats, fantasy_points: row.stats.fantasy_points } : undefined;
                        return (
                          <tr key={row.schedule_id} className="text-sm font-bold text-white/75">
                            <td className="px-4 py-4 font-black tabular-nums text-white">{row.week}</td>
                            <td className="px-4 py-4">
                              <p className="font-black text-white">{gameLogOpponentLabel(row)}</p>
                              <p className="mt-1 text-[10px] font-bold text-white/40">{formatGameLogDate(row.date)}</p>
                            </td>
                            <td className="whitespace-nowrap px-4 py-4 text-[10px] font-black uppercase tracking-[0.16em] text-white/55">{row.location_label}</td>
                            <td className="whitespace-nowrap px-4 py-4 text-xs font-black tabular-nums text-white/70">{row.result ?? "—"}</td>
                            {selectedGameLogColumns.map(([label, keys]) => {
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
                  {selectedGameLogData.games.map((row) => {
                    const stats = row.stats ? { ...row.stats.stats, fantasy_points: row.stats.fantasy_points } : undefined;
                    return (
                      <article key={row.schedule_id} className="border-b border-cfb-border-subtle bg-cfb-surface p-4 last:border-b-0">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-white/45">Week {row.week}</p>
                            <p className="mt-1 truncate font-black text-white">{gameLogOpponentLabel(row)}</p>
                            <p className="mt-1 text-xs font-bold text-white/45">{formatGameLogDate(row.date)} • {row.location_label}</p>
                          </div>
                          <p className="shrink-0 text-right text-xs font-black tabular-nums text-white/70">{row.result ?? "—"}</p>
                        </div>
                        {selectedGameLogColumns.length ? (
                          <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
                            {selectedGameLogColumns.map(([label, keys]) => {
                              const value = row.location === "bye" ? null : gameLogStatValue(stats, keys);
                              return (
                              <div key={label} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-xs">
                                <span className="min-w-0 truncate font-black uppercase tracking-[0.12em] text-white/45" title={label}>{label}</span>
                                <span className="shrink-0 whitespace-nowrap font-black tabular-nums text-white">{formatPlayerCardValue(value)}</span>
                                </div>
                              );
                            })}
                          </div>
                        ) : row.game_status === "final" ? (
                          <p className="mt-4 text-xs font-semibold text-white/55">
                            Verified player statistics are not available for this game.
                          </p>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
                </>
              ) : null}
                </>
              ) : null}
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
                      points={trajectoryQuery.data.projection.map((point) => ({ ...point, value: point.points, actualValue: point.actual_points }))}
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
              {visibleWeeklyProjectionHighlights.length || weeklyProjectionDetailRows.length ? (
                <section className="mt-5" aria-label="Weekly projection">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-brand">This week</p>
                  <p className="mt-1 text-xs font-bold text-white/55">Matchup model projection</p>
                  {visibleWeeklyProjectionHighlights.length ? (
                    <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
                      {visibleWeeklyProjectionHighlights.map(([label, value]) => (
                        <div key={label} className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.07] p-3">
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                          <p className="mt-2 truncate text-xl font-black tabular-nums text-white">
                            {typeof value === "number" ? formatStat(value) : formatPlayerCardValue(value)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {weeklyProjectionDetailRows.length ? (
                    <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
                      {weeklyProjectionDetailRows.map(([label, value]) => (
                        <div key={label} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                          <p className="mt-2 text-xl font-black tabular-nums text-white">{formatStat(value)}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </section>
              ) : null}
              {seasonProjectionStats ? (
                <section className="mt-6 border-t border-white/10 pt-5" aria-label="Season projection">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-white/70">2026 season outlook</p>
                  <p className="mt-1 text-xs font-bold text-white/55">Preseason projected totals</p>
                  <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
                    {typeof seasonProjectionStats.fpts === "number" ? (
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">Fantasy points</p>
                        <p className="mt-2 text-xl font-black tabular-nums text-white">{formatStat(seasonProjectionStats.fpts)}</p>
                      </div>
                    ) : null}
                    {seasonProjectionDetailRows.map(([label, value]) => (
                      <div key={label} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                        <p className="mt-2 text-xl font-black tabular-nums text-white">{formatStat(value)}</p>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}
              {!visibleWeeklyProjectionHighlights.length && !weeklyProjectionDetailRows.length && !seasonProjectionStats ? (
                <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  No weekly matchup projection or season outlook is linked to this card yet.
                </p>
              ) : null}
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
