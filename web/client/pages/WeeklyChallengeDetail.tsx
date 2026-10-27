import { MembershipGate } from "@/components/MembershipGate";
import { useMembership } from "@/hooks/use-membership";
import { isExperience } from "@/hooks/use-challenge-experiences";
import { WeeklyChallengeSponsor } from "@/components/challenges/WeeklyChallengeSponsor";
import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader, SurfaceCard } from "@/components/fantasy";
import { Button } from "@/components/ui/button";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { useAuth } from "@/hooks/use-auth";
import { apiGet, apiChallengeWrite } from "@/lib/api";
import {
  CHALLENGE_LEADERBOARD_LIMIT,
  type Challenge,
  type Entry,
  type Pick,
  type Duel,
  type Participant,
  type Results,
  challengeError,
  deadlineText,
  useChallenge,
  useChallengeState,
} from "@/hooks/use-weekly-challenges";

import {
  CHALLENGE_PICK_COUNTS,
  FANTASY_SLOTS,
  challengeEntryError,
} from "@/lib/challenge-entry";
export function EntryForm({
  challenge: c,
  accountId,
  onSaved,
}: {
  challenge: Challenge;
  accountId: number;
  onSaved: () => void;
}) {
  const storageKey = `cffb_challenge_draft_${accountId}_${c.round_id}_${c.id}_${c.version}`;
  const [initial] = useState(() => {
    try {
      const value = JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
      if (
        value &&
        value.revision === (c.entry?.revision ?? 0) &&
        Array.isArray(value.picks)
      )
        return value as { picks: Pick[]; tiebreaker: string; revision: number };
    } catch {
      /* Storage is only an optional recovery aid. */
    }
    return {
      picks: c.entry?.selections ?? [],
      tiebreaker: c.entry?.tiebreaker?.toString() ?? "",
      revision: c.entry?.revision ?? 0,
    };
  });
  const [picks, setPicks] = useState<Pick[]>(initial.picks);
  const [tiebreaker, setTiebreaker] = useState(initial.tiebreaker);
  const [revision, setRevision] = useState(initial.revision);
  const [official, setOfficial] = useState(c.entry?.status === "submitted");
  const [confirmation, setConfirmation] = useState("");
  const requiredPicks = CHALLENGE_PICK_COUNTS[c.kind];
  const draftError = challengeEntryError(c, picks, tiebreaker, false);
  const submitError = challengeEntryError(c, picks, tiebreaker, true);
  useEffect(() => {
    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify({ picks, tiebreaker, revision }),
      );
    } catch {
      /* Server remains authoritative. */
    }
  }, [storageKey, picks, tiebreaker, revision]);
  const mutation = useMutation({
    mutationFn: (submit: boolean) => {
      const error = challengeEntryError(c, picks, tiebreaker, submit);
      if (error) throw new Error(error);
      return apiChallengeWrite<Entry>(
        accountId,
        "PUT",
        `/weekly-challenges/challenges/${c.id}/entry`,
        {
          expected_revision: revision,
          submit,
          selections: picks,
          tiebreaker: tiebreaker === "" ? null : Number(tiebreaker),
        },
      );
    },
    onSuccess: (entry) => {
      setRevision(entry.revision);
      setOfficial(entry.status === "submitted");
      setConfirmation(
        entry.status === "submitted"
          ? "Your official entry is submitted."
          : "Draft saved. Submit it before the deadline to compete.",
      );
      onSaved();
    },
    onError: () => onSaved(),
  });
  const change = (next: Pick[]) => {
    setConfirmation("");
    mutation.reset();
    setPicks(next);
  };
  const pickGame = (game_id: number, team: string) => {
    const selected = picks.some(
      (p) => p.game_id === game_id && p.team === team,
    );
    if (c.kind === "lock") change(selected ? [] : [{ game_id, team }]);
    else {
      // A replacement within an already selected game doesn't add a pick.
      if (
        !selected &&
        !picks.some((p) => p.game_id === game_id) &&
        picks.length >= requiredPicks
      )
        return;
      change([
        ...picks.filter((p) => p.game_id !== game_id),
        ...(selected ? [] : [{ game_id, team }]),
      ]);
    }
  };
  const loadSaved = () => {
    setPicks(c.entry?.selections ?? []);
    setRevision(c.entry?.revision ?? 0);
    setOfficial(c.entry?.status === "submitted");
    setTiebreaker(c.entry?.tiebreaker?.toString() ?? "");
    setConfirmation("");
    mutation.reset();
  };
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (c.state !== "Open" || mutation.isPending || submitError) return;
        setConfirmation("");
        mutation.mutate(true);
      }}
      className="space-y-5"
      aria-label={`${c.name} entry`}
    >
      <fieldset
        disabled={mutation.isPending || c.state !== "Open"}
        className="space-y-5"
      >
        {(c.entry?.revision ?? 0) > revision && (
          <div
            role="alert"
            className="rounded border border-amber-500/50 p-3 text-sm"
          >
            The saved entry changed on another screen. Your unsaved choices
            remain here.{" "}
            <button className="underline" type="button" onClick={loadSaved}>
              Load saved entry
            </button>
          </div>
        )}
        {c.kind === "fantasy5" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {FANTASY_SLOTS.map((slot) => {
              const chosen = picks.find((p) => p.slot === slot)?.player_id;
              return (
                <label key={slot} className="space-y-2">
                  <span className="cfb-micro-label">
                    {slot}
                    {slot === "FLEX" ? " · RB / WR / TE" : ""}
                  </span>
                  <select
                    className="cfb-control min-h-12 w-full p-2 text-base"
                    aria-label={`${slot} player`}
                    value={chosen ?? ""}
                    onChange={(event) =>
                      change([
                        ...picks.filter((p) => p.slot !== slot),
                        ...(event.target.value
                          ? [{ slot, player_id: Number(event.target.value) }]
                          : []),
                      ])
                    }
                  >
                    <option value="">Choose {slot}</option>
                    {c.players
                      .filter((p) =>
                        slot === "FLEX"
                          ? ["RB", "WR", "TE"].includes(p.position)
                          : p.position === slot,
                      )
                      .map((p) => (
                        <option
                          key={p.id}
                          value={p.id}
                          disabled={picks.some(
                            (pick) =>
                              pick.player_id === p.id && pick.slot !== slot,
                          )}
                        >
                          {p.name} · {p.school} · {p.position}
                        </option>
                      ))}
                  </select>
                  {chosen && (
                    <div className="flex items-center gap-2 text-sm">
                      {c.players.find((p) => p.id === chosen)?.image_url && (
                        <img
                          src={
                            c.players.find((p) => p.id === chosen)!.image_url!
                          }
                          className="h-12 w-12 object-contain"
                          alt=""
                        />
                      )}
                      <span>
                        {c.players.find((p) => p.id === chosen)?.name}
                      </span>
                    </div>
                  )}
                </label>
              );
            })}
          </div>
        ) : (
          <div className="space-y-3">
            {c.games
              .filter(
                (g) =>
                  c.kind !== "upset" ||
                  c.underdogs.some((d) => d.game_id === g.id),
              )
              .map((g) => {
                const teams =
                  c.kind === "upset"
                    ? c.underdogs
                        .filter((d) => d.game_id === g.id)
                        .map((d) => d.team)
                    : [g.away_team, g.home_team];
                return (
                  <fieldset
                    key={g.id}
                    className="rounded-lg border border-border p-4"
                  >
                    <legend className="px-1 text-sm font-semibold">
                      {g.away_team} at {g.home_team}
                    </legend>
                    <p className="mb-3 text-xs text-muted-foreground">
                      {deadlineText(g.start_date)} · {g.status}
                      {g.id === c.featured_game_id
                        ? " · Featured tiebreaker game"
                        : ""}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {teams.map((team) => (
                        <button
                          key={team}
                          type="button"
                          className={`min-h-11 rounded-md border px-3 py-2 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-40 ${picks.some((p) => p.game_id === g.id && p.team === team) ? "border-primary bg-primary/15 text-primary" : "border-border"}`}
                          aria-pressed={picks.some(
                            (p) => p.game_id === g.id && p.team === team,
                          )}
                          disabled={
                            c.kind !== "lock" &&
                            picks.length >= requiredPicks &&
                            !picks.some((p) => p.game_id === g.id)
                          }
                          onClick={() => pickGame(g.id, team)}
                        >
                          {picks.some(
                            (p) => p.game_id === g.id && p.team === team,
                          )
                            ? "✓ "
                            : ""}
                          {team}
                          {c.kind === "upset"
                            ? ` · ${c.underdogs.find((d) => d.game_id === g.id && d.team === team)?.points} points`
                            : ""}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                );
              })}
          </div>
        )}
        {c.kind === "slate12" && (
          <label className="block space-y-2">
            <span className="text-sm font-bold">
              Featured game combined final-score prediction
            </span>
            <input
              className="cfb-control block min-h-12 w-40 p-2 text-base"
              type="number"
              min="0"
              max="2147483647"
              step="1"
              aria-label="Featured game total score"
              value={tiebreaker}
              onChange={(e) => {
                setTiebreaker(e.target.value);
                setConfirmation("");
              }}
            />
          </label>
        )}
        <div
          aria-live="polite"
          className="space-y-1 text-sm text-muted-foreground"
        >
          <p>
            {picks.length} / {requiredPicks}{" "}
            {c.kind === "fantasy5" ? "players" : "picks"} selected · Shared
            deadline {deadlineText(c.lock_at)}
          </p>
          <p>
            {submitError ??
              (c.kind === "upset"
                ? "All 3 picks selected. Remove a pick to choose a different game."
                : "Your selections are complete.")}
          </p>
        </div>
        {mutation.isError && (
          <p role="alert" className="text-sm text-red-300">
            {challengeError(mutation.error)} Your choices are preserved. A
            closed deadline cannot be extended.
          </p>
        )}
        {confirmation && (
          <p role="status" className="text-sm text-emerald-300">
            {confirmation}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <Button
            type="submit"
            disabled={
              mutation.isPending || c.state !== "Open" || Boolean(submitError)
            }
          >
            {mutation.isPending
              ? "Saving…"
              : official
                ? "Update Official Entry"
                : "Submit Official Entry"}
          </Button>
          {!official && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setConfirmation("");
                if (!draftError && c.state === "Open" && !mutation.isPending)
                  mutation.mutate(false);
              }}
              disabled={
                mutation.isPending || c.state !== "Open" || Boolean(draftError)
              }
            >
              Save Draft
            </Button>
          )}
        </div>
      </fieldset>
    </form>
  );
}

