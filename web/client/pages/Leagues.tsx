import { Link, useNavigate } from "react-router-dom";
import {
  Trophy,
  ChevronRight,
  CalendarDays,
  Send,
  BellRing,
  Lock,
  Globe2,
  Users,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagues } from "@/hooks/use-leagues";

const LeagueCard = ({
  id,
  name,
  status,
  teams,
  memberCount,
  draftLabel,
  isPrivate,
  draftStatus,
  onOpen,
  onOpenDraft,
}: {
  id: number;
  name: string;
  status: string;
  teams: number;
  memberCount: number;
  draftLabel: string;
  isPrivate: boolean;
  draftStatus: string;
  onOpen: (leagueId: number) => void;
  onOpenDraft: (leagueId: number, draftStatus: string) => void;
}) => (
  <Card className="bg-card/40 backdrop-blur-md border-border/60 rounded-[2.5rem] overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.3)] group hover:border-primary/40 transition-all duration-500 relative">
    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full -mr-16 -mt-16 group-hover:bg-primary/10 transition-colors" />
    <div className="flex flex-col md:flex-row relative z-10">
      <div className="flex-1 p-8 border-b md:border-b-0 md:border-r border-border/40 relative overflow-hidden">
        <div className="absolute -top-6 -left-6 w-24 h-24 blur-[40px] opacity-20 rounded-full bg-gradient-to-br from-primary to-blue-600" />
        <div className="relative z-10 flex flex-col h-full justify-between gap-6">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-2xl transition-transform group-hover:scale-110 duration-500 bg-gradient-to-br from-primary to-blue-600">
              <Trophy className="w-6 h-6 text-white" />
            </div>
            <div className="space-y-1">
              <h3 className="text-2xl font-black italic tracking-tight text-foreground uppercase group-hover:text-primary transition-colors">
                {name}
              </h3>
              <p className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase">
                {status.replace(/_/g, " ")} • {teams} teams
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/70">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2">
              <Users className="w-3 h-3 text-primary" />
              {memberCount}/{teams} members
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2">
              {isPrivate ? <Lock className="w-3 h-3 text-primary" /> : <Globe2 className="w-3 h-3 text-primary" />}
              {isPrivate ? "Private" : "Public"}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-[1.1] p-8 bg-white/5 border-b md:border-b-0 md:border-r border-border/40">
        <div className="space-y-6">
          <h4 className="text-[10px] font-black tracking-[0.3em] text-primary uppercase opacity-60">
            League snapshot
          </h4>
          <div className="space-y-4">
            <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
              <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">
                Draft
              </p>
              <p className="mt-2 text-sm font-bold text-foreground">{draftLabel}</p>
            </div>
            <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
              <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">
                League Context
              </p>
              <p className="mt-2 text-sm font-bold text-foreground">
                Open your league hub for roster, matchup, scoreboard, and settings.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="p-8 flex flex-col gap-4 items-center justify-center bg-gradient-to-br from-primary/5 to-transparent min-w-[240px]">
        <Button
          variant="outline"
          className="w-full border-white/5 bg-white/5 text-foreground font-black tracking-[0.2em] text-[10px] uppercase h-12 px-8 rounded-2xl hover:bg-white/10 transition-all duration-300"
          onClick={() => onOpen(id)}
        >
          League Hub
          <ChevronRight className="w-3 h-3 ml-2" />
        </Button>
        {(draftStatus === "draft_live" || draftStatus === "draft_scheduled") && (
          <Button
            variant="outline"
            className="w-full border-primary/30 bg-primary/10 text-primary font-black tracking-[0.2em] text-[10px] uppercase h-12 px-8 rounded-2xl hover:bg-primary/15 transition-all duration-300"
            onClick={() => onOpenDraft(id, draftStatus)}
          >
            {draftStatus === "draft_live" ? "Enter Draft Room" : "Open Draft Lobby"}
            <ChevronRight className="w-3 h-3 ml-2" />
          </Button>
        )}
      </div>
    </div>
  </Card>
);

