import { useMemo, useState } from "react";
import { Activity, Filter, Search, TrendingUp, User } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { usePlayers } from "@/hooks/use-players";
import { cn } from "@/lib/utils";
import type { Player } from "@/types/player";

const posStyles: Record<string, { bg: string; border: string; text: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400" },
};

const PositionPill = ({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) => (
  <button
    type="button"
    onClick={onClick}
    className={cn(
      "px-6 py-3 rounded-full text-[11px] font-black tracking-[0.2em] uppercase transition-all duration-300 border",
      active
        ? "bg-primary text-primary-foreground border-primary shadow-[0_0_25px_rgba(var(--primary),0.35)]"
        : "bg-white/5 border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/10"
    )}
  >
    {label}
  </button>
);

const PlayerRow = ({
  player,
  onClick,
}: {
  player: Player;
  onClick: () => void;
}) => {
  const style = posStyles[player.pos] || {
    bg: "bg-white/10",
    border: "border-white/10",
    text: "text-foreground",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className="grid w-full grid-cols-[1fr_120px] items-center gap-4 border-b border-white/10 px-8 py-5 text-left transition-colors hover:bg-white/[0.03]"
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
        <div className="flex flex-wrap items-center gap-3 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
          <span>{player.school}</span>
          <span>Projection pending</span>
          <span>Availability pending</span>
        </div>
      </div>
      <div className="text-right">
        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
          View profile
        </span>
      </div>
    </button>
  );
};

export default function WaiverWire() {
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("name-asc");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);
  const { data, isLoading, isError } = usePlayers({
    search: searchQuery || undefined,
    position: activeFilter === "ALL" ? undefined : activeFilter,
    limit: 100,
  });

  const players = useMemo(() => {
    const rows = [...(data?.data ?? [])];
    if (sortBy === "name-desc") {
      rows.sort((left, right) => right.name.localeCompare(left.name));
    } else if (sortBy === "school-asc") {
      rows.sort((left, right) => left.school.localeCompare(right.school));
    } else if (sortBy === "school-desc") {
      rows.sort((left, right) => right.school.localeCompare(left.school));
    } else {
      rows.sort((left, right) => left.name.localeCompare(right.name));
    }
    return rows;
  }, [data?.data, sortBy]);

  const schoolsCount = useMemo(
    () => new Set(players.map((player) => player.school)).size,
    [players]
  );
  const positionsCount = useMemo(
    () => new Set(players.map((player) => player.pos)).size,
    [players]
  );

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  return (
    <div className="min-h-screen px-8 py-12">
      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />

      <div className="mx-auto max-w-6xl space-y-10">
        <div className="flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-xl border border-primary/20 bg-primary/10 p-2">
                <TrendingUp className="h-5 w-5 text-primary" />
              </div>
              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">
                Live Player Index
              </span>
            </div>
            <h1 className="text-7xl font-black italic uppercase tracking-tighter text-foreground">
              Waiver Wire
            </h1>
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground/60">
              Search backend player records instead of seeded mock waiver data.
            </p>
          </div>

          <div className="relative w-full md:w-[420px]">
            <Search className="absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by player or school..."
              className="h-16 rounded-[2rem] border-white/10 bg-white/5 pl-14 text-xs font-bold uppercase tracking-widest"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-full border border-white/5 bg-white/[0.02] p-3 backdrop-blur-xl">
          {["ALL", "QB", "RB", "WR", "TE", "K"].map((pos) => (
            <PositionPill
              key={pos}
              label={pos}
              active={activeFilter === pos}
              onClick={() => setActiveFilter(pos)}
            />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card className="rounded-[2rem] border border-white/10 bg-card/30 backdrop-blur-md">
            <CardHeader className="pb-3">
              <CardTitle className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">
                Indexed Players
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-black italic text-foreground">
                {data?.total ?? 0}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-[2rem] border border-white/10 bg-card/30 backdrop-blur-md">
            <CardHeader className="pb-3">
              <CardTitle className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">
                Schools In View
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-black italic text-foreground">
                {schoolsCount}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-[2rem] border border-white/10 bg-card/30 backdrop-blur-md">
            <CardHeader className="pb-3">
              <CardTitle className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">
                Positions In View
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-black italic text-foreground">
                {positionsCount}
              </p>
            </CardContent>
          </Card>
        </div>

        <Card className="overflow-hidden rounded-[3rem] border border-white/5 bg-card/30 backdrop-blur-[40px] shadow-[0_40px_100px_rgba(0,0,0,0.5)]">
          <div className="flex items-center justify-between border-b border-white/5 bg-gradient-to-r from-white/5 via-white/[0.02] to-transparent px-8 py-6">
            <div className="flex items-center gap-4">
              <Filter className="h-5 w-5 text-primary" />
              <h3 className="text-[11px] font-black uppercase tracking-[0.5em] text-primary italic">
                Available Talent
              </h3>
            </div>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="h-12 w-[180px] rounded-xl border-white/10 bg-white/5 text-[10px] font-black uppercase tracking-widest">
                <SelectValue placeholder="Sort By" />
              </SelectTrigger>
              <SelectContent className="border-white/10 bg-[#0A0C10]">
                <SelectItem value="name-asc">Name A-Z</SelectItem>
                <SelectItem value="name-desc">Name Z-A</SelectItem>
                <SelectItem value="school-asc">School A-Z</SelectItem>
                <SelectItem value="school-desc">School Z-A</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="max-h-[650px] overflow-y-auto">
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
              <div className="flex flex-col items-center justify-center gap-6 px-8 py-24 text-center opacity-70">
                <User className="h-16 w-16 text-muted-foreground/40" />
                <div className="space-y-2">
                  <p className="text-xl font-black italic uppercase tracking-tight text-foreground">
                    No players found
                  </p>
                  <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground/60">
                    Seed player records or widen your search to populate this view.
                  </p>
                </div>
              </div>
            ) : (
              <div>
                {players.map((player) => (
                  <PlayerRow
                    key={player.id}
                    player={player}
                    onClick={() => openPlayerDetails(player)}
                  />
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card className="rounded-[2rem] border border-amber-500/20 bg-amber-500/10">
          <CardContent className="flex items-start gap-4 p-6">
            <Activity className="mt-0.5 h-5 w-5 text-amber-300" />
            <div className="space-y-2">
              <p className="text-[10px] font-black uppercase tracking-[0.28em] text-amber-300">
                Contract Note
              </p>
              <p className="text-sm leading-7 text-amber-50/90">
                Projection, rostered percentage, and add-drop availability still need backend support.
                This screen now avoids fake market movement and uses the real player index instead.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
