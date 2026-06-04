import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Clock3, Loader2, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MockDraftInviteLinkPanel } from "@/components/mock-draft/MockDraftInviteLinkPanel";
import { useMockDraftLobby, useMockDraftReady } from "@/hooks/use-mock-drafts";
import { shouldShowMockInvitePanel } from "./mock-draft-flow";

const formatClock = (totalSeconds: number) => {
  const safe = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
};

export default function MockDraftLobby() {
  const { mockDraftId } = useParams();
  const navigate = useNavigate();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: lobby, isLoading, error } = useMockDraftLobby(parsedMockDraftId, Boolean(parsedMockDraftId));
  const readyMutation = useMockDraftReady(parsedMockDraftId);

  const openSeatCount = Math.max(0, (lobby?.team_count ?? 0) - (lobby?.participants.length ?? 0));
  const sortedParticipants = useMemo(
    () => [...(lobby?.participants ?? [])].sort((a, b) => a.seat_number - b.seat_number),
    [lobby?.participants]
  );

  if (!parsedMockDraftId) return <div className="py-16 text-center text-red-300">Invalid mock draft id.</div>;
  if (isLoading) {
    return <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading lobby...</div>;
  }
  if (!lobby) {
    return <div className="py-16 text-center text-red-300">{error instanceof Error ? error.message : "Mock lobby unavailable."}</div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-8">
      <Card className="rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader className="border-b border-white/10">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="text-3xl font-black uppercase text-foreground">{lobby.name}</CardTitle>
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                {lobby.joined_count}/{lobby.team_count} joined • Open seats become bots at start
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">Starts In</p>
              <p className="text-4xl font-black tabular-nums text-foreground">{formatClock(lobby.seconds_until_start)}</p>
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cyan-200">{lobby.status}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 p-5">
          {shouldShowMockInvitePanel(lobby.session.mode, lobby.invite_link) ? (
            <MockDraftInviteLinkPanel inviteLink={lobby.invite_link!} inviteCode={lobby.invite_code ?? ""} />
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              disabled={readyMutation.isPending || lobby.settings_locked}
              onClick={() => readyMutation.mutate(true)}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Ready
            </Button>
            <Button
              className="bg-gradient-to-r from-cyan-300 to-blue-500 text-slate-950"
              disabled={!lobby.can_enter_room}
              onClick={() => navigate(`/draft/mock/${parsedMockDraftId}/room`)}
            >
              {lobby.can_enter_room ? <Clock3 className="mr-2 h-4 w-4" /> : <Lock className="mr-2 h-4 w-4" />}
              {lobby.can_enter_room ? "Enter Room" : "Room Locked"}
            </Button>
          </div>
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{lobby.message}</p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sortedParticipants.map((participant) => (
          <Card key={participant.id} className="rounded-2xl border-white/10 bg-card/35">
            <CardContent className="p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Seat {participant.seat_number}</p>
              <p className="mt-2 text-lg font-black text-foreground">{participant.team_name}</p>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                {participant.display_name} • {participant.participant_type}
              </p>
            </CardContent>
          </Card>
        ))}
        {Array.from({ length: openSeatCount }).map((_, index) => (
          <Card key={`open-${index}`} className="rounded-2xl border-dashed border-white/10 bg-card/20">
            <CardContent className="p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">Open Seat</p>
              <p className="mt-2 text-lg font-black text-foreground">Future Bot Seat</p>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">Filled at scheduled start</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