function Duels({ challenge: c }: { challenge: Challenge }) {
  const { user } = useAuth();
  const membership = useMembership();
  const paidBlocked = membership.enabled && (!membership.data || (membership.data.enforcement_active && !membership.data.features.weekly_challenges));
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [success, setSuccess] = useState("");
  const base = `/weekly-challenges/challenges/${c.id}/duels`;
  const duels = useQuery({
    queryKey: ["weekly-challenges", "duels", user?.id, c.id],
    queryFn: () => apiGet<Duel[]>(base),
    refetchInterval: 30_000,
  });
  const people = useQuery({
    queryKey: ["weekly-challenges", "participants", user?.id, query],
    queryFn: () =>
      apiGet<Participant[]>("/weekly-challenges/participants", { q: query }),
    enabled: query.trim().length >= 2,
  });
  const mutate = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: number;
      action: "invite" | "accept" | "decline";
    }) =>
      apiChallengeWrite<Duel[]>(
        user!.id,
        "POST",
        action === "invite" ? base : `${base}/${id}/${action}`,
        action === "invite" ? { invitee_id: id } : {},
      ),
    onSuccess: (_, v) => {
      setSuccess(
        v.action === "invite"
          ? "Invitation sent."
          : v.action === "accept"
            ? "Ranked duel accepted."
            : "Invitation declined.",
      );
      void client.invalidateQueries({
        queryKey: ["weekly-challenges", "duels", user?.id, c.id],
      });
    },
  });
  return (
    <SurfaceCard className="space-y-4">
      <h2 className="cfb-section-title text-xl">Your Rivalry Duels</h2>
      <p className="text-sm text-muted-foreground">
        Submit your five picks, then invite or accept. Both managers need
        complete entries. Opponent selections stay hidden until the shared
        deadline.
      </p>
      {duels.isPending && <p role="status">Loading invitations…</p>}
      {duels.isError && (
        <p role="alert">
          Could not load invitations.{" "}
          <button className="underline" onClick={() => void duels.refetch()}>
            Retry
          </button>
        </p>
      )}
      {duels.data?.map((d) => (
        <div key={d.id} className="space-y-2 rounded border border-border p-3">
          <p className="text-sm font-bold">
            {d.inviter.display_name} vs {d.invitee.display_name} · {d.status}
          </p>
          {d.outcome && (
            <p className="text-sm">
              {d.outcome.startsWith("winner:")
                ? `Winner: ${Number(d.outcome.split(":")[1]) === d.inviter.user_id ? d.inviter.display_name : d.invitee.display_name}`
                : d.outcome.replace("_", " ")}
            </p>
          )}
          {c.state === "Open" &&
            d.status === "pending" &&
            d.invitee.user_id === user?.id && (
              <div className="flex gap-3">
                <Button
                  disabled={paidBlocked || mutate.isPending || c.entry?.status !== "submitted"}
                  onClick={() => mutate.mutate({ id: d.id, action: "accept" })}
                >
                  Accept Duel
                </Button>
                <Button
                  variant="outline"
                  disabled={mutate.isPending}
                  onClick={() => mutate.mutate({ id: d.id, action: "decline" })}
                >
                  Decline
                </Button>
              </div>
            )}
        </div>
      ))}
      {c.state === "Open" && (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(search.trim());
            }}
            className="flex flex-wrap items-end gap-2"
          >
            <label className="min-w-0 flex-1 text-sm">
              Find a manager
              <input
                className="cfb-control mt-1 block min-h-11 w-full p-2 text-base"
                value={search}
                minLength={2}
                maxLength={80}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Manager name or username"
              />
            </label>
            <Button type="submit" variant="outline">
              Search Managers
            </Button>
          </form>
          {people.isError && <p role="alert">Manager search failed.</p>}
          {query && people.data?.length === 0 && <p>No matching managers.</p>}
          {people.data?.map((p) => (
            <div
              key={p.user_id}
              className="flex items-center justify-between gap-3 border-t border-border py-3"
            >
              <Link
                to={p.profile_url}
                className="flex min-w-0 items-center gap-2 text-sm"
              >
                <ManagerAvatar
                  managerName={p.display_name}
                  avatarUrl={p.avatar_url}
                  size="sm"
                />
                <span className="truncate">{p.display_name}</span>
              </Link>
              <Button
                variant="outline"
                disabled={paidBlocked || mutate.isPending || c.entry?.status !== "submitted"}
                onClick={() =>
                  mutate.mutate({ id: p.user_id, action: "invite" })
                }
              >
                Invite
              </Button>
            </div>
          ))}
        </>
      )}
      {mutate.isError && (
        <p role="alert" className="text-sm text-red-300">
          {challengeError(mutate.error)}
        </p>
      )}
      {success && (
        <p role="status" className="text-sm text-emerald-300">
          {success}
        </p>
      )}
    </SurfaceCard>
  );
}

