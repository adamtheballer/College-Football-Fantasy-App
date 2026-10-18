import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { SurfaceCard } from "@/components/fantasy";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import { isExperience } from "@/hooks/use-challenge-experiences";
type RecentResult = {
  challenge_id: number;
  kind: string;
  name: string;
  season: number;
  week: number;
  raw_points: number | null;
  rank: number | null;
  status: string;
};
export function RecentChallengeResults() {
  const { user } = useAuth();
  const q = useQuery({
    queryKey: ["weekly-challenges", "my-results", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const rows = await apiGet<RecentResult[]>(
        "/weekly-challenges/my-results",
      );
      if (!Array.isArray(rows)) throw new Error("Results unavailable.");
      return rows;
    },
    refetchInterval: 30_000,
  });
  return (
    <SurfaceCard>
      <h2 className="cfb-section-title mb-4">Your Results</h2>
      {q.isPending && <p role="status">Loading your results…</p>}
      {q.isError && (
        <p role="alert">
          Results could not be loaded.{" "}
          <button className="underline" onClick={() => void q.refetch()}>
            Retry
          </button>
        </p>
      )}
      {q.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Your finalized entries will appear here.
        </p>
      )}
      <div className="divide-y divide-border">
        {q.data?.map((r) => (
          <Link
            className="flex min-h-14 items-center justify-between gap-3 py-3 text-sm"
            key={r.challenge_id}
            to={
              isExperience(r.kind)
                ? `/weekly-challenges/experiences/${r.challenge_id}`
                : `/weekly-challenges/${r.challenge_id}`
            }
          >
            <span className="font-bold">
              {r.name}
              <span className="block text-xs font-normal text-muted-foreground">
                {r.season} · Week {r.week} ·{" "}
                {r.status === "no_contest"
                  ? "No contest"
                  : r.rank
                    ? `Rank #${r.rank}`
                    : "Final"}
              </span>
            </span>
            <span>
              {r.raw_points ?? "Pending"}
              {r.raw_points !== null
                ? ` ${r.kind === "survivor" ? "weeks" : "points"}`
                : ""}
            </span>
          </Link>
        ))}
      </div>
    </SurfaceCard>
  );
}
