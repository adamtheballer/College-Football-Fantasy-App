import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowDown, ArrowLeft, ArrowUp, CheckCircle2, Clock3, Loader2, Pause, Play, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  useDraftLobbyHeartbeat,
  useDraftLobbyJoin,
  useDraftLobbyReady,
  useDraftRoom,
  useDraftRoomRealtime,
  useDraftRoomStatus,
  useDraftSlotMove,
} from "@/hooks/use-draft";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

const phaseLabel = (status: string) => {
  const normalized = (status || "").toLowerCase();
  if (normalized === "filling") return "Filling";
  if (normalized === "lobby_open") return "Lobby Open";
  if (normalized === "countdown") return "Countdown";
  if (normalized === "scheduled") return "Scheduled";
  if (normalized === "live") return "Live";
  if (normalized === "paused") return "Paused";
  if (normalized === "completed") return "Complete";
  if (normalized === "abandoned") return "Abandoned";
  return status || "Unknown";
};

export default function DraftLobby() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const parsedLeagueId = leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;

  const { data: league } = useLeagueDetail(parsedLeagueId);
  const {
    data: draftRoom,
    isLoading,
    error,
  } = useDraftRoom(parsedLeagueId, Boolean(parsedLeagueId));
  useDraftRoomRealtime(parsedLeagueId, Boolean(parsedLeagueId));
  const statusMutation = useDraftRoomStatus(parsedLeagueId);
  const slotMoveMutation = useDraftSlotMove(parsedLeagueId);
  const joinLobbyMutation = useDraftLobbyJoin(parsedLeagueId);
  const readyMutation = useDraftLobbyReady(parsedLeagueId);
  const heartbeatMutation = useDraftLobbyHeartbeat(parsedLeagueId);
  const [countdownSeconds, setCountdownSeconds] = useState<number>(0);
  const [now, setNow] = useState(() => Date.now());

  const isCommissioner = Boolean(user && league?.commissioner_user_id === user.id);
  const slotsFilled = draftRoom?.teams?.length ?? 0;
  const slotCapacity = league?.max_teams ?? slotsFilled;
  const isDraftWindowOpen = ["countdown", "live", "paused"].includes(draftRoom?.status ?? "");
  const canEnterDraftRoom = Boolean(draftRoom && !["abandoned"].includes(draftRoom.status));
  const enterDraftHelpText = isDraftWindowOpen
    ? "Draft room is open for live draft activity."
    : "You can enter early to preview the board, queue players, and monitor lobby status.";
  const canReorderSlots = isCommissioner && ["filling", "lobby_open", "scheduled"].includes(draftRoom?.status ?? "");
  const currentUserTeam =
    draftRoom?.teams?.find((team) => team.owner_user_id === user?.id) ?? null;
  const isLobbyJoined = Boolean(currentUserTeam?.lobby_joined);
  const isLobbyReady = Boolean(currentUserTeam?.lobby_ready);
  const joinedCount = draftRoom?.lobby_joined_count ?? 0;
  const connectedCount = draftRoom?.lobby_connected_count ?? 0;
  const readyCount = draftRoom?.lobby_ready_count ?? 0;

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const next = Number(draftRoom?.seconds_remaining ?? 0);
    setCountdownSeconds(Number.isFinite(next) ? Math.max(0, next) : 0);
  }, [draftRoom?.seconds_remaining, draftRoom?.status, draftRoom?.current_pick, now]);

  useEffect(() => {
    if (!draftRoom || !["scheduled", "countdown"].includes(draftRoom.status)) return;
    const timer = window.setInterval(() => {
      setCountdownSeconds((current) => Math.max(0, current - 1));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [draftRoom]);

  useEffect(() => {
    if (!parsedLeagueId || !draftRoom) return;
    if (draftRoom.status === "countdown" || draftRoom.status === "live" || draftRoom.status === "paused") {
      navigate(`/league/${parsedLeagueId}/draft`, { replace: true });
    }
  }, [draftRoom, navigate, parsedLeagueId]);

  useEffect(() => {
    if (!parsedLeagueId || !draftRoom || !isLobbyJoined) return;
    const timer = window.setInterval(() => {
      heartbeatMutation.mutate();
    }, 12_000);
    return () => window.clearInterval(timer);
  }, [draftRoom, heartbeatMutation, isLobbyJoined, parsedLeagueId]);

  const formattedCountdown = useMemo(() => {
    const scheduledAt = league?.draft?.draft_datetime_utc ? Date.parse(league.draft.draft_datetime_utc) : NaN;
    const scheduledSeconds =
      draftRoom?.status === "scheduled" && Number.isFinite(scheduledAt)
        ? Math.max(0, Math.ceil((scheduledAt - now) / 1000))
        : countdownSeconds;
    const mins = Math.floor(scheduledSeconds / 60)
      .toString()
      .padStart(2, "0");
    const secs = (scheduledSeconds % 60).toString().padStart(2, "0");
    return `${mins}:${secs}`;
  }, [countdownSeconds, draftRoom?.status, league?.draft?.draft_datetime_utc, now]);
  const countdownLabel = useMemo(() => {
    if (draftRoom?.status === "countdown") return "Draft Starts In";
    if (draftRoom?.status === "scheduled") return "Scheduled For";
    if (draftRoom?.status === "live") return "Round Live";
    return "Awaiting Start";
  }, [draftRoom?.status]);

  const settingsFlavor = useMemo(() => {
    const scoring = league?.settings?.scoring_json ?? {};
    const metaPreset = String((scoring as Record<string, unknown>)["preset"] ?? (scoring as Record<string, unknown>)["settings_preset"] ?? "").toLowerCase();
    if (metaPreset.includes("default")) return "Default";
    if (metaPreset.includes("custom")) return "Custom";
    if (league?.settings?.superflex_enabled || league?.settings?.defense_enabled) return "Custom";
    return "Default";
  }, [league?.settings]);

  if (!parsedLeagueId) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="rounded-[2rem] border-red-400/30 bg-card/50">
          <CardContent className="p-10 text-center text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
            Invalid league id.
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="rounded-[2rem] border-white/10 bg-card/50">
          <CardContent className="p-10 flex items-center justify-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">Loading draft lobby...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!draftRoom || error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Draft lobby unavailable.";
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="rounded-[2rem] border-red-400/25 bg-card/50">
          <CardContent className="p-10 text-center space-y-4">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">{message}</p>
            <Button asChild variant="outline" className="rounded-xl text-[10px] font-black uppercase tracking-[0.16em]">
              <Link to={`/league/${parsedLeagueId}`}>Back to league</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl py-8 space-y-5">
      <Card className="rounded-[2rem] border-white/10 bg-card/40">
        <CardHeader className="border-b border-white/10">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <Button
                type="button"
                variant="ghost"
                className="h-8 -ml-2 px-2 text-[9px] font-black uppercase tracking-[0.2em] text-muted-foreground"
                onClick={() => navigate(`/league/${parsedLeagueId}`)}
              >
                <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                Exit
              </Button>
              <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">Draft Lobby</CardTitle>
              <p className="text-sm font-black text-foreground">{league?.name ?? "League"}</p>
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                {slotsFilled} of {slotCapacity} slots filled • Snake draft
              </p>
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/75">
                Draft Name: {league?.draft?.draft_type ? `${String(league.draft.draft_type).toUpperCase()} Draft` : "League Draft"} • Phase:{" "}
                {phaseLabel(draftRoom.status)}
              </p>
            </div>
            <div className="text-right space-y-2">
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">Status</p>
              <p className="text-lg font-black text-foreground">{phaseLabel(draftRoom.status)}</p>
              <div className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                <Clock3 className="h-4 w-4 text-primary" />
                <div className="text-right">
                  <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/80">{countdownLabel}</p>
                  <p className="text-lg font-black tabular-nums">{formattedCountdown}</p>
                </div>
              </div>
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-emerald-200/85">
                Ready {readyCount} / {slotCapacity} • Connected {connectedCount} / {slotCapacity}
              </p>
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/75">
                {slotCapacity}-Team • Snake • {settingsFlavor} Settings
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              <Users className="h-4 w-4 text-primary" />
              Draft Lobby
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                disabled={joinLobbyMutation.isPending || isLobbyJoined}
                onClick={() => joinLobbyMutation.mutate()}
              >
                {joinLobbyMutation.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                {isLobbyJoined ? "Joined" : "Join Draft Lobby"}
              </Button>
              <Button
                type="button"
                variant={isLobbyReady ? "default" : "outline"}
                className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                disabled={readyMutation.isPending || !isLobbyJoined}
                onClick={() => readyMutation.mutate(!isLobbyReady)}
              >
                {readyMutation.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="mr-1 h-3.5 w-3.5" />}
                {isLobbyReady ? "Ready" : "Mark Ready"}
              </Button>
              {isCommissioner ? (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                    disabled={statusMutation.isPending || draftRoom.status === "lobby_open"}
                    onClick={() => statusMutation.mutate({ status: "lobby_open" })}
                  >
                    Open Lobby
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                    disabled={statusMutation.isPending || draftRoom.status !== "live"}
                    onClick={() => statusMutation.mutate({ status: "paused" })}
                  >
                    <Pause className="mr-1 h-3.5 w-3.5" />
                    Pause
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                    disabled={
                      statusMutation.isPending ||
                      draftRoom.status === "live" ||
                      draftRoom.status === "countdown"
                    }
                    onClick={() =>
                      statusMutation.mutate({
                        status: draftRoom.status === "paused" ? "active" : "countdown",
                      })
                    }
                  >
                    <Play className="mr-1 h-3.5 w-3.5" />
                    {draftRoom.status === "paused" ? "Resume Draft" : "Start Draft"}
                  </Button>
                </>
              ) : null}
              <Button
                type="button"
                className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                onClick={() => navigate(`/league/${parsedLeagueId}/draft`)}
                disabled={!canEnterDraftRoom}
              >
                {isDraftWindowOpen ? "Enter Draft" : "Preview Draft Room"}
              </Button>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-3">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              Ready: {readyCount} / {slotCapacity} Managers • Joined: {joinedCount} / {slotCapacity}
            </p>
            <p className="mt-1 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/75">
              {enterDraftHelpText} Start Draft triggers a 60-second countdown. No picks are processed until the countdown reaches 0.
            </p>
          </div>

          {joinLobbyMutation.error ? (
            <div className="rounded-xl border border-red-400/25 bg-red-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-red-200">
              {joinLobbyMutation.error instanceof ApiError ? joinLobbyMutation.error.message : "Unable to join lobby."}
            </div>
          ) : null}
          {readyMutation.error ? (
            <div className="rounded-xl border border-red-400/25 bg-red-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-red-200">
              {readyMutation.error instanceof ApiError ? readyMutation.error.message : "Unable to update ready status."}
            </div>
          ) : null}

          <div className="rounded-2xl border border-white/10 bg-white/[0.02] divide-y divide-white/5">
            {draftRoom.teams.map((team, index) => (
              <div key={team.id} className="grid grid-cols-[72px_minmax(0,1fr)_170px_120px] items-center gap-4 px-4 py-3">
                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">Slot {index + 1}</p>
                <div className="min-w-0">
                  <p className="truncate text-sm font-black uppercase tracking-tight text-foreground">{team.name}</p>
                  <p className="truncate text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/75">
                    {team.owner_name || "Auto Team"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      team.lobby_connected
                        ? "bg-emerald-300 shadow-[0_0_10px_rgba(74,222,128,0.9)]"
                        : team.lobby_joined
                          ? "bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,0.8)]"
                          : "bg-rose-300 shadow-[0_0_10px_rgba(251,113,133,0.8)]"
                    }`}
                  />
                  <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                    {team.lobby_connected ? "Connected" : team.lobby_joined ? "Idle" : "Not Joined"}
                  </p>
                  {team.lobby_ready ? (
                    <span className="inline-flex h-5 items-center rounded-full border border-emerald-300/40 bg-emerald-400/10 px-2 text-[8px] font-black uppercase tracking-[0.12em] text-emerald-100">
                      Ready
                    </span>
                  ) : null}
                </div>
                <div className="flex items-center justify-end gap-2">
                  {canReorderSlots ? (
                    <div className="flex items-center gap-1">
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 rounded-lg"
                        disabled={index === 0 || slotMoveMutation.isPending}
                        onClick={() =>
                          slotMoveMutation.mutate({
                            from_slot: index + 1,
                            to_slot: Math.max(1, index),
                          })
                        }
                        aria-label={`Move ${team.name} up`}
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 rounded-lg"
                        disabled={index === draftRoom.teams.length - 1 || slotMoveMutation.isPending}
                        onClick={() =>
                          slotMoveMutation.mutate({
                            from_slot: index + 1,
                            to_slot: Math.min(draftRoom.teams.length, index + 2),
                          })
                        }
                        aria-label={`Move ${team.name} down`}
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-primary">Draft Order</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">Round 1</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.1em] text-foreground/90">
                  {draftRoom.teams.map((team, index) => `${index + 1}. ${team.name}`).join("  •  ")}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">Round 2 (Snake)</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.1em] text-foreground/90">
                  {[...draftRoom.teams]
                    .reverse()
                    .map((team, index) => `${index + 1}. ${team.name}`)
                    .join("  •  ")}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
