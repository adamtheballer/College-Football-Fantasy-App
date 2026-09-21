import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  Bell,
  Clock,
  ShieldCheck,
  Trophy,
} from "lucide-react";

import { EmptyState, SkeletonState } from "@/components/states";
import { LeagueMatchupCarousel } from "@/components/league/LeagueMatchupCarousel";
import { formatDisplayedProbabilityPair, validProbability } from "@/components/league/WinChanceMeter";
import { Button } from "@/components/ui/button";
import { PageHeader, PositionBadge, StatusBadge, SurfaceCard } from "@/components/fantasy";
import { PublicLegalLinks } from "@/components/legal/PublicLegalLinks";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagueWorkspace, useLeagues } from "@/hooks/use-leagues";
import { apiGet } from "@/lib/api";
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

export const formatDashboardWinChance = (
  myPercent: number | null | undefined,
  opponentPercent: number | null | undefined,
) => {
  if (
    !validProbability(myPercent) ||
    !validProbability(opponentPercent) ||
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

export function SaturdayPick6HomeFeature() {
  return (
    <SurfaceCard variant="default" padding="default" className="cfb-feature-surface border-cfb-gold/35 bg-cfb-surface-raised">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cfb-gold/45 bg-cfb-canvas text-cfb-gold">
            <Trophy className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="cfb-micro-label text-cfb-gold">Saturday Pick 6</p>
            <p className="mt-1 text-sm font-semibold text-cfb-text-secondary">Make your pick and view this week&apos;s contest.</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Link
            to="/saturday-pick-6"
            className="text-xs font-semibold text-cfb-text-secondary underline-offset-4 hover:text-cfb-gold hover:underline"
          >
            Open Saturday Pick 6 event
          </Link>
          <Button asChild variant="outline" className="border-cfb-gold/50 text-cfb-gold hover:bg-cfb-gold/10 hover:text-cfb-gold">
            <Link to="/saturday-pick-6">Make Your Pick</Link>
          </Button>
        </div>
      </div>
    </SurfaceCard>
  );
}

function GuestHome() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 pb-16 pt-5 sm:pt-10">
      <section className="grid gap-6 lg:grid-cols-[1.08fr_0.92fr] lg:items-center" aria-labelledby="guest-home-title">
        <div className="space-y-6">
          <div className="space-y-3">
            <p className="cfb-micro-label text-cfb-gold">CFFB · 2026 season</p>
            <h1 id="guest-home-title" className="cfb-display-title max-w-2xl text-4xl sm:text-5xl">
              Play College Fantasy Football in 2026
            </h1>
            <p className="max-w-xl text-base leading-7 text-cfb-text-secondary sm:text-lg">
              Create or join a college fantasy football league with CFFB. Draft real college players, manage your roster,
              make trades, use the waiver wire, set weekly lineups, and compete with friends throughout the season.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild className="h-11 px-5">
              <Link to="/signup">Create a League</Link>
            </Button>
            <Button asChild variant="outline" className="h-11 px-5">
              <Link to="/login?flow=signup">Join a League</Link>
            </Button>
            <a
              className="inline-flex h-11 items-center px-2 text-sm font-bold text-cfb-brand underline-offset-4 transition hover:text-cfb-cyan hover:underline"
              href="https://apps.apple.com/us/app/college-football-fantasy/id6804566813"
            >
              Download the App
            </a>
          </div>
          <p className="text-sm text-cfb-text-muted">Invite your managers, draft your team, and own every Saturday.</p>
        </div>

        <SurfaceCard variant="scoreboard" padding="default" className="cfb-feature-surface cfb-matte-surface space-y-5">
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

      <section aria-labelledby="league-tools-title" className="space-y-4">
        <div>
          <p className="cfb-micro-label text-cfb-brand">Built for real leagues</p>
          <h2 id="league-tools-title" className="mt-1 text-2xl font-black text-cfb-text-primary">College fantasy football from draft day to the final</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-cfb-text-secondary">CFFB gives college football fans a dedicated way to create a private league, draft players, manage a roster, submit waiver claims, make trades, and compete in weekly fantasy matchups.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { title: "Live Drafts", detail: "Build a roster together in a shared league draft room." },
            { title: "Weekly Matchups", detail: "Follow lineup scores and head-to-head results all season." },
            { title: "Waiver Wire", detail: "Review available players and make the roster moves that matter." },
            { title: "League Management", detail: "Invite managers, organize your season, and keep everyone connected." },
          ].map((item, index) => (
            <SurfaceCard key={item.title} padding="compact"><p className="cfb-micro-label text-cfb-brand">0{index + 1}</p><h3 className="mt-2 text-base font-bold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-cfb-text-secondary">{item.detail}</p></SurfaceCard>
          ))}
        </div>
      </section>

      <section aria-labelledby="how-cffb-works" className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
        <div>
          <p className="cfb-micro-label text-cfb-gold">How it works</p>
          <h2 id="how-cffb-works" className="mt-1 text-2xl font-black text-cfb-text-primary">Run your league in five plays</h2>
          <p className="mt-2 text-sm leading-6 text-cfb-text-secondary">Everything that matters to your league stays connected in one product.</p>
        </div>
        <ol className="grid gap-3 sm:grid-cols-2">
          {[
            ["Create or join a league", "Start a private league for your group or join from an invitation."],
            ["Draft college football players", "Build a team from the available player pool before the season."],
            ["Set your weekly lineup", "Choose your starters before games lock each week."],
            ["Make trades and waiver claims", "Improve your roster as the season and player roles change."],
            ["Compete through the season", "Follow matchups, standings, and the story of your league week by week."],
          ].map(([title, detail], index) => (
            <li key={title} className="flex gap-3 rounded-xl border border-cfb-border-subtle bg-cfb-surface/75 p-4">
              <span className="cfb-micro-label mt-0.5 text-cfb-brand">0{index + 1}</span>
              <div><h3 className="text-sm font-black text-cfb-text-primary">{title}</h3><p className="mt-1 text-sm leading-5 text-cfb-text-secondary">{detail}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="college-fantasy-football-faq" className="space-y-4">
        <div><p className="cfb-micro-label text-cfb-brand">Common questions</p><h2 id="college-fantasy-football-faq" className="mt-1 text-2xl font-black text-cfb-text-primary">College fantasy football FAQ</h2></div>
        <div className="grid gap-3 md:grid-cols-2">
          {[
            ["What is college fantasy football?", "It is a season-long game where managers draft real college players, set lineups, and compete based on player production."],
            ["Can I create a private league?", "Yes. Create a CFFB league, invite friends, schedule a draft, and manage the season together."],
            ["Does CFFB have waivers and trades?", "Yes. Managers can manage their rosters through waiver claims and league trades."],
            ["Is CFFB available on iPhone?", "Yes. College Football Fantasy is available on the App Store for iPhone."],
          ].map(([question, answer]) => (
            <SurfaceCard key={question} padding="compact"><h3 className="text-base font-bold text-cfb-text-primary">{question}</h3><p className="mt-2 text-sm leading-6 text-cfb-text-secondary">{answer}</p></SurfaceCard>
          ))}
        </div>
      </section>

      <nav aria-label="Learn more about CFFB" className="flex flex-wrap items-center gap-x-5 gap-y-3 border-y border-cfb-border-subtle py-5 text-sm font-bold text-cfb-brand">
        <a href="/how-to-play-college-fantasy-football" className="hover:text-cfb-cyan hover:underline">How to Play College Fantasy Football</a>
        <a href="/college-fantasy-football-leagues" className="hover:text-cfb-cyan hover:underline">Create or Join a League</a>
        <a href="/college-fantasy-football-waiver-wire" className="hover:text-cfb-cyan hover:underline">College Fantasy Football Waiver Wire</a>
        <a href="/about" className="hover:text-cfb-cyan hover:underline">About CFFB</a>
      </nav>

      <footer className="border-t border-cfb-border-subtle pt-5 text-center text-sm text-cfb-text-muted">
        <p>© 2026 CFFB · College Fantasy Football</p>
        <PublicLegalLinks className="mt-3" />
      </footer>
    </div>
  );
}

export default function Index() {
  const { isBootstrapping, isLoggedIn, user } = useAuth();
  const navigate = useNavigate();
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  // A cached manager can be rendered before the refresh cookie has restored
  // its access token. Do not start league-dependent queries in that short
  // window: parallel 401s can otherwise leave Home on its loading skeleton
  // even after the session becomes valid.
  const sessionReady = isLoggedIn && !isBootstrapping;
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(20, sessionReady);
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
    Boolean(sessionReady && selectedLeague?.id),
  );

  useEffect(() => {
    if (!sessionReady || !leagues.length) return;
    if (selectedLeague?.id && selectedLeague.id !== activeLeagueId) {
      setActiveLeagueId(selectedLeague.id);
    }
  }, [activeLeagueId, leagues.length, selectedLeague?.id, sessionReady, setActiveLeagueId]);

  useEffect(() => {
    if (!sessionReady) {
      setAlerts([]);
      setAlertsLoaded(!isBootstrapping);
      return;
    }

    const controller = new AbortController();
    apiGet<AlertPayload>("/notifications/alerts", { limit: 5 }, controller.signal)
      .then((payload) => setAlerts(payload.data ?? []))
      .catch(() => setAlerts([]))
      .finally(() => setAlertsLoaded(true));

    return () => controller.abort();
  }, [isBootstrapping, sessionReady]);

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
    <div className="mx-auto w-full max-w-7xl space-y-6 pb-[calc(env(safe-area-inset-bottom)+5rem)] pt-1 sm:pb-16 sm:pt-3">
      <section className="space-y-4">
        <PageHeader
          eyebrow="League dashboard"
          title={`Good to see you, ${user?.firstName ?? "Manager"}.`}
          description="Your current league, matchup, and time-sensitive decisions."
          className="cfb-home-league-header border-b-0 pb-2"
        />
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

      <SaturdayPick6HomeFeature />

      <section className="grid gap-4 xl:grid-cols-2">
        <SurfaceCard variant="default" padding="none">
            <div className="cfb-data-section-header">
              <p className="cfb-micro-label text-cfb-brand">Roster Status</p>
              <h2 className="mt-1 text-xl font-black text-cfb-text-primary">{ownedTeamName}</h2>
            </div>
            <div className="grid divide-y divide-cfb-border-subtle sm:grid-cols-2 sm:divide-x sm:divide-y-0">
              <div className="p-4 sm:p-5">
                <ShieldCheck className="h-5 w-5 text-cfb-success" aria-hidden="true" />
                <p className="mt-3 text-2xl font-black text-cfb-text-primary">{rosterSize}</p>
                <p className="text-xs font-semibold text-cfb-text-muted">Players rostered</p>
              </div>
              <div className="p-4 sm:p-5">
                <PositionBadge position="FLEX" />
                <p className="mt-3 text-sm font-bold text-cfb-text-secondary">
                  {rosterSize > 0 ? "Roster is ready for lineup review." : "Roster fills after the draft."}
                </p>
              </div>
            </div>
        </SurfaceCard>

        <SurfaceCard variant="default" padding="none">
            <div className="cfb-data-section-header">
              <p className="cfb-micro-label text-cfb-brand">Upcoming Drafts</p>
            </div>
            {upcomingDrafts.length === 0 ? (
              <div className="px-6 py-8 text-center text-sm font-semibold text-cfb-text-muted">
                No scheduled drafts
              </div>
            ) : (
              upcomingDrafts.map((league) => (
                <div key={league.id} className="cfb-data-row flex items-center gap-3 px-4 py-3 sm:px-5">
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

      <section className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <SurfaceCard variant="default" padding="none">
          <div className="cfb-data-section-header">
            <p className="cfb-micro-label text-cfb-brand">League Standings</p>
          </div>
          {standings.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm font-semibold text-cfb-text-muted">
              Standings appear after league schedule data is available
            </div>
          ) : (
            standings.slice(0, 5).map((standing, index) => (
              <div key={standing.team_id} className="cfb-data-row flex items-center justify-between px-4 py-3 sm:px-5">
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
          <div className="cfb-data-section-header">
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
              <div key={alert.id} className="cfb-data-row flex items-start gap-4 px-4 py-4 sm:px-5">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-sm bg-cfb-surface-raised text-cfb-brand">
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

    </div>
  );
}
