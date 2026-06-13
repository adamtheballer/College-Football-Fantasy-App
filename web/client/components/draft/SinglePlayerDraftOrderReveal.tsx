import { ArrowLeft, Bot, Shuffle, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { DraftBoardParticipant } from "@/types/draft-board";

export function SinglePlayerDraftOrderReveal({
  participants,
  formattedTime,
  onContinue,
  onExit,
}: {
  participants: DraftBoardParticipant[];
  formattedTime: string;
  onContinue: () => void;
  onExit: () => void;
}) {
  const ordered = [...participants].sort((a, b) => Number(a.draftPosition ?? 999) - Number(b.draftPosition ?? 999));

  return (
    <div className="relative mx-auto max-w-[1800px] space-y-6 px-6 pb-10 pt-6">
      <div className="pointer-events-none absolute -left-24 top-12 h-72 w-72 rounded-full bg-primary/10 blur-[100px]" />
      <div className="pointer-events-none absolute right-10 top-40 h-80 w-80 rounded-full bg-blue-500/10 blur-[120px]" />

      <Card className="relative overflow-hidden rounded-[2.75rem] border-cyan-200/10 bg-card/55">
        <Button
          variant="outline"
          size="icon"
          className="absolute left-6 top-6 z-20 h-12 w-12 rounded-2xl border-cyan-200/20 bg-slate-950/45 text-cyan-100 hover:bg-cyan-400/10 hover:text-white"
          aria-label="Exit pre-draft room"
          onClick={onExit}
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-cyan-300/12 blur-[90px]" />
        <div className="pointer-events-none absolute -bottom-28 left-10 h-72 w-96 rounded-full bg-blue-500/10 blur-[100px]" />
        <CardContent className="relative flex flex-col gap-8 p-6 pt-24 md:p-8 md:pt-24 xl:flex-row xl:items-center xl:justify-between">
          <div className="max-w-4xl space-y-5">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2">
              <Shuffle className="h-3.5 w-3.5 text-cyan-100" />
              <span className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">Randomized Draft Order</span>
            </div>
            <div>
              <h1 className="text-4xl font-black italic uppercase tracking-tight text-foreground md:text-6xl">
                Single-Player Draft Order
              </h1>
              <p className="mt-3 text-[11px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                Bots are filled, draft order is locked, and the draft room countdown is ready.
              </p>
            </div>
            <Button
              className="h-14 rounded-2xl bg-primary px-8 text-[11px] font-black uppercase tracking-[0.2em] text-primary-foreground"
              onClick={onContinue}
            >
              Continue to Draft
            </Button>
          </div>

          <div className="flex w-full min-w-0 items-center justify-between gap-6 rounded-[1.5rem] border border-cyan-300/20 bg-slate-950/45 px-6 py-5 shadow-[0_0_40px_rgba(34,211,238,0.08)] sm:w-auto sm:min-w-[320px]">
            <div className="min-w-0">
              <p className="text-[9px] font-black uppercase tracking-[0.24em] text-muted-foreground">Draft Starts In:</p>
            </div>
            <div className="min-w-[132px] shrink-0 text-right">
              <p className="whitespace-nowrap text-4xl font-black tabular-nums tracking-tight text-white">{formattedTime}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {ordered.map((participant) => (
          <div
            key={participant.id}
            className={`rounded-[1.5rem] border p-5 ${
              participant.isUser ? "border-primary/60 bg-primary/15 shadow-[0_0_32px_rgba(34,211,238,0.16)]" : "border-white/10 bg-white/[0.035]"
            }`}
          >
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">Pick {participant.draftPosition ?? "--"}</p>
            <p className="mt-2 truncate text-lg font-black text-foreground">{participant.teamName}</p>
            <p className="mt-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.16em] text-cyan-100/85">
              {participant.participantType === "bot" ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
              {participant.name}{participant.isUser ? " • You" : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
