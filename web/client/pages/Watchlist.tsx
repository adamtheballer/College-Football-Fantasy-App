import React, { useState, useMemo } from "react";
import { Bookmark, Plus, UserPlus, Search, Sparkles, Star, ChevronLeft, Heart, X, Check, TrendingUp, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Player } from "@/types/player";
import { secDepthCharts } from "@/data/sec_depth_charts";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { getMatchupGrade, matchupGradeColor } from "@/lib/matchupGrades";

const posStyles: Record<string, { bg: string, border: string, text: string, shadow: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400", shadow: "shadow-[0_0_15px_rgba(59,130,246,0.3)]" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400", shadow: "shadow-[0_0_15px_rgba(16,185,129,0.3)]" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400", shadow: "shadow-[0_0_15px_rgba(168,85,247,0.3)]" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400", shadow: "shadow-[0_0_15px_rgba(249,115,22,0.3)]" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400", shadow: "shadow-[0_0_15px_rgba(6,182,212,0.3)]" },
  DL: { bg: "bg-red-500/20", border: "border-red-500/30", text: "text-red-400", shadow: "shadow-[0_0_15px_rgba(239,68,68,0.3)]" },
  DB: { bg: "bg-pink-500/20", border: "border-pink-500/30", text: "text-pink-400", shadow: "shadow-[0_0_15px_rgba(236,72,153,0.3)]" },
  LB: { bg: "bg-amber-500/20", border: "border-amber-500/30", text: "text-amber-400", shadow: "shadow-[0_0_15px_rgba(245,158,11,0.3)]" },
  DE: { bg: "bg-rose-500/20", border: "border-rose-500/30", text: "text-rose-400", shadow: "shadow-[0_0_15px_rgba(244,63,94,0.3)]" },
  S: { bg: "bg-indigo-500/20", border: "border-indigo-500/30", text: "text-indigo-400", shadow: "shadow-[0_0_15px_rgba(99,102,241,0.3)]" },
  OL: { bg: "bg-slate-500/20", border: "border-slate-500/30", text: "text-slate-400", shadow: "shadow-[0_0_15px_rgba(100,116,139,0.3)]" },
  CB: { bg: "bg-violet-500/20", border: "border-violet-500/30", text: "text-violet-400", shadow: "shadow-[0_0_15px_rgba(139,92,246,0.3)]" },
};

const weeklyProjection = (fpts: number) => {
  const base = fpts > 80 ? fpts / 12 : fpts;
  return Math.min(35, Math.max(0, base));
};

const applyFirstYearStarterAdjustment = (
  projection: Player["projection"],
  pos: string,
  firstYearStarter?: boolean
) => {
  if (!firstYearStarter) {
    return projection;
  }
  const penalty = pos === "QB" ? 0.92 : 0.94;
  const scale = penalty;
  const adjust = (value?: number, factor = scale) => (value === undefined ? value : value * factor);
  const fpts = projection.fpts * penalty;
  return {
    ...projection,
    fpts,
    passingYards: adjust(projection.passingYards),
    passingTds: adjust(projection.passingTds),
    ints: projection.ints ? projection.ints * 1.08 : projection.ints,
    rushingYards: adjust(projection.rushingYards),
    rushingTds: adjust(projection.rushingTds),
    receptions: adjust(projection.receptions),
    receivingYards: adjust(projection.receivingYards),
    receivingTds: adjust(projection.receivingTds),
    expectedTdPerPlay: adjust(projection.expectedTdPerPlay),
    qbr: projection.qbr ? projection.qbr - 4 : projection.qbr,
    floor: fpts * 0.55,
    ceiling: fpts * 1.45,
    boomProb: Math.min(0.45, (projection.boomProb ?? 0.2) + 0.05),
    bustProb: Math.min(0.45, (projection.bustProb ?? 0.2) + 0.07),
  };
};

