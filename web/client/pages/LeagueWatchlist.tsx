import { useMemo } from "react";
import { Navigate, useParams } from "react-router-dom";
import { Bookmark, Search, X } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { useToggleWatchlistPlayer, useWatchlists } from "@/hooks/use-watchlists";
import { ApiError } from "@/lib/api";
import { DEMO_LEAGUE_ID } from "@/lib/leaguePreviewData";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { Player } from "@/types/player";

const positionTone = (position?: string | null) => {
  switch ((position ?? "").toUpperCase()) {
    case "QB":
      return "border-blue-300/45 bg-blue-400/10 text-blue-100 shadow-[0_0_22px_rgba(96,165,250,0.16)]";
    case "RB":
      return "border-emerald-300/45 bg-emerald-400/10 text-emerald-100 shadow-[0_0_22px_rgba(52,211,153,0.16)]";
    case "WR":
      return "border-violet-300/45 bg-violet-400/10 text-violet-100 shadow-[0_0_22px_rgba(167,139,250,0.16)]";
    case "TE":
      return "border-amber-300/45 bg-amber-400/10 text-amber-100 shadow-[0_0_22px_rgba(251,191,36,0.14)]";
    case "K":
      return "border-sky-300/45 bg-sky-400/10 text-sky-100 shadow-[0_0_22px_rgba(56,189,248,0.16)]";
    default:
      return "border-slate-300/25 bg-white/5 text-slate-100";
  }
};

export default function LeagueWatchlist() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const leagueQuery = useLeagueDetail(parsedLeagueId, !isDemoLeague);
  const postDraft = isDemoLeague || isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });
  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    !isDemoLeague && postDraft && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
  );
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const watchlists = watchlistsQuery.data?.data ?? [];
  const watchlistErrorMessage =
    watchlistsQuery.error instanceof ApiError
      ? watchlistsQuery.error.message
      : watchlistsQuery.error instanceof Error
        ? watchlistsQuery.error.message
        : "Unable to load your saved watchlist.";

  const watchedPlayers = useMemo(() => {
    const playerById = new Map<number, { player: Player; watchlistId: number }>();
    for (const list of watchlists) {
      for (const player of list.players) {
        if (!playerById.has(player.id)) {
          playerById.set(player.id, { player, watchlistId: list.id });
        }
      }
    }
    return Array.from(playerById.values()).sort((first, second) =>
      first.player.name.localeCompare(second.player.name)
    );
  }, [watchlists]);

  if (!isDemoLeague && leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (!postDraft) {
    return <Navigate to={`/league/${parsedLeagueId}/lobby`} replace />;
  }

  return (
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] rounded-[3rem] bg-[radial-gradient(circle_at_20%_8%,rgba(56,189,248,0.16),transparent_32%),radial-gradient(circle_at_72%_0%,rgba(59,130,246,0.13),transparent_38%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Watchlist
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">Watchlist</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Your saved league-specific available-player targets. Players stay available only if they are not rostered in this league.
            </p>
          </div>
          <div className="rounded-[1.25rem] border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_0_34px_rgba(56,189,248,0.12)]">
            <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Watched</p>
            <p className="mt-1 text-2xl font-black text-sky-100">{watchedPlayers.length}</p>
          </div>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

      <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(8,15,29,0.97),rgba(12,25,45,0.94))] shadow-[0_24px_80px_rgba(14,165,233,0.10)]">
        <div className="border-b border-sky-300/10 px-5 py-5">
          <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-300">
            Saved Targets
          </h2>
          <p className="mt-2 text-xs font-semibold text-slate-500">
            Add players from league player cards or supported waiver actions.
          </p>
        </div>

        {isDemoLeague ? (
          <div className="px-5 py-12 text-center">
            <Bookmark className="mx-auto h-10 w-10 text-sky-300/70" />
            <p className="mt-4 text-sm font-bold text-slate-300">Watchlists are saved to your account in real leagues.</p>
          </div>
        ) : watchlistsQuery.isLoading ? (
          <div className="px-5 py-12 text-center text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
            Loading watchlist...
          </div>
        ) : watchlistsQuery.isError ? (
          <div className="px-5 py-12">
            <ErrorState
              title="Unable to load watchlist"
              message={watchlistErrorMessage}
              retryLabel="Retry Watchlist"
              onRetry={() => void watchlistsQuery.refetch()}
            />
          </div>
        ) : watchedPlayers.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Search className="mx-auto h-10 w-10 text-sky-300/70" />
            <p className="mt-4 text-sm font-bold text-slate-300">No watched players yet.</p>
            <p className="mt-2 text-xs font-semibold text-slate-500">Open a player card and press Watch to save a target here.</p>
          </div>
        ) : (
          <div className="divide-y divide-sky-300/10">
            {watchedPlayers.map(({ player, watchlistId }) => {
              const position = player.pos ?? "-";
              return (
                <div
                  key={player.id}
                  className="grid gap-4 px-5 py-4 text-sm text-slate-200 transition-all duration-200 hover:bg-sky-300/[0.045] md:grid-cols-[minmax(0,1fr)_180px_130px_80px]"
                >
                  <div className="min-w-0">
                    <p className="truncate text-base font-black text-slate-50">{player.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      Watchlist target
                    </p>
                  </div>
                  <div className="flex items-center text-sm font-bold text-slate-400">{player.school ?? "-"}</div>
                  <div className="flex items-center">
                    <span className={`rounded-2xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] ${positionTone(position)}`}>
                      {position}
                    </span>
                  </div>
                  <div className="flex items-center justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      aria-label={`Remove ${player.name} from watchlist`}
                      onClick={() =>
                        void toggleWatchlistPlayer.mutateAsync({
                          watchlistId,
                          playerId: player.id,
                          isSaved: true,
                        })
                      }
                      className="h-10 w-10 rounded-xl border-white/10 bg-white/[0.04] p-0 text-slate-300 hover:border-red-300/35 hover:bg-red-400/10 hover:text-red-100"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
