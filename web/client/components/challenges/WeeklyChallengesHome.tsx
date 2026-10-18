import { WeeklyChallengeSponsor } from "@/components/challenges/WeeklyChallengeSponsor";
import { Link } from "react-router-dom";
import { Trophy, ArrowRight } from "lucide-react";
import { SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { useCurrentChallenges } from "@/hooks/use-weekly-challenges";

export function WeeklyChallengesHome() {
  const query = useCurrentChallenges();
  const card = (
    <SurfaceCard className="space-y-4" aria-label="Weekly Challenges">
      <div className="flex items-start gap-3">
        <Trophy
          className="mt-1 h-6 w-6 shrink-0 text-primary"
          aria-hidden="true"
        />
        <div>
          <h2 className="cfb-section-title text-xl">Weekly Challenges</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {query.data
              ? `${query.data.season} · Week ${query.data.week} · ${query.data.state}`
              : query.isError
                ? "Challenges are temporarily unavailable."
                : "Loading competition week…"}
          </p>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Free weekly competitions. Earn recognition, cosmetic badges, and a place
        in the Season Championship.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button asChild>
          <Link to="/weekly-challenges">
            Open Challenges <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/weekly-challenges/leaderboard">View Leaderboard</Link>
        </Button>
      </div>
      {query.isError && (
        <button
          type="button"
          className="text-sm text-primary underline"
          onClick={() => void query.refetch()}
        >
          Retry loading this week
        </button>
      )}
    </SurfaceCard>
  );
  return query.data?.sponsor ? (
    <div className="space-y-3">
      <WeeklyChallengeSponsor sponsor={query.data.sponsor} />
      {card}
    </div>
  ) : (
    card
  );
}
