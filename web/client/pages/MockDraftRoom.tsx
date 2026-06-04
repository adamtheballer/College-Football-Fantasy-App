import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Bot, Clipboard, Loader2, Mail, Search, Timer, Trophy, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDraftTimer } from "@/hooks/use-draft-timer";
import {
  useEmailMockDraftHistory,
  useExitMockDraft,
  useMockDraftAutoPick,
  useMockDraftHistory,
  useMockDraftPick,
  useMockDraftRoom,
} from "@/hooks/use-mock-drafts";
import { usePlayers } from "@/hooks/use-players";
import { ApiError } from "@/lib/api";
import { MOCK_DRAFT_EXIT_PATH, shouldShowMockCompletionModal, shouldTriggerMockAutoPick } from "./mock-draft-flow";

export default function MockDraftRoom() {
  const { mockDraftId } = useParams();
  const navigate = useNavigate();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: room, isLoading, error } = useMockDraftRoom(parsedMockDraftId, Boolean(parsedMockDraftId));
  const pickMutation = useMockDraftPick(parsedMockDraftId);
  const autoPickMutation = useMockDraftAutoPick(parsedMockDraftId);
  const emailMutation = useEmailMockDraftHistory(parsedMockDraftId);
  const exitMutation = useExitMockDraft(parsedMockDraftId);
  const { data: history } = useMockDraftHistory(parsedMockDraftId, Boolean(room?.is_complete));
  const [search, setSearch] = useState("");
  const [completionChoiceMade, setCompletionChoiceMade] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const { data: playersPayload, isLoading: playersLoading } = usePlayers({ search: search.trim() || undefined, sort: "adp", limit: 500 });

  const timer = useDraftTimer({
    serverTime: room?.server_time,
    currentPickExpiresAt: room?.current_pick_expires_at,
    currentPick: room?.current_overall_pick,
  });

  const draftedPlayerIds = useMemo(() => new Set((room?.picks ?? []).map((pick) => pick.player_id)), [room?.picks]);
  const availablePlayers = useMemo(
    () => (playersPayload?.data ?? []).filter((player) => !draftedPlayerIds.has(player.id)).slice(0, 150),
    [draftedPlayerIds, playersPayload?.data]
  );
  const currentParticipant = room?.participants.find((participant) => participant.id === room.current_participant_id) ?? null;
  const showCompletionModal = shouldShowMockCompletionModal(Boolean(room?.is_complete), completionChoiceMade);

  useEffect(() => {
    if (!shouldTriggerMockAutoPick(room, { isExpired: timer.isExpired, autoPickPending: autoPickMutation.isPending })) return;
    if (room.current_participant_type === "bot") {
      const timeout = window.setTimeout(() => {
        void autoPickMutation.mutateAsync({ force: false }).catch(() => undefined);
      }, 1_200);
      return () => window.clearTimeout(timeout);
    }
    if (timer.isExpired) {
      void autoPickMutation.mutateAsync({ force: false }).catch(() => undefined);
    }
  }, [autoPickMutation, room?.current_overall_pick, room?.current_participant_type, room?.is_complete, room?.status, timer.isExpired]);

  if (!parsedMockDraftId) return <div className="py-16 text-center text-red-300">Invalid mock draft id.</div>;
  if (isLoading) {
    return <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading mock room...</div>;
  }
  if (!room) {
    return <div className="py-16 text-center text-red-300">{error instanceof Error ? error.message : "Mock room unavailable."}</div>;
  }

  const sendEmail = async () => {
    setEmailError(null);
    try {
      await emailMutation.mutateAsync();
      setCompletionChoiceMade(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setEmailError("Email is not configured. Copy the history and exit when ready.");
        setCompletionChoiceMade(true);
        return;
      }
      setEmailError(err instanceof Error ? err.message : "Unable to send history email.");
    }
  };

  const exitDraft = async () => {
    const response = await exitMutation.mutateAsync();
    navigate(response.navigate_to || MOCK_DRAFT_EXIT_PATH);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 py-6">
      {showCompletionModal ? (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-xl">
          <Card className="w-full max-w-xl rounded-[2rem] border-cyan-200/20 bg-[#07111f] text-center">
            <CardContent className="space-y-5 p-6">
              <Trophy className="mx-auto h-10 w-10 text-cyan-200" />
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-200">Mock Draft Complete</p>
                <h2 className="mt-2 text-2xl font-black text-white">Want to send the draft history to your email?</h2>
                <p className="mt-2 text-sm font-semibold text-slate-400">{history ? `${history.pick_count} picks are ready.` : "History is being prepared."}</p>
              </div>
              {emailError ? <p className="text-sm font-semibold text-amber-200">{emailError}</p> : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <Button variant="outline" onClick={() => setCompletionChoiceMade(true)}>No thanks</Button>
                <Button className="bg-cyan-300 text-slate-950" disabled={emailMutation.isPending} onClick={() => void sendEmail()}>
                  {emailMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
                  Send to my email
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {room.is_complete && completionChoiceMade ? (
        <Card className="rounded-[2rem] border-emerald-300/20 bg-emerald-400/10">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <p className="text-lg font-black text-foreground">Mock Draft Complete</p>
              <p className="text-sm font-semibold text-muted-foreground">You can copy results or exit back to the Draft tab.</p>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" disabled={!history?.plain_text} onClick={() => history?.plain_text && navigator.clipboard?.writeText(history.plain_text)}>
                <Clipboard className="mr-2 h-4 w-4" />
                Copy History
              </Button>
              <Button className="bg-cyan-300 text-slate-950" onClick={() => void exitDraft()}>Exit Mock Draft</Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card className="rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader className="border-b border-white/10">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="text-3xl font-black uppercase text-foreground">{room.session.name}</CardTitle>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                Round {room.current_round} • Pick {room.current_round_pick} • Overall {room.current_overall_pick}/{room.total_picks}
              </p>
              <p className="mt-2 text-sm font-bold text-cyan-100">
                On clock: {room.current_team_name ?? "Complete"} {currentParticipant?.participant_type === "bot" ? "(Bot)" : ""}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">Timer</p>
              <p className="text-5xl font-black tabular-nums text-foreground">{room.status === "live" ? timer.formattedTime : "--:--"}</p>
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cyan-200">{room.phase_type ?? room.status}</p>
            </div>
          </div>
        </CardHeader>
        {room.status === "intermission" ? (
          <CardContent className="p-8 text-center">
            <Timer className="mx-auto h-10 w-10 text-cyan-200" />
            <p className="mt-3 text-2xl font-black text-foreground">Pre-draft intermission</p>
            <p className="mt-2 text-sm font-semibold text-muted-foreground">Draft order is locked. Picks open when the backend intermission timer ends.</p>
          </CardContent>
        ) : null}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="rounded-[2rem] border-white/10 bg-card/40">
          <CardHeader><CardTitle className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">Draft Order</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {room.participants
              .filter((participant) => participant.draft_position !== null)
              .sort((a, b) => Number(a.draft_position) - Number(b.draft_position))
              .map((participant) => (
                <div key={participant.id} className={`rounded-xl border p-3 ${participant.id === room.current_participant_id ? "border-cyan-300/50 bg-cyan-400/10" : "border-white/10 bg-white/[0.03]"}`}>
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Pick {participant.draft_position}</p>
                  <p className="mt-1 font-black text-foreground">{participant.team_name}</p>
                  <p className="mt-1 flex items-center gap-1 text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                    {participant.participant_type === "bot" ? <Bot className="h-3 w-3" /> : <User className="h-3 w-3" />}
                    {participant.display_name}
                  </p>
                </div>
              ))}
          </CardContent>
        </Card>

        <Card className="rounded-[2rem] border-white/10 bg-card/40">
          <CardHeader className="border-b border-white/10">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">Available Players</CardTitle>
              <div className="relative w-full max-w-sm">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-10" placeholder="Search players..." />
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {playersLoading ? (
              <div className="p-6 text-sm text-muted-foreground">Loading players...</div>
            ) : (
              <div className="max-h-[680px] overflow-y-auto">
                {availablePlayers.map((player, index) => (
                  <div key={player.id} className="grid grid-cols-[64px_minmax(0,1fr)_80px_120px] items-center gap-3 border-b border-white/10 px-4 py-3">
                    <p className="font-black tabular-nums text-muted-foreground">{index + 1}</p>
                    <div className="min-w-0">
                      <p className="truncate font-black text-foreground">{player.name}</p>
                      <p className="truncate text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{player.school}</p>
                    </div>
                    <p className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-3 py-1 text-center text-xs font-black text-cyan-100">{player.pos}</p>
                    <Button
                      className="bg-gradient-to-r from-cyan-300 to-blue-500 text-slate-950"
                      disabled={!room.can_make_pick || pickMutation.isPending || autoPickMutation.isPending || room.is_complete}
                      onClick={() => pickMutation.mutate(player.id)}
                    >
                      {pickMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Draft"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[2rem] border-white/10 bg-card/40">
        <CardHeader><CardTitle className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">Pick History</CardTitle></CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {room.picks.slice().reverse().slice(0, 24).map((pick) => (
            <div key={pick.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{pick.round_number}.{pick.round_pick} • {pick.pick_source}</p>
              <p className="mt-1 font-black text-foreground">{pick.player_name}</p>
              <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">{pick.team_name}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
