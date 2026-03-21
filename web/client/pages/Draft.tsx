import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, Clock3, Loader2, ShieldAlert, Trophy, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDraftPick, useDraftRoom } from "@/hooks/use-draft";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { usePlayers } from "@/hooks/use-players";
import { ApiError } from "@/lib/api";

const formatApiError = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Sign in again to enter the draft room.";
    if (error.status === 403) return "You do not have access to this draft room.";
    if (error.status === 404) return "This draft room does not exist yet.";
    return error.message || fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

const formatStatus = (value: string) => value.replace(/_/g, " ");

export default function Draft() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");

  const parsedLeagueId =
    leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;

  const { data: league } = useLeagueDetail(parsedLeagueId);
  const {
    data: draftRoom,
    isLoading: draftRoomLoading,
    error: draftRoomError,
  } = useDraftRoom(parsedLeagueId);
  const { data: playersPayload, isLoading: playersLoading } = usePlayers({ limit: 250 });
  const pickMutation = useDraftPick(parsedLeagueId);

  const draftedIds = useMemo(
    () => new Set(draftRoom?.picks.map((pick) => pick.player_id) ?? []),
    [draftRoom?.picks]
  );

  const availablePlayers = useMemo(() => {
    const basePlayers = playersPayload?.data ?? [];
    const normalizedSearch = searchQuery.trim().toLowerCase();
    return basePlayers
      .filter((player) => !draftedIds.has(player.id))
      .filter((player) => {
        if (!normalizedSearch) return true;
        return (
          player.name.toLowerCase().includes(normalizedSearch) ||
          player.school.toLowerCase().includes(normalizedSearch) ||
          player.pos.toLowerCase().includes(normalizedSearch)
        );
      })
      .sort((left, right) => {
        if (left.pos !== right.pos) {
          return left.pos.localeCompare(right.pos);
        }
        return left.name.localeCompare(right.name);
      });
  }, [draftedIds, playersPayload?.data, searchQuery]);

  const myPicks = useMemo(
    () =>
      draftRoom?.user_team_id
        ? draftRoom.picks.filter((pick) => pick.team_id === draftRoom.user_team_id)
        : [],
    [draftRoom]
  );

  const totalRosterSlots = useMemo(() => {
    if (!draftRoom) return 0;
    return Object.values(draftRoom.roster_slots).reduce(
      (total, count) => total + Number(count || 0),
      0
    );
  }, [draftRoom]);

  const makePick = async (playerId: number) => {
    try {
      await pickMutation.mutateAsync(playerId);
    } catch {
      // Error is rendered inline below.
    }
  };

  if (!parsedLeagueId) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardContent className="p-12 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              Invalid league ID.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (draftRoomLoading) {
    return (
      <div className="max-w-5xl mx-auto py-16">
        <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
          <CardContent className="p-12 flex items-center justify-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/70">
              Loading live draft room...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!draftRoom || draftRoomError) {
    return (
      <div className="max-w-5xl mx-auto py-16">
        <Card className="bg-card/40 border border-red-400/20 rounded-[2.5rem]">
          <CardContent className="p-12 text-center space-y-4">
            <ShieldAlert className="mx-auto h-8 w-8 text-red-300" />
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              {formatApiError(draftRoomError, "Unable to load draft room.")}
            </p>
            <Button
              variant="outline"
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate(`/league/${parsedLeagueId}/lobby`)}
            >
              Back to Draft Lobby
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const leagueName = league?.name || `League ${draftRoom.league_id}`;
  const currentTeamLabel = draftRoom.current_team_name || "Draft complete";

  return (
    <div className="max-w-7xl mx-auto py-12 space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">
            Live Draft Room
          </p>
          <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground">
            {leagueName}
          </h1>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Draft status: {formatStatus(draftRoom.status)}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="outline" className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
            <Link to={`/league/${parsedLeagueId}/lobby`}>Back to Lobby</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
            <Link to={`/league/${parsedLeagueId}`}>League Hub</Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_0.9fr] gap-6">
        <div className="space-y-6">
          <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                Draft State
              </CardTitle>
            </CardHeader>
            <CardContent className="p-8 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Current Pick
                </p>
                <p className="text-3xl font-black italic text-foreground">
                  {draftRoom.current_pick}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  On The Clock
                </p>
                <p className="text-lg font-black uppercase text-foreground">{currentTeamLabel}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Pick Timer
                </p>
                <p className="text-3xl font-black italic text-foreground">
                  {draftRoom.pick_timer_seconds}s
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                Available Players
              </CardTitle>
            </CardHeader>
            <CardContent className="p-8 space-y-6">
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search players, schools, or positions..."
                className="h-12 rounded-2xl bg-white/5 border-white/10"
              />

              {pickMutation.error && (
                <div className="rounded-2xl border border-red-400/20 bg-red-500/5 p-4 text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                  {formatApiError(pickMutation.error, "Unable to save draft pick.")}
                </div>
              )}

              <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.03]">
                <div className="grid grid-cols-[minmax(0,1fr)_120px_120px_140px] gap-4 border-b border-white/10 px-6 py-4 text-[9px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                  <span>Player</span>
                  <span>Position</span>
                  <span>School</span>
                  <span>Action</span>
                </div>
                {playersLoading ? (
                  <div className="px-6 py-10 text-center text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                    Loading players...
                  </div>
                ) : availablePlayers.length === 0 ? (
                  <div className="px-6 py-10 text-center text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                    No available players match this search.
                  </div>
                ) : (
                  availablePlayers.slice(0, 80).map((player) => (
                    <div
                      key={player.id}
                      className="grid grid-cols-[minmax(0,1fr)_120px_120px_140px] gap-4 border-b border-white/5 px-6 py-4 last:border-b-0"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-black uppercase tracking-tight text-foreground">
                          {player.name}
                        </p>
                      </div>
                      <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                        {player.pos}
                      </span>
                      <span className="truncate text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                        {player.school}
                      </span>
                      <Button
                        type="button"
                        className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]"
                        disabled={!draftRoom.can_make_pick || pickMutation.isPending}
                        onClick={() => makePick(player.id)}
                      >
                        {pickMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save Pick"}
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                <Users className="h-4 w-4" />
                Teams
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-3">
              {draftRoom.teams.map((team) => {
                const isCurrent = team.id === draftRoom.current_team_id;
                const isUserTeam = team.id === draftRoom.user_team_id;
                return (
                  <div
                    key={team.id}
                    className={`rounded-2xl border p-4 ${
                      isCurrent
                        ? "border-primary/40 bg-primary/10"
                        : isUserTeam
                          ? "border-emerald-500/30 bg-emerald-500/10"
                          : "border-white/10 bg-white/5"
                    }`}
                  >
                    <p className="text-sm font-black uppercase tracking-tight text-foreground">
                      {team.name}
                    </p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                      {team.owner_name || "Unassigned owner"}
                    </p>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                <Trophy className="h-4 w-4" />
                Your Saved Picks
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                  Saved
                </p>
                <p className="mt-2 text-3xl font-black italic text-foreground">
                  {myPicks.length}/{totalRosterSlots}
                </p>
              </div>
              {myPicks.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-5 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    No picks saved yet
                  </p>
                </div>
              ) : (
                myPicks.map((pick) => (
                  <div key={pick.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-sm font-black uppercase tracking-tight text-foreground">
                      {pick.player_name}
                    </p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                      {pick.player_position} • {pick.player_school} • Pick {pick.overall_pick}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                <Clock3 className="h-4 w-4" />
                Recent Picks
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-3">
              {draftRoom.picks.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-5 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    Draft has not started yet
                  </p>
                </div>
              ) : (
                [...draftRoom.picks]
                  .slice(-8)
                  .reverse()
                  .map((pick) => (
                    <div key={pick.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-sm font-black uppercase tracking-tight text-foreground">
                        {pick.player_name}
                      </p>
                      <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                        {pick.team_name} • Pick {pick.overall_pick}
                      </p>
                    </div>
                  ))
              )}
            </CardContent>
          </Card>

          {!draftRoom.can_make_pick && (
            <div className="rounded-[2rem] border border-amber-500/20 bg-amber-500/10 p-5 flex gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-300 shrink-0" />
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-100/85">
                This room is live and persisted, but you can only save picks when it is your team&apos;s turn or you are the commissioner.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