export default function Leagues() {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const { setActiveLeagueId } = useActiveLeagueId();
  const { data: leagueRows = [], isLoading, isError } = useLeagues(20, isLoggedIn);

  return (
    <div className="max-w-6xl mx-auto space-y-12 animate-in fade-in duration-1000 relative z-10 pb-20">
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
            ? "Manage your active leagues, jump into drafts, and navigate to the right league context in one tap."
            : "Sign in to create or join a league and use the supported React experience."}
        </p>
      </div>

      {isLoggedIn ? (
        <div className="space-y-8">
          {isLoading && (
            <div className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
              Loading leagues...
            </div>
          )}
          {isError && (
            <Card className="bg-card/40 backdrop-blur-md border-border/40 rounded-[3rem] p-12 text-center">
              <p className="text-[11px] font-bold uppercase tracking-widest text-red-300">
                Unable to load leagues. Confirm the backend is running and your session is valid.
              </p>
            </Card>
          )}
          {leagueRows.map((league) => (
            <LeagueCard
              key={league.id}
              id={league.id}
              name={league.name}
              status={league.status}
              teams={league.max_teams}
              memberCount={league.members.length}
              draftLabel={
                league.draft?.draft_datetime_utc
                  ? new Date(league.draft.draft_datetime_utc).toLocaleString()
                  : "Draft not scheduled"
              }
              isPrivate={league.is_private}
              draftStatus={league.draft?.status || "none"}
              onOpen={(leagueId) => {
                setActiveLeagueId(leagueId);
                navigate(`/league/${leagueId}`);
              }}
              onOpenDraft={(leagueId, draftStatus) => {
                setActiveLeagueId(leagueId);
                if (draftStatus === "draft_live") {
                  navigate(`/league/${leagueId}/draft`);
                  return;
                }
                navigate(`/league/${leagueId}/lobby`);
              }}
            />
          ))}
          {!isLoading && !isError && leagueRows.length === 0 && (
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
                      Supported notifications, settings, and league metadata are now wired to the live backend.
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <Card className="bg-card/40 backdrop-blur-md border-border/40 rounded-[3rem] p-12 text-center group hover:border-primary/20 transition-all duration-700 relative overflow-hidden">
            <div className="space-y-6 relative z-10">
              <div className="w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center mx-auto text-primary group-hover:scale-110 transition-transform">
                <Trophy className="w-10 h-10" />
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-black italic uppercase tracking-tight text-foreground">Create League</h3>
                <p className="text-sm font-medium text-muted-foreground/60 max-w-[240px] mx-auto">
                  Start your own custom league and invite your friends to draft.
                </p>
              </div>
              <Button asChild className="w-full h-14 bg-primary text-primary-foreground font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_20px_rgba(var(--primary),0.2)]">
                <Link to="/login" className="block">
                  Sign In to Create
                </Link>
              </Button>
            </div>
          </Card>

          <Card className="bg-card/40 backdrop-blur-md border-border/40 rounded-[3rem] p-12 text-center group hover:border-emerald-500/20 transition-all duration-700 relative overflow-hidden">
            <div className="space-y-6 relative z-10">
              <div className="w-20 h-20 rounded-3xl bg-emerald-500/10 flex items-center justify-center mx-auto text-emerald-500 group-hover:scale-110 transition-transform">
                <Users className="w-10 h-10" />
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-black italic uppercase tracking-tight text-foreground">Join League</h3>
                <p className="text-sm font-medium text-muted-foreground/60 max-w-[240px] mx-auto">
                  Join an existing league with an invite code and start scouting.
                </p>
              </div>
              <Button asChild className="w-full h-14 bg-emerald-500 text-white font-black tracking-[0.2em] text-[10px] uppercase rounded-2xl shadow-[0_10px_20px_rgba(16,185,129,0.2)]">
                <Link to="/login" className="block">
                  Sign In to Join
                </Link>
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
