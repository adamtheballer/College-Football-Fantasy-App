import { useMemo, useState, type ComponentType } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Calendar,
  ChevronRight,
  ClipboardList,
  Globe2,
  LineChart,
  ListOrdered,
  Lock,
  Settings2,
  ShieldCheck,
  Trophy,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import {
  useLeagueDetail,
  useLeagueMatchupTab,
  useLeagueRosterTab,
  useLeagueSettingsTab,
  useLeagueWaiverTab,
} from "@/hooks/use-leagues";
import { createBlankRosterRows, isPlaceholderRosterPlayer } from "@/lib/rosterDisplay";
import { cn } from "@/lib/utils";
import type {
  LeagueMatchupTabResponse,
  LeagueMatchupTeam,
  LeagueRosterPlayer,
  LeagueRosterTabResponse,
  LeagueSettingsTabResponse,
  LeagueWaiverTabResponse,
} from "@/types/league";

type LeagueTab = "roster" | "matchup" | "waivers" | "settings";

const tabs: Array<{ id: LeagueTab; label: string; icon: ComponentType<{ className?: string }> }> = [
  { id: "roster", label: "Roster", icon: ClipboardList },
  { id: "matchup", label: "Matchup", icon: Trophy },
  { id: "waivers", label: "Waivers", icon: ShieldCheck },
  { id: "settings", label: "Settings", icon: Settings2 },
];

const slotOrder = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];
const POST_DRAFT_LEAGUE_STATUSES = new Set(["post_draft", "active", "playoffs", "completed", "archived"]);
const POST_DRAFT_DRAFT_STATUSES = new Set(["completed", "complete"]);

const formatNumber = (value: number | null | undefined, digits = 1) =>
  Number.isFinite(value) ? Number(value).toFixed(digits) : "0.0";

const formatDate = (value?: string | null) =>
  value ? new Date(value).toLocaleString() : "Draft not scheduled";

const slotRank = (slot: string) => {
  const index = slotOrder.indexOf(slot.toUpperCase());
  return index === -1 ? slotOrder.length : index;
};

const normalizeStatus = (value: unknown) => String(value ?? "").trim().toLowerCase();

const isPostDraftState = (leagueStatus?: string | null, draftStatus?: string | null) =>
  normalizeStatus(draftStatus)
    ? POST_DRAFT_DRAFT_STATUSES.has(normalizeStatus(draftStatus))
    : POST_DRAFT_LEAGUE_STATUSES.has(normalizeStatus(leagueStatus));

function SummaryCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
}) {
  return (
    <Card className="rounded-[1.75rem] border-white/10 bg-[#101928]/85 shadow-[0_20px_80px_rgba(59,130,246,0.08)]">
      <CardContent className="flex items-center justify-between gap-4 p-5">
        <div className="space-y-1">
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">
            {label}
          </p>
          <p className="text-xl font-black italic text-slate-50">{value}</p>
        </div>
        <div className="rounded-2xl border border-sky-300/20 bg-sky-400/10 p-3">
          <Icon className="h-5 w-5 text-sky-300" />
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/10 bg-black/15 p-6">
      <p className="text-sm font-black uppercase tracking-[0.14em] text-slate-100">
        {title}
      </p>
      <p className="mt-2 text-sm leading-6 text-slate-400">{detail}</p>
    </div>
  );
}

