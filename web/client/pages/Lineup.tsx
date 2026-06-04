import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeagueWorkspace } from "@/hooks/use-leagues";
import { useTeamLineup, useUpdateLineup } from "@/hooks/use-game-loop";
import type { LineupAssignment } from "@/types/lineup";

const SLOT_OPTIONS = ["QB", "RB", "WR", "TE", "FLEX", "K", "BENCH", "IR"];

export default function LineupPage() {
  const { leagueId } = useParams();
  const parsedLeagueId = leagueId && /^\d+$/.test(leagueId) ? Number(leagueId) : undefined;
  const [week, setWeek] = useState(1);
  const workspaceQuery = useLeagueWorkspace(parsedLeagueId);
  const workspace = workspaceQuery.data;
  const season = workspace?.league.season_year ?? 2026;
  const teamId = workspace?.owned_team?.id;
  const lineupQuery = useTeamLineup(parsedLeagueId, teamId, season, week);
  const updateLineup = useUpdateLineup(parsedLeagueId ?? 0, teamId ?? 0, season, week);

  const [localAssignments, setLocalAssignments] = useState<Record<number, LineupAssignment>>({});
  const entries = lineupQuery.data?.entries ?? [];
  const assignments = useMemo(() => {
    return entries.map((entry) => localAssignments[entry.player_id] ?? {
      roster_entry_id: entry.roster_entry_id,
      player_id: entry.player_id,
      slot: entry.slot,
      is_starter: entry.is_starter,
    });
  }, [entries, localAssignments]);

  const setAssignment = (playerId: number, patch: Partial<LineupAssignment>) => {
    const existing = assignments.find((row) => row.player_id === playerId);
    if (!existing) return;
    setLocalAssignments((current) => ({
      ...current,
      [playerId]: { ...existing, ...patch },
    }));
  };

  const save = () => {
    updateLineup.mutate({ assignments });
  };

  if (!parsedLeagueId) {
    return <div className="max-w-4xl mx-auto py-16 text-red-300">Invalid league ID.</div>;
  }

  return (
    <div className="max-w-6xl mx-auto py-10 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">Weekly Lineup</p>
          <h1 className="text-4xl font-black italic uppercase text-foreground">
            {workspace?.owned_team?.name ?? "My Team"}
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setWeek((value) => Math.max(1, value - 1))}>Prev Week</Button>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-black">
            Week {week}
          </div>
          <Button variant="outline" onClick={() => setWeek((value) => value + 1)}>Next Week</Button>
          <Button asChild variant="outline"><Link to={`/league/${parsedLeagueId}`}>League Hub</Link></Button>
        </div>
      </div>

      {!teamId ? (
        <Card className="bg-card/40 border-white/10 rounded-[2rem]">
          <CardContent className="p-8 text-sm text-muted-foreground">You do not own a team in this league yet.</CardContent>
        </Card>
      ) : (
        <Card className="bg-card/40 border-white/10 rounded-[2rem] overflow-hidden">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">
              Week {week} Lineup • {lineupQuery.data?.status ?? "loading"}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {lineupQuery.isLoading ? (
              <div className="p-8 text-sm text-muted-foreground">Loading lineup...</div>
            ) : entries.length === 0 ? (
              <div className="p-8 text-sm text-muted-foreground">No rostered players are available for this lineup.</div>
            ) : (
              <div className="divide-y divide-white/10">
                {entries.map((entry) => {
                  const assignment = assignments.find((row) => row.player_id === entry.player_id);
                  return (
                    <div key={entry.id} className="grid grid-cols-1 md:grid-cols-[1fr_160px_160px] gap-4 p-5 items-center">
                      <div>
                        <p className="text-sm font-black text-foreground">{entry.player_name ?? `Player ${entry.player_id}`}</p>
                        <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                          {entry.player_position ?? "POS"} • {entry.player_school ?? "School"}
                        </p>
                      </div>
                      <select
                        className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs font-bold text-foreground"
                        value={assignment?.slot ?? entry.slot}
                        disabled={lineupQuery.data?.status !== "editable"}
                        onChange={(event) => {
                          const slot = event.target.value;
                          setAssignment(entry.player_id, { slot, is_starter: !["BENCH", "IR"].includes(slot) });
                        }}
                      >
                        {SLOT_OPTIONS.map((slot) => <option key={slot} value={slot}>{slot}</option>)}
                      </select>
                      <select
                        className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs font-bold text-foreground"
                        value={String(assignment?.is_starter ?? entry.is_starter)}
                        disabled={lineupQuery.data?.status !== "editable"}
                        onChange={(event) => setAssignment(entry.player_id, { is_starter: event.target.value === "true" })}
                      >
                        <option value="true">Starter</option>
                        <option value="false">Bench</option>
                      </select>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="p-5 flex flex-wrap items-center gap-3 border-t border-white/10">
              <Button
                onClick={save}
                disabled={lineupQuery.data?.status !== "editable" || updateLineup.isPending}
                className="rounded-2xl text-[10px] font-black uppercase tracking-[0.18em]"
              >
                Save Lineup
              </Button>
              {updateLineup.error && (
                <p className="text-xs text-red-300">{updateLineup.error.message}</p>
              )}
              {updateLineup.isSuccess && (
                <p className="text-xs text-emerald-300">Lineup saved.</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
