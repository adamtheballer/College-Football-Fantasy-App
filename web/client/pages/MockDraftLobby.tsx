import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Clock3, Copy, Loader2, Trash2, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import {
  useDeleteMockDraft,
  useMockDraftLobby,
  useMockDraftLobbyHeartbeat,
  useMockDraftLobbyJoin,
  useMockDraftLobbyReady,
  useMockDraftRealtime,
} from "@/hooks/use-mock-draft";

export default function MockDraftLobby() {
  const { mockDraftId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: lobby, isLoading, error } = useMockDraftLobby(parsedMockDraftId, Boolean(parsedMockDraftId));
  useMockDraftRealtime(parsedMockDraftId, Boolean(parsedMockDraftId));
  const joinMutation = useMockDraftLobbyJoin(parsedMockDraftId);
  const readyMutation = useMockDraftLobbyReady(parsedMockDraftId);
  const heartbeatMutation = useMockDraftLobbyHeartbeat(parsedMockDraftId);
  const deleteMutation = useDeleteMockDraft(parsedMockDraftId);

  const isCommissioner = Boolean(user && lobby?.commissioner_user_id === user.id);
  const currentSeat = lobby?.seats.find((seat) => seat.owner_user_id === user?.id) ?? null;
  const canEnter = Boolean(lobby?.can_enter_room);
  const isPublicMultiplayer = lobby?.mode === "public_multiplayer";

  useEffect(() => {
    if (!parsedMockDraftId || !lobby || !currentSeat) return;
    const timer = window.setInterval(() => heartbeatMutation.mutate(), 12_000);
    return () => window.clearInterval(timer);
  }, [currentSeat, heartbeatMutation, lobby, parsedMockDraftId]);

  const statusLabel = useMemo(() => String(lobby?.status || "scheduled").replace(/_/g, " ").toUpperCase(), [lobby?.status]);
  const lobbyTimerSeconds = Math.max(0, Number(lobby?.seconds_remaining ?? 0));
  const timerLabel = useMemo(() => {
    if (!lobby) return "Seat Fill Clock";
    if (lobby.status === "scheduled") return "Seat Fill Clock";
    if (lobby.status === "countdown") return "Draft Starts In";
    if (lobby.status === "live") return "Draft Live";
    if (lobby.status === "paused") return "Draft Paused";
    return "Lobby Clock";
  }, [lobby]);
  const timerDescription = useMemo(() => {
    if (!lobby) return "";
    if (lobby.status === "scheduled") {
      return "Open seats become auto managers when this expires.";
    }
    if (lobby.status === "countdown") {
      return "The room is unlocked. Enter and review everything before picks open.";
    }
    if (lobby.status === "live") {
      return "The draft room is active.";
    }
    if (lobby.status === "paused") {
      return "The commissioner paused the draft.";
    }
    return "Lobby status in progress.";
  }, [lobby]);

  if (!parsedMockDraftId) {
    return <div className="py-16 text-center text-sm font-black uppercase tracking-[0.2em] text-red-300">Invalid mock draft id.</div>;
  }

  if (isLoading) {
    return (
      <div className="py-16 flex items-center justify-center gap-3 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        Loading mock lobby...
      </div>
    );
  }

  if (!lobby) {
    return <div className="py-16 text-center text-sm font-black uppercase tracking-[0.2em] text-red-300">{error instanceof Error ? error.message : "Mock lobby unavailable."}</div>;
  }

  return (
    <div className="mx-auto max-w-6xl py-8 space-y-6">
      <Card className="rounded-[2rem] border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-2">
              <CardTitle className="text-[12px] font-black uppercase tracking-[0.28em] text-primary">Mock Draft Lobby</CardTitle>
              <p className="text-2xl font-black text-foreground">{lobby.name}</p>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                {lobby.joined_count}/{lobby.manager_count} seats filled
                {isPublicMultiplayer ? ` • Invite code ${lobby.invite_code}` : " • Single-player room"}
              </p>
            </div>
            <div className="space-y-2 text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Status</p>
              <p className="text-xl font-black text-foreground">{statusLabel}</p>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-200">
                Ready {lobby.ready_count}/{lobby.manager_count} • Connected {lobby.connected_count}/{lobby.manager_count}
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 p-5">
          <div className="rounded-[1.6rem] border border-cyan-400/20 bg-gradient-to-r from-cyan-500/10 via-blue-500/10 to-emerald-500/10 p-5">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100">{timerLabel}</p>
                <p className="text-4xl font-black tabular-nums text-foreground">
                  {String(Math.floor(lobbyTimerSeconds / 60)).padStart(2, "0")}:{String(lobbyTimerSeconds % 60).padStart(2, "0")}
                </p>
                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/90">{timerDescription}</p>
              </div>
              <div className="min-w-[240px] flex-1 space-y-3">
                <div className="h-3 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-400 to-emerald-300 transition-[width] duration-1000"
                    style={{
                      width: `${Math.max(
                        0,
                        Math.min(
                          100,
                          ((lobby.status === "scheduled" ? 120 : lobby.status === "countdown" ? 120 : 0) - lobbyTimerSeconds) /
                            Math.max(1, lobby.status === "scheduled" ? 120 : lobby.status === "countdown" ? 120 : 1) *
                            100
                        )
                      )}%`,
                    }}
                  />
                </div>
                <div className="flex gap-3 flex-wrap text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                  <span className={lobby.status === "scheduled" ? "text-cyan-100" : ""}>1. Claim Seats</span>
                  <span className={lobby.status === "countdown" ? "text-cyan-100" : ""}>2. Enter Draft Room</span>
                  <span className={["live", "paused", "completed"].includes(lobby.status) ? "text-cyan-100" : ""}>3. Draft Starts</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex gap-3 flex-wrap">
            <Button
              className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
              onClick={() => joinMutation.mutate()}
              disabled={!isPublicMultiplayer || joinMutation.isPending || Boolean(currentSeat)}
            >
              {joinMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Users className="mr-2 h-4 w-4" />}
              {currentSeat ? "Joined" : "Join Lobby"}
            </Button>
            <Button
              variant={currentSeat?.lobby_ready ? "default" : "outline"}
              className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
              onClick={() => readyMutation.mutate(!currentSeat?.lobby_ready)}
              disabled={readyMutation.isPending || !currentSeat}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {currentSeat?.lobby_ready ? "Ready" : "Mark Ready"}
            </Button>
            {isPublicMultiplayer ? (
              <Button
                variant="outline"
                className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.18em]"
                onClick={() => navigator.clipboard.writeText(lobby.invite_code)}
              >
                <Copy className="mr-2 h-4 w-4" />
                Copy Invite Code
              </Button>
            ) : null}
            {isCommissioner ? (
              <Button
                variant="outline"
                className="h-10 rounded-xl border-red-400/30 text-[10px] font-black uppercase tracking-[0.18em] text-red-200"
                onClick={() =>
                  deleteMutation.mutate(undefined, {
                    onSuccess: () => navigate("/draft", { replace: true }),
                  })
                }
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            ) : null}
            <Button
              className="h-10 rounded-xl bg-gradient-to-r from-cyan-400 to-blue-500 text-[10px] font-black uppercase tracking-[0.18em] text-slate-950"
              onClick={() => navigate(`/mock-drafts/${parsedMockDraftId}/room`)}
              disabled={!canEnter}
            >
              <Clock3 className="mr-2 h-4 w-4" />
              {canEnter ? "Enter Draft Room" : "Room Locked"}
            </Button>
          </div>
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/80">
            When the 120-second seat timer expires, every unclaimed seat becomes an auto manager. Then a 120-second review window begins before the draft clock opens.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {lobby.seats
          .sort((a, b) => a.seat_number - b.seat_number)
          .map((seat) => (
            <Card key={seat.id} className="rounded-[1.75rem] border-white/10 bg-card/35">
              <CardContent className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">Seat {seat.seat_number}</p>
                    <p className="text-lg font-black text-foreground">{seat.name}</p>
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                      {seat.is_cpu ? "CPU manager" : seat.owner_name || "Open seat"}
                    </p>
                  </div>
                  <div className="text-right text-[10px] font-black uppercase tracking-[0.16em]">
                    <p className={seat.lobby_joined ? "text-cyan-200" : "text-muted-foreground"}>{seat.lobby_joined ? "Joined" : "Open"}</p>
                    <p className={seat.lobby_connected ? "text-emerald-200" : "text-muted-foreground"}>{seat.lobby_connected ? "Connected" : "Offline"}</p>
                    <p className={seat.lobby_ready ? "text-amber-200" : "text-muted-foreground"}>{seat.lobby_ready ? "Ready" : "Waiting"}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
      </div>
    </div>
  );
}
