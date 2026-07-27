type TrajectoryPoint = {
  week: number;
  value: number;
  source?: "published" | "modeled" | "bye";
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
  const x = (week: number) => PADDING.left + ((week - 1) / 12) * plotWidth;
  const y = (value: number) => PADDING.top + (1 - Math.min(finiteValue(value), yMax) / yMax) * plotHeight;
  const line = ordered.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.week)} ${y(point.value)}`).join(" ");
  const area = `${line} L ${x(13)} ${PADDING.top + plotHeight} L ${x(1)} ${PADDING.top + plotHeight} Z`;
  const peak = ordered.reduce((best, point) => point.value > best.value ? point : best, ordered[0] ?? { week: 1, value: 0 });

  return (
    <section className="rounded-3xl border border-cyan-200/20 bg-[#091323] p-4 sm:p-5" aria-label={ariaLabel}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100">{yLabel} by week</p>
          <p className="mt-1 text-xs font-bold text-white/55">Week 1–13 trajectory</p>
        </div>
        <p className="text-xs font-black text-white">Peak: {valueFormatter(peak.value)} <span className="text-white/45">(W{peak.week})</span></p>
      </div>
      <div className="overflow-x-auto pb-1">
        <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="h-auto min-w-[620px] w-full" role="img" aria-label={ariaLabel}>
          <defs>
            <linearGradient id={`trajectory-fill-${yLabel.replace(/[^a-z0-9]/gi, "").toLowerCase()}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#4dd9ff" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#4dd9ff" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {horizontalTicks.map((tick) => (
            <g key={tick}>
              <line x1={PADDING.left} x2={CHART_WIDTH - PADDING.right} y1={y(tick)} y2={y(tick)} stroke="rgba(191,219,254,0.16)" strokeDasharray="4 6" />
              <text x={PADDING.left - 10} y={y(tick) + 4} textAnchor="end" fill="rgba(226,232,240,0.62)" fontSize="11" fontWeight="700">
                {yMax === 30 && tick === 30 ? "30+" : tick}
              </text>
            </g>
          ))}
          {ordered.map((point) => (
            <text key={`label-${point.week}`} x={x(point.week)} y={CHART_HEIGHT - 16} textAnchor="middle" fill="rgba(226,232,240,0.62)" fontSize="10" fontWeight="700">
              W{point.week}
            </text>
          ))}
          <text transform={`translate(14 ${PADDING.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle" fill="rgba(226,232,240,0.72)" fontSize="11" fontWeight="800">
            {yLabel}
          </text>
          <text x={PADDING.left + plotWidth / 2} y={CHART_HEIGHT - 1} textAnchor="middle" fill="rgba(226,232,240,0.72)" fontSize="11" fontWeight="800">
            Week
          </text>
          <path d={area} fill={`url(#trajectory-fill-${yLabel.replace(/[^a-z0-9]/gi, "").toLowerCase()})`} />
          <path d={line} fill="none" stroke="#5ee7ff" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />
          {ordered.map((point) => (
            <g key={point.week}>
              <title>Week {point.week}: {valueFormatter(point.value)}</title>
              <circle cx={x(point.week)} cy={y(point.value)} r="5" fill={point.source === "published" ? "#ffffff" : point.source === "bye" ? "#64748b" : "#5ee7ff"} stroke="#08111f" strokeWidth="3" />
            </g>
          ))}
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-bold text-white/50">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-white" />Published</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-cyan-300" />Modeled outlook</span>
        {points.some((point) => point.source === "bye") ? <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-slate-500" />Bye</span> : null}
      </div>
    </section>
  );
}
