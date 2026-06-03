import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bell,
  CalendarClock,
  ChevronRight,
  ShieldCheck,
  Trophy,
  Users,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useLeagueWorkspace, useLeagues } from "@/hooks/use-leagues";
import { apiGet } from "@/lib/api";

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

const formatStatus = (status: string) => status.replace(/_/g, " ");

const formatDraftTime = (value: string | null | undefined) => {
  if (!value) return "Draft not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Draft not scheduled";
  return parsed.toLocaleString();
};

const HomeStatCard = ({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Trophy;
}) => (
  <Card className="cfb-color-wash bg-card/55 backdrop-blur-md border border-cyan-200/10 rounded-[2.5rem] overflow-hidden transition-all duration-300 hover:border-primary/35 hover:-translate-y-0.5">
    <CardContent className="p-8">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <p className="text-[10px] font-black uppercase tracking-[0.28em] text-muted-foreground/60">
            {label}
          </p>
          <p className="text-4xl font-black italic tracking-tight text-foreground">
            {value}
          </p>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300/30 to-blue-500/28 text-primary shadow-[0_0_30px_rgba(34,211,238,0.18)]">
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </CardContent>
  </Card>
);

export default function Index() {
  const { isLoggedIn, user } = useAuth();
  const navigate = useNavigate();
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(20, isLoggedIn);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [alertsLoaded, setAlertsLoaded] = useState(false);

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
    Boolean(isLoggedIn && selectedLeague?.id)
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

  const stats = useMemo(() => {
    const leagueCount = leagues.length;
    const totalMembers = leagues.reduce((sum, league) => sum + league.members.length, 0);
    const rosterSize = workspace?.roster?.length ?? 0;
    const draftReadyCount = leagues.filter(
      (league) => league.status === "draft_live" || league.status === "draft_scheduled"
    ).length;

    return [
      { label: "Active Leagues", value: String(leagueCount), icon: Trophy },
      { label: "Managers Joined", value: String(totalMembers), icon: Users },
      { label: "Rostered Players", value: String(rosterSize), icon: ShieldCheck },
      { label: "Draft Ready", value: String(draftReadyCount), icon: CalendarClock },
    ];
  }, [leagues, workspace?.roster?.length]);

  const upcomingDrafts = useMemo(
    () =>
      [...leagues]
        .filter((league) => Boolean(league.draft?.draft_datetime_utc))
        .sort((left, right) => {
          const l = new Date(left.draft?.draft_datetime_utc ?? "").getTime();
          const r = new Date(right.draft?.draft_datetime_utc ?? "").getTime();
          return l - r;
        })
        .slice(0, 4),
    [leagues]
  );
  const dashboardHeroTitle = `Welcome ${user?.firstName?.toUpperCase() ?? "Manager"}`;

  if (!isLoggedIn) {
    return (
      <div className="relative max-w-6xl mx-auto space-y-12 overflow-hidden pb-20 pt-12">
        <div className="pointer-events-none absolute -left-16 top-12 h-48 w-48 rounded-full bg-primary/14 blur-[90px]" />
        <div className="pointer-events-none absolute right-4 top-28 h-36 w-36 rounded-full bg-cyan-300/10 blur-[70px]" />
        <div className="pointer-events-none absolute right-28 top-10 h-24 w-24 rounded-full bg-amber-300/08 blur-[56px]" />
        <div className="relative space-y-6">
          <p className="text-[10px] font-black uppercase tracking-[0.5em] text-primary">
            College Football Fantasy
          </p>
          <h1
            className="cfb-home-hero-title text-7xl font-black italic uppercase tracking-tight"
            data-text="College Football Fantasy"
          >
            College Football Fantasy
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Backend-driven league management, roster actions, waivers, injuries, and projections
            built for Power 4 fantasy.
          </p>
          <div className="flex flex-wrap gap-4">
            <Button asChild className="h-12 rounded-2xl px-8 text-[10px] font-black uppercase tracking-[0.2em]">
              <Link to="/login">Sign In</Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-12 rounded-2xl px-8 text-[10px] font-black uppercase tracking-[0.2em]"
            >
              <Link to="/signup">Create Account</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative max-w-7xl mx-auto space-y-10 overflow-hidden pb-20 pt-12">
      <div className="pointer-events-none absolute -left-20 top-4 h-56 w-56 rounded-full bg-primary/12 blur-[100px]" />
      <div className="pointer-events-none absolute right-8 top-24 h-44 w-44 rounded-full bg-cyan-300/09 blur-[80px]" />
      <div className="pointer-events-none absolute right-40 top-12 h-32 w-32 rounded-full bg-amber-300/07 blur-[70px]" />
      <div className="relative space-y-4">
        <p className="text-[10px] font-black uppercase tracking-[0.5em] text-primary">
          Dashboard Overview
        </p>
        <h1
          className="cfb-home-hero-title text-6xl font-black italic uppercase tracking-tight"
          data-text={dashboardHeroTitle}
        >
          {dashboardHeroTitle}
        </h1>
        <p className="text-lg text-muted-foreground">
          Jump into your current league, draft workflow, and weekly decisions from one dashboard.
        </p>
      </div>

      {selectedLeague && (
        <Card className="cfb-color-wash bg-card/55 backdrop-blur-md border border-primary/20 rounded-[2.5rem] overflow-hidden shadow-[0_24px_70px_rgba(10,15,35,0.32)]">
          <CardContent className="p-6 md:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="space-y-2">
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">
                Resume League
              </p>
              <p className="text-2xl font-black italic text-foreground uppercase tracking-tight">
                {selectedLeague.name}
              </p>
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-muted-foreground/70">
                {formatStatus(selectedLeague.status)} • Draft {formatDraftTime(selectedLeague.draft?.draft_datetime_utc)}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                className="h-11 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
                onClick={() => navigate(`/league/${selectedLeague.id}`)}
              >
                Open League Hub
              </Button>
              {(selectedLeague.draft?.status === "live" || selectedLeague.status === "draft_live") && (
                <Button
                  variant="outline"
                  className="h-11 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] border-primary/30 text-primary"
                  onClick={() => navigate(`/league/${selectedLeague.id}/lobby`)}
                >
                  Open Draft Lobby
                </Button>
              )}
              {selectedLeague.draft?.status === "scheduled" && (
                <Button
                  variant="outline"
                  className="h-11 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] border-primary/30 text-primary"
                  onClick={() => navigate(`/league/${selectedLeague.id}/lobby`)}
                >
                  Join Draft Lobby
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <HomeStatCard
            key={stat.label}
            label={stat.label}
            value={stat.value}
            icon={stat.icon}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <Card className="cfb-color-wash bg-card/55 border-cyan-200/10 rounded-[2.5rem] overflow-hidden">
          <CardHeader className="border-b border-white/10 bg-white/[0.04]">
            <CardTitle className="text-[10px] font-black uppercase tracking-[0.32em] text-primary">
              Your Leagues
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {leaguesLoading ? (
              <div className="px-8 py-12 text-center text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                Loading leagues...
              </div>
            ) : leagues.length === 0 ? (
              <div className="px-8 py-12 text-center space-y-4">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                  No leagues joined yet
                </p>
                <Button
                  onClick={() => navigate("/leagues/create")}
                  className="h-11 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]"
                >
                  Create League
                </Button>
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
                    className={`flex w-full items-center justify-between border-b border-white/10 px-8 py-5 text-left last:border-b-0 hover:bg-white/[0.04] ${
                      isActive ? "bg-primary/12" : ""
                    }`}
                  >
                    <div className="space-y-1">
                      <p className="text-sm font-black italic uppercase tracking-tight text-foreground">
                        {league.name}
                      </p>
                      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/70">
                        {formatStatus(league.status)} • {league.members.length}/{league.max_teams} members
                      </p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-primary" />
                  </button>
                );
              })
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="cfb-color-wash bg-card/55 border-cyan-200/10 rounded-[2.5rem] overflow-hidden">
            <CardHeader className="border-b border-white/10 bg-white/[0.04]">
              <CardTitle className="text-[10px] font-black uppercase tracking-[0.32em] text-primary">
                Upcoming Drafts
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {upcomingDrafts.length === 0 ? (
                <div className="px-8 py-10 text-center text-[10px] font-black uppercase tracking-[0.25em] text-muted-foreground/60">
                  No scheduled drafts
                </div>
              ) : (
                upcomingDrafts.map((league) => (
                  <div key={league.id} className="border-b border-white/10 px-8 py-5 last:border-b-0">
                    <p className="text-[13px] font-black uppercase tracking-tight text-foreground">
                      {league.name}
                    </p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/70">
                      {formatDraftTime(league.draft?.draft_datetime_utc)}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="cfb-color-wash bg-card/55 border-cyan-200/10 rounded-[2.5rem] overflow-hidden">
            <CardHeader className="border-b border-white/10 bg-white/[0.04]">
              <CardTitle className="text-[10px] font-black uppercase tracking-[0.32em] text-primary">
                League Alerts
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {!alertsLoaded ? (
                <div className="px-8 py-10 text-center text-[10px] font-black uppercase tracking-[0.25em] text-muted-foreground/60">
                  Loading alerts...
                </div>
              ) : alerts.length === 0 ? (
                <div className="px-8 py-10 text-center text-[10px] font-black uppercase tracking-[0.25em] text-muted-foreground/60">
                  No alerts available
                </div>
              ) : (
                alerts.map((alert) => (
                  <div key={alert.id} className="flex items-start gap-4 border-b border-white/10 px-8 py-5 last:border-b-0">
                    <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5">
                      <Bell className="h-4 w-4 text-primary" />
                    </div>
                    <div className="min-w-0 space-y-1">
                      <p className="text-[11px] font-black uppercase tracking-[0.2em] text-foreground">
                        {alert.title}
                      </p>
                      <p className="text-xs text-muted-foreground">{alert.body}</p>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
