import { Loader2, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { DraftBoardPlayer } from "@/types/draft-board";

const positionPillClass: Record<string, string> = {
  QB: "border-blue-300/40 bg-blue-500/15 text-blue-100 shadow-[0_0_16px_rgba(96,165,250,0.18)]",
  RB: "border-emerald-300/40 bg-emerald-500/15 text-emerald-100 shadow-[0_0_16px_rgba(74,222,128,0.18)]",
  WR: "border-violet-300/40 bg-violet-500/15 text-violet-100 shadow-[0_0_16px_rgba(196,181,253,0.18)]",
  TE: "border-amber-300/40 bg-amber-500/15 text-amber-100 shadow-[0_0_16px_rgba(251,191,36,0.18)]",
  K: "border-slate-300/40 bg-slate-400/15 text-slate-100 shadow-[0_0_16px_rgba(203,213,225,0.14)]",
};

const normalizePosition = (position: string | null | undefined) => (position || "").trim().toUpperCase();

export function AvailablePlayersTable({
  players,
  searchQuery,
  onSearchChange,
  onDraftPlayer,
  onQueuePlayer,
  onSelectPlayer,
  queuedPlayerIds,
  draftPending,
  autoPickPending,
  canDraft,
}: {
  players: DraftBoardPlayer[];
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onDraftPlayer: (playerId: number) => void;
  onQueuePlayer?: (playerId: number) => void;
  onSelectPlayer?: (player: DraftBoardPlayer) => void;
  queuedPlayerIds?: Set<number>;
  draftPending: boolean;
  autoPickPending: boolean;
  canDraft: boolean;
}) {
  const isSearching = searchQuery.trim().length > 0;
  return (
    <Card data-testid="available-players-table" className="rounded-[2rem] border-white/10 bg-card/45">
      <CardHeader className="border-b border-white/10">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Available Players</CardTitle>
          <div className="relative w-full md:max-w-md">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(event) => onSearchChange(event.target.value)}
              className="h-12 rounded-2xl border-cyan-200/15 bg-slate-950/35 pl-11 text-sm font-bold"
              placeholder="Search players, schools, positions..."
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="grid grid-cols-[72px_minmax(0,1fr)_96px_110px_180px] border-b border-white/10 px-5 py-3 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
          <span>RK</span><span>Player</span><span>Pos</span><span>Proj</span><span className="text-right">Action</span>
        </div>
        <div className="max-h-[690px] overflow-y-auto">
          {players.length === 0 ? (
            <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
              No available players match this search.
            </div>
          ) : (
            players.map((player) => {
              const position = normalizePosition(player.position);
              const positionClass = positionPillClass[position] ?? "border-white/20 bg-white/10 text-foreground";
              const isSelectable = Boolean(onSelectPlayer);
              const isQueued = queuedPlayerIds?.has(player.id) ?? false;
              const displayedRank = isSearching ? player.boardRank ?? player.rank : player.rank;
              return (
                <div
                  key={player.id}
                  data-testid="draft-player-row"
                  role={isSelectable ? "button" : undefined}
                  tabIndex={isSelectable ? 0 : undefined}
                  aria-label={isSelectable ? `Open ${player.name} player card` : undefined}
                  className={`grid grid-cols-[72px_minmax(0,1fr)_96px_110px_180px] items-center gap-3 border-b border-white/10 px-5 py-4 transition-colors hover:bg-white/[0.045] ${isSelectable ? "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60" : ""}`}
                  onClick={() => onSelectPlayer?.(player)}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectPlayer?.(player);
                    }
                  }}
                >
                  <p className="text-xl font-black tabular-nums text-muted-foreground">{displayedRank}</p>
                  <div className="min-w-0">
                    <p className="truncate text-base font-black text-foreground transition-colors hover:text-cyan-100">{player.name}</p>
                    <p className="mt-1 truncate text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">{player.school}</p>
                  </div>
                  <span className={`w-fit rounded-full border px-4 py-2 text-xs font-black ${positionClass}`}>{position || player.position}</span>
                  <p className="text-sm font-black tabular-nums text-foreground">{typeof player.projection === "number" ? player.projection.toFixed(1) : "--"}</p>
                  <div className="flex justify-end gap-2">
                    {onQueuePlayer ? (
                      <Button
                        variant="outline"
                        className="h-10 rounded-2xl px-4 text-[10px] font-black uppercase tracking-[0.14em]"
                        onClick={(event) => {
                          event.stopPropagation();
                          onQueuePlayer(player.id);
                        }}
                        disabled={isQueued}
                      >
                        {isQueued ? "Queued" : "Queue"}
                      </Button>
                    ) : null}
                    <Button
                      className="h-10 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 px-5 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950"
                      disabled={!canDraft || draftPending || autoPickPending || player.disabled}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDraftPlayer(player.id);
                      }}
                    >
                      {draftPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Draft"}
                    </Button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </CardContent>
    </Card>
  );
}
