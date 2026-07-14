import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { WeekSelector } from "@/components/league/WeekSelector";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useLeagueRosterTab } from "@/hooks/use-leagues";
import { useUpdateLineup } from "@/hooks/use-roster-actions";
import {
  DEMO_LEAGUE_ID,
  createDemoLeagueRosterResponse,
} from "@/lib/leaguePreviewData";
import { getEligibleSlotsForPosition, normalizePosition } from "@/lib/rosterLegality";
import type { LeagueRosterPlayer } from "@/types/league";

const starterSlot = (slot?: string | null) => {
  const normalized = (slot || "").toUpperCase();
  return normalized !== "BENCH" && normalized !== "IR";
};

const rosterSlotOrder = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];

const isRealRosterPlayer = (player: LeagueRosterPlayer) =>
  Boolean(
    player.player_id !== null &&
      player.player_id !== undefined &&
      !player.is_placeholder &&
      !/\bpreview\b/i.test(player.player_name ?? ""),
  );

function createEmptyRosterSlots(
  slotLimits: Record<string, number> | undefined,
  teamId: number,
  teamName: string,
): LeagueRosterPlayer[] {
  const limits = slotLimits && Object.keys(slotLimits).length > 0
    ? slotLimits
    : { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, BENCH: 4, IR: 1 };
  let rowIndex = 0;

  return rosterSlotOrder.flatMap((slot) => {
    const count = Math.max(0, Number(limits[slot] ?? 0));
    return Array.from({ length: count }, () => {
      rowIndex += 1;
      return {
        id: -rowIndex,
        league_id: null,
        team_id: teamId,
        fantasy_team_id: teamId,
        fantasy_team_name: teamName,
        player_id: null,
        player_name: "N/A",
        player_school: null,
        player_position: slot === "BENCH" || slot === "IR" ? slot : slot,
        school: null,
        position: slot === "BENCH" || slot === "IR" ? slot : slot,
        slot,
        roster_slot: slot,
        status: "EMPTY",
        acquisition_type: "EMPTY",
        draft_pick_id: null,
        is_starter: starterSlot(slot),
        is_ir: slot === "IR",
        opponent: null,
        projected_points: null,
        floor: null,
        ceiling: null,
        boom_prob: null,
        bust_prob: null,
        weekly_projected_fantasy_points: null,
        is_placeholder: true,
      };
    });
  });
}

