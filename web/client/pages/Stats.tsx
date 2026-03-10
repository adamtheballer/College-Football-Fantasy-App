import React, { useEffect, useMemo, useState } from "react";
import { Activity, Shield, BarChart3, CalendarDays, Stethoscope, Trophy } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

type TeamSummary = {
  team: string;
  conference: string;
  bye_week: number | null;
  has_offense_data: boolean;
  has_defense_data: boolean;
  has_advanced_data: boolean;
  updated_at: string | null;
};

type TeamDetail = {
  team: string;
  conference: string;
  season: number;
  week: number;
  bye_week: number | null;
  offense: Record<string, string | number | null>;
  defense: Record<string, string | number | null>;
  advanced: Record<string, string | number | null | Record<string, unknown>>;
  last_updated: string | null;
};

type TeamStanding = {
  team: string;
  conference: string;
  conference_rank: number | null;
  conference_wins: number | null;
  conference_losses: number | null;
  overall_wins: number | null;
  overall_losses: number | null;
};

type TeamInjury = {
  player_id: number;
  player_name: string;
  team: string;
  conference: string;
  position: string;
  status: string;
  injury: string | null;
  return_timeline: string | null;
  notes: string | null;
  last_updated: string;
};

type StatsTab = "offense" | "defense" | "advanced" | "injuries" | "standings";

const CONFERENCES = ["ALL", "SEC", "BIG10", "BIG12", "ACC"] as const;
const CURRENT_YEAR = new Date().getFullYear();
const SEASONS = Array.from({ length: CURRENT_YEAR - 2003 }, (_, idx) => CURRENT_YEAR - idx);
const POWER4_TEAMS_BY_CONFERENCE: Record<string, string[]> = {
  SEC: [
    "Alabama",
    "Arkansas",
    "Auburn",
    "Florida",
    "Georgia",
    "Kentucky",
    "LSU",
    "Mississippi State",
    "Missouri",
    "Oklahoma",
    "Ole Miss",
    "South Carolina",
    "Tennessee",
    "Texas",
    "Texas A&M",
    "Vanderbilt",
  ],
  BIG10: [
    "Illinois",
    "Indiana",
    "Iowa",
    "Maryland",
    "Michigan",
    "Michigan State",
    "Minnesota",
    "Nebraska",
    "Northwestern",
    "Ohio State",
    "Oregon",
    "Penn State",
    "Purdue",
    "Rutgers",
    "UCLA",
    "USC",
    "Washington",
    "Wisconsin",
  ],
  BIG12: [
    "Arizona",
    "Arizona State",
    "Baylor",
    "BYU",
    "Cincinnati",
    "Colorado",
    "Houston",
    "Iowa State",
    "Kansas",
    "Kansas State",
    "Oklahoma State",
    "TCU",
    "Texas Tech",
    "UCF",
    "Utah",
    "West Virginia",
  ],
  ACC: [
    "Boston College",
    "California",
    "Clemson",
    "Duke",
    "Florida State",
    "Georgia Tech",
    "Louisville",
    "Miami",
    "NC State",
    "North Carolina",
    "Pittsburgh",
    "SMU",
    "Stanford",
    "Syracuse",
    "Virginia",
    "Virginia Tech",
    "Wake Forest",
  ],
};
const FALLBACK_TEAM_ROWS: TeamSummary[] = Object.entries(POWER4_TEAMS_BY_CONFERENCE)
  .flatMap(([conference, teamNames]) =>
    teamNames.map((team) => ({
      team,
      conference,
      bye_week: null,
      has_offense_data: false,
      has_defense_data: false,
      has_advanced_data: false,
      updated_at: null,
    }))
  )
  .sort((a, b) => a.team.localeCompare(b.team));

const formatLabel = (value: string) =>
  value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

const renderValue = (value: unknown) => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return Number.isInteger(value) ? value : value.toFixed(3);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

const flattenEntries = (value: unknown, prefix = ""): Array<[string, unknown]> => {
  if (value === null || value === undefined) {
    return [[prefix || "value", value]];
  }
  if (typeof value !== "object") {
    return [[prefix || "value", value]];
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return [[prefix || "value", "[]"]];
    return value.flatMap((item, index) => flattenEntries(item, `${prefix}[${index}]`));
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj);
  if (keys.length === 0) {
    return [[prefix || "value", "{}"]];
  }
  return keys.flatMap((key) => {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    return flattenEntries(obj[key], nextPrefix);
  });
};

