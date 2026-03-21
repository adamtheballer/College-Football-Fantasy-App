import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardList, Trophy, ArrowRight, Users, ShieldAlert } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLeagues } from "@/hooks/use-leagues";
import { useLeagueTeams, useTeamRoster } from "@/hooks/use-teams";
import { ApiError } from "@/lib/api";
import type { RosterEntry } from "@/types/roster";
import type { Team } from "@/types/team";

const SLOT_ORDER = ["QB", "RB", "WR", "TE", "K", "FLEX", "SUPERFLEX", "BENCH", "IR"];

const formatApiError = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Sign in again to load roster data.";
    if (error.status === 403) return "You do not have access to this roster view.";
    if (error.status === 404) return "The selected roster view could not be found.";
    return error.message || fallback;
  }

  return fallback;
};

const sortRosterEntries = (entries: RosterEntry[]) => {
  return [...entries].sort((left, right) => {
    const slotDelta =
      SLOT_ORDER.indexOf(left.slot) - SLOT_ORDER.indexOf(right.slot);
    if (slotDelta !== 0) {
      return slotDelta;
    }
    return left.player.name.localeCompare(right.player.name);
  });
};

const RosterTable = ({ entries }: { entries: RosterEntry[] }) => {
  const sortedEntries = useMemo(() => sortRosterEntries(entries), [entries]);

  if (sortedEntries.length === 0) {
    return (
      <div className="rounded-[2rem] border border-dashed border-white/10 bg-white/[0.03] px-6 py-10 text-center">
        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
          No roster entries yet
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.03]">
      <div className="grid grid-cols-[110px_minmax(0,1fr)_120px_120px] gap-4 border-b border-white/10 px-6 py-4 text-[9px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
        <span>Slot</span>
        <span>Player</span>
        <span>School</span>
        <span>Status</span>
      </div>
      {sortedEntries.map((entry) => (
        <div
          key={entry.id}
          className="grid grid-cols-[110px_minmax(0,1fr)_120px_120px] gap-4 border-b border-white/5 px-6 py-4 last:border-b-0"
        >
          <span className="text-[10px] font-black uppercase tracking-[0.25em] text-primary">
            {entry.slot}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-black uppercase tracking-tight text-foreground">
              {entry.player.name}
            </p>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
              {entry.player.position}
            </p>
          </div>
          <span className="truncate text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
            {entry.player.school}
          </span>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
            {entry.status}
          </span>
        </div>
      ))}
    </div>
  );
};

const TeamRosterCard = ({ team }: { team: Team }) => {
  const {
    data: rosterPayload,
    isLoading,
    isError,
    error,
  } = useTeamRoster(team.id);

  return (
    <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] overflow-hidden">
      <CardContent className="p-8 space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1.25rem] bg-gradient-to-br from-primary to-blue-600 shadow-2xl">
                <Users className="h-5 w-5 text-white" />
              </div>
              <div>
                <h3 className="text-2xl font-black italic uppercase tracking-tight text-foreground">
                  {team.name}
                </h3>
                <p className="text-[10px] font-black uppercase tracking-[0.25em] text-muted-foreground/60">
                  Owner {team.owner_name || "Unassigned"}
                </p>
              </div>
            </div>
          </div>
          <Button
            asChild
            type="button"
            variant="outline"
            className="h-11 rounded-2xl px-5 text-[10px] font-black uppercase tracking-[0.2em]"
          >
            <Link to={`/league/${team.league_id}`}>
              League Hub
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] px-6 py-10 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
              Loading roster...
            </p>
          </div>
        ) : isError ? (
          <div className="rounded-[2rem] border border-red-400/20 bg-red-500/5 px-6 py-10 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-red-300">
              {formatApiError(error, "Unable to load roster entries.")}
            </p>
          </div>
        ) : (
          <RosterTable entries={rosterPayload?.data ?? []} />
        )}
      </CardContent>
    </Card>
  );
};

const LeagueSelectorCard = ({
  id,
  name,
  memberCount,
  maxTeams,
  status,
  isActive,
  onSelect,
}: {
  id: number;
  name: string;
  memberCount: number;
  maxTeams: number;
  status: string;
  isActive: boolean;
  onSelect: (leagueId: number) => void;
}) => (
  <button type="button" onClick={() => onSelect(id)} className="w-full text-left">
    <Card
      className={`bg-card/40 backdrop-blur-md border rounded-[3rem] overflow-hidden transition-all duration-500 hover:scale-[1.02] cursor-pointer ${
        isActive ? "border-primary/40 shadow-[0_0_0_1px_rgba(59,130,246,0.3)]" : "border-white/5"
      }`}
    >
      <CardContent className="p-10 relative z-10 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div className="w-20 h-20 rounded-[2rem] flex items-center justify-center shadow-2xl transition-transform duration-500 bg-gradient-to-br from-primary to-blue-600">
            <Trophy className="w-10 h-10 text-white" />
          </div>
          <div className="space-y-2">
            <h3 className="text-3xl font-black italic uppercase tracking-tight text-foreground group-hover:text-primary transition-colors">
              {name}
            </h3>
            <div className="flex items-center gap-4">
              <span className="text-[10px] font-black tracking-[0.3em] text-primary uppercase">
                {status.replace(/_/g, " ")}
              </span>
              <div className="w-1 h-1 rounded-full bg-white/10" />
              <span className="text-[10px] font-black tracking-[0.2em] text-muted-foreground uppercase">
                {memberCount}/{maxTeams} members
              </span>
            </div>
          </div>
        </div>
        <div className="w-16 h-16 rounded-[1.5rem] bg-white/5 border border-white/10 flex items-center justify-center group-hover:bg-primary/20 group-hover:border-primary/40 transition-all duration-500">
          <ArrowRight className="w-6 h-6 text-muted-foreground/20 group-hover:text-primary transition-all" />
        </div>
      </CardContent>
    </Card>
  </button>
);

