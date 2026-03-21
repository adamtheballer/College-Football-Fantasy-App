import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ChevronRight,
  TrendingUp,
  AlertCircle,
  Zap,
  Trophy,
  Users,
  Calendar,
  MessageSquare,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Star,
  ChevronLeft,
  Target,
  ArrowRightLeft,
  ShieldCheck
} from "lucide-react";

import { useAuth } from "@/hooks/use-auth";
import { Link } from "react-router-dom";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselPrevious,
  CarouselNext,
} from "@/components/ui/carousel";

const MyTeamItem = ({ name, league, record, pts, nextOpp, date, color }: any) => (
  <div className="flex items-center justify-between py-4 group cursor-pointer hover:bg-white/[0.05] px-5 rounded-[2rem] transition-all duration-500 border border-white/10 hover:border-primary/20 relative overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-r from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
    <div className="flex items-center gap-4 relative z-10">
      <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center text-sm font-black text-white shadow-2xl transition-transform group-hover:scale-110 duration-500", color)}>
        {name.split(" ").map((n: string) => n[0]).join("")}
      </div>
      <div className="space-y-1">
        <h4 className="text-[14px] font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors leading-none">{name}</h4>
        <p className="text-[9px] font-black tracking-[0.2em] text-muted-foreground/30 uppercase group-hover:text-muted-foreground/60 transition-colors">{league}</p>
      </div>
    </div>
    <div className="text-right flex items-center gap-6 relative z-10">
      <div className="text-right">
        <p className="text-base font-black italic text-foreground leading-none tracking-tighter group-hover:text-primary transition-colors">{record}</p>
        <p className="text-[9px] font-black tracking-widest text-muted-foreground/30 uppercase mt-1">{pts} pts</p>
      </div>
      <div className="text-right border-l border-white/5 pl-6 hidden md:block">
        <p className="text-[10px] font-black tracking-[0.2em] text-primary uppercase drop-shadow-[0_0_8px_rgba(var(--primary),0.4)]">Next: {nextOpp}</p>
        <p className="text-[9px] font-medium text-muted-foreground/40 mt-1">{date}</p>
      </div>
      <div className="w-8 h-8 rounded-full flex items-center justify-center bg-white/5 group-hover:bg-primary/20 transition-all duration-500 group-hover:scale-110">
        <ChevronRight className="w-4 h-4 text-muted-foreground/20 group-hover:text-primary transition-all" />
      </div>
    </div>
  </div>
);

const NewsItem = ({ player, team, news, time, type }: any) => (
  <div className="flex gap-4 p-5 group cursor-pointer bg-white/5 hover:bg-white/[0.08] rounded-[2rem] transition-all duration-500 border border-white/10 hover:border-primary/20 relative overflow-hidden">
    <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 blur-2xl rounded-full -mr-12 -mt-12 group-hover:bg-primary/10 transition-colors" />
    <div className={cn(
      "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-2xl transition-transform group-hover:scale-110 duration-500 relative z-10",
      type === 'injury' ? "bg-gradient-to-br from-red-500/20 to-red-600/40 text-red-500 border border-red-500/20" : "bg-gradient-to-br from-primary/20 to-blue-600/40 text-primary border border-primary/20"
    )}>
      {type === 'injury' ? <AlertCircle className="w-5 h-5" /> : <Zap className="w-5 h-5" />}
    </div>
    <div className="space-y-1 relative z-10 flex-1 min-w-0">
      <div className="flex items-center justify-between">
        <h4 className="text-[11px] font-black italic uppercase tracking-widest text-foreground group-hover:text-primary transition-colors truncate">
          {player} <span className="text-muted-foreground/30 font-bold not-italic ml-1">• {team}</span>
        </h4>
        <span className="text-[9px] font-black text-muted-foreground/40 uppercase bg-white/5 px-2 py-0.5 rounded-full shrink-0 ml-2">{time}</span>
      </div>
      <p className="text-[12px] font-medium text-muted-foreground/80 leading-snug group-hover:text-foreground transition-colors line-clamp-2">
        {news}
      </p>
    </div>
  </div>
);

