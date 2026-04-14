import React, { useEffect, useMemo, useState } from "react";
import { Bell, Zap, Activity, TrendingUp, ShieldAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import { useLeagues } from "@/hooks/use-leagues";

const iconMap: Record<string, any> = {
  INJURY: ShieldAlert,
  TOUCHDOWN: Zap,
  USAGE: Activity,
  WAIVER: TrendingUp,
  PROJECTION: Bell,
};

const typeColors: Record<string, string> = {
  INJURY: "text-red-400",
  TOUCHDOWN: "text-emerald-400",
  USAGE: "text-blue-400",
  WAIVER: "text-amber-400",
  PROJECTION: "text-purple-400",
};

export default function Alerts() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setActiveLeagueId } = useActiveLeagueId();
  const { data: leagueRows = [] } = useLeagues();
  const [alerts, setAlerts] = useState<
    {
      id: number;
      type: string;
      title: string;
      body: string;
      timestamp: string;
      payload: Record<string, unknown> | null;
    }[]
  >([]);
  const [loaded, setLoaded] = useState(false);

  const leaguesById = useMemo(
    () => new Map(leagueRows.map((league) => [league.id, league.name])),
    [leagueRows]
  );

  const resolveAlertPath = (alertType: string, payload: Record<string, unknown> | null) => {
    const rawPath = payload?.path;
    if (typeof rawPath === "string" && rawPath.trim()) {
      return rawPath;
    }
    const leagueId = payload?.league_id;
    const leaguePath =
      typeof leagueId === "number" && Number.isFinite(leagueId)
        ? `/league/${leagueId}`
        : "/leagues";
    switch (alertType) {
      case "WAIVER":
        return "/waivers";
      case "INJURY":
        return "/injury-center";
      case "PROJECTION":
      case "TOUCHDOWN":
      case "USAGE":
      default:
        return leaguePath;
    }
  };

  const openAlertDestination = (alert: {
    id: number;
    type: string;
    payload: Record<string, unknown> | null;
  }) => {
    const leagueId = alert.payload?.league_id;
    if (typeof leagueId === "number" && Number.isFinite(leagueId)) {
      setActiveLeagueId(leagueId);
    }
    navigate(resolveAlertPath(alert.type, alert.payload));
  };

  useEffect(() => {
    if (!user) {
      setAlerts([]);
      setLoaded(true);
      return;
    }
    const controller = new AbortController();
    apiGet<{ data: any[] }>("/notifications/alerts", { limit: 50 }, controller.signal)
      .then((payload) => {
        if (!payload?.data?.length) {
          setAlerts([]);
          return;
        }
        const mapped = payload.data.map((row) => ({
          id: row.id,
          type: row.alert_type,
          title: row.title,
          body: row.body,
          timestamp: row.sent_at ? new Date(row.sent_at).toLocaleString() : "Just now",
          payload: row.payload && typeof row.payload === "object" ? row.payload : null,
        }));
        setAlerts(mapped);
      })
      .catch(() => {
        setAlerts([]);
      })
      .finally(() => setLoaded(true));
    return () => controller.abort();
  }, [user]);

  return (
    <div className="max-w-5xl mx-auto space-y-10 animate-in fade-in duration-1000">
      <div className="space-y-2">
        <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground">
          Alerts
        </h1>
        <p className="text-[11px] font-black tracking-[0.4em] text-primary uppercase">
          Real-Time Fantasy Signals
        </p>
      </div>

      <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl">
        <CardHeader className="px-10 py-8 border-b border-white/5 bg-white/5">
          <CardTitle className="text-[10px] font-black tracking-[0.5em] text-primary uppercase">
            Notification Feed
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 divide-y divide-white/10">
          {alerts.map((alert) => {
            const Icon = iconMap[alert.type] || Bell;
            const leagueId = alert.payload?.league_id;
            const leagueLabel =
              typeof leagueId === "number" && leaguesById.has(leagueId)
                ? leaguesById.get(leagueId)
                : null;
            return (
              <button
                key={alert.id}
                type="button"
                onClick={() => openAlertDestination(alert)}
                className="flex w-full items-center gap-6 px-10 py-6 text-left hover:bg-white/[0.04] transition-all"
              >
                <div className={cn("w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center", typeColors[alert.type])}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 space-y-1">
                  <h3 className="text-[12px] font-black uppercase tracking-widest text-foreground">{alert.title}</h3>
                  <p className="text-[11px] font-medium text-muted-foreground/70">{alert.body}</p>
                  {leagueLabel ? (
                    <p className="text-[9px] font-black uppercase tracking-[0.22em] text-primary/80">
                      {leagueLabel}
                    </p>
                  ) : null}
                </div>
                <span className="text-[9px] font-black uppercase tracking-widest text-muted-foreground/40">{alert.timestamp}</span>
              </button>
            );
          })}
          {loaded && alerts.length === 0 && (
            <div className="px-10 py-12 text-center">
              <p className="text-[10px] font-black tracking-[0.3em] text-muted-foreground/60 uppercase">
                No league player alerts right now
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
