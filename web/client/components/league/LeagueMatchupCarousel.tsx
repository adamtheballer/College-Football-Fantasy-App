import { ChevronRight, Trophy } from "lucide-react";

import { WinChanceBar, formatDisplayedProbabilityPair } from "@/components/league/WinChanceMeter";
import type { LeagueDetail } from "@/types/league";

const formatPoints = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";

const formatRecord = (league: LeagueDetail) => {
  const summary = league.current_user_summary;
  if (!summary) return "0-0-0";
  return `${summary.wins ?? 0}-${summary.losses ?? 0}-${summary.ties ?? 0}`;
};

const probabilityPair = (league: LeagueDetail) => {
  const summary = league.current_user_summary;
  const left = summary?.win_probability_for;
  const right = summary?.win_probability_against;
  if (
    typeof left !== "number" ||
    typeof right !== "number" ||
    !Number.isFinite(left) ||
    !Number.isFinite(right) ||
    left < 5 ||
    right < 5 ||
    left > 95 ||
    right > 95 ||
    Math.abs(left + right - 100) > 0.000001
  ) {
    return null;
  }
  return formatDisplayedProbabilityPair(left, right);
};

export function LeagueMatchupCarousel({
  leagues,
  activeLeagueId,
  onOpenLeague,
}: {
  leagues: LeagueDetail[];
  activeLeagueId?: number | null;
  onOpenLeague: (leagueId: number) => void;
}) {
  return (
    <section aria-labelledby="league-matchup-carousel-title">
      <div className="mb-3 flex items-center justify-between gap-3 px-1 sm:mb-4">
        <div>
          <p className="cfb-micro-label text-cfb-brand">Your leagues</p>
          <h2 id="league-matchup-carousel-title" className="mt-1 text-xl font-black text-cfb-text-primary sm:text-2xl">
            Matchups at a glance
          </h2>
        </div>
        <p className="text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">Swipe leagues</p>
      </div>

      <div
        aria-label="Swipe through your league matchups"
        className="flex min-w-0 max-w-full snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain pb-1 touch-pan-x [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {leagues.map((league) => {
          const summary = league.current_user_summary;
          const chance = probabilityPair(league);
          const active = league.id === activeLeagueId;
          const hasMatchup = Boolean(summary?.opponent_team_name);

          return (
            <button
              key={league.id}
              type="button"
              onClick={() => onOpenLeague(league.id)}
              className={`w-[min(21rem,calc(100vw-2.5rem))] shrink-0 snap-start rounded-2xl border p-4 text-left shadow-[0_14px_34px_rgba(2,6,23,0.28)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 sm:w-[22rem] ${
                active
                  ? "border-cfb-brand/70 bg-cfb-brand/[0.12]"
                  : "border-cfb-border-subtle bg-cfb-surface-raised/90 hover:border-cfb-brand/45 hover:bg-cfb-surface-hover"
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-cfb-brand/35 bg-cfb-brand/[0.10] text-cfb-brand">
                  {league.icon_url ? (
                    <img src={league.icon_url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <Trophy className="h-4 w-4" aria-hidden="true" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-black text-cfb-text-primary">{league.name}</p>
                  <p className="mt-0.5 text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">
                    {formatRecord(league)} · {hasMatchup ? `Week ${summary?.matchup_week ?? 1}` : "Schedule pending"}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-cfb-brand" aria-hidden="true" />
              </div>

              <div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 border-y border-cfb-border-subtle py-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-black text-cfb-text-primary">{summary?.team_name ?? "Your Team"}</p>
                  <p className="mt-1 font-display text-2xl font-black tracking-[-0.06em] text-cfb-brand">
                    {formatPoints(summary?.projected_points_for)}
                  </p>
                </div>
                <span className="rounded-full border border-cfb-border-subtle bg-cfb-canvas px-2 py-1 text-[10px] font-black text-cfb-text-secondary">VS</span>
                <div className="min-w-0 text-right">
                  <p className="truncate text-xs font-black text-cfb-text-primary">{summary?.opponent_team_name ?? "Opponent TBD"}</p>
                  <p className="mt-1 font-display text-2xl font-black tracking-[-0.06em] text-cfb-pink">
                    {formatPoints(summary?.projected_points_against)}
                  </p>
                </div>
              </div>

              <div className="mt-3">
                <div className="mb-1.5 flex items-center justify-between gap-3 text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">
                  <span>Win chance</span>
                  <span className="text-cfb-text-secondary">
                    {chance ? `${chance.left.toFixed(1)}% / ${chance.right.toFixed(1)}%` : "Unavailable"}
                  </span>
                </div>
                {chance ? (
                  <WinChanceBar
                    myPercent={summary?.win_probability_for}
                    opponentPercent={summary?.win_probability_against}
                    className="h-2"
                    testIdPrefix={`league-card-${league.id}-win-chance`}
                  />
                ) : (
                  <div className="h-2 rounded-full bg-cfb-canvas" />
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
