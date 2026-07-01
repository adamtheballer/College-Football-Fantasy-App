import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CalendarDays,
  ClipboardList,
  History,
  Medal,
  Settings2,
  ShieldCheck,
  Trophy,
  Users,
} from "lucide-react";

import { LeagueTabs } from "@/components/league/LeagueTabs";
import { useLeagueSettingsTab } from "@/hooks/use-leagues";
import { useLeagueTransactions } from "@/hooks/use-roster-actions";
import { DEMO_LEAGUE_ID, createDemoLeagueSettingsResponse } from "@/lib/leaguePreviewData";
import type { LeagueRosterPlayer } from "@/types/league";

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

export default function LeagueSettings() {
  const { leagueId } = useParams();
  const parsedLeagueId = Number(leagueId);
  const isDemoLeague = parsedLeagueId === DEMO_LEAGUE_ID;
  const [activePanel, setActivePanel] = useState<SettingsPanel>("standings");
  const settingsQuery = useLeagueSettingsTab(parsedLeagueId, !isDemoLeague);
  const transactionsQuery = useLeagueTransactions(parsedLeagueId, !isDemoLeague);
  const data = isDemoLeague ? createDemoLeagueSettingsResponse() : settingsQuery.data;
  const tradeTransactions = (transactionsQuery.data?.data ?? []).filter((transaction) =>
    transaction.transaction_type.toLowerCase().includes("trade")
  );
  const rosterGroups = useMemo(() => groupRostersByTeam(data?.rosters ?? []), [data?.rosters]);
  const scoringEntries = Object.entries(data?.scoring_settings ?? {});
  const rosterEntries = Object.entries(data?.roster_settings ?? {}).sort(
    ([first], [second]) => slotOrder.indexOf(first) - slotOrder.indexOf(second)
  );
  const leagueInfo = data?.league_info ?? {};

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
              <p className="mt-1 text-2xl font-black text-violet-100">{tradeTransactions.length}</p>
            </div>
          </div>
        </div>
        <LeagueTabs leagueId={parsedLeagueId} />
      </div>

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
          {(data?.standings ?? []).length === 0 ? (
            <EmptyState message="Standings are not available yet." />
          ) : (
            <div className="divide-y divide-sky-300/10">
              {data?.standings.map((row, index) => {
                const teamName = formatValue(row.team_name ?? row.name ?? `Team ${index + 1}`);
                return (
                  <div
                    key={`${teamName}-${index}`}
                    className="grid gap-4 px-5 py-4 transition hover:bg-sky-300/[0.045] md:grid-cols-[70px_minmax(0,1fr)_110px_120px_120px]"
                  >
                    <span className="text-2xl font-black italic text-sky-200">#{formatValue(row.rank ?? index + 1)}</span>
                    <span className="font-black text-slate-50">{teamName}</span>
                    <span className="text-sm font-bold text-slate-400">
                      {formatValue(row.wins ?? 0)}-{formatValue(row.losses ?? 0)}-{formatValue(row.ties ?? 0)}
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
        <section className="grid gap-5 lg:grid-cols-[1fr_0.9fr]">
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
            <PanelHeader title="Roster Rules" subtitle="Slots and waiver rules for this league." icon={ShieldCheck} />
            <div className="grid gap-3 p-5">
              {rosterEntries.map(([slot, count]) => (
                <div key={slot} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <span className={`rounded-xl border px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] ${slotTone(slot)}`}>
                    {slot}
                  </span>
                  <span className="text-xl font-black text-slate-50">{formatValue(count)}</span>
                </div>
              ))}
              {Object.entries(data?.waiver_rules ?? {}).map(([key, value]) => (
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
          <PanelHeader title="Manager Schedules" subtitle="Every scheduled matchup by week." icon={CalendarDays} />
          {(data?.schedule ?? []).length === 0 ? (
            <EmptyState message="Schedule has not been generated yet." />
          ) : (
            <div className="grid gap-4 p-5 md:grid-cols-2">
              {data?.schedule.map((row) => (
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
        </section>
      ) : null}

      {activePanel === "rosters" ? (
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Every Manager Roster" subtitle="League-scoped roster ownership for each fantasy team." icon={Users} />
          {Object.keys(rosterGroups).length === 0 ? (
            <EmptyState message="No roster players have been imported yet." />
          ) : (
            <div className="grid gap-5 p-5 lg:grid-cols-2">
              {Object.entries(rosterGroups).map(([teamName, players]) => (
                <div key={teamName} className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.035]">
                  <div className="border-b border-white/10 px-4 py-3">
                    <p className="text-[11px] font-black uppercase tracking-[0.18em] text-sky-200">{teamName}</p>
                  </div>
                  <div className="divide-y divide-white/10">
                    {players.map((player) => {
                      const slot = player.slot ?? player.roster_slot;
                      return (
                        <div key={player.id} className="grid grid-cols-[72px_minmax(0,1fr)_70px] items-center gap-3 px-4 py-3">
                          <span className={`rounded-xl border px-2 py-2 text-center text-[10px] font-black uppercase tracking-[0.12em] ${slotTone(slot)}`}>
                            {slot ?? "-"}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-black text-slate-50">{player.player_name}</p>
                            <p className="truncate text-xs font-bold text-slate-500">{player.school ?? player.player_school ?? "-"}</p>
                          </div>
                          <p className="text-right text-sm font-black text-sky-100">
                            {Number(player.weekly_projected_fantasy_points ?? player.projected_points ?? 0).toFixed(1)}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "trades" ? (
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Trade History" subtitle="League-specific trade history. This does not mix transactions from other leagues." icon={History} />
          {tradeTransactions.length === 0 ? (
            <EmptyState message="No completed league trades have been recorded yet." />
          ) : (
            <div className="divide-y divide-sky-300/10">
              {tradeTransactions.map((transaction) => (
                <div key={transaction.id} className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_150px_180px]">
                  <p className="font-black uppercase text-slate-50">{transaction.transaction_type.replace(/_/g, " ")}</p>
                  <p className="text-sm font-bold text-slate-400">Team #{transaction.team_id}</p>
                  <p className="text-sm font-bold text-slate-500">
                    {new Date(transaction.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {activePanel === "draft" ? (
        <section className="overflow-hidden rounded-[2rem] border border-sky-300/20 bg-[#0b1424]/92 shadow-[0_18px_70px_rgba(14,165,233,0.10)]">
          <PanelHeader title="Draft Results" subtitle="Every pick imported into this league." icon={ClipboardList} />
          {(data?.draft_results ?? []).length === 0 ? (
            <EmptyState message="Draft results are not available yet." />
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
