import { experiencePath } from "@/hooks/use-challenge-experiences";
import { WeeklyChallengeSponsor } from "@/components/challenges/WeeklyChallengeSponsor";
import { Link } from "react-router-dom";
import { Trophy, ArrowRight } from "lucide-react";
import { SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import {
  useChallengeState,
  deadlineText,
  useCurrentChallenges,
} from "@/hooks/use-weekly-challenges";

export function WeeklyChallengesHome() {
  const query = useCurrentChallenges();
  const challenges = query.data?.challenges ?? [];
  const simple = [
    "lock",
    "upset",
    "slate12",
    "fanwars",
    "survivor",
    "fantasy5",
    "millionaire",
    "creator",
    "duels",
  ];
  const candidate = [...challenges]
    .filter((c) => c.state === "Open" && c.entry?.status !== "submitted")
    .sort(
      (a, b) =>
        Number(!!b.entry) - Number(!!a.entry) ||
        simple.indexOf(a.kind) - simple.indexOf(b.kind),
    )[0];
  const candidateState = useChallengeState(candidate);
  const first = candidateState === "Open" ? candidate : undefined;
  const submitted = challenges.filter(
    (c) => c.entry?.status === "submitted",
  ).length;
  const href = first ? experiencePath(first) : "/weekly-challenges";
  const card = (
    <SurfaceCard
      className="space-y-4"
      aria-label="Weekly Challenges"
      data-guide-challenges
    >
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
      {first && (
        <p className="text-sm">
          <strong>
            {first.entry
              ? "Finish your saved picks"
              : submitted
                ? "Your next challenge"
                : "Make your first pick"}
            : {first.name}
          </strong>
          <span className="mt-1 block text-xs text-muted-foreground">
            {first.kind === "lock"
              ? "Pick one winner, then submit."
              : "Choose your picks, review, then submit."}{" "}
            Deadline: {deadlineText(first.lock_at)}
          </span>
        </p>
      )}
      {submitted > 0 && (
        <p className="text-xs text-muted-foreground">
          {submitted} official {submitted === 1 ? "entry" : "entries"} submitted
          this week.
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button asChild>
          <Link to={href}>
            {first
              ? first.entry
                ? "Finish picks"
                : submitted
                  ? "Enter next challenge"
                  : "Make your first pick"
              : "Open Challenges"}{" "}
            <ArrowRight className="ml-2 h-4 w-4" />
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
      <WeeklyChallengeSponsor
        sponsor={query.data.sponsor}
        challengeHref={first ? href : undefined}
      />
      {card}
    </div>
  ) : (
    card
  );
}
