import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { Activity, AlertTriangle, BarChart3, Info, Loader2, UserRound, X } from "lucide-react";

import type { PlayerCardResponse } from "@/hooks/use-players";
import { buildProjectedStats, formatStat, statRowsForPosition, statValue } from "@/lib/playerProjectionStats";
import { cn } from "@/lib/utils";
import type { PlayerStats } from "@/types/player";

type PlayerCardTab = "summary" | "stats" | "alerts" | "projections";

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
};

type PlayerCardAction = {
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
  { id: "alerts", label: "Alerts", icon: AlertTriangle },
  { id: "projections", label: "Projections", icon: Activity },
];

const statDisplayKeys = [
  ["Pass Yds", ["pass_yards", "PassingYards", "passingYards"]],
  ["Pass TD", ["pass_tds", "PassingTouchdowns", "passingTouchdowns"]],
  ["INT", ["interceptions", "Interceptions"]],
  ["Rush Yds", ["rush_yards", "RushingYards", "rushingYards"]],
  ["Rush TD", ["rush_tds", "RushingTouchdowns", "rushingTouchdowns"]],
  ["Rec", ["receptions", "Receptions"]],
  ["Rec Yds", ["rec_yards", "ReceivingYards", "receivingYards"]],
  ["Rec TD", ["rec_tds", "ReceivingTouchdowns", "receivingTouchdowns"]],
  ["Fum Lost", ["fumbles_lost", "FumblesLost", "fumblesLost"]],
] as const;

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
    glow: "shadow-[0_28px_100px_rgba(59,130,246,0.28)]",
    accent: "text-blue-100",
    pill: "border-blue-200/45 bg-blue-200/15 text-blue-50",
    silhouette: "from-blue-200/35 via-blue-100/20 to-transparent",
  },
  RB: {
    headerBase: "bg-emerald-950",
    markerA: "rgba(52,211,153,0.24)",
    markerB: "rgba(20,184,166,0.20)",
    markerC: "rgba(6,78,59,0.42)",
    glow: "shadow-[0_28px_100px_rgba(16,185,129,0.25)]",
    accent: "text-emerald-100",
    pill: "border-emerald-200/45 bg-emerald-200/15 text-emerald-50",
    silhouette: "from-emerald-200/35 via-emerald-100/20 to-transparent",
  },
  WR: {
    headerBase: "bg-violet-950",
    markerA: "rgba(167,139,250,0.28)",
    markerB: "rgba(217,70,239,0.18)",
    markerC: "rgba(76,29,149,0.42)",
    glow: "shadow-[0_28px_100px_rgba(139,92,246,0.28)]",
    accent: "text-violet-100",
    pill: "border-violet-200/45 bg-violet-200/15 text-violet-50",
    silhouette: "from-violet-200/35 via-violet-100/20 to-transparent",
  },
  TE: {
    headerBase: "bg-amber-950",
    markerA: "rgba(251,191,36,0.26)",
    markerB: "rgba(249,115,22,0.24)",
    markerC: "rgba(120,53,15,0.42)",
    glow: "shadow-[0_28px_100px_rgba(245,158,11,0.24)]",
    accent: "text-amber-100",
    pill: "border-amber-200/45 bg-amber-200/15 text-amber-50",
    silhouette: "from-amber-200/35 via-amber-100/20 to-transparent",
  },
  K: {
    headerBase: "bg-slate-900",
    markerA: "rgba(203,213,225,0.18)",
    markerB: "rgba(100,116,139,0.22)",
    markerC: "rgba(15,23,42,0.45)",
    glow: "shadow-[0_28px_100px_rgba(148,163,184,0.20)]",
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
  glow: "shadow-[0_28px_100px_rgba(34,211,238,0.24)]",
  accent: "text-cyan-100",
  pill: "border-cyan-200/45 bg-cyan-200/15 text-cyan-50",
  silhouette: "from-cyan-200/35 via-cyan-100/20 to-transparent",
};

const playbookMarks = [
  { label: "X", className: "left-[58%] top-8" },
  { label: "O", className: "left-[69%] top-14" },
  { label: "X", className: "left-[78%] top-7" },
  { label: "12", className: "left-[87%] bottom-7 text-[18px]" },
];

