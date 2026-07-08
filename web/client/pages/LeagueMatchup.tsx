import { useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { PageErrorState, PageLoadingState } from "@/components/PageState";
import { SideBySideMatchup } from "@/components/league/SideBySideMatchup";
import { WeekSelector } from "@/components/league/WeekSelector";
import { WinChanceMeter } from "@/components/league/WinChanceMeter";
import { useLeagueMatchupTab, useLeagueSettingsTab } from "@/hooks/use-leagues";
import {
  DEMO_LEAGUE_ID,
  createDemoLeagueMatchupResponse,
} from "@/lib/leaguePreviewData";
import { isPreDraftLeague } from "@/lib/leagueState";

function MatchupEmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <section className="rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] p-8 text-center shadow-[0_24px_90px_rgba(14,165,233,0.12)]">
      <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
        {title}
      </p>
      <p className="mx-auto mt-3 max-w-2xl text-sm font-semibold leading-6 text-slate-400">
        {detail}
      </p>
    </section>
  );
}

function formatMatchupStatus(status: string | null | undefined) {
  const normalized = (status || "projected").toLowerCase();
  if (normalized === "live") return "Live";
  if (normalized === "final") return "Final";
  if (normalized === "stat_corrected") return "Corrected";
  if (normalized === "final_pending_review") return "Final Pending Review";
  return "Projected";
}

function trustStateFor({
  status,
  dataUpdatedAt,
  isFetching,
  isError,
}: {
  status: string | null | undefined;
  dataUpdatedAt: number;
  isFetching: boolean;
  isError: boolean;
}) {
  if (isError) {
    return {
      label: "Stats unavailable",
      detail: "The scoring service could not refresh this matchup. Existing scores are preserved.",
      className: "border-red-300/30 bg-red-500/10 text-red-100",
    };
  }
  const normalized = (status || "projected").toLowerCase();
  const ageMs = dataUpdatedAt ? Date.now() - dataUpdatedAt : 0;
  if (normalized === "live" && ageMs > 120_000) {
    return {
      label: "Stats delayed",
      detail: "Live scoring has not refreshed in over two minutes.",
      className: "border-amber-300/30 bg-amber-400/10 text-amber-100",
    };
  }
  if (normalized === "stat_corrected") {
    return {
      label: "Corrected",
      detail: "Official stat corrections have been applied to this matchup.",
      className: "border-violet-300/30 bg-violet-400/10 text-violet-100",
    };
  }
  if (normalized === "final") {
    return {
      label: "Final",
      detail: "This matchup is final and no longer live-polling.",
      className: "border-emerald-300/30 bg-emerald-400/10 text-emerald-100",
    };
  }
  if (normalized === "live") {
    return {
      label: isFetching ? "Refreshing live stats" : "Live scoring",
      detail: "Scores refresh automatically while this matchup is live.",
      className: "border-sky-300/30 bg-sky-400/10 text-sky-100",
    };
  }
  return {
    label: "Projected",
    detail: "Projected totals use this league’s scoring settings until live stats arrive.",
    className: "border-slate-300/20 bg-slate-400/10 text-slate-200",
  };
}

