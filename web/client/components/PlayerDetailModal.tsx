import React, { useEffect, useState } from "react";
import { X, Trophy, Activity, Target, Shield, ArrowLeft, Bookmark, ChevronDown, Quote, TrendingUp, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Player } from "@/types/player";
import { apiGet } from "@/lib/api";

interface PlayerDetailModalProps {
  player: Player | null;
  isOpen: boolean;
  onClose: () => void;
}

type MatchupSnapshot = {
  grade: string;
  rank: number | null;
  yardsPerTarget: number | null;
  yardsPerRush: number | null;
  pressureRate: number | null;
};

const matchupGradeColor = (grade?: string) => {
  if (grade === "A+" || grade === "A") return "text-emerald-400";
  if (grade === "B") return "text-lime-300";
  if (grade === "C") return "text-amber-300";
  if (grade === "D") return "text-orange-400";
  if (grade === "F") return "text-red-400";
  return "text-muted-foreground";
};

const posStyles: Record<string, { bg: string, border: string, text: string, shadow: string, accent: string }> = {
  QB: { bg: "bg-blue-500/20", border: "border-blue-500/30", text: "text-blue-400", shadow: "shadow-[0_0_15px_rgba(59,130,246,0.3)]", accent: "blue" },
  RB: { bg: "bg-emerald-500/20", border: "border-emerald-500/30", text: "text-emerald-400", shadow: "shadow-[0_0_15px_rgba(16,185,129,0.3)]", accent: "emerald" },
  WR: { bg: "bg-purple-500/20", border: "border-purple-500/30", text: "text-purple-400", shadow: "shadow-[0_0_15px_rgba(168,85,247,0.3)]", accent: "purple" },
  TE: { bg: "bg-orange-500/20", border: "border-orange-500/30", text: "text-orange-400", shadow: "shadow-[0_0_15px_rgba(249,115,22,0.3)]", accent: "orange" },
  K: { bg: "bg-cyan-500/20", border: "border-cyan-500/30", text: "text-cyan-400", shadow: "shadow-[0_0_15px_rgba(6,182,212,0.3)]", accent: "cyan" },
  DL: { bg: "bg-red-500/20", border: "border-red-500/30", text: "text-red-400", shadow: "shadow-[0_0_15px_rgba(239,68,68,0.3)]", accent: "red" },
  DB: { bg: "bg-pink-500/20", border: "border-pink-500/30", text: "text-pink-400", shadow: "shadow-[0_0_15px_rgba(236,72,153,0.3)]", accent: "pink" },
  LB: { bg: "bg-amber-500/20", border: "border-amber-500/30", text: "text-amber-400", shadow: "shadow-[0_0_15px_rgba(245,158,11,0.3)]", accent: "amber" },
  DE: { bg: "bg-rose-500/20", border: "border-rose-500/30", text: "text-rose-400", shadow: "shadow-[0_0_15px_rgba(244,63,94,0.3)]", accent: "rose" },
  S: { bg: "bg-indigo-500/20", border: "border-indigo-500/30", text: "text-indigo-400", shadow: "shadow-[0_0_15px_rgba(99,102,241,0.3)]", accent: "indigo" },
  OL: { bg: "bg-slate-500/20", border: "border-slate-500/30", text: "text-slate-400", shadow: "shadow-[0_0_15px_rgba(100,116,139,0.3)]", accent: "slate" },
  CB: { bg: "bg-violet-500/20", border: "border-violet-500/30", text: "text-violet-400", shadow: "shadow-[0_0_15px_rgba(139,92,246,0.3)]", accent: "violet" },
};

