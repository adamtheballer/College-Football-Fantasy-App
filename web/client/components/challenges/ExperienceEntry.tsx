import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { SurfaceCard } from "@/components/fantasy";
import { apiChallengeWrite } from "@/lib/api";
import {
  type Challenge,
  type Entry,
  type Pick,
  challengeError,
  deadlineText,
  useChallengeState,
} from "@/hooks/use-weekly-challenges";

export const MILLIONAIRE_SLOTS = [
  "QB",
  "RB",
  "WR1",
  "WR2",
  "TE",
  "FLEX",
] as const;
const slotPosition = (slot: string) => (slot.startsWith("WR") ? "WR" : slot);
export function experienceEntryError(
  c: Challenge,
  picks: Pick[],
  complete: boolean,
): string | null {
  const x = c.experience;
  if (!x) return "Competition configuration is unavailable.";
  if (c.kind === "millionaire") {
    if (picks.length > 6 || (complete && picks.length !== 6))
      return "Fill all six lineup slots.";
    if (
      new Set(picks.map((p) => p.player_id)).size !== picks.length ||
      new Set(picks.map((p) => p.slot)).size !== picks.length
    )
      return "Choose six unique players in distinct slots.";
    const pool = new Map(c.players.map((p) => [p.id, p]));
    const salaries = new Map(x.salaries.map((p) => [p.player_id, p.salary]));
    let total = 0;
    for (const p of picks) {
      const player = pool.get(p.player_id!);
      const salary = salaries.get(p.player_id!);
      if (
        !player ||
        x.ineligible_player_ids.includes(p.player_id!) ||
        salary === undefined ||
        !MILLIONAIRE_SLOTS.includes(
          p.slot as (typeof MILLIONAIRE_SLOTS)[number],
        ) ||
        p.team !== undefined ||
        p.game_id !== undefined ||
        (p.slot === "FLEX"
          ? !["RB", "WR", "TE"].includes(player.position)
          : player.position !== slotPosition(p.slot!))
      )
        return "Choose an eligible salaried player in each required slot.";
      total += salary;
    }
    if (Math.round(total * 100) > 10000)
      return "Your lineup exceeds the $100 virtual budget.";
  } else {
    const max =
      c.kind === "creator" ? 10 : c.kind === "survivor" ? 1 : c.games.length;
    if (
      picks.length > max ||
      (complete &&
        (c.kind === "fanwars" ? picks.length === 0 : picks.length !== max))
    )
      return c.kind === "fanwars"
        ? "Choose at least one eligible game."
        : `Choose exactly ${max} ${max === 1 ? "pick" : "picks"}.`;
    if (new Set(picks.map((p) => p.game_id)).size !== picks.length)
      return "Choose only one side of each game.";
    if (
      picks.some((p) => {
        const g = c.games.find((g) => g.id === p.game_id);
        return (
          !g ||
          p.player_id !== undefined ||
          p.slot !== undefined ||
          ![g.home_team, g.away_team].includes(p.team!)
        );
      })
    )
      return "Choose a team from the published slate.";
    if (c.kind === "fanwars" && !x.allegiance)
      return "Choose the school you represent first.";
    if (
      c.kind === "survivor" &&
      picks.some((p) =>
        x.previous_picks.some(
          (old) =>
            old.week !== x.week &&
            old.team?.trim().toLowerCase() === p.team?.trim().toLowerCase(),
        ),
      )
    )
      return "You already used this team in this series.";
  }
  return null;
}

