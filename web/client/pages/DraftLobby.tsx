import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertTriangle, CalendarClock, CheckCircle2, Clock, Copy, Link2, Lock, RefreshCw, Users, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
} from "@/hooks/use-leagues";
import { useDraftPlayerPool } from "@/hooks/use-players";
import { CFB27_RATINGS } from "@/lib/cfb27Ratings";
import {
  canJoinDraftRoom,
  formatDraftCountdown,
  getDraftCountdownParts,
  hasDraftStarted,
} from "@/lib/draftStatus";

const toDateTimeLocalValue = (date: Date | null) => {
  if (!date || Number.isNaN(date.getTime())) return "";
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
};

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
  const { data: league, error, isLoading } = useLeagueDetail(parsedLeagueId);
  const rescheduleDraft = useRescheduleDraft(parsedLeagueId);
  const rotateInvite = useRotateLeagueInvite(parsedLeagueId);
  const revokeInvite = useRevokeLeagueInvite(parsedLeagueId);
  const [now, setNow] = useState(Date.now());
  const [showReschedule, setShowReschedule] = useState(false);
  const [draftDateTime, setDraftDateTime] = useState("");
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);
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
    setDraftDateTime(toDateTimeLocalValue(draftTime));
  }, [draftTime]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(interval);
  }, []);

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
    const nextDraftTime = draftDateTime ? new Date(draftDateTime) : null;
    if (!nextDraftTime || Number.isNaN(nextDraftTime.getTime())) {
      setRescheduleError("Choose a valid draft date and time.");
      return;
    }

    setRescheduleError(null);
    try {
      await rescheduleDraft.mutateAsync({
        draft_datetime_utc: nextDraftTime.toISOString(),
        timezone: league.draft?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        draft_type: league.draft?.draft_type || "snake",
        pick_timer_seconds: league.draft?.pick_timer_seconds || 90,
        status: "scheduled",
      });
      setShowReschedule(false);
    } catch (error) {
      setRescheduleError(getErrorMessage(error));
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
            {isCommissioner ? (
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
          <div className="grid gap-4 md:grid-cols-4">
            <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-white/5 border border-white/10 md:col-span-2">
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
          {countdownParts && countdownParts.totalMs > 0 ? (
            <div className="grid grid-cols-4 gap-3">
              {[
                ["Days", countdownParts.days],
                ["Hours", countdownParts.hours],
                ["Minutes", countdownParts.minutes],
                ["Seconds", countdownParts.seconds],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-white/10 bg-black/15 p-4 text-center">
                  <p className="text-3xl font-black text-slate-50">{value}</p>
                  <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-slate-500">{label}</p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="space-y-2 text-sm font-bold uppercase tracking-[0.2em] text-muted-foreground">
            <p>Draft Order: Pending</p>
            <p>Timezone: {league.draft?.timezone}</p>
            <p>Draft Time: {draftTime?.toLocaleString()}</p>
          </div>
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
                {isCommissioner ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 shrink-0 rounded-2xl border-amber-200/25 bg-amber-300/10 px-5 text-[10px] font-black uppercase tracking-[0.2em] text-amber-100 hover:bg-amber-300/15"
                    onClick={() => setShowReschedule((current) => !current)}
                  >
                    <CalendarClock className="mr-2 h-4 w-4" />
                    Reschedule Draft
                  </Button>
                ) : null}
              </div>

              {showReschedule && isCommissioner ? (
                <form
                  className="mt-5 grid gap-3 rounded-2xl border border-white/10 bg-black/15 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleRescheduleDraft();
                  }}
                >
                  <label className="grid gap-2">
                    <span className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                      New Draft Time
                    </span>
                    <Input
                      type="datetime-local"
                      value={draftDateTime}
                      onChange={(event) => setDraftDateTime(event.target.value)}
                      className="h-12 rounded-2xl border-white/10 bg-white/5 text-sm font-bold"
                    />
                  </label>
                  <Button
                    type="submit"
                    className="h-12 rounded-2xl bg-primary px-6 text-[10px] font-black uppercase tracking-[0.2em] text-primary-foreground"
                    disabled={rescheduleDraft.isPending}
                  >
                    {rescheduleDraft.isPending ? "Saving..." : "Save New Time"}
                  </Button>
                  {rescheduleError ? (
                      <p className="text-[11px] font-bold text-red-300 md:col-span-2">{rescheduleError}</p>
                  ) : null}
                </form>
              ) : null}
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
