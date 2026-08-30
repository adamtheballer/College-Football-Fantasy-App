import { useEffect, useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { WeekSelector } from "@/components/league/WeekSelector";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { ErrorState } from "@/components/states/ErrorState";
import { useLeagueDetail, useLeagueRosterTab } from "@/hooks/use-leagues";
import { ApiError } from "@/lib/api";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import { isNumericProjection } from "@/lib/projection-display";
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

const currentRosterPointValue = (player: LeagueRosterPlayer) => {
  const state = (player.live_game_state ?? "").toLowerCase();
  if (["live", "final", "post"].includes(state) || typeof player.live_points === "number") {
    return player.live_points ?? 0;
  }
  const projection = player.projected_points ?? player.weekly_projected_fantasy_points;
  return isNumericProjection(projection, player.projection_status) ? projection : 0;
};

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

export function TeamRosterRail({
  teams,
  selectedTeamId,
  ownedTeamId,
  onSelect,
}: {
  teams: LeagueRosterTeam[];
  selectedTeamId: number | null;
  ownedTeamId: number | null;
  onSelect: (teamId: number) => void;
}) {
  if (teams.length < 2) return null;

  return (
    <section
      aria-label="League rosters"
      className="overflow-hidden rounded-[1.25rem] border border-cfb-border-subtle bg-cfb-surface/70"
    >
      <div
        aria-label="Swipe through league rosters"
        className="flex snap-x snap-mandatory gap-2 overflow-x-auto px-3 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:px-4"
      >
        {teams.map((teamRoster) => {
          const { team } = teamRoster;
          const selected = team.id === selectedTeamId;
          const isOwned = team.id === ownedTeamId;
          return (
            <button
              key={team.id}
              type="button"
              aria-label={`View ${team.name} roster`}
              aria-pressed={selected}
              onClick={() => onSelect(team.id)}
              className={`snap-start shrink-0 rounded-xl border px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 ${
                selected
                  ? "border-cfb-brand/80 bg-cfb-brand/[0.12] text-cfb-text-primary"
                  : "border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-secondary hover:border-cfb-border-strong hover:bg-cfb-surface-hover"
              }`}
            >
              <div className="flex min-w-[172px] items-center gap-2.5">
                <ManagerAvatar
                  avatarUrl={team.owner_avatar_url}
                  managerName={team.owner_name ?? team.name}
                  size="sm"
                  className="border-cfb-brand/45 bg-cfb-brand/[0.08] text-cfb-brand"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] font-black leading-4">{team.name}</span>
                  <span className="mt-0.5 block truncate text-[9px] font-bold text-cfb-text-muted">
                    {isOwned ? "Your roster" : team.record || "League roster"}
                  </span>
                </span>
                {isOwned ? <span className="text-[8px] font-black uppercase tracking-[0.12em] text-cfb-brand">You</span> : null}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default function LeagueRoster() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [quickSwapPlayer, setQuickSwapPlayer] = useState<LeagueRosterPlayer | null>(null);
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
  useEffect(() => {
    setQuickSwapPlayer(null);
  }, [selectedTeamId, selectedWeek]);
  const rosterPointMode = realRoster.some(
    (player) => typeof player.live_points === "number" || (player.live_game_state ?? "").toLowerCase() === "live"
  ) ? "live" : "projected";
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
        (total, player) => {
          return total + currentRosterPointValue(player);
        },
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
        (total, player) => {
          return total + currentRosterPointValue(player);
        },
        0
      )
    : null;

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
      <main className="relative mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8">
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
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-4 px-0 pb-24 pt-4 sm:gap-6 sm:px-6 sm:py-8">
      <div className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="cfb-micro-label text-cfb-brand">League Roster</p>
            <h1 className="cfb-display-title mt-1 text-3xl italic sm:mt-2 sm:text-5xl">Roster</h1>
            <p className="mt-2 hidden max-w-2xl text-sm font-medium leading-6 text-cfb-text-secondary sm:block">
              Manage your lineup or inspect every league team&apos;s current roster.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
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

      <TeamRosterRail
        teams={teamRosters}
        selectedTeamId={selectedTeamId}
        ownedTeamId={ownedTeamId}
        onSelect={setSelectedTeamId}
      />

      {isEmptyRoster ? (
        <section className="rounded-[1.25rem] border border-cfb-brand/30 bg-cfb-brand/[0.09] px-5 py-4">
          <p className="text-sm font-bold text-cfb-text-primary">
            No players on this roster yet. Complete the draft to populate your roster.
          </p>
        </section>
      ) : null}

      <section className="rounded-[1.25rem] border border-cfb-border-subtle bg-cfb-surface/70 px-4 py-3 sm:px-5 sm:py-4">
        <p className="cfb-micro-label text-cfb-brand">
          {viewingOwnedTeam ? "Managing your roster" : "Viewing league roster"}
        </p>
        <p className="mt-1 text-sm font-bold text-cfb-text-primary">
          {previewTeamName}{selectedTeamRoster?.team.record ? ` · ${selectedTeamRoster.team.record}` : ""}
          {!viewingOwnedTeam ? " · Read-only" : ""}
        </p>
      </section>

      <section className="grid grid-cols-3 gap-2 sm:gap-4">
        <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised p-3 sm:p-5">
          <p className="text-[9px] font-black uppercase leading-tight tracking-[0.12em] text-cfb-text-muted sm:text-[10px] sm:tracking-[0.2em]">
            {rosterPointMode === "live" ? "Starter Total" : "Starter Proj"}
          </p>
          <p className="mt-1 text-xl font-black tabular-nums text-cfb-brand sm:text-3xl">{starterTotal === null ? "N/A" : starterTotal.toFixed(1)}</p>
        </div>
        <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised p-3 sm:p-5">
          <p className="text-[9px] font-black uppercase leading-tight tracking-[0.12em] text-cfb-text-muted sm:text-[10px] sm:tracking-[0.2em]">
            {rosterPointMode === "live" ? "Bench Total" : "Bench Depth"}
          </p>
          <p className="mt-1 text-xl font-black tabular-nums text-cfb-text-primary sm:text-3xl">{benchTotal === null ? "N/A" : benchTotal.toFixed(1)}</p>
        </div>
        <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised p-3 sm:p-5">
          <p className="text-[9px] font-black uppercase leading-tight tracking-[0.12em] text-cfb-text-muted sm:text-[10px] sm:tracking-[0.2em]">
            Week
          </p>
          <p className="mt-1 text-xl font-black tabular-nums text-cfb-text-primary sm:text-3xl">{selectedWeek ?? rosterData?.week ?? 1}</p>
          {rosterData?.message ? (
            <p className="mt-2 text-xs font-semibold text-cfb-text-secondary">{rosterData.message}</p>
          ) : null}
        </div>
      </section>

      <RosterSlotTable
        title="Starters"
        players={starters}
        emptyText="No starters set yet."
        pointMode={rosterPointMode}
        leagueId={parsedLeagueId}
        ownedRosterActions={ownedRosterActions}
        quickSwapPlayer={quickSwapPlayer}
        onQuickSwapPlayerChange={setQuickSwapPlayer}
      />
      <RosterSlotTable
        title="Bench"
        players={bench}
        emptyText="Bench is empty."
        tone="bench"
        pointMode={rosterPointMode}
        leagueId={parsedLeagueId}
        ownedRosterActions={ownedRosterActions}
        quickSwapPlayer={quickSwapPlayer}
        onQuickSwapPlayerChange={setQuickSwapPlayer}
      />
      <RosterSlotTable
        title={`IR (${rosterData?.ir_slots ?? 0})`}
        players={ir}
        emptyText="IR spot empty."
        pointMode={rosterPointMode}
        leagueId={parsedLeagueId}
        ownedRosterActions={ownedRosterActions}
        quickSwapPlayer={quickSwapPlayer}
        onQuickSwapPlayerChange={setQuickSwapPlayer}
      />
    </main>
  );
}
