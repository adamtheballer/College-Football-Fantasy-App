import { Bot, RadioTower, Sparkles, TimerReset, Trophy, User, Zap } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { DraftBoardState } from "@/types/draft-board";
import { DraftTimerDisplay } from "./DraftTimerDisplay";

export function DraftStatusHeader({ state }: { state: DraftBoardState }) {
  const isPreDraftCountdown = state.status === "intermission" || state.phaseType === "prestart_countdown";
  const picksMade = Math.max(0, Math.min(state.totalPicks, state.picks.length));
  const progressPercent = state.totalPicks > 0 ? Math.min(100, Math.max(0, (picksMade / state.totalPicks) * 100)) : 0;
  const onClockLabel = state.isComplete
    ? "Draft complete"
    : isPreDraftCountdown
      ? "Draft starts after countdown"
    : `On clock: ${state.currentTeamName || state.currentParticipantName || "Waiting"}${state.currentParticipantType === "bot" ? " (Bot)" : ""}`;
  const StatusIcon = isPreDraftCountdown ? TimerReset : state.currentParticipantType === "bot" ? Bot : User;
  return (
    <Card data-testid="draft-status-header" className="relative overflow-hidden rounded-[2.75rem] border-cyan-200/10 bg-card/60 shadow-[0_28px_90px_rgba(15,23,42,0.45)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(103,232,249,0.18),transparent_32%),radial-gradient(circle_at_64%_18%,rgba(59,130,246,0.13),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.045),transparent_42%,rgba(34,211,238,0.05))]" />
      <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-cyan-300/16 blur-[90px]" />
      <div className="pointer-events-none absolute -bottom-28 left-10 h-72 w-96 rounded-full bg-blue-500/14 blur-[100px]" />
      <div className="pointer-events-none absolute left-8 right-8 top-6 h-px bg-gradient-to-r from-transparent via-cyan-200/30 to-transparent" />
      <div className="pointer-events-none absolute bottom-0 left-0 h-1 bg-gradient-to-r from-cyan-300 via-blue-400 to-violet-400 transition-all duration-700" style={{ width: `${progressPercent}%` }} />
      <CardContent className="relative flex flex-col gap-6 p-6 md:p-8 xl:flex-row xl:items-center xl:justify-between">
        <div className="space-y-4">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2">
            <RadioTower className="h-3.5 w-3.5 text-cyan-100" />
            <span className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">Draft Room</span>
          </div>
          <div className="overflow-visible pr-6 md:pr-10">
            <h1 className="max-w-5xl overflow-visible bg-gradient-to-r from-white via-cyan-50 to-cyan-300 bg-clip-text pr-3 text-4xl font-black italic uppercase tracking-tight text-transparent drop-shadow-[0_0_28px_rgba(34,211,238,0.18)] md:pr-5 md:text-6xl">
              {state.title}
            </h1>
            <p className="mt-3 text-[11px] font-black uppercase tracking-[0.22em] text-muted-foreground">{state.subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-cyan-100">
              <StatusIcon className="h-3.5 w-3.5" />
              {onClockLabel}
            </span>
            {state.isUserOnClock ? (
              <span className="rounded-full border border-emerald-300/25 bg-emerald-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-emerald-100">Your pick</span>
            ) : null}
          </div>
          <div className="grid max-w-3xl gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-cyan-200/12 bg-slate-950/25 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
              <div className="flex items-center gap-2 text-cyan-100">
                <Zap className="h-3.5 w-3.5" />
                <span className="text-[8px] font-black uppercase tracking-[0.22em] text-muted-foreground">Picks Made</span>
              </div>
              <p className="mt-2 text-lg font-black text-white tabular-nums">{picksMade}/{state.totalPicks}</p>
            </div>
            <div className="rounded-2xl border border-cyan-200/12 bg-slate-950/25 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
              <div className="flex items-center gap-2 text-cyan-100">
                <Sparkles className="h-3.5 w-3.5" />
                <span className="text-[8px] font-black uppercase tracking-[0.22em] text-muted-foreground">Mode</span>
              </div>
              <p className="mt-2 text-lg font-black uppercase text-white">{state.mode === "single_mock" ? "Solo Mock" : state.mode === "multiplayer_mock" ? "Mock Room" : "League Draft"}</p>
            </div>
            <div className="rounded-2xl border border-cyan-200/12 bg-slate-950/25 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
              <div className="flex items-center gap-2 text-cyan-100">
                <Trophy className="h-3.5 w-3.5" />
                <span className="text-[8px] font-black uppercase tracking-[0.22em] text-muted-foreground">Next Up</span>
              </div>
              <p className="mt-2 truncate text-lg font-black text-white">{state.currentTeamName || state.currentParticipantName || "Waiting"}</p>
            </div>
          </div>
        </div>
        <DraftTimerDisplay formattedTime={state.formattedTime} status={state.status} isComplete={state.isComplete} />
      </CardContent>
    </Card>
  );
}
