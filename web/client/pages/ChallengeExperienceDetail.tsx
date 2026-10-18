import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { WeeklyChallengeSponsor } from "@/components/challenges/WeeklyChallengeSponsor";
import { ExperienceEntry } from "@/components/challenges/ExperienceEntry";
import { ExperienceLeaderboard } from "@/components/challenges/ExperienceLeaderboard";
import { ChallengeShare } from "@/components/challenges/ChallengeShare";
import { useAuth } from "@/hooks/use-auth";
import {
  useChallenge,
  useChallengeState,
  challengeError,
  deadlineText,
  type Challenge,
} from "@/hooks/use-weekly-challenges";
import { apiChallengeWrite } from "@/lib/api";

function SchoolChoice({ c, onSaved }: { c: Challenge; onSaved: () => void }) {
  const { user } = useAuth();
  const x = c.experience!;
  const [search, setSearch] = useState(""),
    [conference, setConference] = useState("");
  const m = useMutation({
    mutationFn: (id: number) =>
      apiChallengeWrite(
        user!.id,
        "PUT",
        `/weekly-challenges/experiences/${c.id}/allegiance`,
        { school_id: id },
      ),
    onSuccess: onSaved,
  });
  return (
    <SurfaceCard className="space-y-4">
      <h2 className="cfb-section-title text-xl">Who Do You Represent?</h2>
      {x.allegiance ? (
        <>
          <p className="text-lg font-black text-primary">
            {x.allegiance.name} · {x.allegiance.conference}
          </p>
          <p className="text-xs text-muted-foreground">
            Your school is fixed for Week {x.week}. Changes in a later week do
            not rewrite past contributions.
          </p>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <p>
              Weekly rank
              <br />
              <strong>
                {x.school_week_rank
                  ? `#${x.school_week_rank}`
                  : "Provisional / Pending"}
              </strong>
            </p>
            <p>
              Season rank
              <br />
              <strong>
                {x.school_season_rank
                  ? `#${x.school_season_rank}`
                  : "Provisional / Pending"}
              </strong>
            </p>
            <p>
              Your Fan Points
              <br />
              <strong>{x.personal_contribution ?? "Pending"}</strong>
            </p>
            <p>
              Correct predictions
              <br />
              <strong>{x.personal_correct ?? "Pending"}</strong>
            </p>
          </div>
        </>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              aria-label="Search schools"
              placeholder="Search schools"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="cfb-control min-h-11 p-3 text-base"
            />
            <select
              aria-label="School conference"
              value={conference}
              onChange={(e) => setConference(e.target.value)}
              className="cfb-control min-h-11 p-3 text-base"
            >
              <option value="">All conferences</option>
              {[...new Set(x.schools.map((s) => s.conference))]
                .sort()
                .map((v) => (
                  <option key={v}>{v}</option>
                ))}
            </select>
          </div>
          <div className="grid max-h-80 gap-2 overflow-auto sm:grid-cols-2">
            {x.schools
              .filter(
                (s) =>
                  s.name.toLowerCase().includes(search.toLowerCase()) &&
                  (!conference || s.conference === conference),
              )
              .map((s) => (
                <Button
                  variant="outline"
                  key={s.id}
                  disabled={m.isPending || c.state !== "Open"}
                  onClick={() => m.mutate(s.id)}
                  className="h-auto min-h-12 whitespace-normal"
                >
                  {s.name} · {s.conference}
                </Button>
              ))}
          </div>
          {x.schools.length === 0 && (
            <p className="text-sm">
              Current school metadata is awaiting publication.
            </p>
          )}
        </>
      )}
      {m.isError && (
        <p role="alert" className="text-sm text-red-300">
          {challengeError(m.error)}
        </p>
      )}
    </SurfaceCard>
  );
}

