import { Bell, MessageCircle, ShieldAlert } from "lucide-react";
import { useRef } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { SideBySideMatchup } from "@/components/league/SideBySideMatchup";
import { WinChanceBar } from "@/components/league/WinChanceMeter";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { OpeningWeekPatch } from "@/components/league/OpeningWeekPatch";
import { RivalWeekPatch } from "@/components/league/RivalWeekPatch";
import { RivalryControls } from "@/components/league/RivalryControls";
import { EmptyState, ErrorState, SkeletonState } from "@/components/states";
import { SurfaceCard, type StatusBadgeVariant } from "@/components/fantasy";
import { useLeagueDetail, useLeagueMatchupTab, useLeagueScoreboard } from "@/hooks/use-leagues";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { LeagueMatchupTabResponse, LeagueMatchupTeam, LeagueScoreboardRow } from "@/types/league";

export function formatMatchupStatus(status: string | null | undefined) {
  const normalized = (status || "projected").toLowerCase();
  if (normalized === "live") return "Live";
  if (normalized === "final") return "Final";
  if (normalized === "stat_corrected" || normalized === "corrected") return "Corrected";
  if (normalized === "delayed") return "Delayed";
  if (normalized === "unavailable") return "Unavailable";
  return "Projected";
}

export function matchupStatusVariant(status: string | null | undefined): StatusBadgeVariant {
  const normalized = (status || "projected").toLowerCase();
  if (normalized === "live") return "live";
  if (normalized === "final") return "final";
  if (normalized === "stat_corrected" || normalized === "corrected") return "corrected";
  if (normalized === "delayed") return "delayed";
  if (normalized === "unavailable") return "unavailable";
  return "projected";
}

export function formatMatchupPoints(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";
}

export function shouldShowMatchupScorePanels(status: string | null | undefined) {
  return ["Live", "Final", "Corrected"].includes(formatMatchupStatus(status));
}

function teamTotal(team: LeagueMatchupTeam | null) {
  return team?.live_projected_total ?? team?.projected_total ?? team?.projected_points ?? null;
}

function leadingTeam(myTeam: LeagueMatchupTeam | null, opponentTeam: LeagueMatchupTeam | null) {
  const myProbability = myTeam?.win_probability;
  const opponentProbability = opponentTeam?.win_probability;
  if (
    typeof myProbability !== "number" ||
    typeof opponentProbability !== "number" ||
    !Number.isFinite(myProbability) ||
    !Number.isFinite(opponentProbability)
  ) {
    return "Win chance unavailable";
  }
  if (myProbability === opponentProbability) return "Even matchup";
  return myProbability > opponentProbability
    ? myTeam?.fantasy_team_name ?? "Your Team"
    : opponentTeam?.fantasy_team_name ?? "Opponent";
}

function teamInitials(name: string | null | undefined) {
  const letters = (name ?? "Team")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
  return letters || "TM";
}

function displayedProbabilityPair(
  myPercent: number | null | undefined,
  opponentPercent: number | null | undefined,
) {
  if (
    typeof myPercent !== "number" ||
    typeof opponentPercent !== "number" ||
    !Number.isFinite(myPercent) ||
    !Number.isFinite(opponentPercent) ||
    Math.abs(myPercent + opponentPercent - 100) > 0.001
  ) {
    return null;
  }
  const my = Math.round((myPercent + Number.EPSILON) * 10) / 10;
  return { my, opponent: Math.round((100 - my + Number.EPSILON) * 10) / 10 };
}

export function freshnessText(data: LeagueMatchupTabResponse | undefined): string | null {
  const freshness = data?.live_scoring_freshness;
  if (freshness?.state === "fresh") {
    const age = freshness.data_age_seconds;
    const ageText = typeof age === "number" ? ` Last provider update ${age < 60 ? "just now" : `${Math.floor(age / 60)}m ago`}.` : "";
    return `Live provider data is current.${ageText}`;
  }
  if (freshness?.state === "delayed") return "Live provider data is delayed. Do not treat the score as fully current.";
  if (freshness?.state === "stale") return "Live provider data is stale. Existing scores are retained while the worker retries.";
  if (freshness?.state === "unavailable" && data?.status && formatMatchupStatus(data.status) === "Live") {
    return "Live score data is unavailable. Existing scores should not be replaced by false zeroes.";
  }
  const label = formatMatchupStatus(data?.status);
  if (label === "Live") return "Live scoring refreshes automatically while games are active.";
  if (label === "Corrected") return "Scores include a stat correction and should be treated as corrected.";
  if (label === "Final") return "This matchup is final unless a controlled correction is applied.";
  if (label === "Delayed") return "Provider data is delayed. Do not treat the score as fully current.";
  if (label === "Unavailable") return "Provider data is unavailable. Existing scores should not be replaced by false zeroes.";
  // Pregame projections are already communicated by the scoreboard and each
  // player row. Do not add a redundant explanatory callout.
  return null;
}

