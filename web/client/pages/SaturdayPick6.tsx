import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink, Lock, Trophy, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SurfaceCard } from "@/components/fantasy";
import { ApiError } from "@/lib/api";
import {
  getSaturdayPickSponsorLogo,
  getSaturdayPickSponsorUrl,
  westGeorgiaCornholeSponsor,
} from "@/lib/saturday-pick-sponsor";
import {
  type SaturdayPickContest,
  useClearSaturdayPick,
  useSaturdayPickContest,
  useSaveSaturdayPick,
} from "@/hooks/use-saturday-pick";

const SEASON = 2026;
const WEEK = 1;

const formatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Game time to be announced";
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const timeUntil = (value: string) => {
  const remaining = new Date(value).getTime() - Date.now();
  if (remaining <= 0) return "Locked";
  const hours = Math.floor(remaining / 3_600_000);
  const minutes = Math.floor((remaining % 3_600_000) / 60_000);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
};

function SponsorCard({ contest }: { contest?: SaturdayPickContest | null }) {
  const sponsor = contest?.sponsor ?? westGeorgiaCornholeSponsor;
  const url = getSaturdayPickSponsorUrl(sponsor);
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center gap-4 rounded-2xl border border-cfb-gold/35 bg-slate-950/45 p-4 transition hover:border-cfb-gold/70 hover:bg-cfb-gold/[0.08]"
    >
      <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl bg-white p-2 shadow-[0_0_28px_rgba(250,204,21,0.12)]">
        <img src={getSaturdayPickSponsorLogo(sponsor)} alt={`${sponsor.name} logo`} className="max-h-full max-w-full object-contain" />
      </span>
      <span className="min-w-0">
        <span className="cfb-micro-label text-cfb-cyan">Presented by</span>
        <span className="mt-1 flex items-center gap-2 text-lg font-black text-cfb-text-primary group-hover:text-cfb-gold">
          {sponsor.name} <ExternalLink className="h-4 w-4 shrink-0" aria-label={`Visit ${sponsor.name}`} />
        </span>
        <span className="mt-1 block text-sm font-medium leading-5 text-cfb-text-secondary">
          {sponsor.offer_text ?? westGeorgiaCornholeSponsor.offer_text}
        </span>
      </span>
    </a>
  );
}

