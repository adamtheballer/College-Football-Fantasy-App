import { Clock, ShieldAlert, Swords, Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { SideBySideMatchup } from "@/components/league/SideBySideMatchup";
import { WeekSelector } from "@/components/league/WeekSelector";
import { WinChanceBar, WinChanceMeter } from "@/components/league/WinChanceMeter";
import { EmptyState, ErrorState, SkeletonState } from "@/components/states";
import { SurfaceCard, type StatusBadgeVariant } from "@/components/fantasy";
import { useLeagueDetail, useLeagueMatchupTab, useLeagueScoreboard, useMatchupRivalry } from "@/hooks/use-leagues";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { LeagueMatchupTabResponse, LeagueMatchupTeam } from "@/types/league";

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

function freshnessText(data: LeagueMatchupTabResponse | undefined) {
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
    <section className="relative overflow-hidden rounded-[1.65rem] border border-cfb-border-strong bg-[linear-gradient(135deg,hsl(var(--background-surface-raised)/0.98),hsl(var(--background-surface)/0.94))] p-4 shadow-[0_22px_60px_rgba(2,6,23,0.34)] sm:p-6">
      <h2 className="sr-only">
        {myTeam?.fantasy_team_name ?? "Your team"} vs {opponentTeam?.fantasy_team_name ?? "Opponent"}
      </h2>
      <div className="pointer-events-none absolute inset-x-[22%] top-0 h-px bg-gradient-to-r from-transparent via-cfb-brand/60 to-transparent" />
      <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-cfb-pink/10 blur-3xl" />
      <div className="pointer-events-none absolute -left-16 bottom-0 h-40 w-40 rounded-full bg-cfb-brand/10 blur-3xl" />

      <div className="relative flex items-center justify-between gap-3">
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

      <div className="relative mt-5 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 sm:mt-6 sm:gap-6">
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

      <div className="relative mt-5 flex items-center justify-between gap-3 border-t border-cfb-border-subtle pt-3 text-[10px] font-bold uppercase tracking-[0.12em] text-cfb-text-muted">
        <span>Week {displayWeek}</span>
        <span className="text-right">{winChance ? "Win chance from weekly lineup totals" : "Win chance unavailable"}</span>
      </div>

      <div className="relative mt-4 hidden grid-cols-[1fr_auto] items-center gap-4 border-t border-cfb-border-subtle pt-4 sm:grid">
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
  const selectedMatchupValue = selectedMatchupId ?? data?.matchup_id ?? "";
  const isViewingOwnMatchup = Boolean(
    data?.my_team?.fantasy_team_id && data?.user_team?.fantasy_team_id === data.my_team.fantasy_team_id,
  );
  const rivalryQuery = useMatchupRivalry(parsedLeagueId, data?.matchup_id, postDraft && Boolean(data?.matchup_id));
  const [showRivalryReveal, setShowRivalryReveal] = useState(false);

  useEffect(() => {
    const rivalry = rivalryQuery.data;
    if (!rivalry?.is_rivalry_matchup || !data?.matchup_id) {
      setShowRivalryReveal(false);
      return;
    }
    const storageKey = `cff-rivalry-reveal:${parsedLeagueId}:${data.matchup_id}`;
    try {
      if (!window.localStorage.getItem(storageKey)) {
        window.localStorage.setItem(storageKey, "seen");
        setShowRivalryReveal(true);
      }
    } catch {
      // Privacy-restricted browsers can still use the matchup without persistence.
      setShowRivalryReveal(true);
    }
  }, [data?.matchup_id, parsedLeagueId, rivalryQuery.data]);

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
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-4 px-3 pb-24 pt-3 sm:gap-6 sm:px-2 sm:py-2">
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
            <label className="flex min-w-[260px] flex-col gap-2 text-left">
              <span className="cfb-micro-label text-cfb-text-muted">League matchup</span>
              <select
                aria-label="League matchup"
                className="h-11 rounded-xl border border-cfb-border-subtle bg-cfb-surface px-3 text-sm font-bold text-cfb-text-primary outline-none transition focus:border-cfb-brand focus:ring-2 focus:ring-cfb-brand/20"
                value={selectedMatchupValue}
                disabled={scoreboardQuery.isLoading || scoreboardQuery.isError || !scheduledMatchups.length}
                onChange={(event) => updateSelection(displayWeek, Number(event.target.value))}
              >
                {scheduledMatchups.map((matchup) => (
                  <option key={matchup.matchup_id} value={matchup.matchup_id}>
                    {matchup.home_team_name} vs {matchup.away_team_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

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
          {showRivalryReveal && rivalryQuery.data?.is_rivalry_matchup ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="rivalry-reveal-title">
              <section className="relative w-full max-w-md overflow-hidden rounded-3xl border border-cfb-gold/45 bg-[radial-gradient(circle_at_20%_0%,rgba(234,179,8,0.2),transparent_38%),linear-gradient(145deg,#172554,#0f172a_72%)] p-7 text-center shadow-[0_30px_100px_rgba(0,0,0,0.55)]">
                <div className="pointer-events-none absolute inset-x-12 top-0 h-px bg-gradient-to-r from-transparent via-cfb-gold to-transparent" />
                <Swords className="mx-auto h-10 w-10 text-cfb-gold" aria-hidden="true" />
                <p className="mt-4 cfb-micro-label text-cfb-gold">{rivalryQuery.data.is_championship ? "CFB Fantasy Bowl" : "Rivalry Week"}</p>
                <h2 id="rivalry-reveal-title" className="mt-2 text-3xl font-black text-cfb-text-primary">{rivalryQuery.data.user_team_name} vs {rivalryQuery.data.rival_team_name}</h2>
                <p className="mt-3 text-sm leading-6 text-cfb-text-secondary">Series record: {rivalryQuery.data.series.wins}-{rivalryQuery.data.series.losses}{rivalryQuery.data.series.ties ? `-${rivalryQuery.data.series.ties}` : ""}. Rivalry status is for bragging rights only and never changes scoring or standings.</p>
                <button type="button" onClick={() => setShowRivalryReveal(false)} className="mt-6 inline-flex min-h-11 items-center justify-center rounded-xl bg-cfb-gold px-5 text-xs font-black uppercase tracking-[0.14em] text-slate-950 transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-cfb-gold focus:ring-offset-2 focus:ring-offset-slate-950">View matchup</button>
              </section>
            </div>
          ) : null}
          <div className="space-y-4">
            {rivalryQuery.data?.is_rivalry_matchup ? (
              <section className="flex flex-col gap-3 rounded-2xl border border-cfb-gold/35 bg-[linear-gradient(120deg,rgba(79,57,14,0.38),rgba(15,29,48,0.92)_58%,rgba(11,53,58,0.42))] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cfb-gold/35 bg-cfb-gold/10 text-cfb-gold"><Swords className="h-5 w-5" aria-hidden="true" /></div>
                  <div>
                    <p className="cfb-micro-label text-cfb-gold">{rivalryQuery.data.is_championship ? "CFB Fantasy Bowl · Championship" : "Rivalry Week"}</p>
                    <p className="mt-1 text-sm font-black text-cfb-text-primary">{rivalryQuery.data.user_team_name} vs {rivalryQuery.data.rival_team_name}</p>
                  </div>
                </div>
                <p className="text-xs font-bold text-cfb-text-secondary">Series {rivalryQuery.data.series.wins}-{rivalryQuery.data.series.losses}{rivalryQuery.data.series.ties ? `-${rivalryQuery.data.series.ties}` : ""}{rivalryQuery.data.last_meeting ? ` · Last ${rivalryQuery.data.last_meeting.result} ${rivalryQuery.data.last_meeting.own_score.toFixed(1)}-${rivalryQuery.data.last_meeting.rival_score.toFixed(1)}` : ""}</p>
              </section>
            ) : null}
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
