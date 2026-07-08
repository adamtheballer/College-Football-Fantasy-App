import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { WeekSelector } from "@/components/league/WeekSelector";
import { PageErrorState, PageLoadingState } from "@/components/PageState";
import { useLeagueRosterTab, useLeagueSettingsTab } from "@/hooks/use-leagues";
import {
  DEMO_LEAGUE_ID,
  createDemoLeagueRosterResponse,
  createWeekOnePreviewRoster,
} from "@/lib/leaguePreviewData";
import { isPreDraftLeague } from "@/lib/leagueState";

const starterSlot = (slot?: string | null) => {
  const normalized = (slot || "").toUpperCase();
  return normalized !== "BENCH" && normalized !== "IR";
};

const projectionValue = (player: { projected_points?: number | null; weekly_projected_fantasy_points?: number | null }) => {
  const value = player.projected_points ?? player.weekly_projected_fantasy_points;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};

export default function LeagueRoster() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const isPreDraft = !isDemoLeague && isPreDraftLeague(settingsQuery.data);
  const rosterQuery = useLeagueRosterTab(
    parsedLeagueId,
    selectedWeek ?? undefined,
    !isDemoLeague && !isPreDraft
  );
  const demoData = isDemoLeague ? createDemoLeagueRosterResponse() : null;
  const rosterData = demoData ?? rosterQuery.data;
  const fetchedRoster = rosterData?.roster ?? rosterData?.data ?? [];
  const previewTeamName = rosterData?.owned_team?.name ?? rosterData?.fantasy_team_name ?? "Your Team";
  const previewTeamId = rosterData?.owned_team?.id ?? rosterData?.fantasy_team_id ?? -100;
  const isPreviewRoster = !isDemoLeague && !rosterQuery.isLoading && fetchedRoster.length === 0;
  const roster = isPreviewRoster
    ? createWeekOnePreviewRoster(previewTeamId ?? -100, previewTeamName ?? "Your Team")
    : fetchedRoster;
  const starters = useMemo(
    () => roster.filter((player) => starterSlot(player.slot ?? player.roster_slot)),
    [roster]
  );
  const bench = useMemo(
    () => roster.filter((player) => (player.slot ?? player.roster_slot ?? "").toUpperCase() === "BENCH"),
    [roster]
  );
  const ir = useMemo(
    () => roster.filter((player) => (player.slot ?? player.roster_slot ?? "").toUpperCase() === "IR"),
    [roster]
  );
  const starterTotal = isPreviewRoster
    ? null
    : starters.reduce((total, player) => total + (projectionValue(player) ?? 0), 0);

  const benchTotal = isPreviewRoster
    ? null
    : bench.reduce((total, player) => total + (projectionValue(player) ?? 0), 0);

  if (settingsQuery.isLoading && !settingsQuery.isError && !isDemoLeague) {
    return <PageLoadingState title="Loading league state" description="Checking whether this league has completed the draft." />;
  }

  if (rosterQuery.isError && !isDemoLeague) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
        <PageErrorState
          title="Unable to load roster"
          description="Retry after confirming your session and league access are still valid."
          onAction={() => {
            void settingsQuery.refetch();
            void rosterQuery.refetch();
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
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] rounded-[3rem] bg-[radial-gradient(circle_at_18%_12%,rgba(56,189,248,0.2),transparent_34%),radial-gradient(circle_at_78%_8%,rgba(59,130,246,0.18),transparent_36%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Roster
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Roster</h1>
            <p className="mt-2 text-sm text-slate-400">
              League-scoped Week 1 roster for {previewTeamName ?? "your team"}.
            </p>
          </div>
          <WeekSelector
            week={rosterData?.week}
            selectedWeek={selectedWeek}
            onChange={setSelectedWeek}
          />
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      {isPreviewRoster ? (
        <section className="rounded-[1.25rem] border border-sky-300/25 bg-sky-400/[0.08] px-5 py-4 shadow-[0_0_36px_rgba(56,189,248,0.12)]">
          <p className="text-sm font-bold text-sky-100">
            Week 1 placeholder roster is shown until this league imports real draft results.
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[1.35rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(14,165,233,0.16),rgba(15,23,42,0.92))] p-5 shadow-[0_18px_60px_rgba(14,165,233,0.12)]">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            Starter Projection
          </p>
          <p className="mt-1 text-3xl font-black text-sky-100">
            {starterTotal === null ? "" : starterTotal.toFixed(1)}
          </p>
        </div>
        <div className="rounded-[1.35rem] border border-white/10 bg-[#0b1424]/90 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Bench Depth
          </p>
          <p className="mt-1 text-3xl font-black text-slate-100">
            {benchTotal === null ? "" : benchTotal.toFixed(1)}
          </p>
        </div>
        <div className="rounded-[1.35rem] border border-white/10 bg-[#0b1424]/90 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Week
          </p>
          <p className="mt-1 text-3xl font-black text-slate-100">{selectedWeek ?? rosterData?.week ?? 1}</p>
          {rosterData?.message ? (
            <p className="mt-2 text-xs font-semibold text-slate-400">{rosterData.message}</p>
          ) : null}
        </div>
      </section>

      <RosterSlotTable title="Starters" players={starters} emptyText="No starters set yet." leagueId={parsedLeagueId} />
      <RosterSlotTable title="Bench" players={bench} emptyText="Bench is empty." leagueId={parsedLeagueId} />
      <RosterSlotTable
        title={`IR (${rosterData?.ir_slots ?? 0})`}
        players={ir}
        emptyText="IR spot empty."
        leagueId={parsedLeagueId}
      />
    </main>
  );
}
