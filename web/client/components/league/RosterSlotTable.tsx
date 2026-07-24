import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { usePlayerCard } from "@/hooks/use-players";
import { useDropRosterPlayer, useUpdateLineup } from "@/hooks/use-roster-actions";
import { getEligibleSlotsForPosition, normalizePosition } from "@/lib/rosterLegality";
import type { LeagueRosterPlayer } from "@/types/league";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const slotRank = (slot?: string | null) => {
  const order = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];
  const index = order.indexOf((slot || "BENCH").toUpperCase());
  return index === -1 ? order.length : index;
};

const slotType = (player: LeagueRosterPlayer) =>
  (player.slot ?? player.roster_slot ?? "BENCH").toUpperCase();

const slotLabel = (player: LeagueRosterPlayer) => player.display_label ?? slotType(player);

const positionLabel = (player: LeagueRosterPlayer) =>
  (player.position ?? player.player_position ?? "—").toUpperCase();

const schoolAcronyms = new Set(["BYU", "LSU", "SMU", "TCU", "UCF", "UCLA", "USC"]);

const displaySchoolName = (school?: string | null) => {
  const value = school?.trim();
  if (!value || value !== value.toUpperCase()) return value ?? "";
  return value
    .split(/(\s+)/)
    .map((part) => {
      if (!part.trim() || schoolAcronyms.has(part) || /[&()]/.test(part)) return part;
      return `${part.slice(0, 1)}${part.slice(1).toLowerCase()}`;
    })
    .join("");
};

const weeklyProjectionLabel = (player: LeagueRosterPlayer) => {
  const projection = player.projected_points ?? player.weekly_projected_fantasy_points;
  return typeof projection === "number" && Number.isFinite(projection) ? projection.toFixed(1) : "0.0";
};

const isRealRosterPlayer = (player: LeagueRosterPlayer) =>
  Boolean(
    player.player_id !== null &&
      player.player_id !== undefined &&
      !player.is_placeholder &&
      !/\bpreview\b/i.test(player.player_name ?? ""),
  );

const positionStyles: Record<
  string,
  {
    pill: string;
    row: string;
    dot: string;
    text: string;
    border: string;
    panel: string;
  }
> = {
  QB: {
    pill: "border-blue-300/45 bg-blue-400/15 text-blue-100 shadow-[0_0_22px_rgba(96,165,250,0.18)]",
    row: "hover:bg-blue-400/[0.06]",
    dot: "bg-blue-300 shadow-[0_0_16px_rgba(147,197,253,0.75)]",
    text: "text-blue-200",
    border: "border-blue-300/25",
    panel: "from-blue-500/18",
  },
  RB: {
    pill: "border-emerald-300/45 bg-emerald-400/15 text-emerald-100 shadow-[0_0_22px_rgba(52,211,153,0.18)]",
    row: "hover:bg-emerald-400/[0.06]",
    dot: "bg-emerald-300 shadow-[0_0_16px_rgba(110,231,183,0.75)]",
    text: "text-emerald-200",
    border: "border-emerald-300/25",
    panel: "from-emerald-500/18",
  },
  WR: {
    pill: "border-violet-300/45 bg-violet-400/15 text-violet-100 shadow-[0_0_22px_rgba(167,139,250,0.18)]",
    row: "hover:bg-violet-400/[0.06]",
    dot: "bg-violet-300 shadow-[0_0_16px_rgba(196,181,253,0.75)]",
    text: "text-violet-200",
    border: "border-violet-300/25",
    panel: "from-violet-500/18",
  },
  TE: {
    pill: "border-amber-300/45 bg-amber-400/15 text-amber-100 shadow-[0_0_22px_rgba(251,191,36,0.18)]",
    row: "hover:bg-amber-400/[0.06]",
    dot: "bg-amber-300 shadow-[0_0_16px_rgba(252,211,77,0.75)]",
    text: "text-amber-200",
    border: "border-amber-300/25",
    panel: "from-amber-500/18",
  },
  K: {
    pill: "border-white/70 bg-white/15 text-white shadow-[0_0_24px_rgba(255,255,255,0.28)]",
    row: "hover:bg-white/[0.07]",
    dot: "bg-white shadow-[0_0_18px_rgba(255,255,255,0.95)]",
    text: "text-white",
    border: "border-white/35",
    panel: "from-white/18",
  },
  FLEX: {
    pill: "border-fuchsia-300/45 bg-fuchsia-400/15 text-fuchsia-100 shadow-[0_0_22px_rgba(217,70,239,0.18)]",
    row: "hover:bg-fuchsia-400/[0.06]",
    dot: "bg-fuchsia-300 shadow-[0_0_16px_rgba(240,171,252,0.75)]",
    text: "text-fuchsia-200",
    border: "border-fuchsia-300/25",
    panel: "from-fuchsia-500/18",
  },
  BENCH: {
    pill: "border-slate-300/30 bg-slate-300/10 text-slate-200",
    row: "hover:bg-slate-300/[0.04]",
    dot: "bg-slate-400 shadow-[0_0_14px_rgba(148,163,184,0.55)]",
    text: "text-slate-200",
    border: "border-slate-300/15",
    panel: "from-slate-500/12",
  },
  IR: {
    pill: "border-rose-300/40 bg-rose-400/15 text-rose-100",
    row: "hover:bg-rose-400/[0.05]",
    dot: "bg-rose-300 shadow-[0_0_14px_rgba(251,113,133,0.6)]",
    text: "text-rose-200",
    border: "border-rose-300/20",
    panel: "from-rose-500/14",
  },
};

