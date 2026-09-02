import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { ArrowDown, ArrowUp, Pencil, Search, Sparkles, UserPlus, Zap } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { useLeagueDetail, useLeagueWaiverTab } from "@/hooks/use-leagues";
import { usePlayerCard } from "@/hooks/use-players";
import {
  useAddFreeAgent,
  useCancelWaiverClaim,
  useEditWaiverClaim,
  useReorderWaiverClaims,
  useSubmitWaiverClaim,
} from "@/hooks/use-waivers";
import {
  useCreateWatchlist,
  useToggleWatchlistPlayer,
  useWatchlists,
} from "@/hooks/use-watchlists";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import { formatProjectionDisplay } from "@/lib/projection-display";
import type { PlayerStats } from "@/types/player";

const positions = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;
type AvailablePlayerRow = {
  id: number;
  name: string;
  school: string | null;
  opponent: string | null;
  position: string | null;
  weekly_projected_fantasy_points: number | null;
  final_fantasy_points: number | null;
  projection_status: string;
  availability_state: string;
  available_at: string | null;
  rank: number;
  projection?: PlayerStats | null;
};

const positionTone = (position?: string | null) => {
  switch ((position ?? "").toUpperCase()) {
    case "QB":
      return {
        border: "border-blue-300/45",
        bg: "bg-blue-400/10",
        text: "text-blue-100",
        glow: "",
        dot: "bg-blue-300",
      };
    case "RB":
      return {
        border: "border-emerald-300/45",
        bg: "bg-emerald-400/10",
        text: "text-emerald-100",
        glow: "",
        dot: "bg-emerald-300",
      };
    case "WR":
      return {
        border: "border-violet-300/45",
        bg: "bg-violet-400/10",
        text: "text-violet-100",
        glow: "",
        dot: "bg-violet-300",
      };
    case "TE":
      return {
        border: "border-amber-300/45",
        bg: "bg-amber-400/10",
        text: "text-amber-100",
        glow: "",
        dot: "bg-amber-300",
      };
    case "K":
      return {
        border: "border-sky-300/45",
        bg: "bg-sky-400/10",
        text: "text-sky-100",
        glow: "",
        dot: "bg-sky-300",
      };
    default:
      return {
        border: "border-slate-300/25",
        bg: "bg-white/5",
        text: "text-slate-100",
        glow: "",
        dot: "bg-slate-400",
      };
  }
};

const formatProcessTime = (value?: string | null, timezone?: string | number | boolean) => {
  if (!value) return "the next waiver processing window";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "the next waiver processing window";
  const timeZone = typeof timezone === "string" ? timezone : undefined;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(date);
};

const canClaimAvailability = (value?: string | null) => !value || value === "waivers" || value === "free_agent";

const availabilityLabel = (value?: string | null) => {
  switch (value) {
    case "free_agent":
      return "Free agent";
    case "waiver_locked":
      return "Waiver lock";
    case "claim_pending":
      return "Claim pending";
    case "game_locked":
      return "Game locked";
    default:
      return "On waivers";
  }
};

export const waiverProjectionLabel = (
  points: number | null | undefined,
  projectionStatus: string | null | undefined,
) => formatProjectionDisplay(points, projectionStatus);

export const waiverWeekPoints = (
  finalPoints: number | null | undefined,
  projectedPoints: number | null | undefined,
  projectionStatus: string | null | undefined,
) => {
  if (typeof finalPoints === "number" && Number.isFinite(finalPoints)) {
    return { label: finalPoints.toFixed(1), isFinal: true };
  }
  return {
    label: waiverProjectionLabel(projectedPoints, projectionStatus),
    isFinal: false,
  };
};

export const waiverOpponentLabel = (opponent: string | null | undefined) => opponent?.trim() || "—";

