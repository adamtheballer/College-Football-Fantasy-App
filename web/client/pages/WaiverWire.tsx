import React, { useState, useMemo } from "react";
import { Search, ChevronUp, MoreVertical, Plus, User, Activity, TrendingUp, Filter, ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { Player } from "@/types/player";
import { getSchedulePreview } from "@/lib/strengthOfSchedule";
import { matchupGradeColor } from "@/lib/matchupGrades";

const posStyles: Record<string, { bg: string, border: string, text: string, shadow: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400", shadow: "shadow-[0_0_15px_rgba(59,130,246,0.3)]" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400", shadow: "shadow-[0_0_15px_rgba(16,185,129,0.3)]" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400", shadow: "shadow-[0_0_15px_rgba(168,85,247,0.3)]" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400", shadow: "shadow-[0_0_15px_rgba(249,115,22,0.3)]" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400", shadow: "shadow-[0_0_15px_rgba(6,182,212,0.3)]" },
  DL: { bg: "bg-red-500/20", border: "border-red-500/30", text: "text-red-400", shadow: "shadow-[0_0_15px_rgba(239,68,68,0.3)]" },
  DB: { bg: "bg-pink-500/20", border: "border-pink-500/30", text: "text-pink-400", shadow: "shadow-[0_0_15px_rgba(236,72,153,0.3)]" },
};

const weeklyProjection = (fpts: number) => {
  const base = fpts > 80 ? fpts / 12 : fpts;
  return Math.min(35, Math.max(0, base));
};

const playersMock: (Player & { initials: string, change: string, game: string, isAdded: boolean })[] = [
  {
    id: 1,
    initials: "D.B",
    name: "D. Bowers",
    pos: "RB",
    school: "WISCONSIN",
    conf: "Big Ten",
    rank: 15,
    adp: 18.5,
    posRank: 4,
    rostered: 25,
    status: "HEALTHY",
    projection: { fpts: 10.6, rushingYards: 850, rushingTds: 8, expectedPlays: 16.2, expectedRushPerPlay: 0.14, expectedTdPerPlay: 0.04, boomProb: 0.18, bustProb: 0.20, floor: 6.1, ceiling: 16.4 },
    history: [{ year: 2025, stats: { fpts: 145, rushingYards: 1100, rushingTds: 12 } }],
    analysis: "A bruising back who thrives in short-yardage situations. Reliable goal-line option.",
    change: "+3.0",
    game: "BYE",
    isAdded: true
  },
  {
    id: 2,
    initials: "J.B",
    name: "J. Bowers",
    pos: "QB",
    school: "WASHINGTON",
    conf: "Big Ten",
    rank: 22,
    adp: 25.4,
    posRank: 8,
    rostered: 40,
    status: "HEALTHY",
    projection: { fpts: 5.3, passingYards: 2400, passingTds: 15, ints: 10, expectedPlays: 40.1, expectedRushPerPlay: 0.06, expectedTdPerPlay: 0.05, boomProb: 0.12, bustProb: 0.26, floor: 3.0, ceiling: 9.4, qbr: 64.2 },
    history: [{ year: 2025, stats: { fpts: 210, passingYards: 3100, passingTds: 22, ints: 8 } }],
    analysis: "Showing promise in a new system. High-upside developmental talent.",
    change: "+4.0",
    game: "SAT 7:30 @ ALA (#18)",
    isAdded: true
  },
  {
    id: 3,
    initials: "M.D",
    name: "M. Daniels",
    pos: "TE",
    school: "PITT",
    conf: "ACC",
    rank: 35,
    adp: 42.1,
    posRank: 3,
    rostered: 34,
    status: "HEALTHY",
    projection: { fpts: 11.2, receptions: 55, receivingYards: 650, receivingTds: 5, expectedPlays: 9.6, expectedRushPerPlay: 0.00, expectedTdPerPlay: 0.05, boomProb: 0.20, bustProb: 0.15, floor: 7.2, ceiling: 17.8 },
    history: [{ year: 2025, stats: { fpts: 122, receptions: 48, receivingYards: 580, receivingTds: 4 } }],
    analysis: "Reliable safety valve for his QB. Excellent hands and route running for his size.",
    change: "+5.1",
    game: "SAT 7:30 VS UGA (#3)",
    isAdded: true
  },
  {
    id: 4,
    initials: "C.M",
    name: "C. Maye",
    pos: "RB",
    school: "KANSAS STATE",
    conf: "Big 12",
    rank: 8,
    adp: 12.8,
    posRank: 2,
    rostered: 35,
    status: "HEALTHY",
    projection: { fpts: 18.0, rushingYards: 1100, rushingTds: 10, expectedPlays: 22.4, expectedRushPerPlay: 0.19, expectedTdPerPlay: 0.05, boomProb: 0.26, bustProb: 0.12, floor: 12.6, ceiling: 26.8 },
    history: [{ year: 2025, stats: { fpts: 285, rushingYards: 1550, rushingTds: 18 } }],
    analysis: "Dynamic threat with game-breaking speed. One of the best pure runners in the country.",
    change: "+3.1",
    game: "SAT 7:30 @ TEX (#19)",
    isAdded: true
  },
  {
    id: 5,
    initials: "M.W",
    name: "M. Walker",
    pos: "WR",
    school: "UTAH",
    conf: "Big 12",
    rank: 45,
    adp: 55.2,
    posRank: 12,
    rostered: 58,
    status: "HEALTHY",
    projection: { fpts: 9.4, receptions: 60, receivingYards: 850, receivingTds: 6, expectedPlays: 10.4, expectedRushPerPlay: 0.00, expectedTdPerPlay: 0.05, boomProb: 0.17, bustProb: 0.18, floor: 6.0, ceiling: 14.5 },
    history: [{ year: 2025, stats: { fpts: 115, receptions: 52, receivingYards: 780, receivingTds: 4 } }],
    analysis: "Vertical threat who can stretch any defense. Improving his consistency each week.",
    change: "-4.3",
    game: "SAT 7:30 VS OSU (#12)",
    isAdded: false
  },
];

const PositionPill = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
  <button
    onClick={onClick}
    className={cn(
      "px-8 py-3 rounded-full text-[11px] font-black tracking-[0.2em] uppercase transition-all duration-500",
      active
        ? "bg-primary text-primary-foreground shadow-[0_0_25px_rgba(var(--primary),0.4)] scale-105 border-white/20 border"
        : "text-muted-foreground hover:text-foreground hover:bg-white/5 border border-white/5"
    )}
  >
    {label}
  </button>
);

