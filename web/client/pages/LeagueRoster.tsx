import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { WeekSelector } from "@/components/league/WeekSelector";
import { useLeagueRosterTab, useLeagueSettingsTab } from "@/hooks/use-leagues";
import {
  DEMO_LEAGUE_ID,
  createDemoLeagueRosterResponse,
} from "@/lib/leaguePreviewData";
import {
  createEmptyRosterSlotRows,
  isRealRosterPlayer,
  rosterProjectionTotal,
  shouldBlankRoster,
} from "@/lib/rosterDisplay";

const PRE_DRAFT_STATUSES = new Set([
  "created",
  "draft_pending",
  "draft_scheduled",
  "pending",
  "scheduled",
]);

const isPreDraftStatus = (value?: string | null) =>
  PRE_DRAFT_STATUSES.has((value ?? "").trim().toLowerCase());

const starterSlot = (slot?: string | null) => {
  const normalized = (slot || "").toUpperCase();
  return normalized !== "BENCH" && normalized !== "IR";
};

export default function LeagueRoster() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const rosterQuery = useLeagueRosterTab(
    parsedLeagueId,
    selectedWeek ?? undefined,
    !isDemoLeague
  );
  const demoData = isDemoLeague ? createDemoLeagueRosterResponse() : null;
  const isPreDraft =
    !isDemoLeague &&
    (isPreDraftStatus(settingsQuery.data?.league_status) ||
      isPreDraftStatus(settingsQuery.data?.draft_status));
  const rosterData = demoData ?? rosterQuery.data;
  const fetchedRoster = rosterData?.roster ?? rosterData?.data ?? [];
  const previewTeamName = rosterData?.owned_team?.name ?? rosterData?.fantasy_team_name ?? "Your Team";
  const roster = fetchedRoster;
  const realRosterPlayers = roster.filter(isRealRosterPlayer);
  const hasRealRosterPlayers = realRosterPlayers.length > 0;
  const forceBlankRoster = shouldBlankRoster(roster, {
    isDemoLeague,
    isPreDraft,
    message: rosterData?.message,
  });
  const emptyRosterSlots = useMemo(
    () =>
      createEmptyRosterSlotRows({
        rosterSlotLimits: rosterData?.roster_slot_limits,
        fantasyTeamId: rosterData?.fantasy_team_id ?? rosterData?.owned_team?.id ?? null,
        fantasyTeamName: previewTeamName,
        leagueId: rosterData?.league_id ?? parsedLeagueId,
      }),
    [
      parsedLeagueId,
      previewTeamName,
      rosterData?.fantasy_team_id,
      rosterData?.league_id,
      rosterData?.owned_team?.id,
      rosterData?.roster_slot_limits,
    ]
  );
  const displayRoster = forceBlankRoster ? emptyRosterSlots : realRosterPlayers;
  const isEmptyRealRoster =
    !isDemoLeague && !rosterQuery.isLoading && (forceBlankRoster || !hasRealRosterPlayers);
  const rawStarters = useMemo(
    () => displayRoster.filter((player) => starterSlot(player.slot ?? player.roster_slot)),
    [displayRoster]
  );
  const rawBench = useMemo(
    () => displayRoster.filter((player) => (player.slot ?? player.roster_slot ?? "").toUpperCase() === "BENCH"),
    [displayRoster]
  );
  const rawIr = useMemo(
    () => displayRoster.filter((player) => (player.slot ?? player.roster_slot ?? "").toUpperCase() === "IR"),
    [displayRoster]
  );
  const starters = rawStarters;
  const bench = rawBench;
  const ir = rawIr;
  const starterTotal = rosterProjectionTotal(starters, forceBlankRoster);
  const benchTotal = rosterProjectionTotal(bench, forceBlankRoster);

  if (settingsQuery.isLoading && !settingsQuery.isError && !isDemoLeague) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <section className="rounded-[1.5rem] border border-sky-300/15 bg-[#0b1424]/90 p-6">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
            Loading league state
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-400">
            Checking whether this league has completed the draft.
          </p>
        </section>
      </main>
    );
  }

  if (rosterQuery.isError && !isDemoLeague) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <section className="rounded-[1.5rem] border border-red-300/20 bg-red-500/10 p-6">
          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-red-200">
            Unable to load roster
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-300">
            Retry after confirming your session and league access are still valid.
          </p>
          <button
            type="button"
            className="mt-4 rounded-xl border border-red-200/30 bg-red-300/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-red-100"
            onClick={() => {
            void settingsQuery.refetch();
            void rosterQuery.refetch();
          }}
          >
            Retry
          </button>
        </section>
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
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      {isEmptyRealRoster ? (
        <section className="rounded-[1.25rem] border border-sky-300/25 bg-sky-400/[0.08] px-5 py-4 shadow-[0_0_36px_rgba(56,189,248,0.12)]">
          <p className="text-sm font-bold text-sky-100">
            No players on this roster yet. Complete the draft to populate your roster.
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[1.35rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(14,165,233,0.16),rgba(15,23,42,0.92))] p-5 shadow-[0_18px_60px_rgba(14,165,233,0.12)]">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            Starter Projection
          </p>
          <p className="mt-1 text-3xl font-black text-sky-100">
            {starterTotal === null ? "N/A" : starterTotal.toFixed(1)}
          </p>
        </div>
        <div className="rounded-[1.35rem] border border-white/10 bg-[#0b1424]/90 p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Bench Depth
          </p>
          <p className="mt-1 text-3xl font-black text-slate-100">
            {benchTotal === null ? "N/A" : benchTotal.toFixed(1)}
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

      <RosterSlotTable title="Starters" players={starters} emptyText="No players on this roster yet. Complete the draft to populate your roster." leagueId={parsedLeagueId} forceBlank={forceBlankRoster} />
      <RosterSlotTable title="Bench" players={bench} emptyText="No players on this roster yet. Complete the draft to populate your roster." leagueId={parsedLeagueId} forceBlank={forceBlankRoster} />
      <RosterSlotTable
        title={`IR (${rosterData?.ir_slots ?? 0})`}
        players={ir}
        emptyText="IR spot empty."
        leagueId={parsedLeagueId}
        forceBlank={forceBlankRoster}
      />
    </main>
  );
}
