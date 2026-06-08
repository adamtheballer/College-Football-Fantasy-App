import { useMemo, useState } from "react";
import { AlertCircle, ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { DraftBoardPick, DraftBoardPlayer, DraftBoardRoster, DraftBoardState } from "@/types/draft-board";
import { AvailablePlayersTable } from "./AvailablePlayersTable";
import { DraftCompleteModal } from "./DraftCompleteModal";
import { DraftOrderPanel } from "./DraftOrderPanel";
import { DraftStatusHeader } from "./DraftStatusHeader";

type DraftBoardActiveTab = "draft" | "queue" | "roster" | "history";

const draftBoardTabs: Array<{ value: DraftBoardActiveTab; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "queue", label: "Queue" },
  { value: "roster", label: "Roster" },
  { value: "history", label: "History" },
];

type RosterSlotDefinition = {
  key: string;
  label: string;
  accepts: string[];
  area: "starter" | "bench" | "ir";
};

const rosterSlotDefinitions: RosterSlotDefinition[] = [
  { key: "QB", label: "QB", accepts: ["QB"], area: "starter" },
  { key: "RB1", label: "RB1", accepts: ["RB"], area: "starter" },
  { key: "RB2", label: "RB2", accepts: ["RB"], area: "starter" },
  { key: "WR1", label: "WR1", accepts: ["WR"], area: "starter" },
  { key: "WR2", label: "WR2", accepts: ["WR"], area: "starter" },
  { key: "TE", label: "TE", accepts: ["TE"], area: "starter" },
  { key: "FLEX", label: "FLEX", accepts: ["RB", "WR", "TE"], area: "starter" },
  { key: "K", label: "K", accepts: ["K"], area: "starter" },
  { key: "BENCH1", label: "Bench 1", accepts: ["QB", "RB", "WR", "TE", "K"], area: "bench" },
  { key: "BENCH2", label: "Bench 2", accepts: ["QB", "RB", "WR", "TE", "K"], area: "bench" },
  { key: "BENCH3", label: "Bench 3", accepts: ["QB", "RB", "WR", "TE", "K"], area: "bench" },
  { key: "BENCH4", label: "Bench 4", accepts: ["QB", "RB", "WR", "TE", "K"], area: "bench" },
  { key: "BENCH5", label: "Bench 5", accepts: ["QB", "RB", "WR", "TE", "K"], area: "bench" },
  { key: "IR", label: "IR", accepts: [], area: "ir" },
];

const rosterPositionStyles: Record<string, { border: string; bg: string; glow: string; text: string; dot: string }> = {
  QB: { border: "border-blue-300/30", bg: "bg-[#0b1830]", glow: "shadow-[inset_0_1px_0_rgba(147,197,253,0.08)]", text: "text-blue-100/85", dot: "bg-blue-400/60" },
  RB: { border: "border-emerald-300/30", bg: "bg-[#0a1f24]", glow: "shadow-[inset_0_1px_0_rgba(110,231,183,0.08)]", text: "text-emerald-100/85", dot: "bg-emerald-400/60" },
  WR: { border: "border-violet-300/30", bg: "bg-[#151530]", glow: "shadow-[inset_0_1px_0_rgba(196,181,253,0.08)]", text: "text-violet-100/85", dot: "bg-violet-400/60" },
  TE: { border: "border-amber-300/30", bg: "bg-[#211b16]", glow: "shadow-[inset_0_1px_0_rgba(252,211,77,0.08)]", text: "text-amber-100/85", dot: "bg-amber-400/60" },
  K: { border: "border-slate-300/25", bg: "bg-[#182235]", glow: "shadow-[inset_0_1px_0_rgba(203,213,225,0.07)]", text: "text-slate-100/85", dot: "bg-slate-400/55" },
  EMPTY: { border: "border-white/10", bg: "bg-[#071224]", glow: "shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]", text: "text-muted-foreground", dot: "bg-white/18" },
};

const normalizeRosterPosition = (position: string | null | undefined) => (position || "").trim().toUpperCase();

