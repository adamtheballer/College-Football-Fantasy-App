import { useMemo } from "react";
import { Navigate, useParams } from "react-router-dom";
import { Bookmark, Search, X } from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { useToggleWatchlistPlayer, useWatchlists } from "@/hooks/use-watchlists";
import { ApiError } from "@/lib/api";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import type { Player } from "@/types/player";

const positionTone = (position?: string | null) => {
  switch ((position ?? "").toUpperCase()) {
    case "QB":
      return "border-blue-300/45 bg-blue-400/10 text-blue-100";
    case "RB":
      return "border-emerald-300/45 bg-emerald-400/10 text-emerald-100";
    case "WR":
      return "border-violet-300/45 bg-violet-400/10 text-violet-100";
    case "TE":
      return "border-amber-300/45 bg-amber-400/10 text-amber-100";
    case "K":
      return "border-sky-300/45 bg-sky-400/10 text-sky-100";
    default:
      return "border-slate-300/25 bg-white/5 text-slate-100";
  }
};

export default function LeagueWatchlist() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const postDraft = isLeaguePostDraft({
    draftStatus: leagueQuery.data?.draft?.status,
    leagueStatus: leagueQuery.data?.status,
  });
  const watchlistsQuery = useWatchlists(
    parsedLeagueId,
    postDraft && typeof parsedLeagueId === "number" && !Number.isNaN(parsedLeagueId)
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
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cfb-brand">
          League Watchlist
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="cfb-display-title text-3xl text-cfb-text-primary sm:text-4xl">Watchlist</h1>
            <p className="mt-1.5 max-w-2xl text-sm text-cfb-text-secondary">
              Your saved league-specific available-player targets. Players stay available only if they are not rostered in this league.
            </p>
          </div>
          <div className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised px-4 py-3">
            <p className="text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">Watched</p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-cfb-text-primary">{watchedPlayers.length}</p>
          </div>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

      <section data-testid="league-watchlist-board" className="overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface">
        <div className="border-b border-cfb-border-subtle px-4 py-4 sm:px-5">
          <h2 className="text-[11px] font-black uppercase tracking-[0.18em] text-cfb-brand">
            Saved Targets
          </h2>
          <p className="mt-1.5 text-xs font-semibold text-cfb-text-secondary">
            Add players from league player cards or supported waiver actions.
          </p>
        </div>

        {watchlistsQuery.isLoading ? (
          <div className="px-5 py-10 text-center text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">
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
            <Search className="mx-auto h-8 w-8 text-cfb-text-muted" />
            <p className="mt-3 text-sm font-semibold text-cfb-text-primary">No watched players yet.</p>
            <p className="mt-1.5 text-xs font-medium text-cfb-text-muted">Open a player card and press Watch to save a target here.</p>
          </div>
        ) : (
          <div className="divide-y divide-cfb-border-subtle">
            {watchedPlayers.map(({ player, watchlistId }) => {
              const position = player.pos ?? "-";
              return (
                <div
                  key={player.id}
                  className="grid gap-3 px-4 py-3 text-sm text-cfb-text-secondary transition-colors hover:bg-cfb-surface-hover sm:px-5 md:grid-cols-[minmax(0,1fr)_180px_130px_80px]"
                >
                  <div className="min-w-0">
                    <p className="truncate text-base font-bold text-cfb-text-primary">{player.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">
                      Watchlist target
                    </p>
                  </div>
                  <div className="flex items-center text-sm font-medium text-cfb-text-secondary">{player.school ?? "-"}</div>
                  <div className="flex items-center">
                    <span className={`rounded-md border px-2 py-1 text-[10px] font-black uppercase tracking-[0.1em] ${positionTone(position)}`}>
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
                      className="h-9 w-9 rounded-md border-cfb-border-subtle bg-cfb-surface-raised p-0 text-cfb-text-secondary hover:border-red-300/35 hover:bg-red-400/10 hover:text-red-100"
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
