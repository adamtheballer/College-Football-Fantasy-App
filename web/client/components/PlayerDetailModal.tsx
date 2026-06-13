import { useEffect, useMemo, useState } from "react";
import { Activity, Bookmark, CalendarDays, Target, TrendingUp, Trophy, X, Zap } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Player } from "@/types/player";
import { useActiveLeagueId } from "@/hooks/use-active-league";

interface PlayerDetailModalProps {
  player: Player | null;
  isOpen: boolean;
  onClose: () => void;
  tradeLeagueId?: number | null;
}

type MatchupSnapshot = {
  grade: string;
  rank: number | null;
  yardsPerTarget: number | null;
  yardsPerRush: number | null;
  pressureRate: number | null;
};

const posStyles: Record<string, { text: string; border: string; bg: string; glow: string; gradient: string }> = {
  QB: {
    text: "text-blue-100",
    border: "border-blue-300/35",
    bg: "bg-blue-500/15",
    glow: "shadow-[0_0_34px_rgba(96,165,250,0.26)]",
    gradient: "from-blue-500/24 via-cyan-400/10 to-transparent",
  },
  RB: {
    text: "text-emerald-100",
    border: "border-emerald-300/35",
    bg: "bg-emerald-500/15",
    glow: "shadow-[0_0_34px_rgba(74,222,128,0.24)]",
    gradient: "from-emerald-500/24 via-cyan-400/10 to-transparent",
  },
  WR: {
    text: "text-violet-100",
    border: "border-violet-300/35",
    bg: "bg-violet-500/15",
    glow: "shadow-[0_0_34px_rgba(196,181,253,0.24)]",
    gradient: "from-violet-500/24 via-cyan-400/10 to-transparent",
  },
  TE: {
    text: "text-amber-100",
    border: "border-amber-300/35",
    bg: "bg-amber-500/15",
    glow: "shadow-[0_0_34px_rgba(251,191,36,0.22)]",
    gradient: "from-amber-500/24 via-cyan-400/10 to-transparent",
  },
  K: {
    text: "text-slate-100",
    border: "border-slate-300/35",
    bg: "bg-slate-400/15",
    glow: "shadow-[0_0_28px_rgba(203,213,225,0.18)]",
    gradient: "from-slate-400/20 via-cyan-400/8 to-transparent",
  },
};

const matchupGradeClass = (grade?: string) => {
  if (grade === "A+" || grade === "A") return "text-emerald-300";
  if (grade === "B") return "text-lime-300";
  if (grade === "C") return "text-amber-300";
  if (grade === "D") return "text-orange-300";
  if (grade === "F") return "text-red-300";
  return "text-slate-400";
};

const formatNumber = (value: unknown, fallback = "—") => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  const rounded = Math.round(parsed * 10) / 10;
  return Number.isInteger(rounded) ? rounded.toLocaleString() : rounded.toFixed(1);
};

const getInitials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