export default function SaturdayPick6() {
  const { data: contest, isLoading, error } = useSaturdayPickContest(SEASON, WEEK);
  const savePick = useSaveSaturdayPick(SEASON, WEEK);
  const clearPick = useClearSaturdayPick(SEASON, WEEK);
  const [pendingPickId, setPendingPickId] = useState<number | null>(null);
  const [isChangingPick, setIsChangingPick] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const isOpen = contest?.status === "OPEN" && new Date(contest.lock_at).getTime() > Date.now();
  const activePickId = useMemo(() => {
    if (isChangingPick) return pendingPickId;
    return pendingPickId ?? contest?.entry?.selected_pick_player_id ?? null;
  }, [contest?.entry?.selected_pick_player_id, isChangingPick, pendingPickId]);
  const chosenPlayer = contest?.players.find((player) => player.id === activePickId) ?? null;
  const canChoose = Boolean(isOpen && (!contest?.entry || isChangingPick) && !clearPick.isPending);

  useEffect(() => {
    if (!contest?.entry || isChangingPick) return;
    setPendingPickId(null);
  }, [contest?.entry, isChangingPick]);

  const beginChange = async () => {
    if (!contest) return;
    // Do not preserve the old pick after the manager deliberately begins a change.
    setPendingPickId(null);
    setIsChangingPick(true);
    setMessage("Removing your previous pick...");
    try {
      await clearPick.mutateAsync({ contestId: contest.id });
      setMessage("Choose a new player, then lock in your new pick.");
    } catch (caught) {
      setIsChangingPick(false);
      setMessage(caught instanceof ApiError ? caught.message : "Unable to change your pick. Please try again.");
    }
  };

  const lockPick = async () => {
    if (!contest || !pendingPickId || !canChoose) return;
    setMessage(null);
    try {
      await savePick.mutateAsync({ contestId: contest.id, selectedPickPlayerId: pendingPickId });
      setPendingPickId(null);
      setIsChangingPick(false);
      setMessage("Your Pick 6 selection is locked in until the first featured game begins.");
    } catch (caught) {
      setMessage(caught instanceof ApiError ? caught.message : "Unable to lock your pick. Please try again.");
    }
  };

  if (isLoading) {
    return <div className="mx-auto max-w-7xl py-16 text-center text-sm font-black uppercase tracking-[0.18em] text-cfb-text-secondary">Loading Saturday Pick 6...</div>;
  }

  if (!contest) {
    const noContest = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-5xl space-y-6 pb-24 pt-6">
        <SurfaceCard variant="scoreboard" padding="spacious" className="cfb-playbook-pattern relative overflow-hidden">
          <div className="grid gap-8 lg:grid-cols-[1fr_0.9fr] lg:items-center">
            <div>
              <p className="cfb-micro-label text-cfb-gold">Saturday Pick 6</p>
              <h1 className="mt-3 text-5xl font-black italic tracking-[-0.05em] text-cfb-text-primary">COMING NEXT WEEK</h1>
              <p className="mt-4 max-w-xl text-lg font-medium leading-8 text-cfb-text-secondary">
                Six featured players. One winner. Lock your pick before the first featured game starts.
              </p>
              {!noContest && <p className="mt-4 text-sm font-bold text-rose-200">The contest could not be loaded. Please try again shortly.</p>}
            </div>
            <SponsorCard />
          </div>
        </SurfaceCard>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-24 pt-5">
      <SurfaceCard variant="scoreboard" padding="spacious" className="cfb-playbook-pattern relative overflow-hidden">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cfb-gold/40 bg-cfb-gold/[0.1] px-4 py-2 text-[11px] font-black uppercase tracking-[0.2em] text-cfb-gold">
              <Trophy className="h-4 w-4" /> Saturday Pick 6
            </div>
            <p className="mt-6 cfb-micro-label text-cfb-cyan">Week {contest.week_number} • {contest.contest_position} Week</p>
            <h1 className="mt-3 text-5xl font-black italic tracking-[-0.05em] text-cfb-text-primary sm:text-6xl">MAKE YOUR PICK</h1>
            <p className="mt-4 max-w-2xl text-lg font-medium leading-8 text-cfb-text-secondary">
              Choose which featured {contest.contest_position} will score the most fantasy points. Your pick locks when the first featured game begins.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-xl border border-cfb-brand/35 bg-cfb-brand/[0.1] px-4 py-3 text-sm font-black text-cfb-text-primary">
              <Lock className="h-4 w-4 text-cfb-cyan" /> Locks in {formatDate(contest.lock_at)} ({timeUntil(contest.lock_at)})
            </div>
          </div>
          <SponsorCard contest={contest} />
        </div>
      </SurfaceCard>

      {contest.entry && !isChangingPick && (
        <SurfaceCard padding="default" className="flex flex-col gap-4 border-cfb-success/35 bg-cfb-success/[0.06] sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="cfb-micro-label text-cfb-success">Current locked pick</p>
            <p className="mt-1 text-xl font-black text-cfb-text-primary">{chosenPlayer?.player_name ?? "Your selected player"}</p>
            <p className="mt-1 text-sm font-medium text-cfb-text-secondary">Your pick remains editable until {formatDate(contest.lock_at)}.</p>
          </div>
          <Button variant="outline" onClick={() => void beginChange()} disabled={!isOpen || clearPick.isPending}>Change Pick</Button>
        </SurfaceCard>
      )}

      {isChangingPick && (
        <div className="rounded-2xl border border-cfb-gold/35 bg-cfb-gold/[0.08] px-5 py-4 text-sm font-bold text-cfb-text-primary">
          Your previous pick is no longer selected. Choose one player below, then confirm with <strong>Lock In New Pick</strong>.
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {contest.players.map((player) => {
          const selected = activePickId === player.id;
          const isSaved = contest.entry?.selected_pick_player_id === player.id && !isChangingPick;
          return (
            <button
              key={player.id}
              type="button"
              disabled={!canChoose}
              onClick={() => setPendingPickId(player.id)}
              className={`relative min-h-[245px] rounded-3xl border p-6 text-left transition ${selected ? "border-cfb-cyan bg-cfb-brand/[0.14] shadow-[0_0_36px_rgba(56,189,248,0.18)]" : "border-cfb-border-strong bg-cfb-surface/75"} ${canChoose ? "hover:-translate-y-0.5 hover:border-cfb-cyan/75" : "cursor-default opacity-90"}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-cfb-border-strong bg-slate-950/55 text-cfb-text-muted">
                  <UserRound className="h-7 w-7" aria-label="Neutral player avatar" />
                </div>
                <span className="rounded-full border border-cfb-border-strong px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-cfb-text-secondary">{player.canonical_position}</span>
              </div>
              <h2 className="mt-5 text-2xl font-black text-cfb-text-primary">{player.player_name}</h2>
              <p className="mt-1 text-sm font-black uppercase tracking-[0.15em] text-cfb-text-muted">{player.school}</p>
              <div className="mt-6 grid grid-cols-2 gap-4 border-t border-cfb-border-subtle pt-4 text-sm">
                <div><p className="cfb-micro-label text-cfb-text-muted">Opponent</p><p className="mt-1 font-bold text-cfb-text-primary">vs. {player.opponent}</p></div>
                <div><p className="cfb-micro-label text-cfb-text-muted">Projected</p><p className="mt-1 text-xl font-black text-cfb-cyan">{player.projected_points?.toFixed(1) ?? "—"}</p></div>
              </div>
              <p className="mt-4 text-xs font-semibold text-cfb-text-secondary">{formatDate(player.game_time)}</p>
              {selected && <span className="absolute right-5 top-5 flex items-center gap-1 rounded-full bg-cfb-cyan px-3 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950"><CheckCircle2 className="h-3.5 w-3.5" /> {isSaved ? "Locked" : "Selected"}</span>}
            </button>
          );
        })}
      </div>

      <SurfaceCard padding="default" className="sticky bottom-4 flex flex-col gap-4 border-cfb-brand/35 bg-slate-950/95 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="cfb-micro-label text-cfb-cyan">Your selection</p>
          <p className="mt-1 text-lg font-black text-cfb-text-primary">{chosenPlayer?.player_name ?? "Choose one featured player"}</p>
          {message && <p className="mt-1 text-sm font-medium text-cfb-text-secondary">{message}</p>}
        </div>
        {canChoose ? (
          <Button className="min-w-56" disabled={!pendingPickId || savePick.isPending} onClick={lockPick}>
            <Lock className="mr-2 h-4 w-4" /> {isChangingPick ? "Lock In New Pick" : "Lock In Pick"}
          </Button>
        ) : !isOpen ? (
          <Button variant="outline" disabled><Lock className="mr-2 h-4 w-4" /> Picks Locked</Button>
        ) : null}
      </SurfaceCard>

      <p className="text-center text-sm font-medium text-cfb-text-muted">Presented by <a className="font-black text-cfb-gold underline-offset-4 hover:underline" href={getSaturdayPickSponsorUrl(contest.sponsor ?? westGeorgiaCornholeSponsor)} target="_blank" rel="noreferrer">West Georgia Cornhole</a>. <Link className="font-bold text-cfb-cyan hover:underline" to="/">Back to dashboard</Link></p>
    </div>
  );
}
