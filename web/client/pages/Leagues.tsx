import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Trophy, Users, ChevronRight, Search, PlusCircle, Sparkles, CalendarDays, Send, BellRing } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import { LeagueDetail } from "@/types/league";

const TeamStanding = ({ rank, initials, name, record, color }: any) => (
  <div className="flex items-center gap-4 group cursor-pointer py-1.5 transition-all duration-300 hover:translate-x-1">
    <span className="text-[10px] font-black text-muted-foreground/60 w-4">{rank}.</span>
    <div className={cn("w-6 h-6 rounded-full flex items-center justify-center text-[8px] font-black text-white shadow-lg", color)}>
      {initials}
    </div>
    <div className="flex-1">
      <span className="text-xs font-bold text-foreground group-hover:text-primary transition-colors">{name}</span>
      <span className="text-[10px] font-bold text-muted-foreground/60 ml-2">({record})</span>
    </div>
  </div>
);

const LeagueCard = ({ id, name, week, teams, standings, icon: Icon, color, onStartDraft }: any) => (
  <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[2.5rem] overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.3)] group hover:border-primary/40 transition-all duration-500 relative">
    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
    <div className="flex flex-col md:flex-row relative z-10">
      {/* Left: League Info */}
      <div className="flex-1 p-8 border-b md:border-b-0 md:border-r border-border/40 relative overflow-hidden">
        <div className={cn("absolute -top-6 -left-6 w-24 h-24 blur-[40px] opacity-20 rounded-full", color)} />
        <div className="relative z-10 flex flex-col h-full justify-between gap-6">
          <div className="space-y-4">
            <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center shadow-2xl transition-transform group-hover:scale-110 duration-500", color)}>
              <Icon className="w-6 h-6 text-white" />
            </div>
            <div className="space-y-1">
              <h3 className="text-2xl font-black italic tracking-tight text-foreground uppercase group-hover:text-primary transition-colors">{name}</h3>
              <p className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase">{week} • {teams} teams</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex -space-x-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="w-6 h-6 rounded-full border-2 border-[#050810] bg-muted flex items-center justify-center overflow-hidden">
                   <Users className="w-3 h-3 text-muted-foreground" />
                </div>
              ))}
            </div>
            <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest">+ {Math.max(0, teams - 4)} Members</span>
          </div>
        </div>
      </div>

      {/* Middle: Standings Preview */}
      <div className="flex-[1.5] p-8 bg-white/5 border-b md:border-b-0 md:border-r border-border/40">
        <div className="space-y-6">
          <h4 className="text-[10px] font-black tracking-[0.3em] text-primary uppercase opacity-60">Standings preview</h4>
          <div className="space-y-1">
            {standings.map((s: any, i: number) => (
              <TeamStanding key={i} {...s} />
            ))}
          </div>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="p-8 flex flex-col gap-4 items-center justify-center bg-gradient-to-br from-primary/5 to-transparent min-w-[240px]">
        <Link to={`/league/${id}`} className="w-full">
          <Button variant="outline" className="w-full border-white/5 bg-white/5 text-foreground font-black tracking-[0.2em] text-[10px] uppercase h-12 px-8 rounded-2xl hover:bg-white/10 transition-all duration-300">
            League Hub
            <ChevronRight className="w-3 h-3 ml-2" />
          </Button>
        </Link>
        <Button 
          onClick={() => onStartDraft(id)}
          className="w-full bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase h-14 px-8 rounded-2xl shadow-[0_10px_30px_rgba(var(--primary),0.2)] hover:scale-105 transition-all duration-300 group/btn relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover/btn:translate-x-full transition-transform duration-1000" />
          <Sparkles className="w-4 h-4 mr-2 text-primary-foreground animate-pulse" />
          View Roster
        </Button>
      </div>
    </div>
  </Card>
);

