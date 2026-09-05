type Popularity = {
  rostered_percent?: number | null;
  start_percent?: number | null;
} | null | undefined;

const formatPercent = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "—";

/** A shared compact read-only metric row for roster and waiver player rows. */
export function PlayerPopularityMetrics({ popularity }: { popularity: Popularity }) {
  return (
    <span
      data-player-popularity
      className="mt-0.5 flex flex-wrap gap-x-2 text-[8px] font-black uppercase tracking-[0.1em] text-cfb-text-muted"
    >
      <span>Rostered {formatPercent(popularity?.rostered_percent)}</span>
      <span>Start {formatPercent(popularity?.start_percent)}</span>
    </span>
  );
}
