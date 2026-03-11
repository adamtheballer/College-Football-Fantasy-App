import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Trophy,
  Users,
  ChevronLeft,
  MessageSquare,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  ChevronRight,
  Calendar,
  Info,
  Star
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { Player } from "@/types/player";
import { getMatchupGrade, matchupGradeColor } from "@/lib/matchupGrades";
import { allPlayersMock } from "@/data/playersMock";
import { apiGet } from "@/lib/api";
import { LeagueDetail } from "@/types/league";

const PositionPill = ({ pos }: { pos: string }) => {
  const colors: any = {
    QB: "border-blue-500/50 text-blue-400 bg-blue-500/10",
    RB: "border-emerald-500/50 text-emerald-400 bg-emerald-500/10",
    WR: "border-orange-500/50 text-orange-400 bg-orange-500/10",
    TE: "border-purple-500/50 text-purple-400 bg-purple-500/10",
    K: "border-pink-500/50 text-pink-400 bg-pink-500/10",
    BENCH: "border-border text-muted-foreground bg-white/5",
    IR: "border-red-500/50 text-red-400 bg-red-500/10",
  };
  return (
    <div className={cn("px-3 py-1 rounded-full border text-[9px] font-black uppercase tracking-widest min-w-[50px] text-center", colors[pos] || "border-border text-muted-foreground")}>
      {pos}
    </div>
  );
};

const RosterRow = ({ pos, name, team, rostered, start, game, score, proj, boom, player, onClick, isIR = false }: any) => {
  const normalizedPos = player?.pos || pos.replace(/[0-9]/g, "");
  const matchup = getMatchupGrade(team || "TEAM", normalizedPos);
  const colors: any = {
    QB: "bg-blue-500",
    RB: "bg-emerald-500",
    WR: "bg-orange-500",
    TE: "bg-purple-500",
    K: "bg-pink-500",
    BENCH: "bg-muted-foreground",
    IR: "bg-red-500",
  };
  return (
    <div
      onClick={() => player && onClick && onClick(player)}
      className={cn(
        "grid grid-cols-[80px_1fr_80px] items-center py-4 px-6 border-b border-border/40 last:border-0 hover:bg-white/5 transition-all group relative",
        player && "cursor-pointer",
        isIR && "bg-red-500/5"
      )}
    >
      <div className="flex flex-col gap-1">
        <PositionPill pos={pos} />
      </div>
      <div className="flex flex-col gap-1 px-4">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">{name}</h4>
          <span className="text-[9px] font-bold text-muted-foreground/40 uppercase">@{team}</span>
        </div>
        <div className="flex items-center gap-3 text-[9px] font-bold text-muted-foreground/60 uppercase tracking-widest">
          <span>{rostered}% Rost</span>
          <span className="w-1 h-1 rounded-full bg-border" />
          <span>{start}% Start</span>
          <span className="w-1 h-1 rounded-full bg-border" />
          <span className={cn(game === "OUT" && "text-red-400")}>{game}</span>
          <span className="w-1 h-1 rounded-full bg-border" />
          <span className={cn("font-black", matchupGradeColor(matchup.grade))}>Matchup {matchup.grade}</span>
        </div>
      </div>
      <div className="text-right space-y-1">
        <p className="text-sm font-black text-foreground">{score !== undefined && score !== 0 ? score : '-'}</p>
        <p className="text-[9px] font-black text-muted-foreground/50 uppercase tracking-widest">Proj {proj ?? '-'}</p>
      </div>
    </div>
  );
};

