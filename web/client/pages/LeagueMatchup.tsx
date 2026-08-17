import { Clock, ShieldAlert, Trophy } from "lucide-react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { SideBySideMatchup } from "@/components/league/SideBySideMatchup";
import { WeekSelector } from "@/components/league/WeekSelector";
import { WinChanceBar, WinChanceMeter } from "@/components/league/WinChanceMeter";
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
  return team?.projected_total ?? team?.projected_points ?? null;
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

function MatchupRail({
  matchups,
  selectedMatchupId,
  isLoading,
  onSelect,
}: {
  matchups: LeagueScoreboardRow[];
  selectedMatchupId: number | undefined;
  isLoading: boolean;
  onSelect: (matchupId: number) => void;
}) {
  if (!isLoading && matchups.length === 0) return null;

  return (
    <section
      aria-label="League matchups"
      className="overflow-hidden rounded-[1.25rem] border border-cfb-border-subtle bg-cfb-surface/70"
    >
      <div
        aria-label="Swipe through league matchups"
        className="flex snap-x snap-mandatory gap-2 overflow-x-auto px-3 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:px-4"
      >
        {isLoading ? Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="h-[62px] min-w-[184px] animate-pulse rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised" />
        )) : matchups.map((matchup) => {
          const selected = matchup.matchup_id === selectedMatchupId;
          const status = formatMatchupStatus(matchup.status);
          return (
            <button
              key={matchup.matchup_id}
              type="button"
              aria-label={`View ${matchup.home_team_name} versus ${matchup.away_team_name}`}
              aria-pressed={selected}
              onClick={() => onSelect(matchup.matchup_id)}
              className={`snap-start shrink-0 rounded-xl border px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 ${
                selected
                  ? "border-cfb-brand/80 bg-cfb-brand/[0.12] text-cfb-text-primary"
                  : "border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-secondary hover:border-cfb-border-strong hover:bg-cfb-surface-hover"
              }`}
            >
              <div className="flex min-w-[188px] items-center gap-2">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-cfb-brand/45 bg-cfb-brand/[0.08] text-[10px] font-black text-cfb-brand">
                  {teamInitials(matchup.home_team_name)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[11px] font-black leading-4">{matchup.home_team_name}</p>
                  <p className="truncate text-[10px] font-bold text-cfb-text-muted">{formatMatchupPoints(matchup.home_score)}</p>
                </div>
                <span className="text-[9px] font-black uppercase tracking-[0.1em] text-cfb-text-muted">vs</span>
                <div className="min-w-0 flex-1 text-right">
                  <p className="truncate text-[11px] font-black leading-4">{matchup.away_team_name}</p>
                  <p className="truncate text-[10px] font-bold text-cfb-text-muted">{formatMatchupPoints(matchup.away_score)}</p>
                </div>
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-cfb-pink/45 bg-cfb-pink/[0.08] text-[10px] font-black text-cfb-pink">
                  {teamInitials(matchup.away_team_name)}
                </span>
              </div>
              <p className={`mt-1.5 text-center text-[8px] font-black uppercase tracking-[0.13em] ${selected ? "text-cfb-brand" : "text-cfb-text-muted"}`}>
                {status}
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
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

export function freshnessText(data: LeagueMatchupTabResponse | undefined) {
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
  return "Projected matchup values are shown until live scoring begins.";
}

function MatchupTeamSummary({
  team,
  accent,
  align,
  label,
  compactLabel,
  status,
}: {
  team: LeagueMatchupTeam | null;
  accent: "brand" | "pink";
  align: "left" | "right";
  label: string;
  compactLabel: string;
  status: string;
}) {
  const isBrand = accent === "brand";
  const pointsLabel = shouldShowMatchupScorePanels(status) ? "Points" : "Projected";

  return (
    <div className={`min-w-0 ${align === "right" ? "text-right" : "text-left"}`}>
      <div className={`flex items-center gap-2.5 ${align === "right" ? "justify-end" : "justify-start"}`}>
        <div
          aria-hidden="true"
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-sm font-black tracking-tight shadow-[0_0_24px_rgba(58,144,255,0.16)] sm:h-12 sm:w-12 sm:text-base ${
            isBrand
              ? "border-cfb-brand/80 bg-cfb-brand/10 text-cfb-brand"
              : "border-cfb-pink/80 bg-cfb-pink/10 text-cfb-pink"
          }`}
        >
          {teamInitials(team?.fantasy_team_name)}
        </div>
        <p className="hidden cfb-micro-label text-cfb-text-muted sm:block">{label}</p>
      </div>
      <p className="mt-2 truncate text-[9px] font-black uppercase tracking-[0.1em] text-cfb-text-muted sm:hidden">{compactLabel}</p>
      <p className="mt-1 truncate text-xs font-black text-cfb-text-primary sm:mt-2 sm:text-base">
        {team?.fantasy_team_name ?? "Team TBD"}
      </p>
      <p className="mt-0.5 text-[10px] font-bold text-cfb-text-muted sm:text-xs">{team?.record ?? "0-0-0"}</p>
      <p className={`mt-1 font-display text-2xl font-black tracking-[-0.06em] sm:mt-2 sm:text-4xl ${isBrand ? "text-cfb-brand" : "text-cfb-pink"}`}>
        {formatMatchupPoints(teamTotal(team))}
      </p>
      <p className={`mt-0.5 text-[9px] font-black uppercase tracking-[0.15em] ${isBrand ? "text-cfb-brand" : "text-cfb-pink"}`}>
        {pointsLabel}
      </p>
    </div>
  );
}

function CompactMatchupScoreboard({
  data,
  myTeam,
  opponentTeam,
  displayWeek,
  isViewingOwnMatchup,
}: {
  data: LeagueMatchupTabResponse;
  myTeam: LeagueMatchupTeam | null;
  opponentTeam: LeagueMatchupTeam | null;
  displayWeek: number;
  isViewingOwnMatchup: boolean;
}) {
  const winChance = displayedProbabilityPair(myTeam?.win_probability, opponentTeam?.win_probability);
  const myTeamIsLeading = Boolean(winChance && winChance.my >= winChance.opponent);
  const statusLabel = formatMatchupStatus(data.status);

  return (
    <section className="overflow-hidden rounded-xl border border-cfb-border-strong bg-cfb-surface-raised p-4 sm:p-6">
      <h2 className="sr-only">
        {myTeam?.fantasy_team_name ?? "Your team"} vs {opponentTeam?.fantasy_team_name ?? "Opponent"}
      </h2>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="cfb-micro-label text-cfb-text-secondary">Week {displayWeek} Matchup</p>
          <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-muted">
            {statusLabel === "Projected" ? "Preweek baseline" : `${statusLabel} scoring`}
          </p>
        </div>
        <span className="rounded-full border border-cfb-border-subtle bg-cfb-canvas/70 px-3 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-cfb-text-secondary">
          {statusLabel}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 sm:mt-6 sm:gap-6">
        <MatchupTeamSummary
          label={isViewingOwnMatchup ? "My Projection" : "Home Projection"}
          compactLabel={isViewingOwnMatchup ? "My proj" : "Home proj"}
          team={myTeam}
          accent="brand"
          align="left"
          status={data.status ?? "projected"}
        />

        <div className="flex min-w-[112px] flex-col items-center gap-2 text-center">
          <span className="text-[9px] font-black uppercase tracking-[0.13em] text-cfb-text-muted">Win chance</span>
          <div className="flex items-center gap-1.5 whitespace-nowrap text-[10px] font-black tabular-nums sm:text-xs">
            <span className={myTeamIsLeading ? "text-emerald-300" : "text-red-300"}>
              {winChance ? `${winChance.my.toFixed(1)}%` : "—"}
            </span>
            <span className="text-cfb-text-muted">VS</span>
            <span className={myTeamIsLeading ? "text-red-300" : "text-emerald-300"}>
              {winChance ? `${winChance.opponent.toFixed(1)}%` : "—"}
            </span>
          </div>
          <WinChanceBar
            myPercent={myTeam?.win_probability}
            opponentPercent={opponentTeam?.win_probability}
            className="h-2.5 w-full"
            testIdPrefix="compact-win-chance"
          />
        </div>

        <MatchupTeamSummary
          label={isViewingOwnMatchup ? "Their Projection" : "Away Projection"}
          compactLabel={isViewingOwnMatchup ? "Their proj" : "Away proj"}
          team={opponentTeam}
          accent="pink"
          align="right"
          status={data.status ?? "projected"}
        />
      </div>

      <div className="mt-5 flex items-center justify-between gap-3 border-t border-cfb-border-subtle pt-3 text-[10px] font-bold uppercase tracking-[0.12em] text-cfb-text-muted">
        <span>Week {displayWeek}</span>
        <span className="text-right">{winChance ? "Win chance from weekly lineup totals" : "Win chance unavailable"}</span>
      </div>

      <div className="mt-4 hidden grid-cols-[1fr_auto] items-center gap-4 border-t border-cfb-border-subtle pt-4 sm:grid">
        <WinChanceMeter
          myPercent={myTeam?.win_probability}
          opponentPercent={opponentTeam?.win_probability}
          myProjectedTotal={null}
          opponentProjectedTotal={null}
        />
        <div className="rounded-xl border border-cfb-border-subtle bg-cfb-canvas/70 px-4 py-3 text-right">
          <p className="cfb-micro-label text-cfb-text-muted">Projected Leader</p>
          <p className="mt-1 text-sm font-black text-cfb-text-primary">
            {leadingTeam(myTeam, opponentTeam)}
          </p>
        </div>
      </div>
    </section>
  );
}

export default function LeagueMatchup() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const [searchParams, setSearchParams] = useSearchParams();
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
  const isViewingOwnMatchup = Boolean(
    data?.my_team?.fantasy_team_id && data?.user_team?.fantasy_team_id === data.my_team.fantasy_team_id,
  );

  const updateSelection = (week: number, matchupId?: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("week", String(week));
    if (matchupId) next.set("matchup", String(matchupId));
    else next.delete("matchup");
    setSearchParams(next);
  };

  if (leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-6 py-8">
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
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-4 px-3 pb-24 pt-4 sm:gap-6 sm:px-6 sm:py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[380px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_10%,hsl(var(--brand-primary)/0.18),transparent_32%),radial-gradient(circle_at_76%_8%,hsl(var(--accent-pink)/0.12),transparent_34%)] blur-2xl" />

      <div className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="cfb-micro-label text-cfb-brand">League Matchup</p>
            <h1 className="cfb-display-title mt-1 text-3xl sm:mt-2 sm:text-5xl">Matchup</h1>
            <p className="mt-2 hidden max-w-2xl text-sm font-medium leading-6 text-cfb-text-secondary sm:block">
              Week {displayWeek} scoring view with honest projected, live, final, corrected,
              delayed, and unavailable states.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <WeekSelector
              week={data?.week}
              selectedWeek={selectedWeek}
              onChange={(week) => updateSelection(week)}
            />
          </div>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

      <MatchupRail
        matchups={scheduledMatchups}
        selectedMatchupId={activeMatchupId}
        isLoading={scoreboardQuery.isLoading}
        onSelect={(matchupId) => updateSelection(displayWeek, matchupId)}
      />

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
          <div className="space-y-4">
            <CompactMatchupScoreboard
              data={data}
              myTeam={myTeam}
              opponentTeam={opponentTeam}
              displayWeek={displayWeek}
              isViewingOwnMatchup={isViewingOwnMatchup}
            />

            <div className="flex flex-col gap-3 rounded-2xl border border-cfb-border-subtle bg-cfb-surface/65 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm font-medium leading-6 text-cfb-text-secondary">{freshnessText(data)}</p>
              <div className="flex shrink-0 items-center gap-2 text-xs font-black text-cfb-text-primary">
                <Clock className="h-4 w-4 text-cfb-gold" aria-hidden="true" />
                {leadingTeam(myTeam, opponentTeam)}
              </div>
            </div>

            {data?.message ? (
              <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4 text-sm font-medium text-cfb-text-secondary">
                {data.message}
              </div>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-cfb-gold" aria-hidden="true" />
            <p className="cfb-micro-label text-cfb-brand">Lineup Comparison</p>
          </div>
          <SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} leagueId={parsedLeagueId} />
        </>
      )}
    </main>
  );
}