export default function Rosters() {
  const { data: leagueRows = [], isLoading, isError } = useLeagues();
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | null>(null);
  const selectedLeague = useMemo(
    () => leagueRows.find((league) => league.id === selectedLeagueId) ?? leagueRows[0] ?? null,
    [leagueRows, selectedLeagueId]
  );
  const {
    data: teamsPayload,
    isLoading: teamsLoading,
    isError: teamsError,
    error: teamsErrorDetail,
  } = useLeagueTeams(selectedLeague?.id);

  useEffect(() => {
    if (leagueRows.length === 0) {
      setSelectedLeagueId(null);
      return;
    }

    setSelectedLeagueId((current) => {
      if (current && leagueRows.some((league) => league.id === current)) {
        return current;
      }
      return leagueRows[0].id;
    });
  }, [leagueRows]);

  return (
    <div className="max-w-5xl mx-auto space-y-12 animate-in fade-in duration-1000 py-12">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="h-[2px] w-12 bg-gradient-to-r from-primary to-blue-400" />
          <span className="text-[10px] font-black tracking-[0.5em] text-primary uppercase">
            Supported League Flow
          </span>
        </div>
        <h1 className="text-7xl font-black italic tracking-tighter text-foreground uppercase bg-gradient-to-br from-white via-white to-primary/40 bg-clip-text text-transparent">
          Rosters
        </h1>
        <p className="text-muted-foreground text-xl font-medium max-w-2xl leading-relaxed">
          Browse live league teams and roster entries from backend contracts. Synthetic roster fillers have been removed.
        </p>
      </div>

      {isLoading ? (
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] p-20 text-center space-y-4">
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
            Loading leagues...
          </p>
        </Card>
      ) : isError ? (
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] p-20 text-center space-y-4">
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-red-300">
            Unable to load league roster entry points right now.
          </p>
        </Card>
      ) : leagueRows.length === 0 ? (
        <Card className="bg-card/40 backdrop-blur-md border border-white/5 border-dashed rounded-[3rem] p-20 text-center space-y-8">
          <div className="w-24 h-24 rounded-[2rem] bg-white/5 border border-white/10 flex items-center justify-center text-muted-foreground mx-auto">
            <ClipboardList className="w-12 h-12" />
          </div>
          <div className="space-y-4">
            <h2 className="text-3xl font-black italic uppercase text-foreground">No leagues joined yet</h2>
            <p className="text-muted-foreground max-w-sm mx-auto uppercase tracking-widest text-[10px] font-bold leading-loose">
              Create or join a league first, then open the league hub to access supported roster information.
            </p>
          </div>
          <Link to="/leagues" className="block">
            <span className="inline-flex h-14 items-center rounded-2xl bg-primary px-12 text-[10px] font-black uppercase tracking-[0.2em] text-primary-foreground shadow-[0_10px_30px_rgba(var(--primary),0.2)]">
              Browse Leagues
            </span>
          </Link>
        </Card>
      ) : (
        <>
          <div className="space-y-6">
            {leagueRows.map((league) => (
              <LeagueSelectorCard
                key={league.id}
                id={league.id}
                name={league.name}
                memberCount={league.members.length}
                maxTeams={league.max_teams}
                status={league.status}
                isActive={selectedLeague?.id === league.id}
                onSelect={setSelectedLeagueId}
              />
            ))}
          </div>

          {selectedLeague && (
            <Card className="bg-card/40 backdrop-blur-md border border-white/5 rounded-[3rem] overflow-hidden">
              <CardContent className="p-10 space-y-6">
                <div className="flex flex-wrap items-start justify-between gap-6">
                  <div className="space-y-2">
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">
                      Active League
                    </p>
                    <h2 className="text-4xl font-black italic uppercase tracking-tight text-foreground">
                      {selectedLeague.name}
                    </h2>
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                      {selectedLeague.members.length}/{selectedLeague.max_teams} managers joined
                    </p>
                  </div>
                  <Button
                    asChild
                    type="button"
                    className="h-12 rounded-2xl bg-primary px-6 text-[10px] font-black uppercase tracking-[0.2em] text-primary-foreground"
                  >
                    <Link to={`/league/${selectedLeague.id}`}>
                      Open League Hub
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>

                {teamsLoading ? (
                  <div className="rounded-[2rem] border border-white/10 bg-white/[0.03] px-6 py-12 text-center">
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                      Loading teams...
                    </p>
                  </div>
                ) : teamsError ? (
                  <div className="rounded-[2rem] border border-red-400/20 bg-red-500/5 px-6 py-12 text-center space-y-3">
                    <ShieldAlert className="mx-auto h-8 w-8 text-red-300" />
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-red-300">
                      {formatApiError(teamsErrorDetail, "Unable to load team rosters for this league.")}
                    </p>
                  </div>
                ) : (teamsPayload?.data.length ?? 0) === 0 ? (
                  <div className="rounded-[2rem] border border-dashed border-white/10 bg-white/[0.03] px-6 py-12 text-center space-y-4">
                    <Users className="mx-auto h-10 w-10 text-muted-foreground/40" />
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                      No teams created in this league yet
                    </p>
                    <p className="text-xs font-bold uppercase tracking-[0.15em] text-muted-foreground/50">
                      Team assignment and full owned-team hydration will land with the canonical league workspace contract.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {teamsPayload?.data.map((team) => (
                      <TeamRosterCard key={team.id} team={team} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
