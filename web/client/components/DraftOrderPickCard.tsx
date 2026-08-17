import { Bot } from "lucide-react";

import { getDraftedPlayerLastName, getDraftManagerInitials } from "@/lib/draftOrderCarousel";
import { cn } from "@/lib/utils";

type DraftOrderPickCardProps = {
  managerName: string;
  isCpu: boolean;
  round: number;
  roundPick: number;
  playerName?: string | null;
  compact?: boolean;
};

/**
 * Shared order-card content for real and mock drafts. Completed cards reveal
 * the drafted player's compact surname directly beneath the pick number.
 */
export function DraftOrderPickCard({
  managerName,
  isCpu,
  round,
  roundPick,
  playerName,
  compact = false,
}: DraftOrderPickCardProps) {
  const draftedLastName = getDraftedPlayerLastName(playerName);
  const initials = getDraftManagerInitials(managerName, "M");

  return (
    <div className={cn("flex min-w-0 flex-col items-center text-center", compact ? "gap-0.5" : "gap-1.5")}>
      <p className={cn("w-full truncate font-black text-foreground", compact ? "text-[8px] uppercase tracking-[0.04em]" : "text-[11px] tracking-tight")}>
        {managerName}
      </p>
      <span
        aria-label={isCpu ? "Computer manager" : `${managerName} initials ${initials}`}
        className={cn(
          "flex shrink-0 items-center justify-center border border-white/14 bg-black/20 font-black text-amber-100 shadow-[0_0_10px_rgba(103,232,249,0.18)]",
          compact ? "h-6 w-6 rounded-full text-[8px]" : "h-8 w-8 rounded-lg text-[10px]",
        )}
      >
        {isCpu ? <Bot className={compact ? "h-3 w-3" : "h-3.5 w-3.5"} /> : initials}
      </span>
      <p className={cn("whitespace-nowrap font-black tabular-nums text-muted-foreground", compact ? "text-[9px]" : "text-[10px] uppercase tracking-[0.16em]")}>
        ({round}.{roundPick})
      </p>
      <span
        data-testid="draft-order-picked-player"
        aria-live="polite"
        className={cn(
          "min-h-[1em] max-w-full truncate font-black uppercase text-cyan-100",
          compact ? "text-[8px] tracking-[0.04em]" : "text-[9px] tracking-[0.12em]",
          draftedLastName && "animate-in fade-in zoom-in-95 duration-300",
        )}
      >
        {draftedLastName ?? "\u00a0"}
      </span>
    </div>
  );
}
