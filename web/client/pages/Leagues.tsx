import { type MouseEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Trophy,
  ChevronRight,
  Lock,
  Globe2,
  Users,
  Copy,
  Link2,
  LockKeyhole,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/fantasy";
import { ErrorState, SkeletonState } from "@/components/states";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagues } from "@/hooks/use-leagues";
import { formatDraftCountdown, hasDraftStarted } from "@/lib/draftStatus";
import { isLeaguePostDraft, shouldShowLeagueDraftRoomAction } from "@/lib/leagueLifecycle";
import type { LeagueListCurrentUserSummary } from "@/types/league";

const formatWinProbability = (value: number | null | undefined) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Pending";
  const percentage = value <= 1 ? value * 100 : value;
  return `${Math.round(percentage)}%`;
};

const formatRecord = (summary: LeagueListCurrentUserSummary | null | undefined) => {
  if (!summary) return "0-0";
  const wins = summary.wins ?? 0;
  const losses = summary.losses ?? 0;
  const ties = summary.ties ?? 0;
  return ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
};

const formatProjectedPoints = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";

export const LeagueCard = ({
  id,
  name,
  status,
  teams,
  memberCount,
  draftLabel,
  draftDateTime,
  isPrivate,
  draftStatus,
  inviteCode,
  iconUrl,
  currentUserSummary,
  onOpen,
  onOpenDraft,
}: {
  id: number;
  name: string;
  status: string;
  teams: number;
  memberCount: number;
  draftLabel: string;
  draftDateTime?: string | null;
  isPrivate: boolean;
  draftStatus: string;
  inviteCode?: string | null;
  iconUrl?: string | null;
  currentUserSummary?: LeagueListCurrentUserSummary | null;
  onOpen: (leagueId: number) => void;
  onOpenDraft: (leagueId: number, draftUnlocked: boolean) => void;
}) => {
  const [copiedInviteField, setCopiedInviteField] = useState<"code" | "link" | null>(null);
  const [iconFailed, setIconFailed] = useState(false);
  const [now, setNow] = useState(Date.now());
  const leagueImageUrl = iconUrl?.trim() || null;
  const openLeague = () => onOpen(id);
  const normalizedDraftStatus = (draftStatus || "").toLowerCase();
  const normalizedLeagueStatus = (status || "").toLowerCase();
  const draftLive = normalizedDraftStatus === "live" || normalizedDraftStatus === "draft_live";
  const draftUnlocked = draftLive || hasDraftStarted(draftDateTime, now);
  const shouldShowDraftAction = shouldShowLeagueDraftRoomAction({
    draftStatus,
    leagueStatus: status,
    draftDateTime,
  });
  const postDraft = isLeaguePostDraft({ draftStatus, leagueStatus: status });
  const completeStatuses = ["completed", "complete", "draft_completed", "final", "closed", "post_draft"];
  const inviteShouldBeVisible =
    Boolean(inviteCode) &&
    !completeStatuses.includes(normalizedDraftStatus) &&
    !completeStatuses.includes(normalizedLeagueStatus);
  const inviteLink =
    inviteCode && typeof window !== "undefined"
      ? `${window.location.origin}/join/${inviteCode}`
      : null;

  useEffect(() => {
    if (!shouldShowDraftAction || draftUnlocked) return undefined;
    const interval = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(interval);
  }, [draftUnlocked, shouldShowDraftAction]);

  useEffect(() => {
    setIconFailed(false);
  }, [leagueImageUrl]);

  const copyInviteValue = async (
    event: MouseEvent<HTMLButtonElement>,
    field: "code" | "link",
    value?: string | null
  ) => {
    event.stopPropagation();
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedInviteField(field);
    window.setTimeout(() => setCopiedInviteField(null), 1600);
  };

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={openLeague}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openLeague();
        }
      }}
      className="relative cursor-pointer overflow-hidden rounded-lg border-cfb-border-subtle bg-cfb-surface shadow-sm transition-colors hover:border-cfb-border-strong hover:bg-cfb-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
    <div className="relative z-10 grid gap-0 sm:grid-cols-[minmax(11rem,0.8fr)_minmax(14rem,1.1fr)_11rem]">
      <div className="border-b border-border/60 p-3 sm:border-b-0 sm:border-r sm:p-4">
        <div className="flex h-full flex-col justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-md border border-primary/25 bg-primary/[0.07] text-primary">
              {leagueImageUrl && !iconFailed ? (
                <img
                  src={leagueImageUrl}
                  alt={`${name} league logo`}
                  className="h-full w-full object-contain p-1"
                  onError={() => setIconFailed(true)}
                />
              ) : (
                <Trophy className="h-4 w-4 text-white" aria-label="Default league trophy" />
              )}
            </div>
            <div className="min-w-0 space-y-1">
              <h3 className="text-base font-bold tracking-tight text-foreground">
                {name}
              </h3>
              <p className="text-[10px] font-semibold tracking-[0.08em] text-muted-foreground uppercase">
                {status.replace(/_/g, " ")} • {teams} teams
              </p>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              <span className="inline-flex items-center gap-2 rounded-md border border-cfb-border-subtle bg-cfb-surface-raised px-2.5 py-1.5">
                <Users className="w-3 h-3 text-primary" />
                {memberCount}/{teams} members
              </span>
              <span className="inline-flex items-center gap-2 rounded-md border border-cfb-border-subtle bg-cfb-surface-raised px-2.5 py-1.5">
                {isPrivate ? <Lock className="w-3 h-3 text-primary" /> : <Globe2 className="w-3 h-3 text-primary" />}
                {isPrivate ? "Private" : "Public"}
              </span>
            </div>
            {inviteShouldBeVisible ? (
              <details
                className="max-w-md rounded-md border border-cfb-brand/20 bg-cfb-brand/[0.05] px-3 py-2"
                onClick={(event) => event.stopPropagation()}
              >
                <summary className="cursor-pointer text-[9px] font-semibold uppercase tracking-[0.12em] text-sky-200/80">
                  Invite options
                </summary>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="min-w-0 flex-1 truncate rounded-md border border-cfb-border-subtle bg-cfb-surface px-3 py-2 font-mono text-xs font-bold tracking-[0.08em] text-cfb-text-primary">
                    {inviteCode}
                  </span>
                  <button
                    type="button"
                    onClick={(event) => copyInviteValue(event, "code", inviteCode)}
                    className="inline-flex h-9 items-center gap-2 rounded-md border border-sky-300/25 bg-sky-300/15 px-3 text-[9px] font-bold uppercase tracking-[0.12em] text-sky-100 transition hover:border-sky-200/60 hover:bg-sky-300/20"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    {copiedInviteField === "code" ? "Copied" : "Code"}
                  </button>
                  <button
                    type="button"
                    onClick={(event) => copyInviteValue(event, "link", inviteLink)}
                    className="inline-flex h-9 items-center gap-2 rounded-md border border-emerald-300/25 bg-emerald-300/12 px-3 text-[9px] font-bold uppercase tracking-[0.12em] text-emerald-100 transition hover:border-emerald-200/60 hover:bg-emerald-300/18"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    {copiedInviteField === "link" ? "Copied" : "Link"}
                  </button>
                </div>
              </details>
            ) : null}
          </div>
        </div>
      </div>

      <div className="border-b border-cfb-border-subtle bg-cfb-surface-raised/55 p-3 sm:border-b-0 sm:border-r sm:p-4">
        <div className="space-y-2">
          <h4 className="text-[10px] font-semibold tracking-[0.12em] text-primary uppercase opacity-80">
            League snapshot
          </h4>
          <div>
            <div className="grid gap-2 grid-cols-3">
              <div className="rounded-md border border-cfb-border-subtle bg-cfb-surface p-2.5">
                <p className="text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">
                  Draft
                </p>
                <p className="mt-1.5 text-sm font-semibold text-foreground">{draftLabel}</p>
              </div>
              <div className="rounded-md border border-cfb-border-subtle bg-cfb-surface p-2.5">
                <p className="text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">
                  Your record
                </p>
                <p className="mt-1.5 text-sm font-semibold text-foreground">
                  {formatRecord(currentUserSummary)}
                </p>
              </div>
              <div className="rounded-md border border-cfb-border-subtle bg-cfb-surface p-2.5">
                <p className="text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">
                  {currentUserSummary?.matchup_week ? `Week ${currentUserSummary.matchup_week}` : "Matchup"}
                </p>
                <p className="mt-1.5 truncate text-sm font-semibold text-foreground">
                  {currentUserSummary?.opponent_team_name || "Schedule pending"}
                </p>
                <p className="mt-1 text-xs font-bold tabular-nums text-foreground">
                  {formatProjectedPoints(currentUserSummary?.projected_points_for)} - {formatProjectedPoints(currentUserSummary?.projected_points_against)}
                </p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-sky-200">
                  Win chance {formatWinProbability(currentUserSummary?.win_probability_for)}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-3 sm:flex sm:min-w-[11rem] sm:flex-col sm:justify-center sm:p-4">
        <Button
          variant="outline"
          className="h-10 w-full rounded-md border-cfb-border-subtle bg-cfb-surface px-3 text-[10px] font-bold uppercase tracking-[0.1em] text-foreground hover:bg-cfb-surface-hover"
          onClick={(event) => {
            event.stopPropagation();
            openLeague();
          }}
        >
          {postDraft ? "Open League Hub" : "League Hub"}
          <ChevronRight className="w-3 h-3 ml-2" />
        </Button>
        {shouldShowDraftAction && (
          <Button
            variant="outline"
            className={[
              "h-10 w-full rounded-lg px-3 text-[10px] font-bold uppercase tracking-[0.1em] transition-colors",
              draftUnlocked
                ? "border-primary/30 bg-primary/10 text-primary hover:bg-primary/15"
                : "border-amber-400/35 bg-amber-50 text-amber-800 hover:bg-amber-100",
            ].join(" ")}
            onClick={(event) => {
              event.stopPropagation();
              onOpenDraft(id, draftUnlocked);
            }}
          >
            {draftUnlocked ? "Join Draft Room" : "Draft Room Locked"}
            {draftUnlocked ? <ChevronRight className="w-3 h-3 ml-2" /> : <LockKeyhole className="w-3 h-3 ml-2" />}
          </Button>
        )}
        {shouldShowDraftAction && !draftUnlocked ? (
          <p className="col-span-2 text-center text-[9px] font-semibold uppercase tracking-[0.1em] text-amber-100/80 sm:col-auto">
            Opens in {formatDraftCountdown(draftDateTime, now)}
          </p>
        ) : null}
      </div>
    </div>
    </Card>
  );
};