function MatchupTeamSummary({
  team,
  accent,
  align,
  status,
  currentScore,
}: {
  team: LeagueMatchupTeam | null;
  accent: "brand" | "pink";
  align: "left" | "right";
  status: string;
  currentScore?: number | null;
}) {
  const isBrand = accent === "brand";
  const showActual = shouldShowMatchupScorePanels(status) && typeof currentScore === "number";
  const projected = teamTotal(team);

  return (
    <div className={`min-w-0 ${align === "right" ? "text-right" : "text-left"}`}>
      <div className={`flex items-center ${align === "right" ? "justify-end" : "justify-start"}`}>
        <ManagerAvatar
          avatarUrl={team?.owner_avatar_url}
          managerName={team?.fantasy_team_name}
          size="sm"
          className={`sm:h-10 sm:w-10 sm:text-sm ${
            isBrand
              ? "border-cfb-brand/80 bg-cfb-brand/10 text-cfb-brand"
              : "border-cfb-pink/80 bg-cfb-pink/10 text-cfb-pink"
          }`}
        />
      </div>
      <p className="mt-0.5 truncate text-[11px] font-black text-cfb-text-primary sm:mt-1 sm:text-sm">
        {team?.fantasy_team_name ?? "Team TBD"}
      </p>
      <p className="text-[9px] font-bold text-cfb-text-muted sm:text-[10px]">{team?.record ?? "0-0-0"}</p>
      <p className="cfb-score-value mt-0.5 text-2xl text-cfb-text-primary sm:mt-1 sm:text-4xl">
        {showActual ? formatMatchupPoints(team?.current_points ?? currentScore) : formatMatchupPoints(projected)}
      </p>
      <p aria-label={`Projected ${formatMatchupPoints(projected)}`} className="mt-0.5 text-[9px] font-bold text-cfb-text-muted">
        {showActual ? `Proj ${formatMatchupPoints(projected)}` : "Pregame projection"}
      </p>
    </div>
  );
}

