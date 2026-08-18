import { Grid3X3, LocateFixed, Users } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";

import { Button } from "./ui/button";
import { cn } from "../lib/utils";

export type DraftBoardSlot = {
  overallPick: number;
  round: number;
  roundPick: number;
  teamId: number;
  teamName: string;
  playerName?: string | null;
  playerPosition?: string | null;
  isCurrent: boolean;
  isUser: boolean;
};

export function DraftBoard({
  slots,
  onOpenRosters,
  totalRounds,
  followCurrentPick = false,
}: {
  slots: DraftBoardSlot[];
  onOpenRosters: () => void;
  totalRounds: number;
  /** Keep the active pick visible when the live draft advances. */
  followCurrentPick?: boolean;
}) {
  const teams = Array.from(
    slots
      .reduce(
        (seen, slot) => seen.set(slot.teamId, slot.teamName),
        new Map<number, string>(),
      )
      .entries(),
  );
  const rounds = Array.from({ length: totalRounds }, (_, index) => index + 1);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const currentPickRef = useRef<HTMLDivElement | null>(null);
  const currentPick = slots.find((slot) => slot.isCurrent)?.overallPick ?? null;

  const focusCurrentPick = useCallback((behavior: ScrollBehavior = "smooth") => {
    const container = scrollRef.current;
    const currentCell = currentPickRef.current;
    if (!container || !currentCell) return;

    // The board is intentionally a normal, horizontally-scrollable grid. Do
    // not pin a team or round column; center only the active pick in the
    // board's own scroller so users can always reorient without moving the
    // entire page sideways.
    const left = Math.max(0, currentCell.offsetLeft - (container.clientWidth - currentCell.offsetWidth) / 2);
    if (typeof container.scrollTo === "function") {
      container.scrollTo({ left, behavior });
    } else {
      container.scrollLeft = left;
    }
  }, []);

  useEffect(() => {
    if (!followCurrentPick || !currentPick) return;
    const frame = window.requestAnimationFrame(() => focusCurrentPick("auto"));
    return () => window.cancelAnimationFrame(frame);
  }, [currentPick, focusCurrentPick, followCurrentPick]);

  return (
    <section
      data-testid="draft-board"
      className="overflow-hidden rounded-[1.75rem] border border-sky-100/18 bg-[#08172b]/[0.92] shadow-[0_14px_34px_rgba(2,6,23,0.48)] backdrop-blur-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-4 sm:px-5">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-amber-200">Draft board</p>
          <p className="mt-1 text-[9px] font-bold uppercase tracking-[0.15em] text-muted-foreground">Every pick, live in draft order</p>
        </div>
        <div className="flex items-center gap-1 rounded-xl border border-white/12 bg-black/20 p-1">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-300/15 px-3 py-2 text-[9px] font-black uppercase tracking-[0.12em] text-cyan-50">
            <Grid3X3 className="h-3.5 w-3.5" /> Board
          </span>
          {currentPick ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => focusCurrentPick()}
              className="h-auto rounded-lg px-3 py-2 text-[9px] font-black uppercase tracking-[0.12em] text-amber-100 hover:bg-amber-200/10 hover:text-amber-50"
              aria-label="Center board on the current draft pick"
              title="Center current pick"
            >
              <LocateFixed className="mr-1.5 h-3.5 w-3.5" /> Current
            </Button>
          ) : null}
          <Button type="button" variant="ghost" onClick={onOpenRosters} className="h-auto rounded-lg px-3 py-2 text-[9px] font-black uppercase tracking-[0.12em] text-muted-foreground hover:bg-white/[0.06] hover:text-white">
            <Users className="mr-1.5 h-3.5 w-3.5" /> Rosters
          </Button>
        </div>
      </div>
      <div ref={scrollRef} data-testid="draft-board-scroll" className="overflow-x-auto overscroll-x-contain p-3 sm:p-5">
        <div className="grid min-w-max gap-1.5" style={{ gridTemplateColumns: `4.5rem repeat(${Math.max(1, teams.length)}, minmax(8.5rem, 1fr))` }}>
          <div className="flex items-end px-2 pb-2 text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">Round</div>
          {teams.map(([teamId, teamName]) => {
            const isUser = slots.some((slot) => slot.teamId === teamId && slot.isUser);
            return (
              <div key={teamId} className={cn("min-w-0 border-b px-2 pb-2 text-center text-[9px] font-black uppercase tracking-[0.12em] text-muted-foreground", isUser ? "border-cyan-200/55 text-cyan-100" : "border-white/10")} title={teamName}>
                <span className="block truncate">{isUser ? "Your team" : teamName}</span>
              </div>
            );
          })}
          {rounds.flatMap((round) => {
            const roundSlots = slots.filter((slot) => slot.round === round);
            const byTeam = new Map(roundSlots.map((slot) => [slot.teamId, slot]));
            return [
              <div key={`round-${round}`} className="flex min-h-[5.25rem] items-center px-2 text-sm font-black tabular-nums text-slate-300">{round}</div>,
              ...teams.map(([teamId]) => {
                const slot = byTeam.get(teamId);
                if (!slot) return <div key={`${round}-${teamId}`} className="min-h-[5.25rem] rounded-xl border border-white/5 bg-black/10" />;
                return (
                  <div
                    key={slot.overallPick}
                    ref={slot.isCurrent ? currentPickRef : undefined}
                    aria-current={slot.isCurrent ? "step" : undefined}
                    className={cn("relative min-h-[5.25rem] overflow-hidden rounded-xl border p-2.5 transition", slot.isCurrent ? "border-amber-200/75 bg-amber-300/12 shadow-[0_0_24px_rgba(251,191,36,0.16)]" : slot.isUser ? "border-cyan-200/45 bg-cyan-300/[0.09]" : "border-white/10 bg-black/20")}
                  >
                    <p className="text-[8px] font-black tabular-nums tracking-[0.16em] text-muted-foreground">{slot.round}.{slot.roundPick}</p>
                    <p className="mt-2 truncate text-xs font-black text-white">{slot.playerName ?? "On deck"}</p>
                    <p className="mt-1 truncate text-[8px] font-black uppercase tracking-[0.12em] text-muted-foreground">{slot.playerPosition ?? (slot.isCurrent ? "On the clock" : slot.teamName)}</p>
                  </div>
                );
              }),
            ];
          })}
        </div>
      </div>
    </section>
  );
}