export function PlayerDetailModal({ player, isOpen, onClose, tradeLeagueId = null }: PlayerDetailModalProps) {
  const navigate = useNavigate();
  const { activeLeagueId } = useActiveLeagueId();
  const [matchup, setMatchup] = useState<MatchupSnapshot | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [schedule, setSchedule] = useState<
    { week: number; opponent: string; homeAway: string; grade: string; colorClass: string }[]
  >([]);

  useEffect(() => {
    if (!player || !isOpen) return;
    const controller = new AbortController();
    const season = new Date().getFullYear();
    const week = 1;

    setMatchup(null);
    setReasons([]);
    setSchedule([]);

    apiGet<{ data: any[] }>(`/schedule/player/${player.id}`, { season, week, weeks: 4 }, controller.signal)
      .then((payload) => {
        const rows = payload?.data ?? [];
        setSchedule(
          rows.slice(0, 4).map((game) => ({
            week: game.week,
            opponent: game.opponent,
            homeAway: game.home_away,
            grade: game.grade,
            colorClass: matchupGradeClass(game.grade),
          }))
        );

        const nextOpponent = rows[0]?.opponent;
        const nextWeek = rows[0]?.week ?? week;
        if (!nextOpponent) return;

        apiGet<{ data: any[] }>(
          "/matchups",
          { season, week: nextWeek, team: nextOpponent, position: player.pos },
          controller.signal
        )
          .then((matchupPayload) => {
            const row = matchupPayload?.data?.[0];
            if (!row) return;
            setMatchup({
              grade: row.grade,
              rank: row.rank,
              yardsPerTarget: row.yards_per_target,
              yardsPerRush: row.yards_per_rush,
              pressureRate: row.pressure_rate,
            });
          })
          .catch(() => {});
      })
      .catch(() => {});

    apiGet<{ reasons: { detail: string }[] }>(`/projections/${player.id}/explanations`, { season, week }, controller.signal)
      .then((payload) => setReasons((payload?.reasons ?? []).slice(0, 4).map((reason) => reason.detail)))
      .catch(() => {});

    return () => controller.abort();
  }, [player, isOpen]);

  const productionStats = useMemo(() => {
    if (!player) return [];
    if (player.pos === "QB") {
      return [
        { label: "Pass Yds", value: formatNumber(player.projection.passingYards) },
        { label: "Pass TD", value: formatNumber(player.projection.passingTds) },
        { label: "INT", value: formatNumber(player.projection.ints) },
        { label: "Rush Yds", value: formatNumber(player.projection.rushingYards) },
      ];
    }
    if (player.pos === "K") {
      const kickerStats = player.projection as Player["projection"] & { fg?: number; xp?: number };
      return [
        { label: "FG", value: formatNumber(kickerStats.fg) },
        { label: "XP", value: formatNumber(kickerStats.xp) },
        { label: "Floor", value: formatNumber(player.projection.floor) },
        { label: "Ceiling", value: formatNumber(player.projection.ceiling) },
      ];
    }
    return [
      { label: "Rush Yds", value: formatNumber(player.projection.rushingYards) },
      { label: "Rec Yds", value: formatNumber(player.projection.receivingYards) },
      { label: "Receptions", value: formatNumber(player.projection.receptions) },
      { label: "TDs", value: formatNumber((player.projection.rushingTds ?? 0) + (player.projection.receivingTds ?? 0)) },
    ];
  }, [player]);

  if (!player || !isOpen) return null;

  const position = String(player.pos || "").toUpperCase();
  const style = posStyles[position] ?? posStyles.QB;
  const targetLeagueId = tradeLeagueId ?? activeLeagueId;
  const nextGame = schedule[0];
  const weeklyProjection =
    Number(player.projection.fpts) > 80 ? Number(player.projection.fpts) / 12 : Number(player.projection.fpts);

  return (
    <div className="fixed inset-0 z-[1600] bg-slate-950/45 backdrop-blur-2xl" onClick={onClose}>
      <div
        className="absolute right-0 top-0 h-screen w-full overflow-hidden border-l border-cyan-200/15 bg-[#071120]/96 shadow-[-40px_0_120px_rgba(0,0,0,0.55)] animate-in slide-in-from-right-10 duration-300 md:w-[75vw]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-90", style.gradient)} />
        <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-cyan-300/12 blur-[110px]" />
        <div className="pointer-events-none absolute bottom-0 left-1/4 h-80 w-96 rounded-full bg-blue-500/10 blur-[120px]" />

        <div className="relative flex h-full flex-col p-6 lg:p-8">
          <div className="flex items-start justify-between gap-6">
            <div className="min-w-0">
              <p className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100/70">Player Card</p>
              <h2 className="mt-2 truncate text-4xl font-black italic uppercase leading-none tracking-tight text-white drop-shadow-[0_0_24px_rgba(34,211,238,0.14)] lg:text-6xl">
                {player.name}
              </h2>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-white/12 bg-white/[0.055] px-4 py-2 text-[10px] font-black uppercase tracking-[0.22em] text-slate-200">
                  {player.school}
                </span>
                <span className={cn("rounded-full border px-4 py-2 text-[10px] font-black uppercase tracking-[0.22em]", style.border, style.bg, style.text, style.glow)}>
                  {position || "N/A"}
                </span>
                <span className="rounded-full border border-emerald-300/20 bg-emerald-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-100">
                  {player.status}
                </span>
              </div>
            </div>

            <div className="flex shrink-0 gap-3">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-12 w-12 rounded-2xl border-white/10 bg-white/5 text-cyan-100"
              >
                <Bookmark className="h-5 w-5" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-12 w-12 rounded-2xl border-white/10 bg-white/5 text-white hover:bg-red-400/10 hover:text-red-100"
                onClick={onClose}
                aria-label="Close player card"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
          </div>

          <div className="mt-7 grid min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_380px]">
            <div className="grid min-h-0 gap-5">
              <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
                {[
                  { label: "ADP", value: formatNumber(player.sheetAdp ?? player.adp), icon: TrendingUp },
                  { label: "Rank", value: `#${formatNumber(player.rank, "—")}`, icon: Target },
                  { label: "Projection", value: formatNumber(player.sheetProjectedSeasonPoints ?? player.projection.fpts), icon: Zap },
                  { label: "Rostered", value: `${formatNumber(player.rostered, "0")}%`, icon: Trophy },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-[1.5rem] border border-white/10 bg-white/[0.055] p-5">
                    <stat.icon className="h-5 w-5 text-cyan-200" />
                    <p className="mt-5 text-[9px] font-black uppercase tracking-[0.22em] text-slate-400">{stat.label}</p>
                    <p className="mt-2 truncate text-3xl font-black italic text-white">{stat.value}</p>
                  </div>
                ))}
              </div>

              <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
                <div className="rounded-[1.75rem] border border-white/10 bg-slate-950/35 p-5">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100/70">Projected Production</p>
                      <p className="mt-1 text-sm font-bold text-slate-400">Season profile and fantasy output</p>
                    </div>
                    <p className={cn("text-5xl font-black italic", style.text)}>
                      {formatNumber(player.projection.fpts)}
                    </p>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    {productionStats.map((stat) => (
                      <div key={stat.label} className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                        <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">{stat.label}</p>
                        <p className="mt-1 text-2xl font-black text-white">{stat.value}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[1.75rem] border border-white/10 bg-slate-950/35 p-5">
                  <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100/70">
                    <Activity className="h-4 w-4" />
                    Weekly Outlook
                  </p>
                  <div className="mt-5 grid grid-cols-3 gap-3">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                      <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">Week</p>
                      <p className="mt-1 text-xl font-black text-white">{nextGame?.week ?? "—"}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                      <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">Grade</p>
                      <p className={cn("mt-1 text-xl font-black", matchupGradeClass(matchup?.grade ?? nextGame?.grade))}>
                        {matchup?.grade ?? nextGame?.grade ?? "—"}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                      <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">FPTS</p>
                      <p className="mt-1 text-xl font-black text-white">{formatNumber(weeklyProjection)}</p>
                    </div>
                  </div>
                  <p className="mt-4 text-sm font-semibold leading-6 text-slate-300">
                    {nextGame ? `${nextGame.homeAway ?? "vs"} ${nextGame.opponent}` : "No upcoming schedule data available."}
                    {matchup?.rank ? ` Defense rank ${matchup.rank}.` : ""}
                  </p>
                </div>
              </div>

              <div className="grid min-h-0 gap-5 xl:grid-cols-2">
                <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-5">
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100/70">Fantasy Read</p>
                  <p className="mt-4 line-clamp-4 text-sm font-semibold leading-6 text-slate-300">
                    {player.analysis || "No player analysis has been added yet."}
                  </p>
                </div>
                <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-5">
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100/70">Projection Drivers</p>
                  <div className="mt-4 grid gap-2">
                    {(reasons.length ? reasons : ["Usage, depth chart role, and scoring format drive this ranking."]).map((reason) => (
                      <p key={reason} className="line-clamp-1 rounded-xl border border-white/10 bg-slate-950/30 px-3 py-2 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-300">
                        {reason}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <aside className="grid min-h-0 gap-5">
              <div className={cn("relative overflow-hidden rounded-[2rem] border p-6", style.border, style.bg, style.glow)}>
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent" />
                <div className="relative flex aspect-square items-center justify-center rounded-[1.5rem] border border-white/10 bg-slate-950/35">
                  {player.imageUrl ? (
                    <img src={player.imageUrl} alt={player.name} className="h-full w-full rounded-[1.5rem] object-cover" />
                  ) : (
                    <div className="flex h-36 w-36 items-center justify-center rounded-[2rem] border border-white/10 bg-white/[0.06] text-5xl font-black italic text-cyan-200">
                      {getInitials(player.name)}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5">
                <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100/70">
                  <CalendarDays className="h-4 w-4" />
                  Next Games
                </p>
                <div className="mt-4 grid gap-2">
                  {schedule.length ? schedule.map((game) => (
                    <div key={`${game.week}-${game.opponent}`} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/30 px-3 py-2">
                      <p className="truncate text-[11px] font-black uppercase tracking-[0.12em] text-slate-300">
                        W{game.week} • {game.opponent}
                      </p>
                      <p className={cn("text-sm font-black", game.colorClass)}>{game.grade}</p>
                    </div>
                  )) : (
                    <p className="rounded-xl border border-dashed border-white/10 p-3 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                      No schedule data
                    </p>
                  )}
                </div>
              </div>

              <Button
                type="button"
                className="h-14 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 text-[11px] font-black uppercase tracking-[0.2em] text-slate-950 shadow-[0_0_28px_rgba(34,211,238,0.22)]"
                onClick={() => {
                  if (targetLeagueId) {
                    navigate(`/trade/${targetLeagueId}/${player.id}`);
                  } else {
                    navigate("/trade");
                  }
                  onClose();
                }}
              >
                Trade For Player
              </Button>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