const ActivityItem = ({ user, action, target, time }: any) => (
  <div className="flex items-center justify-between py-3 group hover:bg-white/[0.05] px-4 rounded-2xl transition-all border border-transparent hover:border-white/5">
    <div className="flex items-center gap-4">
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-secondary/80 to-secondary flex items-center justify-center text-[11px] font-black text-primary border border-primary/10 group-hover:border-primary/40 transition-all duration-300 shadow-xl">
        {user[0]}
      </div>
      <div className="text-[11px] font-medium text-muted-foreground group-hover:text-foreground transition-colors truncate max-w-[180px]">
        <span className="text-foreground font-black italic uppercase group-hover:text-primary transition-colors">{user}</span> {action} <span className="text-primary font-black italic uppercase drop-shadow-[0_0_8px_rgba(var(--primary),0.3)]">{target}</span>
      </div>
    </div>
    <span className="text-[9px] font-black text-muted-foreground/20 uppercase group-hover:text-muted-foreground/40 transition-colors shrink-0">{time}</span>
  </div>
);

const StatCard = ({ label, value, trend, icon: Icon, color }: any) => (
  <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[2.5rem] overflow-hidden group hover:border-primary/50 transition-all duration-500 p-8 relative">
    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
    <div className="flex items-center justify-between mb-6 relative z-10">
      <div className={cn("p-4 rounded-2xl shadow-2xl transition-transform group-hover:scale-110 duration-500", color)}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div className={cn("flex items-center gap-1 text-[10px] font-black uppercase py-1 px-3 rounded-full bg-white/5 border border-white/5", trend.startsWith('+') ? "text-emerald-400" : "text-red-400")}>
        {trend.startsWith('+') ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
        {trend}
      </div>
    </div>
    <div className="space-y-2 relative z-10">
      <h3 className="text-4xl font-black italic text-foreground tracking-tighter group-hover:text-primary transition-colors">{value}</h3>
      <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground uppercase opacity-40 group-hover:opacity-100 transition-opacity">{label}</p>
    </div>
  </Card>
);

export default function Index() {
  const { isLoggedIn, user } = useAuth();

  return (
    <div className="max-w-7xl mx-auto space-y-12 animate-in fade-in duration-1000 relative z-10 pb-32">
      {/* Hero Section */}
      <div className="space-y-8 pt-16 relative border-b border-white/5 pb-16">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-4">
             <div className="flex items-center gap-3">
                <div className="h-[2px] w-12 bg-gradient-to-r from-primary to-blue-400 shadow-[0_0_20px_rgba(var(--primary),0.8)]" />
                <span className="text-[10px] font-black tracking-[0.5em] text-primary uppercase drop-shadow-[0_0_10px_rgba(var(--primary),0.5)]">
                  {isLoggedIn ? "Dashboard Overview" : "Fantasy Scouting Network"}
                </span>
             </div>
             <h1 className="text-8xl font-black tracking-tighter text-foreground uppercase italic bg-gradient-to-br from-white via-primary to-blue-600 bg-clip-text text-transparent leading-[0.9] drop-shadow-2xl">
               College Football <br />
               <span className="text-white">Fantasy</span>
             </h1>
          </div>
          {!isLoggedIn && (
            <Button asChild className="h-16 px-10 rounded-2xl bg-primary text-primary-foreground font-black tracking-[0.2em] text-xs uppercase shadow-[0_15px_30px_rgba(var(--primary),0.3)] hover:scale-105 transition-all">
              <Link to="/login">
                Get Started Now
              </Link>
            </Button>
          )}
        </div>
        <p className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-blue-400 to-emerald-400 italic font-black uppercase tracking-[0.4em] text-3xl max-w-3xl leading-none py-2">
          MANAGE. TRACK. DOMINATE.
        </p>
      </div>

      {/* Reorganized Command Center Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {/* Quick Stats Carousel - Now a full width banner item above the grid */}
        <div className="md:col-span-2 lg:col-span-3 group relative">
          <Carousel
            opts={{
              align: "start",
              loop: true,
              dragFree: true,
            }}
            className="w-full"
          >
            <CarouselContent className="-ml-6">
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Season Points"
                  value={isLoggedIn ? "0.0" : "--"}
                  trend="0.0%"
                  icon={Trophy}
                  color="bg-gradient-to-br from-primary to-blue-600 shadow-primary/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Active Leagues"
                  value={isLoggedIn ? "01" : "00"}
                  trend={isLoggedIn ? "New" : "None"}
                  icon={Users}
                  color="bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Player Efficiency"
                  value={isLoggedIn ? "0.0%" : "--"}
                  trend="0.0%"
                  icon={Activity}
                  color="bg-gradient-to-br from-amber-500 to-orange-600 shadow-amber-500/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Global Rank"
                  value="N/A"
                  trend="-"
                  icon={Star}
                  color="bg-gradient-to-br from-purple-500 to-indigo-600 shadow-purple-500/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Draft Picks"
                  value={isLoggedIn ? "06" : "--"}
                  trend="Upcoming"
                  icon={Target}
                  color="bg-gradient-to-br from-rose-500 to-red-600 shadow-rose-500/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Trade Offers"
                  value={isLoggedIn ? "02" : "00"}
                  trend="New"
                  icon={ArrowRightLeft}
                  color="bg-gradient-to-br from-cyan-500 to-blue-600 shadow-cyan-500/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Scouting Score"
                  value={isLoggedIn ? "94.2" : "--"}
                  trend="+2.4"
                  icon={Zap}
                  color="bg-gradient-to-br from-yellow-400 to-orange-500 shadow-yellow-500/30"
                />
              </CarouselItem>
              <CarouselItem className="pl-6 basis-full sm:basis-1/2 lg:basis-1/4">
                <StatCard
                  label="Waiver Priority"
                  value={isLoggedIn ? "#04" : "--"}
                  trend="Stable"
                  icon={ShieldCheck}
                  color="bg-gradient-to-br from-emerald-400 to-teal-500 shadow-emerald-500/30"
                />
              </CarouselItem>
            </CarouselContent>
            <div className="absolute top-1/2 -translate-y-1/2 left-[-20px] z-20">
              <CarouselPrevious className="h-10 w-10 bg-black/40 border-white/10 hover:bg-primary/20 hover:text-white transition-all opacity-0 group-hover:opacity-100" />
            </div>
            <div className="absolute top-1/2 -translate-y-1/2 right-[-20px] z-20">
              <CarouselNext className="h-10 w-10 bg-black/40 border-white/10 hover:bg-primary/20 hover:text-white transition-all opacity-0 group-hover:opacity-100" />
            </div>
          </Carousel>
        </div>

        {/* My Teams - Bento Large Card */}
        <div className="md:col-span-2 lg:col-span-2">
           <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[3rem] h-full overflow-hidden shadow-2xl group transition-all duration-700 hover:border-primary/20">
              <CardHeader className="px-10 pt-10 border-b border-border/40 bg-gradient-to-br from-primary/5 to-transparent flex flex-row items-center justify-between space-y-0">
                <div className="space-y-1">
                  <CardTitle className="text-[10px] font-black tracking-[0.4em] text-primary uppercase">My Teams</CardTitle>
                  <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-widest">Active roster summary</p>
                </div>
                <div className="p-3 rounded-2xl bg-primary/10 text-primary group-hover:scale-110 transition-transform cursor-pointer">
                  <ChevronRight className="w-5 h-5" />
                </div>
              </CardHeader>
              <CardContent className="p-6">
                {isLoggedIn ? (
                  <>
                    <div className="space-y-1 divide-y divide-white/10 border-t border-white/10">
                      <MyTeamItem
                        name="Mountain Falcons"
                        league="Saturday League"
                        record="0-0"
                        pts="0.0"
                        nextOpp="TBD"
                        date="Draft Scheduled"
                        color="bg-gradient-to-br from-red-500 to-red-600 shadow-[0_5px_20px_rgba(239,68,68,0.3)]"
                      />
                    </div>
                    <div className="mt-6 px-4">
                      <Button asChild variant="ghost" className="w-full h-14 rounded-3xl border border-border/40 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground hover:text-primary hover:bg-primary/5 transition-all">
                        <Link to="/leagues">
                          Manage League
                        </Link>
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="py-12 text-center space-y-6">
                    <div className="w-16 h-16 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto opacity-40">
                       <Zap className="w-8 h-8 text-primary" />
                    </div>
                    <div className="space-y-2">
                       <h4 className="text-xl font-black italic uppercase text-foreground">No active teams</h4>
                       <p className="text-[11px] font-medium text-muted-foreground/40 uppercase tracking-widest max-w-[200px] mx-auto">Sign in to create your first team and start drafting players</p>
                    </div>
                    <Button asChild variant="outline" className="border-primary/20 text-primary text-[9px] font-black uppercase tracking-widest h-10 px-8 rounded-xl hover:bg-primary/5">
                       <Link to="/login" className="block">
                          Login to Sync
                       </Link>
                    </Button>
                  </div>
                )}
              </CardContent>
           </Card>
        </div>

        {/* Headlines - Bento Tall Card */}
        <div className="lg:row-span-2">
           <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3.5rem] h-full overflow-hidden shadow-2xl group transition-all duration-700 hover:border-primary/20 relative">
              <CardHeader className="px-8 pt-8 border-b border-white/5 bg-gradient-to-br from-primary/10 via-transparent to-transparent flex flex-row items-center justify-between space-y-0">
                <div className="space-y-1">
                  <CardTitle className="text-[10px] font-black tracking-[0.4em] text-primary uppercase">Headlines</CardTitle>
                  <p className="text-[10px] font-medium text-muted-foreground/40 uppercase tracking-widest truncate max-w-[120px]">Latest updates & news</p>
                </div>
                <div className="p-2 rounded-xl bg-primary/10 text-primary group-hover:scale-110 transition-transform">
                   <ChevronRight className="w-4 h-4" />
                </div>
              </CardHeader>
              <CardContent className="p-5 space-y-4">
                <NewsItem
                  player="D. Bowers"
                  team="WIS"
                  type="injury"
                  time="2H AGO"
                  news="Questionable for Week 9 with minor ankle sprain. Expected to participate in partial practice Friday."
                />
                <NewsItem
                  player="J. Daniels"
                  team="LSU"
                  type="update"
                  time="4H AGO"
                  news="Projected to start as QB1 against Georgia. Coaching staff confirms full readiness for the matchup."
                />
                <NewsItem
                  player="M. Harrison"
                  team="OSU"
                  type="update"
                  time="1D AGO"
                  news="Leads the conference in receiving yards through 8 weeks. Fantasy value continues to soar."
                />
                <NewsItem
                  player="C. Williams"
                  team="USC"
                  type="injury"
                  time="2D AGO"
                  news="Returns to full practice after brief absence. Cleared for Saturday night clash."
                />
              </CardContent>
           </Card>
        </div>

        {/* Schedule - Bento Large Card */}
        <div className="md:col-span-2 lg:col-span-2">
           <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3.5rem] overflow-hidden shadow-2xl group transition-all duration-700 hover:border-amber-500/40 relative">
              <CardHeader className="px-8 py-4 border-b border-white/5 bg-gradient-to-br from-amber-500/10 via-transparent to-transparent flex flex-row items-center justify-between space-y-0">
                 <CardTitle className="text-[10px] font-black tracking-[0.5em] text-amber-400 uppercase">Schedule</CardTitle>
                 <Calendar className="w-4 h-4 text-amber-400" />
              </CardHeader>
              <CardContent className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="flex items-center gap-4 p-4 rounded-3xl bg-white/5 border border-white/5 group hover:border-amber-500/40 transition-all cursor-pointer relative overflow-hidden">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex flex-col items-center justify-center text-amber-500 shadow-xl border border-amber-500/10 group-hover:scale-110 transition-transform duration-500 relative z-10">
                      <span className="text-[8px] font-black uppercase tracking-tighter">Sat</span>
                      <span className="text-sm font-black italic">26</span>
                    </div>
                    <div className="space-y-0.5 relative z-10">
                      <h4 className="text-[12px] font-black italic uppercase tracking-tight text-foreground group-hover:text-amber-400 transition-colors">Waiver</h4>
                      <p className="text-[9px] font-bold text-muted-foreground/40 uppercase tracking-[0.1em]">11:59 PM EST</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 p-4 rounded-3xl bg-white/5 border border-white/5 group hover:border-primary/40 transition-all cursor-pointer relative overflow-hidden">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex flex-col items-center justify-center text-primary shadow-xl border border-primary/10 group-hover:scale-110 transition-transform duration-500 relative z-10">
                      <span className="text-[8px] font-black uppercase tracking-tighter">Sat</span>
                      <span className="text-sm font-black italic">26</span>
                    </div>
                    <div className="space-y-0.5 relative z-10">
                      <h4 className="text-[12px] font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">Kickoff</h4>
                      <p className="text-[9px] font-bold text-muted-foreground/40 uppercase tracking-[0.1em]">WIS vs ALA</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 p-4 rounded-3xl bg-white/5 border border-white/5 group hover:border-emerald-500/40 transition-all cursor-pointer relative overflow-hidden">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex flex-col items-center justify-center text-emerald-500 shadow-xl border border-emerald-500/10 group-hover:scale-110 transition-transform duration-500 relative z-10">
                      <span className="text-[8px] font-black uppercase tracking-tighter">Tue</span>
                      <span className="text-sm font-black italic">29</span>
                    </div>
                    <div className="space-y-0.5 relative z-10">
                      <h4 className="text-[12px] font-black italic uppercase tracking-tight text-foreground group-hover:text-emerald-400 transition-colors">Recap</h4>
                      <p className="text-[9px] font-bold text-muted-foreground/40 uppercase tracking-[0.1em]">Finalized</p>
                    </div>
                  </div>
                </div>
              </CardContent>
           </Card>
        </div>

        {/* Activity - Bento Square Card */}
        <div className="md:col-span-2 lg:col-span-2">
           <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3.5rem] overflow-hidden shadow-2xl group transition-all duration-700 hover:border-emerald-500/40 relative">
              <CardHeader className="px-8 py-4 border-b border-white/5 bg-gradient-to-br from-emerald-500/10 via-transparent to-transparent flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-[10px] font-black tracking-[0.5em] text-emerald-400 uppercase drop-shadow-[0_0_10px_rgba(52,211,153,0.3)]">Recent Activity</CardTitle>
                <Activity className="w-4 h-4 text-emerald-400" />
              </CardHeader>
              <CardContent className="p-4 relative z-10">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1">
                  <ActivityItem user="Mike R." action="added" target="D. Travis" time="15m ago" />
                  <ActivityItem user="Sarah J." action="dropped" target="R. Wilson" time="42m ago" />
                  <ActivityItem user="John D." action="traded" target="K. Allen" time="2h ago" />
                  <ActivityItem user="Alex P." action="added" target="T. Etienne" time="5h ago" />
                </div>
              </CardContent>
           </Card>
        </div>

        {/* Global Chat - Bento Square Card */}
        <div className="md:col-span-2 lg:col-span-1">
           <div className="p-8 rounded-[3.5rem] h-full bg-gradient-to-br from-primary/10 to-blue-600/10 border border-primary/20 relative overflow-hidden group hover:scale-[1.02] transition-all duration-500 cursor-pointer flex flex-col justify-center min-h-[160px]">
              <div className="absolute top-[-20%] right-[-20%] w-40 h-40 bg-primary/20 blur-[50px] rounded-full" />
              <div className="relative z-10 space-y-4">
                 <div className="flex items-center gap-3">
                   <MessageSquare className="w-5 h-5 text-primary shadow-[0_0_15px_rgba(var(--primary),0.5)]" />
                   <h3 className="text-sm font-black italic uppercase tracking-widest text-foreground">Global Chat</h3>
                 </div>
                 <p className="text-[11px] font-medium text-muted-foreground/80 leading-relaxed">
                   Join the discussion with <span className="text-primary font-black italic uppercase">1,248 active scouts</span>.
                 </p>
                 <div className="pt-2">
                   <Button className="w-full bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase h-10 rounded-2xl shadow-[0_10px_20px_rgba(var(--primary),0.2)]">
                     Enter Lobby
                   </Button>
                 </div>
              </div>
           </div>
        </div>
      </div>

    </div>
  );
}