export default function Stats() {
  const [season, setSeason] = useState<number>(2026);
  const [conference, setConference] = useState<string>("ALL");
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<StatsTab>("offense");

  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>("");
  const [teamDetail, setTeamDetail] = useState<TeamDetail | null>(null);
  const [standings, setStandings] = useState<TeamStanding[]>([]);
  const [injuries, setInjuries] = useState<TeamInjury[]>([]);
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [teamsError, setTeamsError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingTeams(true);
    apiGet<{ data: TeamSummary[] }>("/stats/teams", { season, conference }, controller.signal)
      .then((payload) => {
        const apiRows = payload?.data ?? [];
        const rows =
          apiRows.length > 0
            ? apiRows
            : conference === "ALL"
              ? FALLBACK_TEAM_ROWS
              : FALLBACK_TEAM_ROWS.filter((row) => row.conference === conference);
        setTeamsError(null);
        setTeams(rows);
        if (!selectedTeam || !rows.some((row) => row.team === selectedTeam)) {
          setSelectedTeam(rows[0].team);
        }
      })
      .catch(() => {
        const fallbackRows = conference === "ALL"
          ? FALLBACK_TEAM_ROWS
          : FALLBACK_TEAM_ROWS.filter((row) => row.conference === conference);
        setTeams(fallbackRows);
        setTeamsError("Backend connection failed. Showing static Power-4 team list.");
        setSelectedTeam(fallbackRows[0]?.team ?? "");
        setTeamDetail(null);
      })
      .finally(() => setLoadingTeams(false));
    return () => controller.abort();
  }, [season, conference]);

  useEffect(() => {
    if (!selectedTeam) {
      setTeamDetail(null);
      return;
    }
    const controller = new AbortController();
    setLoadingDetail(true);
    apiGet<TeamDetail>(`/stats/team/${encodeURIComponent(selectedTeam)}`, { season }, controller.signal)
      .then((payload) => setTeamDetail(payload))
      .catch(() => setTeamDetail(null))
      .finally(() => setLoadingDetail(false));
    return () => controller.abort();
  }, [selectedTeam, season]);

  useEffect(() => {
    const standingsConference =
      conference === "ALL" ? teams.find((team) => team.team === selectedTeam)?.conference : conference;
    if (!standingsConference) {
      setStandings([]);
      return;
    }
    const controller = new AbortController();
    apiGet<{ data: TeamStanding[] }>(
      "/stats/standings",
      { season, conference: standingsConference },
      controller.signal
    )
      .then((payload) => setStandings(payload?.data ?? []))
      .catch(() => setStandings([]));
    return () => controller.abort();
  }, [season, conference, selectedTeam, teams]);

  useEffect(() => {
    const injuriesConference =
      conference === "ALL" ? teams.find((team) => team.team === selectedTeam)?.conference : conference;
    const params: Record<string, string | number> = { season, week: 1 };
    if (injuriesConference) {
      params.conference = injuriesConference;
    }
    const controller = new AbortController();
    apiGet<{ data: TeamInjury[] }>("/stats/injuries", params, controller.signal)
      .then((payload) => {
        const rows = payload?.data ?? [];
        setInjuries(
          selectedTeam
            ? rows.filter((row) => row.team === selectedTeam)
            : rows
        );
      })
      .catch(() => setInjuries([]));
    return () => controller.abort();
  }, [season, conference, selectedTeam, teams]);

  const filteredTeams = useMemo(() => {
    const searchLower = search.trim().toLowerCase();
    if (!searchLower) return teams;
    return teams.filter((team) => team.team.toLowerCase().includes(searchLower));
  }, [teams, search]);

  const statsRows = useMemo(() => {
    if (!teamDetail) return [];
    if (activeTab === "offense") return flattenEntries(teamDetail.offense);
    if (activeTab === "defense") return flattenEntries(teamDetail.defense);
    if (activeTab === "advanced") return flattenEntries(teamDetail.advanced);
    return [];
  }, [teamDetail, activeTab]);

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-in fade-in duration-700">
      <div className="space-y-2">
        <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground">Stats</h1>
        <p className="text-[11px] font-black tracking-[0.3em] text-primary uppercase">
          Power 4 Team Research Center
        </p>
      </div>

      <Card className="bg-card/40 backdrop-blur-md border border-white/10 rounded-[2.5rem] p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2" id="season-selector">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Season</p>
            <Select value={String(season)} onValueChange={(value) => setSeason(Number(value))}>
              <SelectTrigger className="h-10 w-[160px] bg-white/5 border-white/10 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]">
                <SelectValue placeholder="Select season" />
              </SelectTrigger>
              <SelectContent className="bg-[#0A0C10] border-border rounded-2xl max-h-[280px]">
                {SEASONS.map((value) => (
                  <SelectItem key={value} value={String(value)} className="text-xs font-semibold">
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2" id="conference-filter">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Conference</p>
            <div className="flex gap-2 flex-wrap">
              {CONFERENCES.map((value) => (
                <Button
                  key={value}
                  variant={conference === value ? "default" : "outline"}
                  className={cn(
                    "h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]",
                    conference === value
                      ? "bg-primary text-primary-foreground"
                      : "bg-white/5 border-white/10 text-muted-foreground hover:text-primary"
                  )}
                  onClick={() => setConference(value)}
                >
                  {value}
                </Button>
              ))}
            </div>
          </div>
          <div className="space-y-2" id="team-search">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Search Team</p>
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search team..."
              className="h-10 bg-white/5 border-white/10 rounded-xl text-[11px] font-bold"
            />
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
        <Card className="bg-card/40 backdrop-blur-md border border-white/10 rounded-[2.5rem] overflow-hidden" id="power4-team-list">
          <CardHeader className="border-b border-white/10">
            <CardTitle className="text-[10px] font-black tracking-[0.3em] uppercase text-primary">
              Power 4 Teams
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 max-h-[740px] overflow-y-auto">
            {loadingTeams && (
              <div className="p-6 text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">
                Loading teams...
              </div>
            )}
            {!loadingTeams && filteredTeams.length === 0 && (
              <div className="p-6 text-[10px] font-black tracking-[0.2em] uppercase text-muted-foreground/60">
                No teams found for this filter.
              </div>
            )}
            {teamsError && (
              <div className="px-6 py-4 border-b border-white/5 text-[9px] font-black uppercase tracking-[0.15em] text-amber-300/80">
                {teamsError}
              </div>
            )}
            {filteredTeams.map((team) => (
              <button
                key={team.team}
                onClick={() => setSelectedTeam(team.team)}
                className={cn(
                  "w-full text-left px-5 py-4 border-b border-white/5 hover:bg-white/5 transition-colors",
                  selectedTeam === team.team && "bg-primary/10"
                )}
              >
                <p className="text-[12px] font-black uppercase tracking-wider text-foreground">{team.team}</p>
                <div className="mt-1 flex items-center justify-between text-[9px] font-bold uppercase tracking-[0.15em] text-muted-foreground/60">
                  <span>{team.conference}</span>
                  <span>{team.bye_week ? `Bye Wk ${team.bye_week}` : "Bye - N/A"}</span>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="bg-card/40 backdrop-blur-md border border-white/10 rounded-[2.5rem] overflow-hidden" id="team-analytics-panel">
          <CardHeader className="border-b border-white/10">
            <div className="flex flex-col gap-3">
              <CardTitle className="text-2xl font-black italic uppercase tracking-tight text-foreground">
                {selectedTeam || "Select a Team"}
              </CardTitle>
              <div className="flex flex-wrap gap-2">
                {[
                  { key: "offense", label: "Offense", icon: Activity },
                  { key: "defense", label: "Defense", icon: Shield },
                  { key: "advanced", label: "Advanced", icon: BarChart3 },
                  { key: "injuries", label: "Injuries", icon: Stethoscope },
                  { key: "standings", label: "Standings", icon: Trophy },
                ].map((tab) => (
                  <Button
                    key={tab.key}
                    id={`${tab.key}-tab`}
                    onClick={() => setActiveTab(tab.key as StatsTab)}
                    className={cn(
                      "h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-[0.2em] gap-2",
                      activeTab === tab.key
                        ? "bg-primary text-primary-foreground"
                        : "bg-white/5 border border-white/10 text-muted-foreground hover:text-primary"
                    )}
                  >
                    <tab.icon className="w-3.5 h-3.5" />
                    {tab.label}
                  </Button>
                ))}
              </div>
              <div className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                <CalendarDays className="w-4 h-4" />
                {teamDetail?.bye_week ? `Bye Week ${teamDetail.bye_week}` : "Bye Week N/A"}
                <span>•</span>
                <span>
                  {teamDetail?.last_updated
                    ? `Updated ${new Date(teamDetail.last_updated).toLocaleString()}`
                    : "No saved data"}
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loadingDetail && activeTab !== "standings" && activeTab !== "injuries" && (
              <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Loading stats...
              </div>
            )}

            {(activeTab === "offense" || activeTab === "defense" || activeTab === "advanced") && (
              <div className="max-h-[640px] overflow-auto">
                {statsRows.length === 0 ? (
                  <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    No {activeTab} data available for {season}. Switch to 2025 if needed.
                  </div>
                ) : (
                  <table className="w-full">
                    <thead className="sticky top-0 bg-white/5 border-b border-white/10">
                      <tr>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                          Stat
                        </th>
                        <th className="px-6 py-4 text-right text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                          Value
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {statsRows.map(([key, value], index) => (
                        <tr key={`${key}-${index}`}>
                          <td className="px-6 py-3 text-[11px] font-black uppercase tracking-[0.12em] text-foreground">
                            {formatLabel(key)}
                          </td>
                          <td className="px-6 py-3 text-right text-[11px] font-bold text-muted-foreground/80">
                            {renderValue(value)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {activeTab === "injuries" && (
              <div className="max-h-[640px] overflow-auto">
                {injuries.length === 0 ? (
                  <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    No injury rows for selected filters.
                  </div>
                ) : (
                  <table className="w-full">
                    <thead className="sticky top-0 bg-white/5 border-b border-white/10">
                      <tr>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Player</th>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Pos</th>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Status</th>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Injury</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {injuries.map((row) => (
                        <tr key={row.player_id}>
                          <td className="px-6 py-3 text-[11px] font-black uppercase tracking-[0.12em] text-foreground">{row.player_name}</td>
                          <td className="px-6 py-3 text-[11px] font-bold text-muted-foreground/80">{row.position}</td>
                          <td className="px-6 py-3 text-[11px] font-bold text-muted-foreground/80">{row.status}</td>
                          <td className="px-6 py-3 text-[11px] font-bold text-muted-foreground/80">{row.injury || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {activeTab === "standings" && (
              <div className="max-h-[640px] overflow-auto">
                {standings.length === 0 ? (
                  <div className="p-8 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    No standings data available yet for {season}.
                  </div>
                ) : (
                  <table className="w-full">
                    <thead className="sticky top-0 bg-white/5 border-b border-white/10">
                      <tr>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Rank</th>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Team</th>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Conf</th>
                        <th className="px-6 py-4 text-left text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Overall</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10">
                      {standings.map((row) => (
                        <tr
                          key={row.team}
                          className={cn(selectedTeam === row.team && "bg-primary/10")}
                        >
                          <td className="px-6 py-3 text-[11px] font-black text-foreground">
                            {row.conference_rank ?? "-"}
                          </td>
                          <td className="px-6 py-3 text-[11px] font-black uppercase tracking-[0.12em] text-foreground">
                            {row.team}
                          </td>
                          <td className="px-6 py-3 text-[11px] font-bold text-muted-foreground/80">
                            {row.conference_wins !== null && row.conference_losses !== null
                              ? `${row.conference_wins}-${row.conference_losses}`
                              : "-"}
                          </td>
                          <td className="px-6 py-3 text-[11px] font-bold text-muted-foreground/80">
                            {row.overall_wins !== null && row.overall_losses !== null
                              ? `${row.overall_wins}-${row.overall_losses}`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
