import { useEffect, useMemo, useState } from "react";
import { Bookmark, ChevronLeft, Plus, Search, X } from "lucide-react";

import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { usePlayers } from "@/hooks/use-players";
import { cn } from "@/lib/utils";
import type { Player } from "@/types/player";

type WatchlistRecord = {
  id: string;
  name: string;
  playerIds: number[];
};

type WatchlistState = {
  lists: WatchlistRecord[];
  activeListId: string | null;
};

const EMPTY_STATE: WatchlistState = {
  lists: [],
  activeListId: null,
};

const storageKeyForUser = (userId: number) => `cfb-watchlists:${userId}`;

const posStyles: Record<string, { bg: string; border: string; text: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400" },
};

export default function Watchlist() {
  const { user } = useAuth();
  const [view, setView] = useState<"browse" | "watchlists">("browse");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);
  const [watchlists, setWatchlists] = useState<WatchlistState>(EMPTY_STATE);
  const [showNamingModal, setShowNamingModal] = useState(false);
  const [newWatchlistName, setNewWatchlistName] = useState("");
  const [pendingPlayerId, setPendingPlayerId] = useState<number | null>(null);
  const { data, isLoading, isError } = usePlayers({
    search: searchQuery || undefined,
    limit: 100,
  });

  useEffect(() => {
    if (!user) {
      setWatchlists(EMPTY_STATE);
      return;
    }

    try {
      const raw = localStorage.getItem(storageKeyForUser(user.id));
      if (!raw) {
        setWatchlists(EMPTY_STATE);
        return;
      }
      const parsed = JSON.parse(raw) as WatchlistState;
      setWatchlists({
        lists: parsed.lists ?? [],
        activeListId: parsed.activeListId ?? parsed.lists?.[0]?.id ?? null,
      });
    } catch {
      setWatchlists(EMPTY_STATE);
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    try {
      localStorage.setItem(storageKeyForUser(user.id), JSON.stringify(watchlists));
    } catch {
      // Ignore storage failures to keep browse mode functional.
    }
  }, [user, watchlists]);

  const players = data?.data ?? [];
  const activeWatchlist =
    watchlists.lists.find((list) => list.id === watchlists.activeListId) ?? null;
  const favoriteIds = activeWatchlist?.playerIds ?? [];
  const favoritePlayers = useMemo(
    () => players.filter((player) => favoriteIds.includes(player.id)),
    [favoriteIds, players]
  );

  const createWatchlist = () => {
    const trimmedName = newWatchlistName.trim();
    if (!trimmedName) return;
    const nextList: WatchlistRecord = {
      id: `watchlist-${Date.now()}`,
      name: trimmedName,
      playerIds: pendingPlayerId ? [pendingPlayerId] : [],
    };
    setWatchlists((prev) => ({
      lists: [...prev.lists, nextList],
      activeListId: nextList.id,
    }));
    setShowNamingModal(false);
    setNewWatchlistName("");
    setPendingPlayerId(null);
    setView("watchlists");
  };

  const ensureActiveWatchlist = (playerId: number) => {
    if (activeWatchlist) {
      setWatchlists((prev) => ({
        ...prev,
        lists: prev.lists.map((list) =>
          list.id !== activeWatchlist.id
            ? list
            : {
                ...list,
                playerIds: list.playerIds.includes(playerId)
                  ? list.playerIds.filter((id) => id !== playerId)
                  : [...list.playerIds, playerId],
              }
        ),
      }));
      return;
    }

    setPendingPlayerId(playerId);
    setShowNamingModal(true);
  };

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-12 pb-12 pt-8">
      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />

      {showNamingModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 p-6 backdrop-blur-md">
          <Card className="w-full max-w-md rounded-[2.5rem] border border-primary/20 bg-card/90 p-10 shadow-2xl">
            <div className="space-y-2">
              <h2 className="text-3xl font-black italic uppercase tracking-tighter text-foreground">
                Create Watchlist
              </h2>
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                Save this list on the current device
              </p>
            </div>
            <div className="mt-8 space-y-4">
              <Input
                value={newWatchlistName}
                onChange={(event) => setNewWatchlistName(event.target.value)}
                placeholder="e.g. Late-Round Targets"
                className="h-14 rounded-2xl border-white/10 bg-white/5"
                autoFocus
                onKeyDown={(event) => event.key === "Enter" && createWatchlist()}
              />
              <div className="flex gap-4">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowNamingModal(false);
                    setPendingPlayerId(null);
                  }}
                  className="h-12 flex-1 rounded-xl text-[10px] font-black uppercase tracking-widest"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={createWatchlist}
                  disabled={!newWatchlistName.trim()}
                  className="h-12 flex-1 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]"
                >
                  Create
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      <div className="flex items-center justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-6xl font-black italic uppercase tracking-tighter text-foreground">
            {view === "browse" ? "Browse Players" : activeWatchlist?.name || "Watchlists"}
          </h1>
          <p className="text-[10px] font-black uppercase tracking-[0.35em] text-muted-foreground/60">
            {view === "browse"
              ? "Search real backend player records"
              : "Saved locally for the signed-in browser session"}
          </p>
        </div>

        {view === "browse" ? (
          <Button
            type="button"
            onClick={() => setView("watchlists")}
            className="h-14 rounded-2xl border border-white/10 bg-white/5 px-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground hover:bg-primary/10 hover:text-primary"
          >
            <Bookmark className="mr-3 h-4 w-4" />
            My Watchlists
          </Button>
        ) : (
          <Button
            type="button"
            onClick={() => setShowNamingModal(true)}
            className="h-14 rounded-2xl px-8 text-[10px] font-black uppercase tracking-[0.2em]"
          >
            <Plus className="mr-3 h-4 w-4" />
            New Watchlist
          </Button>
        )}
      </div>

      <Card className="rounded-[2rem] border border-amber-500/20 bg-amber-500/10">
        <CardContent className="p-6">
          <p className="text-[10px] font-black uppercase tracking-[0.28em] text-amber-300">
            Cleanup Status
          </p>
          <p className="mt-2 text-sm leading-7 text-amber-50/90">
            The SEC depth-chart mock pool has been removed. Watchlist browsing now uses the backend player index.
            True cross-device watchlist persistence still needs dedicated backend endpoints.
          </p>
        </CardContent>
      </Card>

      {view === "watchlists" ? (
        <div className="space-y-8">
          <div className="flex flex-wrap gap-3">
            {watchlists.lists.map((list) => (
              <Button
                key={list.id}
                type="button"
                variant={watchlists.activeListId === list.id ? "default" : "outline"}
                onClick={() =>
                  setWatchlists((prev) => ({ ...prev, activeListId: list.id }))
                }
                className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              >
                {list.name}
              </Button>
            ))}
          </div>

          {favoritePlayers.length === 0 ? (
            <button
              type="button"
              onClick={() => setView("browse")}
              className="flex h-[40vh] w-full flex-col items-center justify-center rounded-[3rem] border border-dashed border-white/10 bg-card/20 p-12 text-center transition-colors hover:border-primary/20"
            >
              <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-muted-foreground">
                <Plus className="h-10 w-10" />
              </div>
              <span className="text-[11px] font-black uppercase tracking-[0.35em] text-muted-foreground">
                Add Players
              </span>
            </button>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {favoritePlayers.map((player) => {
                const style = posStyles[player.pos] || {
                  bg: "bg-white/10",
                  border: "border-white/10",
                  text: "text-foreground",
                };
                return (
                  <Card
                    key={player.id}
                    onClick={() => openPlayerDetails(player)}
                    className="cursor-pointer rounded-[2.5rem] border border-white/10 bg-card/40 p-8 transition-all duration-300 hover:border-primary/40"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-2">
                        <h3 className="text-xl font-black italic uppercase text-foreground">
                          {player.name}
                        </h3>
                        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                          {player.school}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation();
                          ensureActiveWatchlist(player.id);
                        }}
                        className="h-10 w-10 rounded-xl border border-white/10 bg-white/5 p-0 text-primary"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                    <div
                      className={cn(
                        "mt-6 inline-flex rounded-xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.2em]",
                        style.bg,
                        style.border,
                        style.text
                      )}
                    >
                      {player.pos}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}

          <div className="flex justify-center">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setView("browse")}
              className="h-12 rounded-xl px-8 text-[10px] font-black uppercase tracking-[0.3em]"
            >
              <ChevronLeft className="mr-3 h-4 w-4" />
              Back to Browsing Players
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          <div className="relative max-w-2xl">
            <Search className="absolute left-6 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by player name or school..."
              className="h-16 rounded-2xl border-white/10 bg-white/5 pl-16 text-sm font-medium"
            />
          </div>

          <Card className="overflow-hidden rounded-[3rem] border border-white/5 bg-card/40">
            <div className="border-b border-white/5 bg-gradient-to-r from-white/5 via-white/[0.02] to-transparent px-8 py-6">
              <h3 className="text-[11px] font-black uppercase tracking-[0.5em] text-primary italic">
                Player Pool
              </h3>
            </div>
            <div className="max-h-[620px] overflow-y-auto">
              {isLoading ? (
                <div className="px-8 py-20 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                    Loading players...
                  </p>
                </div>
              ) : isError ? (
                <div className="px-8 py-20 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.3em] text-red-300">
                    Unable to load backend player records.
                  </p>
                </div>
              ) : players.length === 0 ? (
                <div className="px-8 py-20 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                    No players found.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-white/10">
                  {players.map((player) => {
                    const style = posStyles[player.pos] || {
                      bg: "bg-white/10",
                      border: "border-white/10",
                      text: "text-foreground",
                    };
                    const isSaved = favoriteIds.includes(player.id);
                    return (
                      <div
                        key={player.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => openPlayerDetails(player)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            openPlayerDetails(player);
                          }
                        }}
                        className="grid w-full grid-cols-[1fr_120px] items-center gap-4 px-8 py-5 text-left transition-colors hover:bg-white/[0.03]"
                      >
                        <div className="space-y-2">
                          <div className="flex items-center gap-3">
                            <h4 className="text-[15px] font-black italic uppercase tracking-tight text-foreground">
                              {player.name}
                            </h4>
                            <span
                              className={cn(
                                "rounded-md border px-2 py-1 text-[9px] font-black uppercase tracking-widest",
                                style.bg,
                                style.border,
                                style.text
                              )}
                            >
                              {player.pos}
                            </span>
                          </div>
                          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                            {player.school}
                          </p>
                        </div>
                        <div className="flex justify-end">
                          <Button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              ensureActiveWatchlist(player.id);
                            }}
                            className={cn(
                              "h-10 rounded-xl px-4 text-[9px] font-black uppercase tracking-[0.2em]",
                              isSaved
                                ? "bg-primary text-primary-foreground"
                                : "border border-white/10 bg-white/5 text-muted-foreground hover:bg-primary/10 hover:text-primary"
                            )}
                          >
                            <Bookmark className={cn("mr-2 h-4 w-4", isSaved ? "fill-current" : "")} />
                            {isSaved ? "Saved" : "Save"}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
