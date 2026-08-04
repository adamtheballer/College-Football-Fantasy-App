type TrajectoryPoint = {
  week: number;
  value: number;
  source?: "preseason" | "current" | "published" | "bye";
};

const CHART_WIDTH = 760;
const CHART_HEIGHT = 312;
const PADDING = { top: 24, right: 26, bottom: 46, left: 54 };

const finiteValue = (value: number) => (Number.isFinite(value) ? value : 0);

export function PlayerTrajectoryChart({
  ariaLabel,
  points,
  yLabel,
  yMax,
  valueFormatter,
}: {
  ariaLabel: string;
  points: TrajectoryPoint[];
  yLabel: string;
  yMax: number;
  valueFormatter: (value: number) => string;
}) {
  const ordered = [...points].sort((left, right) => left.week - right.week);
  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;
  const horizontalTicks = yMax === 100 ? [0, 25, 50, 75, 100] : [0, 10, 20, 30];
  const weeks = Array.from({ length: 14 }, (_, index) => index);
  const x = (week: number) => PADDING.left + (week / 13) * plotWidth;
  const y = (value: number) => PADDING.top + (1 - Math.min(finiteValue(value), yMax) / yMax) * plotHeight;
  // Do not visually bridge weeks that have not produced a published snapshot.
  // A preseason card therefore renders one Week 0 dot, not a fictitious line.
  const connectedLine = ordered.reduce((path, point, index) => {
    const previous = ordered[index - 1];
    const command = previous && point.week === previous.week + 1 ? "L" : "M";
    return `${path}${command}${x(point.week)} ${y(point.value)} `;
  }, "");
  const hasConnectedWeeks = ordered.some((point, index) => index > 0 && point.week === ordered[index - 1].week + 1);
  const peak = ordered.reduce((best, point) => point.value > best.value ? point : best, ordered[0] ?? { week: 0, value: 0 });
  const isPreseasonOnly = ordered.length === 1 && ordered[0]?.week === 0;
  const isCurrentProjectionOnly = isPreseasonOnly && ordered[0]?.source === "current";

  return (
    <section className="rounded-3xl border border-cyan-200/20 bg-[#091323] p-4 sm:p-5" aria-label={ariaLabel}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100">{yLabel} by week</p>
          <p className="mt-1 text-xs font-bold text-white/55">
            {isCurrentProjectionOnly
              ? "Current projection — weekly snapshots begin at Week 1"
              : isPreseasonOnly
                ? "Preseason baseline — weekly snapshots begin at Week 1"
                : "Week 0–13 trajectory"}
          </p>
        </div>
        <p className="text-xs font-black text-white">Peak: {valueFormatter(peak.value)} <span className="text-white/45">({peak.week === 0 ? "W0" : `W${peak.week}`})</span></p>
      </div>
      <div className="overflow-x-auto pb-1">
        <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="h-auto min-w-[620px] w-full" role="img" aria-label={ariaLabel}>
          {horizontalTicks.map((tick) => (
            <g key={tick}>
              <line x1={PADDING.left} x2={CHART_WIDTH - PADDING.right} y1={y(tick)} y2={y(tick)} stroke="rgba(191,219,254,0.16)" strokeDasharray="4 6" />
              <text x={PADDING.left - 10} y={y(tick) + 4} textAnchor="end" fill="rgba(226,232,240,0.62)" fontSize="11" fontWeight="700">
                {yMax === 30 && tick === 30 ? "30+" : tick}
              </text>
            </g>
          ))}
          {weeks.map((week) => (
            <text key={`label-${week}`} x={x(week)} y={CHART_HEIGHT - 16} textAnchor="middle" fill="rgba(226,232,240,0.62)" fontSize="10" fontWeight="700">
              W{week}
            </text>
          ))}
          <text transform={`translate(14 ${PADDING.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle" fill="rgba(226,232,240,0.72)" fontSize="11" fontWeight="800">
            {yLabel}
          </text>
          <text x={PADDING.left + plotWidth / 2} y={CHART_HEIGHT - 1} textAnchor="middle" fill="rgba(226,232,240,0.72)" fontSize="11" fontWeight="800">
            Week
          </text>
          {hasConnectedWeeks ? <path d={connectedLine} fill="none" stroke="#5ee7ff" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" /> : null}
          {ordered.map((point) => (
            <g key={point.week}>
              <title>{point.week === 0 ? point.source === "current" ? "Current projection" : "Preseason baseline" : `Week ${point.week}`}: {valueFormatter(point.value)}</title>
              <circle cx={x(point.week)} cy={y(point.value)} r="6" fill={point.source === "published" ? "#ffffff" : point.source === "bye" ? "#64748b" : "#5ee7ff"} stroke="#08111f" strokeWidth="3" />
            </g>
          ))}
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-bold text-white/50">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-cyan-300" />{points.some((point) => point.source === "current") ? "Current projection" : "Preseason baseline"}</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-white" />Published weekly snapshot</span>
        {points.some((point) => point.source === "bye") ? <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-slate-500" />Bye</span> : null}
      </div>
    </section>
  );
}
