import { Activity, Bell, CheckCheck, MessageSquare, ShieldAlert, Timer, TrendingUp, Trophy, Zap } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useAuth } from "@/hooks/use-auth";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
} from "@/hooks/use-notifications";
import { cn } from "@/lib/utils";
import { resolveNotificationPath, type NotificationAlert } from "@/lib/notifications";

const icons: Record<string, typeof Bell> = {
  DRAFT: Timer,
  TRADE: Trophy,
  WAIVER: TrendingUp,
  MATCHUP: Trophy,
  CHAT: MessageSquare,
  PLAYER: Activity,
  INJURY: ShieldAlert,
  TOUCHDOWN: Zap,
  PROJECTION: Bell,
};

const colors: Record<string, string> = {
  DRAFT: "text-sky-300",
  TRADE: "text-emerald-300",
  WAIVER: "text-amber-300",
  MATCHUP: "text-violet-300",
  CHAT: "text-cyan-300",
  PLAYER: "text-blue-300",
  INJURY: "text-red-300",
};

const notificationCategory = (alert: NotificationAlert) => alert.category || alert.alert_type.split("_")[0] || "SYSTEM";

export default function Alerts() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setActiveLeagueId } = useActiveLeagueId();
  const alertsQuery = useNotifications(Boolean(user));
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();
  const alerts = alertsQuery.data?.data ?? [];
  const unreadCount = alertsQuery.data?.unread_count ?? 0;
  const subtitle = useMemo(
    () => (unreadCount ? `${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}` : "All caught up"),
    [unreadCount],
  );

  const openAlert = (alert: NotificationAlert) => {
    if (!alert.read_at) {
      markRead.mutate({ id: alert.id, read: true });
    }
    if (alert.destination?.league_id) {
      setActiveLeagueId(alert.destination.league_id);
    }
    navigate(resolveNotificationPath(alert.destination));
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-16 pt-2 sm:space-y-8">
      <div className="flex flex-col gap-4 border-b border-border/40 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <h1 className="text-4xl font-black uppercase italic tracking-tight text-foreground sm:text-5xl">Notifications</h1>
          <p className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">{subtitle}</p>
        </div>
        <Button
          variant="outline"
          disabled={!unreadCount || markAllRead.isPending}
          onClick={() => markAllRead.mutate()}
          className="h-10 rounded-xl border-primary/25 bg-primary/5 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-primary hover:bg-primary/10"
        >
          <CheckCheck className="mr-2 h-4 w-4" />
          Mark all read
        </Button>
      </div>

      <Card className="overflow-hidden rounded-3xl border-border/60 bg-card/45 shadow-[0_20px_50px_rgba(0,0,0,0.25)] backdrop-blur-md">
        <CardHeader className="border-b border-border/40 px-5 py-5 sm:px-7">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.22em] text-foreground">Notification center</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border/40 p-0">
          {alerts.map((alert) => {
            const category = notificationCategory(alert);
            const Icon = icons[category] ?? Bell;
            return (
              <button
                key={alert.id}
                type="button"
                onClick={() => openAlert(alert)}
                className={cn(
                  "flex w-full items-start gap-3 px-5 py-4 text-left transition hover:bg-white/[0.035] sm:gap-4 sm:px-7",
                  !alert.read_at && "bg-primary/[0.055]",
                )}
              >
                <span className={cn("mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5", colors[category] ?? "text-slate-300")}>
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1 space-y-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-sm font-bold text-foreground">{alert.title}</span>
                    {!alert.read_at ? <span className="h-2 w-2 shrink-0 rounded-full bg-primary" aria-label="Unread" /> : null}
                  </span>
                  <span className="block text-xs leading-relaxed text-muted-foreground">{alert.body}</span>
                  <span className="block text-[10px] font-bold uppercase tracking-[0.13em] text-muted-foreground/65">
                    {new Date(alert.sent_at).toLocaleString()}
                  </span>
                </span>
              </button>
            );
          })}
          {alertsQuery.isLoading ? (
            <p className="px-7 py-10 text-center text-sm text-muted-foreground">Loading notifications…</p>
          ) : null}
          {!alertsQuery.isLoading && alerts.length === 0 ? (
            <p className="px-7 py-12 text-center text-sm text-muted-foreground">No notifications yet.</p>
          ) : null}
          {alertsQuery.isError ? (
            <p role="alert" className="px-7 py-4 text-sm text-red-300">Unable to load notifications.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
