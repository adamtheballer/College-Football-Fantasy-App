import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRightLeft, BarChart3, Newspaper, X } from "lucide-react";

import type { LeagueRosterPlayer } from "@/types/league";
import { cn } from "@/lib/utils";

const slotRank = (slot?: string | null) => {
  const order = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];
  const index = order.indexOf((slot || "BENCH").toUpperCase());
  return index === -1 ? order.length : index;
};

const slotLabel = (slot?: string | null) => (slot || "BENCH").toUpperCase();

const positionLabel = (player: LeagueRosterPlayer) =>
  (player.position ?? player.player_position ?? "FLEX").toUpperCase();

const positionStyles: Record<
  string,
  {
    pill: string;
    row: string;
    dot: string;
    text: string;
    border: string;
    panel: string;
  }
> = {
  QB: {
    pill: "border-blue-300/45 bg-blue-400/15 text-blue-100 shadow-[0_0_22px_rgba(96,165,250,0.18)]",
    row: "hover:bg-blue-400/[0.06]",
    dot: "bg-blue-300 shadow-[0_0_16px_rgba(147,197,253,0.75)]",
    text: "text-blue-200",
    border: "border-blue-300/25",
    panel: "from-blue-500/18",
  },
  RB: {
    pill: "border-emerald-300/45 bg-emerald-400/15 text-emerald-100 shadow-[0_0_22px_rgba(52,211,153,0.18)]",
    row: "hover:bg-emerald-400/[0.06]",
    dot: "bg-emerald-300 shadow-[0_0_16px_rgba(110,231,183,0.75)]",
    text: "text-emerald-200",
    border: "border-emerald-300/25",
    panel: "from-emerald-500/18",
  },
  WR: {
    pill: "border-violet-300/45 bg-violet-400/15 text-violet-100 shadow-[0_0_22px_rgba(167,139,250,0.18)]",
    row: "hover:bg-violet-400/[0.06]",
    dot: "bg-violet-300 shadow-[0_0_16px_rgba(196,181,253,0.75)]",
    text: "text-violet-200",
    border: "border-violet-300/25",
    panel: "from-violet-500/18",
  },
  TE: {
    pill: "border-amber-300/45 bg-amber-400/15 text-amber-100 shadow-[0_0_22px_rgba(251,191,36,0.18)]",
    row: "hover:bg-amber-400/[0.06]",
    dot: "bg-amber-300 shadow-[0_0_16px_rgba(252,211,77,0.75)]",
    text: "text-amber-200",
    border: "border-amber-300/25",
    panel: "from-amber-500/18",
  },
  K: {
    pill: "border-white/70 bg-white/15 text-white shadow-[0_0_24px_rgba(255,255,255,0.28)]",
    row: "hover:bg-white/[0.07]",
    dot: "bg-white shadow-[0_0_18px_rgba(255,255,255,0.95)]",
    text: "text-white",
    border: "border-white/35",
    panel: "from-white/18",
  },
  FLEX: {
    pill: "border-fuchsia-300/45 bg-fuchsia-400/15 text-fuchsia-100 shadow-[0_0_22px_rgba(217,70,239,0.18)]",
    row: "hover:bg-fuchsia-400/[0.06]",
    dot: "bg-fuchsia-300 shadow-[0_0_16px_rgba(240,171,252,0.75)]",
    text: "text-fuchsia-200",
    border: "border-fuchsia-300/25",
    panel: "from-fuchsia-500/18",
  },
  BENCH: {
    pill: "border-slate-300/30 bg-slate-300/10 text-slate-200",
    row: "hover:bg-slate-300/[0.04]",
    dot: "bg-slate-400 shadow-[0_0_14px_rgba(148,163,184,0.55)]",
    text: "text-slate-200",
    border: "border-slate-300/15",
    panel: "from-slate-500/12",
  },
  IR: {
    pill: "border-rose-300/40 bg-rose-400/15 text-rose-100",
    row: "hover:bg-rose-400/[0.05]",
    dot: "bg-rose-300 shadow-[0_0_14px_rgba(251,113,133,0.6)]",
    text: "text-rose-200",
    border: "border-rose-300/20",
    panel: "from-rose-500/14",
  },
};

const getPositionStyle = (position?: string | null) =>
  positionStyles[(position || "").toUpperCase()] ?? positionStyles.FLEX;