const getPositionStyle = (position?: string | null) =>
  positionStyles[(position || "").toUpperCase()] ?? positionStyles.FLEX;

type RosterSlotTableTone = "default" | "bench";

type OwnedRosterActions = {
  teamId: number;
  roster: LeagueRosterPlayer[];
  superflexEnabled: boolean;
};

const isUnavailableForSwap = (player: LeagueRosterPlayer) => {
  const status = (player.status ?? "").toUpperCase();
  return Boolean(player.is_locked || player.is_ir || ["OUT", "IR", "INJURED", "PUP"].includes(status));
};

const playerCanFillSlot = (player: LeagueRosterPlayer, slot: string, superflexEnabled: boolean) => {
  const position = normalizePosition(player.position ?? player.player_position);
  return Boolean(position && getEligibleSlotsForPosition(position, superflexEnabled).includes(slot as never));
};

export function RosterSlotTable({
  title,
  players,
  emptyText = "No roster players yet.",
  showPositionColumn = true,
  tone = "default",
  leagueId,
  ownedRosterActions,
}: {
  title: string;
  players: LeagueRosterPlayer[];
  emptyText?: string;
  showPositionColumn?: boolean;
  tone?: RosterSlotTableTone;
  leagueId?: number | string;
  ownedRosterActions?: OwnedRosterActions;
}) {
  const navigate = useNavigate();
  const [selectedPlayer, setSelectedPlayer] = useState<LeagueRosterPlayer | null>(null);
  const [swapPlayer, setSwapPlayer] = useState<LeagueRosterPlayer | null>(null);
  const [swapError, setSwapError] = useState<string | null>(null);
  const isBenchTone = tone === "bench";
  const sorted = [...players].sort((left, right) => {
    const slotDelta = slotRank(left.roster_slot || left.slot) - slotRank(right.roster_slot || right.slot);
    if (slotDelta !== 0) return slotDelta;
    return (left.slot_index ?? 0) - (right.slot_index ?? 0);
  });

  const selectedPosition = selectedPlayer ? positionLabel(selectedPlayer) : null;
  const selectedProjection =
    selectedPlayer?.projected_points ?? selectedPlayer?.weekly_projected_fantasy_points ?? 0;
  const { data: selectedPlayerCard, isLoading: selectedPlayerCardLoading } = usePlayerCard(
    selectedPlayer?.player_id,
    Boolean(selectedPlayer?.player_id)
  );
  const ownedTeamId = ownedRosterActions?.teamId;
  const numericLeagueId = typeof leagueId === "number" ? leagueId : Number(leagueId);
  const updateLineupMutation = useUpdateLineup(ownedTeamId, Number.isFinite(numericLeagueId) ? numericLeagueId : undefined);
  const dropPlayerMutation = useDropRosterPlayer(ownedTeamId, Number.isFinite(numericLeagueId) ? numericLeagueId : undefined);
  const tableColumns = showPositionColumn
    ? "md:grid-cols-[0.55fr_1.45fr_0.75fr_0.45fr_0.55fr_0.5fr]"
    : "md:grid-cols-[0.55fr_1.6fr_0.9fr_0.65fr_0.5fr]";
  const openTradeBuilder = () => {
    if (!leagueId || !selectedPlayer?.player_id) return;
    const teamId = selectedPlayer.team_id ?? selectedPlayer.fantasy_team_id;
    const query = teamId ? `?teamId=${teamId}` : "";
    navigate(`/trade/${leagueId}/${selectedPlayer.player_id}${query}`);
  };
  const swapCandidates = useMemo(() => {
    if (!swapPlayer || !ownedRosterActions) return [];
    const selectedSlot = slotType(swapPlayer);
    return ownedRosterActions.roster.filter((candidate) => {
      if (candidate.id === swapPlayer.id || !isRealRosterPlayer(candidate) || isUnavailableForSwap(candidate)) return false;
      const candidateSlot = slotType(candidate);
      return (
        candidateSlot !== selectedSlot &&
        playerCanFillSlot(candidate, selectedSlot, ownedRosterActions.superflexEnabled) &&
        playerCanFillSlot(swapPlayer, candidateSlot, ownedRosterActions.superflexEnabled)
      );
    });
  }, [ownedRosterActions, swapPlayer]);
  const beginSwap = () => {
    if (!selectedPlayer || !ownedRosterActions || isUnavailableForSwap(selectedPlayer)) return;
    setSwapError(null);
    setSwapPlayer(selectedPlayer);
    setSelectedPlayer(null);
  };
  const confirmSwap = async (candidate: LeagueRosterPlayer) => {
    if (!swapPlayer || !swapPlayer.id || !candidate.id || !swapPlayer.slot_index || !candidate.slot_index) return;
    setSwapError(null);
    try {
      await updateLineupMutation.mutateAsync([
        {
          roster_entry_id: swapPlayer.id,
          slot: slotType(candidate),
          slot_index: candidate.slot_index,
        },
        {
          roster_entry_id: candidate.id,
          slot: slotType(swapPlayer),
          slot_index: swapPlayer.slot_index,
        },
      ]);
      setSwapPlayer(null);
    } catch (error) {
      setSwapError(error instanceof Error ? error.message : "Unable to swap players.");
    }
  };
  const dropSelectedPlayer = async () => {
    if (!selectedPlayer || !selectedPlayer.id || !ownedRosterActions || isUnavailableForSwap(selectedPlayer)) return;
    if (!window.confirm(`Drop ${selectedPlayer.player_name}? You can add them again if they are available.`)) return;
    try {
      await dropPlayerMutation.mutateAsync(selectedPlayer.id);
      setSelectedPlayer(null);
    } catch (error) {
      setSwapError(error instanceof Error ? error.message : "Unable to drop player.");
    }
  };

  return (
    <section
      className={cn(
        "overflow-hidden rounded-[1.5rem] border",
        isBenchTone
          ? "border-slate-300/15 bg-[linear-gradient(135deg,rgba(5,10,18,0.98),rgba(13,18,28,0.94)_52%,rgba(8,13,24,0.98))] shadow-[0_18px_54px_rgba(2,6,23,0.42)]"
          : "border-sky-300/15 bg-[linear-gradient(135deg,rgba(8,18,32,0.98),rgba(13,23,39,0.94)_48%,rgba(15,23,42,0.98))] shadow-[0_22px_70px_rgba(14,165,233,0.08)]"
      )}
    >
      <div
        className={cn(
          "border-b px-5 py-4",
          isBenchTone ? "border-white/10 bg-white/[0.025]" : "border-sky-300/10 bg-sky-300/[0.03]"
        )}
      >
        <h2
          className={cn(
            "text-[11px] font-black uppercase tracking-[0.22em]",
            isBenchTone ? "text-slate-300" : "text-sky-300"
          )}
        >
          {title}
        </h2>
      </div>
      {sorted.length === 0 ? (
        <p
          className={cn(
            "border-t border-dashed px-5 py-6 text-sm text-slate-400",
            isBenchTone ? "border-white/10" : "border-sky-300/10"
          )}
        >
          {emptyText}
        </p>
      ) : (
        <div className="divide-y divide-white/10">
          <div className={cn("hidden gap-3 px-5 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500 md:grid", tableColumns)}>
            <span>Slot</span>
            <span>Player</span>
            <span>School</span>
            {showPositionColumn ? <span>Pos</span> : null}
            <span>Opp</span>
            <span className="text-right">Proj</span>
          </div>
          {sorted.map((player) => {
            const position = positionLabel(player);
            const isRealPlayer = isRealRosterPlayer(player);
            const style = getPositionStyle(isRealPlayer ? position : slotType(player));
            const projection = isRealPlayer
              ? player.projected_points ?? player.weekly_projected_fantasy_points ?? null
              : 0;
            return (
              <button
                key={player.slot_id ?? `${player.team_id ?? player.fantasy_team_id}-${slotType(player)}-${player.slot_index ?? 0}`}
                type="button"
                onClick={() => {
                  if (!isRealPlayer) return;
                  setSelectedPlayer(player);
                }}
                disabled={!isRealPlayer}
                aria-disabled={!isRealPlayer}
                className={cn(
                  "grid w-full gap-3 px-5 py-4 text-left text-sm text-cfb-text-secondary transition focus:outline-none focus-visible:bg-cfb-brand/[0.08] focus-visible:ring-2 focus-visible:ring-cfb-brand/50 md:items-center",
                  tableColumns,
                  isRealPlayer ? style.row : "cursor-not-allowed opacity-75"
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex min-w-[3.25rem] shrink-0 justify-center whitespace-nowrap rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em]",
                      style.pill
                    )}
                  >
                    {slotLabel(player)}
                  </span>
                  <span className={cn("h-2.5 w-2.5 rounded-full", style.dot)} />
                </span>
                <span className="flex flex-col gap-1">
                  <span className="font-black text-cfb-text-primary">{isRealPlayer ? player.player_name : "N/A"}</span>
                  <span
                    className={cn(
                      "inline-flex w-fit shrink-0 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[9px] font-black uppercase tracking-[0.14em]",
                      style.pill
                    )}
                  >
                    {position}
                  </span>
                </span>
                <span className="text-cfb-text-muted">{isRealPlayer ? displaySchoolName(player.school ?? player.player_school) || "—" : "—"}</span>
                {showPositionColumn ? (
                  <span className={cn("font-black", style.text)}>{position}</span>
                ) : null}
                <span className="text-cfb-text-muted">{isRealPlayer ? player.opponent ?? "TBD" : "—"}</span>
                <span className={cn("text-right font-black", style.text)}>
                  {typeof projection === "number" && Number.isFinite(projection) ? projection.toFixed(1) : "0.0"}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {selectedPlayer ? (
        <PlayerCardModal
          action={
            leagueId && selectedPlayer.player_id
              ? {
                  label: "Trade Player",
                  onClick: openTradeBuilder,
                }
              : null
          }
          actions={
            ownedRosterActions && !isUnavailableForSwap(selectedPlayer)
              ? [
                  { label: "Swap Player", onClick: beginSwap },
                  { label: "Drop Player", onClick: () => void dropSelectedPlayer() },
                ]
              : []
          }
          card={selectedPlayerCard}
          loading={selectedPlayerCardLoading}
          onClose={() => setSelectedPlayer(null)}
          player={{
            id: selectedPlayer.player_id ?? 0,
            name: selectedPlayer.player_name ?? "Unknown player",
            school: selectedPlayer.school ?? selectedPlayer.player_school,
            position: selectedPosition,
            rankLabel: selectedPosition ?? "N/A",
            projectedPoints: selectedProjection,
            opponent: selectedPlayer.opponent,
            playerClass: null,
            status: selectedPlayer.status,
            projection: {
              fpts: selectedProjection,
              floor: selectedPlayer.floor ?? undefined,
              ceiling: selectedPlayer.ceiling ?? undefined,
              boomProb: selectedPlayer.boom_prob ?? undefined,
              bustProb: selectedPlayer.bust_prob ?? undefined,
            },
          }}
          title="Roster Player Card"
        />
      ) : null}
      <Dialog open={Boolean(swapPlayer)} onOpenChange={(open) => !open && setSwapPlayer(null)}>
        <DialogContent
          className="max-w-2xl border-white/10 bg-slate-950 text-slate-50"
          overlayClassName="bg-slate-950/45 backdrop-blur-[2px]"
        >
          <DialogHeader>
            <DialogTitle className="pr-8 text-2xl font-black italic">Swap {swapPlayer?.player_name}</DialogTitle>
            <DialogDescription className="text-slate-300">
              Choose an unlocked, healthy teammate eligible for {swapPlayer ? slotLabel(swapPlayer) : "this slot"}. Both lineup slots update together.
            </DialogDescription>
          </DialogHeader>
          {swapCandidates.length ? (
            <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
              {swapCandidates.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  disabled={updateLineupMutation.isPending}
                  onClick={() => void confirmSwap(candidate)}
                  className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-white/[0.045] p-4 text-left transition hover:border-cyan-200/40 hover:bg-cyan-200/10 disabled:opacity-60"
                >
                  <span>
                    <span className="block font-black text-white">{candidate.player_name}</span>
                    <span className="mt-1 block text-[10px] font-black uppercase tracking-[0.16em] text-white/55">
                      {positionLabel(candidate)} • {displaySchoolName(candidate.school ?? candidate.player_school)}
                    </span>
                    <span className="mt-2 block text-[10px] font-black uppercase tracking-[0.14em] text-cyan-100/70">
                      Opp {candidate.opponent ?? "TBD"} • Proj {weeklyProjectionLabel(candidate)}
                    </span>
                  </span>
                  <span className="rounded-full border border-white/15 px-3 py-1 text-[9px] font-black uppercase tracking-[0.14em] text-white/70">
                    {slotLabel(candidate)}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm font-semibold text-slate-300">
              No eligible, unlocked teammates can make this swap.
            </p>
          )}
          {swapError ? <p className="text-sm font-bold text-red-300">{swapError}</p> : null}
          <DialogFooter>
            <button type="button" onClick={() => setSwapPlayer(null)} className="rounded-xl border border-white/15 px-4 py-2 text-xs font-black uppercase tracking-[0.14em] text-white/75">
              Cancel
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