function CompactMatchupScoreboard({
  data,
  myTeam,
  opponentTeam,
  displayWeek,
  scoreRow,
  matchupIndex,
  matchupCount,
}: {
  data: LeagueMatchupTabResponse;
  myTeam: LeagueMatchupTeam | null;
  opponentTeam: LeagueMatchupTeam | null;
  displayWeek: number;
  scoreRow?: LeagueScoreboardRow;
  matchupIndex: number;
  matchupCount: number;
}) {
  const winChance = displayedProbabilityPair(myTeam?.win_probability, opponentTeam?.win_probability);
  const myTeamIsLeading = Boolean(winChance && winChance.my >= winChance.opponent);

  return (
    <section className="relative border-b border-cfb-border-subtle bg-cfb-surface-raised/50 px-3 pb-3 pt-6 sm:px-5 sm:pb-4 sm:pt-7">
      <h2 className="sr-only">
        {myTeam?.fantasy_team_name ?? "Your team"} vs {opponentTeam?.fantasy_team_name ?? "Opponent"}
      </h2>
      {matchupCount > 1 ? (
        <div
          aria-label={`Matchup ${matchupIndex + 1} of ${matchupCount}. Swipe left or right to view another matchup.`}
          className="absolute right-3 top-2 flex items-center gap-1 sm:right-5"
        >
          {Array.from({ length: matchupCount }, (_, index) => (
            <span
              key={index}
              aria-hidden="true"
              className={`h-1.5 rounded-full transition-[width,background-color] ${
                index === matchupIndex ? "w-3 bg-cfb-brand" : "w-1.5 bg-cfb-border-strong"
              }`}
            />
          ))}
        </div>
      ) : null}
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 sm:gap-5">
        <MatchupTeamSummary
          team={myTeam}
          accent="brand"
          align="left"
          status={data.status ?? "projected"}
          currentScore={scoreRow?.home_score}
        />

        <div className="flex min-w-[80px] flex-col items-center text-center">
          <span className="font-ui text-[8px] font-bold uppercase tracking-[0.06em] text-cfb-brand">Week {displayWeek} matchup</span>
          <span className="mt-0.5 font-ui text-[8px] font-bold uppercase tracking-[0.06em] text-cfb-text-muted">Win chance</span>
          <div className="mt-0.5 flex items-center gap-1 whitespace-nowrap text-[10px] font-black tabular-nums sm:text-xs">
            <span className={myTeamIsLeading ? "text-emerald-300" : "text-red-300"}>
              {winChance ? `${winChance.my.toFixed(1)}%` : "—"}
            </span>
            <span className="text-cfb-text-muted">VS</span>
            <span className={myTeamIsLeading ? "text-red-300" : "text-emerald-300"}>
              {winChance ? `${winChance.opponent.toFixed(1)}%` : "—"}
            </span>
          </div>
        </div>

        <MatchupTeamSummary
          team={opponentTeam}
          accent="pink"
          align="right"
          status={data.status ?? "projected"}
          currentScore={scoreRow?.away_score}
        />
      </div>

      <div className="mt-3 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-t border-cfb-border-subtle pt-2 text-[9px] font-bold uppercase tracking-[0.12em] text-cfb-text-muted">
        <span>{winChance ? `${winChance.my.toFixed(1)}%` : "—"}</span>
        {winChance ? <WinChanceBar myPercent={myTeam?.win_probability} opponentPercent={opponentTeam?.win_probability} className="h-2" testIdPrefix="scoreboard-win-chance" /> : <span className="text-center normal-case tracking-normal">Win Probability available after lineups are set</span>}
        <span>{winChance ? `${winChance.opponent.toFixed(1)}%` : "—"}</span>
      </div>
    </section>
  );
}

