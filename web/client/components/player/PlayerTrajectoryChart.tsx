import { useLayoutEffect, useRef, useState } from "react";

type TrajectoryPoint = {
  week: number;
  value: number | null;
  actualValue?: number | null;
  forecastValue?: number | null;
  isFinalized?: boolean;
  source?: "preseason" | "current" | "published" | "actual" | "bye" | "unavailable";
};

type PlottedPoint = TrajectoryPoint & {
  renderKey: string;
  value: number;
};

const MAX_CHART_WIDTH = 760;
const CHART_HEIGHT = 312;
const PADDING = { top: 24, right: 26, bottom: 46, left: 54 };

const finiteValue = (value: number | null) => (typeof value === "number" && Number.isFinite(value) ? value : 0);

export function PlayerTrajectoryChart({
  ariaLabel,
  points,
  yLabel,
  yMax,
  valueFormatter,
  seriesKind = "value",
  scoringLabel = "Standard CFFB scoring",
}: {
  ariaLabel: string;
  points: TrajectoryPoint[];
  yLabel: string;
  yMax: number;
  valueFormatter: (value: number) => string;
  seriesKind?: "projection" | "value";
  scoringLabel?: string;
}) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState(MAX_CHART_WIDTH);
  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const measure = () => {
      const width = canvas.getBoundingClientRect().width;
      if (width > 0) setChartWidth(Math.max(240, Math.min(MAX_CHART_WIDTH, width)));
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(canvas);
    return () => observer?.disconnect();
  }, []);
  const [hoveredPointKey, setHoveredPointKey] = useState<string | null>(null);
  const [selectedPointKey, setSelectedPointKey] = useState<string | null>(null);
  const ordered = [...points].sort((left, right) => left.week - right.week);
  const isProjection = seriesKind === "projection";
  // A final score supersedes the model estimate for its own week. The API
  // retains both values for auditability, but a weekly chart must render one
  // fantasy-points dot per week.
  const displayPoints: TrajectoryPoint[] = isProjection
    ? ordered.map((point) => {
      const finalPoints = point.source === "actual" ? point.value : point.actualValue;
      return typeof finalPoints === "number" && Number.isFinite(finalPoints)
        ? { ...point, forecastValue: point.forecastValue !== undefined ? point.forecastValue : point.source === "actual" ? null : point.value, value: finalPoints, actualValue: null, source: "actual" }
        : point;
    })
    : ordered;
  const plotWidth = chartWidth - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;
  const values = displayPoints.flatMap((point) => typeof point.value === "number" && Number.isFinite(point.value) ? [point.value] : []);
  const yMin = Math.min(0, ...values.map((value) => Math.floor(value / 10) * 10));
  const yUpper = Math.max(yMax, ...values.map((value) => Math.ceil(value / 10) * 10));
  const horizontalTicks = Array.from({ length: 5 }, (_, index) => yMin + (yUpper - yMin) * index / 4);
  const weeks = Array.from({ length: 14 }, (_, index) => index);
  const x = (week: number) => PADDING.left + (week / 13) * plotWidth;
  const y = (value: number) => PADDING.top + (1 - (finiteValue(value) - yMin) / (yUpper - yMin)) * plotHeight;
  // Do not visually bridge weeks that have not produced a published snapshot.
  // A preseason card therefore renders one Week 0 dot, not a fictitious line.
  const allNumericPoints: PlottedPoint[] = displayPoints.flatMap((point) => (
    point.source !== "actual" && point.source !== "unavailable" && typeof point.value === "number" && Number.isFinite(point.value)
      ? [{ ...point, value: point.value, renderKey: `week-${point.week}` }]
      : []
  ));
  const actualPoints: PlottedPoint[] = displayPoints.flatMap((point) => {
    const value = point.source === "actual" ? point.value : point.actualValue;
    return typeof value === "number" && Number.isFinite(value)
      ? [{ ...point, value, source: "actual" as const, renderKey: `week-${point.week}` }]
      : [];
  });
  const lastActual = actualPoints.at(-1);
  const numericPoints = isProjection
    ? allNumericPoints.filter((point) => !lastActual || point.week > lastActual.week).slice(0, 1)
    : allNumericPoints;
  const projectedWithAnchor = isProjection && lastActual && numericPoints[0]?.week === lastActual.week + 1
    ? [lastActual, ...numericPoints] : numericPoints;
  const connectedPath = (series: PlottedPoint[]) => series.reduce((path, point, index) => {
    const previous = series[index - 1];
    const command = previous && point.week === previous.week + 1 ? "L" : "M";
    return `${path}${command}${x(point.week)} ${y(point.value)} `;
  }, "");
  const hasConnectedWeeks = (series: PlottedPoint[]) => series.some((point, index) => index > 0 && point.week === series[index - 1].week + 1);
  const projectionLine = connectedPath(projectedWithAnchor);
  const actualLine = connectedPath(actualPoints);
  const hasConnectedProjectionWeeks = hasConnectedWeeks(projectedWithAnchor);
  const hasConnectedActualWeeks = hasConnectedWeeks(actualPoints);
  const plottedPoints = [...numericPoints, ...actualPoints];
  const peak = plottedPoints.reduce((best, point) => point.value > best.value ? point : best, plottedPoints[0] ?? { week: 0, value: 0 });
  const isPreseasonOnly = ordered.length === 1 && ordered[0]?.week === 0;
  const isCurrentProjectionOnly = isPreseasonOnly && ordered[0]?.source === "current";
  const activePointKey = hoveredPointKey ?? selectedPointKey;
  const activePoint = plottedPoints.find((point) => point.renderKey === activePointKey) ?? null;

  const pointLabel = (point: TrajectoryPoint) => {
    if (point.source === "bye" || point.value === null) return "BYE";
    if (isProjection && point.source === "actual") return `Week ${point.week} actual fantasy points (Finalized)`;
    if (isProjection && point.source === "published") return `Week ${point.week} fantasy points (Projected)`;
    if (point.week === 0) return point.source === "current" ? "Current projection" : "Preseason";
    return `Week ${point.week} value`;
  };

  const pointColor = (point: TrajectoryPoint) => {
    // A completed week is a final fantasy total; an upcoming week is a model
    // projection. Keeping those two states visually distinct prevents the
    // chart from suggesting that a player has two fantasy scores in one week.
    if (isProjection) return point.source === "actual" ? "#2f80ff" : "#ffffff";
    return "#2f80ff";
  };

  const pointValueText = (point: TrajectoryPoint) => (
    point.source === "bye" || point.value === null ? "BYE" : `${valueFormatter(point.value)}${isProjection && point.source === "actual" && typeof point.forecastValue === "number" ? ` • Projected ${valueFormatter(point.forecastValue)}` : ""}`
  );
  const pointAriaLabel = (point: PlottedPoint) => (
    `${pointLabel(point)}: ${pointValueText(point)}. Select to ${selectedPointKey === point.renderKey ? "hide" : "show"} its value.`
  );
  const toggleSelectedPoint = (pointKey: string) => {
    setSelectedPointKey((current) => current === pointKey ? null : pointKey);
  };
  const activeValueText = activePoint ? pointValueText(activePoint) : null;
  const activeLabelWidth = activeValueText ? Math.max(46, activeValueText.length * 7 + 18) : 0;
  const activeLabelX = activePoint
    ? Math.max(PADDING.left, Math.min(x(activePoint.week) - activeLabelWidth / 2, chartWidth - PADDING.right - activeLabelWidth))
    : 0;
  const activeLabelY = activePoint ? Math.max(5, y(activePoint.value) - 32) : 0;

  return (
    <section className="rounded-3xl border border-cyan-200/20 bg-[#091323] p-4 sm:p-5" aria-label={ariaLabel}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100">{yLabel} by week</p>
          <p className="mt-1 text-xs font-bold text-white/55">
            {isProjection
              ? `Projected until weekly finalization • ${scoringLabel}`
              : isCurrentProjectionOnly
              ? "Current projection — weekly snapshots begin at Week 1"
              : isPreseasonOnly
                ? "Preseason baseline — weekly snapshots begin at Week 1"
                : "Week 0–13 trajectory"}
          </p>
        </div>
        {plottedPoints.length ? <p className="text-xs font-black text-white">Peak: {valueFormatter(peak.value)} <span className="text-white/45">({peak.week === 0 ? "Preseason" : `W${peak.week}`})</span></p> : null}
      </div>
      <div ref={canvasRef} className="min-w-0 pb-1">
        <svg viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`} className="h-auto w-full" role="img" aria-label={ariaLabel}>
          {horizontalTicks.map((tick) => (
            <g key={tick}>
              <line x1={PADDING.left} x2={chartWidth - PADDING.right} y1={y(tick)} y2={y(tick)} stroke="rgba(191,219,254,0.16)" strokeDasharray="4 6" />
              <text x={PADDING.left - 10} y={y(tick) + 4} textAnchor="end" fill="rgba(226,232,240,0.62)" fontSize="11" fontWeight="700">
                {Number(tick.toFixed(1))}
              </text>
            </g>
          ))}
          {weeks.filter(week => chartWidth >= 500 || [0, 3, 6, 9, 13].includes(week)).map((week) => (
            <text key={`label-${week}`} x={x(week)} y={CHART_HEIGHT - 16} textAnchor="middle" fill="rgba(226,232,240,0.62)" fontSize="10" fontWeight="700">
              {week === 0 ? (isProjection ? "Preweek" : "Preseason") : `W${week}`}
            </text>
          ))}
          <text transform={`translate(14 ${PADDING.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle" fill="rgba(226,232,240,0.72)" fontSize="11" fontWeight="800">
            {yLabel}
          </text>
          <text x={PADDING.left + plotWidth / 2} y={CHART_HEIGHT - 1} textAnchor="middle" fill="rgba(226,232,240,0.72)" fontSize="11" fontWeight="800">
            Week
          </text>
          {isProjection ? (
            <>
              {hasConnectedProjectionWeeks ? (
                <path
                  data-testid="trajectory-projection-line"
                  d={projectionLine}
                  fill="none"
                  stroke="#ffffff"
                  strokeDasharray="7 7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="3"
                />
              ) : null}
              {hasConnectedActualWeeks ? (
                <path
                  data-testid="trajectory-actual-line"
                  d={actualLine}
                  fill="none"
                  stroke="#2f80ff"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="4"
                />
              ) : null}
            </>
          ) : hasConnectedProjectionWeeks ? (
            <path data-testid="trajectory-value-line" d={projectionLine} fill="none" stroke="#2f80ff" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" />
          ) : null}
          {numericPoints.map((point) => (
            <g key={point.renderKey}>
              <title>{pointLabel(point)}: {pointValueText(point)}</title>
              <circle
                data-testid={`trajectory-point-${point.renderKey}`}
                cx={x(point.week)}
                cy={y(point.value)}
                r="6"
                fill={pointColor(point)}
                stroke="#08111f"
                strokeWidth="3"
                role="button"
                tabIndex={0}
                aria-label={pointAriaLabel(point)}
                aria-pressed={selectedPointKey === point.renderKey}
                className="cursor-pointer"
                onPointerEnter={() => setHoveredPointKey(point.renderKey)}
                onPointerLeave={() => setHoveredPointKey(null)}
                onClick={() => toggleSelectedPoint(point.renderKey)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggleSelectedPoint(point.renderKey);
                  }
                }}
              />
            </g>
          ))}
          {displayPoints.filter((point) => point.source === "bye").map((point) => (
            <g key={`empty-${point.week}`}>
              <title>{pointLabel(point)}: BYE</title>
              <text x={x(point.week)} y={y(0) - 8} textAnchor="middle" fill="rgba(226,232,240,0.62)" fontSize="9" fontWeight="800">BYE</text>
            </g>
          ))}
          {displayPoints.filter((point) => point.source === "unavailable").map((point) => (
            <g key={`unavailable-${point.week}`}><title>Week {point.week}: {point.isFinalized===false ? "awaiting weekly finalization" : "finalized stats unavailable"}</title><text x={x(point.week)} y={y(0) - 8} textAnchor="middle" fill="rgba(226,232,240,0.62)" fontSize="9">N/A</text></g>
          ))}
          {actualPoints.map((point) => (
            <g key={point.renderKey}>
              <title>{pointLabel(point)}: {pointValueText(point)}</title>
              <circle
                data-testid={`trajectory-point-${point.renderKey}`}
                cx={x(point.week)}
                cy={y(point.value)}
                r="6"
                fill="#2f80ff"
                stroke="#08111f"
                strokeWidth="3"
                role="button"
                tabIndex={0}
                aria-label={pointAriaLabel(point)}
                aria-pressed={selectedPointKey === point.renderKey}
                className="cursor-pointer"
                onPointerEnter={() => setHoveredPointKey(point.renderKey)}
                onPointerLeave={() => setHoveredPointKey(null)}
                onClick={() => toggleSelectedPoint(point.renderKey)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggleSelectedPoint(point.renderKey);
                  }
                }}
              />
            </g>
          ))}
          {activePoint && activeValueText ? (
            <g data-testid="trajectory-point-value" pointerEvents="none">
              <rect x={activeLabelX} y={activeLabelY} width={activeLabelWidth} height="22" rx="6" fill="#07111f" stroke="rgba(94,231,255,0.75)" />
              <text x={activeLabelX + activeLabelWidth / 2} y={activeLabelY + 15} textAnchor="middle" fill="#f8fafc" fontSize="11" fontWeight="800">
                {activeValueText}
              </text>
            </g>
          ) : null}
        </svg>
      </div>
      {activePoint ? <p data-testid="trajectory-selected-point" role="status" className="mt-2 text-xs font-bold leading-5 text-white">{pointLabel(activePoint)}: {pointValueText(activePoint)}</p> : null}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-bold text-white/50">
        {isProjection ? (
          <>
            <span><span className="mr-1 inline-block w-3 border-t-2 border-dashed border-white align-middle" />Weekly projection</span>
            <span><span className="mr-1 inline-block w-3 border-t-2 border-blue-500 align-middle" />Final fantasy points</span>
          </>
        ) : (
          <>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500" />{points.some((point) => point.source === "current") ? "Current projection" : "Preseason baseline"}</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500" />Published weekly snapshot</span>
          </>
        )}
        {points.some((point) => point.source === "bye") ? <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-slate-500" />Bye</span> : null}
      </div>
    </section>
  );
}