const formatPoints = (value?: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "-";

const formatPercent = (value?: number | null) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${Math.round(value * 100)}%`;
};

const readText = (player: LeagueRosterPlayer, keys: string[]) => {
  const record = player as unknown as Record<string, unknown>;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
};

const readStats = (player: LeagueRosterPlayer) => {
  const record = player as unknown as Record<string, unknown>;
  const raw =
    record.previous_season_stats ??
    record.stats_2025 ??
    record.season_stats ??
    record.previousStats;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as Record<string, string | number | null | undefined>;
};

const buildOutlook = (player: LeagueRosterPlayer) => {
  const position = positionLabel(player);
  const school = player.school ?? player.player_school ?? "school not listed";
  const projection = player.projected_points ?? player.weekly_projected_fantasy_points ?? 0;
  const floor = player.floor;
  const ceiling = player.ceiling;
  const range =
    typeof floor === "number" && typeof ceiling === "number"
      ? ` Projection range: ${floor.toFixed(1)}-${ceiling.toFixed(1)}.`
      : "";

  return `${player.player_name} is listed as a ${position} from ${school} with a Week 1 projection of ${projection.toFixed(
    1
  )} fantasy points.${range} This outlook uses roster slot, opponent, and projection data currently loaded for this league.`;
};

type RosterSlotTableTone = "default" | "bench";

export function RosterSlotTable({
  title,
  players,
  emptyText = "No roster players yet.",
  showPositionColumn = true,
  tone = "default",
  leagueId,
}: {
  title: string;
  players: LeagueRosterPlayer[];
  emptyText?: string;
  showPositionColumn?: boolean;
  tone?: RosterSlotTableTone;
  leagueId?: number | string;
}) {
  const navigate = useNavigate();
  const [selectedPlayer, setSelectedPlayer] = useState<LeagueRosterPlayer | null>(null);
  const isBenchTone = tone === "bench";
  const sorted = [...players].sort((left, right) => {
    const slotDelta = slotRank(left.roster_slot || left.slot) - slotRank(right.roster_slot || right.slot);
    if (slotDelta !== 0) return slotDelta;
    return left.player_name.localeCompare(right.player_name);
  });

  const selectedPosition = selectedPlayer ? positionLabel(selectedPlayer) : null;
  const selectedStyle = getPositionStyle(selectedPosition);
  const selectedProjection =
    selectedPlayer?.projected_points ?? selectedPlayer?.weekly_projected_fantasy_points ?? 0;
  const selectedNews =
    selectedPlayer
      ? readText(selectedPlayer, ["news", "player_news", "latest_news", "headline"])
      : null;
  const selectedStats = selectedPlayer ? readStats(selectedPlayer) : null;
  const tableColumns = showPositionColumn
    ? "md:grid-cols-[0.55fr_1.45fr_0.75fr_0.45fr_0.55fr_0.5fr]"
    : "md:grid-cols-[0.55fr_1.6fr_0.9fr_0.65fr_0.5fr]";
  const openTradeBuilder = () => {
    if (!leagueId || !selectedPlayer?.player_id) return;
    const teamId = selectedPlayer.team_id ?? selectedPlayer.fantasy_team_id;
    const query = teamId ? `?teamId=${teamId}` : "";
    navigate(`/trade/${leagueId}/${selectedPlayer.player_id}${query}`);
  };

  return (
    <section
      className={cn(
        "overflow-hidden rounded-[1.5rem] border",
        isBenchTone
          ? "border-slate-300/15 bg-[linear-gradient(135deg,rgba(5,10,18,0.98),rgba(13,18,28,0.94)_52%,rgba(8,13,24,0.98))] shadow-[0_18px_54px_rgba(2,6,23,0.42)]"
          : "border-sky-300/15 bg-[linear-gradient(135deg,rgba(8,18,32,0.98),rgba(13,23,39,0.94)_48%,rgba(15,23,42,0.98))] shadow-[0_22px_70px_rgba(14,165,233,0.08)]"
      )}
    >
      <div
        className={cn(
          "border-b px-5 py-4",
          isBenchTone ? "border-white/10 bg-white/[0.025]" : "border-sky-300/10 bg-sky-300/[0.03]"
        )}
      >
        <h2
          className={cn(
            "text-[11px] font-black uppercase tracking-[0.22em]",
            isBenchTone ? "text-slate-300" : "text-sky-300"
          )}
        >
          {title}
        </h2>
      </div>
      {sorted.length === 0 ? (
        <p
          className={cn(
            "border-t border-dashed px-5 py-6 text-sm text-slate-400",
            isBenchTone ? "border-white/10" : "border-sky-300/10"
          )}
        >
          {emptyText}
        </p>
      ) : (
        <div className="divide-y divide-white/10">
          <div className={cn("hidden gap-3 px-5 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500 md:grid", tableColumns)}>
            <span>Slot</span>
            <span>Player</span>
            <span>School</span>
            {showPositionColumn ? <span>Pos</span> : null}
            <span>Opp</span>
            <span className="text-right">Proj</span>
          </div>
          {sorted.map((player) => {
            const position = positionLabel(player);
            const style = getPositionStyle(position);
            const projection = player.projected_points ?? player.weekly_projected_fantasy_points ?? 0;
            return (
              <button
                key={`${player.team_id ?? player.fantasy_team_id}-${player.player_id}-${player.slot ?? player.roster_slot}`}
                type="button"
                onClick={() => setSelectedPlayer(player)}
                className={cn(
                  "grid w-full gap-3 px-5 py-4 text-left text-sm text-slate-200 transition focus:outline-none focus-visible:bg-sky-300/[0.06] focus-visible:ring-2 focus-visible:ring-sky-300/50 md:items-center",
                  tableColumns,
                  style.row
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex min-w-[3.25rem] shrink-0 justify-center whitespace-nowrap rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em]",
                      style.pill
                    )}
                  >
                    {slotLabel(player.slot ?? player.roster_slot)}
                  </span>
                  <span className={cn("h-2.5 w-2.5 rounded-full", style.dot)} />
                </span>
                <span className="flex flex-col gap-1">
                  <span className="font-black text-slate-50">{player.player_name}</span>
                  <span
                    className={cn(
                      "inline-flex w-fit shrink-0 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[9px] font-black uppercase tracking-[0.14em]",
                      style.pill
                    )}
                  >
                    {position}
                  </span>
                </span>
                <span className="text-slate-400">{player.school ?? player.player_school ?? "-"}</span>
                {showPositionColumn ? (
                  <span className={cn("font-black", style.text)}>{position}</span>
                ) : null}
                <span className="text-slate-400">{player.opponent ?? "TBD"}</span>
                <span className={cn("text-right font-black", style.text)}>
                  {projection.toFixed(1)}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {selectedPlayer ? (
        <div
          className="fixed inset-0 z-[120] flex justify-end bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label={`${selectedPlayer.player_name} player card`}
          onClick={() => setSelectedPlayer(null)}
        >
          <div
            className={cn(
              "relative flex h-full w-full max-w-[460px] flex-col overflow-hidden rounded-[1.75rem] border bg-[linear-gradient(145deg,var(--tw-gradient-stops))] p-5 shadow-[0_30px_90px_rgba(2,8,23,0.7)]",
              selectedStyle.border,
              selectedStyle.panel,
              "via-[#0b1424] to-[#050914]"
            )}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setSelectedPlayer(null)}
              className="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white"
              aria-label="Close player card"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="pr-12">
              <div className={cn("mb-4 inline-flex whitespace-nowrap rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em]", selectedStyle.pill)}>
                {selectedPosition} · {slotLabel(selectedPlayer.slot ?? selectedPlayer.roster_slot)}
              </div>
              <h3 className="text-3xl font-black italic leading-none text-slate-50">
                {selectedPlayer.player_name}
              </h3>
              <p className="mt-2 text-sm font-bold uppercase tracking-[0.16em] text-slate-400">
                {selectedPlayer.school ?? selectedPlayer.player_school ?? "-"} · Opp {selectedPlayer.opponent ?? "TBD"}
              </p>
              {leagueId ? (
                <button
                  type="button"
                  onClick={openTradeBuilder}
                  className={cn(
                    "mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] transition hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/50",
                    selectedStyle.border,
                    "bg-sky-400/15 text-sky-100 shadow-[0_0_34px_rgba(56,189,248,0.16)] hover:bg-sky-300/20"
                  )}
                >
                  <ArrowRightLeft className="h-4 w-4" />
                  Trade Player
                </button>
              ) : null}
            </div>

            <div className="mt-6 grid grid-cols-3 gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">Proj</p>
                <p className={cn("mt-1 text-2xl font-black", selectedStyle.text)}>
                  {formatPoints(selectedProjection)}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">Floor</p>
                <p className="mt-1 text-2xl font-black text-slate-100">{formatPoints(selectedPlayer.floor)}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">Ceiling</p>
                <p className="mt-1 text-2xl font-black text-slate-100">{formatPoints(selectedPlayer.ceiling)}</p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">Boom</p>
                <p className="mt-1 text-xl font-black text-emerald-200">{formatPercent(selectedPlayer.boom_prob)}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">Bust</p>
                <p className="mt-1 text-xl font-black text-rose-200">{formatPercent(selectedPlayer.bust_prob)}</p>
              </div>
            </div>

            <div className="mt-5 space-y-4 overflow-y-auto pr-1">
              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="mb-3 flex items-center gap-2 text-sky-200">
                  <Newspaper className="h-4 w-4" />
                  <p className="text-[10px] font-black uppercase tracking-[0.18em]">News</p>
                </div>
                <p className="text-sm font-semibold leading-6 text-slate-300">
                  {selectedNews ?? "No verified player news is loaded for this league response yet."}
                </p>
              </section>

              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="mb-3 flex items-center gap-2 text-sky-200">
                  <BarChart3 className="h-4 w-4" />
                  <p className="text-[10px] font-black uppercase tracking-[0.18em]">Previous Stats</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {["games", "pass_yards", "rush_yards", "receiving_yards", "receptions", "touchdowns"].map((stat) => (
                    <div key={stat} className="rounded-xl border border-white/10 bg-slate-950/25 px-3 py-2">
                      <p className="text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">
                        {stat.replace(/_/g, " ")}
                      </p>
                      <p className="mt-1 font-black text-slate-100">
                        {selectedStats?.[stat] ?? "-"}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="mb-3 flex items-center gap-2 text-sky-200">
                  <Activity className="h-4 w-4" />
                  <p className="text-[10px] font-black uppercase tracking-[0.18em]">Outlook</p>
                </div>
                <p className="text-sm font-semibold leading-6 text-slate-300">
                  {buildOutlook(selectedPlayer)}
                </p>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
