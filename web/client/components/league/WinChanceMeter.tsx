function meterClass(percent: number) {
  if (percent >= 60) return "from-cfb-success via-cfb-cyan to-cfb-brand";
  if (percent >= 45) return "from-cfb-gold via-cfb-cyan to-cfb-brand";
  return "from-cfb-pink via-cfb-danger to-cfb-gold";
}

function validProbability(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 5 && value <= 95;
}

function formatDisplayedProbabilityPair(left: number, right: number) {
  // Round one side only, then derive its complement. This prevents a pair of
  // independently rounded values from visibly totaling 99.9% or 100.1%.
  const displayedLeft = Math.round((left + Number.EPSILON) * 10) / 10;
  const displayedRight = Math.round((100 - displayedLeft + Number.EPSILON) * 10) / 10;
  return { left: displayedLeft, right: displayedRight };
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
  const hasWinChance =
    validProbability(myPercent) &&
    validProbability(opponentPercent) &&
    Math.abs(myPercent + opponentPercent - 100) < 0.000001;
  const leftProbability = hasWinChance ? Number(myPercent) : 0;
  const rightProbability = hasWinChance ? Number(opponentPercent) : 0;
  const displayedWinChance = hasWinChance
    ? formatDisplayedProbabilityPair(leftProbability, rightProbability)
    : null;
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
              {displayedWinChance
                ? `${displayedWinChance.left.toFixed(1)}% / ${displayedWinChance.right.toFixed(1)}%`
                : "Unavailable"}
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
            {displayedWinChance
              ? `${displayedWinChance.left.toFixed(1)}% / ${displayedWinChance.right.toFixed(1)}%`
              : "Unavailable"}
          </p>
        </div>
      )}
      {hasWinChance ? (
        <div
          aria-label={`Win chance: ${displayedWinChance?.left.toFixed(1)}% to ${displayedWinChance?.right.toFixed(1)}%`}
          className="flex h-5 overflow-hidden rounded-full border border-cfb-border-subtle bg-cfb-canvas shadow-[inset_0_1px_8px_rgba(2,6,23,0.85)]"
          role="img"
        >
          <div
            className={`h-full shrink-0 bg-gradient-to-r ${meterClass(leftProbability)} shadow-[0_0_26px_hsl(var(--brand-primary)/0.24)] transition-[width] duration-500`}
            data-testid="win-chance-left-bar"
            style={{ width: `${leftProbability}%` }}
          />
          <div
            className="h-full shrink-0 bg-gradient-to-r from-cfb-pink via-cfb-danger to-cfb-gold transition-[width] duration-500"
            data-testid="win-chance-right-bar"
            style={{ width: `${rightProbability}%` }}
          />
        </div>
      ) : (
        <p className="text-center text-xs font-bold text-cfb-text-muted">Win chance unavailable</p>
      )}
    </div>
  );
}

export { formatDisplayedProbabilityPair };
