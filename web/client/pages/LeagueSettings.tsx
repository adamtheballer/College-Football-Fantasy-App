import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
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
import { RosterSlotTable } from "@/components/league/RosterSlotTable";
import { ErrorState } from "@/components/states";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useLeagueDetail, useLeagueSettingsTab } from "@/hooks/use-leagues";
import { getLeagueScheduleWeeks } from "@/lib/leagueSchedule";
import { tradeOfferPath } from "@/lib/trade-links";
import type { LeagueRosterPlayer, LeagueSettingsTabResponse } from "@/types/league";

type SettingsPanel = "standings" | "scoring" | "schedule" | "rosters" | "trades" | "draft";

const panels: Array<{ id: SettingsPanel; label: string; icon: typeof Trophy }> = [
  { id: "standings", label: "Standings", icon: Trophy },
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
  const [activePanel, setActivePanel] = useState<SettingsPanel>("standings");
  const [selectedRosterTeam, setSelectedRosterTeam] = useState<string>("");
  const [selectedScheduleWeek, setSelectedScheduleWeek] = useState<number | null>(null);
  const [copiedInviteField, setCopiedInviteField] = useState<"code" | "link" | null>(null);
  const leagueQuery = useLeagueDetail(parsedLeagueId);
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId);
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

  const copyInviteValue = async (field: "code" | "link", value?: string | null) => {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedInviteField(field);
    window.setTimeout(() => setCopiedInviteField(null), 1800);
  };

  if (leagueQuery.isLoading) {
    return (
      <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
        <div className="rounded-[1.5rem] border border-cfb-border-subtle bg-cfb-surface-raised/80 p-8 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cfb-text-muted">
          Loading league...
        </div>
      </main>
    );
  }

  if (leagueQuery.isError) {
    return (
      <main className="relative mx-auto w-full max-w-[1320px] px-6 py-8">
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
    <main className="relative mx-auto flex w-full max-w-[1320px] flex-col gap-6 px-6 py-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[460px] rounded-[3rem] bg-[radial-gradient(circle_at_18%_8%,rgba(56,189,248,0.2),transparent_34%),radial-gradient(circle_at_76%_0%,rgba(99,102,241,0.18),transparent_38%)] blur-2xl" />
      <div className="space-y-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-sky-300">
          League Command Center
        </p>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black italic text-slate-50">
              {data?.league_name ?? "League Settings"}
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              League-specific standings, point system, schedules, manager rosters, trade history, and draft results.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[430px]">
            <div className="rounded-[1.25rem] border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_0_34px_rgba(56,189,248,0.12)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Teams</p>
              <p className="mt-1 text-2xl font-black text-sky-100">
                {formatValue(leagueInfo.teams ?? data?.members?.length)}
              </p>
            </div>
            <div className="rounded-[1.25rem] border border-emerald-300/20 bg-emerald-400/10 p-4 shadow-[0_0_34px_rgba(52,211,153,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Schedule</p>
              <p className="mt-1 text-2xl font-black text-emerald-100">{data?.schedule?.length ?? 0}</p>
            </div>
            <div className="rounded-[1.25rem] border border-violet-300/20 bg-violet-400/10 p-4 shadow-[0_0_34px_rgba(167,139,250,0.10)]">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-400">Trades</p>
              <p className="mt-1 text-2xl font-black text-violet-100">{tradeHistory.length}</p>
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

      <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[linear-gradient(135deg,rgba(13,23,39,0.96),rgba(16,30,52,0.9)_48%,rgba(15,23,42,0.96))] p-3 shadow-[0_24px_90px_rgba(14,165,233,0.12)]">
        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          {panels.map((panel) => {
            const Icon = panel.icon;
            const active = activePanel === panel.id;
            return (
              <button
                key={panel.id}
                type="button"
                onClick={() => setActivePanel(panel.id)}
                className={[
                  "flex min-h-[72px] items-center justify-center gap-2 rounded-2xl border px-3 text-center text-[10px] font-black uppercase tracking-[0.14em] transition-all duration-200",
                  active
                    ? "border-sky-300/55 bg-sky-300/18 text-sky-50 shadow-[0_0_28px_rgba(56,189,248,0.22)]"
                    : "border-white/10 bg-white/[0.04] text-slate-400 hover:-translate-y-0.5 hover:border-sky-300/25 hover:bg-sky-300/[0.07] hover:text-slate-100",
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
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Standings" subtitle="Current league records and points leaderboard." icon={Medal} />
          {standingsRows.length === 0 ? (
            <EmptyState message="No league teams are available yet." />
          ) : (
            <div className="divide-y divide-sky-300/10">
              {standingsRows.map((row, index) => {
                const teamName = formatValue(row.team_name ?? row.name ?? `Team ${index + 1}`);
                return (
                  <div
                    key={`${teamName}-${index}`}
                    className="grid gap-4 px-5 py-4 transition hover:bg-sky-300/[0.045] md:grid-cols-[70px_minmax(0,1fr)_110px_120px_120px]"
                  >
                    <span className="text-2xl font-black italic text-sky-200">#{formatValue(row.rank ?? index + 1)}</span>
                    <span className="font-black text-slate-50">{teamName}</span>
                    <span className="text-sm font-bold text-slate-400">
                      {formatRecord(row)}
                    </span>
                    <span className="text-sm font-bold text-slate-400">PF {formatValue(row.points_for ?? 0)}</span>
                    <span className="text-sm font-bold text-slate-400">PA {formatValue(row.points_against ?? 0)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "scoring" ? (
        <section className="grid gap-5 xl:grid-cols-[1.2fr_0.9fr_0.9fr]">
          <div className="rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
            <PanelHeader title="Point System" subtitle="League-specific fantasy scoring values." icon={Settings2} />
            <div className="grid gap-3 p-5 sm:grid-cols-2">
              {scoringEntries.length === 0 ? (
                <EmptyState message="No point system has been configured." />
              ) : (
                scoringEntries.map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      {scoringLabels[key] ?? key.replace(/_/g, " ")}
                    </p>
                    <p className="mt-2 text-2xl font-black text-sky-100">{formatValue(value)}</p>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
            <PanelHeader title="Roster System" subtitle="Starting, bench, and IR slots for every team." icon={ShieldCheck} />
            <div className="grid gap-3 p-5">
              {rosterEntries.map(([slot, count]) => (
                <div key={slot} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <span className={`rounded-xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] ${slotTone(slot)}`}>
                    {slot}
                  </span>
                  <span className="text-xl font-black text-slate-50">{formatValue(count)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
            <PanelHeader title="Waiver System" subtitle="How unrostered players are claimed in this league." icon={ListOrdered} />
            <div className="grid gap-3 p-5">
              <div className="rounded-2xl border border-sky-300/30 bg-sky-300/[0.11] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-200">Claim format</p>
                <p className="mt-2 text-2xl font-black text-slate-50">{waiverSystem}</p>
                <p className="mt-2 text-xs font-semibold leading-5 text-slate-400">
                  {waiverSystem === "FAAB"
                    ? "Managers submit blind bids from their league FAAB budget."
                    : "Claims are awarded using the league waiver wire order."}
                </p>
              </div>
              {waiverRuleEntries.map(([key, value]) => (
                <div key={key} className="flex items-center justify-between rounded-2xl border border-sky-300/15 bg-sky-300/[0.05] p-4">
                  <span className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm font-black uppercase text-sky-100">{formatValue(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {activePanel === "schedule" ? (
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Manager Schedules" subtitle="The regular-season schedule is generated when the draft completes. Choose any week to see every league matchup." icon={CalendarDays} />
          {(data?.schedule ?? []).length === 0 ? (
            <EmptyState message="Schedule has not been generated yet." />
          ) : (
            <div className="space-y-5 p-5">
              <div className="flex flex-col gap-3 rounded-2xl border border-sky-300/15 bg-sky-300/[0.045] p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-300">Regular Season</p>
                  <p className="mt-1 text-xs font-bold text-slate-500">
                    Weeks 1–{regularSeasonFinalWeek} · every team has one matchup each week.
                  </p>
                </div>
                <Select
                  value={selectedScheduleWeek === null ? undefined : String(selectedScheduleWeek)}
                  onValueChange={(value) => setSelectedScheduleWeek(Number(value))}
                >
                  <SelectTrigger className="h-12 w-full rounded-2xl border-sky-300/20 bg-slate-950/45 text-[11px] font-black uppercase tracking-[0.14em] text-slate-100 md:w-[240px]">
                    <SelectValue placeholder="Choose week" />
                  </SelectTrigger>
                  <SelectContent className="border-sky-300/20 bg-slate-950 text-slate-100">
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
                        "rounded-xl border px-3 py-2.5 text-[10px] font-black uppercase tracking-[0.12em] transition",
                        active
                          ? "border-sky-300/65 bg-sky-300/20 text-sky-50 shadow-[0_0_20px_rgba(56,189,248,0.18)]"
                          : "border-white/10 bg-white/[0.035] text-slate-400 hover:border-sky-300/35 hover:bg-sky-300/[0.08] hover:text-slate-100",
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
                    <div key={row.matchup_id} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 transition hover:-translate-y-0.5 hover:border-sky-300/25 hover:bg-sky-300/[0.06]">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-300">Week {row.week}</p>
                      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                        <p className="text-sm font-black text-slate-50">{row.home_team_name}</p>
                        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-black text-slate-400">VS</span>
                        <p className="text-right text-sm font-black text-slate-50">{row.away_team_name}</p>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-3 text-xs font-bold text-slate-400">
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
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Manager Roster" subtitle="Select one manager to inspect their league-scoped roster." icon={Users} />
          {rosterTeamNames.length === 0 ? (
            <EmptyState message="No roster players have been imported yet." />
          ) : (
            <div className="space-y-5 p-5">
              <div className="flex flex-col gap-3 rounded-2xl border border-sky-300/15 bg-sky-300/[0.045] p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-300">Select Manager</p>
                  <p className="mt-1 text-xs font-bold text-slate-500">Only one roster is shown at a time so this stays readable.</p>
                </div>
                <Select value={selectedRosterTeam} onValueChange={setSelectedRosterTeam}>
                  <SelectTrigger className="h-12 w-full rounded-2xl border-sky-300/20 bg-slate-950/45 text-[11px] font-black uppercase tracking-[0.14em] text-slate-100 md:w-[340px]">
                    <SelectValue placeholder="Choose manager" />
                  </SelectTrigger>
                  <SelectContent className="border-sky-300/20 bg-slate-950 text-slate-100">
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
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Trade History" subtitle="Completed league trades, including both managers, exchanged players, and the completion time." icon={History} />
          {tradeHistory.length === 0 ? (
            <EmptyState message="No completed league trades have been recorded yet." />
          ) : (
            <div className="space-y-4 p-5">
              {tradeHistory.map((trade) => {
                const tradePath = tradeOfferPath(parsedLeagueId, trade.id);
                return (
                  <article key={trade.id} className="rounded-[1.4rem] border border-sky-300/15 bg-sky-300/[0.035] p-4">
                    <div className="flex flex-col gap-3 border-b border-sky-300/10 pb-4 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2 text-sm font-black text-slate-50">
                          <span>{trade.proposing_party.team_name}</span>
                          <ArrowRightLeft className="h-4 w-4 text-sky-300" aria-hidden="true" />
                          <span>{trade.receiving_party.team_name}</span>
                        </div>
                        <p className="mt-2 text-xs font-semibold text-slate-400">
                          Managers: {trade.proposing_party.manager_name ?? "Unavailable"} and {trade.receiving_party.manager_name ?? "Unavailable"}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                        <p className="text-right text-xs font-bold text-slate-500">
                          Completed {formatDateTime(trade.processed_at ?? trade.accepted_at ?? trade.created_at)}
                        </p>
                        {tradePath ? (
                          <Link to={tradePath} className="rounded-lg border border-primary/50 bg-primary/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-primary transition hover:bg-primary/20">
                            View trade
                          </Link>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div className="rounded-xl border border-rose-300/20 bg-rose-500/10 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-rose-100">{trade.proposing_party.team_name} sent</p>
                        <ul className="mt-2 space-y-1 text-sm font-semibold text-slate-100">
                          {formatTradeAssets(trade.proposing_team_sends).map((asset) => <li key={asset}>{asset}</li>)}
                        </ul>
                      </div>
                      <div className="rounded-xl border border-emerald-300/20 bg-emerald-500/10 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-emerald-100">{trade.receiving_party.team_name} sent</p>
                        <ul className="mt-2 space-y-1 text-sm font-semibold text-slate-100">
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
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Draft Results" subtitle="Every completed pick in this league appears here automatically." icon={ClipboardList} />
          {(data?.draft_results ?? []).length === 0 ? (
            <EmptyState message="No completed draft picks yet. Results will appear here as soon as the draft begins." />
          ) : (
            <div className="divide-y divide-sky-300/10">
              {data?.draft_results.map((pick, index) => (
                <div key={`${pick.overall_pick}-${index}`} className="grid gap-3 px-5 py-4 md:grid-cols-[80px_90px_minmax(0,1fr)_minmax(0,1fr)_70px]">
                  <p className="text-xl font-black italic text-sky-200">#{formatValue(pick.overall_pick)}</p>
                  <p className="text-sm font-bold text-slate-400">R{formatValue(pick.round_number)}.{formatValue(pick.round_pick)}</p>
                  <p className="font-black text-slate-50">{formatValue(pick.player_name)}</p>
                  <p className="text-sm font-bold text-slate-400">{formatValue(pick.team_name)}</p>
                  <p className="text-right text-sm font-black text-sky-100">{formatValue(pick.position)}</p>
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
    <div className="flex items-center justify-between gap-4 border-b border-sky-300/10 px-5 py-5">
      <div>
        <h2 className="text-[11px] font-black uppercase tracking-[0.22em] text-sky-300">{title}</h2>
        <p className="mt-2 text-xs font-semibold text-slate-500">{subtitle}</p>
      </div>
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-sky-300/25 bg-sky-300/10 text-sky-100 shadow-[0_0_26px_rgba(56,189,248,0.14)]">
        <Icon className="h-5 w-5" />
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="p-5">
      <div className="rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-6 text-sm font-bold text-slate-400">
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
    <section className="overflow-hidden rounded-[2rem] border border-amber-300/25 bg-[linear-gradient(135deg,rgba(30,41,59,0.96),rgba(15,23,42,0.94)_45%,rgba(67,56,202,0.16))] shadow-[0_22px_80px_rgba(251,191,36,0.12)]">
      <div className="grid gap-5 p-5 lg:grid-cols-[1fr_1.1fr] lg:items-center">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-amber-300/35 bg-amber-300/15 text-amber-100">
              <Link2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-amber-200">
                Commissioner Invite
              </p>
              <h2 className="mt-1 text-xl font-black text-slate-50">Invite code saved in league settings</h2>
            </div>
          </div>
          <p className="mt-4 max-w-2xl text-sm font-semibold leading-6 text-slate-400">
            This code and link stay visible here until the draft is completed, so the commissioner can always copy them again before the league locks.
          </p>
        </div>

        <div className="grid gap-3">
          <div className="grid gap-3 rounded-2xl border border-white/10 bg-white/[0.045] p-4 md:grid-cols-[1fr_auto] md:items-center">
            <div className="min-w-0">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">Invite Code</p>
              <p className="mt-1 break-all font-mono text-lg font-black text-slate-50">{invite.code}</p>
            </div>
            <button
              type="button"
              onClick={() => onCopy("code", invite.code)}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-amber-300/25 bg-amber-300/12 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-amber-100 transition hover:border-amber-200/60 hover:bg-amber-300/18"
            >
              <Copy className="h-4 w-4" />
              {copiedField === "code" ? "Copied" : "Copy Code"}
            </button>
          </div>

          <div className="grid gap-3 rounded-2xl border border-white/10 bg-white/[0.045] p-4 md:grid-cols-[1fr_auto] md:items-center">
            <div className="min-w-0">
              <p className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-500">Invite Link</p>
              <p className="mt-1 break-all font-mono text-xs font-bold text-slate-300">{invite.link}</p>
            </div>
            <button
              type="button"
              onClick={() => onCopy("link", invite.link)}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-sky-300/25 bg-sky-300/12 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-sky-100 transition hover:border-sky-200/60 hover:bg-sky-300/18"
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
