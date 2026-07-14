import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Search, Sparkles, UserPlus, Zap } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { useLeagueWaiverTab } from "@/hooks/use-leagues";
import { useDraftPlayerPool, usePlayerCard } from "@/hooks/use-players";
import {
  useCreateWatchlist,
  useToggleWatchlistPlayer,
  useWatchlists,
} from "@/hooks/use-watchlists";
import { DEMO_LEAGUE_ID, createDemoLeagueWaiverResponse } from "@/lib/leaguePreviewData";
import { buildDraftBoard } from "@/lib/draftRankings";
import type { PlayerStats } from "@/types/player";

const positions = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;
const availablePlayersDraftConfig = {
  leagueSize: 12,
  rosterSlots: {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    K: 1,
    BE: 5,
    IR: 0,
  },
};

type AvailablePlayerRow = {
  id: number;
  name: string;
  school: string | null;
  position: string | null;
  weekly_projected_fantasy_points: number;
  rank: number;
  playerClass?: string | null;
  status?: string | null;
  projection?: PlayerStats | null;
  sheetProjectionStats?: Record<string, number | null | undefined> | null;
};

const positionTone = (position?: string | null) => {
  switch ((position ?? "").toUpperCase()) {
    case "QB":
      return {
        border: "border-blue-300/45",
        bg: "bg-blue-400/10",
        text: "text-blue-100",
        glow: "shadow-[0_0_26px_rgba(96,165,250,0.18)]",
        dot: "bg-blue-300",
      };
    case "RB":
      return {
        border: "border-emerald-300/45",
        bg: "bg-emerald-400/10",
        text: "text-emerald-100",
        glow: "shadow-[0_0_26px_rgba(52,211,153,0.18)]",
        dot: "bg-emerald-300",
      };
    case "WR":
      return {
        border: "border-violet-300/45",
        bg: "bg-violet-400/10",
        text: "text-violet-100",
        glow: "shadow-[0_0_26px_rgba(167,139,250,0.18)]",
        dot: "bg-violet-300",
      };
    case "TE":
      return {
        border: "border-amber-300/45",
        bg: "bg-amber-400/10",
        text: "text-amber-100",
        glow: "shadow-[0_0_26px_rgba(251,191,36,0.16)]",
        dot: "bg-amber-300",
      };
    case "K":
      return {
        border: "border-sky-300/45",
        bg: "bg-sky-400/10",
        text: "text-sky-100",
        glow: "shadow-[0_0_26px_rgba(56,189,248,0.18)]",
        dot: "bg-sky-300",
      };
    default:
      return {
        border: "border-slate-300/25",
        bg: "bg-white/5",
        text: "text-slate-100",
        glow: "shadow-[0_0_20px_rgba(148,163,184,0.10)]",
        dot: "bg-slate-400",
      };
  }
};

