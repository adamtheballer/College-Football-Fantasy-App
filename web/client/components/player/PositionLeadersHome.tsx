import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { SurfaceCard, PositionBadge } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import {
  usePositionLeaders,
  rankingPeriodLabel,
  rankingPoints,
  RANKING_POSITIONS,
} from "@/hooks/use-player-rankings";
import { PlayerRankingPortrait } from "./PlayerRankingPortrait";

export function PositionLeadersHome() {
  const [period, setPeriod] = useState<"week" | "season">("week");
  const q = usePositionLeaders(period);
  const params = new URLSearchParams({ period });
  if (q.data?.week) params.set("week", String(q.data.week));
  return (
    <section aria-label="Positional leaders" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="cfb-micro-label text-cfb-brand">
            Verified player performance
          </p>
          <h2 className="cfb-section-title mt-1 text-2xl">
            Positional leaders
          </h2>
          <p className="mt-1 text-sm text-cfb-text-secondary">
            {q.data
              ? `${rankingPeriodLabel(q.data)} · ${q.data.scoring_label}`
              : "Loading verified results…"}
          </p>
        </div>
        <label className="text-xs font-bold">
          Results{" "}
          <select
            aria-label="Leader results period"
            value={period}
            onChange={(e) => setPeriod(e.target.value as "week" | "season")}
            className="cfb-control ml-2 min-h-11 px-3 text-base"
          >
            <option value="week">Latest completed week</option>
            <option value="season">Season totals</option>
          </select>
        </label>
      </div>
      {q.isError ? (
        <SurfaceCard>
          <p role="alert">Player leaders couldn’t load.</p>
          <Button variant="outline" onClick={() => void q.refetch()}>
            Retry leaders
          </Button>
        </SurfaceCard>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2 sm:grid sm:grid-cols-3 lg:grid-cols-5">
          {RANKING_POSITIONS.map((position) => {
            const player = q.data?.data.find(
              (r) => r.position === position,
            )?.player;
            return (
              <SurfaceCard
                key={position}
                padding="compact"
                className="w-40 shrink-0 space-y-3 sm:w-auto sm:min-w-0"
              >
                <PositionBadge position={position} />
                {q.isLoading ? (
                  <p
                    role="status"
                    className="animate-pulse text-sm text-cfb-text-muted"
                  >
                    Loading…
                  </p>
                ) : player ? (
                  <>
                    <Link
                      to={`/player-rankings?${params}&position=${position}`}
                      aria-label={`View ${position} rankings led by ${player.name}`}
                      className="block space-y-2 rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-cfb-brand"
                    >
                      <PlayerRankingPortrait player={player} large />
                      <h3 className="break-words font-bold leading-tight">
                        {player.name}
                      </h3>
                      <p className="text-xs text-cfb-text-muted">
                        {player.school}
                      </p>
                      <p className="cfb-stat-value text-2xl text-cfb-brand">
                        {rankingPoints(player.fantasy_points)}{" "}
                        <span className="text-xs text-cfb-text-secondary">
                          FPTS
                        </span>
                      </p>
                    </Link>
                  </>
                ) : (
                  <p className="text-sm text-cfb-text-muted">
                    Verified results pending.
                  </p>
                )}
              </SurfaceCard>
            );
          })}
        </div>
      )}
      <p className="text-xs text-cfb-text-muted sm:hidden">
        Swipe to see all five positions.
      </p>
      {q.data && (
        <p className="text-xs text-cfb-text-muted">
          {q.data.updated_at
            ? `Verified ${new Date(q.data.updated_at).toLocaleString()}`
            : "Waiting for verified final stats."}
          {q.data.pending_players > 0
            ? ` · ${q.data.pending_players} players pending; ranks cover verified results.`
            : ""}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline">
          <Link to={`/player-rankings?${params}`}>
            All player rankings <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link to={`/player-rankings?${params}&view=mine`}>
            My leagues’ player ranks
          </Link>
        </Button>
      </div>
    </section>
  );
}
