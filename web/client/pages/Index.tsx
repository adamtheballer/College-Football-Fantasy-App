import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bell,
  CalendarClock,
  ChevronRight,
  Clock,
  ShieldCheck,
  Sparkles,
  Trophy,
  Users,
  Zap,
} from "lucide-react";

import { EmptyState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { PlaybookDecor, PositionBadge, StatusBadge, SurfaceCard } from "@/components/fantasy";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagueWorkspace, useLeagues } from "@/hooks/use-leagues";
import { useSaturdayPickContest } from "@/hooks/use-saturday-pick";
import { apiGet } from "@/lib/api";
import { getSaturdayPickRewardMessage, getSaturdayPickSponsorLogo } from "@/lib/saturday-pick-sponsor";
import type { LeagueDetail } from "@/types/league";

type AlertItem = {
  id: number;
  alert_type: string;
  title: string;
  body: string;
  sent_at: string | null;
  payload: Record<string, unknown> | null;
};

type AlertPayload = {
  data: AlertItem[];
};

export const formatDashboardStatus = (status: string | null | undefined) =>
  String(status ?? "unknown").replace(/_/g, " ");

export const formatDraftTime = (value: string | null | undefined) => {
  if (!value) return "Draft not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Draft not scheduled";
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

export const formatDashboardPoints = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "—";

export const isUpcomingDraft = (league: LeagueDetail, now = Date.now()) => {
  const scheduledAt = league.draft?.draft_datetime_utc;
  if (!scheduledAt) return false;

  const timestamp = new Date(scheduledAt).getTime();
  return Number.isFinite(timestamp) && timestamp > now;
};

function GuestHome() {
  return (
    <div className="mx-auto grid w-full max-w-7xl gap-8 pb-20 pt-8 lg:grid-cols-[1.08fr_0.92fr] lg:items-center">
      <div className="space-y-7">
        <div className="inline-flex items-center gap-2 rounded-full border border-cfb-brand/30 bg-cfb-brand/[0.12] px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-blue-100">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          College Football Fantasy
        </div>
        <div className="space-y-4">
          <h1 className="cfb-display-title max-w-3xl text-5xl sm:text-6xl lg:text-7xl">
            Draft. Manage. Compete.
          </h1>
          <p className="max-w-2xl text-lg font-medium leading-8 text-cfb-text-secondary">
            Build a league, draft Power 4 stars, manage your roster, and track the weekly
            matchup with a fantasy dashboard built for college football.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild className="h-12 rounded-xl px-7 text-[11px] font-black uppercase tracking-[0.16em]">
            <Link to="/signup">Create Account</Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="h-12 rounded-xl px-7 text-[11px] font-black uppercase tracking-[0.16em]"
          >
            <Link to="/login">Sign In</Link>
          </Button>
        </div>
      </div>

      <SurfaceCard variant="scoreboard" padding="spacious" className="cfb-playbook-pattern relative space-y-6">
        <PlaybookDecor className="opacity-55" />
        <div className="flex items-center justify-between">
          <div>
            <p className="cfb-micro-label text-cfb-brand">Week 1 Preview</p>
            <h2 className="mt-2 text-2xl font-black text-cfb-text-primary">Fantasy Matchup</h2>
          </div>
          <StatusBadge variant="projected">Projected</StatusBadge>
        </div>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div>
            <p className="text-sm font-black text-cfb-text-primary">Your Team</p>
            <p className="mt-2 font-display text-5xl font-black tracking-[-0.06em] text-cfb-brand">—</p>
          </div>
          <div className="rounded-full border border-cfb-border-strong bg-cfb-surface px-3 py-2 text-xs font-black text-cfb-text-secondary">
            VS
          </div>
          <div className="text-right">
            <p className="text-sm font-black text-cfb-text-primary">Opponent</p>
            <p className="mt-2 font-display text-5xl font-black tracking-[-0.06em] text-cfb-pink">—</p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
            <Zap className="h-5 w-5 text-cfb-gold" aria-hidden="true" />
            <p className="mt-3 text-sm font-black">Live scoring</p>
          </div>
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
            <Users className="h-5 w-5 text-cfb-cyan" aria-hidden="true" />
            <p className="mt-3 text-sm font-black">League tools</p>
          </div>
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
            <Trophy className="h-5 w-5 text-cfb-success" aria-hidden="true" />
            <p className="mt-3 text-sm font-black">Weekly glory</p>
          </div>
        </div>
      </SurfaceCard>
    </div>
  );
}

export default function Index() {
  const { isLoggedIn, user } = useAuth();
  const navigate = useNavigate();
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(20, isLoggedIn);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [alertsLoaded, setAlertsLoaded] = useState(false);
  const [currentTime, setCurrentTime] = useState(() => Date.now());

  const selectedLeague = useMemo(() => {
    if (!leagues.length) return null;
    if (activeLeagueId) {
      const active = leagues.find((league) => league.id === activeLeagueId);
      if (active) return active;
    }
    return leagues[0];
  }, [activeLeagueId, leagues]);

  const { data: workspace } = useLeagueWorkspace(
    selectedLeague?.id,
    Boolean(isLoggedIn && selectedLeague?.id),
  );
  const saturdayPickQuery = useSaturdayPickContest(isLoggedIn);

  useEffect(() => {
    if (!isLoggedIn || !leagues.length) return;
    if (selectedLeague?.id && selectedLeague.id !== activeLeagueId) {
      setActiveLeagueId(selectedLeague.id);
    }
  }, [activeLeagueId, isLoggedIn, leagues.length, selectedLeague?.id, setActiveLeagueId]);

  useEffect(() => {
    if (!isLoggedIn) {
      setAlerts([]);
      setAlertsLoaded(true);
      return;
    }

    const controller = new AbortController();
    apiGet<AlertPayload>("/notifications/alerts", { limit: 5 }, controller.signal)
      .then((payload) => setAlerts(payload.data ?? []))
      .catch(() => setAlerts([]))
      .finally(() => setAlertsLoaded(true));

    return () => controller.abort();
  }, [isLoggedIn]);

  useEffect(() => {
    const intervalId = window.setInterval(() => setCurrentTime(Date.now()), 60_000);
    return () => window.clearInterval(intervalId);
  }, []);

  const rosterSize = workspace?.roster?.length ?? 0;
  const upcomingDrafts = useMemo(
    () =>
      [...leagues]
        .filter((league) => isUpcomingDraft(league, currentTime))
        .sort((left, right) => {
          const l = new Date(left.draft?.draft_datetime_utc ?? "").getTime();
          const r = new Date(right.draft?.draft_datetime_utc ?? "").getTime();
          return l - r;
        })
        .slice(0, 4),
    [currentTime, leagues],
  );

  if (!isLoggedIn) {
    return <GuestHome />;
  }

  const matchup = workspace?.matchup_summary ?? null;
  const standings = workspace?.standings_summary ?? [];
  const ownedTeamName = workspace?.owned_team?.name ?? "Your Team";

  return (
    <div className="mx-auto w-full max-w-7xl space-y-7 pb-24 pt-4">
      <section className="relative grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div aria-hidden="true" className="pointer-events-none absolute -left-8 -top-8 h-28 w-80 rotate-[-14deg] rounded-full bg-gradient-to-r from-cfb-pink/45 via-cfb-brand/35 to-transparent blur-xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-8 top-20 h-24 w-96 rotate-[-18deg] rounded-full bg-gradient-to-r from-transparent via-cfb-cyan/35 to-cfb-gold/30 blur-xl" />
        <div aria-hidden="true" className="pointer-events-none absolute bottom-2 left-16 h-20 w-96 rotate-[-10deg] rounded-full bg-gradient-to-r from-cfb-gold/30 via-cfb-brand/20 to-transparent blur-xl" />
        <SurfaceCard variant="scoreboard" padding="spacious" className="cfb-playbook-pattern relative min-h-[330px]">
          <div className="flex h-full flex-col justify-between gap-8">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-cfb-brand/35 bg-cfb-brand/[0.12] px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-blue-100">
                <Zap className="h-4 w-4" aria-hidden="true" />
                Game Week Command Center
              </div>
              <div>
                <h1 className="text-4xl font-black tracking-[-0.04em] text-cfb-text-primary sm:text-5xl">
                  Good to see you, {user?.firstName ?? "Manager"}.
                </h1>
                <p className="mt-3 max-w-2xl text-base font-medium leading-7 text-cfb-text-secondary">
                  Resume your active league, check the matchup board, and handle roster decisions
                  before kickoff.
                </p>
              </div>
            </div>

            {selectedLeague ? (
              <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
                <div>
                  <p className="cfb-micro-label text-cfb-brand">Current League</p>
                  <h2 className="mt-2 text-3xl font-black italic text-cfb-text-primary">
                    {selectedLeague.name}
                  </h2>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.16em] text-cfb-text-muted">
                    {formatDashboardStatus(selectedLeague.status)} • {selectedLeague.members.length}/
                    {selectedLeague.max_teams} managers • {formatDraftTime(selectedLeague.draft?.draft_datetime_utc)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    className="h-11 rounded-xl text-[11px] font-black uppercase tracking-[0.16em]"
                    onClick={() => navigate(`/league/${selectedLeague.id}`)}
                  >
                    Open League
                  </Button>
                  <Button
                    variant="outline"
                    className="h-11 rounded-xl text-[11px] font-black uppercase tracking-[0.16em]"
                    onClick={() => navigate(`/league/${selectedLeague.id}/matchup`)}
                  >
                    View Matchup
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-3">
                <Button onClick={() => navigate("/leagues/create")}>Create League</Button>
                <Button variant="outline" onClick={() => navigate("/leagues/join")}>
                  Join League
                </Button>
              </div>
            )}
          </div>
        </SurfaceCard>

        <SurfaceCard variant="raised" padding="default" className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="cfb-micro-label text-cfb-brand">Week {matchup?.week ?? 1}</p>
              <h2 className="mt-2 text-2xl font-black text-cfb-text-primary">Matchup Snapshot</h2>
            </div>
            <StatusBadge variant={matchup?.status === "live" ? "live" : "projected"}>
              {matchup?.status ? formatDashboardStatus(matchup.status) : "Projected"}
            </StatusBadge>
          </div>

          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div>
              <p className="truncate text-sm font-black text-cfb-text-primary">{ownedTeamName}</p>
              <p className="mt-2 font-display text-4xl font-black tracking-[-0.06em] text-cfb-brand">
                {formatDashboardPoints(matchup?.projected_points_for)}
              </p>
            </div>
            <span className="rounded-full border border-cfb-border-subtle bg-cfb-surface px-3 py-2 text-xs font-black text-cfb-text-secondary">
              VS
            </span>
            <div className="text-right">
              <p className="truncate text-sm font-black text-cfb-text-primary">
                {matchup?.opponent_team_name ?? "Opponent TBD"}
              </p>
              <p className="mt-2 font-display text-4xl font-black tracking-[-0.06em] text-cfb-pink">
                {formatDashboardPoints(matchup?.projected_points_against)}
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
            <p className="text-sm font-bold text-cfb-text-secondary">
              {matchup
                ? "Projected totals update as the league scoring data refreshes."
                : "No scheduled matchup is available yet. Draft or schedule generation will populate this card."}
            </p>
          </div>
        </SurfaceCard>
      </section>

      <SurfaceCard
        variant="scoreboard"
        padding="spacious"
        className="min-h-[270px] border-cfb-brand/50 shadow-[0_0_64px_rgba(37,99,235,0.22)]"
      >
        <PlaybookDecor className="opacity-45" />
        <div aria-hidden="true" className="absolute -left-16 -top-20 h-64 w-96 rotate-[-20deg] rounded-full bg-cfb-brand/30 blur-3xl" />
        <div aria-hidden="true" className="absolute -bottom-24 right-0 h-72 w-96 rounded-full bg-cfb-pink/20 blur-3xl" />
        <div className="relative flex h-full flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-cfb-gold/45 bg-cfb-gold/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.2em] text-yellow-100">
              <Trophy className="h-4 w-4" aria-hidden="true" />
              Saturday Pick 6
            </div>
            <p className="mt-6 cfb-micro-label text-cfb-brand">{saturdayPickQuery.data ? `${saturdayPickQuery.data.contest_position} Week` : "The weekly college football challenge"}</p>
            {saturdayPickQuery.data?.sponsor ? <div className="mt-3 flex items-center gap-3"><div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-cyan-100/35 bg-white p-1.5 shadow-[0_0_20px_rgba(34,211,238,0.16)]">{getSaturdayPickSponsorLogo(saturdayPickQuery.data.sponsor) ? <img src={getSaturdayPickSponsorLogo(saturdayPickQuery.data.sponsor) ?? undefined} alt={`${saturdayPickQuery.data.sponsor.name} logo`} className="h-full w-full object-contain" /> : <span className="text-xs font-black text-cfb-brand">{saturdayPickQuery.data.sponsor.name.slice(0, 2).toUpperCase()}</span>}</div><p className="font-display text-3xl font-black italic tracking-[-0.04em] text-cyan-100 sm:text-4xl">Presented by {saturdayPickQuery.data.sponsor.name}</p></div> : null}
            <h2 className="mt-2 cfb-display-title text-4xl sm:text-5xl lg:text-6xl">
              {saturdayPickQuery.data ? "Make your pick" : "Coming next week"}
            </h2>
            <p className="mt-4 max-w-2xl text-base font-bold leading-7 text-cfb-text-secondary sm:text-lg">
              {saturdayPickQuery.data
                ? `${getSaturdayPickRewardMessage(saturdayPickQuery.data.sponsor)} Choose which featured ${saturdayPickQuery.data.contest_position} will score the most fantasy points.`
    : "Six featured players. One weekly prediction. One prize. Make your call before kickoff."}
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-3 lg:items-end">
            <p className="text-xs font-black uppercase tracking-[0.18em] text-cfb-text-muted">Six players. One winner.</p>
            <Button asChild variant={saturdayPickQuery.data ? "default" : "outline"} className="h-13 rounded-xl px-7 text-[11px] font-black uppercase tracking-[0.16em]">
              <Link to="/saturday-pick-6">{saturdayPickQuery.data?.entry ? "View Your Pick" : saturdayPickQuery.data ? "Make Your Pick" : "Learn More"}</Link>
            </Button>
          </div>
        </div>
      </SurfaceCard>

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <SurfaceCard variant="default" padding="none">
          <div className="flex items-center justify-between border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
            <div>
              <p className="cfb-micro-label text-cfb-brand">Your Leagues</p>
              <h2 className="mt-1 text-xl font-black text-cfb-text-primary">Pick up where you left off</h2>
            </div>
            <Button variant="outline" size="sm" onClick={() => navigate("/leagues")}>
              View All
            </Button>
          </div>

          {leaguesLoading ? (
            <div className="px-6 py-12 text-center text-sm font-black uppercase tracking-[0.18em] text-cfb-text-muted">
              Loading leagues...
            </div>
          ) : leagues.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No leagues joined yet"
                description="Create a league or join with an invite code to start building your team."
                actionLabel="Create League"
                onAction={() => navigate("/leagues/create")}
              />
            </div>
          ) : (
            leagues.map((league) => {
              const isActive = league.id === selectedLeague?.id;
              return (
                <button
                  key={league.id}
                  type="button"
                  onClick={() => {
                    setActiveLeagueId(league.id);
                    navigate(`/league/${league.id}`);
                  }}
                  className={`flex w-full items-center justify-between gap-4 border-b border-cfb-border-subtle px-5 py-5 text-left transition last:border-b-0 hover:bg-cfb-surface-hover/60 sm:px-6 ${
                    isActive ? "bg-cfb-brand/[0.10]" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-base font-black text-cfb-text-primary">{league.name}</p>
                      {isActive ? <StatusBadge variant="projected">Active</StatusBadge> : null}
                    </div>
                    <p className="mt-1 text-[11px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
                      {formatDashboardStatus(league.status)} • {league.members.length}/{league.max_teams} managers
                    </p>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-cfb-brand" aria-hidden="true" />
                </button>
              );
            })
          )}
        </SurfaceCard>

        <div className="grid gap-6">
          <SurfaceCard variant="default" padding="none">
            <div className="border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
              <p className="cfb-micro-label text-cfb-brand">Roster Status</p>
              <h2 className="mt-1 text-xl font-black text-cfb-text-primary">{ownedTeamName}</h2>
            </div>
            <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-6">
              <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
                <ShieldCheck className="h-5 w-5 text-cfb-success" aria-hidden="true" />
                <p className="mt-3 text-2xl font-black text-cfb-text-primary">{rosterSize}</p>
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-cfb-text-muted">Players rostered</p>
              </div>
              <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface/70 p-4">
                <PositionBadge position="FLEX" />
                <p className="mt-3 text-sm font-bold text-cfb-text-secondary">
                  {rosterSize > 0 ? "Roster is ready for lineup review." : "Roster fills after the draft."}
                </p>
              </div>
            </div>
          </SurfaceCard>

          <SurfaceCard variant="default" padding="none">
            <div className="border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
              <p className="cfb-micro-label text-cfb-brand">Upcoming Drafts</p>
            </div>
            {upcomingDrafts.length === 0 ? (
              <div className="px-6 py-10 text-center text-sm font-black uppercase tracking-[0.18em] text-cfb-text-muted">
                No scheduled drafts
              </div>
            ) : (
              upcomingDrafts.map((league) => (
                <div key={league.id} className="flex items-center gap-3 border-b border-cfb-border-subtle px-5 py-4 last:border-b-0 sm:px-6">
                  <Clock className="h-4 w-4 text-cfb-gold" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-cfb-text-primary">{league.name}</p>
                    <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-cfb-text-muted">
                      {formatDraftTime(league.draft?.draft_datetime_utc)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </SurfaceCard>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <SurfaceCard variant="default" padding="none">
          <div className="border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
            <p className="cfb-micro-label text-cfb-brand">League Standings</p>
          </div>
          {standings.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm font-black uppercase tracking-[0.18em] text-cfb-text-muted">
              Standings appear after league schedule data is available
            </div>
          ) : (
            standings.slice(0, 5).map((standing, index) => (
              <div key={standing.team_id} className="flex items-center justify-between border-b border-cfb-border-subtle px-5 py-4 last:border-b-0 sm:px-6">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="font-display text-xl font-black text-cfb-brand">#{standing.rank ?? index + 1}</span>
                  <p className="truncate text-sm font-black text-cfb-text-primary">{standing.team_name}</p>
                </div>
                <p className="text-sm font-black text-cfb-text-secondary">
                  {standing.wins ?? 0}-{standing.losses ?? 0}-{standing.ties ?? 0}
                </p>
              </div>
            ))
          )}
        </SurfaceCard>

        <SurfaceCard variant="default" padding="none">
          <div className="flex items-center justify-between border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
            <div>
              <p className="cfb-micro-label text-cfb-brand">League Alerts</p>
              <h2 className="mt-1 text-xl font-black text-cfb-text-primary">What needs attention</h2>
            </div>
            <Button variant="outline" size="sm" onClick={() => navigate("/alerts")}>
              Open Alerts
            </Button>
          </div>
          {!alertsLoaded ? (
            <div className="px-6 py-10 text-center text-sm font-black uppercase tracking-[0.18em] text-cfb-text-muted">
              Loading alerts...
            </div>
          ) : alerts.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm font-black uppercase tracking-[0.18em] text-cfb-text-muted">
              No alerts available
            </div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.id} className="flex items-start gap-4 border-b border-cfb-border-subtle px-5 py-5 last:border-b-0 sm:px-6">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised text-cfb-brand">
                  <Bell className="h-4 w-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-black text-cfb-text-primary">{alert.title}</p>
                  <p className="mt-1 text-sm font-medium text-cfb-text-secondary">{alert.body}</p>
                </div>
              </div>
            ))
          )}
        </SurfaceCard>
      </section>

      <div className="rounded-2xl border border-cfb-border-subtle bg-cfb-brand/[0.10] px-5 py-4 text-sm font-bold text-blue-100">
        <CalendarClock className="mr-2 inline h-4 w-4" aria-hidden="true" />
        Deadline and lock warnings should always be checked before kickoff.
      </div>
    </div>
  );
}