export default function LeagueWaivers() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState<(typeof positions)[number]>("ALL");
  const [selectedPlayer, setSelectedPlayer] = useState<AvailablePlayerRow | null>(null);
  const waiverQuery = useLeagueWaiverTab(parsedLeagueId, 50, 0, !isDemoLeague);
  const waiverData = isDemoLeague ? createDemoLeagueWaiverResponse() : waiverQuery.data;
  const playerPoolQuery = useDraftPlayerPool({
    league_id: parsedLeagueId,
    available_only: !isDemoLeague && Number.isFinite(parsedLeagueId),
    limit: 200,
    offset: 0,
    fetchAll: true,
    sort: "draft_rank",
    enabled: !isDemoLeague && Number.isFinite(parsedLeagueId),
  });
  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    !isDemoLeague && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const createWatchlist = useCreateWatchlist();
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const { data: selectedPlayerCard, isLoading: selectedPlayerCardLoading } = usePlayerCard(
    selectedPlayer?.id,
    Boolean(selectedPlayer?.id)
  );
  const players = useMemo<AvailablePlayerRow[]>(() => {
    if (isDemoLeague) {
      return (waiverData?.available_players ?? []).map((player, index) => ({
        ...player,
        rank: index + 1,
      }));
    }

    return buildDraftBoard(playerPoolQuery.data?.data ?? [], availablePlayersDraftConfig)
      .map((player) => ({
        id: player.id,
        name: player.name,
        school: player.school,
        position: player.pos,
        weekly_projected_fantasy_points: player.projectedPoints,
        rank: player.masterDraftRank ?? player.draftRank,
        playerClass: player.playerClass,
        status: player.status,
        projection: player.projection,
        sheetProjectionStats: player.sheetProjectionStats,
      }))
      .sort((left, right) => {
        if (left.rank !== right.rank) return left.rank - right.rank;
        return left.name.localeCompare(right.name);
      });
  }, [isDemoLeague, playerPoolQuery.data?.data, waiverData?.available_players]);
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
        return [player.name, player.school, player.position]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      });
  }, [players, position, search]);

  const topProjection = players.reduce(
    (top, player) => Math.max(top, Number(player.weekly_projected_fantasy_points ?? 0)),
    0
  );
  const positionCounts = players.reduce<Record<string, number>>((counts, player) => {
    const key = (player.position ?? "UNK").toUpperCase();
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});

  const handleWatchPlayer = async (playerId: number) => {
    if (isDemoLeague) {
      toast({
        title: "Demo league watchlist",
        description: "Watchlists persist in real leagues after signing in.",
      });
      return;
    }

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

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[460px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_8%,rgba(56,189,248,0.2),transparent_32%),radial-gradient(circle_at_72%_0%,rgba(99,102,241,0.18),transparent_38%),radial-gradient(circle_at_50%_30%,rgba(14,165,233,0.12),transparent_42%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Players
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Available Players</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              League-scoped available players only. Review the waiver pool, current claims, and roster drop candidates from the live league API.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[430px]">
            <div className="rounded-[1.25rem] border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_0_34px_rgba(56,189,248,0.12)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Available</p>
              <p className="mt-1 text-2xl font-black text-sky-100">{players.length}</p>
            </div>
            <div className="rounded-[1.25rem] border border-emerald-300/20 bg-emerald-400/10 p-4 shadow-[0_0_34px_rgba(52,211,153,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Top Proj</p>
              <p className="mt-1 text-2xl font-black text-emerald-100">{topProjection.toFixed(1)}</p>
            </div>
            <div className="rounded-[1.25rem] border border-violet-300/20 bg-violet-400/10 p-4 shadow-[0_0_34px_rgba(167,139,250,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Claims</p>
              <p className="mt-1 text-2xl font-black text-violet-100">{waiverData?.claims.length ?? 0}</p>
            </div>
          </div>
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

      <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] shadow-[0_24px_90px_rgba(14,165,233,0.12)]">
        <div className="border-b border-sky-300/10 px-5 py-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-300">
                Available Players
              </h2>
              <p className="mt-2 text-xs font-semibold text-slate-500">
                Only players not owned on league rosters appear here. Claims are processed by the backend waiver lifecycle.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative min-w-[280px]">
                <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-sky-200/45" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search players, schools..."
                  className="h-12 rounded-2xl border-sky-300/15 bg-slate-950/55 pl-11 text-sm font-bold text-slate-50 placeholder:text-slate-500 focus:border-sky-300/45 focus:ring-sky-300/20"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {positions.map((item) => {
                  const active = position === item;
                  const tone = positionTone(item === "ALL" ? null : item);
                  return (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setPosition(item)}
                      className={[
                        "rounded-2xl border px-4 py-3 text-[10px] font-black uppercase tracking-[0.16em] transition-all duration-200",
                        active
                          ? `${tone.border} ${tone.bg} ${tone.text} ${tone.glow}`
                          : "border-white/10 bg-white/[0.04] text-slate-400 hover:border-sky-300/25 hover:bg-sky-300/[0.07] hover:text-slate-100",
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
        {!isDemoLeague && playerPoolQuery.isLoading ? (
          <p className="px-5 py-6 text-sm text-slate-400">
            Loading the full master-board player pool…
          </p>
        ) : !isDemoLeague && playerPoolQuery.isError ? (
          <p className="px-5 py-6 text-sm font-black uppercase tracking-[0.16em] text-red-300">
            Unable to load the full available-player board
            {playerPoolQuery.error instanceof Error ? `: ${playerPoolQuery.error.message}` : "."}
          </p>
        ) : filteredPlayers.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-400">
            No league-scoped available players match the current filters.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-[920px] w-full table-fixed text-left">
              <thead className="border-b border-sky-300/10 bg-slate-950/35">
                <tr className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                  <th className="w-20 px-5 py-4">RK</th>
                  <th className="px-4 py-4">Player</th>
                  <th className="w-44 px-4 py-4">School</th>
                  <th className="w-24 px-4 py-4">POS</th>
                  <th className="w-32 px-4 py-4 text-right">Week 1 Proj</th>
                  <th className="w-56 px-5 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sky-300/10">
                {filteredPlayers.map((player) => {
                  const tone = positionTone(player.position);
                  const projected = Number(player.weekly_projected_fantasy_points ?? 0);
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
                      className="group cursor-pointer text-sm text-slate-200 transition-colors hover:bg-sky-300/[0.045] focus:outline-none focus-visible:bg-sky-300/[0.065]"
                    >
                      <td className="px-5 py-4 align-middle">
                        <span className="text-xl font-black italic text-slate-500 transition-colors group-hover:text-sky-200">
                          {player.rank}
                        </span>
                      </td>
                      <td className="px-4 py-4 align-middle">
                        <div className="min-w-0">
                          <p className="truncate text-base font-black text-slate-50 transition-colors group-hover:text-sky-50">
                            {player.name}
                          </p>
                          <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                            Available player
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-4 align-middle text-sm font-bold uppercase tracking-[0.08em] text-slate-400">
                        {player.school ?? "-"}
                      </td>
                      <td className="px-4 py-4 align-middle">
                        <span
                          className={`inline-flex min-w-14 items-center justify-center rounded-xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] ${tone.border} ${tone.bg} ${tone.text}`}
                        >
                          {player.position ?? "-"}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-right align-middle">
                        <span className="text-lg font-black tabular-nums text-sky-100">
                          {projected.toFixed(1)}
                        </span>
                      </td>
                      <td className="px-5 py-4 align-middle">
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
                            className="h-10 rounded-xl border-sky-300/20 bg-sky-300/[0.06] px-3 text-[10px] font-black uppercase tracking-[0.14em] text-sky-100 transition-all hover:border-sky-200/45 hover:bg-sky-300/15"
                          >
                            <Sparkles className="mr-2 h-3.5 w-3.5" />
                            {watchedPlayerIds.has(player.id) ? "Watching" : "Watch"}
                          </Button>
                          <Button
                            type="button"
                            disabled
                            onClick={(event) => event.stopPropagation()}
                            className="h-10 rounded-xl bg-sky-300/75 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950 shadow-none"
                          >
                            <UserPlus className="mr-2 h-3.5 w-3.5" />
                            Claim API
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {!isDemoLeague ? (
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.035] p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-sky-300">
                Waiver Claims
              </p>
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                {String(waiverData?.waiver_rules.waiver_type ?? "waivers")}
              </p>
            </div>
            {(waiverData?.claims ?? []).length === 0 ? (
              <p className="mt-4 text-sm font-semibold text-slate-500">
                No active or recent waiver claims for your team.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {waiverData?.claims.map((claim) => (
                  <div key={claim.id} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-black text-slate-50">{claim.add_player_name}</p>
                        <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                          {claim.drop_player_name ? `Drop ${claim.drop_player_name}` : "No drop selected"}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-sky-200">
                          {claim.status}
                        </p>
                        <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                          FAAB {claim.faab_bid}
                        </p>
                      </div>
                    </div>
                    {claim.failure_reason ? (
                      <p className="mt-3 rounded-xl border border-red-300/20 bg-red-500/10 px-3 py-2 text-xs font-bold text-red-100">
                        {claim.failure_reason}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.035] p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-300">
              Drop Candidates
            </p>
            {(waiverData?.roster ?? []).length === 0 ? (
              <p className="mt-4 text-sm font-semibold text-slate-500">
                No roster entries loaded for your team.
              </p>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {waiverData?.roster.map((entry) => (
                  <div key={entry.roster_entry_id} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                    <p className="truncate text-sm font-black text-slate-50">{entry.player_name}</p>
                    <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                      {entry.position ?? "-"} · {entry.school ?? "-"} · {entry.slot}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-5">
        {positions
          .filter((item) => item !== "ALL")
          .map((item) => {
            const tone = positionTone(item);
            return (
              <button
                key={item}
                type="button"
                onClick={() => setPosition(item)}
                className={`group rounded-[1.35rem] border ${tone.border} ${tone.bg} p-5 text-left transition-all duration-200 hover:-translate-y-1 ${tone.glow}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className={`text-[10px] font-black uppercase tracking-[0.22em] ${tone.text}`}>
                    {item} Pool
                  </p>
                  <Zap className={`h-4 w-4 ${tone.text} transition-transform group-hover:rotate-12 group-hover:scale-110`} />
                </div>
                <p className="mt-2 text-3xl font-black text-slate-50">{positionCounts[item] ?? 0}</p>
                <p className="mt-2 text-xs font-bold text-slate-500">Available in this league only</p>
              </button>
            );
          })}
      </section>
      {selectedPlayer ? (
        <PlayerCardModal
          card={selectedPlayerCard}
          loading={selectedPlayerCardLoading}
          onClose={() => setSelectedPlayer(null)}
          player={{
            id: selectedPlayer.id,
            name: selectedPlayer.name,
            school: selectedPlayer.school,
            position: selectedPlayer.position,
            rankLabel: `Master Rank #${selectedPlayer.rank}`,
            projectedPoints: selectedPlayer.weekly_projected_fantasy_points,
            playerClass: selectedPlayer.playerClass,
            status: selectedPlayer.status,
            projection: selectedPlayer.projection,
            sheetProjectionStats: selectedPlayer.sheetProjectionStats,
          }}
          title="Available Player"
          note="Week projection uses the app's current projection formula for the selected week. Schedule-strength adjustments should come from the league schedule data when available."
        />
      ) : null}
    </main>
  );
}