function RosterTable({
  players,
  emptyDetail,
  forceBlank = false,
}: {
  players: LeagueRosterPlayer[];
  emptyDetail: string;
  forceBlank?: boolean;
}) {
  const sortedPlayers = useMemo(
    () =>
      [...players].sort((left, right) => {
        const slotDelta = slotRank(left.roster_slot) - slotRank(right.roster_slot);
        if (slotDelta !== 0) return slotDelta;
        if (forceBlank || isPlaceholderRosterPlayer(left) || isPlaceholderRosterPlayer(right)) return 0;
        return left.player_name.localeCompare(right.player_name);
      }),
    [forceBlank, players]
  );

  if (sortedPlayers.length === 0) {
    return <EmptyState title="No roster players yet" detail={emptyDetail} />;
  }

  return (
    <div className="overflow-hidden rounded-[1.5rem] border border-white/10">
      <div className="grid grid-cols-[1.2fr_0.7fr_0.6fr_0.7fr_0.8fr_0.7fr] gap-3 border-b border-white/10 bg-white/[0.04] px-5 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400 max-lg:hidden">
        <span>Player</span>
        <span>School</span>
        <span>Pos</span>
        <span>Slot</span>
        <span>Opponent</span>
        <span className="text-right">Proj</span>
      </div>
      <div className="divide-y divide-white/10">
        {sortedPlayers.map((player) => {
          const isPlaceholder = forceBlank || isPlaceholderRosterPlayer(player);
          const displayName = isPlaceholder ? "N/A" : player.player_name;
          const displaySchool = isPlaceholder ? "N/A" : player.school || "N/A";
          const displayPosition = player.position || player.player_position || player.roster_slot || "N/A";
          const displayOpponent = isPlaceholder ? "N/A" : player.opponent || "N/A";
          const displayProjection = isPlaceholder ? "-" : formatNumber(player.weekly_projected_fantasy_points);

          return (
            <div
              key={`${player.id}-${player.fantasy_team_id}-${player.player_id ?? "empty"}-${player.roster_slot}`}
              className="grid grid-cols-1 gap-3 px-5 py-4 text-sm text-slate-200 lg:grid-cols-[1.2fr_0.7fr_0.6fr_0.7fr_0.8fr_0.7fr] lg:items-center"
            >
              <div>
                <p className="font-black text-slate-50">{displayName}</p>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500 lg:hidden">
                  {displaySchool} · {displayPosition} · {player.roster_slot || "BENCH"}
                </p>
              </div>
              <span className="hidden text-slate-400 lg:inline">{displaySchool}</span>
              <span className="hidden lg:inline">
                <span className="rounded-full border border-sky-300/25 bg-sky-400/10 px-3 py-1 text-[10px] font-black text-sky-200">
                  {displayPosition}
                </span>
              </span>
              <span className="hidden text-slate-300 lg:inline">{player.roster_slot || "BENCH"}</span>
              <span className="hidden text-slate-400 lg:inline">{displayOpponent}</span>
              <span className="font-black text-sky-200 lg:text-right">
                {displayProjection}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProbabilityMeter({
  userProbability,
  opponentProbability,
}: {
  userProbability: number;
  opponentProbability: number;
}) {
  const safeUserProbability = Math.max(0, Math.min(100, userProbability));
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
        <span>Win Probability</span>
        <span>
          {formatNumber(safeUserProbability)}% / {formatNumber(opponentProbability)}%
        </span>
      </div>
      <div className="h-4 overflow-hidden rounded-full border border-white/10 bg-slate-950">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 shadow-[0_0_28px_rgba(56,189,248,0.45)]"
          style={{ width: `${safeUserProbability}%` }}
        />
      </div>
    </div>
  );
}

function MatchupTeamPanel({
  label,
  team,
}: {
  label: string;
  team: LeagueMatchupTeam | null;
}) {
  if (!team) {
    return (
      <div className="rounded-[1.75rem] border border-white/10 bg-black/15 p-6">
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-500">
          {label}
        </p>
        <p className="mt-3 text-xl font-black text-slate-100">Opponent pending</p>
      </div>
    );
  }

  return (
    <div className="rounded-[1.75rem] border border-white/10 bg-[#0c1524]/80 p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-sky-300">
            {label}
          </p>
          <p className="mt-2 text-2xl font-black italic text-slate-50">
            {team.fantasy_team_name}
          </p>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Record {team.record}
          </p>
        </div>
        <div className="rounded-2xl border border-sky-300/25 bg-sky-400/10 px-4 py-3 text-right">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            Projected
          </p>
          <p className="text-2xl font-black text-sky-200">
            {formatNumber(team.projected_total)}
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {team.roster.length === 0 ? (
          <p className="text-sm text-slate-400">No roster projections available.</p>
        ) : (
          team.roster.slice(0, 12).map((player) => (
            <div
              key={`${team.fantasy_team_id}-${player.player_id}`}
              className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-black text-slate-100">
                  {player.player_name}
                </p>
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                  {player.roster_slot} · {player.position} · {player.school || "-"}
                </p>
              </div>
              <p className="shrink-0 text-sm font-black text-sky-200">
                {formatNumber(player.weekly_projected_fantasy_points)}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function RosterTab({
  data,
  isLoading,
  forceBlank = false,
}: {
  data?: LeagueRosterTabResponse;
  isLoading: boolean;
  forceBlank?: boolean;
}) {
  const rosterRows = useMemo(
    () =>
      forceBlank
        ? createBlankRosterRows({
            players: data?.data,
            rosterSlotLimits: data?.roster_slot_limits,
            fantasyTeamId: data?.fantasy_team_id ?? data?.owned_team?.id ?? null,
            fantasyTeamName: data?.fantasy_team_name ?? data?.owned_team?.name ?? "Your Team",
            leagueId: data?.league_id ?? null,
          })
        : data?.data ?? [],
    [data, forceBlank]
  );

  return (
    <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center justify-between gap-4">
          <span className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
            Your Roster
          </span>
          <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
            Week {data?.week ?? 1}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        {isLoading ? (
          <EmptyState title="Loading roster" detail="Fetching your league-scoped roster." />
        ) : (
          <RosterTable
            players={rosterRows}
            emptyDetail="Your team roster will populate after the league draft is completed."
            forceBlank={forceBlank}
          />
        )}
      </CardContent>
    </Card>
  );
}

function MatchupTab({
  data,
  isLoading,
}: {
  data?: LeagueMatchupTabResponse;
  isLoading: boolean;
}) {
  const userTeam = data?.user_team ?? null;
  const opponentTeam = data?.opponent_team ?? null;
  const hasScheduledMatchup = Boolean(data?.matchup_id && userTeam && opponentTeam);

  if (isLoading) {
    return (
      <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
        <CardContent className="p-6">
          <EmptyState title="Loading matchup" detail="Fetching your current week matchup." />
        </CardContent>
      </Card>
    );
  }

  if (!hasScheduledMatchup) {
    return (
      <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
        <CardContent className="p-6">
          <EmptyState
            title="No matchup scheduled"
            detail={
              data?.message ??
              "No real matchup exists for this league and week yet. Once the schedule is generated, matchup projections will appear here."
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
        <CardContent className="p-6">
          <div className="grid gap-5 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-500">
                Your Team
              </p>
              <p className="mt-2 text-3xl font-black italic text-slate-50">
                {userTeam.fantasy_team_name}
              </p>
              <p className="text-sm font-bold text-slate-400">
                {userTeam.record}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-sky-300/20 bg-sky-400/10 px-8 py-5 text-center">
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-sky-200">
                Week {data?.week ?? 1}
              </p>
              <p className="mt-1 text-2xl font-black text-slate-50">
                {formatNumber(userTeam.projected_total)} - {formatNumber(opponentTeam.projected_total)}
              </p>
            </div>
            <div className="text-left lg:text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-500">
                Opponent
              </p>
              <p className="mt-2 text-3xl font-black italic text-slate-50">
                {opponentTeam.fantasy_team_name}
              </p>
              <p className="text-sm font-bold text-slate-400">
                {opponentTeam.record}
              </p>
            </div>
          </div>
          <div className="mt-6">
            <ProbabilityMeter
              userProbability={userTeam.win_probability}
              opponentProbability={opponentTeam.win_probability}
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <MatchupTeamPanel label="Your Lineup" team={userTeam} />
        <MatchupTeamPanel label="Opponent Lineup" team={opponentTeam} />
      </div>
    </div>
  );
}

function WaiverTab({
  data,
  isLoading,
}: {
  data?: LeagueWaiverTabResponse;
  isLoading: boolean;
}) {
  return (
    <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
      <CardHeader className="border-b border-white/10">
        <CardTitle className="flex items-center justify-between gap-4">
          <span className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
            Waiver Claims
          </span>
          <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
            {data?.total_available ?? 0} available
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 p-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div>
          <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Available In This League
          </p>
          {isLoading ? (
            <EmptyState title="Loading available players" detail="Checking current league ownership only." />
          ) : (data?.available_players ?? []).length === 0 ? (
            <EmptyState title="No available players" detail="Every visible player is already owned in this league." />
          ) : (
            <div className="max-h-[520px] overflow-y-auto rounded-[1.5rem] border border-white/10">
              {data?.available_players.map((player) => (
                <div
                  key={player.id}
                  className="grid grid-cols-[1fr_auto] gap-4 border-b border-white/10 px-5 py-4 last:border-b-0"
                >
                  <div>
                    <p className="font-black text-slate-50">{player.name}</p>
                    <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                      {player.position || "-"} · {player.school || "-"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-black text-sky-200">
                      {formatNumber(player.weekly_projected_fantasy_points)}
                    </p>
                    <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                      Proj
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
            Waiver Claims
          </p>
          {(data?.claims ?? []).length === 0 ? (
            <EmptyState
              title="No claims yet"
              detail="Submit add/drop claims from the league Waivers page. Pending claims can be cancelled until processing."
            />
          ) : (
            <div className="space-y-3">
              {data?.claims.map((claim) => (
                <div key={claim.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-sm font-black text-slate-50">{claim.add_player_name}</p>
                  <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                    {claim.status}
                    {claim.drop_player_name ? ` · Drop ${claim.drop_player_name}` : ""}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SettingsTab({
  data,
  isLoading,
}: {
  data?: LeagueSettingsTabResponse;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
        <CardContent className="p-6">
          <EmptyState title="Loading settings" detail="Fetching league rules and schedule." />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
        <CardHeader className="border-b border-white/10">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
            League Rules
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6 p-6">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              Scoring
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              {Object.entries(data?.scoring_settings ?? {}).map(([key, value]) => (
                <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                    {key.replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 text-lg font-black text-slate-50">{String(value)}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              Roster Settings
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              {Object.entries(data?.roster_settings ?? {}).map(([key, value]) => (
                <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                    {key}
                  </p>
                  <p className="mt-1 text-lg font-black text-slate-50">{value}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              Claims Policy
            </p>
            <p className="mt-2 text-sm font-black uppercase tracking-[0.12em] text-slate-100">
              Active policy · {String(data?.waiver_rules.waiver_type ?? "policy pending")}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              Members
            </p>
            <div className="mt-3 space-y-2">
              {(data?.members ?? []).length === 0 ? (
                <p className="text-sm text-slate-400">No members loaded.</p>
              ) : (
                data?.members.map((member) => (
                  <div
                    key={member.id}
                    className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
                  >
                    <span className="text-sm font-black text-slate-100">User {member.user_id}</span>
                    <span className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-200">
                      {member.role}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
          {data?.commissioner_controls?.length ? (
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
                Commissioner Controls
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {data.commissioner_controls.map((control) => (
                  <span
                    key={control}
                    className="rounded-full border border-sky-300/25 bg-sky-400/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100"
                  >
                    {control.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
              Standings
            </CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-white/10 p-0">
            {(data?.standings ?? []).length === 0 ? (
              <div className="p-6 text-sm text-slate-400">No standings are available yet.</div>
            ) : (
              data?.standings.map((row) => (
                <div key={String(row.team_id)} className="flex items-center justify-between px-6 py-4">
                  <span className="font-black text-slate-100">{String(row.team_name)}</span>
                  <span className="text-sm font-bold text-slate-400">{String(row.record)}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
              Schedule
            </CardTitle>
          </CardHeader>
          <CardContent className="max-h-[420px] divide-y divide-white/10 overflow-y-auto p-0">
            {(data?.schedule ?? []).length === 0 ? (
              <div className="p-6 text-sm text-slate-400">
                Schedule generates after a completed draft with an even number of teams.
              </div>
            ) : (
              data?.schedule.map((row) => (
                <div key={row.matchup_id} className="px-6 py-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                    Week {row.week}
                  </p>
                  <div className="mt-1 flex items-center justify-between gap-4 text-sm font-bold text-slate-100">
                    <span>{row.home_team_name}</span>
                    <span className="text-slate-500">vs</span>
                    <span>{row.away_team_name}</span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[2rem] border-white/10 bg-[#0d1727]/90 xl:col-span-2">
        <CardHeader className="border-b border-white/10">
          <CardTitle className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
            Draft Results And All Rosters
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 p-6 xl:grid-cols-2">
          <div>
            <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              Draft Results
            </p>
            <div className="max-h-[360px] overflow-y-auto rounded-[1.5rem] border border-white/10">
              {(data?.draft_results ?? []).length === 0 ? (
                <div className="p-5 text-sm text-slate-400">No draft results yet.</div>
              ) : (
                data?.draft_results.map((pick) => (
                  <div
                    key={String(pick.draft_pick_id)}
                    className="flex items-center justify-between border-b border-white/10 px-5 py-3 last:border-b-0"
                  >
                    <span className="text-sm font-black text-slate-100">
                      Pick {String(pick.overall_pick)}
                    </span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                      Player {String(pick.player_id)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
          <div>
            <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              All Rosters
            </p>
            <RosterTable
              players={data?.rosters ?? []}
              emptyDetail="League rosters will appear after draft import completes."
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LeagueDetail() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<LeagueTab>("roster");
  const parsedLeagueId = leagueId && /^\d+$/.test(leagueId) ? Number(leagueId) : undefined;
  const { data: league, isLoading, error } = useLeagueDetail(parsedLeagueId);
  const rosterQuery = useLeagueRosterTab(parsedLeagueId, undefined, activeTab === "roster");
  const matchupQuery = useLeagueMatchupTab(parsedLeagueId, undefined, activeTab === "matchup");
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, activeTab === "settings");
  const waiverQuery = useLeagueWaiverTab(parsedLeagueId, 50, 0, activeTab === "waivers");

  if (!parsedLeagueId) {
    return (
      <div className="mx-auto max-w-4xl py-16">
        <Card className="rounded-[2rem] border-border/60 bg-card/40">
          <CardContent className="p-12 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              Invalid league ID.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl py-16">
        <Card className="rounded-[2rem] border-border/60 bg-card/40">
          <CardContent className="p-12 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
              Loading league...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!league || error) {
    return (
      <div className="mx-auto max-w-4xl py-16">
        <Card className="rounded-[2rem] border-border/60 bg-card/40">
          <CardContent className="space-y-4 p-12 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              Unable to load league metadata.
            </p>
            <Button
              variant="outline"
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate("/leagues")}
            >
              Back to Leagues
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const membership = league.members.find((member) => member.user_id === user?.id) || null;
  const isCommissioner = league.commissioner_user_id === user?.id;
  const draftDate = formatDate(league.draft?.draft_datetime_utc);
  const forceBlankRoster = !isPostDraftState(league.status, league.draft?.status);

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-16 pt-10 animate-in fade-in duration-700">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-3">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-sky-300">
              Live League Hub
            </p>
            <h1 className="text-5xl font-black italic uppercase tracking-tight text-slate-50 md:text-6xl">
              {league.name}
            </h1>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-slate-400">
              Season {league.season_year} • {league.status.replace(/_/g, " ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="rounded-2xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate(`/league/${league.id}/lobby`)}
            >
              Draft Lobby
              <ChevronRight className="ml-2 h-3 w-3" />
            </Button>
            <Button
              variant="outline"
              className="rounded-2xl border-white/10 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate("/leagues")}
            >
              Back to Leagues
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Members" value={`${league.members.length}/${league.max_teams}`} icon={Users} />
        <SummaryCard label="Draft" value={draftDate} icon={Calendar} />
        <SummaryCard
          label="Visibility"
          value={league.is_private ? "Private" : "Public"}
          icon={league.is_private ? Lock : Globe2}
        />
        <SummaryCard
          label="Your Role"
          value={membership ? membership.role : isCommissioner ? "Commissioner" : "Member pending"}
          icon={LineChart}
        />
      </div>

      <Card className="overflow-hidden rounded-[2rem] border-white/10 bg-[#0a1322]/95 shadow-[0_24px_90px_rgba(37,99,235,0.12)]">
        <CardContent className="p-4">
          <div
            className="w-full gap-3"
            style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}
          >
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <div key={tab.id} className="min-w-0">
                  <button
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    style={{ display: "flex", width: "100%", minWidth: 0 }}
                    className={cn(
                      "h-full items-center justify-center gap-3 rounded-2xl border px-4 py-4 text-[11px] font-black uppercase tracking-[0.18em] transition",
                      active
                        ? "border-sky-300/45 bg-sky-400/15 text-sky-100 shadow-[0_0_30px_rgba(56,189,248,0.14)]"
                        : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-100"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{tab.label}</span>
                  </button>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {activeTab === "roster" && (
        <RosterTab data={rosterQuery.data} isLoading={rosterQuery.isLoading} forceBlank={forceBlankRoster} />
      )}
      {activeTab === "matchup" && (
        <MatchupTab data={matchupQuery.data} isLoading={matchupQuery.isLoading} />
      )}
      {activeTab === "waivers" && (
        <WaiverTab data={waiverQuery.data} isLoading={waiverQuery.isLoading} />
      )}
      {activeTab === "settings" && (
        <SettingsTab data={settingsQuery.data} isLoading={settingsQuery.isLoading} />
      )}
    </div>
  );
}