function formatLastUpdated(dataUpdatedAt: number) {
  if (!dataUpdatedAt) return "Not refreshed yet";
  const seconds = Math.max(0, Math.round((Date.now() - dataUpdatedAt) / 1000));
  if (seconds < 60) return `Updated ${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  return `Updated ${minutes}m ago`;
}

export default function LeagueMatchup() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const isPreDraft = !isDemoLeague && isPreDraftLeague(settingsQuery.data);
  const matchupQuery = useLeagueMatchupTab(
    parsedLeagueId,
    selectedWeek ?? undefined,
    !isDemoLeague && !isPreDraft
  );
  const data = isDemoLeague ? createDemoLeagueMatchupResponse() : matchupQuery.data;
  const myTeam = data?.my_team ?? data?.user_team ?? null;
  const opponentTeam = data?.opponent_team ?? null;
  const displayWeek = selectedWeek ?? data?.week ?? 1;
  const hasScheduledMatchup = Boolean(data?.matchup_id && myTeam && opponentTeam);
  const matchupStatusLabel = formatMatchupStatus(data?.status);
  const trustState = trustStateFor({
    status: data?.status,
    dataUpdatedAt: matchupQuery.dataUpdatedAt,
    isFetching: matchupQuery.isFetching,
    isError: matchupQuery.isError,
  });

  if (settingsQuery.isLoading && !settingsQuery.isError && !isDemoLeague) {
    return <PageLoadingState title="Loading league state" description="Checking whether this league has a scheduled matchup." />;
  }

  if (matchupQuery.isError && !isDemoLeague) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
        <PageErrorState
          title="Unable to load matchup"
          description="Retry after confirming the backend is reachable and your league access is still valid."
          onAction={() => {
            void settingsQuery.refetch();
            void matchupQuery.refetch();
          }}
        />
      </main>
    );
  }

  if (isPreDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/waivers`} replace />;
  }

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[460px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_10%,rgba(125,211,252,0.2),transparent_32%),radial-gradient(circle_at_70%_4%,rgba(37,99,235,0.2),transparent_38%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Matchup
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Matchup</h1>
            <p className="mt-2 text-sm text-slate-400">
              League-scoring projections show before kickoff. Live/final scoring appears as provider stats arrive.
            </p>
          </div>
          <WeekSelector
            week={data?.week}
            selectedWeek={selectedWeek}
            onChange={setSelectedWeek}
          />
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      {matchupQuery.isLoading && !isDemoLeague ? (
        <MatchupEmptyState
          title="Loading matchup"
          detail="Checking whether this league has a scheduled matchup for the selected week."
        />
      ) : !hasScheduledMatchup ? (
        <MatchupEmptyState
          title="No matchup scheduled"
          detail={
            data?.message ??
            "No real matchup exists for this league and week yet. Once the schedule is generated, the opponent, win chance, and side-by-side lineup will appear here."
          }
        />
      ) : (
        <>
          <section className="rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] p-6 shadow-[0_24px_90px_rgba(14,165,233,0.12)]">
            <div className="grid gap-5 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
                  Your Team
                </p>
                <p className="mt-2 text-3xl font-black italic text-slate-50">
                  {myTeam.fantasy_team_name}
                </p>
                <p className="text-sm font-bold text-slate-400">{myTeam.record}</p>
              </div>
              <div className="rounded-[1.5rem] border border-sky-300/25 bg-sky-400/10 px-8 py-5 text-center shadow-[0_0_40px_rgba(56,189,248,0.14)]">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-200">
                  Week {displayWeek} • {matchupStatusLabel}
                </p>
                <p className="mt-1 text-2xl font-black text-slate-50">
                  {(myTeam.projected_total ?? 0).toFixed(1)} - {(opponentTeam.projected_total ?? 0).toFixed(1)}
                </p>
              </div>
              <div className="text-left lg:text-right">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
                  Opponent
                </p>
                <p className="mt-2 text-3xl font-black italic text-slate-50">
                  {opponentTeam.fantasy_team_name}
                </p>
                <p className="text-sm font-bold text-slate-400">{opponentTeam.record}</p>
              </div>
            </div>
            <div className="mt-6">
              <WinChanceMeter
                myPercent={myTeam.win_probability}
                opponentPercent={opponentTeam.win_probability}
              />
            </div>
            <div className={`mt-5 rounded-2xl border px-4 py-3 ${trustState.className}`}>
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-[10px] font-black uppercase tracking-[0.22em]">{trustState.label}</p>
                <p className="text-[10px] font-black uppercase tracking-[0.18em] opacity-75">
                  {formatLastUpdated(matchupQuery.dataUpdatedAt)}
                </p>
              </div>
              <p className="mt-1 text-xs font-semibold opacity-80">{trustState.detail}</p>
            </div>
            {data?.message ? <p className="mt-4 text-sm text-slate-400">{data.message}</p> : null}
          </section>

          <SideBySideMatchup myTeam={myTeam} opponentTeam={opponentTeam} leagueId={parsedLeagueId} />
        </>
      )}
    </main>
  );
}