export default function LeagueRoster() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [selectedWeek, setSelectedWeek] = useState<number | null>(1);
  const [lineupSlots, setLineupSlots] = useState<Record<number, string>>({});
  const [lineupMessage, setLineupMessage] = useState<string | null>(null);
  const rosterQuery = useLeagueRosterTab(parsedLeagueId, selectedWeek ?? undefined, !isDemoLeague);
  const demoData = isDemoLeague ? createDemoLeagueRosterResponse() : null;
  const rosterData = demoData ?? rosterQuery.data;
  const fetchedRoster = rosterData?.roster ?? rosterData?.data ?? [];
  const previewTeamName = rosterData?.owned_team?.name ?? rosterData?.fantasy_team_name ?? "Your Team";
  const previewTeamId = rosterData?.owned_team?.id ?? rosterData?.fantasy_team_id ?? -100;
  const realRoster = useMemo(() => fetchedRoster.filter(isRealRosterPlayer), [fetchedRoster]);
  const hasRealRosterPlayers = realRoster.length > 0;
  const isEmptyRoster = !isDemoLeague && !rosterQuery.isLoading && !hasRealRosterPlayers;
  const roster = isEmptyRoster
    ? createEmptyRosterSlots(
        rosterData?.roster_slot_limits,
        previewTeamId ?? -100,
        previewTeamName ?? "Your Team",
      )
    : realRoster;
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
  const starterTotal = hasRealRosterPlayers
    ? starters.reduce(
        (total, player) => total + Number(player.projected_points ?? player.weekly_projected_fantasy_points ?? 0),
        0
      )
    : null;
  const updateLineupMutation = useUpdateLineup(
    typeof previewTeamId === "number" && previewTeamId > 0 ? previewTeamId : undefined,
    parsedLeagueId,
  );
  const lineupRows = useMemo(
    () => realRoster.filter((player) => typeof player.id === "number" && player.id > 0),
    [realRoster],
  );
  const lineupSeed = useMemo(
    () => lineupRows.map((player) => `${player.id}:${(player.slot ?? player.roster_slot ?? "BENCH").toUpperCase()}`).join("|"),
    [lineupRows],
  );
  useEffect(() => {
    setLineupSlots(
      Object.fromEntries(
        lineupRows.map((player) => [
          player.id,
          (player.slot ?? player.roster_slot ?? "BENCH").toUpperCase(),
        ]),
      ),
    );
    setLineupMessage(null);
  }, [lineupRows, lineupSeed]);
  const lineupAssignments = useMemo(
    () =>
      lineupRows
        .map((player) => {
          const currentSlot = (player.slot ?? player.roster_slot ?? "BENCH").toUpperCase();
          const nextSlot = (lineupSlots[player.id] ?? currentSlot).toUpperCase();
          return currentSlot === nextSlot ? null : { roster_entry_id: player.id, slot: nextSlot };
        })
        .filter((assignment): assignment is { roster_entry_id: number; slot: string } => Boolean(assignment)),
    [lineupRows, lineupSlots],
  );
  const getSlotOptions = (player: LeagueRosterPlayer) => {
    const currentSlot = (player.slot ?? player.roster_slot ?? "BENCH").toUpperCase();
    const position = normalizePosition(player.position ?? player.player_position);
    const baseOptions = position
      ? getEligibleSlotsForPosition(position, Number(rosterData?.roster_slot_limits?.SUPERFLEX ?? 0) > 0)
      : ["BENCH"];
    const options = new Set<string>(baseOptions);
    if (Number(rosterData?.roster_slot_limits?.IR ?? 0) > 0) options.add("IR");
    options.add(currentSlot);
    return Array.from(options).filter((slot) => slot === currentSlot || Number(rosterData?.roster_slot_limits?.[slot] ?? 0) > 0);
  };
  const saveLineup = async () => {
    setLineupMessage(null);
    try {
      await updateLineupMutation.mutateAsync(lineupAssignments);
      setLineupMessage("Lineup saved.");
    } catch (error) {
      setLineupMessage(error instanceof Error ? error.message : "Unable to save lineup.");
    }
  };

  const benchTotal = hasRealRosterPlayers
    ? bench.reduce(
        (total, player) => total + Number(player.projected_points ?? player.weekly_projected_fantasy_points ?? 0),
        0
      )
    : null;

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

      {isEmptyRoster ? (
        <section className="cfb-playbook-pattern rounded-[1.25rem] border border-cfb-brand/30 bg-cfb-brand/[0.09] px-5 py-4 shadow-[0_0_36px_hsl(var(--brand-primary)/0.12)]">
          <p className="relative text-sm font-bold text-blue-50">
            No players on this roster yet. Complete the draft to populate your roster.
          </p>
        </section>
      ) : null}

      {hasRealRosterPlayers ? (
        <section className="overflow-hidden rounded-[1.5rem] border border-cfb-brand/20 bg-cfb-surface-raised/90 shadow-[0_22px_70px_hsl(var(--brand-primary)/0.08)]">
          <div className="flex flex-col gap-3 border-b border-cfb-border-subtle px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-cfb-brand">Lineup Editor</h2>
              <p className="mt-1 text-sm font-semibold text-cfb-text-secondary">
                Move players between eligible starter, bench, and IR slots before lineup lock.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void saveLineup()}
              disabled={lineupAssignments.length === 0 || updateLineupMutation.isPending || isDemoLeague}
              className="rounded-2xl border border-cfb-brand/35 bg-cfb-brand px-5 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-obsidian shadow-[0_0_28px_hsl(var(--brand-primary)/0.22)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:border-cfb-border-subtle disabled:bg-cfb-surface disabled:text-cfb-text-muted disabled:shadow-none"
            >
              {updateLineupMutation.isPending ? "Saving" : "Save Lineup"}
            </button>
          </div>
          <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
            {lineupRows.map((player) => {
              const position = (player.position ?? player.player_position ?? "N/A").toUpperCase();
              const currentSlot = (player.slot ?? player.roster_slot ?? "BENCH").toUpperCase();
              const selectedSlot = lineupSlots[player.id] ?? currentSlot;
              return (
                <div key={player.id} className="rounded-2xl border border-cfb-border-subtle bg-cfb-canvas/60 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-black text-cfb-text-primary">{player.player_name}</p>
                      <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">
                        {position} • {player.school ?? player.player_school ?? "School TBD"}
                      </p>
                    </div>
                    <span className="rounded-full border border-cfb-border-subtle px-2.5 py-1 text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-secondary">
                      {currentSlot}
                    </span>
                  </div>
                  <Select
                    value={selectedSlot}
                    onValueChange={(slot) => {
                      setLineupSlots((previous) => ({ ...previous, [player.id]: slot }));
                      setLineupMessage(null);
                    }}
                    disabled={isDemoLeague || updateLineupMutation.isPending}
                  >
                    <SelectTrigger className="mt-3 border-cfb-border-subtle bg-cfb-surface text-cfb-text-primary">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {getSlotOptions(player).map((slot) => (
                        <SelectItem key={slot} value={slot}>
                          {slot}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              );
            })}
          </div>
          {lineupMessage ? (
            <p className="border-t border-cfb-border-subtle px-5 py-3 text-sm font-bold text-cfb-text-secondary">
              {lineupMessage}
            </p>
          ) : null}
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
