import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Clock3, Loader2, Lock, UserRound, Wifi, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMockDraftRealtime, useMockDraftRoom } from "@/hooks/use-mock-draft";

export default function MockDraftRoom() {
  const { mockDraftId } = useParams();
  const navigate = useNavigate();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: room, isLoading, error } = useMockDraftRoom(parsedMockDraftId, Boolean(parsedMockDraftId));
  useMockDraftRealtime(parsedMockDraftId, Boolean(parsedMockDraftId));
  const [displaySecondsRemaining, setDisplaySecondsRemaining] = useState<number>(120);

  useEffect(() => {
    if (!room) return;
    const next = Number(room.phase_seconds_remaining ?? room.seconds_remaining ?? room.pick_timer_seconds);
    setDisplaySecondsRemaining(Number.isFinite(next) ? Math.max(0, next) : 120);
  }, [room]);

  useEffect(() => {
    if (!room || room.status !== "countdown" || displaySecondsRemaining <= 0) return;
    const timer = window.setInterval(() => setDisplaySecondsRemaining((current) => Math.max(0, current - 1)), 1_000);
    return () => window.clearInterval(timer);
  }, [displaySecondsRemaining, room]);

  const isDraftRoomUnlocked = ["live", "paused", "completed"].includes(room?.status ?? "");
  const orderedTeams = useMemo(() => {
    if (!room) return [];
    const teamById = new Map(room.teams.map((team) => [team.id, team]));
    const ordered = room.draft_order
      .map((teamId) => teamById.get(teamId))
      .filter((team): team is (typeof room.teams)[number] => Boolean(team));
    const remaining = room.teams.filter((team) => !room.draft_order.includes(team.id));
    return [...ordered, ...remaining];
  }, [room]);

  if (!parsedMockDraftId) {
    return <div className="py-16 text-center text-sm font-black uppercase tracking-[0.2em] text-red-300">Invalid mock draft id.</div>;
  }

  if (isLoading) {
    return (
      <div className="py-16 flex items-center justify-center gap-3 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        Loading pre-draft room...
      </div>
    );
  }

  if (!room) {
    return <div className="py-16 text-center text-sm font-black uppercase tracking-[0.2em] text-red-300">{error instanceof Error ? error.message : "Pre-draft room unavailable."}</div>;
  }

  const occupancyLabel = `${room.lobby_joined_count}/${room.teams.length} joined • ${room.lobby_connected_count}/${room.teams.length} connected • ${room.lobby_ready_count}/${room.teams.length} ready`;
  const roomLabel = room.mode === "single_player" ? "Single-Player Mock Draft" : "Public Multiplayer Mock Draft";

  return (
    <div className="mx-auto max-w-7xl py-6 space-y-6">
      <Card className="rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader className="border-b border-white/10">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-3">
              <Button
                variant="ghost"
                className="h-8 -ml-2 px-2 text-[9px] font-black uppercase tracking-[0.2em] text-muted-foreground"
                onClick={() => navigate(`/mock-drafts/${parsedMockDraftId}/lobby`)}
              >
                <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                Exit
              </Button>
              <CardTitle className="text-[12px] font-black uppercase tracking-[0.28em] text-primary">Pre-Draft Intermission</CardTitle>
              <p className="text-2xl font-black text-foreground">Draft Order Locked</p>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                {roomLabel} • {room.teams.length}-team snake draft • {occupancyLabel}
              </p>
            </div>
            <div className="text-right space-y-2">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Draft Starts In</p>
              <p className="text-5xl font-black tabular-nums text-foreground">
                {String(Math.floor(displaySecondsRemaining / 60)).padStart(2, "0")}:{String(displaySecondsRemaining % 60).padStart(2, "0")}
              </p>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-200">
                Review Window • 120 Seconds
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-4 p-5">
          <Button
            className="h-12 rounded-2xl bg-gradient-to-r from-cyan-400 to-blue-500 px-6 text-[11px] font-black uppercase tracking-[0.22em] text-slate-950"
            onClick={() => navigate(`/mock-drafts/${parsedMockDraftId}/board`)}
            disabled={!isDraftRoomUnlocked}
          >
            {isDraftRoomUnlocked ? <Clock3 className="mr-2 h-4 w-4" /> : <Lock className="mr-2 h-4 w-4" />}
            Enter Draft Room
          </Button>
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
            {isDraftRoomUnlocked
              ? "The draft room is unlocked."
              : "This button unlocks when the 120-second intermission ends."}
          </p>
        </CardContent>
      </Card>

      <Card className="rounded-[2rem] border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Manager Draft List</CardTitle>
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              Pick order rubric
            </p>
          </div>
        </CardHeader>
        <CardContent className="p-5">
          <div className="mx-auto max-w-4xl overflow-hidden rounded-[1.5rem] border border-white/10 bg-slate-950/35">
            <div className="grid grid-cols-[72px_minmax(0,1fr)_150px] gap-4 border-b border-white/10 px-4 py-3 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
              <span>Pick</span>
              <span>Manager</span>
              <span className="text-right">Status</span>
            </div>
            {orderedTeams.map((team, index) => {
              const initials = (team.owner_name || team.name || "MO")
                .split(" ")
                .map((part) => part[0] || "")
                .join("")
                .slice(0, 2)
                .toUpperCase();
              return (
                <div
                  key={team.id}
                  className="grid grid-cols-[72px_minmax(0,1fr)_150px] items-center gap-4 border-b border-white/5 px-4 py-4 last:border-b-0 odd:bg-white/[0.025]"
                >
                  <div>
                    <p className="text-2xl font-black tabular-nums text-primary">{index + 1}</p>
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">1.{index + 1}</p>
                  </div>
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-white/15 bg-gradient-to-br from-slate-800 to-slate-950 text-sm font-black text-foreground shadow-[0_0_18px_rgba(34,211,238,0.08)]">
                      {initials || <UserRound className="h-5 w-5 text-primary" />}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-base font-black text-foreground">{team.name}</p>
                      <p className="truncate text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                        {team.owner_name || (team.owner_user_id ? "Manager" : "CPU Manager")}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 text-[10px] font-black uppercase tracking-[0.14em]">
                    <span className={team.lobby_connected ? "inline-flex items-center gap-1 text-emerald-200" : "inline-flex items-center gap-1 text-muted-foreground"}>
                      {team.lobby_connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                      {team.lobby_connected ? "Connected" : "Offline"}
                    </span>
                    <span className={team.lobby_ready ? "inline-flex items-center gap-1 text-cyan-200" : "inline-flex items-center gap-1 text-amber-200"}>
                      {team.lobby_ready ? <CheckCircle2 className="h-3 w-3" /> : null}
                      {team.lobby_ready ? "Ready" : "Waiting"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
