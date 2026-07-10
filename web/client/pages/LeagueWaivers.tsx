import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Clock3, ReceiptText, Search, ShieldCheck, Sparkles, TrendingUp, UserPlus, X, Zap } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { PageEmptyState, PageErrorState, PageLoadingState } from "@/components/PageState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import {
  useCancelWaiverClaim,
  useLeagueSettingsTab,
  useLeagueWaiverTab,
  useSubmitWaiverClaim,
} from "@/hooks/use-leagues";
import {
  useCreateWatchlist,
  useToggleWatchlistPlayer,
  useWatchlists,
} from "@/hooks/use-watchlists";
import { useDraftPlayerPool } from "@/hooks/use-players";
import { DEMO_LEAGUE_ID, createDemoLeagueWaiverResponse } from "@/lib/leaguePreviewData";
import { isPreDraftLeague } from "@/lib/leagueState";
import type { LeagueRosterPlayer, LeagueWaiverClaim, LeagueWaiverPlayer } from "@/types/league";

const positions = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;
type DraftPoolPlayer = LeagueWaiverPlayer & { draft_rank?: number | null };

type WaiverClaimDraft = {
  teamId: number | null | undefined;
  addPlayerId: number | null | undefined;
  dropPlayerId?: number | null;
  bidAmount?: string | number | null;
  waiverType?: string | null;
};

const hasPositiveId = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value > 0;

export const canSubmitWaiverClaim = (draft: WaiverClaimDraft, isPreDraft: boolean) =>
  !isPreDraft && hasPositiveId(draft.teamId) && hasPositiveId(draft.addPlayerId);

export const buildWaiverClaimPayload = (draft: WaiverClaimDraft) => {
  if (!hasPositiveId(draft.teamId) || !hasPositiveId(draft.addPlayerId)) {
    throw new Error("Choose a player before submitting a waiver claim.");
  }
  const bidAmount = Number(draft.bidAmount ?? 0);
  return {
    team_id: Number(draft.teamId),
    add_player_id: Number(draft.addPlayerId),
    drop_player_id: draft.dropPlayerId ? Number(draft.dropPlayerId) : null,
    bid_amount: draft.waiverType === "faab" ? (Number.isFinite(bidAmount) ? Math.max(0, bidAmount) : 0) : 0,
  };
};

export const claimStatusLabel = (claim: Pick<LeagueWaiverClaim, "status" | "failure_reason">) => {
  const status = claim.status.toLowerCase();
  if (status === "failed" && claim.failure_reason) return `Failed · ${claim.failure_reason}`;
  return status.replace(/_/g, " ");
};

const positionTone = (position?: string | null) => {
  switch ((position ?? "").toUpperCase()) {
    case "QB":
      return { border: "border-blue-300/45", bg: "bg-blue-400/10", text: "text-blue-100", glow: "shadow-[0_0_26px_rgba(96,165,250,0.18)]", dot: "bg-blue-300" };
    case "RB":
      return { border: "border-emerald-300/45", bg: "bg-emerald-400/10", text: "text-emerald-100", glow: "shadow-[0_0_26px_rgba(52,211,153,0.18)]", dot: "bg-emerald-300" };
    case "WR":
      return { border: "border-violet-300/45", bg: "bg-violet-400/10", text: "text-violet-100", glow: "shadow-[0_0_26px_rgba(167,139,250,0.18)]", dot: "bg-violet-300" };
    case "TE":
      return { border: "border-amber-300/45", bg: "bg-amber-400/10", text: "text-amber-100", glow: "shadow-[0_0_26px_rgba(251,191,36,0.16)]", dot: "bg-amber-300" };
    case "K":
      return { border: "border-sky-300/45", bg: "bg-sky-400/10", text: "text-sky-100", glow: "shadow-[0_0_26px_rgba(56,189,248,0.18)]", dot: "bg-sky-300" };
    default:
      return { border: "border-slate-300/25", bg: "bg-white/5", text: "text-slate-100", glow: "shadow-[0_0_20px_rgba(148,163,184,0.10)]", dot: "bg-slate-400" };
  }
};