export function useServerClock(serverNow: string) {
  const [anchor, setAnchor] = useState(() => ({
    time: Date.parse(serverNow),
    monotonic: performance.now(),
  }));
  const [, setTick] = useState(0);
  useEffect(
    () =>
      setAnchor({ time: Date.parse(serverNow), monotonic: performance.now() }),
    [serverNow],
  );
  useEffect(() => {
    const timer = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return anchor.time + performance.now() - anchor.monotonic;
}

export function ExperienceEntry({
  challenge: c,
  accountId,
  onSaved,
}: {
  challenge: Challenge;
  accountId: number;
  onSaved: () => void;
}) {
  const x = c.experience!;
  const state = useChallengeState(c);
  const time = useServerClock(c.server_now);
  const key = `cffb_experience_draft_${accountId}_${c.id}_${c.version}`;
  const [initial] = useState(() => {
    try {
      const s = JSON.parse(sessionStorage.getItem(key) ?? "null");
      if (
        s &&
        s.revision === (c.entry?.revision ?? 0) &&
        Array.isArray(s.picks)
      )
        return s as { picks: Pick[]; revision: number };
    } catch {
      /* Optional recovery only. */
    }
    return {
      picks: c.entry?.selections ?? [],
      revision: c.entry?.revision ?? 0,
    };
  });
  const [picks, setPicks] = useState<Pick[]>(initial.picks),
    [revision, setRevision] = useState(initial.revision),
    [notice, setNotice] = useState("");
  const [slot, setSlot] = useState<(typeof MILLIONAIRE_SLOTS)[number] | null>(
      null,
    ),
    [search, setSearch] = useState(""),
    [school, setSchool] = useState(""),
    [opponent, setOpponent] = useState(""),
    [salaryMax, setSalaryMax] = useState("100"),
    [sort, setSort] = useState("projection");
  const prices = useMemo(
    () => new Map(x.salaries.map((s) => [s.player_id, s.salary])),
    [x.salaries],
  );
  const spent =
    Math.round(
      picks.reduce((n, p) => n + (prices.get(p.player_id!) ?? 0), 0) * 100,
    ) / 100;
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify({ picks, revision }));
    } catch {
      /* Server remains authoritative. */
    }
  }, [key, picks, revision]);
  const mutation = useMutation({
    mutationFn: (submit: boolean) => {
      const error = experienceEntryError(c, picks, submit);
      if (error) throw new Error(error);
      return apiChallengeWrite<Entry>(
        accountId,
        "PUT",
        `/weekly-challenges/challenges/${c.id}/entry`,
        {
          expected_revision: revision,
          submit,
          selections: picks,
          tiebreaker: null,
        },
      );
    },
    onSuccess: (e) => {
      setRevision(e.revision);
      setNotice(
        e.status === "submitted"
          ? "Your official entry is submitted."
          : "Draft saved. Submit before the deadline to compete.",
      );
      onSaved();
    },
    onError: () => onSaved(),
  });
  const disabled = mutation.isPending || state !== "Open";
  const currentSlot = picks.find((p) => p.slot === slot);
  const available =
    100 - spent + (prices.get(currentSlot?.player_id ?? 0) ?? 0);
  const filtered = c.players
    .filter((p) => {
      const g = c.games.find((g) => g.id === p.game_id);
      return (
        slot &&
        (slot === "FLEX"
          ? ["RB", "WR", "TE"].includes(p.position)
          : p.position === slotPosition(slot)) &&
        p.name.toLowerCase().includes(search.toLowerCase()) &&
        (!school || p.school === school) &&
        (!opponent ||
          `${g?.home_team} ${g?.away_team}`
            .toLowerCase()
            .includes(opponent.toLowerCase())) &&
        (prices.get(p.id) ?? Infinity) <= Number(salaryMax)
      );
    })
    .sort((a, b) =>
      sort === "salary-asc"
        ? (prices.get(a.id) ?? 0) - (prices.get(b.id) ?? 0)
        : sort === "salary-desc"
          ? (prices.get(b.id) ?? 0) - (prices.get(a.id) ?? 0)
          : sort === "name"
            ? a.name.localeCompare(b.name)
            : (x.projections[b.id] ?? -Infinity) -
                (x.projections[a.id] ?? -Infinity) ||
              a.name.localeCompare(b.name),
    );
  const change = (next: Pick[]) => {
    setPicks(next);
    setNotice("");
    mutation.reset();
  };
  const gameLocked = (id: number) =>
    x.locked_game_ids.includes(id) ||
    (c.games.find((g) => g.id === id)?.start_date
      ? time >= Date.parse(c.games.find((g) => g.id === id)!.start_date!)
      : true);
  const chooseGame = (id: number, team: string) => {
    if (disabled || (c.kind === "fanwars" && gameLocked(id))) return;
    const selected = picks.some((p) => p.game_id === id && p.team === team);
    change(
      c.kind === "survivor"
        ? selected
          ? []
          : [{ game_id: id, team }]
        : [
            ...picks.filter((p) => p.game_id !== id),
            ...(selected ? [] : [{ game_id: id, team }]),
          ],
    );
  };
  const draftError = experienceEntryError(c, picks, false),
    submitError = experienceEntryError(c, picks, true);
  return (
    <SurfaceCard className="space-y-5">
      <h2 className="cfb-section-title text-xl">
        {c.kind === "millionaire"
          ? "Your $100 Lineup"
          : c.kind === "survivor"
            ? "Your Survivor Pick"
            : "Your Predictions"}
      </h2>
      {c.kind === "millionaire" ? (
        <>
          <div
            className="grid grid-cols-3 gap-2"
            role="region"
            aria-label="Virtual salary budget"
          >
            {[
              ["Budget", 100],
              ["Spent", spent],
              ["Remaining", 100 - spent],
            ].map(([label, value]) => (
              <div key={label} className="rounded border border-border p-3">
                <p className="cfb-micro-label">{label}</p>
                <p className="mt-2 text-xl font-black">${value}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Virtual credits only. Free entry; no cash payout.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {MILLIONAIRE_SLOTS.map((s) => {
              const pick = picks.find((p) => p.slot === s);
              const player = c.players.find((p) => p.id === pick?.player_id);
              return (
                <div key={s} className="rounded border border-border p-3">
                  <p className="cfb-micro-label">
                    {s.startsWith("WR") ? `WR ${s.slice(2)}` : s}
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={disabled}
                    onClick={() => setSlot(s)}
                    aria-label={`${player ? "Change" : "Choose"} ${s.startsWith("WR") ? `WR ${s.slice(2)}` : s} player`}
                    className="mt-2 h-auto min-h-14 w-full justify-start whitespace-normal text-left"
                  >
                    {player ? (
                      <span>
                        {player.name}
                        <span className="block text-xs text-muted-foreground">
                          {player.school} · ${prices.get(player.id)} ·{" "}
                          {x.projections[player.id] === undefined
                            ? "Projection pending"
                            : `${x.projections[player.id].toFixed(1)} proj`}
                        </span>
                      </span>
                    ) : (
                      "Choose player"
                    )}
                  </Button>
                  {player && (
                    <button
                      type="button"
                      disabled={disabled}
                      className="mt-2 min-h-11 text-xs text-primary underline"
                      onClick={() => change(picks.filter((p) => p.slot !== s))}
                    >
                      Remove {player.name}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
          <Dialog
            open={slot !== null}
            onOpenChange={(open) => {
              if (!open) setSlot(null);
            }}
          >
            <DialogContent className="flex max-h-[85dvh] max-w-2xl flex-col overflow-hidden">
              <DialogHeader>
                <DialogTitle>
                  Select {slot?.startsWith("WR") ? "WR" : slot}
                </DialogTitle>
                <DialogDescription>
                  ${available.toFixed(2)} available for this slot. Salaries are
                  frozen for the week.
                </DialogDescription>
              </DialogHeader>
              <div className="grid shrink-0 gap-2 sm:grid-cols-2">
                <input
                  aria-label="Search salary players"
                  className="cfb-control min-h-11 p-2 text-base"
                  placeholder="Search players"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <select
                  aria-label="School"
                  className="cfb-control min-h-11 p-2 text-base"
                  value={school}
                  onChange={(e) => setSchool(e.target.value)}
                >
                  <option value="">All schools</option>
                  {[...new Set(c.players.map((p) => p.school))]
                    .sort()
                    .map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                </select>
                <input
                  aria-label="Opponent"
                  className="cfb-control min-h-11 p-2 text-base"
                  placeholder="Opponent"
                  value={opponent}
                  onChange={(e) => setOpponent(e.target.value)}
                />
                <label className="text-xs">
                  Maximum salary
                  <input
                    aria-label="Maximum salary"
                    type="number"
                    min="1"
                    max="100"
                    className="cfb-control ml-2 min-h-11 w-20 p-2 text-base"
                    value={salaryMax}
                    onChange={(e) => setSalaryMax(e.target.value)}
                  />
                </label>
                <select
                  aria-label="Sort salary players"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="cfb-control min-h-11 p-2 text-base"
                >
                  <option value="projection">Fantasy projection</option>
                  <option value="salary-asc">Salary: low to high</option>
                  <option value="salary-desc">Salary: high to low</option>
                  <option value="name">Player name</option>
                </select>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setSalaryMax(String(available))}
                >
                  Within available budget
                </Button>
              </div>
              <div className="min-h-0 space-y-2 overflow-auto">
                {filtered.length === 0 && (
                  <p className="py-6 text-sm">
                    No eligible players match these filters.
                  </p>
                )}
                {filtered.map((p) => {
                  const used = picks.some(
                    (v) => v.player_id === p.id && v.slot !== slot,
                  );
                  const ineligible = x.ineligible_player_ids.includes(p.id);
                  const over = (prices.get(p.id) ?? Infinity) > available;
                  const g = c.games.find((g) => g.id === p.game_id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      disabled={disabled || used || over || ineligible}
                      className="flex min-h-16 w-full items-center justify-between gap-3 rounded border border-border p-3 text-left disabled:opacity-40"
                      onClick={() => {
                        if (slot) {
                          change([
                            ...picks.filter((v) => v.slot !== slot),
                            { slot, player_id: p.id },
                          ]);
                          setSlot(null);
                        }
                      }}
                    >
                      <span className="min-w-0 text-sm font-bold">
                        {p.name}
                        <span className="block text-xs font-normal text-muted-foreground">
                          {p.position} · {p.school} · {g?.away_team} at{" "}
                          {g?.home_team}
                        </span>
                        <span className="block text-xs font-normal text-muted-foreground">
                          {deadlineText(g?.start_date ?? null)} ·{" "}
                          {ineligible
                            ? "No longer eligible"
                            : used
                              ? "Already selected"
                              : over
                                ? "Over available budget"
                                : x.projections[p.id] === undefined
                                  ? "Projection pending"
                                  : `${x.projections[p.id].toFixed(1)} projected pts`}
                        </span>
                      </span>
                      <span className="shrink-0 font-black">
                        ${prices.get(p.id)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </DialogContent>
          </Dialog>
        </>
      ) : (
        <div className="space-y-3">
          {c.games.map((g) => {
            const lock = c.kind === "fanwars" && gameLocked(g.id);
            return (
              <fieldset key={g.id} className="rounded border border-border p-3">
                <legend className="px-1 text-sm font-bold">
                  {g.away_team} at {g.home_team}
                </legend>
                <p className="mb-3 text-xs text-muted-foreground">
                  {deadlineText(g.start_date)} ·{" "}
                  {lock ? "Pick locked" : (g.status ?? "Status pending")}
                  {g.home_points !== null && g.away_points !== null
                    ? ` · ${g.away_points}–${g.home_points}`
                    : ""}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {[g.away_team, g.home_team].map((team) => {
                    const used =
                      c.kind === "survivor" &&
                      x.previous_picks.some(
                        (p) =>
                          p.week !== x.week &&
                          p.team?.trim().toLowerCase() ===
                            team.trim().toLowerCase(),
                      );
                    return (
                      <Button
                        key={team}
                        type="button"
                        className="h-auto min-h-12 whitespace-normal"
                        variant={
                          picks.some(
                            (p) => p.game_id === g.id && p.team === team,
                          )
                            ? "default"
                            : "outline"
                        }
                        aria-pressed={picks.some(
                          (p) => p.game_id === g.id && p.team === team,
                        )}
                        disabled={disabled || lock || used}
                        onClick={() => chooseGame(g.id, team)}
                      >
                        {team}
                        {used ? " · Used" : ""}
                        {lock ? " · Locked" : ""}
                      </Button>
                    );
                  })}
                </div>
              </fieldset>
            );
          })}
        </div>
      )}
      <p className="text-sm font-bold">
        {picks.length} selected ·{" "}
        {c.kind === "fanwars" ? "Individual kickoff locks" : "Global lock"}:{" "}
        {deadlineText(c.lock_at)}
      </p>
      {submitError && (
        <p className="text-sm text-muted-foreground">{submitError}</p>
      )}
      {notice && (
        <p role="status" className="text-sm text-emerald-300">
          {notice}
        </p>
      )}
      {mutation.isError && (
        <div role="alert" className="text-sm text-red-300">
          <p>{challengeError(mutation.error)}</p>
          <Button
            type="button"
            variant="outline"
            className="mt-3"
            onClick={() => {
              setPicks(c.entry?.selections ?? []);
              setRevision(c.entry?.revision ?? 0);
              mutation.reset();
              setNotice("Saved entry loaded.");
            }}
          >
            Load saved entry
          </Button>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="outline"
          disabled={disabled || !!draftError || c.entry?.status === "submitted"}
          onClick={() => mutation.mutate(false)}
        >
          Save Draft
        </Button>
        <Button
          type="button"
          disabled={disabled || !!submitError}
          onClick={() => mutation.mutate(true)}
        >
          {mutation.isPending
            ? "Saving…"
            : c.entry?.status === "submitted"
              ? "Update Official Entry"
              : "Submit Entry"}
        </Button>
      </div>
    </SurfaceCard>
  );
}
