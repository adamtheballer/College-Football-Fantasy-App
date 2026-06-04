import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CalendarClock, CheckCircle2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MockDraftInviteLinkPanel } from "@/components/mock-draft/MockDraftInviteLinkPanel";
import { useCreateMockDraft } from "@/hooks/use-mock-drafts";
import { ApiError } from "@/lib/api";
import { getMockDraftCreateMode, getMockDraftCreateSuccessRoomPath, shouldShowMockInviteSuccess } from "./mock-draft-flow";
import type { StandaloneMockDraftCreateResponse } from "@/types/mock-draft";

const toLocalDateTimeInput = (date: Date) => {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

const formatCreateMockDraftError = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Please sign in to create a mock draft.";
    return error.message;
  }
  if (error instanceof TypeError && error.message.toLowerCase().includes("fetch")) {
    return "Unable to reach the backend API. Check that FastAPI is running and VITE_API_BASE_URL points to the correct public or local backend URL.";
  }
  if (error instanceof Error && error.message) return error.message;
  return "Unable to create mock draft. Please try again.";
};

export default function CreateMockDraft() {
  const navigate = useNavigate();
  const location = useLocation();
  const createMutation = useCreateMockDraft();
  const isSinglePlayerIntent = new URLSearchParams(location.search).get("single") === "1";
  const [name, setName] = useState(isSinglePlayerIntent ? "Single-Player Mock Draft" : "Multiplayer Mock Draft");
  const [teamCount, setTeamCount] = useState<"4" | "6" | "8" | "10" | "12">("12");
  const [roundCount, setRoundCount] = useState("13");
  const [pickTimer, setPickTimer] = useState<"30" | "60" | "90" | "120">("30");
  const [scheduledStart, setScheduledStart] = useState(() => toLocalDateTimeInput(new Date(Date.now() + 5 * 60_000)));
  const [createdDraft, setCreatedDraft] = useState<StandaloneMockDraftCreateResponse | null>(null);

  const scheduledDate = useMemo(() => new Date(scheduledStart), [scheduledStart]);
  const isFuture = Number.isFinite(scheduledDate.getTime()) && scheduledDate.getTime() > Date.now();
  const canSubmit = name.trim().length > 0 && (isSinglePlayerIntent || isFuture) && !createMutation.isPending;

  if (shouldShowMockInviteSuccess(createdDraft)) {
    return (
      <div className="cfb-ui-font mx-auto max-w-3xl py-8">
        <Card className="rounded-[2rem] border-white/10 bg-card/45">
          <CardHeader>
            <div className="flex items-center gap-3">
              <span className="rounded-full border border-emerald-300/30 bg-emerald-400/10 p-2 text-emerald-100">
                <CheckCircle2 className="h-5 w-5" />
              </span>
              <div>
                <CardTitle className="cfb-display-font text-3xl uppercase text-foreground md:text-4xl">
                  Mock Draft Created
                </CardTitle>
                <p className="mt-2 text-sm font-semibold leading-6 tracking-[-0.015em] text-slate-300/85 md:text-base">
                  Copy the backend-generated invite link before sending it to friends.
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <MockDraftInviteLinkPanel inviteLink={createdDraft.invite_link!} inviteCode={createdDraft.invite_code ?? ""} />
            <div className="flex flex-wrap gap-3">
              <Button className="cfb-control-font" variant="outline" onClick={() => navigate("/draft")}>
                Back to Drafts
              </Button>
              <Button
                className="cfb-control-font bg-gradient-to-r from-cyan-300 to-blue-500 text-slate-950"
                onClick={() => navigate(`/draft/mock/${createdDraft.mock_draft_id}/lobby`)}
              >
                Go to Lobby
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="cfb-ui-font mx-auto max-w-3xl py-8">
      <Card className="rounded-[2rem] border-white/10 bg-card/45">
        <CardHeader>
          <CardTitle className="cfb-display-font text-3xl uppercase text-foreground md:text-4xl">
            Create Mock Draft
          </CardTitle>
          <p className="max-w-2xl text-sm font-semibold leading-6 tracking-[-0.015em] text-slate-300/85 md:text-base">
            Mock drafts are standalone. They do not write real league rosters or draft picks.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label className="cfb-label-font">Name</Label>
            <Input
              className="cfb-control-font"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label className="cfb-label-font">Teams</Label>
              <Select value={teamCount} onValueChange={(value: "4" | "6" | "8" | "10" | "12") => setTeamCount(value)}>
                <SelectTrigger className="cfb-control-font"><SelectValue /></SelectTrigger>
                <SelectContent>{[4, 6, 8, 10, 12].map((value) => <SelectItem key={value} value={String(value)}>{value}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="cfb-label-font">Rounds</Label>
              <Input
                className="cfb-control-font"
                value={roundCount}
                onChange={(event) => setRoundCount(event.target.value)}
                inputMode="numeric"
              />
            </div>
            <div className="space-y-2">
              <Label className="cfb-label-font">Pick Timer</Label>
              <Select value={pickTimer} onValueChange={(value: "30" | "60" | "90" | "120") => setPickTimer(value)}>
                <SelectTrigger className="cfb-control-font"><SelectValue /></SelectTrigger>
                <SelectContent>{[30, 60, 90, 120].map((value) => <SelectItem key={value} value={String(value)}>{value}s</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          {isSinglePlayerIntent ? (
            <p className="cfb-note-font text-[10px] uppercase text-muted-foreground">
              Single-player mock drafts start immediately. Empty seats become bots before entering the room.
            </p>
          ) : (
            <div className="space-y-2">
              <Label className="cfb-label-font">Scheduled Start</Label>
              <Input
                className="cfb-control-font"
                type="datetime-local"
                value={scheduledStart}
                onChange={(event) => setScheduledStart(event.target.value)}
              />
              <p className="cfb-note-font text-[10px] uppercase text-muted-foreground">
                Host cannot start early. Empty seats become bots at the scheduled time.
              </p>
              {!isFuture ? <p className="text-sm font-semibold text-red-300">Scheduled start must be in the future.</p> : null}
            </div>
          )}
          {createMutation.error ? (
            <p className="text-sm font-semibold text-red-300">{formatCreateMockDraftError(createMutation.error)}</p>
          ) : null}
          <div className="flex gap-3">
            <Button className="cfb-control-font" variant="outline" onClick={() => navigate("/draft")}>Cancel</Button>
            <Button
              className="cfb-control-font bg-gradient-to-r from-cyan-300 to-blue-500 text-slate-950"
              disabled={!canSubmit}
              onClick={() =>
                {
                  const mode = getMockDraftCreateMode(isSinglePlayerIntent);
                  const payloadScheduledDate = mode === "single_player" ? new Date(Date.now() + 5 * 60_000) : scheduledDate;
                  createMutation.mutate(
                    {
                      name: name.trim(),
                      mode,
                      team_count: Number(teamCount) as 4 | 6 | 8 | 10 | 12,
                      round_count: Math.max(1, Math.min(20, Number(roundCount) || 13)),
                      pick_timer_seconds: Number(pickTimer) as 30 | 60 | 90 | 120,
                      scheduled_start_at: payloadScheduledDate.toISOString(),
                      player_pool: "power4",
                      scoring_type: "espn_full_ppr",
                      bot_difficulty: "basic",
                    },
                    {
                      onSuccess: (payload) => {
                        const roomPath = getMockDraftCreateSuccessRoomPath(payload);
                        if (roomPath) {
                          navigate(roomPath);
                          return;
                        }
                        setCreatedDraft(payload);
                      },
                    }
                  );
                }
              }
            >
              {createMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CalendarClock className="mr-2 h-4 w-4" />}
              Create Draft
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
