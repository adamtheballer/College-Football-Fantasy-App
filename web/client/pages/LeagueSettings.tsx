import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRightLeft,
  CalendarDays,
  ClipboardList,
  Copy,
  History,
  Link2,
  ListOrdered,
  Medal,
  Settings2,
  ShieldCheck,
  Trophy,
  Users,
} from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { PostseasonBracketPanel } from "@/components/league/PostseasonBracketPanel";
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { ErrorState } from "@/components/states";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useLeagueDetail, useLeaguePostseasonBracket, useLeagueSettingsTab } from "@/hooks/use-leagues";
import { isLeaguePostDraft } from "@/lib/leagueLifecycle";
import { getLeagueScheduleWeeks } from "@/lib/leagueSchedule";
import { tradeOfferPath } from "@/lib/trade-links";
import type { LeagueRosterPlayer, LeagueSettingsTabResponse } from "@/types/league";

type SettingsPanel = "standings" | "playoffs" | "scoring" | "schedule" | "rosters" | "trades" | "draft";

const panels: Array<{ id: SettingsPanel; label: string; icon: typeof Trophy }> = [
  { id: "standings", label: "Standings", icon: Trophy },
  { id: "playoffs", label: "Playoffs", icon: Trophy },
  { id: "scoring", label: "Point System", icon: Settings2 },
  { id: "schedule", label: "Schedules", icon: CalendarDays },
  { id: "rosters", label: "Manager Rosters", icon: Users },
  { id: "trades", label: "Trade History", icon: History },
  { id: "draft", label: "Draft Results", icon: ClipboardList },
];

const scoringLabels: Record<string, string> = {
  ppr: "Reception",
  pass_td: "Passing TD",
  pass_yds_per_pt: "Pass Yards / Point",
  rush_yds_per_pt: "Rush Yards / Point",
  rec_yds_per_pt: "Receiving Yards / Point",
  rush_td: "Rushing TD",
  rec_td: "Receiving TD",
  int: "Interception",
  fumble_lost: "Fumble Lost",
  fg: "Field Goal",
  xp: "Extra Point",
};

const slotOrder = ["QB", "RB", "WR", "TE", "FLEX", "K", "BENCH", "IR"];