const PlayerRow = ({
  player,
  onClick,
}: { player: any, onClick: () => void }) => {
  const style = posStyles[player.pos] || posStyles.DB;
  const schedule = getSchedulePreview(player.school || "TEAM", player.pos);
  return (
    <div
      onClick={onClick}
      className="grid grid-cols-[1fr_180px] items-center py-6 px-10 hover:bg-white/[0.03] border-b border-white/10 transition-all duration-300 group cursor-pointer relative"
    >
      <div className="flex items-center gap-6">
        <div className={cn(
          "w-14 h-14 rounded-2xl flex items-center justify-center text-[11px] font-black tracking-tighter relative transition-all duration-500 group-hover:scale-110 group-hover:shadow-2xl",
          player.isAdded
            ? "bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.2)]"
            : cn(style.bg, style.border, style.text, style.shadow)
        )}>
          {player.initials}
          <div className={cn(
            "absolute -bottom-1 -right-1 w-6 h-6 rounded-lg flex items-center justify-center border-2 border-[#050810] shadow-lg transition-transform duration-300",
            player.isAdded ? "bg-emerald-500 text-white" : "bg-white/10 text-white/50 group-hover:scale-110 group-hover:bg-primary group-hover:text-white"
          )}>
            {player.isAdded ? <Check className="w-3.5 h-3.5 stroke-[3]" /> : <Plus className="w-3.5 h-3.5 stroke-[2]" />}
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h4 className="text-[15px] font-black text-foreground italic uppercase tracking-tight group-hover:text-primary transition-colors drop-shadow-sm">{player.name}</h4>
            <span className={cn("px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest", style.bg, style.border, style.text)}>{player.pos}</span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-widest">
            <span className="text-muted-foreground/80">{player.school}</span>
            <span className="text-muted-foreground/40">•</span>
            <span className="text-primary italic underline decoration-primary/20 underline-offset-4 cursor-pointer hover:decoration-primary transition-all">{player.rostered}% Rost</span>
            <span className={cn("flex items-center gap-1", player.change.startsWith('+') ? "text-emerald-400" : "text-red-400")}>
               {player.change}
               <Activity className="w-3 h-3" />
            </span>
            <span className="text-muted-foreground/40">•</span>
            <span className={cn(player.game === "BYE" ? "text-red-400" : "text-muted-foreground/60 font-medium")}>{player.game}</span>
          </div>
          <div className="flex items-center gap-2 pt-2">
            {schedule.map((game) => (
              <span key={`${player.id}-${game.opponent}`} className={cn("text-[9px] font-black uppercase tracking-widest", matchupGradeColor(game.grade as any))}>
                {game.grade}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        <span className="text-[11px] font-black text-foreground uppercase tracking-widest">
          Proj {weeklyProjection(player.projection.fpts).toFixed(1)}
        </span>
      </div>
    </div>
  );
};

export default function WaiverWire() {
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("projected-desc");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  const filteredPlayers = useMemo(() => {
    let result = playersMock.filter(p => {
      const matchesFilter = activeFilter === "ALL" || p.pos === activeFilter;
      const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           p.school.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesFilter && matchesSearch;
    });

    if (sortBy === "projected-desc") {
      result.sort((a, b) => (b.projection.fpts ?? 0) - (a.projection.fpts ?? 0));
    } else if (sortBy === "trending-asc") {
      result.sort((a, b) => parseFloat(b.change) - parseFloat(a.change));
    } else if (sortBy === "trending-desc") {
      result.sort((a, b) => parseFloat(a.change) - parseFloat(b.change));
    } else if (sortBy === "rostered-desc") {
      result.sort((a, b) => b.rostered - a.rostered);
    } else if (sortBy === "rostered-asc") {
      result.sort((a, b) => a.rostered - b.rostered);
    } else {
      result.sort((a, b) => (b.projection.fpts ?? 0) - (a.projection.fpts ?? 0));
    }

    return result;
  }, [activeFilter, searchQuery, sortBy]);

  return (
    <div className="min-h-screen relative overflow-hidden flex flex-col items-center py-12 px-8">
      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />
      <div className="max-w-6xl w-full space-y-12 relative z-10">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-primary/10 border border-primary/20">
                <TrendingUp className="w-5 h-5 text-primary" />
              </div>
              <span className="text-[10px] font-black tracking-[0.4em] text-primary uppercase drop-shadow-[0_0_10px_rgba(var(--primary),0.5)]">Live Market</span>
            </div>
            <h1 className="text-7xl font-black italic tracking-tighter text-foreground uppercase bg-gradient-to-b from-white via-white to-white/20 bg-clip-text text-transparent">
              Waiver Wire
            </h1>
            <p className="text-muted-foreground text-sm font-medium uppercase tracking-[0.2em] opacity-60">
              Browse available agents
            </p>
          </div>

          <div className="relative w-full md:w-[400px] group">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
            <Input 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by player or school..." 
              className="pl-14 bg-white/5 border-white/5 rounded-[2rem] h-16 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-widest uppercase shadow-2xl backdrop-blur-md"
            />
          </div>
        </div>

        {/* Filters Section */}
        <div className="flex items-center gap-4 bg-white/[0.02] backdrop-blur-xl border border-white/5 p-3 rounded-full w-fit">
          {["ALL", "QB", "RB", "WR", "TE", "K"].map((pos) => (
            <PositionPill 
              key={pos} 
              label={pos} 
              active={activeFilter === pos} 
              onClick={() => setActiveFilter(pos)} 
            />
          ))}
        </div>

        {/* Table Container */}
        <Card className="bg-card/30 backdrop-blur-[40px] border border-white/5 rounded-[3.5rem] overflow-hidden shadow-[0_40px_100px_rgba(0,0,0,0.5)] relative group transition-all duration-700 hover:border-primary/20">
          <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 blur-[120px] rounded-full -mr-64 -mt-64 group-hover:bg-primary/10 transition-colors pointer-events-none" />
          
          <div className="bg-gradient-to-r from-white/5 via-white/[0.02] to-transparent px-10 py-8 border-b border-white/5 flex items-center justify-between relative z-10">
            <div className="flex items-center gap-4">
               <Filter className="w-5 h-5 text-primary" />
               <h3 className="text-[11px] font-black tracking-[0.5em] text-primary uppercase italic">Available Talent</h3>
               <span className="px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-[9px] font-black text-emerald-400 uppercase tracking-widest ml-4">
                  {filteredPlayers.length} Players Found
               </span>
            </div>
            <div className="flex items-center gap-4">
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-[180px] bg-white/5 border-white/10 text-[10px] font-black uppercase tracking-widest h-12 rounded-xl focus:ring-primary/20">
                  <SelectValue placeholder="Sort By" />
                </SelectTrigger>
                <SelectContent className="bg-[#0A0C10] border-white/10">
                  <SelectItem value="projected-desc" className="text-[10px] font-black uppercase tracking-widest focus:bg-primary focus:text-white">Highest Projection</SelectItem>
                  <SelectItem value="trending-asc" className="text-[10px] font-black uppercase tracking-widest focus:bg-primary focus:text-white">Most Trending</SelectItem>
                  <SelectItem value="trending-desc" className="text-[10px] font-black uppercase tracking-widest focus:bg-primary focus:text-white">Least Trending</SelectItem>
                  <SelectItem value="rostered-desc" className="text-[10px] font-black uppercase tracking-widest focus:bg-primary focus:text-white">Most Rostered</SelectItem>
                  <SelectItem value="rostered-asc" className="text-[10px] font-black uppercase tracking-widest focus:bg-primary focus:text-white">Least Rostered</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="relative z-10 flex flex-col h-[650px]">
            {/* Table Header */}
            <div className="grid grid-cols-1 px-10 py-6 bg-white/5 border-b border-white/5">
              <span className="text-[11px] font-black tracking-[0.4em] text-muted-foreground/40 uppercase italic">Player / Position / Info</span>
            </div>
            
            {/* Scrollable Area */}
            <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth">
              <div className="divide-y divide-white/10">
                {filteredPlayers.length > 0 ? (
                  filteredPlayers.map((player) => (
                    <PlayerRow key={player.id} player={player} onClick={() => openPlayerDetails(player)} />
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center py-32 space-y-6 opacity-20">
                    <User className="w-16 h-16" />
                    <p className="text-xl font-black italic uppercase tracking-tighter">No players found</p>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Fade Effect */}
            <div className="absolute bottom-0 left-0 w-full h-32 bg-gradient-to-t from-black/40 to-transparent pointer-events-none" />
          </div>
        </Card>
      </div>
    </div>
  );
}
