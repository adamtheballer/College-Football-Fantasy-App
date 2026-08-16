import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, CircleX, Clock3, Copy, Lock, Radio, Trophy, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SkeletonState } from "@/components/states";
import { type SaturdayPickPlayer, useSaveSaturdayPick, useSaturdayPickContest } from "@/hooks/use-saturday-pick";
import { getSaturdayPickSponsorLogo, saturdayPick6Sponsor } from "@/lib/saturday-pick-sponsor";

export const SATURDAY_PICK_6_COMING_SOON_MESSAGE =
  "Week 1 picks are coming soon. Six featured players will be available once weekly projections are published.";

export const SATURDAY_PICK_6_HOW_IT_WORKS =
  "How it works: Choose one of six featured players before the first kickoff. If your player scores the most fantasy points that week, you unlock that week's featured brand discount code.";

const formatPoints = (value: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";

const formatKickoff = (value: string) => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Kickoff TBD"
    : parsed.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};

export const statusLabel = (status: string) => status.replace(/_/g, " ");

export const positionLabel = (position: SaturdayPickPlayer["canonical_position"]) => ({
  QB: "quarterback",
  RB: "running back",
  WR: "wide receiver",
  TE: "tight end",
}[position]);

export const pickConfirmationMessage = (playerName: string) =>
  `Your pick is in. Follow ${playerName} this Saturday.`;

export const lockDeadlineMessage = (playerName: string, lockAt: string) => {
  const parsed = new Date(lockAt);
  if (Number.isNaN(parsed.getTime())) {
    return `Your pick can be changed until ${playerName}'s game begins. Submit before kickoff; then it will lock.`;
  }
  const time = parsed.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const date = parsed.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  return `Your pick can be changed until ${playerName}'s game starts at ${time} on ${date}. Pick before kickoff; then it will lock.`;
};

export const displayPoints = (player: SaturdayPickPlayer, contestStatus: string) => {
  if (contestStatus === "FINAL") return player.final_points;
  return player.live_points ?? player.projected_points;
};

export const shouldRevealSponsorReward = (
  contestStatus: string,
  entry: { is_winner: boolean } | null | undefined,
) => contestStatus === "FINAL" && entry?.is_winner === true;

export const isSaturdayPick6ComingSoon = (
  contest: { status: string; players: SaturdayPickPlayer[] } | null | undefined,
) =>
  !contest ||
  contest.players.length === 0 ||
  ["DRAFT", "COMING_SOON"].includes(contest.status);

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
  return {
    value: `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`,
    expired: Boolean(lockAt) && remaining === 0,
  };
}

type SaturdayPick6Props = {
  embedded?: boolean;
};

function SaturdayPick6ComingSoon({ embedded }: SaturdayPick6Props) {
  return (
    <section className={embedded ? "rounded-xl border border-cfb-border-subtle bg-cfb-surface p-6 text-center" : "mx-auto max-w-4xl py-20 text-center"}>
      <p className="cfb-micro-label text-cfb-brand">Saturday Pick 6</p>
      <h1 className="mt-3 text-4xl font-black text-cfb-text-primary">Saturday Pick 6</h1>
      <p className="mx-auto mt-4 max-w-xl text-cfb-text-secondary">{SATURDAY_PICK_6_COMING_SOON_MESSAGE}</p>
      <div className="mx-auto mt-6 flex max-w-md items-center justify-center gap-4 rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-4 text-left">
        <img src={saturdayPick6Sponsor.logo_url} alt={saturdayPick6Sponsor.name} className="h-14 w-14 rounded-xl bg-white object-contain p-1" />
        <div><p className="text-sm font-black text-cfb-text-primary">{saturdayPick6Sponsor.name}</p><p className="mt-1 text-xs font-bold text-cyan-100">{saturdayPick6Sponsor.tagline}</p></div>
      </div>
      {!embedded ? <Button asChild className="mt-7"><Link to="/">Back to dashboard</Link></Button> : null}
    </section>
  );
}

