import { useServerClock } from "@/components/challenges/ExperienceEntry";
import { ChallengeAnalyticsChoice } from "@/components/challenges/ChallengeAnalyticsChoice";
import { RecentChallengeResults } from "@/components/challenges/RecentChallengeResults";
import {
  ChallengeTile,
  ModeTile,
} from "@/components/challenges/ChallengeHubCards";
import { useModes, isExperience } from "@/hooks/use-challenge-experiences";
import { WeeklyChallengeSponsor } from "@/components/challenges/WeeklyChallengeSponsor";
import { Link, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import {
  type Round,
  type Challenge,
  FORMATS,
  deadlineText,
  useCurrentChallenges,
  useChallengeState,
} from "@/hooks/use-weekly-challenges";

export default function WeeklyChallenges() {
  const { user } = useAuth();
  const modes = useModes();
  const upcoming = useQuery({
    queryKey: ["weekly-challenges", "upcoming", user?.id],
    enabled: !!user,
    queryFn: () =>
      apiGet<Round | null>("/weekly-challenges/upcoming").then((r) => {
        if (r && !Array.isArray(r.challenges))
          throw new Error("Invalid upcoming round.");
        return r;
      }),
    refetchInterval: 30_000,
  });

  const [params] = useSearchParams();
  const historyId = Number(params.get("round"));
  const [historyOffset, setHistoryOffset] = useState(0);
  const current = useCurrentChallenges(!historyId);
  const historical = useQuery({
    queryKey: ["weekly-challenges", "round", user?.id, historyId],
    enabled: !!user && historyId > 0,
    queryFn: () =>
      apiGet<Round>(`/weekly-challenges/rounds/${historyId}`, {
        include_experiences: true,
      }),
  });
  const history = useQuery({
    queryKey: ["weekly-challenges", "history", user?.id, historyOffset],
    queryFn: () =>
      apiGet<Round[]>("/weekly-challenges/history", {
        include_experiences: true,
        limit: 15,
        offset: historyOffset,
      }),
    enabled: !!user,
  });
  const query = historyId ? historical : current;
  const round = query.data;
  const serverTime = useServerClock(
    round?.server_now ?? "1970-01-01T00:00:00Z",
  );
  const nextDeadline = [
    ...(round?.challenges
      .filter((c) => !isExperience(c.kind) && c.state === "Open" && c.lock_at)
      .map((c) => c.lock_at!) ?? []),
    ...(modes.data
      ?.filter((m) => m.state === "Open" && m.lock_at)
      .map((m) => m.lock_at!) ?? []),
  ]
    .map((t) => Date.parse(t))
    .filter((t) => t > serverTime)
    .sort((a, b) => a - b)[0];
  const minutes = nextDeadline
    ? Math.max(0, Math.ceil((nextDeadline - serverTime) / 60000))
    : null;
  const remaining =
    minutes === null
      ? "No open deadline"
      : `${Math.floor(minutes / 1440)}d ${Math.floor((minutes % 1440) / 60)}h ${minutes % 60}m`;

  const weeklyRank = useQuery({
    queryKey: [
      "weekly-challenges",
      "hub-rank",
      user?.id,
      round?.season,
      round?.id,
    ],
    enabled: !!user && !!round,
    queryFn: () =>
      apiGet<import("@/hooks/use-weekly-challenges").Leaderboard>(
        "/weekly-challenges/leaderboard",
        { season: round!.season, round_id: round!.id },
      ),
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-24 pt-3">
      <PageHeader
        eyebrow={
          round
            ? `${round.season} · Week ${round.week} · ${round.state}`
            : "App-wide competitions"
        }
        title="Weekly Challenges"
        description="Compete. Predict. Dominate College Football."
      />
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline">
          <Link to="/">Home</Link>
        </Button>
        <Button asChild>
          <Link
            to={`/weekly-challenges/leaderboard${historyId && round ? `?round=${round.id}&season=${round.season}` : ""}`}
          >
            View Leaderboard
          </Link>
        </Button>
        {user?.isAdmin && (
          <Button asChild variant="outline">
            <Link to="/admin/challenge-experiences">Manage Challenges</Link>
          </Button>
        )}
      </div>
      {query.isPending && <p role="status">Loading competition week…</p>}
      {query.isError && (
        <SurfaceCard>
          <p role="alert">
            Could not load challenges. Your existing entries are safe.
          </p>
          <Button onClick={() => void query.refetch()} className="mt-3">
            Try again
          </Button>
        </SurfaceCard>
      )}
      {round && (
        <>
          <p className="text-sm text-muted-foreground">
            Closed rounds stay closed until the next Matchup weekly rollover:{" "}
            {deadlineText(round.next_rollover_at)}. A new week opens only after
            its slates are published.
          </p>
          <WeeklyChallengeSponsor sponsor={round.sponsor} />
          <div
            className="grid grid-cols-2 gap-3 sm:grid-cols-4"
            aria-label="Challenge week overview"
          >
            <SurfaceCard padding="compact">
              <p className="cfb-micro-label">Week</p>
              <p className="mt-2 text-2xl font-black">{round.week}</p>
            </SurfaceCard>
            <SurfaceCard padding="compact">
              <p className="cfb-micro-label">Open Challenges</p>
              <p className="mt-2 text-2xl font-black">
                {round.challenges.filter((c) => c.state === "Open").length}
              </p>
            </SurfaceCard>
            <SurfaceCard padding="compact">
              <p className="cfb-micro-label">Time Remaining</p>
              <p className="mt-2 text-sm font-bold">{remaining}</p>
            </SurfaceCard>
            <SurfaceCard padding="compact">
              <p className="cfb-micro-label">Your Weekly Rank</p>
              <p className="mt-2 text-2xl font-black">
                {(
                  weeklyRank.data?.your_rank ??
                  weeklyRank.data?.data?.find((r) => r.user_id === user?.id)
                )?.rank ?? "—"}
              </p>
            </SurfaceCard>
          </div>
          {!historyId && (
            <section className="space-y-4" aria-label="Challenge experiences">
              {modes.isPending && (
                <p role="status">Loading competition modes…</p>
              )}
              {modes.isError && (
                <p role="alert">
                  Competition modes are unavailable.{" "}
                  <button
                    className="underline"
                    aria-label="Retry modes"
                    onClick={() => void modes.refetch()}
                  >
                    Retry
                  </button>
                </p>
              )}
              <div className="grid gap-4 md:grid-cols-2">
                {modes.data?.map((m) => (
                  <ModeTile
                    key={m.kind}
                    mode={m}
                    week={round.week}
                    entered={round.challenges.some(
                      (c) =>
                        m.competitions.includes(c.id) &&
                        c.entry?.status === "submitted",
                    )}
                  />
                ))}
              </div>
            </section>
          )}
          <h2 className="cfb-section-title text-xl">
            {historyId ? "Weekly Competitions" : "Existing Weekly Competitions"}
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {round.challenges
              .filter((c) => historyId || !isExperience(c.kind))
              .map((c) => (
                <ChallengeTile key={c.id} challenge={c} week={round.week} />
              ))}
          </div>
        </>
      )}
      {round && (
        <SurfaceCard>
          <h2 className="cfb-section-title mb-4">Your Active Challenges</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {round.challenges
              .filter((c) => c.entry && !c.state.includes("Final"))
              .map((c) => (
                <ChallengeTile key={c.id} challenge={c} week={round.week} />
              ))}
          </div>
          {!round.challenges.some(
            (c) => c.entry && !c.state.includes("Final"),
          ) && (
            <p className="text-sm text-muted-foreground">
              Enter an open competition to see it here.
            </p>
          )}
        </SurfaceCard>
      )}
      <RecentChallengeResults />
      <ChallengeAnalyticsChoice />
      <SurfaceCard>
        <h2 className="cfb-section-title mb-3">Upcoming Challenges</h2>
        {upcoming.isPending ? (
          <p role="status">Checking next week's competitions…</p>
        ) : upcoming.isError ? (
          <p role="alert">
            Upcoming competitions could not be loaded.{" "}
            <button
              className="underline"
              onClick={() => void upcoming.refetch()}
            >
              Retry
            </button>
          </p>
        ) : upcoming.data ? (
          <>
            <p className="mb-3 text-sm">
              Week {upcoming.data.week} · Entries open only during that
              competition week.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              {upcoming.data.challenges.map((c) => (
                <ChallengeTile
                  key={c.id}
                  challenge={c}
                  week={upcoming.data!.week}
                />
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Next week's slates have not been published yet.
          </p>
        )}
      </SurfaceCard>
      <SurfaceCard>
        <h2 className="cfb-section-title mb-3">Round history</h2>
        <div className="flex flex-wrap gap-3">
          {history.data?.map((r) => (
            <Link
              className="text-sm text-primary underline"
              key={r.id}
              to={`/weekly-challenges?round=${r.id}`}
            >
              {r.season} Week {r.week} · {r.state}
            </Link>
          ))}
        </div>
        {history.data?.length === 0 && (
          <p className="mt-3 text-sm">No older rounds on this page.</p>
        )}
        {(historyOffset > 0 || (history.data?.length ?? 0) >= 15) && (
          <div className="mt-4 flex gap-3">
            <Button
              variant="outline"
              disabled={historyOffset === 0 || history.isFetching}
              onClick={() => setHistoryOffset(Math.max(0, historyOffset - 15))}
            >
              Newer Rounds
            </Button>
            <Button
              variant="outline"
              disabled={(history.data?.length ?? 0) < 15 || history.isFetching}
              onClick={() => setHistoryOffset(historyOffset + 15)}
            >
              Older Rounds
            </Button>
          </div>
        )}
        {history.isError && (
          <p role="alert">
            History is unavailable.{" "}
            <button
              onClick={() => void history.refetch()}
              className="underline"
            >
              Retry
            </button>
          </p>
        )}
      </SurfaceCard>
    </div>
  );
}
