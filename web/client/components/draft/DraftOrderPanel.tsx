import { useEffect, useRef } from "react";
import { Bot, Check, User } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DraftBoardParticipant, DraftBoardPick } from "@/types/draft-board";

const getParticipantForOverallPick = (
  orderedParticipants: DraftBoardParticipant[],
  overallPick: number
) => {
  if (orderedParticipants.length === 0) return null;
  const roundIndex = Math.floor((overallPick - 1) / orderedParticipants.length);
  const pickIndex = (overallPick - 1) % orderedParticipants.length;
  const snakeIndex = roundIndex % 2 === 0 ? pickIndex : orderedParticipants.length - 1 - pickIndex;
  return orderedParticipants[snakeIndex] ?? null;
};

export function DraftOrderPanel({
  participants,
  picks,
  currentOverallPick,
  totalPicks,
}: {
  participants: DraftBoardParticipant[];
  picks: DraftBoardPick[];
  currentOverallPick: number;
  totalPicks: number;
}) {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const currentPickRef = useRef<HTMLDivElement | null>(null);
  const ordered = [...participants].sort((a, b) => Number(a.draftPosition ?? 999) - Number(b.draftPosition ?? 999));
  const picksByOverallPick = new Map(picks.map((pick) => [pick.overallPick, pick]));
  const picksMade = Math.max(0, Math.min(totalPicks, picks.length));
  const progressPercent = totalPicks > 0 ? Math.min(100, Math.max(0, (picksMade / totalPicks) * 100)) : 0;
  const pickSlots = Array.from({ length: Math.max(0, totalPicks) }, (_, index) => {
    const overallPick = index + 1;
    const participant = getParticipantForOverallPick(ordered, overallPick);
    const roundNumber = ordered.length > 0 ? Math.floor(index / ordered.length) + 1 : 1;
    const roundPick = ordered.length > 0 ? (index % ordered.length) + 1 : overallPick;
    return {
      overallPick,
      roundNumber,
      roundPick,
      participant,
      madePick: picksByOverallPick.get(overallPick) ?? null,
      isCurrent: overallPick === currentOverallPick,
    };
  });

  useEffect(() => {
    const currentPickElement = currentPickRef.current;
    const scrollContainer = scrollContainerRef.current;
    if (!currentPickElement || !scrollContainer) return;

    const targetLeft =
      currentPickElement.offsetLeft -
      (scrollContainer.clientWidth - currentPickElement.clientWidth) / 2;
    const maxScrollLeft = scrollContainer.scrollWidth - scrollContainer.clientWidth;
    const nextScrollLeft = Math.max(0, Math.min(targetLeft, maxScrollLeft));

    scrollContainer.scrollTo({
      left: nextScrollLeft,
      behavior: "smooth",
    });
  }, [currentOverallPick]);

  return (
    <Card data-testid="draft-order-panel" className="relative overflow-hidden rounded-[2rem] border-cyan-200/10 bg-card/55 shadow-[0_24px_80px_rgba(8,13,30,0.45)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_0%,rgba(34,211,238,0.12),transparent_30%),radial-gradient(circle_at_88%_10%,rgba(59,130,246,0.09),transparent_28%)]" />
      <div className="pointer-events-none absolute left-8 right-8 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/30 to-transparent" />
      <CardHeader className="relative border-b border-white/10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Draft Order</CardTitle>
            <p className="mt-1 text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">
              Scroll every pick left to right
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/80">
              {totalPicks} picks
            </p>
            <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              {picksMade} locked
            </p>
          </div>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full border border-cyan-200/10 bg-slate-950/35">
          <div
            className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-400 to-violet-400 shadow-[0_0_18px_rgba(34,211,238,0.45)] transition-all duration-700"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </CardHeader>
      <CardContent className="relative overflow-hidden p-0">
        <div className="pointer-events-none absolute bottom-0 left-0 top-0 z-10 w-16 bg-gradient-to-r from-card/95 to-transparent" />
        <div className="pointer-events-none absolute bottom-0 right-0 top-0 z-10 w-16 bg-gradient-to-l from-card/95 to-transparent" />
        <div ref={scrollContainerRef} className="overflow-x-auto p-4" style={{ scrollbarWidth: "thin" }}>
        <div className="flex min-w-max gap-3 pb-1">
        {pickSlots.map((slot) => {
          const participant = slot.participant;
          const isUserPick = Boolean(participant?.isUser);
          const isBotPick = participant?.participantType === "bot";
          const isMade = Boolean(slot.madePick);
          return (
          <div
            key={slot.overallPick}
            ref={slot.isCurrent ? currentPickRef : undefined}
            className={`relative flex h-36 w-36 shrink-0 flex-col justify-between overflow-hidden rounded-[1.4rem] border p-4 transition-all ${
              slot.isCurrent
                ? "scale-[1.02] border-cyan-300/75 bg-cyan-400/18 shadow-[0_0_30px_rgba(34,211,238,0.28)]"
                : isUserPick
                  ? "border-cyan-300/35 bg-cyan-400/[0.09] shadow-[0_0_22px_rgba(34,211,238,0.08)]"
                  : isMade
                    ? "border-emerald-300/20 bg-emerald-400/[0.06]"
                    : "border-white/10 bg-white/[0.04]"
            }`}
            title={participant?.teamName ?? `Pick ${slot.overallPick}`}
          >
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.05] via-transparent to-cyan-300/[0.04]" />
            <div className="pointer-events-none absolute -right-8 -top-8 h-20 w-20 rounded-full bg-cyan-300/10 blur-2xl" />
            {slot.isCurrent ? (
              <span className="absolute right-3 top-3 h-2.5 w-2.5 rounded-full bg-cyan-200 shadow-[0_0_14px_rgba(103,232,249,0.95)] animate-pulse" />
            ) : null}
            <div className="relative">
              <p className="text-[8px] font-black uppercase tracking-[0.2em] text-muted-foreground">Pick {slot.overallPick}</p>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-cyan-100/85">
                {slot.roundNumber}.{slot.roundPick}
              </p>
            </div>
            <div className="relative">
              <div className={`mb-2 flex h-9 w-9 items-center justify-center rounded-xl border ${
                isMade ? "border-emerald-300/35 bg-emerald-400/12 text-emerald-100" : "border-white/15 bg-slate-950/35 text-cyan-100"
              }`}>
                {isMade ? <Check className="h-4 w-4" /> : isBotPick ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
              </div>
              <p className="truncate text-sm font-black text-foreground">
                {slot.madePick?.playerName ?? participant?.teamName ?? "TBD"}
              </p>
              <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                {slot.madePick ? slot.madePick.teamName : `${participant?.name ?? "Manager"}${participant?.isUser ? " • You" : ""}`}
              </p>
            </div>
          </div>
          );
        })}
        </div>
        {pickSlots.length === 0 ? (
          <div className="flex min-h-32 items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
            Draft order unavailable.
          </div>
        ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