const PlayerMatchupRow = ({ pos, p1, p2 }: any) => (
  <div className="grid grid-cols-[1fr_60px_1fr] items-center py-5 border-b border-border/10 last:border-0 px-6 group hover:bg-white/[0.02] transition-colors relative">
    {/* Player 1 */}
    <div className="flex items-center justify-end gap-6 pr-4">
       <div className="flex flex-col items-end">
          <h5 className="text-sm font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">{p1.name}</h5>
          <p className="text-[9px] font-bold text-muted-foreground/60 uppercase tracking-widest leading-none mt-1">{p1.game}</p>
          <div className="flex items-center gap-2 mt-2">
             <span className="text-[9px] font-black text-muted-foreground/30 uppercase tracking-tighter italic">Proj {p1.proj.toFixed(2)}</span>
          </div>
       </div>
       <div className="flex flex-col items-center justify-center min-w-[50px]">
          <span className="text-xl font-black italic text-foreground tracking-tighter">{p1.pts?.toFixed(1) || '0.0'}</span>
          <div className={cn("h-1 w-full rounded-full mt-1", p1.pts > p1.proj ? "bg-emerald-500/40" : "bg-white/5")} />
       </div>
    </div>

    {/* Pos */}
    <div className="flex justify-center relative z-10">
       <div className="w-10 h-10 rounded-xl bg-secondary/80 border border-border/60 flex items-center justify-center text-[10px] font-black text-primary uppercase italic shadow-2xl group-hover:scale-110 group-hover:border-primary/40 transition-all duration-300">
          {pos}
       </div>
    </div>

    {/* Player 2 */}
    <div className="flex items-center justify-start gap-6 pl-4">
       <div className="flex flex-col items-center justify-center min-w-[50px]">
          <span className="text-xl font-black italic text-foreground tracking-tighter">{p2.pts?.toFixed(1) || '0.0'}</span>
          <div className={cn("h-1 w-full rounded-full mt-1", p2.pts > p2.proj ? "bg-emerald-500/40" : "bg-white/5")} />
       </div>
       <div className="flex flex-col items-start">
          <h5 className="text-sm font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">{p2.name}</h5>
          <p className="text-[9px] font-bold text-muted-foreground/60 uppercase tracking-widest leading-none mt-1">{p2.game}</p>
          <div className="flex items-center gap-2 mt-2">
             <span className="text-[9px] font-black text-muted-foreground/30 uppercase tracking-tighter italic">Proj {p2.proj.toFixed(2)}</span>
          </div>
       </div>
    </div>
  </div>
);

const StandingRow = ({ rank, team, owner, record, pts }: any) => (
  <div className="grid grid-cols-[40px_1fr_120px_100px] items-center py-4 px-6 border-b border-border/20 last:border-0 hover:bg-white/5 transition-all group">
    <span className="text-[10px] font-black text-muted-foreground/40">{rank}</span>
    <div className="flex flex-col">
      <h4 className="text-sm font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">{team}</h4>
      <p className="text-[9px] font-bold text-muted-foreground/60 uppercase">{owner}</p>
    </div>
    <div className="text-center">
      <span className="text-xs font-black text-foreground">{record}</span>
    </div>
    <div className="text-right">
      <span className="text-xs font-black text-foreground">{pts}</span>
    </div>
  </div>
);

const weeklyProjection = (player: Player | undefined) => {
  if (!player) return 0;
  const fpts = player.projection?.fpts ?? 0;
  return Number((fpts > 80 ? fpts / 12 : fpts).toFixed(1));
};

const pickByPos = (pos: string, count: number) =>
  allPlayersMock.filter((p) => p.pos === pos).slice(0, count);

const fallbackPlayer = allPlayersMock[0];
const qbs = pickByPos("QB", 4);
const rbs = pickByPos("RB", 6);
const wrs = pickByPos("WR", 6);
const tes = pickByPos("TE", 3);
const ks = pickByPos("K", 2);

const rosterSeed = {
  qb: qbs[0] || fallbackPlayer,
  rb1: rbs[0] || fallbackPlayer,
  rb2: rbs[1] || rbs[0] || fallbackPlayer,
  wr1: wrs[0] || fallbackPlayer,
  wr2: wrs[1] || wrs[0] || fallbackPlayer,
  te: tes[0] || fallbackPlayer,
  k: ks[0] || fallbackPlayer,
};

const benchSeed = {
  qb2: qbs[1] || rosterSeed.qb,
  rb3: rbs[2] || rosterSeed.rb1,
  wr3: wrs[3] || rosterSeed.wr1,
  te2: tes[1] || rosterSeed.te,
};

const oppSeed = {
  qb: qbs[2] || rosterSeed.qb,
  rb: rbs[3] || rosterSeed.rb1,
  wr: wrs[4] || rosterSeed.wr1,
  te: tes[2] || rosterSeed.te,
  k: ks[1] || rosterSeed.k,
};