export function PlayerDetailModal({ player, isOpen, onClose }: PlayerDetailModalProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "stats" | "history">("overview");
  const [historyYear, setHistoryYear] = useState<number>(2025);
  const [matchup, setMatchup] = useState<MatchupSnapshot | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [schedule, setSchedule] = useState<
    { week: number; opponent: string; homeAway: string; grade: string; colorClass: string }[]
  >([]);

  useEffect(() => {
    if (!player || !isOpen) return;
    const controller = new AbortController();
    const season = new Date().getFullYear();
    const week = 1;

    setMatchup(null);
    setReasons([]);
    setSchedule([]);

    apiGet<{ data: any[] }>(`/schedule/player/${player.id}`, { season, week, weeks: 4 }, controller.signal)
      .then((payload) => {
        if (!payload?.data?.length) return;
        const mapped = payload.data.map((game) => ({
          week: game.week,
          opponent: game.opponent,
          homeAway: game.home_away,
          grade: game.grade,
          colorClass:
            game.grade === "A+" || game.grade === "A"
              ? "text-emerald-400"
              : game.grade === "B"
              ? "text-lime-300"
              : game.grade === "C"
              ? "text-amber-300"
              : game.grade === "D"
              ? "text-orange-400"
              : "text-red-400",
        }));
        setSchedule(mapped);
        const nextOpponent = payload.data[0]?.opponent;
        const nextWeek = payload.data[0]?.week ?? week;
        if (nextOpponent) {
          apiGet<{ data: any[] }>(
            "/matchups",
            { season, week: nextWeek, team: nextOpponent, position: player.pos },
            controller.signal
          )
            .then((matchupPayload) => {
              const row = matchupPayload?.data?.[0];
              if (!row) return;
              setMatchup({
                grade: row.grade,
                rank: row.rank,
                yardsPerTarget: row.yards_per_target,
                yardsPerRush: row.yards_per_rush,
                pressureRate: row.pressure_rate,
              });
            })
            .catch(() => {});
        }
      })
      .catch(() => {});

    apiGet<{ reasons: { detail: string }[] }>(`/projections/${player.id}/explanations`, { season, week }, controller.signal)
      .then((payload) => {
        if (!payload?.reasons?.length) return;
        setReasons(payload.reasons.map((r) => r.detail));
      })
      .catch(() => {});

    return () => controller.abort();
  }, [player, isOpen]);

  if (!player || !isOpen) return null;

  const style = posStyles[player.pos] || posStyles.QB;
  const currentHistory =
    player.history.find((h) => h.year === historyYear) ||
    player.history[0] ||
    { year: historyYear, stats: { fpts: 0 } };

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center p-4 md:p-8 animate-in fade-in duration-300 backdrop-blur-2xl bg-black/80">
      <div className="relative w-full max-w-6xl h-full max-h-[90vh] bg-card/60 border border-white/10 rounded-[4rem] shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-500">
        
        {/* Background Glow Overlay */}
        <div className={cn("absolute inset-0 opacity-20 pointer-events-none bg-gradient-to-br from-transparent via-transparent to-primary/20")} />
        <div className={cn("absolute -top-40 -right-40 w-96 h-96 blur-[120px] rounded-full pointer-events-none opacity-20", style.bg.replace("bg-", "bg-"))} />

        {/* Header Navigation */}
        <div className="relative z-10 px-12 pt-12 flex items-center justify-between">
          <Button
            onClick={onClose}
            variant="ghost"
            className="h-14 w-14 rounded-2xl bg-white/5 border border-white/10 text-muted-foreground hover:text-primary transition-all hover:scale-110 shadow-xl"
          >
            <ArrowLeft className="w-6 h-6" />
          </Button>

          <div className="flex flex-col items-center">
             <h2 className="text-5xl md:text-6xl font-black italic uppercase tracking-tighter text-foreground leading-none bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent drop-shadow-2xl">
               {player.name}
             </h2>
             <div className="mt-3 flex items-center gap-4">
               <div className="px-3 py-1 rounded-lg bg-white/5 border border-white/10">
                 <span className="text-[10px] font-black tracking-[0.4em] text-muted-foreground uppercase italic">{player.school}</span>
               </div>
               <div className="w-1.5 h-1.5 rounded-full bg-primary/40 shadow-[0_0_10px_rgba(var(--primary),0.5)]" />
               <div className={cn("px-3 py-1 rounded-lg border", style.bg, style.border)}>
                 <span className={cn("text-[10px] font-black tracking-[0.4em] uppercase", style.text)}>{player.pos}</span>
               </div>
             </div>
          </div>

          <Button
            variant="ghost"
            className="h-14 w-14 rounded-2xl bg-white/5 border border-white/10 text-primary hover:bg-primary/10 transition-all hover:scale-110 shadow-xl"
          >
            <Bookmark className="w-6 h-6" />
          </Button>
        </div>

        {/* Tabs */}
        <div className="relative z-10 px-10 mt-8 border-b border-white/5 flex gap-10">
          {[
            { id: "overview", label: "Overview" },
            { id: "stats", label: "Projections" },
            { id: "history", label: "History" }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                "pb-6 text-[11px] font-black uppercase tracking-[0.3em] transition-all relative",
                activeTab === tab.id ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-primary rounded-full shadow-[0_-4px_12px_rgba(var(--primary),0.4)]" />
              )}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div className="relative z-10 flex-1 overflow-y-auto no-scrollbar p-10">
          {activeTab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 animate-in slide-in-from-bottom-8 duration-500">
              {/* Left Column: Stats Cards */}
              <div className="lg:col-span-8 space-y-10">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                  {[
                    { label: "ADP", value: player.adp, icon: TrendingUp },
                    { label: "CONF", value: player.conf, icon: Trophy },
                    { label: "RANK", value: `#${player.rank}`, icon: Target },
                    { label: "STATUS", value: player.status, icon: Activity, color: "text-emerald-400" },
                  ].map((stat, i) => (
                    <Card key={i} className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8 space-y-6 hover:bg-white/[0.08] transition-all duration-500 group relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-16 h-16 bg-primary/5 blur-xl rounded-full -mr-8 -mt-8 opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center border border-white/5 group-hover:border-primary/20 transition-colors">
                        <stat.icon className="w-5 h-5 text-primary group-hover:scale-110 transition-transform" />
                      </div>
                      <div>
                        <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase mb-2">{stat.label}</p>
                        <p className={cn("text-2xl font-black italic uppercase tracking-tight", stat.color || "text-foreground")}>{stat.value}</p>
                      </div>
                    </Card>
                  ))}
                </div>

                <div className="space-y-8">
                  <div className="flex items-center gap-4">
                    <h3 className="text-[11px] font-black tracking-[0.5em] text-primary uppercase italic">Season Projections</h3>
                    <div className="h-[1px] flex-1 bg-gradient-to-r from-primary/20 to-transparent" />
                  </div>
                  <Card className="bg-[#0A0C10]/40 backdrop-blur-xl border border-white/10 rounded-[3.5rem] p-12 overflow-hidden relative shadow-inner">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/[0.02] to-transparent" />
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-12 relative z-10">
                      {player.pos === "QB" ? (
                        <>
                          <div className="space-y-2">
                            <p className="text-[10px] font-black tracking-widest text-muted-foreground/40 uppercase">Passing Yards</p>
                            <p className="text-4xl font-black italic tracking-tighter text-foreground leading-none">{player.projection.passingYards?.toLocaleString()}</p>
                          </div>
                          <div className="space-y-2">
                            <p className="text-[10px] font-black tracking-widest text-muted-foreground/40 uppercase">Touchdowns</p>
                            <p className="text-4xl font-black italic tracking-tighter text-emerald-400 leading-none">{player.projection.passingTds}</p>
                          </div>
                          <div className="space-y-2">
                            <p className="text-[10px] font-black tracking-widest text-muted-foreground/40 uppercase">Interceptions</p>
                            <p className="text-4xl font-black italic tracking-tighter text-red-400 leading-none">{player.projection.ints}</p>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="space-y-2">
                            <p className="text-[10px] font-black tracking-widest text-muted-foreground/40 uppercase">Rushing Yards</p>
                            <p className="text-4xl font-black italic tracking-tighter text-foreground leading-none">{player.projection.rushingYards?.toLocaleString() || player.projection.receivingYards?.toLocaleString()}</p>
                          </div>
                          <div className="space-y-2">
                            <p className="text-[10px] font-black tracking-widest text-muted-foreground/40 uppercase">Touchdowns</p>
                            <p className="text-4xl font-black italic tracking-tighter text-emerald-400 leading-none">{player.projection.rushingTds || player.projection.receivingTds}</p>
                          </div>
                          <div className="space-y-2">
                            <p className="text-[10px] font-black tracking-widest text-muted-foreground/40 uppercase">Receptions</p>
                            <p className="text-4xl font-black italic tracking-tighter text-blue-400 leading-none">{player.projection.receptions || 0}</p>
                          </div>
                        </>
                      )}
                    </div>
                    <div className="mt-12 pt-12 border-t border-white/5 relative z-10">
                      <Quote className="absolute top-10 left-0 w-10 h-10 text-primary/10" />
                      <p className="text-base font-medium italic text-muted-foreground/80 leading-relaxed pl-14">
                        "{player.analysis}"
                      </p>
                    </div>
                  </Card>
                </div>
              </div>

              {/* Right Column: Profile Image Placeholder & Big Stat */}
              <div className="lg:col-span-4 space-y-8">
                 <div className="aspect-[4/5] rounded-[4rem] bg-gradient-to-b from-white/10 via-white/5 to-transparent border border-white/10 flex items-center justify-center relative group overflow-hidden shadow-2xl">
                    <div className="absolute inset-0 bg-primary/5 group-hover:bg-primary/10 transition-all duration-700" />

                    {player.imageUrl ? (
                      <img
                        src={player.imageUrl}
                        alt={player.name}
                        className="relative z-10 h-full w-full object-cover"
                      />
                    ) : (
                      <Avatar className="relative z-10 h-40 w-40 rounded-[2.5rem] border border-white/10 bg-white/5">
                        <AvatarFallback className="rounded-[2.5rem] bg-white/5 text-5xl font-black italic uppercase text-primary">
                          {player.name
                            .split(" ")
                            .slice(0, 2)
                            .map((part) => part[0])
                            .join("")}
                        </AvatarFallback>
                        <AvatarImage src="" alt={player.name} />
                      </Avatar>
                    )}

                    <div className="text-white/10 scale-[5] relative z-10 transition-transform duration-700 group-hover:scale-[5.5]">
                      <Activity className="w-12 h-12 stroke-[0.5] animate-pulse" />
                    </div>

                    <div className="absolute bottom-12 left-12 right-12 space-y-3 z-20">
                       <p className="text-[11px] font-black uppercase tracking-[0.5em] text-primary italic drop-shadow-[0_0_10px_rgba(var(--primary),0.5)]">Projected</p>
                       <p className="text-5xl font-black italic tracking-tighter text-white drop-shadow-[0_10px_30px_rgba(0,0,0,0.5)]">
                         {player.projection.fpts} <span className="text-xl align-top mt-2 inline-block">PTS</span>
                       </p>
                    </div>
                 </div>
              </div>
            </div>
          )}

          {activeTab === "history" && (
            <div className="space-y-10 animate-in slide-in-from-bottom-8 duration-500">
               <div className="flex items-center justify-between">
                  <h3 className="text-2xl font-black italic uppercase text-foreground">Season History</h3>
                  <div className="relative group">
                    <Button variant="outline" className="h-12 bg-white/5 border-white/10 rounded-xl px-6 gap-3 min-w-[140px] justify-between text-[11px] font-black uppercase tracking-widest">
                      Year: {historyYear}
                      <ChevronDown className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                    </Button>
                    <div className="absolute top-full right-0 mt-2 w-full bg-card/95 border border-white/10 rounded-xl overflow-hidden backdrop-blur-xl hidden group-hover:block z-[400] shadow-2xl">
                       {player.history.map(h => (
                         <button 
                           key={h.year}
                           onClick={() => setHistoryYear(h.year)}
                           className="w-full px-6 py-4 text-left text-[11px] font-black uppercase tracking-widest hover:bg-primary/10 hover:text-primary transition-colors border-b border-white/5 last:border-0"
                         >
                           {h.year}
                         </button>
                       ))}
                    </div>
                  </div>
               </div>

               <Card className="bg-white/5 border border-white/10 rounded-[3rem] overflow-hidden">
                 <table className="w-full text-left">
                   <thead>
                     <tr className="border-b border-white/5 bg-white/5">
                        <th className="px-10 py-6 text-[10px] font-black uppercase tracking-widest text-muted-foreground">Category</th>
                        <th className="px-10 py-6 text-[10px] font-black uppercase tracking-widest text-muted-foreground">Season Stats</th>
                        <th className="px-10 py-6 text-[10px] font-black uppercase tracking-widest text-muted-foreground text-right">Fantasy Points</th>
                     </tr>
                   </thead>
                   <tbody className="divide-y divide-white/[0.02]">
                      {Object.entries(currentHistory.stats).filter(([k]) => k !== 'fpts').map(([key, value]) => {
                        const labelMap: Record<string, string> = {
                          passingYards: "Passing Yards",
                          passingTds: "Passing Touchdowns",
                          ints: "Interceptions",
                          rushingYards: "Rushing Yards",
                          rushingTds: "Rushing Touchdowns",
                          receptions: "Receptions",
                          receivingYards: "Receiving Yards",
                          receivingTds: "Receiving Touchdowns",
                          qbr: "QBR / Efficiency"
                        };
                        return (
                          <tr key={key} className="hover:bg-white/[0.02] transition-colors">
                             <td className="px-10 py-6 text-[11px] font-black uppercase tracking-widest text-muted-foreground">{labelMap[key] || key.replace(/([A-Z])/g, ' $1')}</td>
                             <td className="px-10 py-6 text-lg font-black italic text-foreground tracking-tight">{value}</td>
                             <td className="px-10 py-6 text-right">
                                <span className="text-[10px] font-black bg-primary/10 text-primary px-3 py-1.5 rounded-lg">VERIFIED</span>
                             </td>
                          </tr>
                        );
                      })}
                      <tr className="bg-primary/5">
                         <td className="px-10 py-8 text-[11px] font-black uppercase tracking-[0.3em] text-primary">Season Total</td>
                         <td className="px-10 py-8"></td>
                         <td className="px-10 py-8 text-right text-3xl font-black italic tracking-tighter text-primary">{currentHistory.stats.fpts} PTS</td>
                      </tr>
                   </tbody>
                 </table>
               </Card>
            </div>
          )}

          {activeTab === "stats" && (
            <div className="space-y-10 animate-in slide-in-from-bottom-8 duration-500">
              <div className="flex items-center gap-4">
                <h3 className="text-[11px] font-black tracking-[0.5em] text-primary uppercase italic">Next Week Projection</h3>
                <div className="h-[1px] flex-1 bg-gradient-to-r from-primary/20 to-transparent" />
              </div>

              <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                  <div className="space-y-2">
                    <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">
                      Matchup Grade
                    </p>
                    <div className="flex items-center gap-4">
                      <span className={cn("text-4xl font-black italic", matchupGradeColor(matchup?.grade))}>
                        {matchup?.grade ?? "-"}
                      </span>
                      <span className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                        {matchup?.rank ? `Defense Rank ${matchup.rank}` : "No matchup data"}
                      </span>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">
                      Yards/Target
                      <div className="text-lg font-black text-foreground">{matchup?.yardsPerTarget ?? "-"}</div>
                    </div>
                    <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">
                      Yards/Rush
                      <div className="text-lg font-black text-foreground">{matchup?.yardsPerRush ?? "-"}</div>
                    </div>
                    <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/60">
                      Pressure Rate
                      <div className="text-lg font-black text-foreground">{matchup?.pressureRate ?? "-"}</div>
                    </div>
                  </div>
                </div>
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-2">
                  <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">FPTS</p>
                  <p className="text-3xl font-black italic text-foreground">
                    {(player.projection.fpts > 80 ? player.projection.fpts / 12 : player.projection.fpts).toFixed(1)}
                  </p>
                  <p className="text-[10px] font-bold text-muted-foreground/50 uppercase tracking-widest">
                    Floor {player.projection.floor?.toFixed(1) ?? "-"} • Ceiling {player.projection.ceiling?.toFixed(1) ?? "-"}
                  </p>
                </Card>

                <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-2">
                  <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Next Week Boom/Bust</p>
                  <p className="text-3xl font-black italic text-foreground">
                    {player.projection.boomProb !== undefined ? `${Math.round(player.projection.boomProb * 100)}%` : "-"}
                  </p>
                  <p className="text-[10px] font-bold text-muted-foreground/50 uppercase tracking-widest">
                    Bust {player.projection.bustProb !== undefined ? `${Math.round(player.projection.bustProb * 100)}%` : "-"}
                  </p>
                </Card>

                <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-2">
                  <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Expected Plays</p>
                  <p className="text-3xl font-black italic text-foreground">
                    {player.projection.expectedPlays?.toFixed(1) ?? "-"}
                  </p>
                  <p className="text-[10px] font-bold text-muted-foreground/50 uppercase tracking-widest">
                    Rush/Play {player.projection.expectedRushPerPlay?.toFixed(2) ?? "-"} • TD/Play {player.projection.expectedTdPerPlay?.toFixed(3) ?? "-"}
                  </p>
                </Card>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {player.pos === "QB" ? (
                  <>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Pass Yards</p>
                      <p className="text-2xl font-black italic text-foreground">{player.projection.passingYards?.toFixed(0) ?? "-"}</p>
                    </Card>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Pass TD</p>
                      <p className="text-2xl font-black italic text-emerald-400">{player.projection.passingTds?.toFixed(1) ?? "-"}</p>
                    </Card>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">INT</p>
                      <p className="text-2xl font-black italic text-red-400">{player.projection.ints?.toFixed(1) ?? "-"}</p>
                    </Card>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">QBR</p>
                      <p className="text-2xl font-black italic text-primary">{player.projection.qbr?.toFixed(1) ?? "-"}</p>
                    </Card>
                  </>
                ) : (
                  <>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Rush Yards</p>
                      <p className="text-2xl font-black italic text-foreground">{player.projection.rushingYards?.toFixed(0) ?? "-"}</p>
                    </Card>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Rec Yards</p>
                      <p className="text-2xl font-black italic text-foreground">{player.projection.receivingYards?.toFixed(0) ?? "-"}</p>
                    </Card>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">Receptions</p>
                      <p className="text-2xl font-black italic text-blue-400">{player.projection.receptions?.toFixed(1) ?? "-"}</p>
                    </Card>
                    <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
                      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">TDs</p>
                      <p className="text-2xl font-black italic text-emerald-400">
                        {((player.projection.rushingTds ?? 0) + (player.projection.receivingTds ?? 0)).toFixed(1)}
                      </p>
                    </Card>
                  </>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-4">
                  <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">
                    Projection Reasons
                  </p>
                  <ul className="space-y-2 text-[11px] font-bold uppercase tracking-widest text-muted-foreground/70">
                    {reasons.length ? reasons.map((reason) => (
                      <li key={reason} className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                        {reason}
                      </li>
                    )) : (
                      <li className="text-muted-foreground/50 normal-case tracking-normal">
                        No projection explanation data yet.
                      </li>
                    )}
                  </ul>
                </Card>

                <Card className="bg-white/5 border border-white/10 rounded-[2rem] p-6 space-y-4">
                  <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/40 uppercase">
                    Next 4 Games
                  </p>
                  <div className="space-y-2">
                    {schedule.length ? schedule.map((game) => (
                      <div key={`${game.week}-${game.opponent}-${game.grade}`} className="flex items-center justify-between text-[11px] font-black uppercase tracking-widest">
                        <span className="text-muted-foreground/70">vs {game.opponent}</span>
                        <span className={cn("font-black", game.colorClass)}>{game.grade}</span>
                      </div>
                    )) : (
                      <div className="text-[11px] text-muted-foreground/50 normal-case tracking-normal">
                        No upcoming schedule data available.
                      </div>
                    )}
                  </div>
                </Card>
              </div>
            </div>
          )}
        </div>

        {/* Action Bar */}
        <div className="relative z-10 p-12 bg-white/5 border-t border-white/5 flex items-center justify-between">
           <div className="flex items-center gap-12">
              <div className="flex flex-col gap-1">
                 <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/40 uppercase">% Rostered</span>
                 <span className="text-3xl font-black italic text-foreground tracking-tighter leading-none">{player.rostered}%</span>
              </div>
              <div className="flex flex-col gap-1">
                 <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/40 uppercase">POS Rank</span>
                 <span className="text-3xl font-black italic text-primary tracking-tighter leading-none">#{player.posRank}</span>
              </div>
           </div>

           <div className="flex gap-6 relative">
              <Button
                disabled
                title="Trade flow is not part of the supported React surface yet."
                className="h-16 px-12 bg-primary text-primary-foreground rounded-2xl text-[11px] font-black uppercase tracking-[0.3em] shadow-[0_20px_40px_rgba(var(--primary),0.3)] hover:scale-105 transition-all duration-500 border border-white/10"
              >
                Trade Flow Coming Soon
              </Button>
           </div>
        </div>
      </div>
    </div>
  );
}