export default function Leagues() {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [leagueRows, setLeagueRows] = useState<LeagueDetail[]>([]);

  useEffect(() => {
    if (!isLoggedIn) return;
    setLoading(true);
    apiGet<{ data: { id: number }[] }>("/leagues", { limit: 20 })
      .then(async (payload) => {
        const detailRows = await Promise.all(
          payload.data.map((row) => apiGet<LeagueDetail>(`/leagues/${row.id}`))
        );
        setLeagueRows(detailRows);
      })
      .catch(() => setLeagueRows([]))
      .finally(() => setLoading(false));
  }, [isLoggedIn]);

  const handleStartDraft = (leagueId: string) => {
    navigate(`/league/${leagueId}`);
  };

  const leagues = leagueRows.length
    ? leagueRows.map((league) => ({
        id: String(league.id),
        name: league.name,
        week: league.status === "pre_draft" ? "Pre-Draft" : "Week 1",
        teams: league.max_teams,
        icon: Trophy,
        color: "bg-gradient-to-br from-primary to-blue-600",
        standings: [
          { rank: 1, initials: "SW", name: "Steel Warriors", record: "0-0", color: "bg-emerald-500" },
          { rank: 2, initials: "SS", name: "Steel Spartans", record: "0-0", color: "bg-amber-500" },
          { rank: 3, initials: "BP", name: "Bay Pirates", record: "0-0", color: "bg-blue-400" },
        ],
      }))
    : [];

  return (
    <div className="max-w-6xl mx-auto space-y-12 animate-in fade-in duration-1000 relative z-10 pb-20">
      {/* Header Section */}
      <div className="space-y-6 pt-12 relative">
        <div className="flex items-center justify-between">
          <h1 className="text-6xl font-black tracking-tight text-foreground uppercase italic bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-transparent">
            Leagues
          </h1>
          {isLoggedIn && (
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                className="border-primary/30 text-primary text-[10px] font-black uppercase tracking-widest rounded-2xl h-12 px-8 hover:bg-primary/10 transition-all"
                onClick={() => navigate("/leagues/create")}
              >
                Create League +
              </Button>
              <Button
                variant="outline"
                className="border-emerald-500/30 text-emerald-400 text-[10px] font-black uppercase tracking-widest rounded-2xl h-12 px-8 hover:bg-emerald-500/10 transition-all"
                onClick={() => navigate("/leagues/join")}
              >
                Join League
              </Button>
            </div>
          )}
        </div>
        <p className="text-muted-foreground text-xl font-medium max-w-2xl leading-relaxed">
          {isLoggedIn
            ? "Your active leagues are shown below. Manage your team and prepare for the upcoming matchups."
            : "Sign in to join a league and start competing with friends for the championship."}
        </p>
      </div>

      {isLoggedIn ? (
        <div className="space-y-8">
          {loading && (
            <div className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
              Loading leagues...
            </div>
          )}
          {leagues.map((league, i) => (
            <LeagueCard key={i} {...league} onStartDraft={handleStartDraft} />
          ))}
          {!loading && leagues.length === 0 && (
            <Card className="bg-card/40 backdrop-blur-md border-border/40 rounded-[3rem] p-12 space-y-8">
              <div className="space-y-3 text-center">
                <h3 className="text-2xl font-black uppercase text-foreground">No leagues yet</h3>
                <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground/60">
                  Use the top-right actions to create a league or join with an invite code.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-primary/15 flex items-center justify-center text-primary">
                    <CalendarDays className="w-5 h-5" />
                  </div>
                  <div className="space-y-2">
                    <h4 className="text-sm font-black uppercase tracking-[0.14em] text-foreground">Set the Draft</h4>
                    <p className="text-xs font-medium leading-6 text-muted-foreground/75">
                      Pick your draft date, league size, scoring, and roster settings before the season starts.
                    </p>
                  </div>
                </div>

                <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 flex items-center justify-center text-emerald-400">
                    <Send className="w-5 h-5" />
                  </div>
                  <div className="space-y-2">
                    <h4 className="text-sm font-black uppercase tracking-[0.14em] text-foreground">Invite Your League</h4>
                    <p className="text-xs font-medium leading-6 text-muted-foreground/75">
                      Share a secure invite code so every manager joins the right league before draft night.
                    </p>
                  </div>
                </div>

                <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-amber-500/15 flex items-center justify-center text-amber-300">
                    <BellRing className="w-5 h-5" />
                  </div>
                  <div className="space-y-2">
                    <h4 className="text-sm font-black uppercase tracking-[0.14em] text-foreground">Stay Ready</h4>
                    <p className="text-xs font-medium leading-6 text-muted-foreground/75">
                      The app will handle reminders, lineup alerts, and league activity once your first league is live.
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      ) : (
        <div className="space-y-12">
          {/* Guest Search Area */}
          <div className="flex flex-col md:flex-row gap-6 items-center justify-between bg-white/5 p-8 rounded-[2.5rem] border border-white/5 backdrop-blur-md">
             <div className="space-y-2">
                <h2 className="text-xl font-black italic uppercase tracking-tight text-foreground">Find a Public League</h2>
                <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">Discover new communities and start drafting</p>
             </div>
             <div className="relative w-full md:w-96 group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  placeholder="Enter league ID or name..."
                  className="pl-12 bg-white/5 border-white/10 rounded-2xl h-14 focus:ring-primary/20 focus:border-primary/40 transition-all text-xs font-bold tracking-wider uppercase"
                />
             </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <Card className="bg-card/40 backdrop-blur-md border-border/40 rounded-[3rem] p-12 text-center group hover:border-primary/20 transition-all duration-700 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
              <div className="space-y-6 relative z-10">
                <div className="w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center mx-auto text-primary group-hover:scale-110 transition-transform">
                  <PlusCircle className="w-10 h-10" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-black italic uppercase tracking-tight text-foreground">Create League</h3>
                  <p className="text-sm font-medium text-muted-foreground/60 max-w-[240px] mx-auto">Start your own custom league and invite your friends to draft.</p>
                </div>
                <Link to="/login" className="block">
                  <Button className="w-full h-14 bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_20px_rgba(var(--primary),0.2)]">
                     Create Now +
                  </Button>
                </Link>
              </div>
            </Card>

            <Card className="bg-card/40 backdrop-blur-md border-border/40 rounded-[3rem] p-12 text-center group hover:border-emerald-500/20 transition-all duration-700 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-emerald-500/10 transition-colors" />
              <div className="space-y-6 relative z-10">
                <div className="w-20 h-20 rounded-3xl bg-emerald-500/10 flex items-center justify-center mx-auto text-emerald-500 group-hover:scale-110 transition-transform">
                  <Users className="w-10 h-10" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-black italic uppercase tracking-tight text-foreground">Join League</h3>
                  <p className="text-sm font-medium text-muted-foreground/60 max-w-[240px] mx-auto">Join an existing league with a league ID and start scouting.</p>
                </div>
                <Link to="/login" className="block">
                  <Button className="w-full h-14 bg-emerald-500 text-white font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_20px_rgba(16,185,129,0.2)]">
                     Find League
                  </Button>
                </Link>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