const assignRosterSlots = (picks: DraftBoardPick[]) => {
  const assignments = new Map<string, DraftBoardPick>();
  const sortedPicks = [...picks].sort((a, b) => a.overallPick - b.overallPick);
  for (const pick of sortedPicks) {
    const position = normalizeRosterPosition(pick.playerPosition);
    const eligibleStarter = rosterSlotDefinitions.find((slot) => slot.area === "starter" && !assignments.has(slot.key) && slot.accepts.includes(position));
    if (eligibleStarter) {
      assignments.set(eligibleStarter.key, pick);
      continue;
    }
    const openBench = rosterSlotDefinitions.find((slot) => slot.area === "bench" && !assignments.has(slot.key));
    if (openBench) assignments.set(openBench.key, pick);
  }
  return assignments;
};

export const getDraftablePositionsForRosterPicks = (picks: DraftBoardPick[]) => {
  const assignments = assignRosterSlots(picks);
  const positions = new Set<string>();
  for (const slot of rosterSlotDefinitions) {
    if (slot.area === "ir" || assignments.has(slot.key)) continue;
    slot.accepts.forEach((position) => positions.add(position));
  }
  return positions;
};

export function DraftRoomBoard({
  state,
  searchQuery,
  onSearchChange,
  onDraftPlayer,
  onQueuePlayer,
  queuedPlayerIds: controlledQueuedPlayerIds,
  onQueuedPlayerIdsChange,
  onSelectPlayer,
  draftPending,
  autoPickPending,
  error,
  onExit,
  onEmailHistory,
  onSkipEmail,
  onCopyHistory,
  onReset,
  showCompletionModal,
  completionChoiceMade = false,
  emailPending = false,
  exitPending = false,
  emailError = null,
  historyTextAvailable = false,
}: {
  state: DraftBoardState;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onDraftPlayer: (playerId: number) => void;
  onQueuePlayer?: (playerId: number) => void;
  queuedPlayerIds?: number[];
  onQueuedPlayerIdsChange?: (playerIds: number[]) => void;
  onSelectPlayer?: (player: DraftBoardPlayer) => void;
  draftPending: boolean;
  autoPickPending: boolean;
  error?: string | null;
  onExit?: () => void;
  onEmailHistory?: () => void;
  onSkipEmail?: () => void;
  onCopyHistory?: () => void;
  onReset?: () => void;
  showCompletionModal: boolean;
  completionChoiceMade?: boolean;
  emailPending?: boolean;
  exitPending?: boolean;
  emailError?: string | null;
  historyTextAvailable?: boolean;
}) {
  const [activeTab, setActiveTab] = useState<DraftBoardActiveTab>("draft");
  const [internalQueuedPlayerIds, setInternalQueuedPlayerIds] = useState<number[]>([]);
  const [selectedRosterParticipantId, setSelectedRosterParticipantId] = useState<string | null>(null);
  const queuedPlayerIds = controlledQueuedPlayerIds ?? internalQueuedPlayerIds;
  const setQueuedPlayerIds = (updater: (current: number[]) => number[]) => {
    const next = updater(queuedPlayerIds);
    if (controlledQueuedPlayerIds === undefined) {
      setInternalQueuedPlayerIds(next);
    }
    onQueuedPlayerIdsChange?.(next);
  };
  const queuedPlayerIdSet = useMemo(() => new Set(queuedPlayerIds), [queuedPlayerIds]);
  const playerById = useMemo(() => new Map(state.availablePlayers.map((player) => [player.id, player])), [state.availablePlayers]);
  const queuedPlayers = useMemo(
    () => queuedPlayerIds.map((playerId) => playerById.get(playerId)).filter((player): player is DraftBoardPlayer => Boolean(player)),
    [playerById, queuedPlayerIds]
  );
  const historyRounds = useMemo(() => {
    const rounds = new Map<number, typeof state.picks>();
    state.picks.forEach((pick) => {
      const existing = rounds.get(pick.roundNumber) ?? [];
      existing.push(pick);
      rounds.set(pick.roundNumber, existing);
    });
    return [...rounds.entries()].sort(([a], [b]) => a - b);
  }, [state.picks]);
  const rosterOptions = state.rosters ?? [];
  const selectedRoster = useMemo(() => {
    if (rosterOptions.length === 0) return null;
    const selectedId = selectedRosterParticipantId ? Number(selectedRosterParticipantId) : null;
    const userParticipantId = state.participants.find((participant) => participant.isUser)?.id ?? null;
    return (
      rosterOptions.find((roster) => roster.participantId === selectedId) ??
      rosterOptions.find((roster) => roster.participantId === userParticipantId) ??
      rosterOptions[0]
    );
  }, [rosterOptions, selectedRosterParticipantId, state.participants]);
  const selectedRosterValue = selectedRoster ? String(selectedRoster.participantId) : "";
  const selectedRosterAssignments = useMemo(() => assignRosterSlots(selectedRoster?.picks ?? []), [selectedRoster?.picks]);
  const selectedRosterPicksMade = selectedRoster?.picks.length ?? 0;
  const userRosterPicks = state.userRoster ?? [];
  const userDraftablePositions = useMemo(() => getDraftablePositionsForRosterPicks(userRosterPicks), [userRosterPicks]);
  const draftableAvailablePlayers = useMemo(
    () => state.availablePlayers.filter((player) => userDraftablePositions.has(normalizeRosterPosition(player.position))),
    [state.availablePlayers, userDraftablePositions]
  );
  const isPlayerDraftableForUserRoster = (player: DraftBoardPlayer) => userDraftablePositions.has(normalizeRosterPosition(player.position));

  const queuePlayer = (playerId: number) => {
    setQueuedPlayerIds((current) => (current.includes(playerId) ? current : [...current, playerId]));
    onQueuePlayer?.(playerId);
    setActiveTab("queue");
  };

  const removeQueuedPlayer = (playerId: number) => {
    setQueuedPlayerIds((current) => current.filter((id) => id !== playerId));
  };

  return (
    <div data-testid="draft-room-board" className="relative mx-auto max-w-[1800px] space-y-6 pb-28 pt-4">
      <div className="pointer-events-none absolute -left-24 top-12 h-72 w-72 rounded-full bg-primary/10 blur-[100px]" />
      <div className="pointer-events-none absolute right-10 top-40 h-80 w-80 rounded-full bg-blue-500/10 blur-[120px]" />
      {onExit ? (
        <div className="relative z-20 flex justify-start">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-12 w-12 rounded-2xl border-cyan-200/20 bg-slate-950/70 text-cyan-100 shadow-[0_0_28px_rgba(34,211,238,0.16)] backdrop-blur-xl hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white"
            aria-label="Exit draft room to Draft tab"
            title="Exit to Draft tab"
            onClick={onExit}
            disabled={exitPending}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </div>
      ) : null}

      <DraftCompleteModal
        open={showCompletionModal}
        choiceMade={completionChoiceMade}
        emailPending={emailPending}
        exitPending={exitPending}
        emailError={emailError}
        historyTextAvailable={historyTextAvailable}
        onSendEmail={onEmailHistory ?? (() => undefined)}
        onSkipEmail={onSkipEmail ?? (() => undefined)}
        onCopyHistory={onCopyHistory}
        onReset={onReset}
        onExit={onExit ?? (() => undefined)}
      />

      <DraftStatusHeader state={state} />

      {error ? (
        <div className="rounded-2xl border border-red-300/20 bg-red-400/10 p-4 text-sm font-bold text-red-100">
          <AlertCircle className="mr-2 inline h-4 w-4" /> {error}
        </div>
      ) : null}

      {state.lastPick ? (
        <div className="mx-auto flex w-fit items-center rounded-full border border-cyan-300/15 bg-cyan-400/10 px-5 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100">
          Last pick&nbsp;<span className="text-white">{state.lastPick.playerName}</span>&nbsp;to {state.lastPick.teamName}
        </div>
      ) : null}

      <DraftOrderPanel
        participants={state.participants}
        picks={state.picks}
        currentOverallPick={state.currentOverallPick}
        totalPicks={state.totalPicks}
      />

      {activeTab === "draft" ? (
        <AvailablePlayersTable
          players={draftableAvailablePlayers}
          searchQuery={searchQuery}
          onSearchChange={onSearchChange}
          onDraftPlayer={onDraftPlayer}
          onQueuePlayer={queuePlayer}
          onSelectPlayer={onSelectPlayer}
          queuedPlayerIds={queuedPlayerIdSet}
          draftPending={draftPending}
          autoPickPending={autoPickPending}
          canDraft={state.isUserOnClock && !state.isComplete}
        />
      ) : null}

      {activeTab === "queue" ? (
        <Card className="rounded-[2rem] border-white/10 bg-card/45">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Queue</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-4">
            {queuedPlayers.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-8 text-center text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                No queued players yet. Use Queue on the Draft tab.
              </div>
            ) : (
              queuedPlayers.map((player) => (
                <div key={player.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-foreground">#{player.rank} • {player.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                      {player.position} • {player.school} • {typeof player.projection === "number" ? player.projection.toFixed(1) : "--"} proj
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="h-10 rounded-2xl px-4 text-[10px] font-black uppercase tracking-[0.14em]"
                      onClick={() => removeQueuedPlayer(player.id)}
                    >
                      Remove
                    </Button>
                    <Button
                      className="h-10 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 px-5 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950"
                      disabled={!state.isUserOnClock || state.isComplete || draftPending || autoPickPending || player.disabled || !isPlayerDraftableForUserRoster(player)}
                      onClick={() => onDraftPlayer(player.id)}
                    >
                      {draftPending ? "Drafting..." : "Draft"}
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}

      {activeTab === "roster" ? (
        <RosterTab
          rosterOptions={rosterOptions}
          selectedRoster={selectedRoster}
          selectedRosterValue={selectedRosterValue}
          selectedRosterAssignments={selectedRosterAssignments}
          selectedRosterPicksMade={selectedRosterPicksMade}
          onSelectRoster={setSelectedRosterParticipantId}
        />
      ) : null}

      {activeTab === "history" ? (
        <Card className="rounded-[2rem] border-white/10 bg-card/45">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Draft History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 p-4">
            {historyRounds.length === 0 ? (
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">No picks yet.</p>
            ) : (
              historyRounds.map(([roundNumber, picks]) => (
                <div key={roundNumber} className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Round {roundNumber}</p>
                  <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                    {picks
                      .slice()
                      .sort((a, b) => a.roundPick - b.roundPick)
                      .map((pick) => (
                        <div key={pick.id} className="rounded-xl border border-white/10 bg-slate-950/25 p-3">
                          <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">{pick.roundNumber}.{pick.roundPick} • {pick.teamName}</p>
                          <p className="mt-1 truncate font-black text-foreground">{pick.playerName}</p>
                          <p className="mt-1 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground">{pick.playerPosition} • {pick.playerSchool}</p>
                        </div>
                      ))}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}

      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[1200] flex justify-center px-4">
        <div className="pointer-events-auto grid w-full max-w-xl grid-cols-4 rounded-2xl border border-cyan-200/15 bg-slate-950/88 p-1 shadow-[0_0_40px_rgba(34,211,238,0.16)] backdrop-blur-xl">
          {draftBoardTabs.map((tab) => (
            <button
              key={tab.value}
              type="button"
              className={`rounded-xl px-3 py-3 text-[10px] font-black uppercase tracking-[0.16em] transition-all ${
                activeTab === tab.value ? "bg-cyan-300 text-slate-950 shadow-[0_0_20px_rgba(34,211,238,0.28)]" : "text-cyan-100/70 hover:bg-white/10 hover:text-white"
              }`}
              onClick={() => setActiveTab(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function RosterTab({
  rosterOptions,
  selectedRoster,
  selectedRosterValue,
  selectedRosterAssignments,
  selectedRosterPicksMade,
  onSelectRoster,
}: {
  rosterOptions: DraftBoardRoster[];
  selectedRoster: DraftBoardRoster | null;
  selectedRosterValue: string;
  selectedRosterAssignments: Map<string, DraftBoardPick>;
  selectedRosterPicksMade: number;
  onSelectRoster: (participantId: string) => void;
}) {
  const starterSlots = rosterSlotDefinitions.filter((slot) => slot.area === "starter");
  const benchSlots = rosterSlotDefinitions.filter((slot) => slot.area === "bench");
  const irSlot = rosterSlotDefinitions.find((slot) => slot.area === "ir");

  return (
    <Card className="relative overflow-hidden rounded-[2rem] border-cyan-200/10 bg-[#071224] shadow-[0_24px_80px_rgba(8,13,30,0.45)]">
      <div className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-cyan-300/[0.04] blur-[110px]" />
      <div className="pointer-events-none absolute right-10 top-36 h-80 w-80 rounded-full bg-blue-500/[0.04] blur-[130px]" />
      <CardHeader className="relative border-b border-white/10">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Roster</CardTitle>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
              {selectedRoster ? `${selectedRosterPicksMade}/13 slots filled • ${selectedRoster.participantName}` : "Select a team roster"}
            </p>
          </div>
          <div className="w-full lg:w-72">
            <Select value={selectedRosterValue} onValueChange={onSelectRoster}>
              <SelectTrigger className="h-12 rounded-2xl border-cyan-200/20 bg-slate-950/55 text-[11px] font-black uppercase tracking-[0.16em] text-cyan-50">
                <SelectValue placeholder="Select Team" />
              </SelectTrigger>
              <SelectContent className="border-cyan-200/15 bg-slate-950/95">
                {rosterOptions.map((roster) => (
                  <SelectItem key={roster.participantId} value={String(roster.participantId)} className="text-[11px] font-black uppercase tracking-[0.12em]">
                    {roster.teamName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent className="relative space-y-6 p-5 lg:p-6">
        {selectedRoster ? (
          <>
            <div className="rounded-[1.75rem] border border-white/10 bg-[#081326] p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100/80">Starters</p>
                <div className="h-px flex-1 border-t border-dashed border-cyan-200/15" />
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {starterSlots.map((slot) => (
                  <RosterSlotCard key={slot.key} slot={slot} pick={selectedRosterAssignments.get(slot.key)} />
                ))}
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-white/10 bg-[#081326] p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">Bench / Reserve</p>
                <div className="h-px flex-1 border-t border-dashed border-white/15" />
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {benchSlots.map((slot) => (
                  <RosterSlotCard key={slot.key} slot={slot} pick={selectedRosterAssignments.get(slot.key)} />
                ))}
                {irSlot ? <RosterSlotCard slot={irSlot} pick={selectedRosterAssignments.get(irSlot.key)} /> : null}
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-8 text-center text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
            No rosters available yet.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RosterSlotCard({ slot, pick }: { slot: RosterSlotDefinition; pick?: DraftBoardPick }) {
  const slotPosition = normalizeRosterPosition(pick?.playerPosition) || (slot.key.startsWith("RB") ? "RB" : slot.key.startsWith("WR") ? "WR" : slot.key === "FLEX" ? "WR" : slot.key === "IR" ? "EMPTY" : slot.accepts[0] ?? "EMPTY");
  const styles = rosterPositionStyles[pick ? slotPosition : slotPosition] ?? rosterPositionStyles.EMPTY;
  return (
    <div className={`relative min-h-[92px] overflow-hidden rounded-[1.35rem] border p-4 ${styles.border} ${styles.bg} ${styles.glow}`}>
      <div className={`pointer-events-none absolute -right-8 -top-10 h-24 w-24 rounded-full ${styles.dot} opacity-[0.06] blur-2xl`} />
      <div className="relative flex h-full flex-col justify-between gap-3">
        <div className="flex items-center justify-between gap-3">
          <p className={`text-[10px] font-black uppercase tracking-[0.2em] ${styles.text}`}>{slot.label}</p>
          <span className={`h-2.5 w-2.5 rounded-full ${pick ? styles.dot : "bg-white/20"} shadow-[0_0_16px_currentColor]`} />
        </div>
        <div className="min-w-0">
          <p className={`truncate text-base font-black ${pick ? "text-foreground" : "text-muted-foreground"}`}>
            {pick?.playerName ?? "Open Slot"}
          </p>
          <p className="mt-1 truncate text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
            {pick ? `${pick.playerSchool} • ${pick.roundNumber}.${pick.roundPick}` : slot.area === "ir" ? "Injury reserve" : "Waiting for pick"}
          </p>
        </div>
      </div>
    </div>
  );
}
