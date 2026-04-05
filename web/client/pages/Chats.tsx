import { useEffect, useMemo, useState } from "react";
import { CalendarClock, MessageSquare, Newspaper, RefreshCw, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useLeagueNews, useLeagueWorkspace, useLeagues } from "@/hooks/use-leagues";

const formatTime = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";
  return parsed.toLocaleString();
};

export default function Chats() {
  const { data: leagues = [], isLoading: leaguesLoading } = useLeagues(50, true);
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | null>(activeLeagueId);

  useEffect(() => {
    if (!leagues.length) {
      setSelectedLeagueId(null);
      return;
    }
    setSelectedLeagueId((current) => {
      if (current && leagues.some((league) => league.id === current)) return current;
      if (activeLeagueId && leagues.some((league) => league.id === activeLeagueId)) {
        return activeLeagueId;
      }
      return leagues[0].id;
    });
  }, [activeLeagueId, leagues]);

  useEffect(() => {
    if (selectedLeagueId && selectedLeagueId !== activeLeagueId) {
      setActiveLeagueId(selectedLeagueId);
    }
  }, [activeLeagueId, selectedLeagueId, setActiveLeagueId]);

  const { data: workspace } = useLeagueWorkspace(selectedLeagueId ?? undefined, Boolean(selectedLeagueId));
  const {
    data: newsPayload,
    isLoading: newsLoading,
    refetch: refetchNews,
    isFetching: newsFetching,
  } = useLeagueNews(selectedLeagueId ?? undefined, 50, Boolean(selectedLeagueId));

  const selectedLeague = useMemo(
    () => leagues.find((league) => league.id === selectedLeagueId) ?? null,
    [leagues, selectedLeagueId]
  );
  const newsRows = newsPayload?.data ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12 pt-8">
      <div className="space-y-2">
        <h1 className="bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-6xl font-black uppercase italic tracking-tighter text-transparent">
          League Feed
        </h1>
        <p className="text-[10px] font-black uppercase tracking-[0.32em] text-muted-foreground/70">
          Live league activity, updates, and news
        </p>
      </div>

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardContent className="grid gap-4 p-6 md:grid-cols-[minmax(220px,1fr)_auto_auto] md:items-end">
          <div className="space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              League
            </p>
            <Select
              value={selectedLeagueId ? String(selectedLeagueId) : ""}
              onValueChange={(value) => setSelectedLeagueId(Number(value))}
            >
              <SelectTrigger className="h-12 rounded-xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.16em]">
                <SelectValue placeholder={leaguesLoading ? "Loading leagues..." : "Select league"} />
              </SelectTrigger>
              <SelectContent>
                {leagues.map((league) => (
                  <SelectItem key={league.id} value={String(league.id)}>
                    {league.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              Your Team
            </p>
            <p className="mt-1 text-xs font-black uppercase tracking-[0.14em] text-foreground">
              {workspace?.owned_team?.name ?? "Not assigned"}
            </p>
          </div>

          <button
            type="button"
            onClick={() => refetchNews()}
            className="flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-5 text-[10px] font-black uppercase tracking-[0.18em] text-foreground transition hover:border-white/20"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${newsFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="rounded-[2rem] border border-white/10 bg-card/40">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.24em] text-primary">
              <Newspaper className="h-4 w-4" />
              League Activity
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-5">
            {newsLoading ? (
              <p className="px-2 py-6 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Loading league feed...
              </p>
            ) : newsRows.length === 0 ? (
              <p className="px-2 py-6 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                No feed items yet for this league.
              </p>
            ) : (
              newsRows.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <p className="text-xs font-black uppercase tracking-[0.14em] text-foreground">
                        {item.headline}
                      </p>
                      {item.detail ? (
                        <p className="text-[11px] text-muted-foreground/80">{item.detail}</p>
                      ) : null}
                    </div>
                    <span className="rounded-lg border border-white/10 bg-black/20 px-2 py-1 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/70">
                      {item.transaction_type}
                    </span>
                  </div>
                  <p className="mt-2 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground/60">
                    {item.team_name || selectedLeague?.name || "League"} • {formatTime(item.created_at)}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="rounded-[2rem] border border-white/10 bg-card/40">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.24em] text-primary">
                <Users className="h-4 w-4" />
                Chat Rooms
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-5">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-foreground">
                  League News Room
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground/70">
                  Real-time room is sourced from persisted league activity and injury updates.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-foreground">
                  Global Chat
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground/70">
                  League-wide conversation space is coming soon.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-[2rem] border border-white/10 bg-card/40">
            <CardHeader className="border-b border-white/10">
              <CardTitle className="flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.24em] text-primary">
                <CalendarClock className="h-4 w-4" />
                Roadmap
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <p className="text-[11px] text-muted-foreground/75">
                Team chat channels and direct messaging will be added in the next release.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="rounded-[2rem] border border-white/10 bg-card/40">
        <CardContent className="flex items-center gap-3 p-5 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
          <MessageSquare className="h-4 w-4 text-primary" />
          Stay synced with every league move in one feed.
        </CardContent>
      </Card>
    </div>
  );
}
