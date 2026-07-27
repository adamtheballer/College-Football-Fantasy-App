import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Clock3, Lock, Trophy, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSaveSaturdayPick, useSaturdayPickContest } from "@/hooks/use-saturday-pick";

const formatPoints = (value: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";

const formatKickoff = (value: string) => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Kickoff TBD"
    : parsed.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

export default function SaturdayPick6() {
  const contestQuery = useSaturdayPickContest();
  const savePick = useSaveSaturdayPick();
  const contest = contestQuery.data;
  const [pendingPickId, setPendingPickId] = useState<number | null>(null);
  const selectedPickId = pendingPickId ?? contest?.entry?.selected_pick_player_id ?? null;
  const isOpen = contest?.status === "OPEN";
  const winnerIds = useMemo(() => new Set(contest?.winning_player_ids ?? []), [contest?.winning_player_ids]);

  if (contestQuery.isLoading) {
    return <div className="mx-auto max-w-7xl py-20 text-center text-sm font-black uppercase tracking-[0.2em] text-cfb-text-muted">Loading Saturday Pick 6…</div>;
  }
  if (!contest) {
    return (
      <div className="mx-auto max-w-4xl py-20 text-center">
        <p className="cfb-micro-label text-cfb-brand">Saturday Pick 6</p>
        <h1 className="mt-3 text-4xl font-black text-cfb-text-primary">Coming next week</h1>
        <p className="mx-auto mt-4 max-w-xl text-cfb-text-secondary">Six featured players. One position. One weekly prediction.</p>
        <Button asChild className="mt-7"><Link to="/">Back to dashboard</Link></Button>
      </div>
    );
  }

  const submit = async () => {
    if (!selectedPickId || !isOpen) return;
    await savePick.mutateAsync({ contestId: contest.id, selectedPickPlayerId: selectedPickId });
    setPendingPickId(null);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-7 pb-20 pt-5">
      <section className="relative overflow-hidden rounded-[2rem] border border-cfb-brand/30 bg-gradient-to-br from-cfb-brand/[0.22] via-cfb-surface to-cfb-surface p-6 sm:p-9">
        <div className="absolute -right-12 -top-16 h-48 w-72 rotate-[-18deg] rounded-full bg-cfb-pink/25 blur-3xl" aria-hidden="true" />
        <p className="cfb-micro-label text-cfb-brand">Saturday Pick 6 {contest.sponsor ? `presented by ${contest.sponsor.name}` : ""}</p>
        <div className="relative mt-3 flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <h1 className="text-4xl font-black italic text-cfb-text-primary sm:text-5xl">{contest.contest_position} WEEK</h1>
            <p className="mt-3 max-w-2xl text-lg font-bold text-cfb-text-secondary">Which featured {contest.contest_position === "QB" ? "quarterback" : contest.contest_position} will score the most fantasy points this week?</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-xl border border-cfb-border-strong bg-slate-950/45 px-4 py-3 text-xs font-black uppercase tracking-[0.14em] text-cfb-text-primary">
            {isOpen ? <Clock3 className="h-4 w-4 text-cfb-gold" /> : <Lock className="h-4 w-4 text-cfb-pink" />}
            {isOpen ? `Locks ${formatKickoff(contest.lock_at)}` : contest.status}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {contest.players.map((player) => {
          const selected = selectedPickId === player.id;
          const isWinner = winnerIds.has(player.player_id);
          return (
            <article key={player.id} className={`rounded-3xl border p-5 transition ${selected ? "border-cfb-brand bg-cfb-brand/[0.14] shadow-[0_0_28px_rgba(59,130,246,0.15)]" : "border-cfb-border-subtle bg-cfb-surface"}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-cfb-surface-raised text-cfb-brand"><UserRound className="h-6 w-6" /></div><div className="min-w-0"><h2 className="truncate text-xl font-black text-cfb-text-primary">{player.player_name}</h2><p className="mt-1 text-xs font-black uppercase tracking-[0.14em] text-cfb-text-muted">{player.school} • {player.canonical_position}</p></div></div>
                {isWinner ? <Trophy className="h-5 w-5 shrink-0 text-cfb-gold" aria-label="Weekly winner" /> : null}
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3 text-sm"><div><p className="cfb-micro-label">Opponent</p><p className="mt-1 font-black text-cfb-text-primary">vs. {player.opponent}</p></div><div><p className="cfb-micro-label">{contest.status === "FINAL" ? "Final" : "Projection"}</p><p className="mt-1 text-xl font-black tabular-nums text-cfb-brand">{formatPoints(contest.status === "FINAL" ? player.final_points : player.projected_points)}</p></div></div>
              <p className="mt-4 text-xs font-bold text-cfb-text-secondary">{formatKickoff(player.game_time)} • {player.scoring_status.replace(/_/g, " ")}</p>
              {isOpen ? <Button className="mt-5 w-full" variant={selected ? "default" : "outline"} onClick={() => setPendingPickId(player.id)}>{selected ? <><Check className="mr-2 h-4 w-4" /> Your Pick</> : `Pick ${player.player_name.split(" ").at(-1)}`}</Button> : null}
            </article>
          );
        })}
      </section>

      {isOpen ? <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-cfb-border-subtle bg-cfb-surface p-5"><p className="text-sm font-bold text-cfb-text-secondary">One entry per contest. You can change your selection until the published lock time.</p><Button disabled={!selectedPickId || savePick.isPending} onClick={submit}>{savePick.isPending ? "Saving…" : contest.entry ? "Update Pick" : "Lock In Pick"}</Button></section> : null}
      {contest.entry ? <section className="rounded-2xl border border-cfb-success/30 bg-cfb-success/[0.10] p-5 text-sm font-black text-cfb-text-primary">{contest.status === "FINAL" ? (contest.entry.is_winner ? "YOU GOT IT RIGHT" : "Results are in — next week’s Saturday Pick 6 opens soon.") : "Your Saturday Pick 6 selection is locked in."}{contest.sponsor?.reward_unlocked && contest.sponsor.code ? ` Reward code: ${contest.sponsor.code}` : ""}</section> : null}
    </div>
  );
}
