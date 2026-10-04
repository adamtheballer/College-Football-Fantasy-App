type DraftOrderSlot = {
  overallPick: number;
  isUser: boolean;
};

export type DraftPlayerPickHorizonState = {
  overallPick: number;
  rowIndex: number;
};

/** The next user pick falls after one available player for every pick ahead. */
export function getDraftPlayerPickHorizon(
  slots: DraftOrderSlot[],
  currentPick: number,
): DraftPlayerPickHorizonState | null {
  if (!Number.isInteger(currentPick) || currentPick < 1) return null;

  const nextUserPick = slots.find(
    (slot) => slot.isUser && slot.overallPick >= currentPick,
  );
  if (!nextUserPick) return null;

  return {
    overallPick: nextUserPick.overallPick,
    rowIndex: nextUserPick.overallPick - currentPick,
  };
}

export function DraftPlayerPickHorizon({
  overallPick,
}: {
  overallPick: number;
}) {
  return (
    <div
      data-testid="draft-player-pick-horizon"
      role="status"
      aria-label={`Your next draft pick is pick ${overallPick}`}
      className="flex items-center gap-2 px-3 py-2 sm:px-5"
    >
      <span aria-hidden="true" className="h-px min-w-0 flex-1 bg-cfb-gold/75" />
      <span className="shrink-0 rounded-full border border-cfb-gold/55 bg-cfb-gold/10 px-2.5 py-1 text-[9px] font-black uppercase tracking-[0.12em] text-cfb-gold sm:text-[10px]">
        Your pick #{overallPick}
      </span>
      <span aria-hidden="true" className="h-px min-w-0 flex-1 bg-cfb-gold/75" />
    </div>
  );
}