export function ChallengeResults({ challenge: c }: { challenge: Challenge }) {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["weekly-challenges", "results", user?.id, c.id, CHALLENGE_LEADERBOARD_LIMIT],
    queryFn: () =>
      apiGet<Results>(`/weekly-challenges/challenges/${c.id}/results`, {
        limit: CHALLENGE_LEADERBOARD_LIMIT,
        offset: 0,
      }),
    refetchInterval: 30_000,
  });
  return (
    <SurfaceCard className="space-y-4">
      <h2 className="cfb-section-title text-xl">Top 5</h2>
      <p className="text-sm text-muted-foreground">
        {c.state === "Open"
          ? "Only your own entry is visible before the deadline."
          : "Pending statistics remain Processing. Only final challenge awards count toward season points."}
      </p>
      {query.isPending && <p role="status">Loading results…</p>}
      {query.isError && (
        <p role="alert">
          Results are temporarily unavailable.{" "}
          <button className="underline" onClick={() => void query.refetch()}>
            Retry
          </button>
        </p>
      )}
      {query.data?.data.length === 0 && (
        <p className="text-sm">No submitted results yet.</p>
      )}
      {query.data?.data.slice(0, CHALLENGE_LEADERBOARD_LIMIT).map((row) => (
        <div
          className="flex flex-wrap items-center justify-between gap-3 border-t border-border py-3"
          key={row.entry_id}
        >
          <Link
            className="flex min-w-0 items-center gap-2"
            to={row.participant.profile_url}
          >
            <ManagerAvatar
              managerName={row.participant.display_name}
              avatarUrl={row.participant.avatar_url}
              size="sm"
            />
            <span className="text-sm font-bold">
              {row.rank ? `#${row.rank} · ` : ""}
              {row.participant.display_name}
              {row.participant.user_id === user?.id ? " (You)" : ""}
            </span>
          </Link>
          <div className="text-sm">
            <p>
              {row.challenge_points === null
                ? "Processing"
                : `${row.challenge_points} challenge points`}
            </p>
            {row.raw_points !== null && (
              <p className="text-xs text-muted-foreground">
                {c.kind === "fantasy5" ? "Raw fantasy total" : "Raw result"}:{" "}
                {row.raw_points}
                {row.tiebreaker_error !== null
                  ? ` · Tiebreaker error: ${row.tiebreaker_error}`
                  : ""}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {row.status.replace("_", " ")}
            </p>
          </div>
        </div>
      ))}
    </SurfaceCard>
  );
}

export default function WeeklyChallengeDetail() {
  const { challengeId } = useParams();
  const { user } = useAuth();
  const client = useQueryClient();
  const query = useChallenge(Number(challengeId));
  const state = useChallengeState(query.data);
  const c = query.data ? { ...query.data, state } : undefined;
  if (c && isExperience(c.kind)) return <Navigate to={`/weekly-challenges/experiences/${c.id}`} replace/>;
  return (
    <div className="mx-auto max-w-4xl space-y-5 pb-24 pt-3">
      <Button asChild variant="outline">
        <Link to="/weekly-challenges">All Challenges</Link>
      </Button>
      {query.isPending && <p role="status">Loading challenge…</p>}
      {query.isError && (
        <SurfaceCard>
          <p role="alert">
            Unable to load this challenge. {challengeError(query.error)}
          </p>
          <Button onClick={() => void query.refetch()}>Retry</Button>
        </SurfaceCard>
      )}
      {c && (
        <>
          <WeeklyChallengeSponsor sponsor={c.sponsor} />
          <PageHeader
            eyebrow={c.state}
            title={c.name}
            description={`Shared entry deadline: ${deadlineText(c.lock_at)}`}
          />
          <SurfaceCard className="space-y-3">
            <h2 className="cfb-section-title">Format and eligibility</h2>
            <p className="text-sm leading-relaxed">{c.rules}</p>
            <p className="text-xs text-muted-foreground">
              Rules {c.rules_version}
              {c.scoring_version ? ` · Scoring ${c.scoring_version}` : ""}
            </p>
            {c.scoring_rules && (
              <details>
                <summary className="cursor-pointer text-sm text-primary">
                  Frozen scoring configuration
                </summary>
                <pre className="mt-2 max-h-60 overflow-auto rounded border border-border p-3 text-xs">
                  {JSON.stringify(c.scoring_rules, null, 2)}
                </pre>
              </details>
            )}
          </SurfaceCard>
          {c.state !== "Open" && (
            <SurfaceCard>
              <p className="font-bold">
                {c.state === "Upcoming"
                  ? "Upcoming — entries are not open."
                  : "Closed — entry changes are unavailable."}
              </p>
              {c.settlement_status === "no_contest" && (
                <p className="mt-2 text-sm">
                  No contest — all included games were void. No winner or
                  placement points are awarded.
                </p>
              )}
              {c.cancellation_reason && <p>{c.cancellation_reason}</p>}
              {c.entry && (
                <>
                  <p className="mt-2 text-sm">
                    Your {c.entry.status} entry · revision {c.entry.revision}
                  </p>
                  <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {c.entry.selections.map((p, i) => (
                      <li key={i}>
                        {p.team ??
                          `${p.slot}: ${c.players.find((x) => x.id === p.player_id)?.name ?? `Player ${p.player_id}`}`}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </SurfaceCard>
          )}
          {c.state === "Open" && user && (
            <SurfaceCard>
              <MembershipGate feature="weekly_challenges"><EntryForm
                key={`${user.id}:${c.id}`}
                challenge={c}
                accountId={user.id}
                onSaved={() => {
                  void client.invalidateQueries({
                    queryKey: ["weekly-challenges"],
                  });
                }}
              /></MembershipGate>
            </SurfaceCard>
          )}
          {c.kind === "duels" && <Duels challenge={c} />}
          <ChallengeResults challenge={c} />
        </>
      )}
    </div>
  );
}