const rosterRow = (pos: string, player: Player) => ({
  pos,
  name: player.name,
  team: player.school,
  rostered: player.rostered,
  start: Math.min(99, Math.round(player.rostered * 0.85)),
  game: "vs TBD",
  score: 0,
  proj: weeklyProjection(player),
  player,
});

const leagueMockData: any = {
  "saturday-league": {
    name: "Saturday League",
    currentWeek: 1,
    status: "Active",
    team1: { name: "Mountain Falcons", owner: "Adam B.", score: 0.0, prob: 52, img: "MF" },
    team2: { name: "Crimson Titans", owner: "Opponent", score: 0.0, prob: 48, img: "CT" },
    standings: [
      { rank: 1, team: "Mountain Falcons", owner: "Adam B.", record: "0-0", pts: 0.0 },
    ],
    roster: [
      rosterRow("QB", rosterSeed.qb),
      rosterRow("RB1", rosterSeed.rb1),
      rosterRow("RB2", rosterSeed.rb2),
      rosterRow("WR1", rosterSeed.wr1),
      rosterRow("WR2", rosterSeed.wr2),
      rosterRow("TE", rosterSeed.te),
      rosterRow("K", rosterSeed.k),
    ],
    bench: [
      rosterRow("BENCH", benchSeed.qb2),
      rosterRow("BENCH", benchSeed.rb3),
      rosterRow("BENCH", benchSeed.wr3),
      rosterRow("BENCH", benchSeed.te2),
    ],
    ir: [],
    matchups: [
      {
        pos: "QB",
        p1: { name: rosterSeed.qb.name, game: "vs TBD", proj: weeklyProjection(rosterSeed.qb), pts: 0 },
        p2: { name: oppSeed.qb.name, game: "@ TBD", proj: weeklyProjection(oppSeed.qb), pts: 0 },
      },
      {
        pos: "RB",
        p1: { name: rosterSeed.rb1.name, game: "vs TBD", proj: weeklyProjection(rosterSeed.rb1), pts: 0 },
        p2: { name: oppSeed.rb.name, game: "@ TBD", proj: weeklyProjection(oppSeed.rb), pts: 0 },
      },
      {
        pos: "WR",
        p1: { name: rosterSeed.wr1.name, game: "vs TBD", proj: weeklyProjection(rosterSeed.wr1), pts: 0 },
        p2: { name: oppSeed.wr.name, game: "@ TBD", proj: weeklyProjection(oppSeed.wr), pts: 0 },
      },
      {
        pos: "TE",
        p1: { name: rosterSeed.te.name, game: "vs TBD", proj: weeklyProjection(rosterSeed.te), pts: 0 },
        p2: { name: oppSeed.te.name, game: "@ TBD", proj: weeklyProjection(oppSeed.te), pts: 0 },
      },
      {
        pos: "K",
        p1: { name: rosterSeed.k.name, game: "vs TBD", proj: weeklyProjection(rosterSeed.k), pts: 0 },
        p2: { name: oppSeed.k.name, game: "@ TBD", proj: weeklyProjection(oppSeed.k), pts: 0 },
      },
    ]
  },
};

