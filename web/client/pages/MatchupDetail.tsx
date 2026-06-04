import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMatchupDetail } from "@/hooks/use-game-loop";
import type { Lineup } from "@/types/lineup";

const LineupPanel = ({ title, lineup }: { title: string; lineup: Lineup | null }) => (
  <Card className="bg-card/40 border-white/10 rounded-[2rem] overflow-hidden">
    <CardHeader className="border-b border-white/10">
      <CardTitle className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">{title}</CardTitle>
    </CardHeader>
    <CardContent className="p-0">
      {!lineup || lineup.entries.length === 0 ? (
        <div className="p-6 text-sm text-muted-foreground">No lineup snapshot yet.</div>
      ) : (
        <div className="divide-y divide-white/10">
          {lineup.entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between gap-4 p-4">
              <div>
                <p className="text-sm font-black text-foreground">{entry.player_name ?? `Player ${entry.player_id}`}</p>
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  {entry.player_position ?? "POS"} • {entry.slot}
                </p>
              </div>
              <span className="text-[10px] uppercase tracking-[0.18em] text-primary">
                {entry.is_starter ? "Starter" : "Bench"}
              </span>
            </div>
          ))}
        </div>
      )}
    </CardContent>
  </Card>
);

export default function MatchupDetail() {
  const { leagueId, matchupId } = useParams();
  const parsedLeagueId = leagueId && /^\d+$/.test(leagueId) ? Number(leagueId) : undefined;
  const parsedMatchupId = matchupId && /^\d+$/.test(matchupId) ? Number(matchupId) : undefined;
  const detailQuery = useMatchupDetail(parsedLeagueId, parsedMatchupId);
  const detail = detailQuery.data;

  return (
    <div className="max-w-6xl mx-auto py-10 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">Matchup Detail</p>
          <h1 className="text-4xl font-black italic uppercase text-foreground">
            {detail ? `${detail.matchup.away_team_name} @ ${detail.matchup.home_team_name}` : "Loading Matchup"}
          </h1>
        </div>
        {parsedLeagueId && <Button asChild variant="outline"><Link to={`/league/${parsedLeagueId}`}>League Hub</Link></Button>}
      </div>

      {detailQuery.isLoading || !detail ? (
        <Card className="bg-card/40 border-white/10 rounded-[2rem]">
          <CardContent className="p-8 text-sm text-muted-foreground">Loading matchup...</CardContent>
        </Card>
      ) : (
        <>
          <Card className="bg-card/40 border-white/10 rounded-[2rem]">
            <CardContent className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Away</p>
                <p className="text-2xl font-black text-foreground">{detail.matchup.away_team_name}</p>
                <p className="text-4xl font-black text-primary">{detail.matchup.away_score.toFixed(1)}</p>
              </div>
              <div className="text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                Week {detail.matchup.week} • {detail.matchup.status}
              </div>
              <div className="md:text-right">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Home</p>
                <p className="text-2xl font-black text-foreground">{detail.matchup.home_team_name}</p>
                <p className="text-4xl font-black text-primary">{detail.matchup.home_score.toFixed(1)}</p>
              </div>
            </CardContent>
          </Card>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <LineupPanel title={`${detail.matchup.away_team_name ?? "Away"} Lineup`} lineup={detail.away_lineup} />
            <LineupPanel title={`${detail.matchup.home_team_name ?? "Home"} Lineup`} lineup={detail.home_lineup} />
          </div>
        </>
      )}
    </div>
  );
}