const buildProjection = (pos: string, depth: number, firstYearStarter?: boolean) => {
  const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));
  if (pos === "QB") {
    const fpts = clamp(24 - (depth - 1) * 6, 8, 30);
    const projection = {
      passingYards: fpts * 12,
      passingTds: fpts / 12,
      ints: 0.6,
      fpts,
      qbr: 70 + (depth === 1 ? 8 : 0),
      expectedPlays: 42 - (depth - 1) * 6,
      expectedRushPerPlay: 0.08,
      expectedTdPerPlay: 0.06,
      floor: fpts * 0.65,
      ceiling: fpts * 1.35,
      boomProb: 0.22,
      bustProb: 0.14,
    };
    return applyFirstYearStarterAdjustment(projection, pos, firstYearStarter);
  }
  if (pos === "RB") {
    const fpts = clamp(20 - (depth - 1) * 6, 6, 28);
    const projection = {
      rushingYards: fpts * 5.5,
      rushingTds: fpts / 16,
      receptions: 2.5,
      receivingYards: fpts * 1.8,
      receivingTds: fpts / 60,
      fpts,
      expectedPlays: 18 - (depth - 1) * 4,
      expectedRushPerPlay: 0.18,
      expectedTdPerPlay: 0.05,
      floor: fpts * 0.65,
      ceiling: fpts * 1.35,
      boomProb: 0.20,
      bustProb: 0.16,
    };
    return applyFirstYearStarterAdjustment(projection, pos, firstYearStarter);
  }
  if (pos === "WR" || pos === "TE") {
    const fpts = clamp(18 - (depth - 1) * 5, 5, 26);
    const projection = {
      receptions: pos === "TE" ? 4.0 : 5.2,
      receivingYards: fpts * 8,
      receivingTds: fpts / 24,
      fpts,
      expectedPlays: 10 - (depth - 1) * 2,
      expectedRushPerPlay: 0.0,
      expectedTdPerPlay: 0.05,
      floor: fpts * 0.65,
      ceiling: fpts * 1.35,
      boomProb: 0.18,
      bustProb: 0.18,
    };
    return applyFirstYearStarterAdjustment(projection, pos, firstYearStarter);
  }
  const fpts = clamp(9 - (depth - 1) * 3, 2, 12);
  const projection = {
    fpts,
    expectedPlays: 0,
    expectedRushPerPlay: 0,
    expectedTdPerPlay: 0,
    floor: fpts * 0.7,
    ceiling: fpts * 1.3,
    boomProb: 0.12,
    bustProb: 0.22,
  };
  return applyFirstYearStarterAdjustment(projection, pos, firstYearStarter);
};

const buildSecPlayers = (): Player[] => {
  const players: Player[] = [];
  const posCounts: Record<string, number> = {};

  secDepthCharts.forEach((team) => {
    const positions = team.positions as Record<string, { depth: number; name: string; classYear: string; firstYearStarter?: boolean }[]>;
    Object.entries(positions).forEach(([pos, depthPlayers]) => {
      depthPlayers.forEach((depthPlayer) => {
        if (!depthPlayer.name || depthPlayer.name.toLowerCase() === "not sure") {
          return;
        }
        const posKey = pos.toUpperCase();
        posCounts[posKey] = (posCounts[posKey] || 0) + 1;
        const projection = buildProjection(posKey, depthPlayer.depth, depthPlayer.firstYearStarter);
        players.push({
          id: players.length + 1,
          name: depthPlayer.name,
          school: team.team,
          pos: posKey,
          conf: "SEC",
          rank: players.length + 1,
          adp: players.length + 1,
          posRank: posCounts[posKey],
          rostered: 0,
          status: "HEALTHY",
          projection,
          history: [
            {
              year: 2025,
              stats: {
                fpts: projection.fpts,
                passingYards: projection.passingYards,
                passingTds: projection.passingTds,
                ints: projection.ints,
                rushingYards: projection.rushingYards,
                rushingTds: projection.rushingTds,
                receptions: projection.receptions,
                receivingYards: projection.receivingYards,
                receivingTds: projection.receivingTds,
              },
            },
          ],
          analysis: `${posKey} projection based on current depth chart${depthPlayer.firstYearStarter ? " (first-year starter adjustment applied)." : "."}`,
        });
      });
    });
  });

  return players;
};

const secPlayers = buildSecPlayers();

