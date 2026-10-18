import { useEffect } from "react";
import { Link, useParams, useSearchParams, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { ChallengeTile } from "@/components/challenges/ChallengeHubCards";
import { WeeklyChallengeSponsor } from "@/components/challenges/WeeklyChallengeSponsor";
import {
  useExperiences,
  isExperience,
  type Creator,
} from "@/hooks/use-challenge-experiences";
import {
  CHALLENGE_NAMES,
  useCurrentChallenges,
} from "@/hooks/use-weekly-challenges";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, apiChallengeWrite } from "@/lib/api";

function Mode({ kind }: { kind: Parameters<typeof useExperiences>[0] }) {
  const { user } = useAuth();
  const q = useExperiences(kind);
  const current = useCurrentChallenges();
  const [params] = useSearchParams();
  const creators = useQuery({
    queryKey: ["weekly-challenges", "creators", user?.id],
    enabled: !!user && kind === "creator",
    queryFn: async () => {
      const values = await apiGet<Creator[]>("/weekly-challenges/creators");
      if (!Array.isArray(values)) throw new Error("Creators unavailable.");
      return values;
    },
  });
  const ref = params.get("ref"),
    selected = params.get("creator");
  useEffect(() => {
    if (
      !user ||
      !ref ||
      kind !== "creator" ||
      navigator.doNotTrack === "1" ||
      localStorage.getItem(`cffb_analytics_opt_out_${user.id}`) === "true"
    )
      return;
    void apiChallengeWrite(user.id, "POST", "/weekly-challenges/events", {
      event_type: "referral_open",
      creator_slug: ref,
    }).catch(() => {});
  }, [user?.id, ref, kind]);
  const rows = q.data?.filter(
    (c) => !selected || c.experience?.creator?.slug === selected,
  );
  return (
    <div className="mx-auto max-w-6xl space-y-5 pb-24 pt-3">
      <Button asChild variant="outline">
        <Link to="/weekly-challenges">All Challenges</Link>
      </Button>
      <PageHeader
        title={CHALLENGE_NAMES[kind]}
        description={
          kind === "millionaire"
            ? "$100 Budget. Six Players. One Champion."
            : kind === "survivor"
              ? "One Pick. One Chance. Survive Another Week."
              : kind === "creator"
                ? "Think you know college football better than the experts?"
                : "Represent your school. Compete on accuracy and Fan Power."
        }
      />
      <WeeklyChallengeSponsor sponsor={current.data?.sponsor} />
      {q.isPending && <p role="status">Loading competitions…</p>}
      {q.isError && (
        <SurfaceCard>
          <p role="alert">
            Could not load competitions.{" "}
            <button className="underline" onClick={() => void q.refetch()}>
              Retry
            </button>
          </p>
        </SurfaceCard>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {rows?.map((c) => (
          <ChallengeTile key={c.id} challenge={c} week={c.experience?.week} />
        ))}
      </div>
      {rows?.length === 0 && (
        <SurfaceCard>
          <h2 className="cfb-section-title text-xl">
            No published competition yet
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            The next slate, rules and deadline will appear after administrator
            approval.{" "}
            {kind === "creator"
              ? "Creator predictions are published only after their participation and picks are approved."
              : kind === "millionaire"
                ? "Every salary is reviewed before lineups open."
                : kind === "survivor"
                  ? "New entrants join a new series before its first lock."
                  : "School standings begin when official predictions are scored."}
          </p>
        </SurfaceCard>
      )}
      {kind === "creator" && (
        <SurfaceCard>
          <h2 className="cfb-section-title mb-4">Creator Directory</h2>
          {creators.isPending && (
            <p role="status">Loading approved creators…</p>
          )}
          {creators.isError && (
            <p role="alert">
              Creator directory unavailable.{" "}
              <button
                className="underline"
                onClick={() => void creators.refetch()}
              >
                Retry
              </button>
            </p>
          )}
          {creators.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Approved participating creators will appear here.
            </p>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {creators.data?.map((c) => (
              <section key={c.id} className="rounded border border-border p-4">
                {c.logo_url && (
                  <img
                    src={c.logo_url}
                    alt={`${c.name} logo`}
                    className="mb-3 h-16 w-16 object-contain"
                  />
                )}
                <h3 className="font-bold">{c.name}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {c.description}
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  {Object.entries(c.links).map(([name, url]) => (
                    <a
                      key={name}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-h-11 items-center text-sm font-bold text-primary underline"
                    >
                      {name}
                    </a>
                  ))}
                </div>
                <Button variant="outline" asChild className="mt-3">
                  <Link
                    to={`/weekly-challenges/modes/creator?creator=${encodeURIComponent(c.slug)}&ref=${encodeURIComponent(c.slug)}`}
                  >
                    View Creator Challenges
                  </Link>
                </Button>
              </section>
            ))}
          </div>
        </SurfaceCard>
      )}
    </div>
  );
}
export default function ChallengeMode() {
  const { kind } = useParams();
  return kind && isExperience(kind) ? (
    <Mode kind={kind} />
  ) : (
    <Navigate to="/weekly-challenges" replace />
  );
}
export function CreatorChallengeLink() {
  const { slug } = useParams();
  return (
    <Navigate
      to={`/weekly-challenges/modes/creator?creator=${encodeURIComponent(slug ?? "")}&ref=${encodeURIComponent(slug ?? "")}`}
      replace
    />
  );
}