export default function LeagueDetail() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("roster");
  const [week, setWeek] = useState(1);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isPlayerModalOpen, setIsPlayerModalOpen] = useState(false);
  const [leagueMeta, setLeagueMeta] = useState<LeagueDetail | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);

  useEffect(() => {
    if (!leagueId) return;
    if (!/^\d+$/.test(leagueId)) return;
    apiGet<LeagueDetail>(`/leagues/${leagueId}`)
      .then((payload) => {
        setLeagueMeta(payload);
        setMetaError(null);
      })
      .catch((err: any) => {
        setMetaError(err.message || "Unable to load league.");
      });
  }, [leagueId]);

  const data = leagueMockData[leagueId || "saturday-league"] || leagueMockData["saturday-league"];
  const leagueName = leagueMeta?.name || data.name;
  const leagueStatus = leagueMeta?.status || data.status;
  const inviteCode = leagueMeta?.invite_code || null;
  const draftTime = leagueMeta?.draft?.draft_datetime_utc
    ? new Date(leagueMeta.draft.draft_datetime_utc)
    : null;
  const isPreDraft = leagueStatus === "pre_draft" || String(leagueStatus).toLowerCase().includes("pre");

  const openPlayerDetails = (player: Player) => {
    setSelectedPlayer(player);
    setIsPlayerModalOpen(true);
  };

  const tabs = ["ROSTER", "MATCHUP", "LEAGUE", "SCHEDULE"];

  const renderContent = () => {
    switch (activeTab) {
      case "roster":
        return (
          <div className="space-y-6">
            <div className="flex flex-col md:flex-row gap-4 justify-between items-center px-8">
              <div className="flex items-center gap-4 bg-white/5 p-2 rounded-2xl border border-border/40">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 hover:bg-white/10"
                  onClick={() => setWeek(Math.max(1, week - 1))}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <div className="flex flex-col items-center min-w-[80px]">
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Week {week}</span>
                  <span className="text-[8px] font-bold text-muted-foreground/40 uppercase">2026 Season</span>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 hover:bg-white/10"
                  onClick={() => setWeek(Math.min(18, week + 1))}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
              <div className="flex items-center gap-3">
                <Button variant="outline" className="h-10 px-6 rounded-xl border-border text-[9px] font-black uppercase tracking-widest hover:bg-white/5">
                  Quick Lineup
                </Button>
                <Button variant="outline" className="h-10 px-6 rounded-xl border-border text-[9px] font-black uppercase tracking-widest hover:bg-white/5">
                  Matchup Stats <ChevronRight className="w-3 h-3 ml-2" />
                </Button>
              </div>
            </div>

            <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[2.5rem] overflow-hidden shadow-xl">
               <div className="bg-white/5 px-8 py-4 border-b border-border/40 flex items-center justify-between">
                  <h3 className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase">Edit Starters</h3>
                  <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase">Score</span>
               </div>
               <div className="divide-y divide-border/40">
                 {data.roster.map((player: any, i: number) => (
                   <RosterRow key={i} {...player} player={player.player ?? player} onClick={openPlayerDetails} />
                 ))}
               </div>
               
               {/* Bench Section */}
               <div className="bg-white/10 px-8 py-3 border-y border-border/40">
                  <h3 className="text-[9px] font-black tracking-[0.2em] text-primary uppercase italic">Bench (Max 4)</h3>
               </div>
               <div className="divide-y divide-border/10 bg-white/5">
                  {data.bench.map((player: any, i: number) => (
                    <RosterRow key={i} {...player} pos="BENCH" player={player.player ?? player} onClick={openPlayerDetails} />
                  ))}
                  {/* Empty Bench Spots */}
                  {Array.from({ length: Math.max(0, 4 - data.bench.length) }).map((_, i) => (
                    <div key={`empty-bench-${i}`} className="h-14 flex items-center px-8 border-b border-border/10 last:border-0 opacity-20">
                       <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Empty Bench Slot</span>
                    </div>
                  ))}
               </div>

               {/* IR Section */}
               <div className="bg-red-500/10 px-8 py-3 border-y border-red-500/20">
                  <h3 className="text-[9px] font-black tracking-[0.2em] text-red-400 uppercase italic">IR Slot (Max 1)</h3>
               </div>
               <div className="bg-red-500/5 divide-y divide-red-500/10">
                  {data.ir.map((player: any, i: number) => (
                    <RosterRow key={i} {...player} isIR player={player.player ?? player} onClick={openPlayerDetails} />
                  ))}
                  {data.ir.length === 0 && (
                    <div className="h-14 flex items-center px-8 opacity-20">
                       <span className="text-[10px] font-black uppercase tracking-widest text-red-400">Empty IR Slot</span>
                    </div>
                  )}
               </div>

               <div className="bg-white/5 px-8 py-6 border-t border-border/40 flex items-center justify-between">
                  <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase">Total Team Score</span>
                  <div className="flex items-center gap-4">
                     <span className="text-2xl font-black italic text-primary">133.13</span>
                     <span className="text-[10px] font-bold text-muted-foreground/40 uppercase">pts</span>
                  </div>
               </div>
            </Card>
          </div>
        );
      case "matchup":
        return (
          <div className="space-y-12">
            {/* Score Cards - TOP */}
            <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[3rem] overflow-hidden shadow-2xl relative">
              <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-primary/50 via-primary to-primary/50 opacity-50" />
              <CardContent className="p-12">
                <div className="grid grid-cols-1 lg:grid-cols-3 items-center gap-12">
                   {/* Team 1 */}
                   <div className="flex flex-col items-center gap-4 text-center">
                      <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary to-blue-600 flex items-center justify-center text-3xl font-black italic text-white shadow-2xl ring-4 ring-primary/20 transition-transform hover:scale-110 duration-500">
                        {data.team1.img}
                      </div>
                      <div className="space-y-1">
                        <h3 className="text-2xl font-black italic tracking-tighter text-foreground uppercase leading-none">{data.team1.name}</h3>
                        <p className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">{data.team1.owner}</p>
                      </div>
                      <div className="text-5xl font-black italic tracking-tighter text-foreground bg-gradient-to-b from-white to-white/40 bg-clip-text text-transparent">{data.team1.score}</div>
                   </div>

                   {/* Center vs Info */}
                   <div className="flex flex-col items-center gap-6 py-8 border-y lg:border-y-0 lg:border-x border-border/40">
                      <div className="w-16 h-16 rounded-full bg-secondary/30 flex items-center justify-center text-sm font-black italic text-primary uppercase shadow-inner border border-border/40 animate-pulse">
                        VS
                      </div>
                      <div className="flex flex-col items-center">
                         <span className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/40">Matchup Live</span>
                         <span className="text-[8px] font-bold text-muted-foreground/20 uppercase">Week {week}</span>
                      </div>
                   </div>

                   {/* Team 2 */}
                   <div className="flex flex-col items-center gap-4 text-center">
                      <div className="w-24 h-24 rounded-full bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center text-3xl font-black italic text-white shadow-2xl ring-4 ring-red-500/20 transition-transform hover:scale-110 duration-500">
                        {data.team2.img}
                      </div>
                      <div className="space-y-1">
                        <h3 className="text-2xl font-black italic tracking-tighter text-foreground uppercase leading-none">{data.team2.name}</h3>
                        <p className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">{data.team2.owner}</p>
                      </div>
                      <div className="text-5xl font-black italic tracking-tighter text-foreground bg-gradient-to-b from-white to-white/40 bg-clip-text text-transparent">{data.team2.score}</div>
                   </div>
                </div>
              </CardContent>
            </Card>

            {/* Position Matchups - MIDDLE */}
            <div className="space-y-6">
               <div className="flex items-center justify-between px-8">
                  <h3 className="text-[10px] font-black tracking-[0.4em] text-primary uppercase italic">Position Matchups</h3>
                  <div className="h-[1px] flex-1 mx-8 bg-border/40" />
               </div>

               <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[3rem] overflow-hidden shadow-2xl relative">
                  <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
                  <div className="bg-white/5 px-8 py-5 border-b border-border/40 flex items-center justify-between">
                    <div className="flex flex-col gap-1">
                       <span className="text-[9px] font-black uppercase tracking-[0.2em] text-primary italic leading-none">{data.team1.name}</span>
                    </div>
                    <div className="flex items-center gap-4 bg-white/5 px-4 py-1.5 rounded-full border border-border/40">
                       <span className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/40">VS</span>
                    </div>
                    <div className="flex flex-col gap-1 text-right">
                       <span className="text-[9px] font-black uppercase tracking-[0.2em] text-red-400 italic leading-none">{data.team2.name}</span>
                    </div>
                  </div>
                  <div className="divide-y divide-border/5">
                     {data.matchups.map((match: any, i: number) => (
                       <PlayerMatchupRow key={i} {...match} />
                     ))}
                  </div>
               </Card>
            </div>

            {/* Win Probability Bar - BOTTOM */}
            <div className="px-8 space-y-4">
                <div className="flex items-center justify-between px-4">
                  <h3 className="text-[10px] font-black tracking-[0.4em] text-muted-foreground/60 uppercase italic">Win Probability</h3>
                  <span className="text-[10px] font-black tracking-[0.2em] text-primary">{data.team1.prob}%</span>
                </div>
                <div className="h-4 bg-white/5 rounded-full border border-border/20 overflow-hidden flex relative shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)]">
                    <div
                      className={cn(
                        "h-full transition-all duration-1000 shadow-[0_0_15px_rgba(var(--primary),0.5)]",
                        data.team1.prob > 50 ? "bg-gradient-to-r from-primary via-blue-400 to-emerald-400" : "bg-primary"
                      )}
                      style={{ width: `${data.team1.prob}%` }}
                    />
                    <div
                      className={cn(
                        "h-full transition-all duration-1000",
                        data.team2.prob > 50 ? "bg-gradient-to-l from-red-500 via-orange-400 to-amber-400" : "bg-white/10"
                      )}
                      style={{ width: `${data.team2.prob}%` }}
                    />
                </div>
            </div>
          </div>
        );
      case "league":
        return (
          <div className="space-y-12">
            {/* Standings */}
            <div className="space-y-6">
              <div className="flex items-center justify-between px-8">
                <h3 className="text-[10px] font-black tracking-[0.4em] text-primary uppercase">League Standings</h3>
                <div className="h-[1px] flex-1 mx-8 bg-border/40" />
              </div>
              <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[2.5rem] overflow-hidden shadow-xl">
                 <div className="grid grid-cols-[40px_1fr_120px_100px] px-6 py-4 bg-white/5 border-b border-border/40">
                    <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase">Rank</span>
                    <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase">Team / Owner</span>
                    <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase text-center">Record</span>
                    <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground/60 uppercase text-right">Points</span>
                 </div>
                 <div className="divide-y divide-border/40">
                    {data.standings.map((s: any, i: number) => (
                      <StandingRow key={i} {...s} />
                    ))}
                 </div>
              </Card>
            </div>

            {/* Scoring Rules */}
            <div className="space-y-6">
              <div className="flex items-center justify-between px-8">
                <h3 className="text-[10px] font-black tracking-[0.4em] text-emerald-400 uppercase">Scoring Rules</h3>
                <div className="h-[1px] flex-1 mx-8 bg-border/40" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <Card className="p-6 bg-card/40 border-border/60 rounded-3xl">
                    <h4 className="text-xs font-black italic uppercase text-foreground mb-4">Offense</h4>
                    <div className="space-y-3">
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Passing TD</span>
                          <span className="text-foreground font-black">4 Pts</span>
                       </div>
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Rushing TD</span>
                          <span className="text-foreground font-black">6 Pts</span>
                       </div>
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Reception</span>
                          <span className="text-foreground font-black">1 Pts (PPR)</span>
                       </div>
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>20 Passing Yards</span>
                          <span className="text-foreground font-black">1 Pt</span>
                       </div>
                    </div>
                 </Card>
                 <Card className="p-6 bg-card/40 border-border/60 rounded-3xl">
                    <h4 className="text-xs font-black italic uppercase text-foreground mb-4">Defense</h4>
                    <div className="space-y-3">
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Sack</span>
                          <span className="text-foreground font-black">1 Pt</span>
                       </div>
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Interception</span>
                          <span className="text-foreground font-black">2 Pts</span>
                       </div>
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Shutout</span>
                          <span className="text-foreground font-black">10 Pts</span>
                       </div>
                       <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                          <span>Safety</span>
                          <span className="text-foreground font-black">2 Pts</span>
                       </div>
                    </div>
                 </Card>
              </div>
            </div>
          </div>
        );
      case "schedule":
        return (
          <div className="space-y-8">
            <div className="flex items-center justify-between px-8">
              <h3 className="text-[10px] font-black tracking-[0.4em] text-amber-400 uppercase">Weekly Schedule</h3>
              <div className="h-[1px] flex-1 mx-8 bg-border/40" />
            </div>
            <div className="grid gap-6">
              {[1, 2, 3].map((match, i) => (
                <Card key={i} className="bg-card/40 border-border/60 rounded-[2.5rem] p-8 hover:border-primary/30 transition-all cursor-pointer group">
                  <div className="flex items-center justify-between">
                     <div className="flex items-center gap-6">
                        <div className="text-center space-y-1">
                           <div className="w-12 h-12 rounded-full bg-secondary/50 flex items-center justify-center text-xs font-black italic text-primary">T{i+1}</div>
                           <p className="text-[9px] font-black uppercase text-muted-foreground">Team {i+1}</p>
                        </div>
                        <span className="text-xs font-black italic text-muted-foreground/40">VS</span>
                        <div className="text-center space-y-1">
                           <div className="w-12 h-12 rounded-full bg-secondary/50 flex items-center justify-center text-xs font-black italic text-primary">T{i+4}</div>
                           <p className="text-[9px] font-black uppercase text-muted-foreground">Team {i+4}</p>
                        </div>
                     </div>
                     <div className="text-right space-y-2">
                        <p className="text-[10px] font-black uppercase tracking-widest text-primary italic">Week {week} Matchup</p>
                        <p className="text-[11px] font-medium text-muted-foreground flex items-center justify-end gap-2">
                          <Calendar className="w-3 h-3" /> Saturday, Nov 26 • 3:30 PM
                        </p>
                        <Button variant="ghost" className="h-8 px-4 text-[9px] font-black uppercase tracking-widest text-primary/60 group-hover:text-primary transition-all">
                          Preview Matchup <ChevronRight className="w-3 h-3 ml-1" />
                        </Button>
                     </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-1000 relative z-10 pb-20">
      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={isPlayerModalOpen}
        onClose={() => setIsPlayerModalOpen(false)}
      />
      {/* Header */}
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <Link to="/leagues" className="group flex items-center gap-3 text-[10px] font-black uppercase tracking-widest text-muted-foreground hover:text-primary transition-all">
            <div className="p-2 rounded-xl bg-white/5 border border-border group-hover:border-primary/40 transition-all">
              <ChevronLeft className="w-4 h-4" />
            </div>
            Back to Leagues
          </Link>
          <div className="flex items-center gap-3">
             <Button variant="outline" className="h-10 px-6 rounded-2xl border-border text-[9px] font-black uppercase tracking-widest hover:bg-white/5">
                <MessageSquare className="w-4 h-4 mr-2" /> League Chat
             </Button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
           <h1 className="text-4xl font-black italic tracking-tighter text-foreground uppercase italic bg-gradient-to-r from-white to-primary/40 bg-clip-text text-transparent leading-tight">
             {leagueName}
           </h1>
           <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="h-[2px] w-6 bg-primary/40" />
                <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase opacity-60">Week {week} • 2026</span>
              </div>
              <div className="h-1 w-1 rounded-full bg-border" />
              <span className={cn("text-[10px] font-black tracking-[0.2em] uppercase", isPreDraft ? "text-amber-400" : "text-emerald-400")}>
                {isPreDraft ? "Pre-Draft" : "Live Matchup"}
              </span>
           </div>
        </div>
      </div>

      {metaError && (
        <div className="text-[10px] font-black uppercase tracking-[0.3em] text-red-400">
          {metaError}
        </div>
      )}

      {isPreDraft && (
        <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[2rem] p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">Draft Scheduled</p>
            <p className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
              {draftTime ? draftTime.toLocaleString() : "Draft time TBD"}
            </p>
            {inviteCode && (
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/70">
                Invite Code: <span className="text-primary">{inviteCode}</span>
              </p>
            )}
          </div>
          {leagueMeta?.id && (
            <Button
              className="h-12 px-6 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate(`/league/${leagueMeta.id}/lobby`)}
            >
              Open Draft Lobby
            </Button>
          )}
        </Card>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 p-1.5 bg-card/40 backdrop-blur-md border border-border/60 rounded-2xl w-fit">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab.toLowerCase())}
            className={cn(
              "px-8 py-3 rounded-xl text-[10px] font-black tracking-[0.2em] uppercase transition-all duration-300",
              activeTab === tab.toLowerCase()
                ? "bg-primary text-primary-foreground shadow-[0_10px_20px_rgba(var(--primary),0.2)]"
                : "text-muted-foreground hover:text-foreground hover:bg-white/5"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Dynamic Content */}
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        {renderContent()}
      </div>

    </div>
  );
}