export default function SaturdayPick6({ embedded = false }: SaturdayPick6Props) {
  const contestQuery = useSaturdayPickContest();
  const savePick = useSaveSaturdayPick();
  const contest = contestQuery.data;
  const [pendingPickId, setPendingPickId] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [resultDialogOpen, setResultDialogOpen] = useState(false);
  const countdown = useCountdown(contest?.lock_at);
  const selectedPickId = pendingPickId ?? contest?.entry?.selected_pick_player_id ?? null;
  const isOpen = contest?.status === "OPEN" && !countdown.expired;
  const isResults = Boolean(contest && ["SCORING", "PROVISIONAL", "FINAL"].includes(contest.status));
  const winnerIds = useMemo(() => new Set(contest?.winning_player_ids ?? []), [contest?.winning_player_ids]);
  const players = useMemo(() => {
    if (!contest) return [];
    const rows = [...contest.players];
    return isResults
      ? rows.sort((left, right) => (displayPoints(right, contest.status) ?? -1) - (displayPoints(left, contest.status) ?? -1))
      : rows;
  }, [contest, isResults]);

  useEffect(() => {
    if (contest?.status === "OPEN" && countdown.expired) {
      void contestQuery.refetch();
    }
  }, [contest?.status, contestQuery, countdown.expired]);

  useEffect(() => {
    if (contest?.status === "FINAL" && contest.entry) {
      setResultDialogOpen(true);
    }
  }, [contest?.entry?.id, contest?.id, contest?.status]);

  if (contestQuery.isLoading) {
    return <SkeletonState rows={4} label="Loading Saturday Pick 6" className="mx-auto max-w-7xl py-5" />;
  }
  // A disabled feature, 404 response, unpublished schedule, or empty slate
  // is non-actionable. Keep both route and dashboard card stable.
  if (isSaturdayPick6ComingSoon(contest)) return <SaturdayPick6ComingSoon embedded={embedded} />;

  const selectedPlayer = contest.players.find((player) => player.id === selectedPickId) ?? null;
  const savedPlayer = contest.players.find((player) => player.id === contest.entry?.selected_pick_player_id) ?? null;
  const firstGamePlayer = contest.first_game_player ?? [...contest.players].sort(
    (left, right) => new Date(left.game_time).getTime() - new Date(right.game_time).getTime() || left.sort_order - right.sort_order
  )[0];
  const lockPlayerName = firstGamePlayer?.player_name ?? "the first featured player";
  // Sponsor data remains API-owned and is absent until the server has an
  // approved sponsor configuration. No browser fallback may expose branding
  // or a reward code.
  const sponsor = contest.sponsor ?? {
    ...saturdayPick6Sponsor,
    offer_text: saturdayPick6Sponsor.tagline,
    code: null,
    terms: null,
    reward_unlocked: false,
    url: null,
  };
  const sponsorLogo = getSaturdayPickSponsorLogo(sponsor);
  const revealSponsorReward = Boolean(contest.sponsor) && shouldRevealSponsorReward(contest.status, contest.entry);
  const submit = async () => {
    if (!selectedPickId || !isOpen) return;
    setSubmitError(null);
    try {
      await savePick.mutateAsync({ contestId: contest.id, selectedPickPlayerId: selectedPickId });
      setPendingPickId(null);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Unable to save your pick. Please try again.");
    }
  };
  const copySponsorCode = async () => {
    if (sponsor?.code) await navigator.clipboard?.writeText(sponsor.code);
  };

  return (
    <div className={embedded ? "space-y-7" : "mx-auto max-w-7xl space-y-7 pb-20 pt-5"}>
      <section className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised p-6 sm:p-8">
        <div className="flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-md border border-cfb-gold/45 bg-cfb-gold/10 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-yellow-100"><Trophy className="h-4 w-4" /> Saturday Pick 6</span>
              <span className="cfb-micro-label text-cyan-200">Week {contest.week_number} · {contest.contest_position} Week</span>
            </div>
            <h1 className="mt-5 font-display text-3xl font-black tracking-[-0.04em] text-cfb-text-primary sm:text-4xl">{isResults ? "Live results" : isOpen ? "Make your pick" : contest.status === "SCHEDULED" ? "Picks opening soon" : "Picks locked"}</h1>
            <p className="mt-4 max-w-2xl text-base font-bold leading-7 text-cfb-text-secondary sm:text-lg">Which featured {positionLabel(contest.contest_position)} will score the most fantasy points this week?</p>
            <p className="mt-4 max-w-2xl rounded-lg border border-cfb-border-subtle bg-cfb-surface px-4 py-3 text-sm leading-6 text-cfb-text-secondary">
              <span className="mr-2 font-bold text-cfb-text-primary">How it works</span>
              {SATURDAY_PICK_6_HOW_IT_WORKS.replace("How it works: ", "")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            {sponsor ? <>
              <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-cfb-border-subtle bg-white p-1.5">{sponsorLogo ? <img src={sponsorLogo} alt={sponsor.name} className="h-full w-full object-contain" /> : <span className="text-sm font-black text-cfb-brand">{sponsor.name.slice(0, 2).toUpperCase()}</span>}</div>
              <div className="max-w-md"><p className="cfb-micro-label text-cfb-gold">Presented by</p><p className="mt-2 text-xl font-bold leading-tight text-white">{sponsor.name}</p>{sponsor.offer_text ? <p className="mt-2 text-sm font-semibold leading-6 text-cfb-text-secondary">{sponsor.offer_text}</p> : null}</div>
            </> : null}
            <div className="flex flex-wrap items-center gap-3"><div className="rounded-lg border border-cfb-border-strong bg-cfb-surface px-4 py-3 text-right"><p className="cfb-micro-label">{isOpen ? "Locks in" : "Contest status"}</p><p className="mt-1 font-display text-xl font-black tabular-nums text-cfb-text-primary">{isOpen ? countdown.value : statusLabel(contest.status)}</p></div>{embedded && isOpen ? <Button asChild><Link to="/saturday-pick-6">{contest.entry ? "Change Your Pick" : "Make Your Pick"}</Link></Button> : null}</div>
          </div>
        </div>
      </section>

      {!embedded ? <>
      {contest.entry && contest.status !== "FINAL" ? <section className="rounded-xl border border-cfb-brand/35 bg-cfb-brand/[0.08] p-6"><p className="cfb-micro-label text-cfb-brand">Your pick is in</p><h2 className="mt-2 text-xl font-bold text-cfb-text-primary">{savedPlayer?.player_name ?? "Your Saturday Pick 6 selection"}</h2><p className="mt-2 text-sm leading-6 text-cfb-text-secondary">{savedPlayer ? pickConfirmationMessage(savedPlayer.player_name) : "Follow your pick this Saturday."}</p><p className="mt-3 text-sm leading-6 text-cfb-text-secondary">{isOpen ? lockDeadlineMessage(lockPlayerName, contest.lock_at) : `${lockPlayerName}'s game has started. Your pick is fully locked.`}</p></section> : null}

      {contest.status === "FINAL" ? <section className="rounded-3xl border border-cfb-gold/35 bg-cfb-gold/[0.08] p-5 text-cfb-text-primary"><p className="cfb-micro-label text-yellow-100">Saturday Pick 6 winner</p><p className="mt-2 text-2xl font-black">{winnerIds.size > 1 ? "Two or more players tied for the top score" : `${players[0]?.player_name ?? "Winner"} led the field`}</p>{contest.entry ? <p className="mt-2 font-bold text-cfb-text-secondary">{contest.entry.is_winner ? "YOU GOT IT RIGHT" : `Your pick finished ${Math.max(1, players.findIndex((player) => player.id === contest.entry?.selected_pick_player_id) + 1)}${"th"}.`}</p> : null}</section> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {players.map((player, index) => {
          const selected = selectedPickId === player.id;
          const isWinner = winnerIds.has(player.player_id);
          const shownPoints = displayPoints(player, contest.status);
          const pointLabel = contest.status === "FINAL" ? "Final points" : isResults ? "Live points" : "Projected points";
          return (
            <article key={player.id} className={`relative overflow-hidden rounded-xl border p-5 transition-colors ${selected ? "border-cfb-brand bg-cfb-brand/[0.10]" : "border-cfb-border-subtle bg-cfb-surface"}`}>
              {contest.status === "FINAL" && contest.entry?.selected_pick_player_id === player.id && !contest.entry.is_winner ? <div className="absolute inset-0 z-10 flex items-center justify-center bg-rose-950/35" aria-label="Your pick did not win"><CircleX className="h-28 w-28 text-rose-200 drop-shadow-[0_0_18px_rgba(251,113,133,0.8)]" /></div> : null}
              {isResults ? <span className="absolute right-4 top-4 text-xs font-black tabular-nums text-cyan-100">#{index + 1}</span> : null}
              <div className="flex min-w-0 items-center gap-3 pr-8"><div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/12 bg-cfb-surface-raised text-cfb-brand">{player.image_url ? <img src={player.image_url} alt={player.player_name} className="h-full w-full object-cover" /> : <UserRound className="h-7 w-7" />}</div><div className="min-w-0"><h2 className="truncate text-xl font-black text-cfb-text-primary">{player.player_name}</h2><p className="mt-1 text-xs font-black uppercase tracking-[0.14em] text-cfb-text-muted">{player.school} · {player.canonical_position}</p></div></div>
              {isWinner ? <Trophy className="absolute right-4 top-4 h-5 w-5 text-cfb-gold" aria-label="Weekly winner" /> : null}
              <div className="mt-5 grid grid-cols-2 gap-3 text-sm"><div><p className="cfb-micro-label">Opponent</p><p className="mt-1 font-black text-cfb-text-primary">vs. {player.opponent}</p></div><div><p className="cfb-micro-label">{pointLabel}</p><p className="mt-1 text-xl font-black tabular-nums text-cyan-100">{typeof shownPoints === "number" ? formatPoints(shownPoints) : "Projection pending"}</p></div></div>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs font-bold text-cfb-text-secondary"><span>{formatKickoff(player.game_time)}</span><span className={player.scoring_status === "DATA_DELAYED" ? "text-amber-200" : "text-cyan-100"}>{player.scoring_status === "LIVE" ? <Radio className="mr-1 inline h-3.5 w-3.5" /> : null}{statusLabel(player.scoring_status)}</span></div>
              {isOpen ? <Button type="button" className="mt-5 w-full" variant={selected ? "default" : "outline"} onClick={() => setPendingPickId(player.id)}>{selected ? <><Check className="mr-2 h-4 w-4" /> Your Pick</> : "Choose player"}</Button> : null}
            </article>
          );
        })}
      </section>

      {isOpen ? <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-cfb-border-subtle bg-cfb-surface p-5"><div><p className="text-sm font-black text-cfb-text-primary">{selectedPlayer ? `You selected ${selectedPlayer.player_name}. Lock it in to follow them this Saturday.` : `Choose one featured ${positionLabel(contest.contest_position)}.`}</p><p className="mt-1 text-sm font-bold text-cfb-text-secondary">{lockDeadlineMessage(lockPlayerName, contest.lock_at)}</p>{submitError ? <p role="alert" className="mt-3 text-sm font-bold text-red-300">{submitError}</p> : null}</div><Button type="button" disabled={!selectedPickId || savePick.isPending} onClick={submit}>{savePick.isPending ? "Saving…" : contest.entry ? "Update Pick" : "Lock In Pick"}</Button></section> : null}
      </> : null}

      <Dialog open={resultDialogOpen} onOpenChange={setResultDialogOpen}>
        <DialogContent className="max-w-lg border-cyan-300/35 bg-[#081321] text-cfb-text-primary">
          {revealSponsorReward ? <><DialogHeader><DialogTitle className="pr-8 text-3xl font-black uppercase italic text-cfb-gold">You got it right</DialogTitle><DialogDescription className="text-base font-semibold leading-6 text-cfb-text-secondary">{savedPlayer?.player_name ?? "Your pick"} finished with the most fantasy points.</DialogDescription></DialogHeader><div className="rounded-2xl border border-cfb-gold/30 bg-cfb-gold/[0.10] p-4"><p className="cfb-micro-label text-yellow-100">Your winner discount code</p>{sponsor.code ? <div className="mt-3 flex flex-wrap items-center gap-3"><code className="rounded-xl border border-white/15 bg-slate-950/55 px-4 py-3 font-black tracking-[0.16em] text-cyan-100">{sponsor.code}</code><Button variant="outline" onClick={copySponsorCode}><Copy className="mr-2 h-4 w-4" /> Copy Code</Button></div> : <p className="mt-2 text-sm font-bold text-cfb-text-secondary">Your reward code is being prepared.</p>}</div></> : <><DialogHeader><DialogTitle className="pr-8 text-3xl font-black uppercase italic text-rose-200">Not this week</DialogTitle><DialogDescription className="text-base font-semibold leading-6 text-cfb-text-secondary">{savedPlayer?.player_name ?? "Your pick"} did not finish first. Try again next week.</DialogDescription></DialogHeader><div className="flex justify-center rounded-2xl border border-rose-300/25 bg-rose-500/[0.10] p-5"><CircleX className="h-20 w-20 text-rose-200" aria-label="Pick did not win" /></div></>}
          <DialogFooter><Button onClick={() => setResultDialogOpen(false)}>Close</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
