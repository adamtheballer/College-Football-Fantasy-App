function meterClass(percent: number) {
  if (percent >= 60) return "from-cfb-success via-cfb-cyan to-cfb-brand";
  if (percent >= 45) return "from-cfb-gold via-cfb-cyan to-cfb-brand";
  return "from-cfb-pink via-cfb-danger to-cfb-gold";
}

export function WinChanceMeter({
  myPercent,
  opponentPercent,
  myProjectedTotal,
  opponentProjectedTotal,
}: {
  myPercent?: number | null;
  opponentPercent?: number | null;
  myProjectedTotal?: number | null;
  opponentProjectedTotal?: number | null;
}) {
  const safeMyPercent = Math.min(99, Math.max(1, Number(myPercent ?? 50)));
  const safeOpponentPercent = Number(
    opponentPercent ?? Math.round((100 - safeMyPercent) * 10) / 10
  );
  const formattedMyProjection =
    typeof myProjectedTotal === "number" && Number.isFinite(myProjectedTotal)
      ? myProjectedTotal.toFixed(1)
      : "—";
  const formattedOpponentProjection =
    typeof opponentProjectedTotal === "number" && Number.isFinite(opponentProjectedTotal)
      ? opponentProjectedTotal.toFixed(1)
      : "—";
  const hasProjectedTotals =
    typeof myProjectedTotal === "number" ||
    typeof opponentProjectedTotal === "number";

  return (
    <div className="space-y-3 rounded-2xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
      {hasProjectedTotals ? (
        <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-3 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
          <div className="text-left">
            <p>My Projection</p>
            <p className="mt-1 text-base font-black tracking-normal text-cfb-brand">{formattedMyProjection}</p>
          </div>
          <div className="text-center">
            <p>Win Chance</p>
            <p className="mt-1 whitespace-nowrap text-[11px] tracking-[0.12em] text-cfb-text-secondary">
              {safeMyPercent.toFixed(1)}% / {safeOpponentPercent.toFixed(1)}%
            </p>
          </div>
          <div className="text-right">
            <p>Their Projection</p>
            <p className="mt-1 text-base font-black tracking-normal text-cfb-pink">{formattedOpponentProjection}</p>
          </div>
        </div>
      ) : (
        <div className="text-center text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
          <p>Win Chance</p>
          <p className="mt-1 whitespace-nowrap text-[11px] tracking-[0.12em] text-cfb-text-secondary">
            {safeMyPercent.toFixed(1)}% / {safeOpponentPercent.toFixed(1)}%
          </p>
        </div>
      )}
      <div className="h-5 overflow-hidden rounded-full border border-cfb-border-subtle bg-cfb-canvas shadow-[inset_0_1px_8px_rgba(2,6,23,0.85)]">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${meterClass(safeMyPercent)} shadow-[0_0_26px_hsl(var(--brand-primary)/0.24)] transition-all duration-500`}
          style={{ width: `${safeMyPercent}%` }}
        />
      </div>
    </div>
  );
}
