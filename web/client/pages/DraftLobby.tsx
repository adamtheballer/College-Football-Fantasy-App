import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertTriangle, CalendarClock, CheckCircle2, Clock, Copy, Link2, Lock, RefreshCw, Users, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import {
  useLeagueDetail,
  useRescheduleDraft,
  useRevokeLeagueInvite,
  useRotateLeagueInvite,
  useUpdateDraftOrder,
} from "@/hooks/use-leagues";
import { useDraftPlayerPool } from "@/hooks/use-players";
import { CFB27_RATINGS } from "@/lib/cfb27Ratings";
import {
  canJoinDraftRoom,
  formatDraftCountdown,
  getDraftCountdownParts,
  hasDraftStarted,
} from "@/lib/draftStatus";
import {
  formatLeagueDraftDateTime,
  getLeagueTimezoneLabel,
  leagueLocalDateTimeToUtc,
  toLeagueDateTimeLocalValue,
} from "@/lib/draftSchedule";

const getErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Unable to reschedule draft.";
};

export default function DraftLobby() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const parsedLeagueId =
    leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;
  const { data: league, error, isLoading, refetch: refetchLeague } = useLeagueDetail(parsedLeagueId);
  const rescheduleDraft = useRescheduleDraft(parsedLeagueId);
  const updateDraftOrder = useUpdateDraftOrder(parsedLeagueId);
  const rotateInvite = useRotateLeagueInvite(parsedLeagueId);
  const revokeInvite = useRevokeLeagueInvite(parsedLeagueId);
  const [now, setNow] = useState(Date.now());
  const [showReschedule, setShowReschedule] = useState(false);
  const [draftDate, setDraftDate] = useState("");
  const [draftClockTime, setDraftClockTime] = useState("");
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);
  const [rescheduleSuccess, setRescheduleSuccess] = useState<string | null>(null);
  const [draftOrderMode, setDraftOrderMode] = useState<"random" | "custom">("random");
  const [draftOrderBySlot, setDraftOrderBySlot] = useState<Record<number, number | null>>({});
  const [draftOrderError, setDraftOrderError] = useState<string | null>(null);
  const [draftOrderSuccess, setDraftOrderSuccess] = useState<string | null>(null);
  const [dismissedPoolWarning, setDismissedPoolWarning] = useState(false);
  const [copiedInviteField, setCopiedInviteField] = useState<"code" | "link" | null>(null);
  const [inviteActionError, setInviteActionError] = useState<string | null>(null);
  const playerPoolQuery = useDraftPlayerPool({
    limit: 100,
    offset: 0,
    pages: 1,
    sort: "draft_rank",
    enabled: typeof parsedLeagueId === "number" && Number.isFinite(parsedLeagueId),
  });

  const draftTime = league?.draft?.draft_datetime_utc ? new Date(league.draft.draft_datetime_utc) : null;

  useEffect(() => {
    const localValue = toLeagueDateTimeLocalValue(
      league?.draft?.draft_datetime_utc,
      league?.draft?.timezone || "UTC",
    );
    const [nextDate = "", nextTime = ""] = localValue.split("T");
    setDraftDate(nextDate);
    setDraftClockTime(nextTime);
  }, [league?.draft?.draft_datetime_utc, league?.draft?.timezone]);

  useEffect(() => {
    const order = league?.draft_order;
    if (!order) return;
    const next: Record<number, number | null> = {};
    for (let position = 1; position <= order.max_teams; position += 1) next[position] = null;
    for (const entry of order.entries) {
      if (entry.draft_position) next[entry.draft_position] = entry.team_id;
    }
    setDraftOrderMode(order.draft_order_mode);
    setDraftOrderBySlot(next);
  }, [league?.draft_order]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    // A lobby can stay open for days. Poll the authoritative league schedule so a
    // commissioner change is reflected for every connected member without relying
    // on a browser-local countdown or an unavailable socket connection.
    const interval = window.setInterval(() => {
      void refetchLeague();
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [refetchLeague]);

  const countdown = useMemo(() => {
    return formatDraftCountdown(draftTime, now);
  }, [draftTime, now]);

  const countdownParts = useMemo(() => getDraftCountdownParts(draftTime, now), [draftTime, now]);

  const canEnterDraft = useMemo(() => {
    return hasDraftStarted(draftTime, now);
  }, [draftTime, now]);

  const isFull = league ? league.members.length >= league.max_teams : false;
  const missingManagers = league ? Math.max(0, league.max_teams - league.members.length) : 0;
  const isCommissioner = Boolean(league && user?.id === league.commissioner_user_id);
  const canReschedule = Boolean(
    isCommissioner &&
      league?.draft?.status === "scheduled" &&
      ["pre_draft", "scheduled"].includes(league.status),
  );
  const canEditDraftOrder = canReschedule;
  const expectedPlayerCount = CFB27_RATINGS.length;
  const loadedPlayerCount = playerPoolQuery.data?.total ?? 0;
  const playerPoolComplete = !playerPoolQuery.isLoading && loadedPlayerCount >= expectedPlayerCount;
  const showPlayerPoolWarning =
    !playerPoolQuery.isLoading &&
    !playerPoolComplete &&
    !dismissedPoolWarning &&
    Boolean(parsedLeagueId);

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

  const draftRoomPath = `/league/${league.id}/draft`;
  const draftIsReadyToCommence = canJoinDraftRoom({
    draftDateTime: draftTime,
    memberCount: league.members.length,
    maxTeams: league.max_teams,
    now,
  });

  const handleRescheduleDraft = async () => {
    if (!draftDate || !draftClockTime) {
      setRescheduleError("Choose a valid draft date and time.");
      return;
    }

    const nextDraftTime = leagueLocalDateTimeToUtc(
      `${draftDate}T${draftClockTime}`,
      league.draft?.timezone || "UTC",
    );
    if ("error" in nextDraftTime) {
      setRescheduleError(nextDraftTime.error);
      return;
    }

    setRescheduleError(null);
    try {
      await rescheduleDraft.mutateAsync({
        draft_datetime_utc: nextDraftTime.iso,
        timezone: league.draft?.timezone || "UTC",
        draft_type: league.draft?.draft_type || "snake",
        pick_timer_seconds: league.draft?.pick_timer_seconds || 90,
        status: "scheduled",
      });
      setShowReschedule(false);
      setRescheduleSuccess("Draft time updated. All league members will see the new countdown.");
    } catch (error) {
      setRescheduleError(getErrorMessage(error));
    }
  };

  const saveDraftOrder = async () => {
    if (!league?.draft_order) return;
    setDraftOrderError(null);
    setDraftOrderSuccess(null);
    const entries = Object.entries(draftOrderBySlot)
      .filter(([, teamId]) => typeof teamId === "number")
      .map(([position, teamId]) => ({ team_id: teamId as number, draft_position: Number(position) }));
    try {
      await updateDraftOrder.mutateAsync({ draft_order_mode: draftOrderMode, entries });
      setDraftOrderSuccess(
        draftOrderMode === "custom"
          ? "Draft order saved. Fill every slot before starting the draft."
          : "Random order selected. The order will be generated once when the full draft starts.",
      );
    } catch (orderError) {
      setDraftOrderError(getErrorMessage(orderError));
    }
  };

  const activeInviteCode = isCommissioner ? league.invite_code : null;
  const activeInviteLink = activeInviteCode ? `${window.location.origin}/join/${activeInviteCode}` : null;

  const copyInviteValue = async (field: "code" | "link", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedInviteField(field);
      window.setTimeout(() => setCopiedInviteField(null), 2_000);
    } catch {
      setInviteActionError("Unable to copy the invite. Select the code or link and copy it manually.");
    }
  };

  const handleRotateInvite = async () => {
    setInviteActionError(null);
    try {
      await rotateInvite.mutateAsync();
    } catch (inviteError) {
      setInviteActionError(getErrorMessage(inviteError));
    }
  };

  const handleRevokeInvite = async () => {
    setInviteActionError(null);
    try {
      await revokeInvite.mutateAsync();
    } catch (inviteError) {
      setInviteActionError(getErrorMessage(inviteError));
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-12 space-y-10">
      <Dialog open={showPlayerPoolWarning} onOpenChange={(open) => setDismissedPoolWarning(!open)}>
        <DialogContent className="max-w-xl border-amber-300/20 bg-[#101928]">
          <DialogHeader>
            <DialogTitle className="pr-8 text-2xl font-black uppercase italic text-amber-100">
              Draft player pool is not ready
            </DialogTitle>
            <DialogDescription className="text-sm font-semibold leading-6 text-slate-300">
              This draft has {loadedPlayerCount} backend players available, but the CFB27 draft
              board expects at least {expectedPlayerCount}. Reschedule the draft so the player
              sync can finish before managers enter the room.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 sm:flex-row">
            {canReschedule ? (
              <Button
                type="button"
                className="h-11 rounded-2xl bg-amber-300 px-5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-950 hover:bg-amber-200"
                onClick={() => {
                  setDismissedPoolWarning(true);
                  setShowReschedule(true);
                }}
              >
                Reschedule Draft
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => setDismissedPoolWarning(true)}
            >
              Review Lobby
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={showReschedule && canReschedule}
        onOpenChange={(open) => {
          setShowReschedule(open);
          if (open) {
            setRescheduleError(null);
            setRescheduleSuccess(null);
          }
        }}
      >
        <DialogContent className="max-w-xl border-sky-300/20 bg-[#101928]">
          <DialogHeader>
            <DialogTitle className="pr-8 text-2xl font-black uppercase italic text-slate-50">
              Update Draft Time
            </DialogTitle>
            <DialogDescription className="text-sm font-semibold leading-6 text-slate-300">
              All league members will see the updated draft time.
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              void handleRescheduleDraft();
            }}
          >
            <div className="rounded-2xl border border-white/10 bg-black/15 p-4 text-sm">
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">Current schedule</p>
              <p className="mt-2 font-black text-slate-50">
                {formatLeagueDraftDateTime(draftTime, league.draft?.timezone || "UTC")}
              </p>
              <p className="mt-1 text-xs font-semibold text-sky-200">
                {getLeagueTimezoneLabel(league.draft?.timezone || "UTC")}
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2" htmlFor="draft-reschedule-date">
                <span className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">New date</span>
                <Input
                  id="draft-reschedule-date"
                  type="date"
                  value={draftDate}
                  onChange={(event) => setDraftDate(event.target.value)}
                  className="h-12 rounded-2xl border-white/10 bg-white/5 text-sm font-bold"
                  required
                />
              </label>
              <label className="grid gap-2" htmlFor="draft-reschedule-time">
                <span className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">New time</span>
                <Input
                  id="draft-reschedule-time"
                  type="time"
                  value={draftClockTime}
                  onChange={(event) => setDraftClockTime(event.target.value)}
                  className="h-12 rounded-2xl border-white/10 bg-white/5 text-sm font-bold"
                  required
                />
              </label>
            </div>
            <p className="text-xs font-semibold text-slate-400">
              Times are saved in {getLeagueTimezoneLabel(league.draft?.timezone || "UTC")} and stored securely in UTC.
            </p>
            {rescheduleError ? <p role="alert" className="text-sm font-bold text-red-300">{rescheduleError}</p> : null}
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                className="h-11 rounded-2xl text-[10px] font-black uppercase tracking-[0.18em]"
                onClick={() => setShowReschedule(false)}
                disabled={rescheduleDraft.isPending}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="h-11 rounded-2xl bg-primary px-5 text-[10px] font-black uppercase tracking-[0.18em] text-primary-foreground"
                disabled={rescheduleDraft.isPending}
              >
                {rescheduleDraft.isPending ? "Saving..." : "Save New Draft Time"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <div className="space-y-3">
        <h1 className="text-6xl font-black italic uppercase text-foreground">{league.name}</h1>
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-[0.2em]">
          Draft Lobby • {league.members.length}/{league.max_teams} members
        </p>
      </div>

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="flex flex-col gap-4 px-10 pt-10 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Draft Countdown</CardTitle>
          {canReschedule ? (
            <Button
              type="button"
              variant="outline"
              className="h-11 rounded-2xl border-sky-200/25 bg-sky-300/10 px-5 text-[10px] font-black uppercase tracking-[0.2em] text-sky-100 hover:bg-sky-300/15"
              onClick={() => {
                setRescheduleError(null);
                setRescheduleSuccess(null);
                setShowReschedule(true);
              }}
            >
              <CalendarClock className="mr-2 h-4 w-4" />
              Reschedule Draft
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="px-10 pb-10 space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-white/5 border border-white/10 md:col-span-2">
              <Clock className="w-6 h-6 text-primary" />
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">Starts In</p>
                <p className="whitespace-nowrap text-[clamp(1.35rem,6vw,2rem)] font-black tabular-nums text-foreground">{countdown}</p>
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
          {countdownParts && countdownParts.totalMs > 0 ? (
            <div data-testid="draft-countdown-units" className="grid grid-cols-4 gap-2 sm:gap-3">
              {[
                { label: "Days", compactLabel: "DAYS", value: countdownParts.days },
                { label: "Hours", compactLabel: "HRS", value: countdownParts.hours },
                { label: "Minutes", compactLabel: "MIN", value: countdownParts.minutes },
                { label: "Seconds", compactLabel: "SEC", value: countdownParts.seconds },
              ].map(({ label, compactLabel, value }) => (
                <div key={label} className="min-w-0 rounded-2xl border border-white/10 bg-black/15 px-2 py-3 text-center sm:p-4">
                  <p className="whitespace-nowrap text-[clamp(1.55rem,8.5vw,1.875rem)] font-black leading-none tabular-nums text-slate-50">{value}</p>
                  <p aria-label={label} className="mt-2 whitespace-nowrap text-[8px] font-black uppercase tracking-[0.08em] text-slate-500 sm:text-[9px] sm:tracking-[0.18em]">
                    <span className="sm:hidden">{compactLabel}</span>
                    <span className="hidden sm:inline">{label}</span>
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="space-y-2 text-sm font-bold uppercase tracking-[0.2em] text-muted-foreground">
            <p>Draft Order: {league.draft_order?.draft_order_mode === "custom" ? "Commissioner set" : "Random at start"}</p>
            <p>Timezone: {getLeagueTimezoneLabel(league.draft?.timezone || "UTC")}</p>
            <p>Draft Time: {formatLeagueDraftDateTime(draftTime, league.draft?.timezone || "UTC")}</p>
          </div>
          {rescheduleSuccess ? <p role="status" className="text-sm font-bold text-emerald-300">{rescheduleSuccess}</p> : null}
        </CardContent>
      </Card>

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="px-10 pt-10">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Draft Order</CardTitle>
          <p className="text-sm font-medium text-muted-foreground">
            {league.draft_order?.draft_order_mode === "custom"
              ? "The commissioner can build this order as managers join. Empty slots are allowed now, but every slot must be filled before the draft starts."
              : "A secure random order will be created once, when the league is full and the commissioner starts the draft."}
          </p>
        </CardHeader>
        <CardContent className="space-y-5 px-10 pb-10">
          {canEditDraftOrder ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <Button
                  type="button"
                  variant={draftOrderMode === "random" ? "default" : "outline"}
                  className="h-auto min-h-16 justify-start rounded-2xl px-5 py-4 text-left"
                  onClick={() => setDraftOrderMode("random")}
                >
                  <span><span className="block text-xs font-black uppercase tracking-[0.18em]">Random order</span><span className="mt-1 block text-xs font-medium normal-case">Generated once at draft start.</span></span>
                </Button>
                <Button
                  type="button"
                  variant={draftOrderMode === "custom" ? "default" : "outline"}
                  className="h-auto min-h-16 justify-start rounded-2xl px-5 py-4 text-left"
                  onClick={() => setDraftOrderMode("custom")}
                >
                  <span><span className="block text-xs font-black uppercase tracking-[0.18em]">Custom order</span><span className="mt-1 block text-xs font-medium normal-case">Assign joined managers as they arrive.</span></span>
                </Button>
              </div>

              {draftOrderMode === "custom" && league.draft_order ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {Array.from({ length: league.draft_order.max_teams }, (_, index) => index + 1).map((slot) => {
                    const selectedTeamId = draftOrderBySlot[slot];
                    const usedTeamIds = new Set(
                      Object.entries(draftOrderBySlot)
                        .filter(([position, teamId]) => Number(position) !== slot && typeof teamId === "number")
                        .map(([, teamId]) => teamId as number),
                    );
                    return (
                      <label key={slot} className="rounded-2xl border border-white/10 bg-black/15 p-4">
                        <span className="mb-2 block text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">Pick {slot}</span>
                        <Select
                          value={selectedTeamId ? String(selectedTeamId) : `unassigned-${slot}`}
                          onValueChange={(value) => {
                            setDraftOrderBySlot((current) => ({
                              ...current,
                              [slot]: value.startsWith("unassigned-") ? null : Number(value),
                            }));
                          }}
                        >
                          <SelectTrigger className="h-11 rounded-xl border-white/10 bg-white/5 text-sm font-bold">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={`unassigned-${slot}`}>Open slot</SelectItem>
                            {league.draft_order.entries
                              .filter((entry) => entry.team_id === selectedTeamId || !usedTeamIds.has(entry.team_id))
                              .map((entry) => (
                                <SelectItem key={entry.team_id} value={String(entry.team_id)}>
                                  {entry.owner_name || entry.team_name}
                                </SelectItem>
                              ))}
                          </SelectContent>
                        </Select>
                      </label>
                    );
                  })}
                </div>
              ) : null}

              {draftOrderError ? <p role="alert" className="text-sm font-bold text-red-300">{draftOrderError}</p> : null}
              {draftOrderSuccess ? <p role="status" className="text-sm font-bold text-emerald-300">{draftOrderSuccess}</p> : null}
              <Button
                type="button"
                className="h-11 rounded-2xl px-5 text-[10px] font-black uppercase tracking-[0.18em]"
                onClick={() => void saveDraftOrder()}
                disabled={updateDraftOrder.isPending}
              >
                {updateDraftOrder.isPending ? "Saving..." : "Save Draft Order"}
              </Button>
            </>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-black/15 p-5 text-sm font-semibold text-slate-300">
              {league.draft_order?.entries.some((entry) => entry.draft_position)
                ? league.draft_order.entries
                    .filter((entry) => entry.draft_position)
                    .sort((left, right) => (left.draft_position || 0) - (right.draft_position || 0))
                    .map((entry) => `Pick ${entry.draft_position}: ${entry.owner_name || entry.team_name}`)
                    .join(" · ")
                : "Draft order has not been assigned yet."}
            </div>
          )}
        </CardContent>
      </Card>

      {isCommissioner ? (
        <Card className="border-amber-300/20 bg-amber-300/[0.06] rounded-[2.5rem]">
          <CardHeader className="px-10 pt-10">
            <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Invite Recovery</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 px-10 pb-10">
            {activeInviteCode && activeInviteLink ? (
              <>
                <div className="grid gap-3 rounded-2xl border border-white/10 bg-black/15 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                  <div className="min-w-0">
                    <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">Invite Code</p>
                    <p className="mt-1 break-all font-mono text-lg font-black text-slate-50">{activeInviteCode}</p>
                  </div>
                  <Button type="button" variant="outline" className="h-11 rounded-xl text-[10px] font-black uppercase tracking-[0.16em]" onClick={() => void copyInviteValue("code", activeInviteCode)}>
                    <Copy className="mr-2 h-4 w-4" />
                    {copiedInviteField === "code" ? "Copied" : "Copy Code"}
                  </Button>
                </div>
                <div className="grid gap-3 rounded-2xl border border-white/10 bg-black/15 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                  <div className="min-w-0">
                    <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">Invite Link</p>
                    <p className="mt-1 break-all font-mono text-xs font-bold text-slate-300">{activeInviteLink}</p>
                  </div>
                  <Button type="button" variant="outline" className="h-11 rounded-xl text-[10px] font-black uppercase tracking-[0.16em]" onClick={() => void copyInviteValue("link", activeInviteLink)}>
                    <Link2 className="mr-2 h-4 w-4" />
                    {copiedInviteField === "link" ? "Copied" : "Copy Link"}
                  </Button>
                </div>
              </>
            ) : (
              <p className="rounded-2xl border border-white/10 bg-black/15 p-4 text-sm font-semibold leading-6 text-slate-300">
                This league does not have an active invite. Generate a new secure invite when you are ready to add a manager.
              </p>
            )}
            <div className="flex flex-wrap gap-3">
              <Button type="button" variant="outline" className="h-11 rounded-xl text-[10px] font-black uppercase tracking-[0.16em]" onClick={() => void handleRotateInvite()} disabled={rotateInvite.isPending}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {rotateInvite.isPending ? "Generating..." : activeInviteCode ? "Rotate Invite" : "Generate Invite"}
              </Button>
              {activeInviteCode ? (
                <Button type="button" variant="outline" className="h-11 rounded-xl border-red-300/25 text-[10px] font-black uppercase tracking-[0.16em] text-red-200 hover:bg-red-400/10" onClick={() => void handleRevokeInvite()} disabled={revokeInvite.isPending}>
                  {revokeInvite.isPending ? "Revoking..." : "Revoke Invite"}
                </Button>
              ) : null}
            </div>
            {inviteActionError ? <p className="text-[11px] font-bold text-red-300">{inviteActionError}</p> : null}
          </CardContent>
        </Card>
      ) : null}

      <Card
        className={[
          "border-border/60 rounded-[2.5rem]",
          draftIsReadyToCommence
            ? "bg-emerald-400/10 border-emerald-300/25"
            : "bg-card/40",
        ].join(" ")}
      >
        <CardContent className="flex flex-col gap-5 p-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
              {draftIsReadyToCommence ? (
                <CheckCircle2 className="h-6 w-6 text-emerald-300" />
              ) : (
                <Lock className="h-6 w-6 text-sky-300" />
              )}
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.28em] text-sky-300">
                Draft Room
              </p>
              <h2 className="mt-1 text-2xl font-black uppercase italic text-slate-50">
                {draftIsReadyToCommence ? "Ready to join" : "Locked until draft kickoff"}
              </h2>
              <p className="mt-2 text-sm font-semibold leading-6 text-slate-400">
                {!isFull
                  ? `${missingManagers} more ${missingManagers === 1 ? "manager needs" : "managers need"} to join before the room unlocks.`
                  : canEnterDraft
                      ? "The scheduled time has arrived. League members can enter the draft room."
                      : "Managers can view this lobby now. The join button unlocks when the scheduled draft time arrives."}
              </p>
            </div>
          </div>
          <Button
            className="h-12 rounded-2xl bg-primary px-8 text-[10px] font-black uppercase tracking-[0.2em] text-primary-foreground disabled:cursor-not-allowed disabled:opacity-45"
            disabled={!draftIsReadyToCommence}
            onClick={() => navigate(draftRoomPath)}
          >
            {draftIsReadyToCommence ? "Join Draft Room" : "Draft Room Locked"}
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
        <CardHeader className="px-10 pt-10">
          <CardTitle className="text-xl font-black uppercase tracking-[0.2em]">Participants</CardTitle>
        </CardHeader>
        <CardContent className="px-10 pb-10 space-y-4">
          {!isFull && (
            <div className="rounded-[2rem] border border-amber-300/20 bg-amber-400/10 p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex gap-4">
                  <AlertTriangle className="mt-1 h-5 w-5 shrink-0 text-amber-300" />
                  <div className="space-y-2">
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-amber-300">
                      Draft locked until league is full
                    </p>
                    <p className="text-sm font-bold leading-6 text-amber-50/90">
                      {league.members.length}/{league.max_teams} managers have joined. The draft cannot commence
                      until {missingManagers} more {missingManagers === 1 ? "manager joins" : "managers join"}.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
          {league.members.map((member) => (
            <div key={member.id} className="flex items-center justify-between px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
              <span className="text-sm font-black uppercase tracking-[0.2em] text-foreground">User {member.user_id}</span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{member.role}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      {(!isFull || !canEnterDraft) && (
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground/70">
          Draft room access stays locked until the league is full and the scheduled draft time has arrived.
        </p>
      )}

      <div className="flex items-center gap-4">
        <Button
          className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em] disabled:cursor-not-allowed disabled:opacity-45"
          disabled={!draftIsReadyToCommence}
          onClick={() => navigate(draftRoomPath)}
        >
          {draftIsReadyToCommence ? "Join Draft Room" : "Draft Room Locked"}
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