const slotTone = (slot?: string | null) => {
  switch ((slot ?? "").toUpperCase()) {
    case "QB":
      return "border-blue-300/45 bg-blue-400/10 text-blue-100";
    case "RB":
      return "border-emerald-300/45 bg-emerald-400/10 text-emerald-100";
    case "WR":
      return "border-violet-300/45 bg-violet-400/10 text-violet-100";
    case "TE":
      return "border-amber-300/45 bg-amber-400/10 text-amber-100";
    case "K":
      return "border-sky-300/45 bg-sky-400/10 text-sky-100";
    case "FLEX":
      return "border-fuchsia-300/45 bg-fuchsia-400/10 text-fuchsia-100";
    case "BENCH":
      return "border-slate-300/25 bg-white/5 text-slate-200";
    case "IR":
      return "border-rose-300/40 bg-rose-400/10 text-rose-100";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
};

const formatValue = (value: unknown) => {
  if (typeof value === "boolean") return value ? "On" : "Off";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
};

const groupRostersByTeam = (rosters: LeagueRosterPlayer[]) =>
  rosters.reduce<Record<string, LeagueRosterPlayer[]>>((groups, player) => {
    const teamName = player.fantasy_team_name || `Team ${player.fantasy_team_id}`;
    groups[teamName] = groups[teamName] ?? [];
    groups[teamName].push(player);
    return groups;
  }, {});

type StandingsRow = Record<string, string | number>;

const buildStandingsRows = (data?: LeagueSettingsTabResponse): StandingsRow[] => {
  if ((data?.standings ?? []).length > 0) return data?.standings ?? [];

  return (data?.teams ?? []).map((team, index) => ({
    team_id: team.id,
    team_name: team.name,
    wins: 0,
    losses: 0,
    ties: 0,
    points_for: 0,
    points_against: 0,
    rank: index + 1,
  }));
};

const formatRecord = (row: StandingsRow) => {
  const wins = Number(row.wins ?? 0);
  const losses = Number(row.losses ?? 0);
  const ties = Number(row.ties ?? 0);

  return ties > 0 ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
};

const formatWaiverSystem = (waiverType: unknown) =>
  String(waiverType ?? "faab").trim().toLowerCase() === "faab" ? "FAAB" : "Waiver Wire Order";

export const formatDateTime = (value?: string | null) => {
  if (!value) return "Unknown time";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown time" : parsed.toLocaleString();
};

export const formatTradeAssets = (assets: Array<{ name: string; position: string | null; school: string | null }>) =>
  assets.length
    ? assets.map((asset) => [asset.name, asset.position, asset.school].filter(Boolean).join(" · "))
    : ["No players listed"];

export default function LeagueSettings() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activePanel, setActivePanel] = useState<SettingsPanel>(() => searchParams.get("section") === "playoffs" ? "playoffs" : "standings");
  const [selectedRosterTeam, setSelectedRosterTeam] = useState<string>("");
  const [selectedScheduleWeek, setSelectedScheduleWeek] = useState<number | null>(null);
  const [copiedInviteField, setCopiedInviteField] = useState<"code" | "link" | null>(null);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId);
  const postDraft = isLeaguePostDraft({ draftStatus: leagueQuery.data?.draft?.status, leagueStatus: leagueQuery.data?.status });
  const postseasonQuery = useLeaguePostseasonBracket(parsedLeagueId, activePanel === "playoffs" && postDraft);
  const data = settingsQuery.data;
  const tradeHistory = data?.trade_history ?? [];
  const rosterGroups = useMemo(() => groupRostersByTeam(data?.rosters ?? []), [data?.rosters]);
  const rosterTeamNames = useMemo(() => Object.keys(rosterGroups), [rosterGroups]);
  useEffect(() => {
    if (rosterTeamNames.length === 0) {
      if (selectedRosterTeam) setSelectedRosterTeam("");
      return;
    }

    if (!selectedRosterTeam || !rosterGroups[selectedRosterTeam]) {
      setSelectedRosterTeam(rosterTeamNames[0]);
    }
  }, [rosterGroups, rosterTeamNames, selectedRosterTeam]);
  const selectedRosterPlayers = selectedRosterTeam ? rosterGroups[selectedRosterTeam] ?? [] : [];
  const scheduleWeeks = useMemo(
    () => getLeagueScheduleWeeks(data?.schedule ?? []),
    [data?.schedule]
  );
  const regularSeasonFinalWeek = scheduleWeeks[scheduleWeeks.length - 1] ?? 0;
  useEffect(() => {
    if (scheduleWeeks.length === 0) {
      if (selectedScheduleWeek !== null) setSelectedScheduleWeek(null);
      return;
    }

    if (selectedScheduleWeek === null || !scheduleWeeks.includes(selectedScheduleWeek)) {
      setSelectedScheduleWeek(scheduleWeeks[0]);
    }
  }, [scheduleWeeks, selectedScheduleWeek]);
  const selectedScheduleRows = useMemo(
    () => (data?.schedule ?? []).filter((row) => Number(row.week) === selectedScheduleWeek),
    [data?.schedule, selectedScheduleWeek]
  );
  const scoringEntries = Object.entries(data?.scoring_settings ?? {});
  const rosterEntries = Object.entries(data?.roster_settings ?? {}).sort(
    ([first], [second]) => slotOrder.indexOf(first) - slotOrder.indexOf(second)
  );
  const standingsRows = useMemo(() => buildStandingsRows(data), [data]);
  const waiverSystem = formatWaiverSystem(data?.waiver_rules?.waiver_type);
  const waiverRuleEntries = Object.entries(data?.waiver_rules ?? {}).filter(
    ([key]) => key !== "waiver_type" && key !== "trade_review_type"
  );
  const leagueInfo = data?.league_info ?? {};
  const certifiedCalendar = data?.postseason_calendar;
  const playoffTeams = certifiedCalendar?.playoff_teams ?? leagueQuery.data?.settings.playoff_teams;
  const playoffRounds = certifiedCalendar?.max_rounds ?? (playoffTeams === 2 ? 1 : playoffTeams === 4 ? 2 : playoffTeams ? 3 : null);

  useEffect(() => {
    if (searchParams.get("section") === "playoffs" && activePanel !== "playoffs") setActivePanel("playoffs");
  }, [activePanel, searchParams]);

  const selectPanel = (panel: SettingsPanel) => {
    setActivePanel(panel);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (panel === "playoffs") next.set("section", "playoffs");
      else next.delete("section");
      return next;
    }, { replace: true });
  };

  const copyInviteValue = async (field: "code" | "link", value?: string | null) => {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedInviteField(field);
    window.setTimeout(() => setCopiedInviteField(null), 1800);
  };

  if (leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-0 py-4 sm:px-6 sm:py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-0 py-4 sm:px-6 sm:py-8">
        <ErrorState
          title="Unable to load league"
          message="The league could not be loaded. Confirm the backend is available, then try again."
          retryLabel="Try Again"
          onRetry={() => void leagueQuery.refetch()}
        />
      </main>
    );
  }

  return (
    <main className="relative mx-auto flex w-full max-w-none flex-col gap-4 px-0 py-4 sm:px-0 sm:py-8">
      <div className="space-y-3">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-cfb-brand">
          League Command Center
        </p>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-black text-cfb-text-primary sm:text-4xl">
              {data?.league_name ?? "League Settings"}
            </h1>
            <p className="mt-1.5 max-w-3xl text-sm text-cfb-text-secondary">
              League-specific standings, playoff picture, point system, schedules, manager rosters, trade history, and draft results.
            </p>
            {certifiedCalendar ? (
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
                Regular season · Weeks {certifiedCalendar.regular_season_start_week}–{certifiedCalendar.regular_season_end_week} · Playoffs · Weeks {certifiedCalendar.playoff_start_week}–{certifiedCalendar.championship_week} · {playoffTeams} teams · {playoffRounds} rounds
              </p>
            ) : (
              <p className="mt-2 text-[10px] font-black uppercase tracking-[0.14em] text-cfb-text-muted">
                Playoffs · {playoffTeams ?? "—"} teams · {playoffRounds ?? "—"} rounds · calendar locks with the certified season schedule
              </p>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 sm:min-w-[360px]">
            <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised px-3 py-2.5">
              <p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Teams</p>
              <p className="mt-1 text-xl font-black text-cfb-text-primary">
                {formatValue(leagueInfo.teams ?? data?.members?.length)}
              </p>
            </div>
            <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised px-3 py-2.5">
              <p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Schedule</p>
              <p className="mt-1 text-xl font-black text-cfb-text-primary">{data?.schedule?.length ?? 0}</p>
            </div>
            <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface-raised px-3 py-2.5">
              <p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Trades</p>
              <p className="mt-1 text-xl font-black text-cfb-text-primary">{tradeHistory.length}</p>
            </div>
          </div>
        </div>
        <LeagueTabs
          leagueId={parsedLeagueId}
          draftStatus={leagueQuery.data?.draft?.status}
          leagueStatus={leagueQuery.data?.status}
        />
      </div>

      {data?.invite ? (
        <InviteSettingsCard
          data={data}
          copiedField={copiedInviteField}
          onCopy={copyInviteValue}
        />
      ) : null}

      <section className="overflow-x-auto rounded-xl border border-cfb-border-subtle bg-cfb-surface p-1.5">
        <div className="grid min-w-[680px] grid-cols-7 gap-1" aria-label="League settings sections">
          {panels.map((panel) => {
            const Icon = panel.icon;
            const active = activePanel === panel.id;
            return (
              <button
                key={panel.id}
                type="button"
                aria-pressed={active}
                onClick={() => selectPanel(panel.id)}
                className={[
                  "flex h-10 items-center justify-center gap-1.5 rounded-lg px-2 text-center text-[9px] font-black uppercase tracking-[0.12em] transition-colors",
                  active
                    ? "bg-cfb-surface-raised text-cfb-text-primary"
                    : "text-cfb-text-muted hover:bg-cfb-surface-hover hover:text-cfb-text-primary",
                ].join(" ")}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{panel.label}</span>
              </button>
            );
          })}
        </div>
      </section>

      {activePanel === "standings" ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <PanelHeader title="Standings" subtitle="Current league records and points leaderboard." icon={Medal} />
          {standingsRows.length === 0 ? (
            <EmptyState message="No league teams are available yet." />
          ) : (
            <div className="divide-y divide-cfb-border-subtle">
              {standingsRows.map((row, index) => {
                const teamName = formatValue(row.team_name ?? row.name ?? `Team ${index + 1}`);
                return (
                  <div
                    key={`${teamName}-${index}`}
                    className="grid gap-4 px-4 py-3 transition-colors hover:bg-cfb-surface-hover md:grid-cols-[56px_minmax(0,1fr)_110px_120px_120px]"
                  >
                    <span className="text-lg font-black text-cfb-brand">#{formatValue(row.rank ?? index + 1)}</span>
                    <span className="font-black text-cfb-text-primary">{teamName}</span>
                    <span className="text-sm font-bold text-cfb-text-secondary">
                      {formatRecord(row)}
                    </span>
                    <span className="text-sm font-bold text-cfb-text-secondary">PF {formatValue(row.points_for ?? 0)}</span>
                    <span className="text-sm font-bold text-cfb-text-secondary">PA {formatValue(row.points_against ?? 0)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "playoffs" ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <PanelHeader title="Playoff Picture" subtitle="League playoff seeding, bracket, and final standings." icon={Trophy} />
          {!postDraft ? <EmptyState message="The playoff picture becomes available after the draft." /> : postseasonQuery.isLoading ? <div className="p-5 text-sm font-bold text-cfb-text-secondary">Loading playoff picture...</div> : postseasonQuery.isError || !postseasonQuery.data ? <div className="p-5"><ErrorState title="Unable to load playoffs" message="The playoff picture could not be loaded." retryLabel="Try again" onRetry={() => void postseasonQuery.refetch()} /></div> : <PostseasonBracketPanel leagueId={parsedLeagueId} data={postseasonQuery.data} />}
        </section>
      ) : null}

      {activePanel === "scoring" ? (
        <section className="grid gap-5 xl:grid-cols-[1.2fr_0.9fr_0.9fr]">
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface">
            <PanelHeader title="Point System" subtitle="League-specific fantasy scoring values." icon={Settings2} />
            <div className="grid gap-3 p-5 sm:grid-cols-2">
              {scoringEntries.length === 0 ? (
                <EmptyState message="No point system has been configured." />
              ) : (
                scoringEntries.map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">
                      {scoringLabels[key] ?? key.replace(/_/g, " ")}
                    </p>
                    <p className="mt-1 text-xl font-black text-cfb-text-primary">{formatValue(value)}</p>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface">
            <PanelHeader title="Roster System" subtitle="Starting, bench, and IR slots for every team." icon={ShieldCheck} />
            <div className="grid gap-3 p-5">
              {rosterEntries.map(([slot, count]) => (
                <div key={slot} className="flex items-center justify-between rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3">
                  <span className={`rounded-xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] ${slotTone(slot)}`}>
                    {slot}
                  </span>
                  <span className="text-xl font-black text-cfb-text-primary">{formatValue(count)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-cfb-border-subtle bg-cfb-surface">
            <PanelHeader title="Waiver System" subtitle="How unrostered players are claimed in this league." icon={ListOrdered} />
            <div className="grid gap-3 p-5">
              <div className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3">
                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">Claim format</p>
                <p className="mt-1 text-xl font-black text-cfb-text-primary">{waiverSystem}</p>
                <p className="mt-1.5 text-xs font-semibold leading-5 text-cfb-text-secondary">
                  {waiverSystem === "FAAB"
                    ? "Managers submit blind bids from their league FAAB budget."
                    : "Claims are awarded using the league waiver wire order."}
                </p>
              </div>
              {waiverRuleEntries.map(([key, value]) => (
                <div key={key} className="flex items-center justify-between rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3">
                  <span className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-text-secondary">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm font-black uppercase text-cfb-text-primary">{formatValue(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {activePanel === "schedule" ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <PanelHeader title="Manager Schedules" subtitle="The regular-season schedule is generated when the draft completes. Choose any week to see every league matchup." icon={CalendarDays} />
          {(data?.schedule ?? []).length === 0 ? (
            <EmptyState message="Schedule has not been generated yet." />
          ) : (
            <div className="space-y-5 p-5">
              <div className="flex flex-col gap-3 rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">Regular Season</p>
                  <p className="mt-1 text-xs font-bold text-cfb-text-secondary">
                    Weeks 1–{regularSeasonFinalWeek} · every team has one matchup each week.
                  </p>
                </div>
                <Select
                  value={selectedScheduleWeek === null ? undefined : String(selectedScheduleWeek)}
                  onValueChange={(value) => setSelectedScheduleWeek(Number(value))}
                >
                  <SelectTrigger className="h-10 w-full rounded-lg border-cfb-border-subtle bg-cfb-canvas text-[11px] font-black uppercase tracking-[0.14em] text-cfb-text-primary md:w-[220px]">
                    <SelectValue placeholder="Choose week" />
                  </SelectTrigger>
                  <SelectContent className="border-cfb-border-subtle bg-cfb-surface text-cfb-text-primary">
                    {scheduleWeeks.map((week) => (
                      <SelectItem key={week} value={String(week)}>
                        Week {week}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-7" role="group" aria-label="Regular season week">
                {scheduleWeeks.map((week) => {
                  const active = selectedScheduleWeek === week;
                  return (
                    <button
                      key={week}
                      type="button"
                      onClick={() => setSelectedScheduleWeek(week)}
                      aria-pressed={active}
                      className={[
                        "rounded-lg border px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] transition-colors",
                        active
                          ? "border-cfb-brand/60 bg-cfb-brand/10 text-cfb-brand"
                          : "border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-secondary hover:bg-cfb-surface-hover hover:text-cfb-text-primary",
                      ].join(" ")}
                    >
                      Week {week}
                    </button>
                  );
                })}
              </div>

              {selectedScheduleRows.length === 0 ? (
                <EmptyState message="No matchups are scheduled for this week." />
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {selectedScheduleRows.map((row) => (
                    <div key={row.matchup_id} className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-4 transition-colors hover:bg-cfb-surface-hover">
                      <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">Week {row.week}</p>
                      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                        <p className="text-sm font-black text-cfb-text-primary">{row.home_team_name}</p>
                        <span className="rounded border border-cfb-border-subtle bg-cfb-canvas px-2 py-1 text-[10px] font-black text-cfb-text-muted">VS</span>
                        <p className="text-right text-sm font-black text-cfb-text-primary">{row.away_team_name}</p>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-3 text-xs font-bold text-cfb-text-secondary">
                        <span>Proj {Number(row.home_projected_total ?? 0).toFixed(1)}</span>
                        <span className="text-right">Proj {Number(row.away_projected_total ?? 0).toFixed(1)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "rosters" ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <PanelHeader title="Manager Roster" subtitle="Select one manager to inspect their league-scoped roster." icon={Users} />
          {rosterTeamNames.length === 0 ? (
            <EmptyState message="No roster players have been imported yet." />
          ) : (
            <div className="space-y-5 p-5">
              <div className="flex flex-col gap-3 rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand">Select Manager</p>
                  <p className="mt-1 text-xs font-bold text-cfb-text-secondary">Only one roster is shown at a time so this stays readable.</p>
                </div>
                <Select value={selectedRosterTeam} onValueChange={setSelectedRosterTeam}>
                  <SelectTrigger className="h-10 w-full rounded-lg border-cfb-border-subtle bg-cfb-canvas text-[11px] font-black uppercase tracking-[0.14em] text-cfb-text-primary md:w-[300px]">
                    <SelectValue placeholder="Choose manager" />
                  </SelectTrigger>
                  <SelectContent className="border-cfb-border-subtle bg-cfb-surface text-cfb-text-primary">
                    {rosterTeamNames.map((teamName) => (
                      <SelectItem key={teamName} value={teamName}>
                        {teamName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <RosterSlotTable
                title={`${selectedRosterTeam} · ${selectedRosterPlayers.length} roster spots`}
                players={selectedRosterPlayers}
                emptyText="This manager does not have imported roster players yet."
                showPositionColumn={false}
                leagueId={parsedLeagueId}
              />
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "trades" ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <PanelHeader title="Trade History" subtitle="Completed league trades, including both managers, exchanged players, and the completion time." icon={History} />
          {tradeHistory.length === 0 ? (
            <EmptyState message="No completed league trades have been recorded yet." />
          ) : (
            <div className="space-y-4 p-5">
              {tradeHistory.map((trade) => {
                const tradePath = tradeOfferPath(parsedLeagueId, trade.id);
                return (
                  <article key={trade.id} className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-4">
                    <div className="flex flex-col gap-3 border-b border-cfb-border-subtle pb-4 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2 text-sm font-black text-cfb-text-primary">
                          <span>{trade.proposing_party.team_name}</span>
                          <ArrowRightLeft className="h-4 w-4 text-cfb-brand" aria-hidden="true" />
                          <span>{trade.receiving_party.team_name}</span>
                        </div>
                        <p className="mt-2 text-xs font-semibold text-cfb-text-secondary">
                          Managers: {trade.proposing_party.manager_name ?? "Unavailable"} and {trade.receiving_party.manager_name ?? "Unavailable"}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                        <p className="text-right text-xs font-bold text-cfb-text-muted">
                          Completed {formatDateTime(trade.processed_at ?? trade.accepted_at ?? trade.created_at)}
                        </p>
                        {tradePath ? (
                          <Link to={tradePath} className="rounded-lg border border-cfb-brand/50 bg-cfb-brand/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-cfb-brand transition-colors hover:bg-cfb-brand/15">
                            View trade
                          </Link>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg border border-cfb-border-subtle bg-cfb-canvas p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-rose-100">{trade.proposing_party.team_name} sent</p>
                        <ul className="mt-2 space-y-1 text-sm font-semibold text-cfb-text-primary">
                          {formatTradeAssets(trade.proposing_team_sends).map((asset) => <li key={asset}>{asset}</li>)}
                        </ul>
                      </div>
                      <div className="rounded-lg border border-cfb-border-subtle bg-cfb-canvas p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-emerald-100">{trade.receiving_party.team_name} sent</p>
                        <ul className="mt-2 space-y-1 text-sm font-semibold text-cfb-text-primary">
                          {formatTradeAssets(trade.receiving_team_sends).map((asset) => <li key={asset}>{asset}</li>)}
                        </ul>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "draft" ? (
        <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
          <PanelHeader title="Draft Results" subtitle="Every completed pick in this league appears here automatically." icon={ClipboardList} />
          {(data?.draft_results ?? []).length === 0 ? (
            <EmptyState message="No completed draft picks yet. Results will appear here as soon as the draft begins." />
          ) : (
            <div className="divide-y divide-cfb-border-subtle">
              {data?.draft_results.map((pick, index) => (
                <div key={`${pick.overall_pick}-${index}`} className="grid gap-3 px-5 py-4 md:grid-cols-[80px_90px_minmax(0,1fr)_minmax(0,1fr)_70px]">
                  <p className="text-lg font-black text-cfb-brand">#{formatValue(pick.overall_pick)}</p>
                  <p className="text-sm font-bold text-cfb-text-secondary">R{formatValue(pick.round_number)}.{formatValue(pick.round_pick)}</p>
                  <p className="font-black text-cfb-text-primary">{formatValue(pick.player_name)}</p>
                  <p className="text-sm font-bold text-cfb-text-secondary">{formatValue(pick.team_name)}</p>
                  <p className="text-right text-sm font-black text-cfb-text-primary">{formatValue(pick.position)}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}
    </main>
  );
}

function PanelHeader({
  title,
  subtitle,
  icon: Icon,
}: {
  title: string;
  subtitle: string;
  icon: typeof Trophy;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-cfb-border-subtle px-4 py-3.5">
      <div>
        <h2 className="text-[11px] font-black uppercase tracking-[0.18em] text-cfb-brand">{title}</h2>
        <p className="mt-1 text-xs font-semibold text-cfb-text-secondary">{subtitle}</p>
      </div>
      <Icon className="h-5 w-5 shrink-0 text-cfb-text-muted" aria-hidden="true" />
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="p-5">
      <div className="rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised px-4 py-5 text-sm font-bold text-cfb-text-secondary">
        {message}
      </div>
    </div>
  );
}

function InviteSettingsCard({
  data,
  copiedField,
  onCopy,
}: {
  data: LeagueSettingsTabResponse;
  copiedField: "code" | "link" | null;
  onCopy: (field: "code" | "link", value?: string | null) => void;
}) {
  const invite = data.invite;
  if (!invite) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-cfb-border-subtle bg-cfb-surface">
      <div className="grid gap-4 p-4 lg:grid-cols-[1fr_1.1fr] lg:items-center">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised text-cfb-brand">
              <Link2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cfb-brand">
                Commissioner Invite
              </p>
              <h2 className="mt-1 text-lg font-black text-cfb-text-primary">Invite code saved in league settings</h2>
            </div>
          </div>
          <p className="mt-3 max-w-2xl text-sm font-semibold leading-6 text-cfb-text-secondary">
            This code and link stay visible here until the draft is completed, so the commissioner can always copy them again before the league locks.
          </p>
        </div>

        <div className="grid gap-3">
          <div className="grid gap-3 rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3 md:grid-cols-[1fr_auto] md:items-center">
            <div className="min-w-0">
              <p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Invite Code</p>
              <p className="mt-1 break-all font-mono text-lg font-black text-cfb-text-primary">{invite.code}</p>
            </div>
            <button
              type="button"
              onClick={() => onCopy("code", invite.code)}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-cfb-brand/45 bg-cfb-brand/10 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand transition-colors hover:bg-cfb-brand/15"
            >
              <Copy className="h-4 w-4" />
              {copiedField === "code" ? "Copied" : "Copy Code"}
            </button>
          </div>

          <div className="grid gap-3 rounded-lg border border-cfb-border-subtle bg-cfb-surface-raised p-3 md:grid-cols-[1fr_auto] md:items-center">
            <div className="min-w-0">
              <p className="text-[9px] font-black uppercase tracking-[0.16em] text-cfb-text-muted">Invite Link</p>
              <p className="mt-1 break-all font-mono text-xs font-bold text-cfb-text-secondary">{invite.link}</p>
            </div>
            <button
              type="button"
              onClick={() => onCopy("link", invite.link)}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-cfb-brand/45 bg-cfb-brand/10 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-cfb-brand transition-colors hover:bg-cfb-brand/15"
            >
              <Copy className="h-4 w-4" />
              {copiedField === "link" ? "Copied" : "Copy Link"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