function Experience({ c }: { c: Challenge }) {
  const { user } = useAuth();
  const cache = useQueryClient();
  const [params] = useSearchParams();
  const x = c.experience!;
  const refresh = () => {
    void cache.invalidateQueries({ queryKey: ["weekly-challenges"] });
  };
  useEffect(() => {
    if (
      !user ||
      navigator.doNotTrack === "1" ||
      localStorage.getItem(`cffb_analytics_opt_out_${user.id}`) === "true"
    )
      return;
    void apiChallengeWrite(user.id, "POST", "/weekly-challenges/events", {
      event_type: "view",
      challenge_id: c.id,
    }).catch(() => {});
    const ref = params.get("ref");
    if (ref)
      void apiChallengeWrite(user.id, "POST", "/weekly-challenges/events", {
        event_type: "referral_open",
        challenge_id: c.id,
        creator_slug: ref,
      }).catch(() => {});
  }, [user?.id, c.id, params]);
  const priorPending = x.previous_picks.some(
    (p) =>
      p.week < x.week &&
      ["pending", "ineligible", "eliminated"].includes(p.outcome),
  );
  return (
    <>
      <WeeklyChallengeSponsor sponsor={c.sponsor} />
      <PageHeader
        eyebrow={`${x.season} · Week ${x.week} · ${c.state}`}
        title={x.creator ? `Beat ${x.creator.name}` : c.name}
        description={
          c.kind === "millionaire"
            ? "$100 Budget. Six Players. One Champion."
            : c.kind === "survivor"
              ? "One Pick. One Chance. Survive Another Week."
              : c.kind === "fanwars"
                ? "Represent Your School"
                : "Can You Outpick the Experts?"
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p>{x.participants} entrants</p>
        <p>Deadline: {deadlineText(c.lock_at)}</p>
      </div>
      {x.creator && (
        <SurfaceCard className="flex flex-wrap items-center gap-4">
          {x.creator.logo_url && (
            <img
              alt={`${x.creator.name} logo`}
              src={x.creator.logo_url}
              className="h-16 w-16 object-contain"
            />
          )}
          <div>
            <p className="font-bold">{x.creator.name}</p>
            <p className="text-sm text-muted-foreground">
              {x.creator.description}
            </p>
            <div className="flex flex-wrap gap-3">
              {Object.entries(x.creator.links).map(([name, url]) => (
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
          </div>
        </SurfaceCard>
      )}
      {c.kind === "fanwars" && <SchoolChoice c={c} onSaved={refresh} />}
      {c.kind === "survivor" && (
        <SurfaceCard className="space-y-4">
          <h2 className="cfb-section-title text-xl">
            {x.series?.name ?? "Survivor Series"}
          </h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <p>
              Survivors remaining
              <br />
              <strong className="text-xl">{x.remaining_survivors}</strong>
            </p>
            <p>
              Eliminated entrants
              <br />
              <strong className="text-xl">{x.eliminated}</strong>
            </p>
            <p>
              Your status
              <br />
              <strong>
                {x.survivor_status === "eliminated"
                  ? "YOU'VE BEEN ELIMINATED"
                  : x.survivor_status === "not_joined"
                    ? "Not joined"
                    : priorPending
                      ? "Prior result pending"
                      : c.entry?.status === "submitted" && c.state === "Open"
                        ? "Pick submitted"
                        : x.survivor_status?.replaceAll("_", " ")}
              </strong>
            </p>
            <p>
              Weeks survived
              <br />
              <strong>{x.weeks_survived}</strong>
            </p>
          </div>
          <div
            className="flex gap-3 overflow-x-auto pb-2"
            aria-label="Survivor weekly timeline"
          >
            {x.series &&
              Array.from(
                { length: x.series.end_week - x.series.start_week + 1 },
                (_, i) => i + x.series!.start_week,
              ).map((week) => {
                const p = x.previous_picks.find((p) => p.week === week);
                return (
                  <div
                    className="min-w-36 rounded border border-border p-3 text-xs"
                    key={week}
                  >
                    <strong>Week {week}</strong>
                    <p className="mt-2">{p?.team ?? "No selection"}</p>
                    <p>{p?.outcome.replaceAll("_", " ") ?? "Upcoming"}</p>
                    {p?.game && (
                      <p className="mt-1 text-muted-foreground">
                        vs. {p.opponent} · {p.game.away_points ?? "—"}–
                        {p.game.home_points ?? "—"}
                      </p>
                    )}
                  </div>
                );
              })}
          </div>
          {x.survivor_status === "eliminated" && (
            <p className="text-sm">
              Your streak ended at {x.weeks_survived} weeks. View the remaining
              survivors below or{" "}
              <Link
                to="/weekly-challenges/modes/survivor"
                className="text-primary underline"
              >
                find the next survivor series
              </Link>
              .
            </p>
          )}
        </SurfaceCard>
      )}
      <details className="rounded border border-border bg-card p-4">
        <summary className="min-h-8 cursor-pointer font-bold">
          Rules and eligibility
        </summary>
        <p className="mt-3 text-sm leading-relaxed">{c.rules}</p>
        <p className="mt-3 text-xs text-muted-foreground">
          {c.rules_version}
          {c.scoring_version ? ` · CFFB scoring ${c.scoring_version}` : ""}
        </p>
        {c.scoring_rules && (
          <pre className="mt-3 max-h-60 overflow-auto text-xs">
            {JSON.stringify(c.scoring_rules, null, 2)}
          </pre>
        )}
      </details>
      {c.state === "Open" &&
      user &&
      !(
        c.kind === "survivor" &&
        (x.survivor_status === "eliminated" || priorPending)
      ) ? (
        <ExperienceEntry
          key={`${user.id}:${c.id}`}
          challenge={c}
          accountId={user.id}
          onSaved={refresh}
        />
      ) : (
        <SurfaceCard>
          <p className="font-bold">
            {c.state === "Upcoming"
              ? "Entries are not open yet."
              : c.kind === "survivor" && priorPending
                ? "Your prior survivor result must be resolved before you can advance."
                : "Entry changes are closed."}
          </p>
          {c.cancellation_reason && (
            <p className="mt-2 text-sm">{c.cancellation_reason}</p>
          )}
          {c.entry && (
            <ul className="mt-3 space-y-2 text-sm">
              {c.entry.selections.map((p, i) => (
                <li key={i}>
                  {p.team ??
                    `${p.slot}: ${c.players.find((v) => v.id === p.player_id)?.name ?? "Selected player"}`}
                </li>
              ))}
            </ul>
          )}
        </SurfaceCard>
      )}
      {c.kind === "creator" && x.creator_picks && (
        <SurfaceCard className="space-y-4">
          <h2 className="cfb-section-title text-xl">
            {x.comparison ?? "Creator Comparison"}
          </h2>
          <p className="text-sm">
            {x.creator_correct} correct · {x.creator_score} creator points
            {x.comparison ? " · Final" : " · Provisional"}
          </p>
          {c.games.map((g) => (
            <div key={g.id} className="border-t border-border pt-3 text-sm">
              <strong>
                {g.away_team} at {g.home_team}
              </strong>
              <p className="mt-1 text-muted-foreground">
                Your pick:{" "}
                {c.entry?.selections.find((p) => p.game_id === g.id)?.team ??
                  "No pick"}{" "}
                · Creator:{" "}
                {x.creator_picks?.find((p) => p.game_id === g.id)?.team ??
                  "Pending"}
              </p>
              <p>
                {g.status} · {g.away_points ?? "—"}–{g.home_points ?? "—"}
              </p>
            </div>
          ))}
        </SurfaceCard>
      )}
      {c.kind === "fanwars" && x.rivalries.length > 0 && (
        <SurfaceCard>
          <h2 className="cfb-section-title mb-3">Featured Fan Rivalries</h2>
          <p className="mb-3 text-xs text-muted-foreground">
            Fan competitions; schools need not be scheduled opponents. Scoring
            closes {deadlineText(c.lock_at)}.
          </p>
          {x.rivalries.map((r, i) => (
            <div key={i} className="border-t border-border py-3 text-sm">
              <p className="font-bold">
                {r.a.school} {r.a.fan_points} vs. {r.b.fan_points} {r.b.school}
              </p>
              <p className="text-xs text-muted-foreground">
                {r.a.active_fans} fans vs. {r.b.active_fans} fans ·{" "}
                {r.winner ? `Final: ${r.winner}` : "In progress"}
              </p>
            </div>
          ))}
        </SurfaceCard>
      )}
      {x.corrections.length > 0 && (
        <SurfaceCard>
          <h2 className="cfb-section-title mb-2">Administrative Corrections</h2>
          <ul className="space-y-2 text-sm">
            {x.corrections.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
        </SurfaceCard>
      )}
      <ExperienceLeaderboard challenge={c} />
      {c.published_at && <ChallengeShare challenge={c} />}
    </>
  );
}
export default function ChallengeExperienceDetail() {
  const { challengeId } = useParams();
  const q = useChallenge(Number(challengeId));
  const state = useChallengeState(q.data);
  return (
    <div className="mx-auto max-w-4xl space-y-5 pb-24 pt-3">
      <Button asChild variant="outline">
        <Link to="/weekly-challenges">All Challenges</Link>
      </Button>
      {q.isPending && <p role="status">Loading competition…</p>}
      {q.isError && (
        <SurfaceCard>
          <p role="alert">
            This competition is unavailable. {challengeError(q.error)}
          </p>
          <Button className="mt-3" onClick={() => void q.refetch()}>
            Retry
          </Button>
        </SurfaceCard>
      )}
      {q.data?.experience && <Experience c={{ ...q.data, state }} />}
      {q.data && !q.data.experience && (
        <SurfaceCard>
          <p>Open this existing weekly challenge.</p>
          <Button asChild className="mt-3">
            <Link to={`/weekly-challenges/${q.data.id}`}>Continue</Link>
          </Button>
        </SurfaceCard>
      )}
    </div>
  );
}
