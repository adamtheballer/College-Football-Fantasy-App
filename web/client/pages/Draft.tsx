import React, { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import {
  Trophy,
  Users,
  ChevronRight,
  Search,
  Clock,
  UserPlus,
  ChevronDown,
  PlayCircle,
  ListFilter,
  ArrowUpRight,
  Zap,
  ArrowLeft,
  Sparkles,
  Info,
  TrendingUp,
  Target,
  User,
  Activity,
  Star,
  Eye,
  MessageSquare,
  Bookmark,
  Plus,
  Check
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { Player } from "@/types/player";
import { allPlayersMock } from "@/data/playersMock";
import { buildDraftPlayerPool } from "@/lib/draftPlayerPool";
import { buildDraftBoard, DraftPlayer, DraftRosterSlots } from "@/lib/draftRankings";
import { getSchedulePreview } from "@/lib/strengthOfSchedule";

const posStyles: Record<string, { bg: string, border: string, text: string, shadow: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400", shadow: "shadow-[0_0_15px_rgba(59,130,246,0.3)]" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400", shadow: "shadow-[0_0_15px_rgba(16,185,129,0.3)]" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400", shadow: "shadow-[0_0_15px_rgba(168,85,247,0.3)]" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400", shadow: "shadow-[0_0_15px_rgba(249,115,22,0.3)]" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400", shadow: "shadow-[0_0_15px_rgba(6,182,212,0.3)]" },
};

const DraftOrderPill = ({ name, pick, isCurrent, onClick, round, isUserTeam }: any) => (
  <button 
    onClick={onClick}
    className={cn(
      "flex flex-col items-center gap-1 px-5 py-3 rounded-2xl transition-all duration-500 min-w-[140px] shrink-0 group/pill overflow-hidden relative",
      isCurrent 
        ? "bg-primary text-primary-foreground shadow-[0_0_30px_rgba(var(--primary),0.5)] scale-105 border border-white/20" 
        : isUserTeam
          ? "bg-primary/20 border border-primary/30 text-primary hover:bg-primary/30"
          : "bg-white/5 border border-white/5 text-muted-foreground hover:bg-white/10"
    )}
  >
    <span className="text-[8px] font-black uppercase tracking-[0.2em] opacity-40">{round}.{(pick || 0).toString().padStart(2, '0')}</span>
    <div className="flex items-center gap-2">
       <span className="text-[10px] font-black uppercase tracking-[0.2em] truncate relative z-10">{name}</span>
       {isCurrent && <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse shadow-[0_0_10px_#fff]" />}
       {isUserTeam && !isCurrent && <Star className="w-3 h-3 text-primary fill-current" />}
    </div>
    {(isCurrent || isUserTeam) && <div className="absolute inset-0 bg-gradient-to-r from-white/10 to-transparent pointer-events-none" />}
  </button>
);

const DEFAULT_DRAFT_CONFIG = {
  leagueSize: 12,
  rosterSlots: {
    QB: 1,
    RB: 2,
    WR: 2,
    TE: 1,
    K: 1,
    BE: 4,
    IR: 1,
  } satisfies DraftRosterSlots,
};

const clampValue = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const resolveDraftConfig = () => {
  if (typeof window === "undefined") {
    return DEFAULT_DRAFT_CONFIG;
  }
  const params = new URLSearchParams(window.location.search);
  const leagueSize = Number(params.get("teams")) || DEFAULT_DRAFT_CONFIG.leagueSize;
  const bench = Number(params.get("bench")) || DEFAULT_DRAFT_CONFIG.rosterSlots.BE;
  const ir = Number(params.get("ir")) || DEFAULT_DRAFT_CONFIG.rosterSlots.IR;
  return {
    ...DEFAULT_DRAFT_CONFIG,
    leagueSize: clampValue(leagueSize, 6, 20),
    rosterSlots: {
      ...DEFAULT_DRAFT_CONFIG.rosterSlots,
      BE: clampValue(bench, 2, 10),
      IR: clampValue(ir, 0, 3),
    },
  };
};

const buildRosterSlots = (slots: DraftRosterSlots) => {
  const roster: { pos: string; player: string | null }[] = [];
  if (slots.QB > 0) roster.push({ pos: "QB", player: null });
  for (let i = 1; i <= slots.RB; i += 1) roster.push({ pos: `RB${i}`, player: null });
  for (let i = 1; i <= slots.WR; i += 1) roster.push({ pos: `WR${i}`, player: null });
  if (slots.TE > 0) roster.push({ pos: "TE", player: null });
  if (slots.K > 0) roster.push({ pos: "K", player: null });
  for (let i = 0; i < slots.BE; i += 1) roster.push({ pos: "BE", player: null });
  for (let i = 0; i < slots.IR; i += 1) roster.push({ pos: "IR", player: null });
  return roster;
};

export default function Draft() {
  console.log("Draft component mounting...");
  const draftConfig = React.useMemo(() => resolveDraftConfig(), []);
  const [isIntermission, setIsIntermission] = useState(true);
  const [intermissionTime, setIntermissionTime] = useState(60);
  const [timeLeft, setTimeLeft] = useState(60);
  const [activeTab, setActiveTab] = useState("players");
  const [sortMode, setSortMode] = useState<"recommended" | "adp">("recommended");
  const [viewingTeam, setViewingTeam] = useState<string | null>(null);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);
  const [queue, setQueue] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [draftedPlayers, setDraftedPlayers] = useState<number[]>([]);
  const [currentPick, setCurrentPick] = useState(0); 

  const baseTeams = [
    "Mike R.",
    "Alex P.",
    "Sarah J.",
    "Chris K.",
    "My Team",
    "John D.",
    "Emma W.",
    "David L.",
    "Sam T.",
    "Chris B.",
    "Taylor S.",
    "Jordan M.",
  ];
  const teamNames = React.useMemo(() => {
    const names = [...baseTeams];
    if (names.length < draftConfig.leagueSize) {
      for (let i = names.length; i < draftConfig.leagueSize; i += 1) {
        names.push(`Team ${i + 1}`);
      }
    }
    return names.slice(0, draftConfig.leagueSize);
  }, [draftConfig.leagueSize]);
  const generateSnakeOrder = (teams: string[], rounds: number) => {
    const order: { name: string; pick: number; round: number }[] = [];
    for (let round = 1; round <= rounds; round += 1) {
      const roundTeams = round % 2 === 1 ? teams : [...teams].reverse();
      roundTeams.forEach((name, idx) => {
        order.push({ name, pick: idx + 1, round });
      });
    }
    return order;
  };

  const initialRoster = buildRosterSlots(draftConfig.rosterSlots);
  const [myRoster, setMyRoster] = useState(initialRoster);
  const draftOrder = generateSnakeOrder(teamNames, initialRoster.length);
  const currentPicker = draftOrder[currentPick];
  const isMyTurn = currentPicker?.name === "My Team";

  const handleDraft = (p: DraftPlayer) => {
    if (!isMyTurn || draftedPlayers.includes(p.id)) return;
    setDraftedPlayers(prev => [...prev, p.id]);
    setMyRoster(prev => {
      const newRoster = [...prev];
      let slotIdx = newRoster.findIndex(s => s.pos.startsWith(p.pos) && !s.player);
      if (slotIdx === -1) {
        slotIdx = newRoster.findIndex(s => s.pos === "BE" && !s.player);
      }
      if (slotIdx === -1) {
        slotIdx = newRoster.findIndex(s => s.pos === "IR" && !s.player);
      }
      if (slotIdx !== -1) {
        newRoster[slotIdx] = { ...newRoster[slotIdx], player: p.name };
      }
      return newRoster;
    });
    setCurrentPick(prev => prev + 1);
    setTimeLeft(60);
  };

  const toggleQueue = (playerId: number) => {
    setQueue(prev => prev.includes(playerId) ? prev.filter(id => id !== playerId) : [...prev, playerId]);
  };

  useEffect(() => {
    if (isIntermission && intermissionTime > 0) {
      const timer = setInterval(() => setIntermissionTime(prev => prev - 1), 1000);
      return () => clearInterval(timer);
    } else if (isIntermission && intermissionTime === 0) {
      setIsIntermission(false);
    }
  }, [isIntermission, intermissionTime]);

  useEffect(() => {
    if (!isIntermission && timeLeft > 0) {
      const timer = setInterval(() => setTimeLeft(prev => prev - 1), 1000);
      return () => clearInterval(timer);
    } else if (!isIntermission && timeLeft === 0) {
      setCurrentPick(prev => prev + 1);
      setTimeLeft(60);
    }
  }, [isIntermission, timeLeft]);

  const draftBoardPlayers = React.useMemo(
    () => buildDraftBoard(buildDraftPlayerPool(allPlayersMock), draftConfig),
    [draftConfig]
  );
  const sortedPlayers = [...draftBoardPlayers].sort((a, b) => {
    if (sortMode === "adp") {
      return a.adpRank - b.adpRank;
    }
    return a.draftRank - b.draftRank;
  });
  const filteredPlayers = sortedPlayers.filter(p =>
    !draftedPlayers.includes(p.id) &&
    (p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.school.toLowerCase().includes(searchQuery.toLowerCase()))
  );
  const queuePlayers = sortedPlayers.filter(p => queue.includes(p.id));
  const smartRecommendations = React.useMemo(() => {
    const emptyStarterByPos: Record<string, number> = { QB: 0, RB: 0, WR: 0, TE: 0, K: 0 };
    myRoster.forEach((slot) => {
      if (slot.player) return;
      const pos = slot.pos.replace(/[0-9]/g, "");
      if (pos in emptyStarterByPos) {
        emptyStarterByPos[pos] += 1;
      }
    });
    const gradeToScore = (grade: string) => {
      if (grade === "A+") return 2;
      if (grade === "A") return 1.5;
      if (grade === "B") return 1;
      if (grade === "C") return 0;
      if (grade === "D") return -1;
      return -1.5;
    };
    return filteredPlayers
      .slice(0, 80)
      .map((player) => {
        const needBoost = emptyStarterByPos[player.pos] > 0 ? 8 : 2;
        const schedule = getSchedulePreview(player.school, player.pos, 5);
        const scheduleScore =
          schedule.length > 0
            ? schedule.reduce((sum, game) => sum + gradeToScore(game.grade), 0) / schedule.length
            : 0;
        const injuryPenalty =
          player.status && player.status !== "HEALTHY" ? 2.5 : 0;
        const finalScore =
          player.projectedPoints * 0.55 +
          needBoost * 1.4 +
          scheduleScore * 1.8 -
          injuryPenalty;
        const rosterReason = emptyStarterByPos[player.pos] > 0 ? "fills a starting need" : "adds depth";
        const scheduleReason = schedule.length
          ? `SOS ${schedule.map((g) => g.grade).join("")}`
          : "neutral SOS";
        return {
          player,
          finalScore,
          reasons: [
            `${player.projectedPoints.toFixed(1)} projected points`,
            rosterReason,
            scheduleReason,
            injuryPenalty > 0 ? "injury risk present" : "low injury risk",
          ],
        };
      })
      .sort((a, b) => b.finalScore - a.finalScore)
      .slice(0, 3);
  }, [filteredPlayers, myRoster]);

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  const renderRoster = (teamName: string) => {
    const isMe = teamName === "My Team";
    const rosterToRender = isMe ? myRoster : initialRoster;
    return (
      <div className="fixed inset-0 z-[110] bg-gradient-to-br from-[#010208] via-[#020512] to-[#010208] p-12 overflow-auto h-screen animate-in slide-in-from-top-4 duration-500">
        <div className="max-w-7xl mx-auto space-y-12">
          <div className="flex items-center gap-6">
            <Button onClick={() => setViewingTeam(null)} variant="ghost" className="h-14 w-14 rounded-2xl bg-white/5 hover:bg-white/10 text-muted-foreground group/back">
              <ArrowLeft className="w-6 h-6 group-hover/back:-translate-x-1 transition-transform" />
            </Button>
            <div className="space-y-1">
              <h2 className="text-5xl font-black italic uppercase tracking-tighter text-foreground">{teamName} Roster</h2>
              <p className="text-[12px] font-black uppercase tracking-[0.4em] text-primary">Team Analysis • 2026 Season</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
            {rosterToRender.map((r, i) => (
              <div key={i} className="flex flex-col gap-4 p-8 rounded-[2.5rem] bg-card/40 border border-white/5 group hover:border-primary/40 transition-all duration-500 hover:scale-[1.02] hover:shadow-2xl">
                <div className="flex items-center justify-between">
                  <div className="px-4 py-1 rounded-xl bg-white/5 border border-white/10 text-[10px] font-black text-primary uppercase tracking-widest">
                    {r.pos}
                  </div>
                  <Bookmark className="w-5 h-5 text-white/5 group-hover:text-primary transition-colors" />
                </div>
                <span className={cn(
                  "text-[15px] font-black italic uppercase tracking-tight",
                  !r.player ? "text-muted-foreground/10" : "text-foreground group-hover:text-primary transition-colors"
                )}>
                  {r.player || "Empty Position"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen flex flex-col p-8 space-y-8 relative">
      <Button
        asChild
        variant="ghost"
        className="fixed top-8 left-8 z-[150] h-12 w-12 rounded-2xl bg-white/5 border border-white/10 text-muted-foreground hover:text-primary transition-all hover:scale-110 flex items-center justify-center p-0"
      >
        <Link to="/leagues">
          <ArrowLeft className="w-5 h-5" />
        </Link>
      </Button>

      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />
      {viewingTeam && renderRoster(viewingTeam)}

      {/* Top Draft Header / Order */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-8">
        {/* Timer Card */}
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] overflow-hidden group shadow-2xl hover:border-primary/20 transition-all duration-700 h-full">
           <div className="absolute top-0 right-0 w-48 h-48 bg-primary/5 blur-3xl rounded-full -mr-24 -mt-24" />
           <CardContent className="p-10 relative z-10 flex flex-col items-center justify-center h-full gap-6">
              <div className="flex items-center gap-3">
                 <Clock className="w-5 h-5 text-primary animate-pulse" />
                 <span className="text-[10px] font-black tracking-[0.5em] text-primary uppercase drop-shadow-[0_0_10px_rgba(var(--primary),0.5)]">
                    {isIntermission ? "Intermission" : "On The Clock"}
                 </span>
              </div>
              <div className={cn(
                "text-7xl font-black italic tracking-tighter tabular-nums drop-shadow-[0_0_20px_rgba(255,255,255,0.1)] transition-colors",
                (isIntermission ? intermissionTime : timeLeft) <= 10 ? "text-red-500 animate-pulse" : "text-foreground"
              )}>
                00:{(isIntermission ? intermissionTime : timeLeft).toString().padStart(2, '0')}
              </div>
              <div className="space-y-1 text-center">
                 <p className="text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground/40">
                   {isIntermission ? "Draft Starting Soon" : `Pick ${currentPicker?.round || 0}.${(currentPicker?.pick || 0).toString().padStart(2, '0')}`}
                 </p>
                 <div className="h-[1px] w-12 mx-auto bg-primary/20" />
                 <p className="text-[10px] font-black uppercase tracking-widest text-primary italic">
                   {isIntermission ? "Prepare Strategy" : `Round ${currentPicker?.round}`}
                 </p>
              </div>
           </CardContent>
        </Card>

        {/* Draft Order Strip */}
        <div className="flex flex-col gap-6 bg-white/5 backdrop-blur-md rounded-[3rem] border border-white/5 p-8 overflow-hidden relative group">
           <div className="absolute top-[-50%] left-[-10%] w-[120%] h-[200%] bg-gradient-to-br from-primary/5 via-transparent to-blue-500/5 rotate-12 pointer-events-none" />
           <div className="flex items-center justify-between relative z-10">
              <h3 className="text-[10px] font-black tracking-[0.4em] text-muted-foreground/60 uppercase italic">Draft Order</h3>
              <div className="flex items-center gap-3">
                 <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest px-2 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">Live Sync</span>
                 <Users className="w-3 h-3 text-muted-foreground/40" />
              </div>
           </div>
           <div className="flex items-center gap-6 overflow-x-auto no-scrollbar pb-2 relative z-10">
              {draftOrder.slice(currentPick, currentPick + 12).map((t, i) => (
                <DraftOrderPill 
                  key={`${t.name}-${t.round}-${t.pick}`} 
                  name={t.name} 
                  pick={t.pick} 
                  round={t.round}
                  isCurrent={i === 0 && !isIntermission} 
                  isUserTeam={t.name === "My Team"}
                  onClick={() => setViewingTeam(t.name)}
                />
              ))}
           </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-8 pb-32">
        {/* Main Selection Area */}
        <div className="space-y-8">
           {/* Controls / Search */}
           <div className="flex flex-col md:flex-row gap-6 items-center justify-between">
              <div className="relative w-full md:w-[480px] group">
                <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  placeholder="Search consensus players..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-14 bg-white/5 border-white/5 rounded-[1.5rem] h-16 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-widest uppercase shadow-2xl"
                />
              </div>
              <div className="flex items-center gap-4">
                <Select value={sortMode} onValueChange={(value) => setSortMode(value as "recommended" | "adp")}>
                  <SelectTrigger className="h-16 w-[200px] rounded-[1.5rem] bg-white/5 border-white/5 text-[10px] font-black uppercase tracking-[0.3em]">
                    <SelectValue placeholder="Sort" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="recommended">Recommended</SelectItem>
                    <SelectItem value="adp">ADP</SelectItem>
                  </SelectContent>
                </Select>
                <div className="p-5 px-8 bg-primary/10 rounded-[1.5rem] border border-primary/20 flex items-center gap-4 shadow-[0_0_30px_rgba(var(--primary),0.1)]">
                   <div className="w-2.5 h-2.5 rounded-full bg-primary animate-ping" />
                   <span className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">SNAKE MODE</span>
                </div>
              </div>
           </div>

           {/* Player Table */}
           <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3.5rem] overflow-hidden shadow-2xl group hover:border-primary/20 transition-all duration-700 relative">
              <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 blur-[100px] rounded-full -mr-48 -mt-48 group-hover:bg-primary/10 transition-colors" />
              <div className="overflow-x-auto relative z-10">
                <table className="w-full">
                  <thead>
                    <tr className="bg-white/5 border-b border-white/5">
                      <th className="px-10 py-8 text-left text-[11px] font-black text-muted-foreground/60 uppercase tracking-[0.3em]">Name</th>
                      <th className="px-10 py-8 text-left text-[11px] font-black text-muted-foreground/60 uppercase tracking-[0.3em]">School</th>
                      <th className="px-10 py-8 text-center text-[11px] font-black text-muted-foreground/60 uppercase tracking-[0.3em]">ADP</th>
                      <th className="px-10 py-8 text-center text-[11px] font-black text-muted-foreground/60 uppercase tracking-[0.3em]">Proj Season Pts</th>
                      <th className="px-10 py-8 text-right text-[11px] font-black text-muted-foreground/60 uppercase tracking-[0.3em]">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10">
                    {(activeTab === "queue" ? queuePlayers : filteredPlayers).map((p) => {
                      const style = posStyles[p.pos] || posStyles.QB;
                      const isDrafted = draftedPlayers.includes(p.id);
                      if (isDrafted) return null;

                      return (
                        <tr key={p.id} className="group/row hover:bg-white/[0.04] transition-all duration-300 cursor-pointer">
                          <td className="px-10 py-8 relative" onClick={() => openPlayerDetails(p)}>
                            <div className="space-y-1 relative">
                              <div className="flex items-center gap-3 pl-4">
                                <span className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">#{p.draftRank}</span>
                                <h4 className="text-[15px] font-black italic uppercase text-foreground group-hover/row:text-white group-hover/row:drop-shadow-[0_0_20px_rgba(var(--primary),0.4)] transition-all tracking-tight leading-none">{p.name}</h4>
                              </div>
                              <p className="text-[9px] font-bold text-muted-foreground/40 uppercase tracking-[0.3em] pl-4">
                                {p.conf} • Tier {p.tier}
                              </p>
                              <div className={cn("absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-10 transition-all rounded-full opacity-100 shadow-[0_0_15px_rgba(var(--primary),0.5)]", style.text.replace("text-", "bg-"))} />
                            </div>
                          </td>
                          <td className="px-10 py-8">
                             <div className="flex flex-col gap-2">
                                <span className="text-[12px] font-black uppercase tracking-[0.2em] text-muted-foreground/80 group-hover/row:text-foreground transition-colors">{p.school}</span>
                                <div className={cn(
                                  "w-fit px-4 py-1 rounded-xl border text-[9px] font-black uppercase tracking-widest transition-all duration-500",
                                  style.bg, style.border, style.text, style.shadow,
                                  "group-hover/row:scale-110 group-hover/row:shadow-[0_0_20px_rgba(var(--primary),0.2)]"
                                )}>
                                   {p.pos}
                                </div>
                             </div>
                          </td>
                          <td className="px-10 py-8 text-center">
                             <span className="text-sm font-black text-foreground/80 group-hover/row:text-white transition-colors">{Math.round(p.adpEstimate)}</span>
                          </td>
                          <td className="px-10 py-8 text-center">
                             <div className="flex flex-col items-center gap-1">
                               <span className="text-sm font-black text-emerald-400 group-hover/row:text-emerald-300 transition-colors drop-shadow-[0_0_10px_rgba(52,211,153,0.2)]">
                                 {p.projectedPoints}
                               </span>
                             </div>
                          </td>
                          <td className="px-10 py-8 text-right">
                            <div className="flex items-center justify-end gap-5">
                               <Button 
                                 onClick={() => isMyTurn ? handleDraft(p) : toggleQueue(p.id)}
                                 className={cn(
                                   "font-black tracking-[0.3em] text-[10px] uppercase h-14 px-10 rounded-2xl transition-all duration-500 group/draftbtn relative overflow-hidden min-w-[140px]",
                                   isMyTurn && !isIntermission 
                                     ? "bg-primary text-primary-foreground shadow-[0_10px_30px_rgba(var(--primary),0.3)] hover:scale-105" 
                                     : queue.includes(p.id)
                                       ? "bg-emerald-500/20 text-emerald-500 border border-emerald-500/30"
                                       : "bg-white/5 text-muted-foreground/40 hover:bg-white/10 hover:text-foreground border border-white/5"
                                 )}>
                                  {isMyTurn && !isIntermission ? (
                                    <>
                                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover/draftbtn:translate-x-full transition-transform duration-1000" />
                                      <span className="relative z-10">Draft</span>
                                    </>
                                  ) : queue.includes(p.id) ? "Queued" : "Queue"}
                               </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
           </Card>
        </div>

        {/* Info Column */}
        <div className="space-y-8 sticky top-8 h-fit">
           <Card className="bg-card/40 backdrop-blur-md border border-primary/20 rounded-[3rem] overflow-hidden shadow-2xl relative">
              <CardHeader className="p-8 border-b border-white/10 bg-gradient-to-r from-primary/10 to-transparent">
                <CardTitle className="text-[11px] font-black tracking-[0.45em] uppercase text-primary flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  Smart Draft Assistant
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6 space-y-4">
                {smartRecommendations.map((entry) => (
                  <div key={entry.player.id} className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-[12px] font-black italic uppercase text-foreground">
                        {entry.player.name}
                      </p>
                      <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                        {entry.player.pos}
                      </span>
                    </div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/70">
                      {entry.player.school}
                    </p>
                    <ul className="space-y-1">
                      {entry.reasons.slice(0, 3).map((reason) => (
                        <li
                          key={`${entry.player.id}-${reason}`}
                          className="text-[10px] font-medium text-muted-foreground/80"
                        >
                          • {reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                {smartRecommendations.length === 0 && (
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    No draft suggestions available.
                  </p>
                )}
              </CardContent>
           </Card>

           <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] overflow-hidden shadow-2xl relative group">
              <div className="absolute top-0 right-0 w-48 h-48 bg-amber-500/5 blur-[80px] rounded-full -mr-24 -mt-24 group-hover:bg-amber-500/10 transition-colors" />
              <CardHeader className="p-10 border-b border-white/5 bg-gradient-to-br from-white/5 to-transparent relative z-10">
                 <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <CardTitle className="text-[11px] font-black tracking-[0.5em] text-primary uppercase">Summary</CardTitle>
                      <p className="text-[9px] font-bold text-muted-foreground/40 uppercase tracking-widest italic">Live Feed</p>
                    </div>
                    <Trophy className="w-6 h-6 text-amber-500 drop-shadow-[0_0_15px_rgba(245,158,11,0.5)]" />
                 </div>
              </CardHeader>
              <CardContent className="p-10 space-y-10 relative z-10">
                 <div className="space-y-5">
                    <div className="flex items-center justify-between">
                       <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">Power 4 Total</span>
                       <span className="text-sm font-black text-foreground">{draftBoardPlayers.length}</span>
                    </div>
                    <div className="flex items-center justify-between">
                       <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">Selections</span>
                       <span className="text-sm font-black text-primary italic">{draftedPlayers.length} / {draftOrder.length}</span>
                    </div>
                    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden p-[1px] border border-white/5">
                       <div 
                         className="h-full bg-gradient-to-r from-primary to-blue-400 shadow-[0_0_15px_rgba(var(--primary),0.5)] rounded-full transition-all duration-1000" 
                         style={{ width: `${draftOrder.length ? (draftedPlayers.length / draftOrder.length) * 100 : 0}%` }}
                       />
                    </div>
                 </div>

                 <div className="p-8 rounded-[2rem] bg-white/5 border border-white/5 space-y-6 relative overflow-hidden">
                    <h5 className="text-[10px] font-black tracking-[0.4em] text-emerald-400 uppercase italic">Recent Board Action</h5>
                    <div className="space-y-4">
                       {[
                         { name: "D. Gabriel", school: "ORE", team: "Chris K.", color: "bg-primary" },
                         { name: "O. Gordon", school: "OKST", team: "Sarah J.", color: "bg-emerald-500" },
                         { name: "Q. Ewers", school: "TEX", team: "Mike R.", color: "bg-blue-400" }
                       ].map((pick, i) => (
                         <div key={i} className="flex items-center gap-4 group/pick">
                            <div className={cn("w-2 h-2 rounded-full animate-pulse shadow-[0_0_8px_currentColor]", pick.color.replace("bg-", "text-"))} />
                            <div className="flex flex-col">
                               <span className="text-[11px] font-black text-foreground uppercase tracking-tight group-hover/pick:text-primary transition-colors">{pick.name} ({pick.school})</span>
                               <span className="text-[9px] font-bold text-muted-foreground/30 uppercase tracking-widest">{pick.team}</span>
                            </div>
                            <ArrowUpRight className="w-3 h-3 ml-auto text-muted-foreground/20 group-hover/pick:text-primary transition-all group-hover/pick:translate-x-1 group-hover/pick:-translate-y-1" />
                         </div>
                       ))}
                    </div>
                 </div>
              </CardContent>
           </Card>
        </div>
      </div>

      {/* Bottom Floating Navigation / Tabs - Sticky and non-blocking */}
      <div className="fixed bottom-10 left-1/2 -translate-x-1/2 z-[100] w-[95%] max-w-5xl">
         <div className="bg-[#0A0C10]/90 backdrop-blur-[40px] border border-white/10 rounded-[3rem] p-4 shadow-[0_30px_100px_rgba(0,0,0,0.8)] flex items-center justify-between">
            <div className="flex items-center gap-3">
               {["PLAYERS", "QUEUE", "ROSTER"].map((tab) => (
                 <button
                   key={tab}
                   onClick={() => {
                     if (tab === "ROSTER") {
                       setViewingTeam("My Team");
                     } else {
                       setActiveTab(tab.toLowerCase());
                     }
                   }}
                   className={cn(
                     "px-10 py-5 rounded-[1.5rem] text-[10px] font-black tracking-[0.4em] uppercase transition-all duration-500 relative overflow-hidden group/tab",
                     activeTab === tab.toLowerCase()
                       ? "bg-primary text-primary-foreground shadow-[0_15px_30px_rgba(var(--primary),0.3)]"
                       : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                   )}
                 >
                   <span className="relative z-10">{tab}</span>
                   {activeTab === tab.toLowerCase() && (
                     <div className="absolute inset-0 bg-gradient-to-r from-white/10 to-transparent animate-shimmer" />
                   )}
                   {tab === "QUEUE" && queue.length > 0 && (
                     <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-emerald-500 text-[9px] flex items-center justify-center border-2 border-[#0A0C10] font-black shadow-lg">
                       {queue.length}
                     </div>
                   )}
                 </button>
               ))}
            </div>

            <div className="h-12 w-[1px] bg-white/10 mx-8 hidden md:block" />

            <div className="flex items-center gap-10 pr-6">
               <div className="flex flex-col items-end">
                  <div className="flex items-center gap-2">
                     <span className="text-[10px] font-black text-muted-foreground/40 uppercase tracking-[0.3em]">Current Pick</span>
                     <Sparkles className="w-3 h-3 text-primary animate-pulse" />
                  </div>
                  <span className="text-sm font-black text-foreground italic uppercase tracking-tighter">{currentPicker?.name || "Initializing..."} <span className="text-primary italic font-black">({currentPicker?.round || 0}.{(currentPicker?.pick || 0).toString().padStart(2, '0')})</span></span>
               </div>

               <div className="flex flex-col items-end opacity-40">
                  <span className="text-[10px] font-black text-muted-foreground/40 uppercase tracking-[0.3em]">On Deck</span>
                  <span className="text-sm font-black text-foreground/60 italic uppercase tracking-tighter">{draftOrder[currentPick + 1]?.name || "End of Board"}</span>
               </div>
               
               <button className="w-16 h-16 rounded-[1.5rem] bg-white/5 border border-white/10 flex items-center justify-center group/btn hover:bg-primary/20 hover:border-primary/40 transition-all duration-500 shadow-2xl">
                  <Info className="w-6 h-6 text-muted-foreground/40 group-hover/btn:text-primary transition-colors" />
               </button>
            </div>
         </div>
      </div>
    </div>
  );
}
