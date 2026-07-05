function meterClass(percent: number) {
  if (percent >= 60) return "from-emerald-300 via-sky-300 to-blue-400";
  if (percent >= 45) return "from-yellow-300 via-amber-300 to-sky-300";
  return "from-rose-400 via-orange-400 to-amber-300";
}

export function WinChanceMeter({
  myPercent,
  opponentPercent,
}: {
  myPercent?: number | null;
  opponentPercent?: number | null;
}) {
  const safeMyPercent = Math.min(99, Math.max(1, Number(myPercent ?? 50)));
  const safeOpponentPercent = Number(
    opponentPercent ?? Math.round((100 - safeMyPercent) * 10) / 10
  );

  return (
    <div className="space-y-3 rounded-[1.25rem] border border-sky-300/10 bg-slate-950/35 p-4">
      <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
        <span>Win Chance</span>
        <span>
          {safeMyPercent.toFixed(1)}% / {safeOpponentPercent.toFixed(1)}%
        </span>
      </div>
      <div className="h-5 overflow-hidden rounded-full border border-sky-300/15 bg-slate-950 shadow-[inset_0_1px_8px_rgba(2,6,23,0.85)]">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${meterClass(safeMyPercent)} shadow-[0_0_26px_rgba(56,189,248,0.32)] transition-all duration-500`}
          style={{ width: `${safeMyPercent}%` }}
        />
      </div>
    </div>
  );
}
