import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Search, Sparkles, TrendingUp, UserPlus, Zap } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { useLeagueWaiverTab } from "@/hooks/use-leagues";
import {
  useCreateWatchlist,
  useToggleWatchlistPlayer,
  useWatchlists,
} from "@/hooks/use-watchlists";
import { DEMO_LEAGUE_ID, createDemoLeagueWaiverResponse } from "@/lib/leaguePreviewData";

const positions = ["ALL", "QB", "RB", "WR", "TE", "K"] as const;

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
  const waiverQuery = useLeagueWaiverTab(parsedLeagueId, 50, 0, !isDemoLeague);
  const waiverData = isDemoLeague ? createDemoLeagueWaiverResponse() : waiverQuery.data;
  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    !isDemoLeague && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const createWatchlist = useCreateWatchlist();
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const players = waiverData?.available_players ?? [];
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
      })
      .sort(
        (first, second) =>
          Number(second.weekly_projected_fantasy_points ?? 0) -
          Number(first.weekly_projected_fantasy_points ?? 0)
      );
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
        description: "Open the Watchlist tab to review saved waiver targets.",
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
          League Waivers
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Waiver Wire</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              League-scoped available players only. Drafted players are on rosters; ownership in other leagues does not remove a player here.
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
              <p className="mt-1 text-2xl font-black text-violet-100">{waiverData?.claims?.length ?? 0}</p>
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
                Only players not selected in this league draft appear here. Watch targets or add them from this league only.
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
        {filteredPlayers.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-400">
            No league-scoped available players match the current filters.
          </p>
        ) : (
          <div className="divide-y divide-sky-300/10">
            {filteredPlayers.map((player, index) => {
              const tone = positionTone(player.position);
              const projected = Number(player.weekly_projected_fantasy_points ?? 0);
              const share = topProjection > 0 ? Math.min(100, Math.max(8, (projected / topProjection) * 100)) : 0;
              return (
                <div
                  key={player.id}
                  className="group relative grid gap-4 px-5 py-4 text-sm text-slate-200 transition-all duration-200 hover:-translate-y-0.5 hover:bg-sky-300/[0.045] hover:shadow-[0_18px_50px_rgba(14,165,233,0.10)] xl:grid-cols-[64px_minmax(260px,1.25fr)_minmax(140px,0.55fr)_minmax(250px,0.75fr)_minmax(230px,auto)]"
                >
                  <div className="flex items-center">
                    <span className="text-2xl font-black italic text-slate-600 transition-colors group-hover:text-sky-200">
                      {index + 1}
                    </span>
                  </div>
                  <div className="flex min-w-0 items-center gap-4">
                    <div className={`relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border ${tone.border} ${tone.bg} ${tone.glow}`}>
                      <span className={`absolute -right-1 -top-1 h-3 w-3 rounded-full ${tone.dot} shadow-[0_0_18px_currentColor]`} />
                      <span className={`text-[11px] font-black uppercase tracking-[0.12em] ${tone.text}`}>
                        {player.position ?? "-"}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-base font-black text-slate-50 transition-colors group-hover:text-sky-50">
                        {player.name}
                      </p>
                      <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                        Claim candidate
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center text-sm font-bold text-slate-400">
                    {player.school ?? "-"}
                  </div>
                  <div className="flex min-w-[220px] items-center">
                    <div className="w-full">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <span className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">
                          <TrendingUp className="h-3 w-3 text-sky-300" />
                          Week Proj
                        </span>
                        <span className="text-lg font-black text-sky-100">{projected.toFixed(1)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-950/80 ring-1 ring-sky-300/10">
                        <div
                          className="h-full rounded-full bg-[linear-gradient(90deg,rgba(125,211,252,0.95),rgba(186,230,253,0.9))] shadow-[0_0_18px_rgba(56,189,248,0.30)]"
                          style={{ width: `${share}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex min-w-[220px] items-center justify-end gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void handleWatchPlayer(player.id)}
                      disabled={createWatchlist.isPending || toggleWatchlistPlayer.isPending}
                      className="h-11 rounded-2xl border-sky-300/20 bg-sky-300/[0.06] px-4 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100 transition-all hover:border-sky-200/45 hover:bg-sky-300/15 hover:shadow-[0_0_26px_rgba(56,189,248,0.16)]"
                    >
                      <Sparkles className="mr-2 h-3.5 w-3.5" />
                      {watchedPlayerIds.has(player.id) ? "Watching" : "Watch"}
                    </Button>
                    <Button
                      type="button"
                      className="h-11 rounded-2xl bg-sky-300 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-slate-950 shadow-[0_10px_28px_rgba(14,165,233,0.18)] transition-all hover:bg-sky-200"
                    >
                      <UserPlus className="mr-2 h-3.5 w-3.5" />
                      Add
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

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
    </main>
  );
}
