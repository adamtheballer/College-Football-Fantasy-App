import { ChevronRight, Trophy } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

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

function LeagueIcon({ league }: { league: LeagueDetail }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = league.icon_url?.trim();

  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface text-cfb-brand">
      {imageUrl && !imageFailed ? (
        <img
          src={imageUrl}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setImageFailed(true)}
        />
      ) : (
        <Trophy data-testid={`league-icon-fallback-${league.id}`} className="h-4 w-4" aria-hidden="true" />
      )}
    </div>
  );
}

export function LeagueMatchupCarousel({
  leagues,
  activeLeagueId,
  onOpenLeague,
}: {
  leagues: LeagueDetail[];
  activeLeagueId?: number | null;
  onOpenLeague: (leagueId: number) => void;
}) {
  const railRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef(new Map<number, HTMLButtonElement>());
  const loopResetTimeoutRef = useRef<number | null>(null);
  const [visibleLeagueIndex, setVisibleLeagueIndex] = useState(0);
  const hasLoop = leagues.length > 1;
  const carouselLeagues = hasLoop ? [leagues[leagues.length - 1], ...leagues, leagues[0]] : leagues;

  const nearestCardIndex = useCallback(() => {
    const rail = railRef.current;
    if (!rail || rail.clientWidth <= 0 || carouselLeagues.length === 0) return null;

    const railCenter = rail.scrollLeft + rail.clientWidth / 2;
    let nearestIndex = 0;
    let nearestDistance = Number.POSITIVE_INFINITY;

    for (let index = 0; index < carouselLeagues.length; index += 1) {
      const card = cardRefs.current.get(index);
      if (!card) continue;
      const cardCenter = card.offsetLeft + card.offsetWidth / 2;
      const distance = Math.abs(cardCenter - railCenter);
      if (distance < nearestDistance) {
        nearestIndex = index;
        nearestDistance = distance;
      }
    }

    return nearestIndex;
  }, [carouselLeagues.length]);

  const scrollToCard = useCallback((index: number, behavior: ScrollBehavior = "auto") => {
    const rail = railRef.current;
    const card = cardRefs.current.get(index);
    if (!rail || !card) return;
    const target = { left: card.offsetLeft, behavior };
    if (typeof rail.scrollTo === "function") {
      rail.scrollTo(target);
    } else {
      // JSDOM does not implement Element#scrollTo, and this fallback also
      // keeps the carousel usable in older embedded web views.
      rail.scrollLeft = card.offsetLeft;
    }
  }, []);

  const syncVisibleLeague = useCallback(() => {
    const nearestIndex = nearestCardIndex();
    if (nearestIndex === null) return;
    const leagueIndex = hasLoop
      ? (nearestIndex === 0 ? leagues.length - 1 : nearestIndex === leagues.length + 1 ? 0 : nearestIndex - 1)
      : nearestIndex;
    setVisibleLeagueIndex((current) => (current === leagueIndex ? current : leagueIndex));
  }, [hasLoop, leagues.length, nearestCardIndex]);

  const normalizeLoopPosition = useCallback(() => {
    if (!hasLoop) return;
    const nearestIndex = nearestCardIndex();
    if (nearestIndex === 0) {
      scrollToCard(leagues.length);
    } else if (nearestIndex === leagues.length + 1) {
      scrollToCard(1);
    }
  }, [hasLoop, leagues.length, nearestCardIndex, scrollToCard]);

  const handleScroll = useCallback(() => {
    syncVisibleLeague();
    if (!hasLoop) return;
    if (loopResetTimeoutRef.current !== null) window.clearTimeout(loopResetTimeoutRef.current);
    loopResetTimeoutRef.current = window.setTimeout(() => {
      normalizeLoopPosition();
      loopResetTimeoutRef.current = null;
    }, 120);
  }, [hasLoop, normalizeLoopPosition, syncVisibleLeague]);

  useEffect(() => {
    setVisibleLeagueIndex(0);
    const animationFrame = window.requestAnimationFrame(() => {
      if (hasLoop) scrollToCard(1);
      syncVisibleLeague();
    });
    window.addEventListener("resize", syncVisibleLeague);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      if (loopResetTimeoutRef.current !== null) window.clearTimeout(loopResetTimeoutRef.current);
      window.removeEventListener("resize", syncVisibleLeague);
    };
  }, [hasLoop, leagues.length, scrollToCard, syncVisibleLeague]);

  return (
    <section aria-labelledby="league-matchup-carousel-title">
      <div className="mb-3 flex items-center justify-between gap-3 px-1 sm:mb-4">
        <div>
          <p className="cfb-micro-label text-cfb-brand">Your leagues</p>
          <h2 id="league-matchup-carousel-title" className="mt-1 text-xl font-black text-cfb-text-primary sm:text-2xl">
            Matchups at a glance
          </h2>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <p className="text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">Swipe leagues</p>
          {leagues.length > 0 ? (
            <div
              aria-label={`Showing league ${visibleLeagueIndex + 1} of ${leagues.length}`}
              data-testid="league-carousel-pagination"
              className="flex h-2 items-center justify-end gap-1.5"
            >
              {leagues.map((league, index) => (
                <span
                  key={league.id}
                  aria-hidden="true"
                  data-active={index === visibleLeagueIndex ? "true" : "false"}
                  className={`block rounded-full transition-[width,background-color] duration-200 ${
                    index === visibleLeagueIndex
                      ? "h-1.5 w-4 bg-cfb-brand"
                      : "h-1.5 w-1.5 bg-cfb-text-muted/50"
                  }`}
                />
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div
        aria-label="Swipe through your league matchups"
        ref={railRef}
        onScroll={handleScroll}
        className="flex min-w-0 max-w-full snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain pb-1 touch-pan-x [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {carouselLeagues.map((league, index) => {
          const summary = league.current_user_summary;
          const chance = probabilityPair(league);
          const active = league.id === activeLeagueId;
          const hasMatchup = Boolean(summary?.opponent_team_name);

          return (
            <button
              key={`${league.id}-${index}`}
              data-testid={`league-carousel-card-${league.id}-${index}`}
              type="button"
              ref={(element) => {
                if (element) cardRefs.current.set(index, element);
                else cardRefs.current.delete(index);
              }}
              onClick={() => onOpenLeague(league.id)}
              className={`w-[min(21rem,calc(100vw-2.5rem))] shrink-0 snap-start rounded-2xl border p-4 text-left shadow-[0_14px_34px_rgba(2,6,23,0.28)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 sm:w-[22rem] ${
                active
                  ? "border-cfb-brand/70 bg-cfb-surface-raised"
                  : "border-cfb-border-subtle bg-cfb-surface-raised/90 hover:border-cfb-brand/45 hover:bg-cfb-surface-hover"
              }`}
            >
              <div className="flex items-center gap-3">
                <LeagueIcon league={league} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-black text-cfb-text-primary">{league.name}</p>
                  <p className="mt-0.5 text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">
                    {formatRecord(league)} · {hasMatchup ? `Week ${summary?.matchup_week ?? 1}` : "Schedule pending"}
                  </p>
                  {summary?.is_rivalry_matchup ? <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-amber-200">Rival Week</p> : null}
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
