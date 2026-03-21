import React, { useState, useMemo, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { 
  ArrowLeft, 
  Check, 
  ChevronRight, 
  Users, 
  Trophy, 
  ArrowRightLeft, 
  Shield, 
  Target, 
  Activity,
  User,
  ArrowRight,
  ChevronLeft,
  Star,
  Zap,
  TrendingUp
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { allPlayersMock } from "@/data/playersMock";
import { Player } from "@/types/player";
import { evaluateTrade } from "@/lib/tradeAnalyzer";
import { getSchedulePreview } from "@/lib/strengthOfSchedule";
import { apiPost } from "@/lib/api";

const posStyles: Record<string, { bg: string, border: string, text: string, shadow: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400", shadow: "shadow-[0_0_15px_rgba(59,130,246,0.3)]" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400", shadow: "shadow-[0_0_15px_rgba(16,185,129,0.3)]" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400", shadow: "shadow-[0_0_15px_rgba(168,85,247,0.3)]" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400", shadow: "shadow-[0_0_15px_rgba(249,115,22,0.3)]" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400", shadow: "shadow-[0_0_15px_rgba(6,182,212,0.3)]" },
};

const myRosterMock = [
  { id: 101, name: "Jaxson Dart", pos: "QB", school: "OLE MISS", fpts: 312.4, status: "STARTER", wkProj: 22.5, posRank: 4 },
  { id: 102, name: "Ashton Jeanty", pos: "RB", school: "BSU", fpts: 288.8, status: "STARTER", wkProj: 24.1, posRank: 2 },
  { id: 111, name: "Omarion Hampton", pos: "RB", school: "UNC", fpts: 245.2, status: "STARTER", wkProj: 17.8, posRank: 6 },
  { id: 103, name: "Emeka Egbuka", pos: "WR", school: "OSU", fpts: 238.3, status: "STARTER", wkProj: 18.4, posRank: 8 },
  { id: 106, name: "Tetairoa McMillan", pos: "WR", school: "ARIZONA", fpts: 248.1, status: "STARTER", wkProj: 19.2, posRank: 5 },
  { id: 104, name: "Colston Loveland", pos: "TE", school: "MICHIGAN", fpts: 145.2, status: "STARTER", wkProj: 12.8, posRank: 3 },
  { id: 112, name: "Will Reichard", pos: "K", school: "ALABAMA", fpts: 142.6, status: "STARTER", wkProj: 11.3, posRank: 2 },
  { id: 108, name: "Tez Johnson", pos: "WR", school: "OREGON", fpts: 212.4, status: "BENCH", wkProj: 15.5, posRank: 12 },
  { id: 109, name: "Elic Ayomanor", pos: "WR", school: "STANFORD", fpts: 205.1, status: "BENCH", wkProj: 14.2, posRank: 15 },
  { id: 110, name: "KJ Jefferson", pos: "QB", school: "UCF", fpts: 265.4, status: "BENCH", wkProj: 18.1, posRank: 11 },
  { id: 113, name: "Brock Bowers", pos: "TE", school: "GEORGIA", fpts: 189.5, status: "BENCH", wkProj: 13.6, posRank: 4 },
];

const otherTeamRosterMock = [
  { id: 1, name: "Quinn Ewers", pos: "QB", school: "TEXAS", fpts: 345.5, status: "STARTER", wkProj: 26.4, posRank: 1 },
  { id: 2, name: "Ollie Gordon II", pos: "RB", school: "OKST", fpts: 325.2, status: "STARTER", wkProj: 25.8, posRank: 1 },
  { id: 11, name: "TreVeyon Henderson", pos: "RB", school: "OSU", fpts: 255.5, status: "STARTER", wkProj: 16.4, posRank: 5 },
  { id: 3, name: "Luther Burden III", pos: "WR", school: "MISSOURI", fpts: 302.5, status: "STARTER", wkProj: 23.5, posRank: 1 },
  { id: 12, name: "Rome Odunze", pos: "WR", school: "WASHINGTON", fpts: 271.3, status: "STARTER", wkProj: 19.8, posRank: 3 },
  { id: 13, name: "Brock Bowers", pos: "TE", school: "GEORGIA", fpts: 189.5, status: "STARTER", wkProj: 13.6, posRank: 4 },
  { id: 14, name: "Cam Little", pos: "K", school: "ARKANSAS", fpts: 131.1, status: "STARTER", wkProj: 10.5, posRank: 6 },
  { id: 4, name: "Dillon Gabriel", pos: "QB", school: "OREGON", fpts: 332.2, status: "BENCH", wkProj: 24.8, posRank: 2 },
  { id: 15, name: "Ashton Jeanty", pos: "RB", school: "BSU", fpts: 288.8, status: "BENCH", wkProj: 24.1, posRank: 2 },
  { id: 16, name: "Evan Stewart", pos: "WR", school: "OREGON", fpts: 201.2, status: "BENCH", wkProj: 14.4, posRank: 14 },
  { id: 17, name: "Mason Taylor", pos: "TE", school: "LSU", fpts: 143.2, status: "BENCH", wkProj: 10.2, posRank: 8 },
];

export default function Trade() {
  const { leagueId, playerId } = useParams();
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [mySelectedIds, setMySelectedIds] = useState<number[]>([]);
  const [theirSelectedIds, setTheirSelectedIds] = useState<number[]>([]);

  const targetPlayer = useMemo(() => {
    return allPlayersMock.find(p => p.id === Number(playerId)) || otherTeamRosterMock[0];
  }, [playerId]);

  const toggleMySelection = (id: number) => {
    setMySelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleTheirSelection = (id: number) => {
    setTheirSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleMakeOffer = () => {
    if (mySelectedIds.length > 0) {
      setStep(2);
    }
  };

  const handleSendTrade = () => {
    if (theirSelectedIds.length > 0) {
      navigate(`/league/${leagueId}`);
    }
  };

  const teamNames: Record<string, string> = {
    "saturday-league": "Tiger Kings",
    "pro-scout-elite": "Crimson Tide Elite",
    "default": "The Dynasty Team"
  };

  const opponentTeamName = teamNames[leagueId || "default"] || teamNames["default"];

  const selectedMyPlayers = myRosterMock.filter(p => mySelectedIds.includes(p.id));
  const selectedTheirPlayers = otherTeamRosterMock.filter(p => theirSelectedIds.includes(p.id));
  const [tradeResult, setTradeResult] = useState(() => evaluateTrade(selectedTheirPlayers, selectedMyPlayers));

  useEffect(() => {
    if (!selectedTheirPlayers.length || !selectedMyPlayers.length) {
      setTradeResult(evaluateTrade(selectedTheirPlayers, selectedMyPlayers));
      return;
    }
    const season = new Date().getFullYear();
    const week = 1;
    apiPost<{ receive_value: number; give_value: number; delta: number; verdict: string }>(
      "/trade/analyze",
      {
        receive_ids: selectedTheirPlayers.map((p) => p.id),
        give_ids: selectedMyPlayers.map((p) => p.id),
        season,
        week,
        league_size: 12,
        roster_slots: { QB: 1, RB: 2, WR: 2, TE: 1, K: 1, BE: 4, IR: 1 },
      }
    )
      .then((payload) => {
        setTradeResult({
          receiveValue: payload.receive_value,
          giveValue: payload.give_value,
          delta: payload.delta,
          verdict: payload.verdict,
        });
      })
      .catch(() => {
        setTradeResult(evaluateTrade(selectedTheirPlayers, selectedMyPlayers));
      });
  }, [selectedTheirPlayers, selectedMyPlayers]);

  const averageScheduleGrade = (players: typeof selectedMyPlayers) => {
    if (!players.length) return { label: "Neutral", color: "text-amber-300" };
    const grades = players.flatMap((p) => getSchedulePreview(p.school, p.pos).map((g) => g.grade));
    const score = grades.reduce((sum, g) => {
      if (g === "A+" || g === "A") return sum + 2;
      if (g === "B") return sum + 1;
      if (g === "D") return sum - 1;
      if (g === "F") return sum - 2;
      return sum;
    }, 0);
    if (score >= 4) return { label: "Easy", color: "text-emerald-400" };
    if (score <= -4) return { label: "Hard", color: "text-red-400" };
    return { label: "Neutral", color: "text-amber-300" };
  };
  const mySchedule = averageScheduleGrade(selectedMyPlayers);
  const theirSchedule = averageScheduleGrade(selectedTheirPlayers);
  const myPreview = selectedMyPlayers[0] ? getSchedulePreview(selectedMyPlayers[0].school, selectedMyPlayers[0].pos) : [];
  const theirPreview = selectedTheirPlayers[0] ? getSchedulePreview(selectedTheirPlayers[0].school, selectedTheirPlayers[0].pos) : [];
  const fairnessScore = (() => {
    const total = Math.max(1, tradeResult.giveValue + tradeResult.receiveValue);
    const gap = Math.abs(tradeResult.delta);
    return Math.max(0, Math.min(100, Math.round(100 - (gap / total) * 120)));
  })();

  return (
    <div className="max-w-6xl w-full mx-auto space-y-12 animate-in fade-in duration-1000 py-10 px-4 md:px-6 relative overflow-x-hidden">
      {/* Reorganized Header - Dashboard Style */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
        <div className="space-y-4">
          <div className="flex items-center gap-6">
            <Button asChild variant="ghost" className="h-14 w-14 rounded-[1.5rem] bg-white/5 border border-white/10 text-muted-foreground hover:text-primary transition-all hover:scale-110 flex items-center justify-center p-0">
              <Link to="/leagues">
                <ArrowLeft className="w-6 h-6" />
              </Link>
            </Button>
            <div className="space-y-1">
              <h1 className="text-6xl font-black italic uppercase tracking-tighter text-foreground leading-none">
                Trade Builder
              </h1>
              <div className="flex items-center gap-3">
                <div className="px-5 py-2 rounded-xl bg-primary/10 border border-primary/20 backdrop-blur-md">
                   <span className="text-[10px] font-black tracking-[0.4em] text-primary uppercase leading-none block">
                     {leagueId?.replace(/-/g, ' ')}
                   </span>
                </div>
                <div className="w-1 h-1 rounded-full bg-primary/40" />
                <span className="text-[10px] font-black tracking-[0.4em] text-muted-foreground uppercase">
                  Negotiating with {opponentTeamName}'s Owner
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Progress Bar - Top Right Pill */}
        <div
          className={cn(
            "relative overflow-hidden rounded-[2.5rem] border transition-all duration-500 group/prog h-fit",
            step === 1
              ? "bg-white/5 border-blue-400/20 shadow-[0_20px_50px_rgba(59,130,246,0.25)]"
              : "bg-white/5 border-emerald-400/20 shadow-[0_20px_50px_rgba(16,185,129,0.25)]"
          )}
        >
          <div
            className={cn(
              "absolute inset-y-0 left-0 transition-all duration-500",
              step === 1
                ? "bg-gradient-to-r from-blue-700 via-blue-400 to-blue-700"
                : "bg-gradient-to-r from-emerald-700 via-emerald-400 to-emerald-700"
            )}
            style={{ width: step === 1 ? "50%" : "100%" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover/prog:translate-x-full transition-transform duration-1000" />
          <div className="relative z-10 h-12 px-14 flex items-center justify-center text-[10px] font-black uppercase tracking-[0.4em] text-white select-none">
            Offer
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-8 xl:gap-10 min-w-0">
        {/* Main Selection Area */}
        <div className="space-y-8">
           <div className="flex items-center justify-between px-2">
              <div className="space-y-1">
                 <h2 className="text-3xl font-black italic uppercase text-foreground">
                   {step === 1 ? "Select players to trade away" : "Select players to acquire"}
                 </h2>
                 <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground uppercase opacity-40">
                   {step === 1 ? "Your Full Roster" : `${targetPlayer.name}'s Full Roster`}
                 </p>
              </div>
              <div className="flex items-center gap-4">
                 <div className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 flex items-center gap-2">
                    <Trophy className="w-3.5 h-3.5 text-primary" />
                    <span className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">Season Stats Enabled</span>
                 </div>
              </div>
           </div>

           <Card className="bg-card/30 backdrop-blur-sm border border-white/10 rounded-[2.75rem] overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
              <div className="divide-y divide-white/10">
                {["STARTER", "BENCH"].map((status) => (
                  <div key={status} className="flex flex-col">
                    <div className="px-8 py-4 border-b border-white/10 grid grid-cols-[24px_1fr] lg:grid-cols-[24px_minmax(0,1fr)_88px_88px_88px] items-center">
                      <div />
                      <div className="text-[10px] font-black tracking-[0.35em] text-primary uppercase italic">{status}S</div>
                      <div className="hidden lg:block text-center text-[9px] font-black text-muted-foreground/60 uppercase tracking-[0.25em]">WK PROJ</div>
                      <div className="hidden lg:block text-center text-[9px] font-black text-muted-foreground/60 uppercase tracking-[0.25em]">SEASON</div>
                      <div className="hidden lg:block text-center text-[9px] font-black text-muted-foreground/60 uppercase tracking-[0.25em] whitespace-nowrap">POS RK</div>
                    </div>
                    {(step === 1 ? myRosterMock : otherTeamRosterMock).filter(p => p.status === status).map((player) => {
                      const isSelected = step === 1 ? mySelectedIds.includes(player.id) : theirSelectedIds.includes(player.id);
                      const style = posStyles[player.pos] || posStyles.QB;

                      return (
                        <div
                          key={player.id}
                          onClick={() =>
                            step === 1
                              ? toggleMySelection(player.id)
                              : toggleTheirSelection(player.id)
                          }
                          className={cn(
                            "px-8 py-4 grid grid-cols-[24px_1fr] items-center gap-x-4 gap-y-2 cursor-pointer transition-colors hover:bg-white/[0.03] border-b border-white/10 last:border-0",
                            isSelected && "bg-white/[0.02]"
                          )}
                        >
                          {/* Checkbox */}
                          <div
                            className={cn(
                              "h-5 w-5 rounded-[6px] border flex items-center justify-center",
                              isSelected
                                ? "bg-primary/20 border-primary/40 text-primary"
                                : "bg-white/5 border-white/10 text-transparent"
                            )}
                          >
                            <Check className="w-3.5 h-3.5 stroke-[3]" />
                          </div>

                          {/* Player */}
                          <div className="min-w-0 flex items-center justify-between gap-6">
                            <div className="min-w-0">
                              <div className="flex items-center gap-3 min-w-0">
                                <span
                                  className={cn(
                                    "text-[14px] font-black tracking-tight text-foreground truncate",
                                    player.name.length > 22 ? "text-[13px]" : "text-[14px]"
                                  )}
                                >
                                  {player.name}
                                </span>
                                <span
                                  className={cn(
                                    "px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-[10px] font-black uppercase tracking-widest shrink-0 drop-shadow-[0_0_8px_currentColor]",
                                    style.text
                                  )}
                                >
                                  {player.pos}
                                </span>
                              </div>
                              <div className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-[0.2em] truncate mt-0.5">
                                {player.school}
                              </div>
                            </div>

                            {/* Stats */}
                            <div className="hidden lg:grid grid-cols-3 gap-0 text-center shrink-0">
                              <div className="w-[88px] text-[12px] font-black text-foreground">{player.wkProj}</div>
                              <div className="w-[88px] text-[12px] font-black text-foreground">{player.fpts}</div>
                              <div className="w-[88px] text-[12px] font-black text-primary whitespace-nowrap">#{player.posRank}</div>
                            </div>
                          </div>

                          {/* Mobile stats */}
                          <div className="col-span-2 grid grid-cols-3 gap-4 pl-[28px] lg:hidden pt-1">
                            <div className="text-center">
                              <div className="text-[9px] font-black text-muted-foreground/50 uppercase tracking-[0.25em]">WK</div>
                              <div className="text-[12px] font-black text-foreground">{player.wkProj}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-[9px] font-black text-muted-foreground/50 uppercase tracking-[0.25em]">SEASON</div>
                              <div className="text-[12px] font-black text-foreground">{player.fpts}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-[9px] font-black text-muted-foreground/50 uppercase tracking-[0.25em]">POS</div>
                              <div className="text-[12px] font-black text-primary whitespace-nowrap">#{player.posRank}</div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
           </Card>
        </div>

        {/* Sidebar Summary Area */}
        <div className="space-y-8 h-fit xl:sticky xl:top-12 min-w-0">
           <Card className="bg-[#0A0C10]/80 backdrop-blur-2xl border border-white/10 rounded-[3.5rem] p-8 md:p-10 space-y-10 relative overflow-hidden group shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
              <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[100px] rounded-full -mr-32 -mt-32 pointer-events-none" />
              
              <div className="space-y-8 relative z-10">
                 <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                       <ArrowRightLeft className="w-5 h-5 text-primary" />
                       <h3 className="text-[11px] font-black tracking-[0.5em] text-primary uppercase italic">Trade Overview</h3>
                    </div>
                    <span className="text-[9px] font-black text-muted-foreground/40 uppercase tracking-widest">Sync Active</span>
                 </div>
                 
                 <div className="space-y-10">
                    <div className="space-y-4">
                       <div className="flex items-center justify-between">
                          <p className="text-[9px] font-black text-red-400 uppercase tracking-widest">Sending Away</p>
                       </div>
                       <div className="flex flex-wrap gap-2">
                          {mySelectedIds.length > 0 ? mySelectedIds.map(id => {
                            const p = myRosterMock.find(x => x.id === id);
                            return (
                              <div key={id} className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-[10px] font-black text-foreground uppercase tracking-widest hover:border-red-500/40 transition-colors">
                                {p?.name}
                              </div>
                            );
                          }) : <div className="w-full py-8 rounded-[2rem] border border-dashed border-white/5 flex items-center justify-center text-[10px] font-black text-muted-foreground/20 italic uppercase tracking-[0.3em]">Empty Offer</div>}
                       </div>
                    </div>

                    <div className="h-[1px] w-full bg-white/5" />

                    <div className="space-y-4">
                       <div className="flex items-center justify-between">
                          <p className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Receiving</p>
                       </div>
                       <div className="flex flex-wrap gap-2">
                          {theirSelectedIds.length > 0 ? theirSelectedIds.map(id => {
                            const p = otherTeamRosterMock.find(x => x.id === id);
                            return (
                              <div key={id} className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-[10px] font-black text-foreground uppercase tracking-widest hover:border-emerald-500/40 transition-colors">
                                {p?.name}
                              </div>
                            );
                          }) : <div className="w-full py-8 rounded-[2rem] border border-dashed border-white/5 flex items-center justify-center text-[10px] font-black text-muted-foreground/20 italic uppercase tracking-[0.3em]">Empty Selection</div>}
                       </div>
                    </div>
                 </div>
              </div>

              <div className="pt-4 relative z-10">
                 {step === 1 ? (
                   <Button
                    disabled={mySelectedIds.length === 0}
                    onClick={handleMakeOffer}
                    className={cn(
                      "w-full h-20 rounded-[2.5rem] text-[12px] font-black uppercase tracking-[0.4em] transition-all duration-500 relative overflow-hidden group/btn",
                      mySelectedIds.length > 0
                        ? "bg-gradient-to-r from-blue-700 via-blue-400 to-blue-700 text-white shadow-[0_20px_50px_rgba(59,130,246,0.4)] hover:scale-[1.02] active:scale-95 border border-blue-400/20"
                        : "bg-white/5 text-muted-foreground/20 cursor-not-allowed border border-white/5"
                    )}
                   >
                     {mySelectedIds.length > 0 && (
                       <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover/btn:translate-x-full transition-transform duration-1000" />
                     )}
                     <span className="relative z-10 flex items-center justify-center gap-3">
                        Continue <ArrowRight className="w-4 h-4" />
                     </span>
                   </Button>
                 ) : (
                   <div className="flex flex-col gap-6">
                      <Button
                        disabled={theirSelectedIds.length === 0}
                        onClick={handleSendTrade}
                        className={cn(
                          "w-full h-20 rounded-[2.5rem] text-[12px] font-black uppercase tracking-[0.4em] transition-all duration-500 relative overflow-hidden group/btn",
                          theirSelectedIds.length > 0
                            ? "bg-gradient-to-r from-emerald-700 via-emerald-400 to-emerald-700 text-white shadow-[0_20px_50px_rgba(16,185,129,0.4)] hover:scale-[1.02] active:scale-95 border border-emerald-400/20"
                            : "bg-white/5 text-muted-foreground/20 cursor-not-allowed border border-white/5"
                        )}
                      >
                        <span className="relative z-10 flex items-center justify-center gap-3">
                           Send Trade
                        </span>
                      </Button>
                      <Button 
                        variant="ghost"
                        onClick={() => setStep(1)}
                        className="h-12 text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ChevronLeft className="w-4 h-4 mr-2" /> Adjust Offer
                      </Button>
                   </div>
                 )}
              </div>
           </Card>

           <Card className="bg-gradient-to-br from-primary/5 to-transparent border border-white/5 rounded-[2.5rem] p-8 space-y-6">
              <div className="flex items-center gap-3">
                 <Shield className="w-5 h-5 text-primary" />
                 <h3 className="text-sm font-black italic uppercase text-white">Trade Analysis</h3>
              </div>
              {(selectedMyPlayers.length > 0 || selectedTheirPlayers.length > 0) ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">You Give</p>
                      <p className="text-2xl font-black text-foreground">{tradeResult.giveValue}</p>
                      <p className={cn("text-[9px] font-black uppercase tracking-widest", mySchedule.color)}>
                        Schedule {mySchedule.label}
                      </p>
                      {myPreview.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {myPreview.map((game) => (
                            <span key={`my-${game.opponent}`} className={cn("text-[9px] font-black uppercase tracking-widest", game.colorClass)}>
                              {game.grade}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">You Receive</p>
                      <p className="text-2xl font-black text-foreground">{tradeResult.receiveValue}</p>
                      <p className={cn("text-[9px] font-black uppercase tracking-widest", theirSchedule.color)}>
                        Schedule {theirSchedule.label}
                      </p>
                      {theirPreview.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {theirPreview.map((game) => (
                            <span key={`their-${game.opponent}`} className={cn("text-[9px] font-black uppercase tracking-widest", game.colorClass)}>
                              {game.grade}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-2xl bg-white/5 border border-white/10">
                    <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">Trade Fairness Score</span>
                    <span className="text-[12px] font-black uppercase tracking-widest text-primary">
                      {fairnessScore}/100
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">You Gain</p>
                      <p className={cn("text-xl font-black", tradeResult.delta >= 0 ? "text-emerald-400" : "text-red-400")}>
                        {tradeResult.delta >= 0 ? "+" : ""}{tradeResult.delta.toFixed(1)} pts
                      </p>
                    </div>
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/60">Verdict</p>
                      <p className={cn("text-xl font-black uppercase", tradeResult.delta >= 0 ? "text-emerald-400" : "text-red-400")}>
                        {tradeResult.verdict}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-[10px] font-medium text-muted-foreground/60 leading-loose tracking-widest uppercase">
                  Our AI Evaluator is analyzing this trade. Fair value indicators will appear once both teams select athletes.
                </p>
              )}
           </Card>
        </div>
      </div>
    </div>
  );
}