export default function Leagues() {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const { setActiveLeagueId } = useActiveLeagueId();
  const { data: leagueRows = [], isLoading, isError, refetch } = useLeagues(20, isLoggedIn);

  return (
    <div className="relative z-10 mx-auto max-w-6xl space-y-6 pb-4 pt-1 animate-in fade-in duration-300">
      <PageHeader
        eyebrow="League command center"
        title="Leagues"
        description={isLoggedIn
          ? "Manage your active leagues, jump into drafts, and open the right league hub."
          : "Sign in to create or join a league and use the supported React experience."}
        actions={isLoggedIn ? (
          <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center">
              <Button
                variant="outline"
                className="h-11 border-primary/35 bg-primary/[0.08] px-4 text-sm text-primary hover:bg-primary/[0.14]"
                onClick={() => navigate("/leagues/create")}
              >
                Create league
              </Button>
              <Button
                variant="outline"
                className="h-11 border-emerald-500/30 bg-emerald-500/[0.06] px-4 text-sm text-emerald-300 hover:bg-emerald-500/[0.12]"
                onClick={() => navigate("/leagues/join")}
              >
                Join league
              </Button>
          </div>
        ) : undefined}
      />

      {isLoggedIn ? (
        <div className="space-y-4">
          {isLoading && (
            <SkeletonState rows={3} label="Loading your leagues" />
          )}
          {isError && (
            <ErrorState
              message="Unable to load leagues. Confirm the backend is running and your session is valid."
              retryLabel="Try again"
              onRetry={() => void refetch()}
            />
          )}
          {leagueRows.map((league) => (
            <LeagueCard
              key={league.id}
              id={league.id}
              name={league.name}
              status={league.status}
              teams={league.max_teams}
              memberCount={league.members.length}
              draftLabel={
                league.draft?.draft_datetime_utc
                  ? new Date(league.draft.draft_datetime_utc).toLocaleString()
                  : "Draft not scheduled"
              }
              draftDateTime={league.draft?.draft_datetime_utc}
              isPrivate={league.is_private}
              draftStatus={league.draft?.status || "none"}
              inviteCode={league.invite_code}
              iconUrl={league.icon_url}
              currentUserSummary={league.current_user_summary}
              onOpen={(leagueId) => {
                setActiveLeagueId(leagueId);
                const postDraft = isLeaguePostDraft({
                  draftStatus: league.draft?.status,
                  leagueStatus: league.status,
                });
                navigate(postDraft ? `/league/${leagueId}/roster` : `/league/${leagueId}/lobby`);
              }}
              onOpenDraft={(leagueId, draftUnlocked) => {
                setActiveLeagueId(leagueId);
                if (draftUnlocked) {
                  navigate(`/league/${leagueId}/draft`);
                  return;
                }
                navigate(`/league/${leagueId}/lobby`);
              }}
            />
          ))}
          {!isLoading && leagueRows.length === 0 && (
            <Card className="space-y-5 rounded-lg border-cfb-border-subtle bg-cfb-surface p-6 shadow-sm">
              <div className="space-y-2 text-center">
                <h3 className="text-lg font-bold text-foreground">No leagues yet</h3>
                <p className="text-sm text-muted-foreground">
                  Create a league or join one with an invite code to get started.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button className="h-11 rounded-lg" onClick={() => navigate("/leagues/create")}>Create League</Button>
                <Button className="h-11 rounded-lg" variant="outline" onClick={() => navigate("/leagues/join")}>Join League</Button>
              </div>
            </Card>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card className="rounded-lg border-cfb-border-subtle bg-cfb-surface p-6 text-center shadow-sm">
            <div className="space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Trophy className="w-6 h-6" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-bold text-foreground">Create League</h3>
                <p className="mx-auto max-w-[240px] text-sm text-muted-foreground">
                  Start your own custom league and invite your friends to draft.
                </p>
              </div>
              <Button asChild className="h-11 w-full rounded-lg text-[10px] font-bold uppercase tracking-[0.1em]">
                <Link to="/login" className="block">
                  Sign In to Create
                </Link>
              </Button>
            </div>
          </Card>

          <Card className="rounded-xl border-border/60 bg-[#15181c] p-6 text-center">
            <div className="space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                <Users className="w-6 h-6" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-bold text-foreground">Join League</h3>
                <p className="mx-auto max-w-[240px] text-sm text-muted-foreground">
                  Join an existing league with an invite code and start scouting.
                </p>
              </div>
              <Button asChild className="h-11 w-full rounded-lg bg-emerald-500 text-[10px] font-bold uppercase tracking-[0.1em] text-white hover:bg-emerald-400">
                <Link to="/login" className="block">
                  Sign In to Join
                </Link>
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