const playerDisplayName = (playerId: number | null | undefined, claimName: string | null | undefined, players: LeagueWaiverPlayer[], roster: LeagueRosterPlayer[]) =>
  claimName ??
  players.find((player) => player.id === playerId)?.name ??
  roster.find((player) => player.player_id === playerId)?.player_name ??
  (playerId ? `Player #${playerId}` : "None");

export default function LeagueWaivers() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState<(typeof positions)[number]>("ALL");
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [selectedDropPlayerId, setSelectedDropPlayerId] = useState<number | null>(null);
  const [bidAmount, setBidAmount] = useState("0");

  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const hasDraftResults = Boolean(settingsQuery.data?.draft_results?.length);
  const isPreDraft = !isDemoLeague && Boolean(settingsQuery.data) && (!hasDraftResults || isPreDraftLeague(settingsQuery.data));
  const settingsReady = isDemoLeague || Boolean(settingsQuery.data);
  const waiverQuery = useLeagueWaiverTab(parsedLeagueId, 200, 0, !isDemoLeague && settingsReady && !isPreDraft);
  const draftPoolQuery = useDraftPlayerPool({
    search: undefined,
    position: undefined,
    league_id: undefined,
    available_only: false,
    sort: "draft_rank",
    limit: 200,
    offset: 0,
    pages: 50,
    enabled: !isDemoLeague && settingsReady && isPreDraft,
  });
  const submitClaim = useSubmitWaiverClaim(parsedLeagueId);
  const cancelClaim = useCancelWaiverClaim(parsedLeagueId);

  const waiverData = isDemoLeague ? createDemoLeagueWaiverResponse() : waiverQuery.data;
  const waiverRules = waiverData?.waiver_rules ?? settingsQuery.data?.waiver_rules ?? {};
  const waiverType = String(waiverRules.waiver_type ?? waiverRules.waiver_mode ?? "faab").toLowerCase();
  const isFaab = waiverType === "faab";
  const myRoster = useMemo(
    () =>
      (settingsQuery.data?.rosters ?? []).filter(
        (entry) => entry.fantasy_team_id === waiverData?.fantasy_team_id && entry.player_id
      ),
    [settingsQuery.data?.rosters, waiverData?.fantasy_team_id]
  );
  const draftPoolPlayers = useMemo<DraftPoolPlayer[]>(
    () =>
      (draftPoolQuery.data?.data ?? []).map((player) => ({
        id: player.id,
        name: player.name,
        school: player.school,
        position: player.pos,
        draft_rank: player.rank ?? player.adp ?? null,
        weekly_projected_fantasy_points: Number(player.projection?.fpts ?? player.sheetProjectedSeasonPoints ?? 0),
      })),
    [draftPoolQuery.data?.data]
  );
  const players = isPreDraft ? draftPoolPlayers : waiverData?.available_players ?? [];
  const selectedPlayer = players.find((player) => player.id === selectedPlayerId) ?? null;

  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    !isDemoLeague && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const createWatchlist = useCreateWatchlist();
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const watchlists = watchlistsQuery.data?.data ?? [];
  const primaryWatchlist = watchlists[0] ?? null;
  const watchedPlayerIds = useMemo(
    () => new Set(watchlists.flatMap((watchlist) => watchlist.players.map((player) => player.id))),
    [watchlists]
  );

  const filteredPlayers = useMemo<DraftPoolPlayer[]>(() => {
    const query = search.trim().toLowerCase();
    return (players as DraftPoolPlayer[])
      .filter((player) => position === "ALL" || (player.position ?? "").toUpperCase() === position)
      .filter((player) => {
        if (!query) return true;
        return [player.name, player.school, player.position]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      })
      .sort((first, second) => {
        if (isPreDraft) {
          const firstRank = Number(first.draft_rank ?? Number.POSITIVE_INFINITY);
          const secondRank = Number(second.draft_rank ?? Number.POSITIVE_INFINITY);
          if (firstRank !== secondRank) return firstRank - secondRank;
        }
        return Number(second.weekly_projected_fantasy_points ?? 0) - Number(first.weekly_projected_fantasy_points ?? 0);
      });
  }, [isPreDraft, players, position, search]);

  const topProjection = players.reduce((top, player) => Math.max(top, Number(player.weekly_projected_fantasy_points ?? 0)), 0);
  const positionCounts = players.reduce<Record<string, number>>((counts, player) => {
    const key = (player.position ?? "UNK").toUpperCase();
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
  const pendingClaims = (waiverData?.claims ?? []).filter((claim) => claim.status.toLowerCase() === "pending");

  const handleWatchPlayer = async (playerId: number) => {
    if (isPreDraft) {
      toast({ title: "Draft pool is locked", description: "Watchlists and claims unlock after the league draft creates real rosters." });
      return;
    }
    if (isDemoLeague) {
      toast({ title: "Demo league watchlist", description: "Watchlists persist in real leagues after signing in." });
      return;
    }
    try {
      const watchlist = primaryWatchlist ?? (await createWatchlist.mutateAsync({ name: "League Watchlist", league_id: parsedLeagueId }));
      await toggleWatchlistPlayer.mutateAsync({ watchlistId: watchlist.id, playerId, isSaved: watchedPlayerIds.has(playerId) });
      toast({ title: watchedPlayerIds.has(playerId) ? "Removed from watchlist" : "Added to watchlist", description: "Open the Watchlist tab to review saved waiver targets." });
    } catch (error) {
      toast({ title: "Unable to update watchlist", description: error instanceof Error ? error.message : "Try again.", variant: "destructive" });
    }
  };

  const handleSubmitClaim = async () => {
    if (isDemoLeague) {
      toast({ title: "Demo waiver claim", description: "Create or join a real league to submit waiver claims." });
      return;
    }
    try {
      const payload = buildWaiverClaimPayload({
        teamId: waiverData?.fantasy_team_id,
        addPlayerId: selectedPlayerId,
        dropPlayerId: selectedDropPlayerId,
        bidAmount,
        waiverType,
      });
      await submitClaim.mutateAsync(payload);
      setSelectedPlayerId(null);
      setSelectedDropPlayerId(null);
      setBidAmount("0");
      toast({ title: "Waiver claim submitted", description: "The claim is queued for waiver processing and can be cancelled while pending." });
    } catch (error) {
      toast({ title: "Unable to submit waiver claim", description: error instanceof Error ? error.message : "Try again.", variant: "destructive" });
    }
  };

  const handleCancelClaim = async (claimId: number) => {
    try {
      await cancelClaim.mutateAsync(claimId);
      toast({ title: "Waiver claim cancelled", description: "The pending claim was removed from the processing queue." });
    } catch (error) {
      toast({ title: "Unable to cancel claim", description: error instanceof Error ? error.message : "Try again.", variant: "destructive" });
    }
  };

  const isLoadingPlayers = !isDemoLeague && (settingsQuery.isLoading || (isPreDraft ? draftPoolQuery.isLoading : waiverQuery.isLoading));
  if (isLoadingPlayers) {
    return <PageLoadingState title="Loading waiver pool" description={isPreDraft ? "Fetching the locked draft player pool." : "Fetching available players, waiver rules, and pending claims."} />;
  }

  const playerPoolError = !isDemoLeague && (settingsQuery.isError || (isPreDraft ? draftPoolQuery.isError : waiverQuery.isError));
  if (playerPoolError) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
        <PageErrorState
          title="Unable to load waivers"
          description="The waiver pool could not load. Retry once the backend is reachable and your league access is valid."
          onAction={() => {
            void settingsQuery.refetch();
            void waiverQuery.refetch();
            void draftPoolQuery.refetch();
          }}
        />
      </main>
    );
  }

  const claimCanSubmit = canSubmitWaiverClaim({ teamId: waiverData?.fantasy_team_id, addPlayerId: selectedPlayerId }, isPreDraft);

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[460px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_8%,rgba(56,189,248,0.2),transparent_32%),radial-gradient(circle_at_72%_0%,rgba(99,102,241,0.18),transparent_38%),radial-gradient(circle_at_50%_30%,rgba(14,165,233,0.12),transparent_42%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">League Waivers</p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">{isPreDraft ? "Pre-Draft Waivers Locked" : "Waiver Claims"}</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              {isPreDraft
                ? "Waiver claims unlock after the draft creates real rosters. Use Draft Room to scout the full board before picks open."
                : "Submit add/drop claims, manage pending requests, and review the waiver audit trail for this league."}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[430px]">
            <div className="rounded-[1.25rem] border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_0_34px_rgba(56,189,248,0.12)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">{isPreDraft ? "Draft Pool" : "Available"}</p>
              <p className="mt-1 text-2xl font-black text-sky-100">{isPreDraft ? draftPoolQuery.data?.total ?? players.length : waiverData?.total_available ?? players.length}</p>
            </div>
            <div className="rounded-[1.25rem] border border-emerald-300/20 bg-emerald-400/10 p-4 shadow-[0_0_34px_rgba(52,211,153,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">{isFaab ? "FAAB Left" : "Priority"}</p>
              <p className="mt-1 text-2xl font-black text-emerald-100">{isPreDraft ? "Locked" : isFaab ? waiverData?.faab_remaining ?? waiverRules.faab_budget ?? "—" : waiverData?.waiver_priority ?? "—"}</p>
            </div>
            <div className="rounded-[1.25rem] border border-violet-300/20 bg-violet-400/10 p-4 shadow-[0_0_34px_rgba(167,139,250,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Pending Claims</p>
              <p className="mt-1 text-2xl font-black text-violet-100">{isPreDraft ? "—" : pendingClaims.length}</p>
            </div>
          </div>
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      {!isPreDraft && (
        <section className="grid gap-4 rounded-[2rem] border border-emerald-300/20 bg-[linear-gradient(135deg,rgba(6,24,28,0.86),rgba(15,23,42,0.94))] p-5 shadow-[0_24px_90px_rgba(16,185,129,0.10)] xl:grid-cols-[1fr_1fr_auto]">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-emerald-200">Claim Builder</p>
            <p className="mt-2 text-lg font-black text-slate-50">{selectedPlayer ? `Add ${selectedPlayer.name}` : "Select an available player below"}</p>
            <p className="mt-1 text-xs font-semibold text-slate-500">{selectedPlayer ? `${selectedPlayer.position ?? "POS"} · ${selectedPlayer.school ?? "School N/A"}` : "Claims stay pending until the waiver processor runs."}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-2">
              <span className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Drop Player</span>
              <select
                value={selectedDropPlayerId ?? ""}
                onChange={(event) => setSelectedDropPlayerId(event.target.value ? Number(event.target.value) : null)}
                className="h-12 w-full rounded-2xl border border-sky-300/15 bg-slate-950/70 px-4 text-xs font-black uppercase tracking-[0.12em] text-slate-100 outline-none focus:border-sky-300/45"
              >
                <option value="">No drop</option>
                {myRoster.map((entry) => (
                  <option key={entry.id} value={entry.player_id ?? ""}>
                    {entry.player_name} · {entry.roster_slot ?? entry.slot ?? "Roster"}
                  </option>
                ))}
              </select>
            </label>
            {isFaab && (
              <label className="space-y-2">
                <span className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">FAAB Bid</span>
                <Input
                  type="number"
                  min={0}
                  value={bidAmount}
                  onChange={(event) => setBidAmount(event.target.value)}
                  className="h-12 rounded-2xl border-sky-300/15 bg-slate-950/70 text-xs font-black uppercase tracking-[0.12em] text-slate-100"
                />
              </label>
            )}
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              onClick={() => void handleSubmitClaim()}
              disabled={!claimCanSubmit || submitClaim.isPending}
              className="h-12 w-full rounded-2xl bg-emerald-300 px-5 text-[10px] font-black uppercase tracking-[0.16em] text-slate-950 shadow-[0_10px_28px_rgba(16,185,129,0.18)] hover:bg-emerald-200 xl:w-auto"
            >
              <ShieldCheck className="mr-2 h-3.5 w-3.5" />
              Submit Claim
            </Button>
          </div>
        </section>
      )}

      <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] shadow-[0_24px_90px_rgba(14,165,233,0.12)]">
        <div className="border-b border-sky-300/10 px-5 py-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-300">{isPreDraft ? "Locked Draft Pool" : "Available Waiver Players"}</h2>
              <p className="mt-2 text-xs font-semibold text-slate-500">
                {isPreDraft ? "Players are visible in Draft Room before the draft. Waiver actions are locked until real rosters exist." : "Only players not rostered in this league appear here. Select Claim to start an add/drop request."}
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative min-w-[280px]">
                <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-sky-200/45" />
                <Input aria-label="Search waiver players" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search players, schools..." className="h-12 rounded-2xl border-sky-300/15 bg-slate-950/55 pl-11 text-sm font-bold text-slate-50 placeholder:text-slate-500 focus:border-sky-300/45 focus:ring-sky-300/20" />
              </div>
              <div className="flex flex-wrap gap-2">
                {positions.map((item) => {
                  const active = position === item;
                  const tone = positionTone(item === "ALL" ? null : item);
                  return (
                    <button key={item} type="button" onClick={() => setPosition(item)} className={["rounded-2xl border px-4 py-3 text-[10px] font-black uppercase tracking-[0.16em] transition-all duration-200", active ? `${tone.border} ${tone.bg} ${tone.text} ${tone.glow}` : "border-white/10 bg-white/[0.04] text-slate-400 hover:border-sky-300/25 hover:bg-sky-300/[0.07] hover:text-slate-100"].join(" ")}>
                      {item}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        {filteredPlayers.length === 0 ? (
          <div className="p-5">
            <PageEmptyState
              eyebrow={search || position !== "ALL" ? "No Matches" : "No Players"}
              title={search || position !== "ALL" ? "No players match these filters" : "No waiver players loaded"}
              description={search || position !== "ALL" ? "Clear the search or switch position filters to see more players." : "The waiver pool is empty. Check that players are seeded and the backend is reachable."}
              actionLabel={search || position !== "ALL" ? "Clear Filters" : undefined}
              onAction={search || position !== "ALL" ? () => { setSearch(""); setPosition("ALL"); } : undefined}
              className="shadow-none"
            />
          </div>
        ) : (
          <div className="divide-y divide-sky-300/10">
            {filteredPlayers.map((player, index) => {
              const tone = positionTone(player.position);
              const projected = Number(player.weekly_projected_fantasy_points ?? 0);
              const share = topProjection > 0 ? Math.min(100, Math.max(8, (projected / topProjection) * 100)) : 0;
              const selected = selectedPlayerId === player.id;
              return (
                <div key={player.id} className={["group relative grid gap-4 px-5 py-4 text-sm text-slate-200 transition-all duration-200 xl:grid-cols-[64px_minmax(260px,1.25fr)_minmax(140px,0.55fr)_minmax(250px,0.75fr)_minmax(230px,auto)]", selected ? "bg-emerald-300/[0.07] shadow-[inset_3px_0_0_rgba(110,231,183,0.75)]" : "hover:-translate-y-0.5 hover:bg-sky-300/[0.045] hover:shadow-[0_18px_50px_rgba(14,165,233,0.10)]"].join(" ")}>
                  <div className="flex items-center"><span className="text-2xl font-black italic text-slate-600 transition-colors group-hover:text-sky-200">{index + 1}</span></div>
                  <div className="flex min-w-0 items-center gap-4">
                    <div className={`relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border ${tone.border} ${tone.bg} ${tone.glow}`}>
                      <span className={`absolute -right-1 -top-1 h-3 w-3 rounded-full ${tone.dot} shadow-[0_0_18px_currentColor]`} />
                      <span className={`text-[11px] font-black uppercase tracking-[0.12em] ${tone.text}`}>{player.position ?? "-"}</span>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-base font-black text-slate-50 transition-colors group-hover:text-sky-50">{player.name}</p>
                      <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">{isPreDraft ? "Draft pool player" : "Waiver player"}</p>
                    </div>
                  </div>
                  <div className="flex items-center text-sm font-bold text-slate-400">{player.school ?? "-"}</div>
                  <div className="flex min-w-[220px] items-center">
                    <div className="w-full">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <span className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-[0.16em] text-slate-500"><TrendingUp className="h-3 w-3 text-sky-300" /> Week Proj</span>
                        <span className="text-lg font-black text-sky-100">{projected.toFixed(1)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-950/80 ring-1 ring-sky-300/10"><div className="h-full rounded-full bg-[linear-gradient(90deg,rgba(125,211,252,0.95),rgba(186,230,253,0.9))] shadow-[0_0_18px_rgba(56,189,248,0.30)]" style={{ width: `${share}%` }} /></div>
                    </div>
                  </div>
                  <div className="flex min-w-[220px] items-center justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => void handleWatchPlayer(player.id)} disabled={isPreDraft || createWatchlist.isPending || toggleWatchlistPlayer.isPending} className="h-11 rounded-2xl border-sky-300/20 bg-sky-300/[0.06] px-4 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100 transition-all hover:border-sky-200/45 hover:bg-sky-300/15 hover:shadow-[0_0_26px_rgba(56,189,248,0.16)]">
                      <Sparkles className="mr-2 h-3.5 w-3.5" />
                      {isPreDraft ? "Locked" : watchedPlayerIds.has(player.id) ? "Watching" : "Watch"}
                    </Button>
                    <Button type="button" onClick={() => setSelectedPlayerId(player.id)} disabled={isPreDraft} className="h-11 rounded-2xl bg-sky-300 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-slate-950 shadow-[0_10px_28px_rgba(14,165,233,0.18)] transition-all hover:bg-sky-200">
                      <UserPlus className="mr-2 h-3.5 w-3.5" />
                      {isPreDraft ? "Locked" : selected ? "Selected" : "Claim"}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="rounded-[2rem] border border-violet-300/20 bg-white/[0.035] p-5">
          <div className="flex items-center gap-3">
            <ReceiptText className="h-5 w-5 text-violet-200" />
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-violet-200">Claim Audit Trail</h2>
              <p className="mt-1 text-xs font-semibold text-slate-500">Submitted, cancelled, processed, and failed claims for your team.</p>
            </div>
          </div>
          {(waiverData?.claims ?? []).length === 0 ? (
            <p className="mt-5 rounded-2xl border border-white/10 bg-slate-950/35 p-4 text-sm font-bold text-slate-400">No waiver claims have been submitted yet.</p>
          ) : (
            <div className="mt-5 divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/10">
              {(waiverData?.claims ?? []).map((claim) => (
                <div key={claim.id} className="grid gap-3 bg-slate-950/30 p-4 md:grid-cols-[1fr_auto]">
                  <div>
                    <p className="text-sm font-black text-slate-50">
                      Add {playerDisplayName(claim.add_player_id, claim.add_player_name, players, myRoster)}
                      {claim.drop_player_id ? ` · Drop ${playerDisplayName(claim.drop_player_id, claim.drop_player_name, players, myRoster)}` : ""}
                    </p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                      {claimStatusLabel(claim)}
                      {isFaab ? ` · Bid ${claim.bid_amount ?? claim.bid ?? 0}` : ""}
                      {(claim.priority_at_submission ?? claim.priority) ? ` · Priority ${claim.priority_at_submission ?? claim.priority}` : ""}
                    </p>
                    <p className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
                      <Clock3 className="h-3.5 w-3.5" />
                      Processes {claim.process_after ? new Date(claim.process_after).toLocaleString() : "on next waiver run"}
                    </p>
                  </div>
                  {claim.status.toLowerCase() === "pending" && (
                    <Button type="button" variant="outline" onClick={() => void handleCancelClaim(claim.id)} disabled={cancelClaim.isPending} className="h-10 rounded-xl border-rose-300/25 bg-rose-300/[0.06] text-[10px] font-black uppercase tracking-[0.16em] text-rose-100 hover:bg-rose-300/15">
                      <X className="mr-2 h-3.5 w-3.5" />
                      Cancel
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="rounded-[2rem] border border-sky-300/20 bg-slate-950/35 p-5">
          <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-200">Position Pools</h2>
          <div className="mt-4 grid gap-3">
            {positions.filter((item) => item !== "ALL").map((item) => {
              const tone = positionTone(item);
              return (
                <button key={item} type="button" onClick={() => setPosition(item)} className={`group rounded-[1.35rem] border ${tone.border} ${tone.bg} p-4 text-left transition-all duration-200 hover:-translate-y-1 ${tone.glow}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[10px] font-black uppercase tracking-[0.22em] ${tone.text}`}>{item} Pool</p>
                    <Zap className={`h-4 w-4 ${tone.text} transition-transform group-hover:rotate-12 group-hover:scale-110`} />
                  </div>
                  <p className="mt-2 text-3xl font-black text-slate-50">{positionCounts[item] ?? 0}</p>
                  <p className="mt-1 text-xs font-bold text-slate-500">{isPreDraft ? "In draft pool" : "Available in this league"}</p>
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
