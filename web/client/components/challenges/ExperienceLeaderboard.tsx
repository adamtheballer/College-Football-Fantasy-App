import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { CHALLENGE_LEADERBOARD_LIMIT, type Challenge } from "@/hooks/use-weekly-challenges";
import type { ExperienceLeaderboard as Standings } from "@/hooks/use-challenge-experiences";
export function ExperienceLeaderboard({
  challenge: c,
}: {
  challenge: Challenge;
}) {
  const { user } = useAuth();
  const metric = "power";
  const [conference, setConference] = useState(""),
    [season, setSeason] = useState(false);
  const q = useQuery({
    queryKey: [
      "weekly-challenges",
      "experience-board",
      user?.id,
      c.id,
      metric,
      conference,
      season,
    ],
    enabled: !!user && !!c.published_at,
    queryFn: () =>
      apiGet<Standings>(`/weekly-challenges/experiences/${c.id}/leaderboard`, {
        metric,
        conference: conference || undefined,
        season,
      }),
    refetchInterval: 30_000,
  });
  return (
    <SurfaceCard className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="cfb-section-title text-xl">
          {c.kind === "fanwars" ? "Top 5 Schools" : "Top 5"}
        </h2>
        {q.data && (
          <span className="text-xs">
            {q.data.total} entrants ·{" "}
            {q.data.provisional ? "Provisional" : "Final"}
          </span>
        )}
      </div>
      {c.kind === "fanwars" && (
        <>
          <p className="text-xs text-muted-foreground">
            Schools ranked by Fan Points from resolved eligible picks.
          </p>
          <div
            className="flex flex-wrap gap-2"
            aria-label="School leaderboard period"
          >
            <Button
              variant={season ? "default" : "outline"}
              aria-pressed={season}
              onClick={() => setSeason(!season)}
            >
              {season ? "Season" : "This Week"}
            </Button>
          </div>
          <label className="block text-xs">
            Conference
            <select
              aria-label="School leaderboard conference"
              className="cfb-control mt-2 min-h-11 w-full p-2 text-base"
              value={conference}
              onChange={(e) => setConference(e.target.value)}
            >
              <option value="">National</option>
              <option value="SEC">SEC</option>
              <option value="BIG10">Big Ten</option>
              <option value="BIG12">Big 12</option>
              <option value="ACC">ACC</option>
            </select>
          </label>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="p-2">Rank</th>
                  <th className="p-2">School</th>
                  <th className="p-2">
                    Fan Points
                  </th>
                  <th className="p-2">Fans</th>
                </tr>
              </thead>
              <tbody>
                {q.data?.school_standings.slice(0, CHALLENGE_LEADERBOARD_LIMIT).map((s) => (
                  <tr key={s.school_id} className="border-t border-border">
                    <td className="p-2">
                      {s.rank ? `#${s.rank}` : "Provisional"}
                    </td>
                    <td className="p-2 font-bold">
                      {s.school}
                      <span className="block text-xs font-normal text-muted-foreground">
                        {s.conference} · {s.correct_picks}/{s.eligible_picks}{" "}
                        correct
                      </span>
                    </td>
                    <td className="p-2">
                      {s.fan_points}
                    </td>
                    <td className="p-2">{s.active_fans}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {q.data?.school_standings.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No resolved eligible school predictions yet.
            </p>
          )}
          <h3 className="cfb-micro-label">Individual Contributions</h3>
        </>
      )}
      {q.isPending && c.published_at && (
        <p role="status">Loading authoritative standings…</p>
      )}
      {q.isError && (
        <p role="alert">
          Standings are unavailable.{" "}
          <button className="underline" onClick={() => void q.refetch()}>
            Retry
          </button>
        </p>
      )}
      {q.data?.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No official entries yet.
        </p>
      )}
      <div className="divide-y divide-border">
        {q.data?.data.slice(0, CHALLENGE_LEADERBOARD_LIMIT).map((row) => (
          <section key={row.user_id} className="py-3">
            <div className="flex items-center justify-between gap-3">
              <Link to={row.profile_url} className="min-w-0 text-sm font-bold">
                #{row.rank} {row.display_name}
                {row.user_id === user?.id ? " · You" : ""}
              </Link>
              <span className="text-right text-sm font-black">
                {row.points === null
                  ? row.status === "no_contest"
                    ? "Void"
                    : "Pending"
                  : `${row.points} ${q.data.unit}`}
                <span className="block text-xs font-normal text-muted-foreground">
                  {row.points !== null
                    ? row.status.replaceAll("_", " ")
                    : q.data.provisional
                      ? "Provisional"
                      : "Final"}
                </span>
              </span>
            </div>
            {row.selections && (
              <details className="mt-2 text-xs">
                <summary className="min-h-8 cursor-pointer text-primary">
                  {c.kind === "millionaire" ? "View Lineup" : "View Picks"}
                </summary>
                <ul className="mt-2 space-y-1 text-muted-foreground">
                  {row.selections.map((p, i) => (
                    <li key={i}>
                      {p.team ??
                        `${p.slot}: ${c.players.find((x) => x.id === p.player_id)?.name ?? `Player ${p.player_id}`}`}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        ))}
      </div>
    </SurfaceCard>
  );
}
