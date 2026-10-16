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

function ChallengeTile({ challenge: c }: { challenge: Challenge }) {
  const state = useChallengeState(c);
  return (
    <SurfaceCard className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="cfb-section-title text-xl">{c.name}</h2>
        <span className="rounded border border-border px-2 py-1 text-xs font-bold">
          {state}
        </span>
      </div>
      <p className="text-sm">{FORMATS[c.kind]}</p>
      <p className="text-sm text-muted-foreground">
        Entry deadline: {deadlineText(c.lock_at)}
      </p>
      <p className="text-sm">
        My entry:{" "}
        {c.entry?.status === "submitted"
          ? "Submitted"
          : c.entry
            ? "Draft saved"
            : "Not entered"}
      </p>
      <Button
        asChild
        variant={state === "Open" ? "default" : "outline"}
        className="mt-auto w-full"
      >
        <Link to={`/weekly-challenges/${c.id}`}>
          {state === "Open"
            ? c.entry
              ? "Edit Entry"
              : "Enter"
            : state === "Upcoming"
              ? "View Rules"
              : "View Results"}
        </Link>
      </Button>
    </SurfaceCard>
  );
}

export default function WeeklyChallenges() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const historyId = Number(params.get("round"));
  const [historyOffset, setHistoryOffset] = useState(0);
  const current = useCurrentChallenges(!historyId);
  const historical = useQuery({
    queryKey: ["weekly-challenges", "round", user?.id, historyId],
    enabled: !!user && historyId > 0,
    queryFn: () => apiGet<Round>(`/weekly-challenges/rounds/${historyId}`),
  });
  const history = useQuery({
    queryKey: ["weekly-challenges", "history", user?.id, historyOffset],
    queryFn: () =>
      apiGet<Round[]>("/weekly-challenges/history", {
        limit: 15,
        offset: historyOffset,
      }),
    enabled: !!user,
  });
  const query = historyId ? historical : current;
  const round = query.data;
  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-24 pt-3">
      <PageHeader
        eyebrow={
          round
            ? `${round.season} · Week ${round.week} · ${round.state}`
            : "App-wide competitions"
        }
        title="Weekly Challenges"
        description="Free to enter. Recognition only. One official entry per competition, per week."
      />
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline">
          <Link to="/">Home</Link>
        </Button>
        <Button asChild>
          <Link
            to={`/weekly-challenges/leaderboard${round ? `?round=${round.id}&season=${round.season}` : ""}`}
          >
            View Leaderboard
          </Link>
        </Button>
        {user?.isAdmin && (
          <Button asChild variant="outline">
            <Link to="/admin/weekly-challenges">Manage Challenges</Link>
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
          <div className="grid gap-4 md:grid-cols-2">
            {round.challenges.map((c) => (
              <ChallengeTile key={c.id} challenge={c} />
            ))}
          </div>
        </>
      )}
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