export default function Watchlist() {
  const [view, setView] = useState<"watchlist" | "browse">("browse");
  const [activeWatchlist, setActiveWatchlist] = useState<string | null>(null);
  const [showNamingModal, setShowNamingModal] = useState(false);
  const [newWatchlistName, setNewWatchlistName] = useState("");
  const [favoritedPlayerIds, setFavoritedPlayerIds] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);

  const filteredPlayers = useMemo(() => {
    return secPlayers.filter(p =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.school.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery]);

  const favoritedPlayers = useMemo(() => {
    return secPlayers.filter(p => favoritedPlayerIds.includes(p.id));
  }, [favoritedPlayerIds]);

  const [pendingPlayerId, setPendingPlayerId] = useState<number | null>(null);

  const handleFavorite = (e: React.MouseEvent, playerId: number) => {
    e.stopPropagation();
    if (!activeWatchlist) {
      setPendingPlayerId(playerId);
      setShowNamingModal(true);
      return;
    }

    setFavoritedPlayerIds(prev =>
      prev.includes(playerId) ? prev.filter(id => id !== playerId) : [...prev, playerId]
    );
  };

  const createWatchlist = () => {
    if (newWatchlistName.trim()) {
      const name = newWatchlistName.trim();
      setActiveWatchlist(name);
      setShowNamingModal(false);
      setNewWatchlistName("");
      setView("watchlist");

      if (pendingPlayerId) {
        setFavoritedPlayerIds(prev => [...prev, pendingPlayerId]);
        setPendingPlayerId(null);
      }
    }
  };

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-12 animate-in fade-in duration-1000 relative">
      <PlayerDetailModal 
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />

      {/* Naming Modal Popup */}
      {showNamingModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-md bg-black/40">
          <Card className="w-full max-w-md bg-card/90 border border-primary/20 rounded-[2.5rem] shadow-2xl p-10 space-y-8 animate-in zoom-in-95 duration-300">
            <div className="space-y-2">
              <h2 className="text-3xl font-black italic uppercase tracking-tighter text-foreground">Create Watchlist</h2>
              <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground uppercase opacity-60">Give your new list a custom name</p>
            </div>
            
            <div className="space-y-4">
              <Input 
                value={newWatchlistName}
                onChange={(e) => setNewWatchlistName(e.target.value)}
                placeholder="e.g. My Sleeper Picks"
                className="bg-white/5 border-white/10 h-14 rounded-2xl text-sm font-medium focus:ring-primary/20 focus:border-primary/40"
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && createWatchlist()}
              />
              <div className="flex gap-4 pt-2">
                <Button 
                  variant="ghost" 
                  onClick={() => setShowNamingModal(false)}
                  className="flex-1 h-12 rounded-xl text-[10px] font-black uppercase tracking-widest text-muted-foreground hover:bg-white/5"
                >
                  Cancel
                </Button>
                <Button 
                  onClick={createWatchlist}
                  disabled={!newWatchlistName.trim()}
                  className="flex-1 h-12 bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-xl shadow-[0_10px_20px_rgba(var(--primary),0.2)] hover:scale-105 transition-all"
                >
                  Create List
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-4">
            <h1 className="text-6xl font-black italic uppercase tracking-tighter text-foreground bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-transparent leading-none">
              {view === "browse" ? "Browse Players" : activeWatchlist || "Watchlist"}
            </h1>
          </div>
          <p className="text-muted-foreground font-medium uppercase tracking-[0.4em] text-[10px]">
            {view === "browse" ? "Scout and favorite elite talent" : "Your high-priority draft targets"}
          </p>
        </div>
        
        {view === "browse" ? (
          <Button
            onClick={() => setView("watchlist")}
            className="h-14 px-8 bg-white/5 border border-white/10 text-muted-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl hover:bg-primary/10 hover:text-primary transition-all gap-3"
          >
            <Bookmark className="w-4 h-4" /> My Watchlists
          </Button>
        ) : (
          <Button
            onClick={() => setShowNamingModal(true)}
            className="h-14 px-8 bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_20px_rgba(var(--primary),0.2)] hover:scale-105 transition-all gap-3"
          >
            <Plus className="w-4 h-4" /> New Watchlist
          </Button>
        )}
      </div>

      {view === "watchlist" ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {favoritedPlayers.length > 0 ? (
            <div className="md:col-span-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {favoritedPlayers.map((player) => (
                <Card
                  key={player.id}
                  onClick={() => openPlayerDetails(player)}
                  className="bg-card/40 backdrop-blur-md border border-white/10 rounded-[2.5rem] p-8 group hover:border-primary/40 transition-all duration-500 hover:scale-[1.02] relative overflow-hidden cursor-pointer"
                >
                  <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 blur-2xl rounded-full -mr-12 -mt-12 group-hover:bg-primary/10 transition-colors pointer-events-none" />
                  <div className="flex items-center justify-between relative z-10">
                          <div className="space-y-1">
                            <h3 className="text-xl font-black italic uppercase text-foreground group-hover:text-primary transition-colors">{player.name}</h3>
                            <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/60 uppercase">{player.school} • {player.pos}</p>
                          </div>
                    <Button 
                      onClick={(e) => handleFavorite(e, player.id)}
                      variant="ghost" 
                      className="h-10 w-10 p-0 rounded-xl bg-white/5 border border-white/10 text-primary hover:bg-primary/10 hover:text-red-400 transition-colors group/unfav"
                    >
                      <X className="w-4 h-4 group-hover/unfav:scale-110 transition-transform" />
                    </Button>
                  </div>
                  <div className="mt-8 flex items-center justify-between relative z-10">
                    <div className="flex flex-col">
                      <span className="text-[9px] font-black text-muted-foreground/30 uppercase tracking-widest">Conference</span>
                      <span className="text-[11px] font-black text-foreground uppercase">{player.conf}</span>
                    </div>
                    <div className="flex flex-col text-right">
                      <span className="text-[9px] font-black text-muted-foreground/30 uppercase tracking-widest">ADP</span>
                      <span className="text-[11px] font-black text-primary uppercase italic">{player.adp}</span>
                    </div>
                  </div>
                  <div className="mt-6 flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-muted-foreground/60 relative z-10">
                    <span>Proj {weeklyProjection(player.projection.fpts).toFixed(1)} FPTS</span>
                  </div>
                </Card>
              ))}
              <button 
                onClick={() => setView("browse")}
                className="bg-white/[0.02] border-2 border-dashed border-white/5 rounded-[2.5rem] flex flex-col items-center justify-center p-8 space-y-4 hover:border-primary/40 hover:bg-white/5 transition-all duration-500 group min-h-[160px]"
              >
                <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors">
                  <Plus className="w-6 h-6" />
                </div>
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground group-hover:text-foreground">Add Player</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => setView("browse")}
              className="md:col-span-3 h-[50vh] bg-card/20 backdrop-blur-md border border-white/5 border-dashed rounded-[4rem] flex flex-col items-center justify-center text-center p-12 group hover:border-primary/20 transition-all duration-700"
            >
              <div className="relative mb-6">
                <div className="absolute inset-0 bg-primary/10 blur-[40px] opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative w-20 h-20 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center text-muted-foreground group-hover:text-primary group-hover:scale-110 transition-all duration-500">
                  <Plus className="w-10 h-10" />
                </div>
              </div>

              <span className="text-[11px] font-black uppercase tracking-[0.4em] text-muted-foreground group-hover:text-foreground transition-colors">
                Add Player
              </span>
            </button>
          )}

          {/* Bottom navigation option */}
          <div className="md:col-span-3 flex justify-center pt-8 border-t border-white/5 mt-8">
            <Button
              onClick={() => setView("browse")}
              variant="ghost"
              className="h-12 px-8 rounded-xl text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground hover:text-primary transition-all gap-3"
            >
              <ChevronLeft className="w-4 h-4" /> Back to Browsing Players
            </Button>
          </div>
        </div>
      ) : (
        /* Browse View */
        <div className="space-y-8 animate-in slide-in-from-right-8 duration-500">
          <div className="flex items-center gap-6">
            <div className="relative flex-1 group">
              <Search className="absolute left-6 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
              <Input 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by player name or school..." 
                className="pl-16 h-16 bg-white/5 border-white/10 rounded-2xl text-sm font-medium focus:ring-primary/20 focus:border-primary/40 shadow-xl backdrop-blur-md"
              />
            </div>
          </div>

          <Card className="bg-card/40 backdrop-blur-xl border border-white/5 rounded-[3.5rem] overflow-hidden shadow-[0_40px_100px_rgba(0,0,0,0.5)] relative">
            <div className="bg-gradient-to-r from-white/5 via-white/[0.02] to-transparent px-10 py-6 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-[11px] font-black tracking-[0.5em] text-primary uppercase italic">Player Pool</h3>
            </div>

            <div className="max-h-[600px] overflow-x-hidden no-scrollbar scroll-smooth">
              <table className="w-full table-fixed">
                <thead>
                  <tr className="bg-white/5 border-b border-white/5">
                    <th className="w-[34%] px-4 md:px-6 py-4 text-left text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">Name</th>
                    <th className="w-[8%] px-2 md:px-4 py-4 text-left text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">ADP</th>
                    <th className="w-[11%] px-2 md:px-4 py-4 text-center text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">Pos</th>
                    <th className="w-[14%] px-2 md:px-4 py-4 text-center text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">Projected</th>
                    <th className="w-[10%] px-2 md:px-4 py-4 text-center text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">Match</th>
                    <th className="w-[9%] px-2 md:px-4 py-4 text-center text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">% Rost</th>
                    <th className="w-[14%] px-2 md:px-4 py-4 text-center text-[10px] font-black text-muted-foreground/60 uppercase tracking-[0.2em] whitespace-nowrap">Fav</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {filteredPlayers.map((player) => {
                    const weeklyProj = weeklyProjection(player.projection.fpts);
                    const isFav = favoritedPlayerIds.includes(player.id);
                    const style = posStyles[player.pos] || posStyles.DB;
                    const matchup = getMatchupGrade(player.school || "TEAM", player.pos);
                    return (
                      <tr
                        key={player.id}
                        onClick={() => openPlayerDetails(player)}
                        className="group/row hover:bg-white/[0.04] transition-all duration-300 cursor-pointer relative"
                      >
                        <td className="px-4 md:px-6 py-4 relative">
                          <div className="space-y-1">
                            <h4 className="text-[14px] font-black italic uppercase text-foreground group-hover/row:text-white transition-all tracking-tight leading-none truncate">{player.name}</h4>
                            <p className="text-[8px] font-bold text-muted-foreground/40 uppercase tracking-[0.2em] truncate">{player.school} • {player.conf}</p>
                          </div>
                        </td>
                        <td className="px-2 md:px-4 py-4">
                          <span className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-foreground/80 group-hover/row:text-foreground transition-colors">{player.adp}</span>
                        </td>
                        <td className="px-2 md:px-4 py-4">
                          <div className="flex justify-center">
                            <div className={cn(
                              "px-3 py-1 rounded-xl border text-[8px] font-black uppercase tracking-[0.15em] transition-all duration-500",
                              style.bg, style.border, style.text, style.shadow,
                              "group-hover/row:scale-110 group-hover/row:shadow-[0_0_20px_rgba(var(--primary),0.2)]"
                            )}>
                              {player.pos}
                            </div>
                          </div>
                        </td>
                        <td className="px-2 md:px-4 py-4 text-center">
                          <span className="text-[10px] font-black text-foreground uppercase group-hover/row:text-white transition-colors whitespace-nowrap">
                            {weeklyProj.toFixed(1)} PTS
                          </span>
                        </td>
                        <td className="px-2 md:px-4 py-4 text-center">
                          <span className={cn("text-[10px] font-black uppercase tracking-[0.15em]", matchupGradeColor(matchup.grade))}>
                            {matchup.grade}
                          </span>
                        </td>
                        <td className="px-2 md:px-4 py-4 text-center">
                          <span className="text-[10px] font-black text-muted-foreground/60 uppercase group-hover/row:text-primary transition-colors">{player.rostered}%</span>
                        </td>
                        <td className="px-2 md:px-4 py-4 text-center">
                          <Button
                            onClick={(e) => handleFavorite(e, player.id)}
                            className={cn(
                              "h-10 w-10 p-0 rounded-xl transition-all",
                              isFav
                                ? "bg-primary text-primary-foreground shadow-[0_0_20px_rgba(var(--primary),0.3)]"
                                : "bg-white/5 border border-white/10 text-muted-foreground hover:text-primary hover:bg-white/10"
                            )}
                            aria-label={isFav ? "Unfavorite player" : "Favorite player"}
                          >
                            <Bookmark className={cn("w-4 h-4 transition-all", isFav ? "fill-current scale-110" : "text-muted-foreground")} />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
