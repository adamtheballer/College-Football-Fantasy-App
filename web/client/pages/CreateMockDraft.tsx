import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CalendarClock, CheckCircle2, ClipboardList, Loader2, TimerReset, Users } from "lucide-react";

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

const MOCK_ROSTER_SLOTS = [
  { label: "QB", count: 1 },
  { label: "RB", count: 2 },
  { label: "WR", count: 2 },
  { label: "TE", count: 1 },
  { label: "FLEX", count: 1 },
  { label: "K", count: 1 },
  { label: "BENCH", count: 5 },
] as const;
const MOCK_ROSTER_ROUNDS = MOCK_ROSTER_SLOTS.reduce((sum, slot) => sum + slot.count, 0);
const selectTriggerClass =
  "h-12 rounded-[1.15rem] border-cyan-200/15 bg-slate-950/35 px-4 text-[12px] font-black uppercase tracking-[0.12em] shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_0_24px_rgba(34,211,238,0.06)] transition-all hover:border-cyan-200/30 hover:bg-cyan-400/[0.08] focus:border-cyan-200/45";
const selectItemClass = "py-2 text-[12px] font-black uppercase tracking-[0.1em]";

const toLocalDateTimeInput = (date: Date) => {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

const formatCreateMockDraftError = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Please sign in to create a mock draft.";
    if (error.status === 0) return "Backend server is offline. Start FastAPI and try again.";
    return error.message;
  }
  if (error instanceof TypeError && error.message.toLowerCase().includes("fetch")) {
    return "Backend server is offline. Start FastAPI and try again.";
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
  const [pickTimer, setPickTimer] = useState<"30" | "60" | "90" | "120">("30");
  const [scheduledStart, setScheduledStart] = useState(() => toLocalDateTimeInput(new Date(Date.now() + 5 * 60_000)));
  const [createdDraft, setCreatedDraft] = useState<StandaloneMockDraftCreateResponse | null>(null);

  const scheduledDate = useMemo(() => new Date(scheduledStart), [scheduledStart]);
  const isFuture = Number.isFinite(scheduledDate.getTime()) && scheduledDate.getTime() > Date.now();
  const canSubmit = name.trim().length > 0 && (isSinglePlayerIntent || isFuture) && !createMutation.isPending;
  const totalPicks = Number(teamCount) * MOCK_ROSTER_ROUNDS;

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
    <div className="cfb-ui-font mx-auto max-w-4xl py-8">
      <Card className="relative overflow-hidden rounded-[2.75rem] border-cyan-200/10 bg-card/50 shadow-[0_30px_90px_rgba(7,13,30,0.35)]">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-cyan-300/12 blur-[90px]" />
        <div className="pointer-events-none absolute -bottom-28 left-8 h-72 w-96 rounded-full bg-blue-500/10 blur-[100px]" />
        <CardHeader className="relative space-y-4 pb-4">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2">
            <ClipboardList className="h-3.5 w-3.5 text-cyan-100" />
            <span className="text-[10px] font-black uppercase tracking-[0.28em] text-primary">Mock Draft Setup</span>
          </div>
          <div>
            <CardTitle className="cfb-display-font text-4xl uppercase text-foreground md:text-5xl">
              Create Mock Draft
            </CardTitle>
            <p className="mt-3 max-w-2xl text-sm font-semibold leading-6 tracking-[-0.015em] text-slate-300/85 md:text-base">
              Mock drafts are standalone. Rounds are locked to the roster size so every team fills a full lineup.
            </p>
          </div>
        </CardHeader>
        <CardContent className="relative space-y-5">
          <div className="space-y-2">
            <Label className="cfb-label-font">Name</Label>
            <Input
              className="cfb-control-font h-14 rounded-[1.35rem] border-cyan-200/15 bg-slate-950/35 px-5 text-base font-black tracking-[-0.02em]"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
            />
          </div>
          <div className={`grid gap-4 ${isSinglePlayerIntent ? "md:grid-cols-2" : "md:grid-cols-3"}`}>
            <div className="space-y-3 rounded-[1.5rem] border border-cyan-200/10 bg-slate-950/25 p-4">
              <Label className="cfb-label-font flex items-center gap-2"><Users className="h-3.5 w-3.5 text-cyan-200" /> Teams</Label>
              <Select value={teamCount} onValueChange={(value: "4" | "6" | "8" | "10" | "12") => setTeamCount(value)}>
                <SelectTrigger className={selectTriggerClass}><SelectValue /></SelectTrigger>
                <SelectContent className="border-cyan-200/15 bg-slate-950/95">
                  {[4, 6, 8, 10, 12].map((value) => <SelectItem className={selectItemClass} key={value} value={String(value)}>{value} Teams</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {!isSinglePlayerIntent ? (
              <div className="rounded-[1.5rem] border border-emerald-300/15 bg-emerald-400/[0.08] p-4">
                <Label className="cfb-label-font flex items-center gap-2"><ClipboardList className="h-3.5 w-3.5 text-emerald-200" /> Roster Fill</Label>
                <div className="h-14 rounded-[1.35rem] border border-emerald-300/20 bg-slate-950/35 px-4 py-3">
                  <p className="text-sm font-black uppercase tracking-[0.16em] text-foreground">{MOCK_ROSTER_ROUNDS} Rounds Locked</p>
                  <p className="mt-1 text-[9px] font-black uppercase tracking-[0.18em] text-emerald-100/70">{totalPicks} total picks</p>
                </div>
              </div>
            ) : null}
            <div className="space-y-3 rounded-[1.5rem] border border-cyan-200/10 bg-slate-950/25 p-4">
              <Label className="cfb-label-font flex items-center gap-2"><TimerReset className="h-3.5 w-3.5 text-cyan-200" /> Pick Timer</Label>
              <Select value={pickTimer} onValueChange={(value: "30" | "60" | "90" | "120") => setPickTimer(value)}>
                <SelectTrigger className={selectTriggerClass}><SelectValue /></SelectTrigger>
                <SelectContent className="border-cyan-200/15 bg-slate-950/95">
                  {[30, 60, 90, 120].map((value) => <SelectItem className={selectItemClass} key={value} value={String(value)}>{value}s Clock</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-2 rounded-[1.5rem] border border-white/10 bg-white/[0.035] p-4 sm:grid-cols-7">
            {MOCK_ROSTER_SLOTS.map((slot) => (
              <div key={slot.label} className="rounded-2xl border border-white/10 bg-slate-950/25 px-3 py-2 text-center">
                <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">{slot.label}</p>
                <p className="mt-1 text-lg font-black text-cyan-100">{slot.count}</p>
              </div>
            ))}
          </div>
          {isSinglePlayerIntent ? (
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-[1.35rem] border border-cyan-200/15 bg-cyan-400/[0.06] p-4">
                <p className="text-[9px] font-black uppercase tracking-[0.22em] text-cyan-100/70">Draft Order</p>
                <p className="mt-2 text-sm font-black uppercase tracking-[0.08em] text-foreground">Random reveal</p>
              </div>
              <div className="rounded-[1.35rem] border border-blue-300/15 bg-blue-500/[0.06] p-4">
                <p className="text-[9px] font-black uppercase tracking-[0.22em] text-blue-100/70">CPU Managers</p>
                <p className="mt-2 text-sm font-black uppercase tracking-[0.08em] text-foreground">{Number(teamCount) - 1} bots fill seats</p>
              </div>
              <div className="rounded-[1.35rem] border border-emerald-300/15 bg-emerald-400/[0.06] p-4">
                <p className="text-[9px] font-black uppercase tracking-[0.22em] text-emerald-100/70">Draft Size</p>
                <p className="mt-2 text-sm font-black uppercase tracking-[0.08em] text-foreground">{MOCK_ROSTER_ROUNDS} rounds • {totalPicks} picks</p>
              </div>
              <div className="rounded-[1.35rem] border border-violet-300/15 bg-violet-400/[0.06] p-4">
                <p className="text-[9px] font-black uppercase tracking-[0.22em] text-violet-100/70">Start Flow</p>
                <p className="mt-2 text-sm font-black uppercase tracking-[0.08em] text-foreground">90s countdown</p>
              </div>
            </div>
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
	                      round_count: MOCK_ROSTER_ROUNDS,
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
