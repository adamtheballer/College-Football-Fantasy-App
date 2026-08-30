import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  Bell,
  CalendarClock,
  Clock,
  ShieldCheck,
} from "lucide-react";

import { EmptyState, SkeletonState } from "@/components/states";
import { LeagueMatchupCarousel } from "@/components/league/LeagueMatchupCarousel";
import { formatDisplayedProbabilityPair } from "@/components/league/WinChanceMeter";
import { Button } from "@/components/ui/button";
import { PositionBadge, StatusBadge, SurfaceCard } from "@/components/fantasy";
import { PublicLegalLinks } from "@/components/legal/PublicLegalLinks";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagueWorkspace, useLeagues } from "@/hooks/use-leagues";
import { apiGet } from "@/lib/api";
import type { LeagueDetail } from "@/types/league";
import SaturdayPick6 from "./SaturdayPick6";

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

export const formatDashboardWinChance = (
  myPercent: number | null | undefined,
  opponentPercent: number | null | undefined,
) => {
  if (
    typeof myPercent !== "number" ||
    typeof opponentPercent !== "number" ||
    !Number.isFinite(myPercent) ||
    !Number.isFinite(opponentPercent) ||
    myPercent < 5 ||
    opponentPercent < 5 ||
    myPercent > 95 ||
    opponentPercent > 95 ||
    Math.abs(myPercent + opponentPercent - 100) > 0.000001
  ) {
    return null;
  }

  return formatDisplayedProbabilityPair(myPercent, opponentPercent);
};

export const isUpcomingDraft = (league: LeagueDetail, now = Date.now()) => {
  const scheduledAt = league.draft?.draft_datetime_utc;
  if (!scheduledAt) return false;

  const timestamp = new Date(scheduledAt).getTime();
  return Number.isFinite(timestamp) && timestamp > now;
};

