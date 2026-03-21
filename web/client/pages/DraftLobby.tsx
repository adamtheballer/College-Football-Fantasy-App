import React, { useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Clock, Users, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLeagueDetail } from "@/hooks/use-leagues";

export default function DraftLobby() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const parsedLeagueId =
    leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;
  const { data: league, error, isLoading } = useLeagueDetail(parsedLeagueId);

  const draftTime = league?.draft?.draft_datetime_utc ? new Date(league.draft.draft_datetime_utc) : null;
  const countdown = useMemo(() => {
    if (!draftTime) return "--";
    const diff = draftTime.getTime() - Date.now();
    const hours = Math.max(0, Math.floor(diff / (1000 * 60 * 60)));
    const minutes = Math.max(0, Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)));
    return `${hours}h ${minutes}m`;
  }, [draftTime]);

  const canEnterDraft = useMemo(() => {
    if (!draftTime) return false;
    const diff = draftTime.getTime() - Date.now();
    return diff <= 15 * 60 * 1000;
  }, [draftTime]);

  const isFull = league ? league.members.length >= league.max_teams : false;
  const canEnter = canEnterDraft && isFull;

  if (!parsedLeagueId) {
    return (
      <div className="max-w-3xl mx-auto py-20 text-center">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12">
          <h1 className="text-3xl font-black uppercase text-red-400">Invalid league ID.</h1>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-20 text-center">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12">
          <h1 className="text-3xl font-black uppercase text-red-400">Unable to load league.</h1>
        </Card>
      </div>
    );
  }

  if (isLoading || !league) {
    return (
      <div className="max-w-3xl mx-auto py-20 text-center">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem] p-12">
          <p className="text-sm font-bold uppercase tracking-[0.2em] text-muted-foreground">Loading draft lobby...</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto py-12 space-y-10">
      <div className="space-y-3">
        <h1 className="text-6xl font-black italic uppercase text-foreground">{league.name}</h1>
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-[0.2em]">
          Draft Lobby • {league.members.length}/{league.max_teams} members
        </p>
      </div>

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="px-10 pt-10">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Draft Countdown</CardTitle>
        </CardHeader>
        <CardContent className="px-10 pb-10 space-y-6">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
              <Clock className="w-6 h-6 text-primary" />
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Starts In</p>
                <p className="text-2xl font-black text-foreground">{countdown}</p>
              </div>
            </div>
            <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
              <Users className="w-6 h-6 text-primary" />
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Draft Type</p>
                <p className="text-2xl font-black text-foreground uppercase">{league.draft?.draft_type || "Snake"}</p>
              </div>
            </div>
            <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
              <Zap className="w-6 h-6 text-primary" />
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Pick Timer</p>
                <p className="text-2xl font-black text-foreground">{league.draft?.pick_timer_seconds || 90}s</p>
              </div>
            </div>
          </div>

          <div className="space-y-2 text-sm font-bold uppercase tracking-[0.2em] text-muted-foreground">
            <p>Draft Order: Pending</p>
            <p>Timezone: {league.draft?.timezone}</p>
            <p>Draft Time: {draftTime?.toLocaleString()}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="px-10 pt-10">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Participants</CardTitle>
        </CardHeader>
        <CardContent className="px-10 pb-10 space-y-4">
          {!isFull && (
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-amber-400">
              Draft cannot start until {league.max_teams} teams join.
            </p>
          )}
          {league.members.map((member) => (
            <div key={member.id} className="flex items-center justify-between px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
              <span className="text-sm font-black uppercase tracking-[0.2em] text-foreground">User {member.user_id}</span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{member.role}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex items-center gap-4">
        <Button
          className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
          disabled={!canEnter}
          onClick={() => navigate(`/league/${league.id}`)}
        >
          Enter Draft Room
        </Button>
        <Button
          variant="outline"
          className="h-12 px-6 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
          onClick={() => navigate(`/league/${league.id}`)}
        >
          Back to League
        </Button>
      </div>
    </div>
  );
}
