import { type MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
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

const RECENT_LEAGUE_IDS_KEY = "cfb_recent_league_ids";
const MAX_RECENT_LEAGUES = 20;

const readRecentLeagueIds = () => {
  if (typeof window === "undefined") return [] as number[];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_LEAGUE_IDS_KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return Array.from(new Set(parsed.filter((id): id is number => typeof id === "number" && Number.isFinite(id))));
  } catch {
    return [];
  }
};

export const orderLeaguesByRecent = <T extends { id: number }>(leagues: T[], recentLeagueIds: number[]) => {
  const recentOrder = new Map(recentLeagueIds.map((leagueId, index) => [leagueId, index]));
  return [...leagues].sort((left, right) => {
    const leftIndex = recentOrder.get(left.id);
    const rightIndex = recentOrder.get(right.id);
    if (leftIndex === undefined && rightIndex === undefined) return 0;
    if (leftIndex === undefined) return 1;
    if (rightIndex === undefined) return -1;
    return leftIndex - rightIndex;
  });
};

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
      className="relative cursor-pointer overflow-hidden rounded-lg border-cfb-border-subtle bg-cfb-surface transition-colors hover:border-cfb-border-strong hover:bg-cfb-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <div className="relative z-10">
        <div className="flex min-h-16 items-center gap-3 px-3 py-3 sm:px-4">
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
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-sm font-bold tracking-tight text-foreground sm:text-base">{name}</h3>
              <span className="hidden rounded-md border border-cfb-border-subtle bg-cfb-surface-raised px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-[0.1em] text-cfb-text-muted sm:inline-flex">
                {status.replace(/_/g, " ")}
              </span>
            </div>
            <p className="mt-0.5 truncate text-[9px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              {status.replace(/_/g, " ")} · {teams} teams · {memberCount}/{teams} members
            </p>
          </div>
          <button
            type="button"
            aria-label="League Hub"
            title="Open league hub"
            className="-mr-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-cfb-text-muted transition-colors hover:bg-cfb-surface-hover hover:text-cfb-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand/70"
            onClick={(event) => {
              event.stopPropagation();
              openLeague();
            }}
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-cfb-border-subtle bg-cfb-surface-raised/55 px-3 py-2 text-[9px] font-semibold uppercase tracking-[0.1em] text-cfb-text-secondary sm:px-4">
          <span className="inline-flex items-center gap-1.5">
            {isPrivate ? <Lock className="h-3 w-3 text-primary" /> : <Globe2 className="h-3 w-3 text-primary" />}
            {isPrivate ? "Private" : "Public"}
          </span>
          <span className="hidden h-1 w-1 rounded-full bg-cfb-border-strong sm:block" />
          <span>Record {formatRecord(currentUserSummary)}</span>
          <span className="hidden h-1 w-1 rounded-full bg-cfb-border-strong sm:block" />
          <span className="hidden sm:inline">Proj {formatProjectedPoints(currentUserSummary?.projected_points_for)}</span>
          {currentUserSummary?.matchup_week ? <span className="hidden sm:inline">Week {currentUserSummary.matchup_week} · {formatWinProbability(currentUserSummary.win_probability_for)} win</span> : null}
          <span className="min-w-0 flex-1 truncate text-cfb-text-muted">{draftLabel}</span>
          {shouldShowDraftAction ? (
            <Button
              variant="outline"
              className={[
                "h-8 shrink-0 rounded-md px-2.5 text-[9px] font-bold uppercase tracking-[0.1em]",
                draftUnlocked
                  ? "border-primary/30 bg-primary/10 text-primary hover:bg-primary/15"
                  : "border-amber-400/35 bg-amber-400/10 text-amber-200 hover:bg-amber-400/15",
              ].join(" ")}
              onClick={(event) => {
                event.stopPropagation();
                onOpenDraft(id, draftUnlocked);
              }}
            >
              {draftUnlocked ? "Draft" : "Locked"}
              {draftUnlocked ? <ChevronRight className="ml-1 h-3 w-3" /> : <LockKeyhole className="ml-1 h-3 w-3" />}
            </Button>
          ) : null}
          {shouldShowDraftAction && !draftUnlocked ? <span className="text-amber-200/80">{formatDraftCountdown(draftDateTime, now)}</span> : null}
          {inviteShouldBeVisible ? (
            <details className="shrink-0" onClick={(event) => event.stopPropagation()}>
              <summary className="cursor-pointer text-cfb-brand hover:text-cfb-text-primary">Invite</summary>
              <div className="mt-2 flex min-w-[16rem] flex-wrap items-center gap-2 rounded-md border border-cfb-brand/20 bg-cfb-surface p-2 shadow-lg">
                <span className="min-w-0 flex-1 truncate font-mono text-xs font-bold text-cfb-text-primary">{inviteCode}</span>
                <button type="button" onClick={(event) => copyInviteValue(event, "code", inviteCode)} className="inline-flex h-7 items-center gap-1 rounded-md border border-cfb-border-subtle px-2 text-[9px] font-bold text-cfb-text-secondary hover:bg-cfb-surface-hover">
                  <Copy className="h-3 w-3" />{copiedInviteField === "code" ? "Copied" : "Code"}
                </button>
                <button type="button" onClick={(event) => copyInviteValue(event, "link", inviteLink)} className="inline-flex h-7 items-center gap-1 rounded-md border border-cfb-border-subtle px-2 text-[9px] font-bold text-cfb-text-secondary hover:bg-cfb-surface-hover">
                  <Link2 className="h-3 w-3" />{copiedInviteField === "link" ? "Copied" : "Link"}
                </button>
              </div>
            </details>
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
  const [recentLeagueIds, setRecentLeagueIds] = useState(readRecentLeagueIds);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === RECENT_LEAGUE_IDS_KEY) setRecentLeagueIds(readRecentLeagueIds());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const rememberLeague = useCallback((leagueId: number) => {
    setRecentLeagueIds((current) => {
      const next = [leagueId, ...current.filter((id) => id !== leagueId)].slice(0, MAX_RECENT_LEAGUES);
      if (typeof window !== "undefined") window.localStorage.setItem(RECENT_LEAGUE_IDS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const orderedLeagueRows = useMemo(
    () => orderLeaguesByRecent(leagueRows, recentLeagueIds),
    [leagueRows, recentLeagueIds]
  );

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
          {orderedLeagueRows.map((league) => (
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
                rememberLeague(leagueId);
                setActiveLeagueId(leagueId);
                const postDraft = isLeaguePostDraft({
                  draftStatus: league.draft?.status,
                  leagueStatus: league.status,
                });
                navigate(postDraft ? `/league/${leagueId}/roster` : `/league/${leagueId}/lobby`);
              }}
              onOpenDraft={(leagueId, draftUnlocked) => {
                rememberLeague(leagueId);
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
