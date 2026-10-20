import { useLeagues } from "@/hooks/use-leagues";
import {
  ChallengeLeaderboardFilters,
  ChallengeModeStandings,
} from "@/components/challenges/ChallengeLeaderboardModes";
import { Link, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import {
  type Round,
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
  const [params, setParams] = useSearchParams();
  const leagues = useLeagues(100);
  const leagueId = Number(params.get("league")) || undefined;
  const mode = params.get("mode") ?? "overall";
  const [view, setView] = useState<"week" | "season">("week");
  const current = useCurrentChallenges();
  const season = Number(params.get("season")) || current.data?.season;
  const roundId = Number(params.get("round")) || current.data?.id;
  const history = useQuery({
    queryKey: ["weekly-challenges", "leaderboard-history", user?.id],
    enabled: !!user,
    queryFn: () =>
      apiGet<Round[]>("/weekly-challenges/history", {
        limit: 30,
        include_experiences: true,
      }),
    refetchInterval: 30_000,
  });
  const selectedRound = useQuery({
    queryKey: ["weekly-challenges", "leaderboard-round", user?.id, roundId],
    enabled: !!user && !!roundId && roundId !== current.data?.id,
    queryFn: () =>
      apiGet<Round>(`/weekly-challenges/rounds/${roundId}`, {
        include_experiences: true,
      }),
    refetchInterval: 30_000,
  });
  const round =
    roundId === current.data?.id ? current.data : selectedRound.data;
  const query = useQuery({
    queryKey: [
      "weekly-challenges",
      "leaderboard",
      user?.id,
      season,
      view,
      roundId,
      leagueId,
    ],
    enabled: !!user && !!season && (view === "season" || !!roundId),
    queryFn: () =>
      apiGet<Leaderboard>("/weekly-challenges/leaderboard", {
        season,
        round_id: view === "week" ? roundId : undefined,
        league_id: leagueId,
      }),
    refetchInterval: 30_000,
  });
  return (
    <div className="mx-auto max-w-3xl space-y-5 pb-24 pt-3">
      <PageHeader
        title={view === "season" ? "Season Championship" : "Weekly Leaderboard"}
        eyebrow={`${season ?? "Competition"}${view === "week" && query.data?.week ? ` · Week ${query.data.week}` : ""} · Recognition only`}
        description="The Overall championship retains the five existing formats’ achievement points. Each new mode uses its own standings; fantasy points, fan accuracy and survivor weeks are never added together."
      />
      <Button asChild variant="outline">
        <Link to="/weekly-challenges">Weekly Challenges</Link>
      </Button>
      <ChallengeLeaderboardFilters />
      <label className="block text-xs">
        Competition week
        <select
          aria-label="Leaderboard week"
          className="cfb-control mt-2 min-h-11 w-full p-3 text-base"
          value={roundId ?? ""}
          onChange={(e) => {
            const p = new URLSearchParams(params);
            p.set("round", e.target.value);
            p.set(
              "season",
              String(
                history.data?.find((r) => r.id === Number(e.target.value))
                  ?.season ?? season,
              ),
            );
            p.delete("competition");
            setParams(p);
          }}
        >
          {(history.data ?? (current.data ? [current.data] : [])).map((r) => (
            <option key={r.id} value={r.id}>
              {r.season} · Week {r.week}
            </option>
          ))}
        </select>
      </label>
      {mode !== "overall" ? (
        <ChallengeModeStandings round={round} />
      ) : (
        <>
          <label className="block text-xs">
            Compare with
            <select
              aria-label="Leaderboard league group"
              className="cfb-control mt-2 min-h-11 w-full px-3 text-base"
              value={leagueId ?? ""}
              onChange={(e) => {
                const n = new URLSearchParams(params);
                e.target.value
                  ? n.set("league", e.target.value)
                  : n.delete("league");
                setParams(n);
              }}
            >
              <option value="">Everyone</option>
              {leagues.data?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
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
                Provisional weekly standings — some challenges are still
                processing. Pending awards are excluded.
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
        </>
      )}
    </div>
  );
}
