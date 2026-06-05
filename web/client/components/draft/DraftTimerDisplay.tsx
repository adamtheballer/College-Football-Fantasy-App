export function DraftTimerDisplay({ formattedTime, status, isComplete }: { formattedTime: string; status: string; isComplete: boolean }) {
  const isPreDraft = status === "intermission";
  const statusLabel = isComplete ? "Complete" : isPreDraft ? "Starts In" : status;
  return (
    <div
      data-testid="draft-timer"
      className={`flex w-full min-w-0 rounded-[1.5rem] border border-cyan-300/20 bg-slate-950/45 px-6 py-5 shadow-[0_0_40px_rgba(34,211,238,0.08)] sm:w-auto sm:min-w-[300px] ${
        isPreDraft ? "flex-col items-center justify-center gap-2 text-center" : "items-center justify-between gap-6"
      }`}
    >
      <p className={`font-black uppercase text-cyan-200 ${isPreDraft ? "text-[10px] tracking-[0.24em]" : "text-[10px] tracking-[0.18em]"}`}>{statusLabel}</p>
      <p className={`whitespace-nowrap font-black tabular-nums tracking-tight text-white ${isPreDraft ? "text-5xl" : "text-4xl"}`}>{isComplete ? "--:--" : formattedTime}</p>
    </div>
  );
}
