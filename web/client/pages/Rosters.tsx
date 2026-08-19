import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ManagerAvatar } from "@/components/profile/ManagerAvatar";
import { ClipboardList, Trophy, ArrowRight, Users, ShieldAlert } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useActiveLeagueId } from "@/hooks/use-active-league";
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
      <div className="border-t border-dashed border-cfb-border-subtle px-4 py-8 text-center">
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
          No roster entries yet
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface">
      <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_4.5rem] gap-3 border-b border-cfb-border-subtle bg-cfb-surface-raised px-3 py-2.5 text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted sm:grid-cols-[5.5rem_minmax(0,1fr)_8rem_7rem] sm:px-4">
        <span>Slot</span>
        <span>Player</span>
        <span className="text-right sm:text-left">Status</span>
        <span className="hidden sm:block">School</span>
      </div>
      {sortedEntries.map((entry) => (
        <div
          key={entry.id}
          className="grid min-h-14 grid-cols-[4.5rem_minmax(0,1fr)_4.5rem] items-center gap-3 border-b border-cfb-border-subtle/70 px-3 py-2.5 last:border-b-0 hover:bg-cfb-surface-hover sm:grid-cols-[5.5rem_minmax(0,1fr)_8rem_7rem] sm:px-4"
        >
          <span className="inline-flex w-fit rounded-md border border-cfb-border-subtle bg-cfb-surface-raised px-2 py-1 text-[9px] font-black uppercase tracking-[0.12em] text-cfb-brand">
            {entry.slot}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-black tracking-tight text-cfb-text-primary">
              {entry.player.name}
            </p>
            <p className="text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
              {entry.player.position}
            </p>
          </div>
          <span className="truncate text-right text-[9px] font-black uppercase tracking-[0.1em] text-cfb-text-secondary sm:text-left">
            {entry.status}
          </span>
          <span className="hidden truncate text-[10px] font-bold text-cfb-text-secondary sm:block">{entry.player.school}</span>
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
    <Card className="overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface">
      <CardContent className="space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <ManagerAvatar avatarUrl={team.owner_avatar_url} managerName={team.owner_name} size="md" />
              <div>
                <h3 className="text-base font-black tracking-tight text-cfb-text-primary sm:text-lg">
                  {team.name}
                </h3>
                <p className="text-[9px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
                  Owner {team.owner_name || "Unassigned"}
                </p>
              </div>
            </div>
          </div>
          <Button
            asChild
            type="button"
            variant="outline"
            className="h-9 rounded-md border-cfb-border-subtle bg-cfb-surface-raised px-3 text-[9px] font-black uppercase tracking-[0.12em] text-cfb-text-secondary hover:bg-cfb-surface-hover hover:text-cfb-text-primary"
          >
            <Link to={`/league/${team.league_id}`}>
              League Hub
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="rounded-lg border border-dashed border-cfb-border-subtle bg-cfb-surface-raised px-4 py-8 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
              Loading roster...
            </p>
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-red-400/20 bg-red-500/5 px-4 py-8 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
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
  <button
    type="button"
    onClick={() => onSelect(id)}
    aria-pressed={isActive}
    className="w-full text-left"
  >
    <Card
      className={`overflow-hidden rounded-lg border transition-colors hover:bg-cfb-surface-hover ${
        isActive
          ? "border-cfb-brand/70 bg-cfb-brand/[0.08]"
          : "border-cfb-border-subtle bg-cfb-surface"
      }`}
    >
      <CardContent className="relative z-10 flex items-center justify-between gap-3 p-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-cfb-border-subtle bg-cfb-surface-raised text-cfb-brand">
            <Trophy className="h-4 w-4" />
          </div>
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-sm font-black tracking-tight text-cfb-text-primary sm:text-base">
              {name}
              </h3>
              <span
                className={`rounded-md border px-2 py-1 text-[8px] font-black uppercase tracking-[0.1em] ${
                  isActive
                    ? "border-cfb-brand/40 bg-cfb-brand/15 text-cfb-brand"
                    : "border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-muted"
                }`}
              >
                {isActive ? "Selected" : "Select Roster"}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.12em]">
              <span className="text-cfb-brand">
                {status.replace(/_/g, " ")}
              </span>
              <span className="h-1 w-1 rounded-full bg-cfb-border-strong" />
              <span className="text-cfb-text-muted">
                {memberCount}/{maxTeams} members
              </span>
            </div>
          </div>
        </div>
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${
            isActive
              ? "border-cfb-brand/40 bg-cfb-brand/15"
              : "border-cfb-border-subtle bg-cfb-surface-raised"
          }`}
        >
          <ArrowRight
            className={`h-4 w-4 ${
              isActive ? "text-cfb-brand" : "text-cfb-text-muted"
            }`}
          />
        </div>
      </CardContent>
    </Card>
  </button>
);

export default function Rosters() {
  const { data: leagueRows = [], isLoading, isError } = useLeagues();
  const { activeLeagueId, setActiveLeagueId } = useActiveLeagueId();
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | null>(null);
  const activeLeagueRef = useRef<HTMLDivElement | null>(null);
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
      if (activeLeagueId && leagueRows.some((league) => league.id === activeLeagueId)) {
        return activeLeagueId;
      }
      return leagueRows[0].id;
    });
  }, [activeLeagueId, leagueRows]);

  useEffect(() => {
    if (!selectedLeagueId) return;
    setActiveLeagueId(selectedLeagueId);
  }, [selectedLeagueId, setActiveLeagueId]);

  useEffect(() => {
    if (!selectedLeagueId || !activeLeagueRef.current) {
      return;
    }

    activeLeagueRef.current.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [selectedLeagueId]);

  return (
    <div className="mx-auto max-w-[1320px] space-y-5 px-4 py-5 pb-24 sm:px-6 sm:py-8">
      <div className="space-y-1.5">
        <p className="cfb-micro-label text-cfb-brand">League rosters</p>
        <h1 className="cfb-display-title text-3xl italic sm:text-4xl">Rosters</h1>
        <p className="max-w-2xl text-sm font-medium leading-6 text-cfb-text-secondary">
          Select a league, then scan every roster in a compact board view.
        </p>
      </div>

      {isLoading ? (
        <Card className="rounded-lg border border-cfb-border-subtle bg-cfb-surface p-8 text-center">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
            Loading leagues...
          </p>
        </Card>
      ) : isError ? (
        <Card className="rounded-lg border border-red-400/20 bg-red-500/5 p-8 text-center">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
            Unable to load league roster entry points right now.
          </p>
        </Card>
      ) : leagueRows.length === 0 ? (
        <Card className="rounded-lg border border-dashed border-cfb-border-subtle bg-cfb-surface p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-muted">
            <ClipboardList className="h-5 w-5" />
          </div>
          <div className="mt-4 space-y-2">
            <h2 className="text-lg font-black text-cfb-text-primary">No leagues joined yet</h2>
            <p className="mx-auto max-w-sm text-sm font-medium leading-6 text-cfb-text-secondary">
              Create or join a league first, then open the league hub to access supported roster information.
            </p>
          </div>
          <Link to="/leagues" className="mt-5 inline-flex">
            <span className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-[10px] font-black uppercase tracking-[0.14em] text-primary-foreground">
              Browse Leagues
            </span>
          </Link>
        </Card>
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface">
            <div className="border-b border-cfb-border-subtle bg-cfb-surface-raised px-4 py-3">
              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Select league</p>
            </div>
            <div className="divide-y divide-cfb-border-subtle">
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
          </div>

          {selectedLeague && (
            <div ref={activeLeagueRef}>
              <Card className="overflow-hidden rounded-lg border border-cfb-border-subtle bg-cfb-surface">
              <CardContent className="space-y-4 p-4 sm:p-5">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-cfb-border-subtle pb-4">
                  <div className="space-y-1">
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">
                      Active League
                    </p>
                    <h2 className="text-xl font-black tracking-tight text-cfb-text-primary">
                      {selectedLeague.name}
                    </h2>
                    <p className="text-[9px] font-black uppercase tracking-[0.12em] text-cfb-text-muted">
                      {selectedLeague.members.length}/{selectedLeague.max_teams} managers joined
                    </p>
                  </div>
                  <Button
                    asChild
                    type="button"
                    className="h-9 rounded-md bg-primary px-3 text-[9px] font-black uppercase tracking-[0.12em] text-primary-foreground"
                  >
                    <Link to={`/league/${selectedLeague.id}`}>
                      Open League Hub
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>

                {teamsLoading ? (
                  <div className="rounded-lg border border-dashed border-cfb-border-subtle bg-cfb-surface-raised px-4 py-8 text-center">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
                      Loading teams...
                    </p>
                  </div>
                ) : teamsError ? (
                  <div className="rounded-lg border border-red-400/20 bg-red-500/5 px-4 py-8 text-center">
                    <ShieldAlert className="mx-auto h-5 w-5 text-red-300" />
                    <p className="mt-3 text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                      {formatApiError(teamsErrorDetail, "Unable to load team rosters for this league.")}
                    </p>
                  </div>
                ) : (teamsPayload?.data.length ?? 0) === 0 ? (
                  <div className="rounded-lg border border-dashed border-cfb-border-subtle bg-cfb-surface-raised px-4 py-8 text-center">
                    <Users className="mx-auto h-5 w-5 text-cfb-text-muted" />
                    <p className="mt-3 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-muted">
                      No teams created in this league yet
                    </p>
                    <p className="mx-auto mt-2 max-w-xl text-sm font-medium leading-6 text-cfb-text-secondary">
                      Team assignment and full owned-team hydration will land with the canonical league workspace contract.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {teamsPayload?.data.map((team) => (
                      <TeamRosterCard key={team.id} team={team} />
                    ))}
                  </div>
                )}
              </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