export default function LeagueWaivers() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState<(typeof positions)[number]>("ALL");
  const [selectedPlayer, setSelectedPlayer] = useState<AvailablePlayerRow | null>(null);
  const [claimPlayer, setClaimPlayer] = useState<AvailablePlayerRow | null>(null);
  const [dropRosterEntryId, setDropRosterEntryId] = useState("none");
  const [faabBid, setFaabBid] = useState("0");
  const [preferenceOrder, setPreferenceOrder] = useState("1");
  const [editingClaimId, setEditingClaimId] = useState<number | null>(null);
  const [claimError, setClaimError] = useState<string | null>(null);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const postDraft = isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });
  const waiverQuery = useLeagueWaiverTab(parsedLeagueId, 1000, 0, postDraft);
  const waiverData = waiverQuery.data;
  const nextWaiverProcessAt = typeof waiverData?.waiver_rules.next_process_at === "string"
    ? waiverData.waiver_rules.next_process_at
    : null;
  const addFreeAgent = useAddFreeAgent(parsedLeagueId);
  const submitWaiverClaim = useSubmitWaiverClaim(parsedLeagueId);
  const cancelWaiverClaim = useCancelWaiverClaim(parsedLeagueId);
  const editWaiverClaim = useEditWaiverClaim(parsedLeagueId);
  const reorderWaiverClaims = useReorderWaiverClaims(parsedLeagueId);
  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    postDraft && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const createWatchlist = useCreateWatchlist();
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const selectedPlayerCardQuery = usePlayerCard(
    selectedPlayer?.id,
    Boolean(selectedPlayer?.id)
  );
  const players = useMemo<AvailablePlayerRow[]>(() =>
    (waiverData?.available_players ?? []).map((player, index) => ({
        ...player,
        rank: index + 1,
    })),
  [waiverData?.available_players]);
  const watchlists = watchlistsQuery.data?.data ?? [];
  const primaryWatchlist = watchlists[0] ?? null;
  const watchedPlayerIds = useMemo(
    () => new Set(watchlists.flatMap((watchlist) => watchlist.players.map((player) => player.id))),
    [watchlists]
  );
  const filteredPlayers = useMemo(() => {
    const query = search.trim().toLowerCase();
    return players
      .filter((player) => position === "ALL" || (player.position ?? "").toUpperCase() === position)
      .filter((player) => {
        if (!query) return true;
        return [player.name, player.school, player.opponent, player.position]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      });
  }, [players, position, search]);

  const topProjection = players.reduce<number | null>((top, player) => {
    const projection = player.weekly_projected_fantasy_points;
    if (typeof projection !== "number" || !Number.isFinite(projection)) return top;
    return top === null ? projection : Math.max(top, projection);
  }, null);
  const positionCounts = players.reduce<Record<string, number>>((counts, player) => {
    const key = (player.position ?? "UNK").toUpperCase();
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});

  const handleWatchPlayer = async (playerId: number) => {
    if (watchlistsQuery.isError) {
      toast({
        title: "Unable to update watchlist",
        description:
          watchlistsQuery.error instanceof Error
            ? watchlistsQuery.error.message
            : "Reload the watchlist after the backend is reachable.",
        variant: "destructive",
      });
      return;
    }

    try {
      const watchlist =
        primaryWatchlist ??
        (await createWatchlist.mutateAsync({
          name: "League Watchlist",
          league_id: parsedLeagueId,
        }));

      await toggleWatchlistPlayer.mutateAsync({
        watchlistId: watchlist.id,
        playerId,
        isSaved: watchedPlayerIds.has(playerId),
      });

      toast({
        title: watchedPlayerIds.has(playerId) ? "Removed from watchlist" : "Added to watchlist",
        description: "Open the Watchlist tab to review saved available-player targets.",
      });
    } catch (error) {
      toast({
        title: "Unable to update watchlist",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const openClaimDialog = (player: AvailablePlayerRow) => {
    setClaimPlayer(player);
    setDropRosterEntryId("none");
    setFaabBid("0");
    setPreferenceOrder(String((waiverData?.claims.filter((claim) => claim.status === "pending").length ?? 0) + 1));
    setEditingClaimId(null);
    setClaimError(null);
  };

  const openEditClaimDialog = (claim: NonNullable<typeof waiverData>["claims"][number]) => {
    setClaimPlayer({
      id: claim.add_player_id,
      name: claim.add_player_name,
      school: null,
      opponent: null,
      position: null,
      weekly_projected_fantasy_points: 0,
      final_fantasy_points: null,
      projection_status: "UNAVAILABLE",
      availability_state: "waivers",
      available_at: null,
      rank: claim.preference_order,
    });
    setDropRosterEntryId(claim.drop_roster_entry_id ? String(claim.drop_roster_entry_id) : "none");
    setFaabBid(String(claim.faab_bid));
    setPreferenceOrder(String(claim.preference_order));
    setEditingClaimId(claim.id);
    setClaimError(null);
  };

  const submitClaim = async () => {
    if (!claimPlayer || !waiverData?.fantasy_team_id) {
      setClaimError("Your team is not available for this waiver claim.");
      return;
    }
    const isFreeAgentAdd = claimPlayer.availability_state === "free_agent";
    const usesFaab = !isFreeAgentAdd && waiverData?.waiver_rules.waiver_type === "faab";
    const bid = usesFaab ? Number(faabBid) : 0;
    if (usesFaab && (!Number.isInteger(bid) || bid < 0)) {
      setClaimError("Enter a whole-dollar FAAB bid of $0 or more.");
      return;
    }
    try {
      if (isFreeAgentAdd) {
        await addFreeAgent.mutateAsync({
          playerId: claimPlayer.id,
          payload: {
            team_id: waiverData.fantasy_team_id,
            drop_roster_entry_id: dropRosterEntryId === "none" ? undefined : Number(dropRosterEntryId),
          },
        });
        toast({
          title: "Free agent added",
          description: `${claimPlayer.name} was added to your roster immediately.`,
        });
        setClaimPlayer(null);
        return;
      }
      const payload = {
        team_id: waiverData.fantasy_team_id,
        add_player_id: claimPlayer.id,
        drop_roster_entry_id: dropRosterEntryId === "none" ? undefined : Number(dropRosterEntryId),
        faab_bid: bid,
        preference_order: Number(preferenceOrder),
      };
      const claim = editingClaimId
        ? await editWaiverClaim.mutateAsync({ claimId: editingClaimId, payload })
        : await submitWaiverClaim.mutateAsync(payload);
      toast({
        title: editingClaimId ? "Waiver claim updated" : "Waiver claim submitted",
        description: `${claim.add_player_name} will process ${formatProcessTime(
          claim.process_after,
          waiverData?.waiver_rules.timezone
        )}.`,
      });
      setClaimPlayer(null);
      setEditingClaimId(null);
    } catch (error) {
      setClaimError(error instanceof Error ? error.message : "Unable to submit waiver claim.");
    }
  };

  const cancelClaim = async (claimId: number) => {
    try {
      await cancelWaiverClaim.mutateAsync({ claimId });
      toast({ title: "Waiver claim cancelled" });
    } catch (error) {
      toast({
        title: "Unable to cancel waiver claim",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const moveClaim = async (claimId: number, direction: -1 | 1) => {
    const pendingClaims = (waiverData?.claims ?? [])
      .filter((claim) => claim.status === "pending")
      .sort((left, right) => left.preference_order - right.preference_order || left.id - right.id);
    const currentIndex = pendingClaims.findIndex((claim) => claim.id === claimId);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= pendingClaims.length) return;
    const reordered = [...pendingClaims];
    [reordered[currentIndex], reordered[targetIndex]] = [reordered[targetIndex], reordered[currentIndex]];
    try {
      await reorderWaiverClaims.mutateAsync(reordered.map((claim) => claim.id));
      toast({ title: "Claim order updated" });
    } catch (error) {
      toast({
        title: "Unable to reorder claims",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  if (leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-0 py-4 sm:px-6 sm:py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8">
        <ErrorState
          title="Unable to load league"
          message="The league could not be loaded. Confirm the backend is available, then try again."
          retryLabel="Try Again"
          onRetry={() => void leagueQuery.refetch()}
        />
      </main>
    );
  }

  if (!postDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/lobby`} replace />;
  }

  return (
    <main className="relative mx-auto flex w-full max-w-none flex-col gap-6 px-0 py-4 sm:px-0 sm:py-8">
      <Dialog open={Boolean(claimPlayer)} onOpenChange={(open) => {
        if (!open) {
          setClaimPlayer(null);
          setEditingClaimId(null);
        }
      }}>
        <DialogContent className="max-w-xl border-sky-300/20 bg-[#101928]">
          <DialogHeader>
            <DialogTitle className="pr-8 text-2xl font-black uppercase italic text-slate-50">
              {editingClaimId ? "Edit Waiver Claim" : claimPlayer?.availability_state === "free_agent" ? "Add Free Agent" : "Submit Waiver Claim"}
            </DialogTitle>
            <DialogDescription className="text-sm font-semibold leading-6 text-slate-300">
              {claimPlayer?.availability_state === "free_agent"
                ? `Add ${claimPlayer?.name ?? "this player"} immediately and choose an optional roster drop. The backend verifies availability, lineup locks, and roster legality before completing the transaction.`
                : `Add ${claimPlayer?.name ?? "this player"} and choose an optional roster drop. The backend verifies player availability, lineup locks, FAAB, and roster legality before saving the claim.`}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="rounded-2xl border border-sky-300/15 bg-sky-300/[0.06] p-4">
              <p className="text-sm font-black text-slate-50">Add: {claimPlayer?.name}</p>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">
                {claimPlayer?.position ?? "-"} · {claimPlayer?.school ?? "-"} · {claimPlayer?.opponent ? `vs ${claimPlayer.opponent}` : "Opponent unavailable"} · {(() => {
                  const points = waiverWeekPoints(
                    claimPlayer?.final_fantasy_points,
                    claimPlayer?.weekly_projected_fantasy_points,
                    claimPlayer?.projection_status,
                  );
                  return `${points.label} ${points.isFinal ? "final" : "projected"} points`;
                })()}
              </p>
            </div>
            <label className="grid gap-2">
              <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Drop Player (optional)</span>
              <Select value={dropRosterEntryId} onValueChange={setDropRosterEntryId}>
                <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-slate-950/45 text-slate-50"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No drop selected</SelectItem>
                  {(waiverData?.roster ?? []).map((entry) => (
                    <SelectItem key={entry.roster_entry_id} value={String(entry.roster_entry_id)}>
                      {entry.player_name} · {entry.slot}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            {claimPlayer?.availability_state === "free_agent" ? (
              <p className="rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.06] p-3 text-xs font-semibold text-emerald-100">
                This player cleared waivers and can be added immediately. No FAAB bid or waiver priority is used.
              </p>
            ) : waiverData?.waiver_rules.waiver_type === "faab" ? (
              <label className="grid gap-2">
                <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">FAAB Bid</span>
                <Input type="number" min="0" step="1" value={faabBid} onChange={(event) => setFaabBid(event.target.value)} className="h-12 rounded-2xl border-white/10 bg-slate-950/45 text-sm font-bold text-slate-50" />
                <p className="text-xs font-semibold text-slate-400">
                  ${waiverData?.faab_remaining ?? waiverData?.waiver_rules.faab_budget ?? 0} remaining. Your bid stays hidden until waivers process.
                </p>
              </label>
            ) : (
              <p className="rounded-2xl border border-violet-300/15 bg-violet-300/[0.06] p-3 text-xs font-semibold text-violet-100">
                Your waiver priority is #{waiverData?.waiver_priority ?? "pending"}. Successful claims move your team to the back of the order.
              </p>
            )}
            {claimPlayer?.availability_state !== "free_agent" ? (
              <>
                <label className="grid gap-2">
                  <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Claim Order</span>
                  <Input
                    type="number"
                    min="1"
                    step="1"
                    value={preferenceOrder}
                    onChange={(event) => setPreferenceOrder(event.target.value)}
                    className="h-12 rounded-2xl border-white/10 bg-slate-950/45 text-sm font-bold text-slate-50"
                  />
                  <p className="text-xs font-semibold text-slate-400">Lower numbers process first for your team.</p>
                </label>
                <p className="rounded-2xl border border-white/10 bg-black/15 p-3 text-xs font-semibold leading-5 text-slate-300">
                  Processing is scheduled by the league waiver window. The confirmed claim shows its exact processing time.
                </p>
              </>
            ) : null}
            {claimError ? <p className="text-xs font-bold text-red-300">{claimError}</p> : null}
            <Button type="button" className="h-12 rounded-2xl bg-sky-300 text-[10px] font-black uppercase tracking-[0.2em] text-slate-950 hover:bg-sky-200" onClick={() => void submitClaim()} disabled={submitWaiverClaim.isPending || editWaiverClaim.isPending || addFreeAgent.isPending || !claimPlayer}>
              {submitWaiverClaim.isPending || editWaiverClaim.isPending || addFreeAgent.isPending
                ? "Saving..."
                : editingClaimId
                  ? "Save Waiver Claim"
                  : claimPlayer?.availability_state === "free_agent"
                    ? "Add Free Agent"
                    : "Confirm Waiver Claim"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <div className="space-y-3 sm:space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cfb-brand">
          Waiver Wire
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="cfb-display-title text-3xl text-cfb-text-primary sm:text-4xl">Available Players</h1>
            <p className="mt-1.5 max-w-2xl text-sm text-cfb-text-secondary sm:mt-2">
              Unrostered players are instant adds until their own kickoff. Once a player’s game has started, claims process at ${formatProcessTime(nextWaiverProcessAt, waiverData?.waiver_rules.timezone)}.
            </p>
          </div>
          <p className="text-xs font-semibold text-cfb-text-secondary sm:hidden">
            {players.length} available · Top proj {topProjection?.toFixed(1) ?? "—"} · {waiverData?.claims.length ?? 0} claims
          </p>
          <div className="hidden overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised sm:grid sm:min-w-[390px] sm:grid-cols-3">
            <div className="px-4 py-3">
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">Available</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-cfb-text-primary">{players.length}</p>
            </div>
            <div className="border-x border-cfb-border-subtle px-4 py-3">
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">Top proj</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-cfb-text-primary">{topProjection?.toFixed(1) ?? "—"}</p>
            </div>
            <div className="px-4 py-3">
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">Claims</p>
              <p className="mt-1 text-xl font-semibold tabular-nums text-cfb-text-primary">{waiverData?.claims.length ?? 0}</p>
            </div>
          </div>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

      <section data-testid="league-player-board" className="overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface">
        <div className="border-b border-cfb-border-subtle px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.18em] text-cfb-brand">
                Available Players
              </h2>
              <p className="mt-1.5 text-xs font-semibold leading-5 text-cfb-text-secondary sm:mt-2">
                Players are instant adds before their own kickoff. After kickoff, claims process at ${formatProcessTime(nextWaiverProcessAt, waiverData?.waiver_rules.timezone)}.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative w-full sm:min-w-[280px]">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-cfb-text-muted" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search players, schools..."
                  className="h-10 rounded-md border-cfb-border-subtle bg-cfb-canvas pl-10 text-sm font-semibold text-cfb-text-primary placeholder:text-cfb-text-muted focus:border-cfb-brand/60 focus:ring-cfb-brand/20"
                />
              </div>
              <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {positions.map((item) => {
                  const active = position === item;
                  const tone = positionTone(item === "ALL" ? null : item);
                  return (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setPosition(item)}
                      className={[
                        "h-10 shrink-0 rounded-md border px-3 text-[10px] font-black uppercase tracking-[0.12em] transition-colors",
                        active
                          ? "border-cfb-brand/60 bg-cfb-brand/10 text-cfb-brand"
                          : "border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-secondary hover:border-cfb-border-strong hover:text-cfb-text-primary",
                      ].join(" ")}
                    >
                      {item}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        {waiverQuery.isLoading ? (
          <p className="px-5 py-6 text-sm text-slate-400">
            Loading league-specific available players…
          </p>
        ) : waiverQuery.isError ? (
          <p className="px-5 py-6 text-sm font-black uppercase tracking-[0.16em] text-red-300">
            Unable to load the league waiver pool
            {waiverQuery.error instanceof Error ? `: ${waiverQuery.error.message}` : "."}
          </p>
        ) : filteredPlayers.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-400">
            No league-scoped available players match the current filters.
          </p>
        ) : (
          <>
            <div className="divide-y divide-cfb-border-subtle sm:hidden">
            {filteredPlayers.map((player) => {
              const tone = positionTone(player.position);
              const weekPoints = waiverWeekPoints(
                player.final_fantasy_points,
                player.weekly_projected_fantasy_points,
                player.projection_status,
              );
              const claimable = canClaimAvailability(player.availability_state);
              const watching = watchedPlayerIds.has(player.id);
              return (
                <div
                  key={player.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedPlayer(player)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedPlayer(player);
                    }
                  }}
                  className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-cfb-surface-hover focus:outline-none focus-visible:bg-cfb-surface-hover"
                  data-testid={`waiver-mobile-player-row-${player.id}`}
                >
                  <span
                    data-testid={`waiver-mobile-rank-${player.id}`}
                    className="min-w-[2ch] text-right text-lg font-semibold tabular-nums text-cfb-text-muted"
                  >
                    {player.rank}
                  </span>
                  <div className="min-w-0">
                    <div className="flex min-w-0 items-center gap-2">
                      <p className="truncate text-sm font-bold text-cfb-text-primary">{player.name}</p>
                      <span className={`inline-flex shrink-0 rounded-md border px-1.5 py-0.5 text-[8px] font-black uppercase tracking-[0.1em] ${tone.border} ${tone.bg} ${tone.text}`}>
                        {player.position ?? "-"}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-[10px] font-bold uppercase tracking-[0.1em] text-cfb-text-muted">
                      {player.school ?? "School unavailable"} · {player.opponent ? `vs ${player.opponent}` : "Opponent unavailable"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <div className="text-right">
                      <p className="text-[8px] font-black uppercase tracking-[0.1em] text-cfb-text-muted">{weekPoints.isFinal ? "Final" : `W${waiverData?.current_period?.week ?? 1}`}</p>
                      <p
                        data-testid={`waiver-mobile-week-points-${player.id}`}
                        className={`mt-0.5 text-base font-semibold tabular-nums ${weekPoints.isFinal ? "text-cfb-brand" : weekPoints.label === "BYE" ? "text-amber-200" : weekPoints.label === "OUT" ? "text-rose-200" : "text-cfb-text-primary"}`}
                      >
                        {weekPoints.label}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      aria-label={watching ? `Remove ${player.name} from watchlist` : `Watch ${player.name}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        void handleWatchPlayer(player.id);
                      }}
                      disabled={createWatchlist.isPending || toggleWatchlistPlayer.isPending || watchlistsQuery.isError}
                      className="h-9 w-9 rounded-md border-cfb-border-subtle bg-cfb-surface-raised p-0 text-cfb-text-secondary hover:border-cfb-border-strong hover:bg-cfb-surface-hover hover:text-cfb-text-primary"
                    >
                      <Sparkles className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      disabled={!waiverData?.fantasy_team_id || !claimable}
                      onClick={(event) => {
                        event.stopPropagation();
                        openClaimDialog(player);
                      }}
                      className="h-9 rounded-md bg-cfb-brand px-3 text-[9px] font-black uppercase tracking-[0.1em] text-cfb-canvas shadow-none hover:bg-cfb-brand-hover disabled:opacity-50"
                    >
                      {claimable ? (player.availability_state === "free_agent" ? "Add" : "Claim") : "Locked"}
                    </Button>
                  </div>
                </div>
              );
            })}
            </div>
            <div className="hidden overflow-x-auto sm:block">
            <table className="min-w-[1100px] w-full table-fixed text-left">
              <thead className="border-b border-cfb-border-subtle bg-cfb-surface-raised">
                <tr className="text-[10px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
                  <th className="w-[7rem] min-w-[7rem] whitespace-nowrap px-5 py-3 text-right">RK</th>
                  <th className="px-4 py-3">Player</th>
                  <th className="w-44 px-4 py-3">School</th>
                  <th className="w-44 px-4 py-3">Opponent</th>
                  <th className="w-24 px-4 py-3">POS</th>
                  <th className="w-32 px-4 py-3 text-right">
                    Week {waiverData?.current_period?.week ?? 1} Pts
                  </th>
                  <th className="w-56 px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cfb-border-subtle">
                {filteredPlayers.map((player) => {
                  const tone = positionTone(player.position);
                  const weekPoints = waiverWeekPoints(
                    player.final_fantasy_points,
                    player.weekly_projected_fantasy_points,
                    player.projection_status,
                  );
                  const claimable = canClaimAvailability(player.availability_state);
                  return (
                    <tr
                      key={player.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedPlayer(player)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedPlayer(player);
                        }
                      }}
                      className="group cursor-pointer text-sm text-cfb-text-secondary transition-colors hover:bg-cfb-surface-hover focus:outline-none focus-visible:bg-cfb-surface-hover"
                    >
                      <td className="w-[7rem] min-w-[7rem] whitespace-nowrap px-5 py-3 text-right align-middle">
                        <span
                          data-testid={`waiver-rank-${player.id}`}
                          className="inline-flex min-w-[4ch] justify-end whitespace-nowrap text-lg font-semibold tabular-nums text-cfb-text-muted transition-colors group-hover:text-cfb-text-primary"
                        >
                          {player.rank}
                        </span>
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <div className="min-w-0">
                          <p className="truncate text-base font-bold text-cfb-text-primary transition-colors">
                            {player.name}
                          </p>
                          <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.12em] text-cfb-text-muted">
                            Available player
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3 align-middle text-sm font-semibold text-cfb-text-secondary">
                        {player.school ?? "-"}
                      </td>
                      <td className="px-4 py-3 align-middle text-sm font-semibold text-cfb-text-secondary">
                        {waiverOpponentLabel(player.opponent)}
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <span
                          className={`inline-flex min-w-12 items-center justify-center rounded-md border px-2.5 py-1.5 text-[10px] font-black uppercase tracking-[0.1em] ${tone.border} ${tone.bg} ${tone.text}`}
                        >
                          {player.position ?? "-"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right align-middle">
                        <span
                          data-testid={`waiver-week-points-${player.id}`}
                          className={`text-lg font-semibold tabular-nums ${weekPoints.isFinal ? "text-cfb-brand" : weekPoints.label === "BYE" ? "text-amber-200" : weekPoints.label === "OUT" ? "text-rose-200" : "text-cfb-text-primary"}`}
                        >
                          {weekPoints.label}
                        </span>
                      </td>
                      <td className="px-5 py-3 align-middle">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleWatchPlayer(player.id);
                            }}
                            disabled={
                              createWatchlist.isPending ||
                              toggleWatchlistPlayer.isPending ||
                              watchlistsQuery.isError
                            }
                            className="h-9 rounded-md border-cfb-border-subtle bg-cfb-surface-raised px-3 text-[10px] font-black uppercase tracking-[0.1em] text-cfb-text-secondary transition-colors hover:border-cfb-border-strong hover:bg-cfb-surface-hover hover:text-cfb-text-primary"
                          >
                            <Sparkles className="mr-2 h-3.5 w-3.5" />
                            {watchedPlayerIds.has(player.id) ? "Watching" : "Watch"}
                          </Button>
                          <Button
                            type="button"
                            disabled={!waiverData?.fantasy_team_id || !claimable}
                            onClick={(event) => {
                              event.stopPropagation();
                              openClaimDialog(player);
                            }}
                            className="h-9 rounded-md bg-cfb-brand px-3 text-[10px] font-black uppercase tracking-[0.1em] text-cfb-canvas shadow-none hover:bg-cfb-brand-hover disabled:opacity-50"
                          >
                            <UserPlus className="mr-2 h-3.5 w-3.5" />
                            {claimable
                              ? player.availability_state === "free_agent"
                                ? "Add"
                                : "Claim"
                              : availabilityLabel(player.availability_state)}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </>
        )}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">
                Waiver Claims
              </p>
              <p className="text-[10px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
                {String(waiverData?.waiver_rules.waiver_type ?? "waivers")}
              </p>
            </div>
            {(waiverData?.claims ?? []).length === 0 ? (
              <p className="mt-4 text-sm font-medium text-cfb-text-muted">
                No active or recent waiver claims for your team.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {waiverData?.claims.map((claim) => (
                  <div key={claim.id} className="rounded-md border border-cfb-border-subtle bg-cfb-canvas p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-cfb-text-primary">{claim.add_player_name}</p>
                        <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-muted">
                          {claim.drop_player_name ? `Drop ${claim.drop_player_name}` : "No drop selected"}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] font-black uppercase tracking-[0.14em] text-cfb-brand">
                          {claim.status}
                        </p>
                        <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-muted">
                          {waiverData?.waiver_rules.waiver_type === "faab" ? `FAAB $${claim.faab_bid}` : `Order ${claim.preference_order}`}
                        </p>
                      </div>
                    </div>
                    {claim.failure_reason ? (
                      <p className="mt-3 rounded-xl border border-red-300/20 bg-red-500/10 px-3 py-2 text-xs font-bold text-red-100">
                        {claim.failure_reason}
                      </p>
                    ) : null}
                    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-muted">
                      {claim.status.toLowerCase() === "pending"
                        ? `Order ${claim.preference_order} · Processes ${formatProcessTime(claim.process_after, waiverData?.waiver_rules.timezone)}`
                        : `Updated ${formatProcessTime(claim.processed_at, waiverData?.waiver_rules.timezone)}`}
                    </p>
                    {claim.status.toLowerCase() === "pending" ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          className="h-8 rounded-md border-cfb-border-strong px-3 text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-primary hover:bg-cfb-surface-hover"
                          disabled={editWaiverClaim.isPending}
                          onClick={() => openEditClaimDialog(claim)}
                        >
                          <Pencil className="mr-1.5 h-3.5 w-3.5" /> Edit
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-8 rounded-md border-cfb-border-subtle px-2.5 text-cfb-text-secondary hover:bg-cfb-surface-hover"
                          disabled={reorderWaiverClaims.isPending || claim.preference_order <= 1}
                          onClick={() => void moveClaim(claim.id, -1)}
                          aria-label={`Move ${claim.add_player_name} claim up`}
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-8 rounded-md border-cfb-border-subtle px-2.5 text-cfb-text-secondary hover:bg-cfb-surface-hover"
                          disabled={reorderWaiverClaims.isPending}
                          onClick={() => void moveClaim(claim.id, 1)}
                          aria-label={`Move ${claim.add_player_name} claim down`}
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-8 rounded-md border-red-400/30 px-3 text-[9px] font-black uppercase tracking-[0.14em] text-red-200 hover:bg-red-500/10"
                          disabled={cancelWaiverClaim.isPending}
                          onClick={() => void cancelClaim(claim.id)}
                        >
                          {cancelWaiverClaim.isPending ? "Cancelling..." : "Cancel Claim"}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-primary">
              Drop Candidates
            </p>
            {(waiverData?.roster ?? []).length === 0 ? (
              <p className="mt-4 text-sm font-medium text-cfb-text-muted">
                No roster entries loaded for your team.
              </p>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {waiverData?.roster.map((entry) => (
                  <div key={entry.roster_entry_id} className="rounded-md border border-cfb-border-subtle bg-cfb-canvas p-3">
                    <p className="truncate text-sm font-semibold text-cfb-text-primary">{entry.player_name}</p>
                    <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-muted">
                      {entry.position ?? "-"} · {entry.school ?? "-"} · {entry.slot}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
      </section>

      <section className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-primary">
              {waiverData?.waiver_rules.waiver_type === "faab"
                ? `Top FAAB Bids — Week ${waiverData?.results_period?.week ?? "Recent"}`
                : `Successful Waiver Claims — Week ${waiverData?.results_period?.week ?? "Recent"}`}
            </p>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-muted">Completed only</p>
          </div>
          {(waiverData?.results ?? []).length === 0 ? (
            <p className="mt-4 text-sm font-medium text-cfb-text-muted">No completed waiver awards yet.</p>
          ) : (
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {waiverData?.results.map((claim) => (
                <div key={claim.id} className="rounded-md border border-cfb-border-subtle bg-cfb-canvas p-3">
                  <p className="text-sm font-semibold text-cfb-text-primary">{claim.add_player_name}</p>
                  <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-cfb-text-secondary">
                    {waiverData?.waiver_rules.waiver_type === "faab"
                      ? `Won for $${claim.winning_bid ?? claim.faab_bid} FAAB`
                      : `Priority #${claim.prior_priority ?? "—"} → #${claim.resulting_priority ?? "—"}`}
                  </p>
                  <p className="mt-2 text-xs font-medium text-cfb-text-muted">
                    Processed {formatProcessTime(claim.processed_at, waiverData?.waiver_rules.timezone)}
                  </p>
                </div>
              ))}
            </div>
          )}
      </section>

      <section className="grid gap-4 md:grid-cols-5">
        {positions
          .filter((item) => item !== "ALL")
          .map((item) => {
            return (
              <button
                key={item}
                type="button"
                onClick={() => setPosition(item)}
                className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3 text-left transition-colors hover:border-cfb-border-strong hover:bg-cfb-surface-hover"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-secondary">
                    {item} Pool
                  </p>
                  <Zap className="h-3.5 w-3.5 text-cfb-text-muted" />
                </div>
                <p className="mt-2 text-xl font-semibold tabular-nums text-cfb-text-primary">{positionCounts[item] ?? 0}</p>
                <p className="mt-1 text-xs font-medium text-cfb-text-muted">Available in this league only</p>
              </button>
            );
          })}
      </section>
      {selectedPlayer ? (
        <PlayerCardModal
          card={selectedPlayerCardQuery.data}
          error={selectedPlayerCardQuery.isError}
          leagueId={Number.isFinite(parsedLeagueId) ? parsedLeagueId : undefined}
          loading={selectedPlayerCardQuery.isLoading}
          onClose={() => setSelectedPlayer(null)}
          onRetry={() => void selectedPlayerCardQuery.refetch()}
          player={{
            id: selectedPlayer.id,
            name: selectedPlayer.name,
            school: selectedPlayer.school,
            position: selectedPlayer.position,
            rankLabel: undefined,
            projectedPoints: selectedPlayer.weekly_projected_fantasy_points,
            playerClass: null,
            status: null,
            projection: selectedPlayer.projection,
            hasWeeklyProjection: selectedPlayer.weekly_projected_fantasy_points !== null && selectedPlayer.weekly_projected_fantasy_points !== undefined,
            sheetProjectionStats: null,
          }}
          title="Available Player"
        />
      ) : null}
    </main>
  );
}
