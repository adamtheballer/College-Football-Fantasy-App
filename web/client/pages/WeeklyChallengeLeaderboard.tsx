import { Link, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import {
  type Leaderboard,
  type LeaderRow,
  useCurrentChallenges,
} from "@/hooks/use-weekly-challenges";

function StandingRow({ row }: { row: LeaderRow }) {
  return (
    <Link
      to={row.profile_url}
      className="flex min-h-16 items-center gap-3 border-t border-border py-3 hover:bg-primary/5 focus-visible:outline focus-visible:outline-primary"
    >
      <span className="w-9 shrink-0 text-xl font-black">#{row.rank}</span>
      <ManagerAvatar
        managerName={row.display_name}
        avatarUrl={row.avatar_url}
        size="sm"
      />
      <span className="min-w-0 flex-1 truncate text-sm font-bold">
        {row.display_name}
        {row.username ? (
          <span className="block truncate text-xs font-normal text-muted-foreground">
            @{row.username}
          </span>
        ) : null}
      </span>
      <span className="shrink-0 text-right font-black">
        {row.points}
        <span className="block text-xs font-normal text-muted-foreground">
          points
        </span>
      </span>
    </Link>
  );
}

export default function WeeklyChallengeLeaderboard() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [view, setView] = useState<"week" | "season">("week");
  const current = useCurrentChallenges();
  const season = Number(params.get("season")) || current.data?.season;
  const roundId = Number(params.get("round")) || current.data?.id;
  const query = useQuery({
    queryKey: [
      "weekly-challenges",
      "leaderboard",
      user?.id,
      season,
      view,
      roundId,
    ],
    enabled: !!user && !!season && (view === "season" || !!roundId),
    queryFn: () =>
      apiGet<Leaderboard>("/weekly-challenges/leaderboard", {
        season,
        round_id: view === "week" ? roundId : undefined,
      }),
    refetchInterval: 30_000,
  });
  return (
    <div className="mx-auto max-w-3xl space-y-5 pb-24 pt-3">
      <PageHeader
        title={view === "season" ? "Season Championship" : "Weekly Leaderboard"}
        eyebrow={`${season ?? "Competition"} · Recognition only`}
        description="Combined challenge points across all five competitions. Equal totals share rank."
      />
      <Button asChild variant="outline">
        <Link to="/weekly-challenges">Weekly Challenges</Link>
      </Button>
      <div className="flex gap-3" aria-label="Leaderboard period">
        <Button
          variant={view === "week" ? "default" : "outline"}
          aria-pressed={view === "week"}
          onClick={() => setView("week")}
        >
          This Week
        </Button>
        <Button
          variant={view === "season" ? "default" : "outline"}
          aria-pressed={view === "season"}
          onClick={() => setView("season")}
        >
          Season
        </Button>
      </div>
      <SurfaceCard>
        <h2 className="cfb-section-title mb-3">Top 10</h2>
        {query.data?.provisional && (
          <p className="mb-4 text-sm text-amber-300">
            Provisional weekly standings — some challenges are still processing.
            Pending awards are excluded.
          </p>
        )}
        {view === "season" && (
          <p className="mb-4 text-sm text-muted-foreground">
            Finalized challenge awards only. Raw fantasy totals never count
            directly toward the Season Championship.
          </p>
        )}
        {(query.isPending || current.isPending) && (
          <p role="status">Loading standings…</p>
        )}
        {(query.isError || current.isError) && (
          <p role="alert">
            Standings are temporarily unavailable.{" "}
            <button
              className="underline"
              onClick={() => {
                void current.refetch();
                void query.refetch();
              }}
            >
              Retry
            </button>
          </p>
        )}
        {query.data?.data.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No finalized challenge awards yet.
          </p>
        )}
        {query.data?.data.map((row) => (
          <StandingRow key={row.user_id} row={row} />
        ))}
      </SurfaceCard>
      {query.data?.your_rank && (
        <SurfaceCard>
          <h2 className="cfb-section-title mb-3">Your Rank</h2>
          <StandingRow row={query.data.your_rank} />
        </SurfaceCard>
      )}
    </div>
  );
}
