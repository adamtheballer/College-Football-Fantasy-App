import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertTriangle, CalendarClock, Clock, Users, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { useLeagueDetail, useRescheduleDraft } from "@/hooks/use-leagues";

const DRAFT_STARTED_DRAFT_STATUSES = new Set(["live", "paused", "completed", "complete"]);
const DRAFT_STARTED_LEAGUE_STATUSES = new Set([
  "draft_live",
  "post_draft",
  "playoffs",
  "completed",
  "archived",
]);

const normalizeStatus = (status: string | undefined | null) => status?.trim().toLowerCase() ?? "";

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

const getMemberDisplayName = (member: {
  user_id: number;
  first_name?: string | null;
  display_name?: string | null;
}) => {
  const displayName = member.display_name?.trim() || member.first_name?.trim();
  return displayName || `Manager ${member.user_id}`;
};

export default function DraftLobby() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const parsedLeagueId =
    leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;
  const { data: league, error, isLoading } = useLeagueDetail(parsedLeagueId);
  const rescheduleDraft = useRescheduleDraft(parsedLeagueId);
  const [now, setNow] = useState(Date.now());
  const [showReschedule, setShowReschedule] = useState(false);
  const [draftDateTime, setDraftDateTime] = useState("");
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);
  const [rescheduleSuccess, setRescheduleSuccess] = useState<string | null>(null);

  const draftTime = league?.draft?.draft_datetime_utc ? new Date(league.draft.draft_datetime_utc) : null;

  useEffect(() => {
    setDraftDateTime(toDateTimeLocalValue(draftTime));
  }, [draftTime]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  const countdown = useMemo(() => {
    if (!draftTime) return "--";
    const diff = draftTime.getTime() - now;
    const hours = Math.max(0, Math.floor(diff / (1000 * 60 * 60)));
    const minutes = Math.max(0, Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)));
    return `${hours}h ${minutes}m`;
  }, [draftTime, now]);

  const canEnterDraft = useMemo(() => {
    if (!draftTime) return false;
    const diff = draftTime.getTime() - now;
    return diff <= 15 * 60 * 1000;
  }, [draftTime, now]);

  const isFull = league ? league.members.length >= league.max_teams : false;
  const missingManagers = league ? Math.max(0, league.max_teams - league.members.length) : 0;
  const isCommissioner = Boolean(league && user?.id === league.commissioner_user_id);
  const draftStatus = normalizeStatus(league?.draft?.status);
  const leagueStatus = normalizeStatus(league?.status);
  const draftHasStarted =
    DRAFT_STARTED_DRAFT_STATUSES.has(draftStatus) ||
    (!draftStatus && DRAFT_STARTED_LEAGUE_STATUSES.has(leagueStatus));
  const canRescheduleDraft = isCommissioner && !draftHasStarted;

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
  const draftIsReadyToCommence = isFull && canEnterDraft;

  const handleRescheduleDraft = async () => {
    if (rescheduleDraft.isPending) return;

    if (!canRescheduleDraft) {
      setRescheduleSuccess(null);
      setRescheduleError("Draft time can only be changed by the commissioner before the draft starts.");
      return;
    }

    const nextDraftTime = draftDateTime ? new Date(draftDateTime) : null;
    if (!nextDraftTime || Number.isNaN(nextDraftTime.getTime())) {
      setRescheduleSuccess(null);
      setRescheduleError("Choose a valid draft date and time.");
      return;
    }

    setRescheduleError(null);
    setRescheduleSuccess(null);
    try {
      const updatedDraft = await rescheduleDraft.mutateAsync({
        draft_datetime_utc: nextDraftTime.toISOString(),
        timezone: league.draft?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        draft_type: league.draft?.draft_type || "snake",
        pick_timer_seconds: league.draft?.pick_timer_seconds || 90,
        status: "scheduled",
      });
      const updatedDraftTime = new Date(updatedDraft.draft_datetime_utc);
      setDraftDateTime(toDateTimeLocalValue(updatedDraftTime));
      setNow(Date.now());
      setRescheduleSuccess(`Draft time updated to ${updatedDraftTime.toLocaleString()}.`);
      setShowReschedule(false);
    } catch (error) {
      setRescheduleSuccess(null);
      setRescheduleError(getErrorMessage(error));
    }
  };

  const handleRescheduleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handleRescheduleDraft();
  };

  return (
    <div className="max-w-5xl mx-auto py-12 space-y-10">
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
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
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

          <div className="space-y-2 text-sm font-bold uppercase tracking-[0.2em] text-muted-foreground">
            <p>Draft Order: Pending</p>
            <p>Timezone: {league.draft?.timezone}</p>
            <p>Draft Time: {draftTime?.toLocaleString()}</p>
          </div>
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
          {canRescheduleDraft ? (
            <div className="rounded-[2rem] border border-white/10 bg-white/[0.035] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                  <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">
                    Commissioner draft controls
                  </p>
                  <p className="text-sm font-bold leading-6 text-muted-foreground">
                    Change the scheduled draft time before the draft starts.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="h-11 shrink-0 rounded-2xl border-amber-200/25 bg-amber-300/10 px-5 text-[10px] font-black uppercase tracking-[0.2em] text-amber-100 hover:bg-amber-300/15"
                  onClick={() => {
                    setShowReschedule((current) => !current);
                    setRescheduleError(null);
                    setRescheduleSuccess(null);
                  }}
                >
                  <CalendarClock className="mr-2 h-4 w-4" />
                  Reschedule Draft
                </Button>
              </div>

              {showReschedule ? (
                <form
                  className="mt-5 grid gap-3 rounded-2xl border border-white/10 bg-black/15 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end"
                  onSubmit={handleRescheduleSubmit}
                >
                  <label className="grid gap-2">
                    <span className="text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                      New Draft Time
                    </span>
                    <Input
                      type="datetime-local"
                      value={draftDateTime}
                      onChange={(event) => {
                        setDraftDateTime(event.target.value);
                        setRescheduleError(null);
                        setRescheduleSuccess(null);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          event.currentTarget.form?.requestSubmit();
                        }
                      }}
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
              {rescheduleSuccess ? (
                <p className="mt-3 text-[11px] font-bold text-emerald-200">{rescheduleSuccess}</p>
              ) : null}
            </div>
          ) : null}
          {league.members.map((member) => (
            <div key={member.id} className="flex items-center justify-between px-6 py-4 rounded-2xl bg-white/5 border border-white/10">
              <span className="text-sm font-black uppercase tracking-[0.2em] text-foreground">
                {getMemberDisplayName(member)}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{member.role}</span>
            </div>
          ))}
        </CardContent>
      </Card>

      {(!isFull || !canEnterDraft) && (
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground/70">
          Use Open Draft Preview to view the full draft board. Picks unlock only when the league is full and the scheduled draft window opens.
        </p>
      )}

      <div className="flex items-center gap-4">
        <Button
          className="h-12 px-8 rounded-2xl bg-primary text-primary-foreground text-[10px] font-black uppercase tracking-[0.2em]"
          onClick={() => navigate(draftRoomPath)}
        >
          {draftIsReadyToCommence ? "Enter Draft Room" : "Open Draft Preview"}
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
