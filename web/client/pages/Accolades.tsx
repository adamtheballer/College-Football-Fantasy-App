import React, { useEffect, useMemo, useState } from "react";
import { Crown, Medal, Flame, Swords, Trophy, Percent, ArrowRightLeft, BarChart3 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

type AccoladesPayload = {
  user_id: number;
  first_name: string;
  time_on_app_hours: number;
  trades_sent: number;
  matchups_won: number;
  matchups_played: number;
  global_rank: number | null;
  global_percentile: number | null;
};

type DynastyPayload = {
  user_id: number;
  championships: number;
  win_pct: number;
  trades_completed: number;
  total_points_scored: number;
  years_played: number;
  dynasty_power_rating: number;
};

type RivalRow = {
  rival_user_id: number;
  rival_name: string;
  record_wins: number;
  record_losses: number;
  total_points_for: number;
  total_points_against: number;
  matchup_count: number;
  trash_talk_score: number;
};

type UserLeaderboardRow = {
  user_id: number;
  name: string;
  championships: number;
  win_pct: number;
  total_points: number;
  trades_completed: number;
  dynasty_power_rating: number;
};

const metricCards = (
  accolades: AccoladesPayload | null,
  dynasty: DynastyPayload | null
) => [
  {
    label: "Time On App",
    value: `${accolades?.time_on_app_hours ?? 0}h`,
    icon: Flame,
    color: "text-amber-300",
  },
  {
    label: "Trades Sent",
    value: `${accolades?.trades_sent ?? 0}`,
    icon: ArrowRightLeft,
    color: "text-primary",
  },
  {
    label: "Matchups Won",
    value: `${accolades?.matchups_won ?? 0}/${accolades?.matchups_played ?? 0}`,
    icon: Trophy,
    color: "text-emerald-400",
  },
  {
    label: "Global Rank",
    value: accolades?.global_rank ? `#${accolades.global_rank}` : "N/A",
    icon: Crown,
    color: "text-purple-300",
  },
  {
    label: "Dynasty Rating",
    value: dynasty ? dynasty.dynasty_power_rating.toFixed(1) : "0.0",
    icon: Medal,
    color: "text-cyan-300",
  },
  {
    label: "Win %",
    value: dynasty ? `${dynasty.win_pct.toFixed(1)}%` : "0.0%",
    icon: Percent,
    color: "text-blue-300",
  },
];

export default function Accolades() {
  const { user } = useAuth();
  const [accolades, setAccolades] = useState<AccoladesPayload | null>(null);
  const [dynasty, setDynasty] = useState<DynastyPayload | null>(null);
  const [rivalries, setRivalries] = useState<RivalRow[]>([]);
  const [leaderboard, setLeaderboard] = useState<UserLeaderboardRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    Promise.all([
      apiGet<AccoladesPayload>("/insights/accolades"),
      apiGet<DynastyPayload>("/insights/dynasty"),
      apiGet<{ data: RivalRow[] }>("/insights/rivalries"),
      apiGet<{ data: UserLeaderboardRow[] }>("/insights/users/leaderboard", { limit: 25 }),
    ])
      .then(([acc, dyn, riv, lb]) => {
        setAccolades(acc);
        setDynasty(dyn);
        setRivalries(riv?.data ?? []);
        setLeaderboard(lb?.data ?? []);
      })
      .catch(() => {
        setAccolades(null);
        setDynasty(null);
        setRivalries([]);
        setLeaderboard([]);
      })
      .finally(() => setLoading(false));
  }, [user]);

  const cards = useMemo(() => metricCards(accolades, dynasty), [accolades, dynasty]);

  return (
    <div className="max-w-7xl mx-auto space-y-10 animate-in fade-in duration-700 pb-16">
      <div className="space-y-2">
        <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground">
          Accolades
        </h1>
        <p className="text-[11px] font-black tracking-[0.35em] text-primary uppercase">
          Career, Rivalry, and Dynasty Profile
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {cards.map((card) => (
          <Card key={card.label} className="bg-card/40 border border-white/10 rounded-[2rem]">
            <CardContent className="p-6 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">
                  {card.label}
                </p>
                <p className="text-3xl font-black italic tracking-tight text-foreground">{card.value}</p>
              </div>
              <card.icon className={`w-6 h-6 ${card.color}`} />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-6">
        <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.28em] text-primary">
              <Swords className="w-4 h-4" />
              Rivalry System
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Loading rivalries...
              </div>
            ) : rivalries.length === 0 ? (
              <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                No rivalry matchups yet.
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-white/5 border-b border-white/10">
                  <tr>
                    <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Rival</th>
                    <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Record</th>
                    <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Points</th>
                    <th className="px-6 py-4 text-right text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Trash Talk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {rivalries.map((row) => (
                    <tr key={row.rival_user_id}>
                      <td className="px-6 py-4 text-[12px] font-black italic uppercase text-foreground">{row.rival_name}</td>
                      <td className="px-6 py-4 text-[11px] font-bold text-muted-foreground/80">
                        {row.record_wins}-{row.record_losses}
                      </td>
                      <td className="px-6 py-4 text-[11px] font-bold text-muted-foreground/80">
                        {row.total_points_for.toFixed(1)} - {row.total_points_against.toFixed(1)}
                      </td>
                      <td className="px-6 py-4 text-right text-[11px] font-black text-primary">
                        {row.trash_talk_score}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.28em] text-primary">
              <BarChart3 className="w-4 h-4" />
              Dynasty Career
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-5">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
              <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">Championships</p>
              <p className="text-3xl font-black italic text-foreground">{dynasty?.championships ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
              <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">Years Played</p>
              <p className="text-3xl font-black italic text-foreground">{dynasty?.years_played ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
              <p className="text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">Total Points</p>
              <p className="text-3xl font-black italic text-foreground">{(dynasty?.total_points_scored ?? 0).toFixed(1)}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-card/40 border border-white/10 rounded-[2.5rem] overflow-hidden">
        <CardHeader className="border-b border-white/10">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
            Global User Leaderboard
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {leaderboard.length === 0 ? (
            <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              No user analytics data yet.
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-white/5 border-b border-white/10">
                <tr>
                  <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Rank</th>
                  <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">User</th>
                  <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Power</th>
                  <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Win%</th>
                  <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Titles</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {leaderboard.map((row, idx) => (
                  <tr key={row.user_id}>
                    <td className="px-6 py-4 text-[12px] font-black text-primary">#{idx + 1}</td>
                    <td className="px-6 py-4 text-[12px] font-black uppercase tracking-[0.1em] text-foreground">{row.name}</td>
                    <td className="px-6 py-4 text-[11px] font-black text-foreground">{row.dynasty_power_rating.toFixed(1)}</td>
                    <td className="px-6 py-4 text-[11px] font-bold text-muted-foreground/80">{row.win_pct.toFixed(1)}%</td>
                    <td className="px-6 py-4 text-[11px] font-bold text-muted-foreground/80">{row.championships}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

