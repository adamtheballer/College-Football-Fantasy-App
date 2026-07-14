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
    <div className="grid w-full grid-cols-2 gap-2 rounded-2xl border border-cfb-border-subtle bg-cfb-surface-raised/85 p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_18px_44px_rgba(2,6,23,0.24)] sm:grid-cols-4 lg:min-w-[520px]">
      <button
        type="button"
        onClick={() => onChange(Math.max(displayedWeek - 1, 1))}
        className="flex items-center justify-center rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-secondary transition hover:border-cfb-brand/30 hover:bg-cfb-brand/[0.08] hover:text-cfb-text-primary"
      >
        Prev
      </button>
      <div className="flex items-center justify-center rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 px-4 py-2 text-center text-[11px] font-black text-cfb-text-primary">
        Week {displayedWeek}
      </div>
      <button
        type="button"
        onClick={() => onChange(displayedWeek + 1)}
        className="flex items-center justify-center rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-secondary transition hover:border-cfb-brand/30 hover:bg-cfb-brand/[0.08] hover:text-cfb-text-primary"
      >
        Next
      </button>
      <button
        type="button"
        onClick={() => onChange(null)}
        className="flex items-center justify-center rounded-xl border border-cfb-brand/40 bg-cfb-brand/[0.14] px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-blue-100 transition hover:border-cfb-brand/60 hover:bg-cfb-brand/20 hover:text-blue-50"
      >
        Auto
      </button>
    </div>
  );
}
