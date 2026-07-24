import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { WeekSelector } from "@/components/league/WeekSelector";
import { ErrorState } from "@/components/states/ErrorState";
import { useLeagueDetail, useLeagueRosterTab } from "@/hooks/use-leagues";
import { ApiError } from "@/lib/api";
import {
  DEMO_LEAGUE_ID,
  createDemoLeagueRosterResponse,
} from "@/lib/leaguePreviewData";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { LeagueRosterPlayer } from "@/types/league";

const starterSlot = (slot?: string | null) => {
  const normalized = (slot || "").toUpperCase();
  return normalized !== "BENCH" && normalized !== "IR";
};

const isRealRosterPlayer = (player: LeagueRosterPlayer) =>
  Boolean(
    player.player_id !== null &&
      player.player_id !== undefined &&
      !player.is_placeholder &&
      !/\bpreview\b/i.test(player.player_name ?? ""),
  );

export const formatRosterLoadError = (error: unknown, fallback: string) => {
  if (error instanceof ApiError && error.message) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
};

export const formatLineupLockMessage = (player: LeagueRosterPlayer) => {
  if (!player.is_locked) return null;
  if (!player.game_start_at) return "Locked at kickoff";
  const gameStart = new Date(player.game_start_at);
  if (Number.isNaN(gameStart.getTime())) return "Locked at kickoff";
  return `Locked at kickoff (${gameStart.toLocaleString()})`;
};

export default function LeagueRoster() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const leagueQuery = useLeagueDetail(parsedLeagueId, !isDemoLeague);
  const postDraft = isDemoLeague || isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });
  const rosterQuery = useLeagueRosterTab(parsedLeagueId, selectedWeek ?? undefined, !isDemoLeague && postDraft);
  const demoData = isDemoLeague ? createDemoLeagueRosterResponse() : null;
  const rosterData = demoData ?? rosterQuery.data;
  const fetchedRoster = rosterData?.slots ?? rosterData?.roster ?? rosterData?.data ?? [];
  const previewTeamName = rosterData?.owned_team?.name ?? rosterData?.fantasy_team_name ?? "Your Team";
  const previewTeamId = rosterData?.owned_team?.id ?? rosterData?.fantasy_team_id ?? -100;
  const realRoster = useMemo(() => fetchedRoster.filter(isRealRosterPlayer), [fetchedRoster]);
  const hasRosterSlots = fetchedRoster.length > 0;
  const isEmptyRoster = !isDemoLeague && !rosterQuery.isLoading && !rosterQuery.isError && !hasRosterSlots;
  const roster = fetchedRoster;
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
  const starterTotal = hasRosterSlots
    ? starters.reduce(
        (total, player) => total + Number(player.projected_points ?? player.weekly_projected_fantasy_points ?? 0),
        0
      )
    : null;
  const ownedRosterActions = !isDemoLeague && typeof previewTeamId === "number" && previewTeamId > 0
    ? {
        teamId: previewTeamId,
        roster: realRoster,
        superflexEnabled: Number(rosterData?.roster_slot_limits?.SUPERFLEX ?? 0) > 0,
      }
    : undefined;

  const benchTotal = hasRosterSlots
    ? bench.reduce(
        (total, player) => total + Number(player.projected_points ?? player.weekly_projected_fantasy_points ?? 0),
        0
      )
    : null;

  if (!isDemoLeague && leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (!isDemoLeague && leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-6 py-8">
        <ErrorState
          title="Unable to load league"
          message={formatRosterLoadError(leagueQuery.error, "The league could not be loaded. Please try again.")}
          retryLabel="Retry"
          onRetry={() => void leagueQuery.refetch()}
        />
      </main>
    );
  }

  if (!postDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/lobby`} replace />;
  }

  if (!isDemoLeague && rosterQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-6 py-8">
        <ErrorState
          title="Unable to load roster"
          message={formatRosterLoadError(rosterQuery.error, "The roster could not be loaded. Please try again.")}
          retryLabel="Retry"
          onRetry={() => void rosterQuery.refetch()}
        />
      </main>
    );
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
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

      {isEmptyRoster ? (
        <section className="cfb-playbook-pattern rounded-[1.25rem] border border-cfb-brand/30 bg-cfb-brand/[0.09] px-5 py-4 shadow-[0_0_36px_hsl(var(--brand-primary)/0.12)]">
          <p className="relative text-sm font-bold text-blue-50">
            No players on this roster yet. Complete the draft to populate your roster.
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[1.35rem] border border-cfb-brand/30 bg-[linear-gradient(135deg,hsl(var(--brand-primary)/0.16),hsl(var(--background-surface-raised)/0.94))] p-5 shadow-[0_18px_60px_hsl(var(--brand-primary)/0.12)]">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            Starter Projection
          </p>
          <p className="mt-1 text-3xl font-black text-sky-100">{starterTotal === null ? "N/A" : starterTotal.toFixed(1)}</p>
        </div>
        <div className="rounded-[1.35rem] border border-cfb-border-subtle bg-cfb-surface-raised/90 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Bench Depth
          </p>
          <p className="mt-1 text-3xl font-black text-slate-100">{benchTotal === null ? "N/A" : benchTotal.toFixed(1)}</p>
        </div>
        <div className="rounded-[1.35rem] border border-cfb-border-subtle bg-cfb-surface-raised/90 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Week
          </p>
          <p className="mt-1 text-3xl font-black text-slate-100">{selectedWeek ?? rosterData?.week ?? 1}</p>
          {rosterData?.message ? (
            <p className="mt-2 text-xs font-semibold text-slate-400">{rosterData.message}</p>
          ) : null}
        </div>
      </section>

      <RosterSlotTable title="Starters" players={starters} emptyText="No starters set yet." leagueId={parsedLeagueId} ownedRosterActions={ownedRosterActions} />
      <RosterSlotTable title="Bench" players={bench} emptyText="Bench is empty." leagueId={parsedLeagueId} ownedRosterActions={ownedRosterActions} />
      <RosterSlotTable
        title={`IR (${rosterData?.ir_slots ?? 0})`}
        players={ir}
        emptyText="IR spot empty."
        leagueId={parsedLeagueId}
        ownedRosterActions={ownedRosterActions}
      />
    </main>
  );
}
