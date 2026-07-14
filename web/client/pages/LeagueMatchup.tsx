import { useState } from "react";
import { Clock, Radio, ShieldAlert, Trophy } from "lucide-react";
import { useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { SideBySideMatchup } from "@/components/league/SideBySideMatchup";
import { WeekSelector } from "@/components/league/WeekSelector";
import { WinChanceMeter } from "@/components/league/WinChanceMeter";
import { EmptyState, ErrorState, SkeletonState } from "@/components/states";
import { StatCard, StatusBadge, SurfaceCard, type StatusBadgeVariant } from "@/components/fantasy";
import { useLeagueMatchupTab } from "@/hooks/use-leagues";
import {
  DEMO_LEAGUE_ID,
  createDemoLeagueMatchupResponse,
} from "@/lib/leaguePreviewData";
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
  const myTotal = teamTotal(myTeam);
  const opponentTotal = teamTotal(opponentTeam);
  if (typeof myTotal !== "number" || typeof opponentTotal !== "number") return "Even";
  if (myTotal === opponentTotal) return "Even";
  return myTotal > opponentTotal
    ? myTeam?.fantasy_team_name ?? "Your Team"
    : opponentTeam?.fantasy_team_name ?? "Opponent";
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

function TeamScorePanel({
  label,
  team,
  accent,
}: {
  label: string;
  team: LeagueMatchupTeam | null;
  accent: "brand" | "pink";
}) {
  return (
    <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/75 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="cfb-micro-label text-cfb-text-muted">{label}</p>
          <h2 className="mt-2 truncate text-2xl font-black text-cfb-text-primary">
            {team?.fantasy_team_name ?? "Team TBD"}
          </h2>
          <p className="mt-1 text-sm font-bold text-cfb-text-secondary">
            {team?.record ?? "0-0-0"}
          </p>
        </div>
        <div className={`h-3 w-3 rounded-full ${accent === "brand" ? "bg-cfb-brand" : "bg-cfb-pink"}`} />
      </div>
      <p
        className={`mt-6 font-display text-6xl font-black tracking-[-0.07em] ${
          accent === "brand" ? "text-cfb-brand" : "text-cfb-pink"
        }`}
      >
        {formatMatchupPoints(teamTotal(team))}
      </p>
      <p className="mt-2 text-[11px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">
        Fantasy points
      </p>
    </div>
  );
}

export default function LeagueMatchup() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const matchupQuery = useLeagueMatchupTab(parsedLeagueId, selectedWeek ?? undefined, !isDemoLeague);
  const data = isDemoLeague ? createDemoLeagueMatchupResponse() : matchupQuery.data;
  const myTeam = data?.my_team ?? data?.user_team ?? null;
  const opponentTeam = data?.opponent_team ?? null;
  const displayWeek = selectedWeek ?? data?.week ?? 1;
  const hasScheduledMatchup = Boolean(data?.matchup_id && myTeam && opponentTeam);
  const statusLabel = formatMatchupStatus(data?.status);
  const statusVariant = matchupStatusVariant(data?.status);
  const shouldShowScorePanels = shouldShowMatchupScorePanels(data?.status);

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-0 py-2 sm:px-2">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[380px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_10%,hsl(var(--brand-primary)/0.18),transparent_32%),radial-gradient(circle_at_76%_8%,hsl(var(--accent-pink)/0.12),transparent_34%)] blur-2xl" />

      <div className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="cfb-micro-label text-cfb-brand">League Matchup</p>
            <h1 className="cfb-display-title mt-2 text-4xl sm:text-5xl">Matchup</h1>
            <p className="mt-2 max-w-2xl text-sm font-medium leading-6 text-cfb-text-secondary">
              Week {displayWeek} scoring view with honest projected, live, final, corrected,
              delayed, and unavailable states.
            </p>
          </div>
          <WeekSelector week={data?.week} selectedWeek={selectedWeek} onChange={setSelectedWeek} />
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      {matchupQuery.isError && !isDemoLeague ? (
        <ErrorState
          title="Unable to load matchup"
          message="The matchup API did not return a usable response for this league and week."
          retryLabel="Try Again"
          onRetry={() => void matchupQuery.refetch()}
        />
      ) : matchupQuery.isLoading && !isDemoLeague ? (
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
          <SurfaceCard variant="scoreboard" padding="spacious" className="space-y-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge variant={statusVariant}>{statusLabel}</StatusBadge>
                  <span className="inline-flex items-center gap-2 rounded-full border border-cfb-border-subtle bg-cfb-surface/70 px-3 py-1 text-[11px] font-black uppercase tracking-[0.14em] text-cfb-text-secondary">
                    <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                    Week {displayWeek}
                  </span>
                </div>
                <h2 className="mt-4 text-2xl font-black text-cfb-text-primary sm:text-3xl">
                  {myTeam?.fantasy_team_name} vs {opponentTeam?.fantasy_team_name}
                </h2>
                <p className="mt-2 max-w-3xl text-sm font-medium leading-6 text-cfb-text-secondary">
                  {freshnessText(data)}
                </p>
              </div>
              <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/70 px-5 py-4 text-left lg:text-right">
                <p className="cfb-micro-label text-cfb-text-muted">Projected Leader</p>
                <p className="mt-2 text-lg font-black text-cfb-text-primary">
                  {leadingTeam(myTeam, opponentTeam)}
                </p>
              </div>
            </div>

            {shouldShowScorePanels ? (
              <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-stretch">
                <TeamScorePanel label="Your Team" team={myTeam} accent="brand" />
                <div className="flex items-center justify-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full border border-cfb-border-strong bg-cfb-surface font-black text-cfb-text-primary">
                    VS
                  </div>
                </div>
                <TeamScorePanel label="Opponent" team={opponentTeam} accent="pink" />
              </div>
            ) : null}

            <WinChanceMeter
              myPercent={myTeam?.win_probability}
              opponentPercent={opponentTeam?.win_probability}
              myProjectedTotal={shouldShowScorePanels ? null : teamTotal(myTeam)}
              opponentProjectedTotal={shouldShowScorePanels ? null : teamTotal(opponentTeam)}
            />

            {data?.message ? (
              <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4 text-sm font-medium text-cfb-text-secondary">
                {data.message}
              </div>
            ) : null}
          </SurfaceCard>

          <section className="grid gap-4 md:grid-cols-3">
            <StatCard
              label="Status"
              value={statusLabel}
              helper="Scoring state"
              tone={statusVariant === "live" ? "success" : statusVariant === "delayed" ? "gold" : "brand"}
            />
            <StatCard
              label="Win Chance"
              value={`${formatMatchupPoints(myTeam?.win_probability)}%`}
              helper={myTeam?.fantasy_team_name ?? "Your Team"}
              tone="success"
            />
            <StatCard
              label="Projection Gap"
              value={formatMatchupPoints((teamTotal(myTeam) ?? 0) - (teamTotal(opponentTeam) ?? 0))}
              helper="Your projected margin"
              tone={(teamTotal(myTeam) ?? 0) >= (teamTotal(opponentTeam) ?? 0) ? "brand" : "danger"}
            />
          </section>

          <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-surface/70 px-5 py-4 text-sm font-bold text-cfb-text-secondary">
            <Radio className="mr-2 inline h-4 w-4 text-cfb-brand" aria-hidden="true" />
            Live values refresh automatically only when the backend marks this matchup as live.
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
