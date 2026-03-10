import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trophy, ChevronRight, ClipboardList, Users, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api";
import { LeagueDetail } from "@/types/league";

const LeagueRosterCard = ({ id, name, teamName, record, color, icon: Icon }: any) => (
  <Link to={`/league/${id}`}>
    <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] overflow-hidden group hover:border-primary/40 transition-all duration-500 hover:scale-[1.02] cursor-pointer">
      <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
      <CardContent className="p-10 relative z-10 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div className={cn("w-20 h-20 rounded-[2rem] flex items-center justify-center shadow-2xl transition-transform group-hover:scale-110 duration-500", color)}>
            <Icon className="w-10 h-10 text-white" />
          </div>
          <div className="space-y-2">
            <h3 className="text-3xl font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">{name}</h3>
            <div className="flex items-center gap-4">
               <span className="text-[10px] font-black tracking-[0.3em] text-primary uppercase drop-shadow-[0_0_10px_rgba(var(--primary),0.5)]">{teamName}</span>
               <div className="w-1 h-1 rounded-full bg-white/10" />
               <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase">{record} Record</span>
            </div>
          </div>
        </div>
        <div className="w-16 h-16 rounded-[1.5rem] bg-white/5 border border-white/10 flex items-center justify-center group-hover:bg-primary/20 group-hover:border-primary/40 transition-all duration-500">
          <ArrowRight className="w-6 h-6 text-muted-foreground/20 group-hover:text-primary transition-all" />
        </div>
      </CardContent>
    </Card>
  </Link>
);

export default function Rosters() {
  const { isLoggedIn } = useAuth();
  const [leagueRows, setLeagueRows] = useState<LeagueDetail[]>([]);
  const [loading, setLoading] = useState(false);

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

  const myLeagues = leagueRows.map((league, idx) => ({
    id: String(league.id),
    name: league.name,
    teamName: `Team ${idx + 1}`,
    record: "0-0",
    color: idx % 2 === 0 ? "bg-gradient-to-br from-primary to-blue-600" : "bg-gradient-to-br from-emerald-500 to-teal-600",
    icon: idx % 2 === 0 ? Trophy : ClipboardList,
  }));

  return (
    <div className="max-w-5xl mx-auto space-y-12 animate-in fade-in duration-1000 py-12">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="h-[2px] w-12 bg-gradient-to-r from-primary to-blue-400" />
          <span className="text-[10px] font-black tracking-[0.5em] text-primary uppercase drop-shadow-[0_0_10px_rgba(var(--primary),0.5)]">Roster Selection</span>
        </div>
        <h1 className="text-7xl font-black italic tracking-tighter text-foreground uppercase bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-transparent">
          My Rosters
        </h1>
        <p className="text-muted-foreground text-xl font-medium max-w-2xl leading-relaxed">
          Select a league to manage your active roster and view current matchups.
        </p>
      </div>

      {!isLoggedIn ? (
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] p-20 text-center space-y-8">
           <div className="w-24 h-24 rounded-[2rem] bg-primary/10 flex items-center justify-center mx-auto">
              <Users className="w-12 h-12 text-primary" />
           </div>
           <div className="space-y-4">
              <h2 className="text-3xl font-black italic uppercase text-foreground">Sign in Required</h2>
              <p className="text-muted-foreground max-w-sm mx-auto uppercase tracking-widest text-xs font-bold">You must be logged in to view your team rosters and league details.</p>
           </div>
           <Link to="/login" className="block">
              <Button className="h-14 px-12 bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_30px_rgba(var(--primary),0.3)] hover:scale-105 transition-all">
                 Login to Sync
              </Button>
           </Link>
        </Card>
      ) : loading ? (
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] p-20 text-center space-y-4">
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Loading leagues...</p>
        </Card>
      ) : myLeagues.length === 0 ? (
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 border-dashed rounded-[3rem] p-20 text-center space-y-8 group hover:border-primary/20 transition-all duration-700">
           <div className="relative mx-auto w-24 h-24">
              <div className="absolute inset-0 bg-primary/20 blur-3xl animate-pulse" />
              <div className="relative w-full h-full rounded-[2rem] bg-white/5 border border-white/10 flex items-center justify-center text-muted-foreground group-hover:text-primary transition-all duration-500">
                 <Trophy className="w-12 h-12" />
              </div>
           </div>
           <div className="space-y-4">
              <h2 className="text-3xl font-black italic uppercase text-foreground">No leagues joined yet</h2>
              <p className="text-muted-foreground max-w-sm mx-auto uppercase tracking-widest text-[10px] font-bold leading-loose">
                You haven't joined any leagues yet. Explore available leagues to start drafting your dream team.
              </p>
           </div>
           <Link to="/leagues" className="block">
              <Button className="h-14 px-12 bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_30px_rgba(var(--primary),0.2)] hover:scale-105 transition-all">
                 Browse Leagues
              </Button>
           </Link>
        </Card>
      ) : (
        <div className="space-y-6">
          {myLeagues.map((league) => (
            <LeagueRosterCard key={league.id} {...league} />
          ))}
        </div>
      )}

    </div>
  );
}