export default function LeagueMatchup() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const weekParam = Number(searchParams.get("week"));
  const selectedWeek = Number.isInteger(weekParam) && weekParam > 0 ? weekParam : 1;
  const matchupParam = Number(searchParams.get("matchup"));
  const selectedMatchupId = Number.isInteger(matchupParam) && matchupParam > 0 ? matchupParam : undefined;
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const postDraft = isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });
  const matchupQuery = useLeagueMatchupTab(parsedLeagueId, selectedWeek, selectedMatchupId, postDraft);
  const data = matchupQuery.data;
  const myTeam = data?.my_team ?? data?.user_team ?? null;
  const opponentTeam = data?.opponent_team ?? null;
  const displayWeek = data?.week ?? selectedWeek;
  const hasScheduledMatchup = Boolean(data?.matchup_id && myTeam && opponentTeam);
  const scoreboardQuery = useLeagueScoreboard(
    parsedLeagueId,
    displayWeek,
    postDraft,
  );
  const scheduledMatchups = scoreboardQuery.data?.data ?? [];
  const activeMatchupId = selectedMatchupId ?? data?.matchup_id;
  const activeScoreRow = scheduledMatchups.find((matchup) => matchup.matchup_id === activeMatchupId);
  const activeMatchupIndex = Math.max(0, scheduledMatchups.findIndex((matchup) => matchup.matchup_id === activeMatchupId));
  const swipeStartX = useRef<number | null>(null);
  const scoringFreshnessMessage = freshnessText(data);
  const scoringFreshnessTone = data?.live_scoring_freshness?.state === "fresh"
    ? "border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-100"
    : ["delayed", "stale", "unavailable"].includes(data?.live_scoring_freshness?.state ?? "")
      ? "border-amber-300/25 bg-amber-300/[0.07] text-amber-100"
      : "border-cfb-border-subtle bg-cfb-surface text-cfb-text-secondary";
  const updateSelection = (week: number, matchupId?: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("week", String(week));
    if (matchupId) next.set("matchup", String(matchupId));
    else next.delete("matchup");
    setSearchParams(next);
  };
  const selectAdjacentMatchup = (direction: -1 | 1) => {
    if (scheduledMatchups.length < 2) return;
    const nextIndex = (activeMatchupIndex + direction + scheduledMatchups.length) % scheduledMatchups.length;
    updateSelection(displayWeek, scheduledMatchups[nextIndex]?.matchup_id);
  };

  if (leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-0 py-4 sm:px-6 sm:py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8">
        <ErrorState
          title="Unable to load league"
          message="The league could not be loaded. Confirm the backend is available, then try again."
          retryLabel="Try Again"
          onRetry={() => void leagueQuery.refetch()}
        />
      </main>
    );
  }

  if (!postDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/lobby`} replace />;
  }

  return (
    <main data-testid="league-matchup-page" className="flex w-full max-w-none flex-col gap-0 pb-24 pt-1 sm:pt-4">
      <header className="flex min-h-16 items-center gap-3 border-b border-cfb-border-subtle px-3 sm:px-5">
        <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cfb-brand/50 bg-cfb-brand/[0.1] text-[10px] font-black text-cfb-brand">{teamInitials(leagueQuery.data?.name)}</span>
        <div className="min-w-0 flex-1 text-left text-base font-black italic tracking-tight text-cfb-text-primary">
          <span className="block truncate">{leagueQuery.data?.name ?? "League"}</span>
        </div>
        <button type="button" aria-label="Notifications" onClick={() => navigate("/alerts")} className="flex h-11 w-11 items-center justify-center rounded-full bg-cfb-surface-raised text-cfb-text-primary hover:bg-cfb-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70"><Bell className="h-4 w-4" aria-hidden="true" /></button>
        <button type="button" aria-label="Messages" onClick={() => navigate("/chats")} className="flex h-11 w-11 items-center justify-center rounded-full bg-cfb-surface-raised text-cfb-text-primary hover:bg-cfb-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70"><MessageCircle className="h-4 w-4" aria-hidden="true" /></button>
      </header>
      <div className="px-3 sm:px-5">
        <LeagueTabs leagueId={parsedLeagueId} draftStatus={leagueQuery.data?.draft?.status} leagueStatus={leagueQuery.data?.status} />
      </div>

      <div className="px-3 py-2 sm:px-5"><RivalryControls leagueId={parsedLeagueId} /></div>

      {matchupQuery.isError ? (
        <ErrorState
          title="Unable to load matchup"
          message="The matchup API did not return a usable response for this league and week."
          retryLabel="Try Again"
          onRetry={() => void matchupQuery.refetch()}
        />
      ) : matchupQuery.isLoading ? (
        <SurfaceCard variant="default" padding="spacious">
          <SkeletonState rows={5} />
        </SurfaceCard>
      ) : !hasScheduledMatchup ? (
        <EmptyState
          title="No matchup scheduled"
          description={
            data?.message ??
            "No real matchup exists for this league and week yet. Once the schedule is generated, the opponent, win chance, and side-by-side lineup will appear here."
          }
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
      ) : (
        <>
          <div
            data-testid="matchup-swipe-surface"
            onTouchStart={(event) => {
              swipeStartX.current = event.touches[0]?.clientX ?? null;
            }}
            onTouchEnd={(event) => {
              const startX = swipeStartX.current;
              swipeStartX.current = null;
              const endX = event.changedTouches[0]?.clientX;
              if (startX === null || typeof endX !== "number" || Math.abs(endX - startX) < 48) return;
              selectAdjacentMatchup(endX < startX ? 1 : -1);
            }}
            onTouchCancel={() => {
              swipeStartX.current = null;
            }}
          >
            <OpeningWeekPatch week={displayWeek} />
            <RivalWeekPatch rivalry={data.rivalry} leagueId={parsedLeagueId} matchupId={data.matchup_id} />
            <CompactMatchupScoreboard
              data={data}
              myTeam={myTeam}
              opponentTeam={opponentTeam}
              displayWeek={displayWeek}
              scoreRow={activeScoreRow}
              matchupIndex={activeMatchupIndex}
              matchupCount={scheduledMatchups.length}
            />
          </div>

          {scoringFreshnessMessage ? (
            <p role="status" className={`mx-3 mt-3 rounded-lg border px-3 py-2 text-[11px] font-semibold sm:mx-5 ${scoringFreshnessTone}`}>
              {scoringFreshnessMessage}
            </p>
          ) : null}

          <div className="mx-3 mt-3 rounded-full bg-cfb-surface px-4 py-2 sm:mx-5"><p className="text-sm font-black text-cfb-text-primary">Starters</p></div>
          <div className="mt-2"><SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} leagueId={parsedLeagueId} scoringStatus={data.status} /></div>
        </>
      )}
    </main>
  );
}