function GuestHome() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 pb-16 pt-5 sm:pt-10">
      <section className="grid gap-6 lg:grid-cols-[1.08fr_0.92fr] lg:items-center">
        <div className="space-y-6">
          <div className="space-y-3">
            <p className="cfb-micro-label text-cfb-gold">College Fantasy Football</p>
            <h1 className="cfb-display-title max-w-2xl text-4xl sm:text-5xl">
              Fantasy football for college football.
            </h1>
            <p className="max-w-xl text-base leading-7 text-cfb-text-secondary sm:text-lg">
              Create a league, draft real CFB players, and compete every Saturday.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild className="h-11 px-5">
              <Link to="/signup">Create Your League</Link>
            </Button>
            <Button asChild variant="outline" className="h-11 px-5">
              <Link to="/login">Log In</Link>
            </Button>
          </div>
          <p className="text-sm text-cfb-text-muted">Create a league, draft your team, and compete all season.</p>
        </div>

        <SurfaceCard variant="scoreboard" padding="default" className="space-y-5">
          <div className="flex items-center justify-between gap-4 border-b border-cfb-border-subtle pb-4">
            <div>
              <p className="cfb-micro-label text-cfb-brand">Matchup preview</p>
              <h2 className="mt-1 text-xl font-bold text-cfb-text-primary">Your game week, at a glance</h2>
            </div>
            <StatusBadge variant="projected">Projected</StatusBadge>
          </div>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div><p className="text-sm font-semibold text-cfb-text-primary">Your Team</p><p className="mt-1 text-3xl font-black tabular-nums text-cfb-brand">—</p></div>
            <span className="rounded-md border border-cfb-border-subtle px-2 py-1 text-xs font-bold text-cfb-text-secondary">vs</span>
            <div className="text-right"><p className="text-sm font-semibold text-cfb-text-primary">Opponent</p><p className="mt-1 text-3xl font-black tabular-nums text-cfb-text-secondary">—</p></div>
          </div>
          <div className="grid gap-px overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-border-subtle sm:grid-cols-3">
            {[{ label: "Draft", value: "Build your roster" }, { label: "Matchups", value: "Track every week" }, { label: "Pick 6", value: "Make your call" }].map((item) => (
              <div key={item.label} className="bg-cfb-surface p-3"><p className="cfb-micro-label">{item.label}</p><p className="mt-1 text-sm font-semibold text-cfb-text-primary">{item.value}</p></div>
            ))}
          </div>
        </SurfaceCard>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {[{ title: "Run your league", detail: "Invite managers, set rules, and keep the season moving." }, { title: "Draft real players", detail: "Search a CFB player pool, queue targets, and make every pick count." }, { title: "Compete each Saturday", detail: "Set your lineup and follow your matchup from kickoff to final." }].map((item, index) => (
          <SurfaceCard key={item.title} padding="compact"><p className="cfb-micro-label text-cfb-brand">0{index + 1}</p><h2 className="mt-2 text-base font-bold">{item.title}</h2><p className="mt-2 text-sm leading-6 text-cfb-text-secondary">{item.detail}</p></SurfaceCard>
        ))}
      </section>

      <footer className="border-t border-cfb-border-subtle pt-5 text-center text-sm text-cfb-text-muted">
        <p>© 2026 College Football Fantasy</p>
        <PublicLegalLinks className="mt-3" />
      </footer>
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
  const dashboardLeagues = useMemo(() => {
    if (!activeLeagueId) return leagues;
    const activeLeague = leagues.find((league) => league.id === activeLeagueId);
    return activeLeague ? [activeLeague, ...leagues.filter((league) => league.id !== activeLeagueId)] : leagues;
  }, [activeLeagueId, leagues]);

  const { data: workspace } = useLeagueWorkspace(
    selectedLeague?.id,
    Boolean(isLoggedIn && selectedLeague?.id),
  );

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

  const standings = workspace?.standings_summary ?? [];
  const ownedTeamName = workspace?.owned_team?.name ?? "Your Team";

  return (
    <div className="mx-auto w-full touch-pan-y max-w-7xl space-y-4 pb-[calc(env(safe-area-inset-bottom)+5.5rem)] pt-1 sm:space-y-6 sm:pb-24 sm:pt-3">
      <section className="rounded-lg border border-cfb-border-subtle bg-cfb-surface p-3 shadow-sm sm:p-5">
        <div className="mb-4 border-b border-cfb-border-subtle px-1 pb-4 sm:mb-5">
          <p className="cfb-micro-label text-cfb-brand">League dashboard</p>
          <h1 className="mt-1 text-2xl font-black tracking-[-0.04em] text-cfb-text-primary sm:text-3xl">
            Good to see you, {user?.firstName ?? "Manager"}.
          </h1>
        </div>
        {leaguesLoading ? (
          <SkeletonState rows={1} label="Loading your league matchups" />
        ) : leagues.length === 0 ? (
          <EmptyState
            title="No leagues joined yet"
            description="Create a league or join with an invite code to start building your team."
            actionLabel="Create League"
            onAction={() => navigate("/leagues/create")}
          />
        ) : (
          <LeagueMatchupCarousel
            leagues={dashboardLeagues}
            activeLeagueId={selectedLeague?.id}
            onOpenLeague={(leagueId) => {
              setActiveLeagueId(leagueId);
              navigate(`/league/${leagueId}/matchup`);
            }}
          />
        )}
      </section>

      <SaturdayPick6 embedded />

      <section className="grid gap-6 xl:grid-cols-2">
        <SurfaceCard variant="default" padding="none">
            <div className="border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
              <p className="cfb-micro-label text-cfb-brand">Roster Status</p>
              <h2 className="mt-1 text-xl font-black text-cfb-text-primary">{ownedTeamName}</h2>
            </div>
            <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-6">
              <div className="rounded-md border border-cfb-border-subtle bg-cfb-surface-raised/55 p-4">
                <ShieldCheck className="h-5 w-5 text-cfb-success" aria-hidden="true" />
                <p className="mt-3 text-2xl font-black text-cfb-text-primary">{rosterSize}</p>
                <p className="text-xs font-semibold text-cfb-text-muted">Players rostered</p>
              </div>
              <div className="rounded-md border border-cfb-border-subtle bg-cfb-surface-raised/55 p-4">
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
              <div className="px-6 py-8 text-center text-sm font-semibold text-cfb-text-muted">
                No scheduled drafts
              </div>
            ) : (
              upcomingDrafts.map((league) => (
                <div key={league.id} className="flex items-center gap-3 border-b border-cfb-border-subtle px-5 py-4 last:border-b-0 sm:px-6">
                  <Clock className="h-4 w-4 text-cfb-gold" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-cfb-text-primary">{league.name}</p>
                    <p className="text-[11px] font-semibold text-cfb-text-muted">
                      {formatDraftTime(league.draft?.draft_datetime_utc)}
                    </p>
                  </div>
                </div>
              ))
            )}
        </SurfaceCard>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <SurfaceCard variant="default" padding="none">
          <div className="border-b border-cfb-border-subtle px-5 py-4 sm:px-6">
            <p className="cfb-micro-label text-cfb-brand">League Standings</p>
          </div>
          {standings.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm font-semibold text-cfb-text-muted">
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
            <SkeletonState rows={2} label="Loading your alerts" className="p-5 sm:p-6" />
          ) : alerts.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm font-semibold text-cfb-text-muted">
              No alerts available
            </div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.id} className="flex items-start gap-4 border-b border-cfb-border-subtle px-5 py-5 last:border-b-0 sm:px-6">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-cfb-border-subtle bg-cfb-surface-raised text-cfb-brand">
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

      <div className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised px-5 py-4 text-sm font-semibold text-cfb-text-secondary">
        <CalendarClock className="mr-2 inline h-4 w-4 text-cfb-gold" aria-hidden="true" />
        Deadline and lock warnings should always be checked before kickoff.
      </div>
    </div>
  );
}
