import { useEffect, useMemo, useState } from "react";
import { Bookmark, ChevronLeft, Plus, Search, X } from "lucide-react";

import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { usePlayers } from "@/hooks/use-players";
import {
  useCreateWatchlist,
  useToggleWatchlistPlayer,
  useWatchlists,
} from "@/hooks/use-watchlists";
import { cn } from "@/lib/utils";
import type { Player } from "@/types/player";

const posStyles: Record<string, { bg: string; border: string; text: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400" },
};

export default function Watchlist() {
  const [view, setView] = useState<"browse" | "watchlists">("browse");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);
  const [showNamingModal, setShowNamingModal] = useState(false);
  const [newWatchlistName, setNewWatchlistName] = useState("");
  const [pendingPlayerId, setPendingPlayerId] = useState<number | null>(null);
  const [activeListId, setActiveListId] = useState<number | null>(null);

  const { data: watchlistsPayload, isLoading: watchlistsLoading } = useWatchlists();
  const createWatchlist = useCreateWatchlist();
  const toggleWatchlistPlayer = useToggleWatchlistPlayer();
  const { data, isLoading, isError } = usePlayers({
    search: searchQuery || undefined,
    limit: 100,
  });

  const watchlists = watchlistsPayload?.data ?? [];
  const players = data?.data ?? [];

  useEffect(() => {
    if (!watchlists.length) {
      setActiveListId(null);
      return;
    }
    setActiveListId((current) => {
      if (current && watchlists.some((watchlist) => watchlist.id === current)) {
        return current;
      }
      return watchlists[0].id;
    });
  }, [watchlists]);

  const activeWatchlist = watchlists.find((list) => list.id === activeListId) ?? null;
  const favoritePlayers = activeWatchlist?.players ?? [];
  const favoriteIds = new Set(favoritePlayers.map((player) => player.id));

  const createAndMaybeSavePlayer = async () => {
    const trimmedName = newWatchlistName.trim();
    if (!trimmedName) return;
    try {
      const created = await createWatchlist.mutateAsync({ name: trimmedName });
      setActiveListId(created.id);
      setView("watchlists");
      if (pendingPlayerId) {
        await toggleWatchlistPlayer.mutateAsync({
          watchlistId: created.id,
          playerId: pendingPlayerId,
          isSaved: false,
        });
      }
      setShowNamingModal(false);
      setNewWatchlistName("");
      setPendingPlayerId(null);
      toast({
        title: "Watchlist saved",
        description: "Your watchlist now persists on the backend.",
      });
    } catch (error) {
      toast({
        title: "Unable to save watchlist",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const togglePlayer = async (playerId: number) => {
    if (!activeWatchlist) {
      setPendingPlayerId(playerId);
      setShowNamingModal(true);
      return;
    }
    try {
      await toggleWatchlistPlayer.mutateAsync({
        watchlistId: activeWatchlist.id,
        playerId,
        isSaved: favoriteIds.has(playerId),
      });
    } catch (error) {
      toast({
        title: "Unable to update watchlist",
        description: error instanceof Error ? error.message : "Try again.",
        variant: "destructive",
      });
    }
  };

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  const emptyWatchlistMessage = useMemo(() => {
    if (watchlistsLoading) return "Loading watchlists...";
    if (watchlists.length === 0) return "Create your first watchlist.";
    return "Add players from browse mode to build this list.";
  }, [watchlists.length, watchlistsLoading]);

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
                Persist this list to your account
              </p>
            </div>
            <div className="mt-8 space-y-4">
              <Input
                value={newWatchlistName}
                onChange={(event) => setNewWatchlistName(event.target.value)}
                placeholder="e.g. Late-Round Targets"
                className="h-14 rounded-2xl border-white/10 bg-white/5"
                autoFocus
                onKeyDown={(event) => event.key === "Enter" && createAndMaybeSavePlayer()}
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
                  onClick={createAndMaybeSavePlayer}
                  disabled={!newWatchlistName.trim() || createWatchlist.isPending}
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
              : "Persisted watchlists for your signed-in account"}
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

      <Card className="rounded-[2rem] border border-emerald-500/20 bg-emerald-500/10">
        <CardContent className="p-6">
          <p className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-300">
            Persistence Online
          </p>
          <p className="mt-2 text-sm leading-7 text-emerald-50/90">
            Watchlists now load from backend storage, survive refresh and re-login, and share the same player index as the rest of the app.
          </p>
        </CardContent>
      </Card>

      {view === "watchlists" ? (
        <div className="space-y-8">
          <div className="flex flex-wrap gap-3">
            {watchlists.map((list) => (
              <Button
                key={list.id}
                type="button"
                variant={activeListId === list.id ? "default" : "outline"}
                onClick={() => setActiveListId(list.id)}
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
                {emptyWatchlistMessage}
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
                      <div className="flex items-start gap-4">
                        <Avatar className="h-14 w-14 rounded-2xl border border-white/10 bg-white/5">
                          <AvatarImage src={player.imageUrl} alt={player.name} className="object-cover" />
                          <AvatarFallback className="rounded-2xl bg-white/5 text-[11px] font-black uppercase tracking-[0.2em] text-primary">
                            {player.name
                              .split(" ")
                              .slice(0, 2)
                              .map((part) => part[0])
                              .join("")}
                          </AvatarFallback>
                        </Avatar>
                        <div className="space-y-2">
                          <h3 className="text-xl font-black italic uppercase text-foreground">
                            {player.name}
                          </h3>
                          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                            {player.school}
                          </p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation();
                          void togglePlayer(player.id);
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

            <div className="max-h-[640px] overflow-y-auto">
              {isLoading ? (
                <div className="px-8 py-20 text-center text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                  Loading players...
                </div>
              ) : isError ? (
                <div className="px-8 py-20 text-center text-[10px] font-black uppercase tracking-[0.3em] text-red-300">
                  Unable to load backend player records.
                </div>
              ) : (
                players.map((player) => {
                  const style = posStyles[player.pos] || {
                    bg: "bg-white/10",
                    border: "border-white/10",
                    text: "text-foreground",
                  };
                  const isSaved = favoriteIds.has(player.id);

                  return (
                    <div
                      key={player.id}
                      className="grid grid-cols-[minmax(0,1fr)_160px] items-center gap-4 border-b border-white/10 px-8 py-5 last:border-b-0"
                    >
                      <button
                        type="button"
                        onClick={() => openPlayerDetails(player)}
                        className="flex min-w-0 items-center gap-4 text-left"
                      >
                        <Avatar className="h-14 w-14 rounded-2xl border border-white/10 bg-white/5">
                          <AvatarImage src={player.imageUrl} alt={player.name} className="object-cover" />
                          <AvatarFallback className="rounded-2xl bg-white/5 text-[11px] font-black uppercase tracking-[0.2em] text-primary">
                            {player.name
                              .split(" ")
                              .slice(0, 2)
                              .map((part) => part[0])
                              .join("")}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 space-y-2">
                          <h4 className="truncate text-[15px] font-black italic uppercase tracking-tight text-foreground">
                            {player.name}
                          </h4>
                          <div className="flex flex-wrap items-center gap-3 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                            <span>{player.school}</span>
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
                        </div>
                      </button>

                      <div className="flex justify-end">
                        <Button
                          type="button"
                          variant={isSaved ? "default" : "outline"}
                          onClick={() => void togglePlayer(player.id)}
                          disabled={toggleWatchlistPlayer.isPending}
                          className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
                        >
                          {isSaved ? "Saved" : "Save"}
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
