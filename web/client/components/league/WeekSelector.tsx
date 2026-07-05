export function WeekSelector({
  week,
  selectedWeek,
  onChange,
}: {
  week?: number | null;
  selectedWeek?: number | null;
  onChange: (week: number | null) => void;
}) {
  const displayedWeek = selectedWeek ?? week ?? 1;

  return (
    <div className="grid w-full grid-cols-2 gap-2 rounded-[1.25rem] border border-sky-300/15 bg-[linear-gradient(135deg,rgba(7,20,38,0.88),rgba(12,29,54,0.72))] p-2 shadow-[inset_0_1px_0_rgba(125,211,252,0.10),0_18px_50px_rgba(14,165,233,0.08)] sm:grid-cols-4 lg:min-w-[520px]">
      <button
        type="button"
        onClick={() => onChange(Math.max(displayedWeek - 1, 1))}
        className="flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-200 transition hover:border-sky-300/20 hover:bg-sky-300/[0.06] hover:text-slate-50"
      >
        Prev
      </button>
      <div className="flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-center text-[11px] font-black text-slate-50">
        Week {displayedWeek}
      </div>
      <button
        type="button"
        onClick={() => onChange(displayedWeek + 1)}
        className="flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-200 transition hover:border-sky-300/20 hover:bg-sky-300/[0.06] hover:text-slate-50"
      >
        Next
      </button>
      <button
        type="button"
        onClick={() => onChange(null)}
        className="flex items-center justify-center rounded-xl border border-sky-300/30 bg-sky-400/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-sky-200 transition hover:border-sky-200/50 hover:bg-sky-300/[0.14] hover:text-sky-50"
      >
        Auto
      </button>
    </div>
  );
}
