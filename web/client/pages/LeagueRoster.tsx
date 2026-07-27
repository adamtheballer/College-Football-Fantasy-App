import { useEffect, useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { WeekSelector } from "@/components/league/WeekSelector";
import { ErrorState } from "@/components/states/ErrorState";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useLeagueDetail, useLeagueRosterTab } from "@/hooks/use-leagues";
import { ApiError } from "@/lib/api";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { LeagueRosterPlayer, LeagueRosterTabResponse, LeagueRosterTeam } from "@/types/league";

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

export const getLeagueRosterTeams = (rosterData?: LeagueRosterTabResponse): LeagueRosterTeam[] => {
  if (rosterData?.team_rosters?.length) return rosterData.team_rosters;

  const ownedTeamId = rosterData?.owned_team?.id ?? rosterData?.fantasy_team_id ?? null;
  if (!rosterData?.owned_team && !ownedTeamId) return [];

  return [
    {
      team: {
          id: ownedTeamId ?? -100,
          name: rosterData?.owned_team?.name ?? rosterData?.fantasy_team_name ?? "Your Team",
          owner_user_id: rosterData?.owned_team?.owner_user_id ?? null,
          record: null,
      },
      roster: rosterData?.slots ?? rosterData?.roster ?? rosterData?.data ?? [],
    },
  ];
};

export default function LeagueRoster() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const postDraft = isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });
  const rosterQuery = useLeagueRosterTab(parsedLeagueId, selectedWeek ?? undefined, postDraft);
  const rosterData = rosterQuery.data;
  const ownedTeamId = rosterData?.owned_team?.id ?? rosterData?.fantasy_team_id ?? null;
  const ownedRoster = rosterData?.slots ?? rosterData?.roster ?? rosterData?.data ?? [];
  const teamRosters = useMemo(() => getLeagueRosterTeams(rosterData), [rosterData]);
  useEffect(() => {
    const defaultTeamId = ownedTeamId ?? teamRosters[0]?.team.id ?? null;
    if (selectedTeamId === null || !teamRosters.some((teamRoster) => teamRoster.team.id === selectedTeamId)) {
      setSelectedTeamId(defaultTeamId);
    }
  }, [ownedTeamId, selectedTeamId, teamRosters]);
  const selectedTeamRoster = teamRosters.find((teamRoster) => teamRoster.team.id === selectedTeamId) ?? teamRosters[0];
  const fetchedRoster = selectedTeamRoster?.roster ?? ownedRoster;
  const previewTeamName = selectedTeamRoster?.team.name ?? rosterData?.owned_team?.name ?? rosterData?.fantasy_team_name ?? "Your Team";
  const previewTeamId = selectedTeamRoster?.team.id ?? ownedTeamId ?? -100;
  const viewingOwnedTeam = Boolean(ownedTeamId && previewTeamId === ownedTeamId);
  const realRoster = useMemo(() => fetchedRoster.filter(isRealRosterPlayer), [fetchedRoster]);
  const hasRosterSlots = fetchedRoster.length > 0;
  const isEmptyRoster = !rosterQuery.isLoading && !rosterQuery.isError && !hasRosterSlots;
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
  const ownedRosterActions = viewingOwnedTeam && typeof previewTeamId === "number" && previewTeamId > 0
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

  if (rosterQuery.isError) {
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
              Manage your lineup or inspect every league team&apos;s current roster.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            {teamRosters.length > 1 ? (
              <div className="min-w-[240px]">
                <p className="mb-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">View team roster</p>
                <Select value={selectedTeamId === null ? undefined : String(selectedTeamId)} onValueChange={(value) => setSelectedTeamId(Number(value))}>
                  <SelectTrigger className="h-11 rounded-xl border-sky-300/25 bg-slate-950/45 text-sm font-black text-slate-100">
                    <SelectValue placeholder="Choose a team" />
                  </SelectTrigger>
                  <SelectContent className="border-sky-300/20 bg-slate-950 text-slate-100">
                    {teamRosters.map((teamRoster) => (
                      <SelectItem key={teamRoster.team.id} value={String(teamRoster.team.id)}>
                        {teamRoster.team.name}{teamRoster.team.id === ownedTeamId ? " (You)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
            <WeekSelector
              week={rosterData?.week}
              selectedWeek={selectedWeek}
              onChange={setSelectedWeek}
            />
          </div>
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

      <section className="rounded-[1.25rem] border border-sky-300/20 bg-sky-300/[0.055] px-5 py-4">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-sky-300">
          {viewingOwnedTeam ? "Managing your roster" : "Viewing league roster"}
        </p>
        <p className="mt-1 text-sm font-bold text-slate-200">
          {previewTeamName}{selectedTeamRoster?.team.record ? ` · ${selectedTeamRoster.team.record}` : ""}
          {!viewingOwnedTeam ? " · Read-only" : ""}
        </p>
      </section>

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