export const formatPlayerCardValue = (value: unknown, fallback = "—") => {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : fallback;
  return String(value);
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

const getLatestStats = (card?: PlayerCardResponse) =>
  card?.season_stats.find((row) => row.week === 0)?.stats ?? card?.season_stats[0]?.stats ?? null;

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

export const buildHistoricalStatsTableRows = (season: HistoricalSeason | null): HistoricalStatTableRow[] =>
  season?.categories.flatMap((category) =>
    category.stats.map((stat) => ({
      category: category.label,
      label: stat.label,
      value: stat.value,
    }))
  ) ?? [];

const sourceLabel = (source?: string | null) => {
  if (!source) return "Local";
  return source.toUpperCase();
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
  card,
  loading = false,
  note,
  onClose,
  player,
  title = "Player Card",
}: {
  action?: PlayerCardAction | null;
  card?: PlayerCardResponse | null;
  loading?: boolean;
  note?: string | null;
  onClose: () => void;
  player: PlayerCardModalPlayer;
  title?: string;
}) {
  const [activeTab, setActiveTab] = useState<PlayerCardTab>("summary");
  const [selectedHistoricalSeason, setSelectedHistoricalSeason] = useState<number | null>(null);
  const position = (card?.about.position ?? player.position ?? "").toUpperCase();
  const palette = getPlayerCardPalette(position);
  const historicalStats = card?.historical_stats;
  const historicalSeasons = historicalStats?.seasons ?? [];
  const activeHistoricalSeason: HistoricalSeason | null =
    historicalSeasons.find((row) => row.season === selectedHistoricalSeason) ??
    historicalSeasons[0] ??
    null;
  const latestStats = useMemo(() => getLatestStats(card ?? undefined), [card]);
  const projectionStats = useMemo(() => resolvePlayerCardProjectionStats(player, card), [player, card]);
  const aboutMessage = visiblePlayerCardAboutMessage(card?.about.message);
  const projectionHighlights: Array<[string, unknown]> = [
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
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  const projectionRows = statRowsForPosition(position || player.position || "");
  const projectionDetailRows = projectionStats
    ? projectionRows
        .map((row) => [row.label, statValue(projectionStats, row.projectionKeys)] as const)
    .filter(([, value]) => value !== null)
    : [];
  const historicalTableRows = buildHistoricalStatsTableRows(activeHistoricalSeason);
  const primaryStats = statDisplayKeys
    .map(([label, keys]) => [label, getStatValue(latestStats, keys)] as const)
    .filter(([, value]) => value !== null)
    .slice(0, 6);
  const metricCards = [
    ["Proj", typeof player.projectedPoints === "number" ? player.projectedPoints.toFixed(1) : "—"],
    ["Rank", player.rankLabel ?? "—"],
    ["Class", card?.about.player_class ?? player.playerClass ?? "—"],
    ["Status", card?.about.status ?? player.status ?? "—"],
  ];
  const headerStreakStyle: CSSProperties = {
    backgroundImage: [
      `repeating-linear-gradient(168deg, transparent 0 18px, ${palette.markerA} 19px 27px, transparent 29px 54px)`,
      `linear-gradient(101deg, transparent 0 11%, ${palette.markerB} 11.5% 23%, transparent 24% 100%)`,
      `linear-gradient(116deg, transparent 0 42%, ${palette.markerC} 42.5% 49%, transparent 50% 100%)`,
      "repeating-linear-gradient(90deg, rgba(255,255,255,0.11) 0 1px, transparent 1px 86px)",
    ].join(", "),
    backgroundPosition: "0 0, 0 0, 0 0, 18px 0",
  };

  useEffect(() => {
    setActiveTab("summary");
    setSelectedHistoricalSeason(null);
  }, [player.id]);

  useEffect(() => {
    if (!selectedHistoricalSeason && historicalStats?.selected_season) {
      setSelectedHistoricalSeason(historicalStats.selected_season);
    }
  }, [historicalStats?.selected_season, selectedHistoricalSeason]);

  return (
    <div
      className="fixed inset-0 z-[1400] flex items-center justify-center bg-slate-950/78 p-3 backdrop-blur-md sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`${player.name} player card`}
      onClick={onClose}
    >
      <article
        className={cn(
          "relative flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-[2rem] border border-white/12 bg-[#070d19] text-white",
          palette.glow
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          aria-label="Close player card"
          onClick={onClose}
          className="absolute right-4 top-4 z-30 inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-black/25 text-white/75 backdrop-blur transition hover:bg-white/10 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>

        <header className={cn("relative overflow-hidden px-5 py-6 pr-20 sm:px-8 sm:pr-24", palette.headerBase)}>
          <div className="absolute inset-0 opacity-75 mix-blend-screen" style={headerStreakStyle} />
          <div className="absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent_0_28px,rgba(255,255,255,0.07)_29px,transparent_31px_58px)] opacity-30" />
          <div
            className="pointer-events-none absolute inset-0 hidden text-white/20 [mask-image:linear-gradient(to_right,black_0%,black_58%,transparent_74%)] lg:block"
            aria-hidden="true"
          >
            <div className="absolute left-[40%] top-11 h-px w-36 rotate-[14deg] bg-white/25" />
            <div className="absolute left-[49%] top-[4.25rem] h-px w-32 -rotate-[18deg] bg-white/20" />
            <div className="absolute left-[55%] top-10 h-px w-28 rotate-[25deg] bg-white/15" />
            {playbookMarks.map((mark) => (
              <span
                key={`${mark.label}-${mark.className}`}
                className={cn(
                  "absolute -translate-x-[18%] font-black italic leading-none tracking-normal text-white/25",
                  mark.label.length > 1 ? "text-base" : "text-3xl",
                  mark.className
                )}
              >
                {mark.label}
              </span>
            ))}
          </div>
          <div className="relative z-10 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,440px)] xl:items-start">
            <div className="min-w-0">
              <p className="text-[10px] font-black uppercase tracking-[0.28em] text-white/70">{title}</p>
              <div className="mt-4 flex min-w-0 items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/25 bg-white/10 shadow-[0_16px_34px_rgba(2,6,23,0.28)] sm:h-20 sm:w-20">
                  {card?.about.headshot_url ? (
                    <img src={card.about.headshot_url} alt={player.name} className="h-full w-full object-cover" />
                  ) : (
                    <div className={cn("flex h-full w-full items-center justify-center bg-gradient-to-b", palette.silhouette)}>
                      <UserRound className="h-9 w-9 text-white/70 sm:h-10 sm:w-10" />
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <h2 className="max-w-2xl break-words text-3xl font-black italic leading-[0.9] tracking-tight text-white sm:text-5xl">
                    {player.name}
                  </h2>
                  <p className="mt-3 truncate text-xs font-black uppercase tracking-[0.18em] text-white/75">
                    {[card?.about.jersey ? `#${card.about.jersey}` : null, position || player.position, card?.about.team ?? player.school]
                      .filter(Boolean)
                      .join(" • ")}
                  </p>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className={cn("rounded-full border px-4 py-2 text-xs font-black", palette.pill)}>
                  {position || "N/A"}
                </span>
                <span className="rounded-full border border-white/18 bg-black/20 px-4 py-2 text-xs font-black text-white/80">
                  {sourceLabel(card?.about.source)} PROFILE
                </span>
                {player.rankLabel ? (
                  <span className="rounded-full border border-white/18 bg-black/20 px-4 py-2 text-xs font-black text-white/80">
                    {player.rankLabel}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-2 xl:pt-24 2xl:grid-cols-4">
              {metricCards.map(([label, value]) => (
                <div key={label} className="min-w-0 rounded-2xl border border-white/15 bg-black/25 p-3 backdrop-blur">
                  <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/55">{label}</p>
                  <p className="mt-2 truncate text-xl font-black tabular-nums text-white">{value}</p>
                </div>
              ))}
            </div>
          </div>
        </header>

        <nav className="flex gap-2 overflow-x-auto border-b border-white/10 bg-black/18 px-5 py-3 sm:px-8">
          {tabConfig.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "inline-flex shrink-0 items-center gap-2 rounded-2xl border px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] transition",
                  active
                    ? "border-white/35 bg-white text-slate-950"
                    : "border-white/10 bg-white/[0.045] text-white/60 hover:border-white/25 hover:text-white"
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-8">
          {loading ? (
            <div className="flex min-h-56 items-center justify-center gap-3 rounded-3xl border border-white/10 bg-white/[0.04] text-[10px] font-black uppercase tracking-[0.22em] text-white/55">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading player card
            </div>
          ) : activeTab === "summary" ? (
            <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
              <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
                <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Bio</p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {[
                    ["Height", card?.about.height],
                    ["Weight", card?.about.weight],
                    ["Class", card?.about.player_class ?? player.playerClass],
                    ["Born", card?.about.birthplace],
                    ["School", card?.about.team ?? player.school],
                    ["Status", card?.about.status ?? player.status],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                      <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                      <p className="mt-2 text-sm font-black text-white">{formatPlayerCardValue(value)}</p>
                    </div>
                  ))}
                </div>
                {aboutMessage ? (
                  <p className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-400/10 p-3 text-xs font-bold leading-5 text-amber-100">
                    {aboutMessage}
                  </p>
                ) : null}
                {note ? (
                  <p className="mt-4 rounded-2xl border border-cyan-300/15 bg-cyan-300/10 p-3 text-xs font-bold leading-5 text-cyan-100">
                    {note}
                  </p>
                ) : null}
                {action ? (
                  <button
                    type="button"
                    onClick={action.onClick}
                    className="mt-4 inline-flex w-full items-center justify-center rounded-2xl border border-white/15 bg-white px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-950 transition hover:bg-cyan-100"
                  >
                    {action.label}
                  </button>
                ) : null}
              </section>
              <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
                <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Season Snapshot</p>
                {primaryStats.length ? (
                  <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {primaryStats.map(([label, value]) => (
                      <div key={label} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[9px] font-black uppercase tracking-[0.18em] text-white/45">{label}</p>
                        <p className="mt-2 text-2xl font-black tabular-nums text-white">
                          {formatPlayerCardValue(value)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                    No cached stat line is available for this player yet.
                  </p>
                )}
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
                    ESPN stats are resolved by exact player identity and imported into a clean season table.
                  </p>
                </div>
                {historicalSeasons.length > 1 ? (
                  <label className="flex shrink-0 flex-col gap-2 text-[9px] font-black uppercase tracking-[0.16em] text-white/45">
                    Season
                    <select
                      value={activeHistoricalSeason?.season ?? ""}
                      onChange={(event) => setSelectedHistoricalSeason(Number(event.target.value))}
                      className="rounded-2xl border border-white/15 bg-black/35 px-4 py-3 text-xs font-black text-white outline-none transition focus:border-cyan-200/55"
                    >
                      {historicalSeasons.map((row) => (
                        <option key={row.season} value={row.season}>
                          {row.season}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>

              {activeHistoricalSeason ? (
                <div className="mt-5 space-y-4">
                  <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-2xl font-black italic text-white">
                          {activeHistoricalSeason.season} {activeHistoricalSeason.team_name ?? card?.about.team ?? player.school}
                        </p>
                        <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-white/45">
                          {[activeHistoricalSeason.position ?? position, activeHistoricalSeason.season_type]
                            .filter(Boolean)
                            .join(" • ")}
                        </p>
                      </div>
                      <p className="rounded-full border border-white/15 bg-white/[0.06] px-4 py-2 text-[9px] font-black uppercase tracking-[0.16em] text-white/55">
                        {sourceLabel(activeHistoricalSeason.freshness.provider)} import
                      </p>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {activeHistoricalSeason.summary.slice(0, 8).map((item) => (
                        <div key={item.label} className="rounded-2xl border border-white/10 bg-white/[0.045] p-3">
                          <p className="text-[8px] font-black uppercase tracking-[0.14em] text-white/40">{item.label}</p>
                          <p className="mt-1 text-xl font-black tabular-nums text-white">
                            {formatPlayerCardValue(item.value)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/20">
                    <table className="w-full border-collapse text-left">
                      <thead className="bg-white/[0.055] text-[9px] font-black uppercase tracking-[0.16em] text-white/45">
                        <tr>
                          <th className="px-4 py-3">Category</th>
                          <th className="px-4 py-3">Stat</th>
                          <th className="px-4 py-3 text-right">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10">
                        {historicalTableRows.map((item) => (
                          <tr key={`${item.category}-${item.label}`} className="text-sm font-bold text-white/75">
                            <td className="px-4 py-3 text-[10px] font-black uppercase tracking-[0.14em] text-white/45">
                              {item.category}
                            </td>
                            <td className="px-4 py-3">{item.label}</td>
                            <td className="px-4 py-3 text-right font-black tabular-nums text-white">
                              {formatPlayerCardValue(item.value)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <p className="rounded-2xl border border-white/10 bg-white/[0.035] p-3 text-xs font-bold leading-5 text-white/45">
                    Imported{" "}
                    {activeHistoricalSeason.freshness.imported_at
                      ? new Date(activeHistoricalSeason.freshness.imported_at).toLocaleString()
                      : "time unknown"}
                    {activeHistoricalSeason.freshness.parser_version
                      ? ` • Parser ${activeHistoricalSeason.freshness.parser_version}`
                      : ""}
                  </p>
                </div>
              ) : (
                <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-bold leading-6 text-white/55">
                  {historicalStats?.message ??
                    "No imported historical season stats are linked to this player yet."}
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
          ) : (
            <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
              <p className={cn("text-[10px] font-black uppercase tracking-[0.22em]", palette.accent)}>Fantasy Projection</p>
              {projectionStats ? (
                <div className="mt-5 space-y-4">
                  {projectionHighlights.length ? (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                      {projectionHighlights.map(([label, value]) => (
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
                  No projection object is linked to this card yet.
                </p>
              )}
            </section>
          )}
        </div>
      </article>
    </div>
  );
}
