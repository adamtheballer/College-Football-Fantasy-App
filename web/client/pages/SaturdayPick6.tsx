import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Clock3, Copy, Lock, Radio, Trophy, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { type SaturdayPickPlayer, useSaveSaturdayPick, useSaturdayPickContest } from "@/hooks/use-saturday-pick";

const formatPoints = (value: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";

const formatKickoff = (value: string) => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Kickoff TBD"
    : parsed.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

export const statusLabel = (status: string) => status.replace(/_/g, " ");

export const displayPoints = (player: SaturdayPickPlayer, contestStatus: string) => {
  if (contestStatus === "FINAL") return player.final_points;
  return player.live_points ?? player.projected_points;
};

function useCountdown(lockAt: string | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  const remaining = lockAt ? Math.max(0, new Date(lockAt).getTime() - now) : 0;
  const hours = Math.floor(remaining / 3_600_000);
  const minutes = Math.floor((remaining % 3_600_000) / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1_000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function SaturdayPick6() {
  const contestQuery = useSaturdayPickContest();
  const savePick = useSaveSaturdayPick();
  const contest = contestQuery.data;
  const [pendingPickId, setPendingPickId] = useState<number | null>(null);
  const countdown = useCountdown(contest?.lock_at);
  const selectedPickId = pendingPickId ?? contest?.entry?.selected_pick_player_id ?? null;
  const isOpen = contest?.status === "OPEN";
  const isResults = Boolean(contest && ["SCORING", "PROVISIONAL", "FINAL"].includes(contest.status));
  const winnerIds = useMemo(() => new Set(contest?.winning_player_ids ?? []), [contest?.winning_player_ids]);
  const players = useMemo(() => {
    if (!contest) return [];
    const rows = [...contest.players];
    return isResults
      ? rows.sort((left, right) => (displayPoints(right, contest.status) ?? -1) - (displayPoints(left, contest.status) ?? -1))
      : rows;
  }, [contest, isResults]);

  if (contestQuery.isLoading) {
    return <div className="mx-auto max-w-7xl py-20 text-center text-sm font-black uppercase tracking-[0.2em] text-cfb-text-muted">Loading Saturday Pick 6…</div>;
  }
  if (!contest) {
    return (
      <div className="mx-auto max-w-4xl py-20 text-center">
        <p className="cfb-micro-label text-cfb-brand">Saturday Pick 6</p>
        <h1 className="mt-3 text-4xl font-black text-cfb-text-primary">Coming next week</h1>
        <p className="mx-auto mt-4 max-w-xl text-cfb-text-secondary">Six featured players. One weekly prediction. One prize.</p>
        <Button asChild className="mt-7"><Link to="/">Back to dashboard</Link></Button>
      </div>
    );
  }

  const selectedPlayer = contest.players.find((player) => player.id === selectedPickId) ?? null;
  const submit = async () => {
    if (!selectedPickId || !isOpen) return;
    await savePick.mutateAsync({ contestId: contest.id, selectedPickPlayerId: selectedPickId });
    setPendingPickId(null);
  };
  const copySponsorCode = async () => {
    if (contest.sponsor?.code) await navigator.clipboard?.writeText(contest.sponsor.code);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-7 pb-20 pt-5">
      <section className="relative overflow-hidden rounded-[2rem] border border-cyan-300/30 bg-[radial-gradient(circle_at_20%_20%,rgba(14,165,233,0.22),transparent_32%),linear-gradient(135deg,rgba(15,23,42,0.98),rgba(30,41,59,0.96),rgba(8,47,73,0.88))] p-6 shadow-[0_0_60px_rgba(14,165,233,0.14)] sm:p-9">
        <div aria-hidden="true" className="absolute -left-12 top-16 h-3 w-72 rotate-[-18deg] rounded-full bg-cyan-200/25 blur-sm" />
        <div aria-hidden="true" className="absolute -right-16 -top-14 h-52 w-72 rotate-[-18deg] rounded-full bg-cfb-pink/20 blur-3xl" />
        <div className="relative flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-cfb-gold/45 bg-cfb-gold/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.2em] text-yellow-100"><Trophy className="h-4 w-4" /> Saturday Pick 6</span>
              <span className="cfb-micro-label text-cyan-200">Week {contest.week_number} · {contest.contest_position} Week</span>
            </div>
            <h1 className="mt-5 font-display text-4xl font-black italic tracking-[-0.05em] text-cfb-text-primary sm:text-6xl">{isResults ? "LIVE RESULTS" : "MAKE YOUR PICK"}</h1>
            <p className="mt-4 max-w-2xl text-base font-bold leading-7 text-cfb-text-secondary sm:text-lg">Which featured running back will score the most fantasy points this week?</p>
          </div>
          <div className="flex flex-wrap items-stretch gap-3">
            {contest.sponsor ? <div className="flex max-w-xs items-center gap-3 rounded-2xl border border-cyan-200/25 bg-slate-950/45 p-3"><div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/15 bg-cyan-100/10 text-xs font-black text-cyan-100">{contest.sponsor.logo_url ? <img src={contest.sponsor.logo_url} alt={`${contest.sponsor.name} logo`} className="h-full w-full object-contain" /> : contest.sponsor.name.slice(0, 2).toUpperCase()}</div><div><p className="cfb-micro-label text-cyan-200">Presented by</p><p className="mt-1 text-sm font-black text-white">{contest.sponsor.name}</p></div></div> : null}
            <div className="rounded-2xl border border-cfb-border-strong bg-slate-950/55 px-5 py-3 text-right"><p className="cfb-micro-label text-cfb-text-muted">{isOpen ? "Locks in" : "Contest status"}</p><p className="mt-1 font-display text-2xl font-black tabular-nums text-cyan-100">{isOpen ? countdown : statusLabel(contest.status)}</p></div>
          </div>
        </div>
      </section>

      {contest.status === "FINAL" ? <section className="rounded-3xl border border-cfb-gold/35 bg-cfb-gold/[0.08] p-5 text-cfb-text-primary"><p className="cfb-micro-label text-yellow-100">Saturday Pick 6 winner</p><p className="mt-2 text-2xl font-black">{winnerIds.size > 1 ? "Two or more players tied for the top score" : `${players[0]?.player_name ?? "Winner"} led the field`}</p>{contest.entry ? <p className="mt-2 font-bold text-cfb-text-secondary">{contest.entry.is_winner ? "YOU GOT IT RIGHT" : `Your pick finished ${Math.max(1, players.findIndex((player) => player.id === contest.entry?.selected_pick_player_id) + 1)}${"th"}.`}</p> : null}</section> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {players.map((player, index) => {
          const selected = selectedPickId === player.id;
          const isWinner = winnerIds.has(player.player_id);
          const shownPoints = displayPoints(player, contest.status);
          const pointLabel = contest.status === "FINAL" ? "Final points" : isResults ? "Live points" : "Projected points";
          return (
            <article key={player.id} className={`relative overflow-hidden rounded-3xl border p-5 transition ${selected ? "border-cyan-200 bg-cyan-300/[0.12] shadow-[0_0_30px_rgba(34,211,238,0.18)]" : "border-cfb-border-subtle bg-cfb-surface"}`}>
              {isResults ? <span className="absolute right-4 top-4 text-xs font-black tabular-nums text-cyan-100">#{index + 1}</span> : null}
              <div className="flex min-w-0 items-center gap-3 pr-8"><div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/12 bg-cfb-surface-raised text-cfb-brand">{player.image_url ? <img src={player.image_url} alt={player.player_name} className="h-full w-full object-cover" /> : <UserRound className="h-7 w-7" />}</div><div className="min-w-0"><h2 className="truncate text-xl font-black text-cfb-text-primary">{player.player_name}</h2><p className="mt-1 text-xs font-black uppercase tracking-[0.14em] text-cfb-text-muted">{player.school} · {player.canonical_position}</p></div></div>
              {isWinner ? <Trophy className="absolute right-4 top-4 h-5 w-5 text-cfb-gold" aria-label="Weekly winner" /> : null}
              <div className="mt-5 grid grid-cols-2 gap-3 text-sm"><div><p className="cfb-micro-label">Opponent</p><p className="mt-1 font-black text-cfb-text-primary">vs. {player.opponent}</p></div><div><p className="cfb-micro-label">{pointLabel}</p><p className="mt-1 text-xl font-black tabular-nums text-cyan-100">{formatPoints(shownPoints)}</p></div></div>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs font-bold text-cfb-text-secondary"><span>{formatKickoff(player.game_time)}</span><span className={player.scoring_status === "DATA_DELAYED" ? "text-amber-200" : "text-cyan-100"}>{player.scoring_status === "LIVE" ? <Radio className="mr-1 inline h-3.5 w-3.5" /> : null}{statusLabel(player.scoring_status)}</span></div>
              {isOpen ? <Button className="mt-5 w-full" variant={selected ? "default" : "outline"} onClick={() => setPendingPickId(player.id)}>{selected ? <><Check className="mr-2 h-4 w-4" /> Your Pick</> : "Choose player"}</Button> : null}
            </article>
          );
        })}
      </section>

      {isOpen ? <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-cfb-border-subtle bg-cfb-surface p-5"><div><p className="text-sm font-black text-cfb-text-primary">{selectedPlayer ? `You selected ${selectedPlayer.player_name}.` : "Choose one featured running back."}</p><p className="mt-1 text-sm font-bold text-cfb-text-secondary">You can change your choice until the published lock time.</p></div><Button disabled={!selectedPickId || savePick.isPending} onClick={submit}>{savePick.isPending ? "Saving…" : contest.entry ? "Update Pick" : "Lock In Pick"}</Button></section> : null}

      {contest.entry && contest.sponsor ? <section className={`rounded-3xl border p-6 ${contest.sponsor.reward_unlocked ? "border-cfb-success/40 bg-cfb-success/[0.10]" : "border-cyan-200/20 bg-cyan-200/[0.06]"}`}><p className="cfb-micro-label text-cyan-100">{contest.sponsor.reward_unlocked ? "Reward unlocked" : "This week’s reward"}</p><h2 className="mt-2 text-2xl font-black text-cfb-text-primary">{contest.sponsor.name}</h2><p className="mt-2 font-bold text-cfb-text-secondary">{contest.sponsor.offer_text ?? "Make your pick to compete for this week’s sponsor reward."}</p>{contest.sponsor.reward_unlocked && contest.sponsor.code ? <div className="mt-5 flex flex-wrap items-center gap-3"><code className="rounded-xl border border-white/15 bg-slate-950/55 px-4 py-3 font-black tracking-[0.16em] text-cyan-100">{contest.sponsor.code}</code><Button variant="outline" onClick={copySponsorCode}><Copy className="mr-2 h-4 w-4" /> Copy Code</Button>{contest.sponsor.url ? <Button asChild><a href={contest.sponsor.url} target="_blank" rel="noreferrer">Visit Sponsor</a></Button> : null}</div> : <p className="mt-4 text-sm font-bold text-cfb-text-secondary">Winner-only reward details are revealed after final scoring.</p>}</section> : null}
    </div>
  );
}
