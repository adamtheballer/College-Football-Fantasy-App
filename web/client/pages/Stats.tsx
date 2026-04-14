import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Shield,
  BarChart3,
  CalendarDays,
  Stethoscope,
  Trophy,
  UserRoundSearch,
  TrendingUp,
  Waves,
  Scale,
  Gauge,
  Target,
  BarChart2,
  Check,
  ChevronsUpDown,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { apiGet, apiPost } from "@/lib/api";
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
  offense: Record<string, unknown>;
  defense: Record<string, unknown>;
  advanced: Record<string, unknown>;
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
};

type CompareSide = {
  player_id: number;
  player_name: string;
  school: string;
  position: string;
  fantasy_ppg: number;
  usage_rate: number;
  red_zone_touches: number;
  projected_matchup_difficulty: string;
};

type CompareResponse = {
  player_a: CompareSide;
  player_b: CompareSide;
};

type ProjectionRead = {
  player_id: number;
  season: number;
  week: number;
  pass_attempts: number;
  rush_attempts: number;
  targets: number;
  receptions: number;
  expected_plays: number;
  expected_rush_per_play: number;
  expected_td_per_play: number;
  pass_yards: number;
  rush_yards: number;
  rec_yards: number;
  pass_tds: number;
  rush_tds: number;
  rec_tds: number;
  interceptions: number;
  fantasy_points: number;
  floor: number;
  ceiling: number;
  boom_prob: number;
  bust_prob: number;
  qb_rating: number | null;
};

type ProjectionExplanationPayload = {
  player_id: number;
  season: number;
  week: number;
  reasons: string[];
};

type MatchupGradeRow = {
  team: string;
  season: number;
  week: number;
  position: string;
  grade: string;
  rank: number;
  yards_per_target: number;
  yards_per_rush: number;
  pass_td_rate: number;
  rush_td_rate: number;
  explosive_rate: number;
  pressure_rate: number;
};

type SchedulePreviewRow = {
  week: number;
  opponent: string;
  home_away: "home" | "away";
  grade: string;
};

type TrendPoint = {
  week: number;
  label: string;
  points: number;
};

type PlayerOption = {
  id: number;
  name: string;
  position: string;
  school: string;
};

type StatsTab = "offense" | "defense" | "advanced" | "injuries" | "standings";
type Mode = "teams" | "players";
type PlayerComparisonTab = "overview" | "advanced" | "matchup" | "trends" | "projections";

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
const POWER4_TEAM_SET = new Set(Object.values(POWER4_TEAMS_BY_CONFERENCE).flat());

const formatLabel = (value: string) =>
  value
    .replace(/\./g, " · ")
    .replace(/_/g, " ")
    .replace(/\[(\d+)\]/g, " $1")
    .replace(/\b\w/g, (char) => char.toUpperCase());

const renderValue = (value: unknown) => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return Number.isInteger(value) ? value : value.toFixed(3);
  if (typeof value === "boolean") return value ? "Yes" : "No";
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
  if (!keys.length) return [[prefix || "value", "{}"]];
  return keys.flatMap((key) => flattenEntries(obj[key], prefix ? `${prefix}.${key}` : key));
};

const difficultyClass = (grade: string) => {
  if (grade === "A+" || grade === "A") return "text-emerald-400";
  if (grade === "B") return "text-lime-300";
  if (grade === "C") return "text-amber-300";
  if (grade === "D") return "text-orange-400";
  return "text-red-400";
};

const difficultyChipClass = (grade: string) => {
  if (grade === "A+" || grade === "A") return "bg-emerald-500/15 text-emerald-300 border-emerald-400/40";
  if (grade === "B") return "bg-lime-500/15 text-lime-300 border-lime-400/40";
  if (grade === "C") return "bg-amber-500/15 text-amber-300 border-amber-400/40";
  if (grade === "D") return "bg-orange-500/15 text-orange-300 border-orange-400/40";
  return "bg-red-500/15 text-red-300 border-red-400/40";
};

const difficultyScore = (grade: string) => {
  if (grade === "A+") return 92;
  if (grade === "A") return 84;
  if (grade === "B") return 70;
  if (grade === "C") return 55;
  if (grade === "D") return 38;
  return 20;
};

const matchupDot = (grade: string) => {
  if (grade === "A+" || grade === "A") return "🟢";
  if (grade === "B" || grade === "C") return "🟡";
  return "🔴";
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const safeNum = (value: number | undefined | null) => value ?? 0;

const calculateConsistency = (trend: TrendPoint[]) => {
  if (!trend.length) return 60;
  const values = trend.map((row) => row.points);
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  if (mean <= 0) return 50;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const stdDev = Math.sqrt(variance);
  return Math.round(clamp((1 - stdDev / Math.max(mean, 1)) * 100, 30, 95));
};

const projectionConfidence = (
  projection: ProjectionRead | null,
  side: CompareSide | null,
  consistency: number,
  injuryPenalty = 0
) => {
  if (!projection || !side) return 55;
  const boom = safeNum(projection.boom_prob);
  const bust = safeNum(projection.bust_prob);
  const matchup = difficultyScore(side.projected_matchup_difficulty);
  const base = 0.45 * consistency + 0.25 * matchup + 0.2 * (100 - bust * 100) + 0.1 * (boom * 100);
  return Math.round(clamp(base - injuryPenalty, 25, 96));
};

const tradeValue = (
  projection: ProjectionRead | null,
  side: CompareSide | null,
  consistency: number,
  confidence: number
) => {
  if (!projection || !side) return 40;
  const points = safeNum(projection.fantasy_points);
  const scarcityMap: Record<string, number> = { RB: 12, WR: 10, TE: 8, QB: 4, K: 1 };
  const scarcity = scarcityMap[side.position.toUpperCase()] ?? 3;
  const ceilingBoost = clamp((safeNum(projection.ceiling) - points) * 1.5, 0, 12);
  const bustPenalty = safeNum(projection.bust_prob) * 15;
  return Math.round(clamp(points * 2.1 + scarcity + ceilingBoost + confidence * 0.3 + consistency * 0.2 - bustPenalty, 1, 100));
};

const chartStat = (metricA: number, metricB: number) => {
  const maxValue = Math.max(metricA, metricB, 0.01);
  return {
    a: Math.round((metricA / maxValue) * 100),
    b: Math.round((metricB / maxValue) * 100),
  };
};

export default function Stats() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>(location.pathname === "/stats/players" ? "players" : "teams");
  const [season, setSeason] = useState<number>(2025);
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

  const [playerOptions, setPlayerOptions] = useState<PlayerOption[]>([]);
  const [compareA, setCompareA] = useState<string>("");
  const [compareB, setCompareB] = useState<string>("");
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [openPlayerA, setOpenPlayerA] = useState(false);
  const [openPlayerB, setOpenPlayerB] = useState(false);
  const [comparisonTab, setComparisonTab] = useState<PlayerComparisonTab>("overview");
  const [projectionWeek, setProjectionWeek] = useState<number>(1);
  const [projectionA, setProjectionA] = useState<ProjectionRead | null>(null);
  const [projectionB, setProjectionB] = useState<ProjectionRead | null>(null);
  const [explanationsA, setExplanationsA] = useState<string[]>([]);
  const [explanationsB, setExplanationsB] = useState<string[]>([]);
  const [matchupA, setMatchupA] = useState<MatchupGradeRow | null>(null);
  const [matchupB, setMatchupB] = useState<MatchupGradeRow | null>(null);
  const [scheduleA, setScheduleA] = useState<SchedulePreviewRow[]>([]);
  const [scheduleB, setScheduleB] = useState<SchedulePreviewRow[]>([]);
  const [trendA, setTrendA] = useState<TrendPoint[]>([]);
  const [trendB, setTrendB] = useState<TrendPoint[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);

  useEffect(() => {
    if (location.pathname === "/stats/players") {
      setMode("players");
      return;
    }
    if (mode === "players") {
      setMode("teams");
    }
  }, [location.pathname, mode]);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingTeams(true);
    apiGet<{ data: TeamSummary[] }>("/stats/teams", { season, conference }, controller.signal)
      .then((payload) => {
        const apiRows = payload?.data ?? [];
        setTeams(apiRows);
        setTeamsError(null);
        if (!selectedTeam || !apiRows.some((row) => row.team === selectedTeam)) {
          setSelectedTeam(apiRows[0]?.team ?? "");
        }
      })
      .catch(() => {
        setTeams([]);
        setSelectedTeam("");
        setTeamDetail(null);
        setTeamsError("Unable to load team data from backend.");
      })
      .finally(() => setLoadingTeams(false));
    return () => controller.abort();
  }, [season, conference, selectedTeam]);

  useEffect(() => {
    if (mode !== "teams" || !selectedTeam) return;
    const controller = new AbortController();
    setLoadingDetail(true);
    apiGet<TeamDetail>(`/stats/team/${encodeURIComponent(selectedTeam)}`, { season }, controller.signal)
      .then((payload) => setTeamDetail(payload))
      .catch(() => setTeamDetail(null))
      .finally(() => setLoadingDetail(false));
    return () => controller.abort();
  }, [mode, selectedTeam, season]);

  useEffect(() => {
    if (mode !== "teams") return;
    const controller = new AbortController();
    const standingsConference =
      conference === "ALL" ? teams.find((team) => team.team === selectedTeam)?.conference : conference;
    if (!standingsConference) {
      setStandings([]);
      return;
    }
    apiGet<{ data: TeamStanding[] }>(
      "/stats/standings",
      { season, conference: standingsConference },
      controller.signal
    )
      .then((payload) => setStandings(payload?.data ?? []))
      .catch(() => setStandings([]));
    return () => controller.abort();
  }, [mode, season, conference, selectedTeam, teams]);

  useEffect(() => {
    if (mode !== "teams") return;
    const controller = new AbortController();
    const injuriesConference =
      conference === "ALL" ? teams.find((team) => team.team === selectedTeam)?.conference : conference;
    const params: Record<string, string | number> = { season, week: 1 };
    if (injuriesConference) params.conference = injuriesConference;
    apiGet<{ data: TeamInjury[] }>("/stats/injuries", params, controller.signal)
      .then((payload) => {
        const rows = payload?.data ?? [];
        setInjuries(selectedTeam ? rows.filter((row) => row.team === selectedTeam) : rows);
      })
      .catch(() => setInjuries([]));
    return () => controller.abort();
  }, [mode, season, conference, selectedTeam, teams]);

  useEffect(() => {
    if (mode !== "players") return;
    const controller = new AbortController();
    const loadPlayers = async () => {
      const chunkSize = 500;
      let offset = 0;
      let hasMore = true;
      const collected: PlayerOption[] = [];
      while (hasMore && offset <= 5000) {
        const payload = await apiGet<{ data: Array<{ id: number; name: string; position: string; school: string }> }>(
          "/players",
          { limit: chunkSize, offset },
          controller.signal
        );
        const rows = payload?.data ?? [];
        if (!rows.length) {
          hasMore = false;
          break;
        }
        collected.push(
          ...rows
            .filter((row) => POWER4_TEAM_SET.has(row.school))
            .map((row) => ({
              id: row.id,
              name: row.name,
              position: row.position,
              school: row.school,
            }))
        );
        if (rows.length < chunkSize) {
          hasMore = false;
        }
        offset += rows.length;
      }
      const deduped = new Map<number, PlayerOption>();
      collected.forEach((row) => deduped.set(row.id, row));
      setPlayerOptions(Array.from(deduped.values()).sort((a, b) => a.name.localeCompare(b.name)));
    };
    loadPlayers()
      .catch(() => setPlayerOptions([]));
    return () => controller.abort();
  }, [mode]);

  useEffect(() => {
    if (mode !== "players") return;
    if (!compareA || !compareB || compareA === compareB) {
      setCompareResult(null);
      return;
    }
    setCompareLoading(true);
    apiPost<CompareResponse>("/insights/player-compare", {
      player_a_id: Number(compareA),
      player_b_id: Number(compareB),
      season,
      week: 1,
    })
      .then((payload) => setCompareResult(payload))
      .catch(() => setCompareResult(null))
      .finally(() => setCompareLoading(false));
  }, [mode, compareA, compareB, season]);

  useEffect(() => {
    if (mode !== "players" || !compareResult) {
      setProjectionA(null);
      setProjectionB(null);
      setExplanationsA([]);
      setExplanationsB([]);
      setMatchupA(null);
      setMatchupB(null);
      setScheduleA([]);
      setScheduleB([]);
      setTrendA([]);
      setTrendB([]);
      return;
    }

    const loadSideData = async (side: CompareSide) => {
      const [projection, explanationPayload, schedulePayload] = await Promise.all([
        apiGet<ProjectionRead>(`/projections/${side.player_id}`, { season, week: projectionWeek }),
        apiGet<ProjectionExplanationPayload>(
          `/projections/${side.player_id}/explanations`,
          { season, week: projectionWeek }
        ),
        apiGet<{ data: SchedulePreviewRow[] }>(
          `/schedule/player/${side.player_id}`,
          { season, week: projectionWeek, weeks: 5 }
        ),
      ]);

      const trendWeeks = Array.from({ length: 10 }, (_, idx) => idx + 1);
      const trendResponses = await Promise.all(
        trendWeeks.map((weekValue) =>
          apiGet<ProjectionRead>(`/projections/${side.player_id}`, { season, week: weekValue })
            .then((row) => ({ week: weekValue, points: safeNum(row.fantasy_points) }))
            .catch(() => null)
        )
      );

      const trend = trendResponses
        .filter((row): row is { week: number; points: number } => row !== null)
        .map((row) => ({
          week: row.week,
          label: `W${row.week}`,
          points: Number(row.points.toFixed(2)),
        }));

      const firstOpponent = (schedulePayload?.data ?? [])[0];
      let matchup: MatchupGradeRow | null = null;
      if (firstOpponent) {
        const matchupPayload = await apiGet<{ data: MatchupGradeRow[] }>("/matchups", {
          season,
          week: firstOpponent.week,
          team: firstOpponent.opponent,
          position: side.position.toUpperCase(),
        }).catch(() => ({ data: [] as MatchupGradeRow[] }));
        matchup = matchupPayload.data[0] ?? null;
      }

      return {
        projection,
        explanations: explanationPayload?.reasons ?? [],
        schedule: schedulePayload?.data ?? [],
        trend,
        matchup,
      };
    };

    setDetailsLoading(true);
    Promise.all([loadSideData(compareResult.player_a), loadSideData(compareResult.player_b)])
      .then(([a, b]) => {
        setProjectionA(a.projection);
        setProjectionB(b.projection);
        setExplanationsA(a.explanations);
        setExplanationsB(b.explanations);
        setScheduleA(a.schedule);
        setScheduleB(b.schedule);
        setTrendA(a.trend);
        setTrendB(b.trend);
        setMatchupA(a.matchup);
        setMatchupB(b.matchup);
      })
      .catch(() => {
        setProjectionA(null);
        setProjectionB(null);
        setExplanationsA([]);
        setExplanationsB([]);
        setMatchupA(null);
        setMatchupB(null);
        setScheduleA([]);
        setScheduleB([]);
        setTrendA([]);
        setTrendB([]);
      })
      .finally(() => setDetailsLoading(false));
  }, [mode, compareResult, season, projectionWeek]);

  const changeMode = (nextMode: Mode) => {
    setMode(nextMode);
    if (nextMode === "players") {
      navigate("/stats/players");
      return;
    }
    if (location.pathname === "/stats/players") {
      navigate("/stats");
    }
  };

  const filteredTeams = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return teams;
    return teams.filter((team) => team.team.toLowerCase().includes(q));
  }, [teams, search]);

  const statsRows = useMemo(() => {
    if (!teamDetail) return [];
    if (activeTab === "offense") return flattenEntries(teamDetail.offense);
    if (activeTab === "defense") return flattenEntries(teamDetail.defense);
    if (activeTab === "advanced") return flattenEntries(teamDetail.advanced);
    return [];
  }, [teamDetail, activeTab]);

  const playerAOption = useMemo(
    () => playerOptions.find((row) => String(row.id) === compareA) ?? null,
    [playerOptions, compareA]
  );
  const playerBOption = useMemo(
    () => playerOptions.find((row) => String(row.id) === compareB) ?? null,
    [playerOptions, compareB]
  );

  const consistencyA = useMemo(() => calculateConsistency(trendA), [trendA]);
  const consistencyB = useMemo(() => calculateConsistency(trendB), [trendB]);

  const confidenceA = useMemo(
    () =>
      projectionConfidence(
        projectionA,
        compareResult?.player_a ?? null,
        consistencyA,
        safeNum(projectionA?.bust_prob) > 0.5 ? 8 : 0
      ),
    [projectionA, compareResult?.player_a, consistencyA]
  );
  const confidenceB = useMemo(
    () =>
      projectionConfidence(
        projectionB,
        compareResult?.player_b ?? null,
        consistencyB,
        safeNum(projectionB?.bust_prob) > 0.5 ? 8 : 0
      ),
    [projectionB, compareResult?.player_b, consistencyB]
  );

  const tradeValueA = useMemo(
    () => tradeValue(projectionA, compareResult?.player_a ?? null, consistencyA, confidenceA),
    [projectionA, compareResult?.player_a, consistencyA, confidenceA]
  );
  const tradeValueB = useMemo(
    () => tradeValue(projectionB, compareResult?.player_b ?? null, consistencyB, confidenceB),
    [projectionB, compareResult?.player_b, consistencyB, confidenceB]
  );

  const startRecommendation = useMemo(() => {
    if (!compareResult || !projectionA || !projectionB) return null;
    const scoreA =
      safeNum(projectionA.fantasy_points) * 0.55 +
      safeNum(projectionA.ceiling) * 0.12 +
      confidenceA * 0.18 +
      difficultyScore(compareResult.player_a.projected_matchup_difficulty) * 0.15;
    const scoreB =
      safeNum(projectionB.fantasy_points) * 0.55 +
      safeNum(projectionB.ceiling) * 0.12 +
      confidenceB * 0.18 +
      difficultyScore(compareResult.player_b.projected_matchup_difficulty) * 0.15;
    const recommended = scoreA >= scoreB ? "A" : "B";
    const confidence = Math.round(clamp(Math.abs(scoreA - scoreB) * 1.8 + 52, 52, 95));
    return {
      recommended,
      confidence,
      reasonA: [
        `Projected ${safeNum(projectionA.fantasy_points).toFixed(1)} pts with ${safeNum(projectionA.floor).toFixed(1)} floor`,
        `Matchup grade ${compareResult.player_a.projected_matchup_difficulty} (${difficultyScore(compareResult.player_a.projected_matchup_difficulty)} matchup score)`,
        `Usage profile: ${safeNum(projectionA.targets + projectionA.rush_attempts).toFixed(1)} opportunities`,
      ],
      reasonB: [
        `Projected ${safeNum(projectionB.fantasy_points).toFixed(1)} pts with ${safeNum(projectionB.floor).toFixed(1)} floor`,
        `Matchup grade ${compareResult.player_b.projected_matchup_difficulty} (${difficultyScore(compareResult.player_b.projected_matchup_difficulty)} matchup score)`,
        `Usage profile: ${safeNum(projectionB.targets + projectionB.rush_attempts).toFixed(1)} opportunities`,
      ],
    };
  }, [compareResult, projectionA, projectionB, confidenceA, confidenceB]);

  const radarData = useMemo(() => {
    if (!compareResult || !projectionA || !projectionB) return [];
    const bigPlayA = clamp((safeNum(projectionA.ceiling) - safeNum(projectionA.fantasy_points)) * 5, 5, 100);
    const bigPlayB = clamp((safeNum(projectionB.ceiling) - safeNum(projectionB.fantasy_points)) * 5, 5, 100);
    const ppg = chartStat(compareResult.player_a.fantasy_ppg, compareResult.player_b.fantasy_ppg);
    const redZone = chartStat(compareResult.player_a.red_zone_touches, compareResult.player_b.red_zone_touches);
    const usage = chartStat(compareResult.player_a.usage_rate, compareResult.player_b.usage_rate);
    const consistency = chartStat(consistencyA, consistencyB);
    const bigPlay = chartStat(bigPlayA, bigPlayB);
    const confidence = chartStat(confidenceA, confidenceB);
    return [
      { metric: "Fantasy PPG", a: ppg.a, b: ppg.b },
      { metric: "Red Zone", a: redZone.a, b: redZone.b },
      { metric: "Usage", a: usage.a, b: usage.b },
      { metric: "Big Play", a: bigPlay.a, b: bigPlay.b },
      { metric: "Consistency", a: consistency.a, b: consistency.b },
      { metric: "Confidence", a: confidence.a, b: confidence.b },
    ];
  }, [compareResult, projectionA, projectionB, consistencyA, consistencyB, confidenceA, confidenceB]);

  const trendData = useMemo(() => {
    const weekSet = new Set<number>();
    trendA.forEach((row) => weekSet.add(row.week));
    trendB.forEach((row) => weekSet.add(row.week));
    return Array.from(weekSet)
      .sort((a, b) => a - b)
      .map((weekValue) => ({
        week: `W${weekValue}`,
        playerA: trendA.find((row) => row.week === weekValue)?.points ?? null,
        playerB: trendB.find((row) => row.week === weekValue)?.points ?? null,
      }));
  }, [trendA, trendB]);

  const similarPlayersA = useMemo(() => {
    if (!playerAOption) return [];
    return playerOptions
      .filter((row) => row.id !== playerAOption.id && row.position === playerAOption.position)
      .slice(0, 3);
  }, [playerOptions, playerAOption]);
  const similarPlayersB = useMemo(() => {
    if (!playerBOption) return [];
    return playerOptions
      .filter((row) => row.id !== playerBOption.id && row.position === playerBOption.position)
      .slice(0, 3);
  }, [playerOptions, playerBOption]);

  const gameScriptA = useMemo(() => {
    if (!projectionA || !compareResult) return "Insufficient game-script signal.";
    const expectedRush = safeNum(projectionA.expected_rush_per_play);
    const matchup = difficultyScore(compareResult.player_a.projected_matchup_difficulty);
    if (expectedRush >= 0.5 && matchup >= 65) return "Positive script likely: elevated rushing volume expected.";
    if (expectedRush < 0.38 && matchup >= 65) return "Pass-heavy script likely: lean into passing upside.";
    if (matchup <= 40) return "Tough script expected: lower efficiency against stronger defense.";
    return "Neutral script expected: projection driven by baseline role.";
  }, [projectionA, compareResult]);
  const gameScriptB = useMemo(() => {
    if (!projectionB || !compareResult) return "Insufficient game-script signal.";
    const expectedRush = safeNum(projectionB.expected_rush_per_play);
    const matchup = difficultyScore(compareResult.player_b.projected_matchup_difficulty);
    if (expectedRush >= 0.5 && matchup >= 65) return "Positive script likely: elevated rushing volume expected.";
    if (expectedRush < 0.38 && matchup >= 65) return "Pass-heavy script likely: lean into passing upside.";
    if (matchup <= 40) return "Tough script expected: lower efficiency against stronger defense.";
    return "Neutral script expected: projection driven by baseline role.";
  }, [projectionB, compareResult]);

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-in fade-in duration-700">
      <div className="space-y-2">
        <h1 className="text-5xl font-black italic uppercase tracking-tight text-foreground">Stats</h1>
        <p className="text-[11px] font-black tracking-[0.3em] text-primary uppercase">
          Power 4 Team Research Center
        </p>
      </div>

      <Card className="bg-card/40 backdrop-blur-md border border-white/10 rounded-[2.5rem] p-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="space-y-2" id="stats-mode-toggle">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">View</p>
            <div className="flex gap-2">
              <Button
                className={cn(
                  "h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]",
                  mode === "teams"
                    ? "bg-primary text-primary-foreground"
                    : "bg-white/5 border border-white/10 text-muted-foreground"
                )}
                onClick={() => changeMode("teams")}
              >
                Teams
              </Button>
              <Button
                className={cn(
                  "h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]",
                  mode === "players"
                    ? "bg-primary text-primary-foreground"
                    : "bg-white/5 border border-white/10 text-muted-foreground"
                )}
                onClick={() => changeMode("players")}
              >
                Players
              </Button>
            </div>
          </div>

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
                  className={cn(
                    "h-10 px-4 rounded-xl text-[10px] font-black uppercase tracking-[0.2em]",
                    conference === value
                      ? "bg-primary text-primary-foreground"
                      : "bg-white/5 border border-white/10 text-muted-foreground"
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

      {mode === "teams" ? (
        <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-6">
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
                          <tr key={row.team} className={cn(selectedTeam === row.team && "bg-primary/10")}>
                            <td className="px-6 py-3 text-[11px] font-black text-foreground">{row.conference_rank ?? "-"}</td>
                            <td className="px-6 py-3 text-[11px] font-black uppercase tracking-[0.12em] text-foreground">{row.team}</td>
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
      ) : (
        <Card className="bg-card/40 backdrop-blur-md border border-white/10 rounded-[2.5rem] overflow-hidden">
          <CardHeader className="border-b border-white/10 space-y-4">
            <CardTitle className="text-[11px] font-black tracking-[0.28em] uppercase text-primary flex items-center gap-2">
              <UserRoundSearch className="w-4 h-4" />
              Player Comparison Tool
            </CardTitle>
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_1fr_170px] gap-4">
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Player A</p>
                <Popover open={openPlayerA} onOpenChange={setOpenPlayerA}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={openPlayerA}
                      className="h-12 w-full justify-between bg-white/5 border-white/10 rounded-xl text-[11px] font-bold hover:bg-white/10 hover:text-foreground"
                    >
                      {playerAOption
                        ? `${playerAOption.name} · ${playerAOption.school} · ${playerAOption.position}`
                        : "Search Power 4 Player A"}
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-60" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[--radix-popover-trigger-width] p-0 border-white/10 bg-[#0A0C10]">
                    <Command className="bg-[#0A0C10]">
                      <CommandInput placeholder="Search player A in Power 4..." className="text-[11px] font-semibold" />
                      <CommandList className="max-h-[320px]">
                        <CommandEmpty>No Power 4 player found.</CommandEmpty>
                        <CommandGroup>
                          {playerOptions.map((player) => (
                            <CommandItem
                              key={player.id}
                              value={`${player.name} ${player.school} ${player.position}`}
                              onSelect={() => {
                                setCompareA(String(player.id));
                                setOpenPlayerA(false);
                              }}
                              className="text-[11px] font-semibold"
                            >
                              <Check className={cn("mr-2 h-4 w-4", compareA === String(player.id) ? "opacity-100" : "opacity-0")} />
                              <span>
                                {player.name} · {player.school} · {player.position}
                              </span>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Player B</p>
                <Popover open={openPlayerB} onOpenChange={setOpenPlayerB}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={openPlayerB}
                      className="h-12 w-full justify-between bg-white/5 border-white/10 rounded-xl text-[11px] font-bold hover:bg-white/10 hover:text-foreground"
                    >
                      {playerBOption
                        ? `${playerBOption.name} · ${playerBOption.school} · ${playerBOption.position}`
                        : "Search Power 4 Player B"}
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-60" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[--radix-popover-trigger-width] p-0 border-white/10 bg-[#0A0C10]">
                    <Command className="bg-[#0A0C10]">
                      <CommandInput placeholder="Search player B in Power 4..." className="text-[11px] font-semibold" />
                      <CommandList className="max-h-[320px]">
                        <CommandEmpty>No Power 4 player found.</CommandEmpty>
                        <CommandGroup>
                          {playerOptions.map((player) => (
                            <CommandItem
                              key={player.id}
                              value={`${player.name} ${player.school} ${player.position}`}
                              onSelect={() => {
                                setCompareB(String(player.id));
                                setOpenPlayerB(false);
                              }}
                              className="text-[11px] font-semibold"
                            >
                              <Check className={cn("mr-2 h-4 w-4", compareB === String(player.id) ? "opacity-100" : "opacity-0")} />
                              <span>
                                {player.name} · {player.school} · {player.position}
                              </span>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>
              <div className="space-y-2">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Week</p>
                <Select value={String(projectionWeek)} onValueChange={(value) => setProjectionWeek(Number(value))}>
                  <SelectTrigger className="h-12 bg-white/5 border-white/10 rounded-xl text-[11px] font-bold">
                    <SelectValue placeholder="Week" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0A0C10] border-border rounded-2xl max-h-[320px]">
                    {Array.from({ length: 15 }, (_, idx) => idx + 1).map((weekValue) => (
                      <SelectItem key={weekValue} value={String(weekValue)}>
                        Week {weekValue}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-6">
            {compareLoading && (
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Building comparison...
              </p>
            )}
            {detailsLoading && compareResult && (
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                Loading trends, matchup data, and weekly projections...
              </p>
            )}

            {!compareResult && !compareLoading && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-[11px] font-bold text-muted-foreground/75">
                Select two players to unlock side-by-side decision intelligence: weekly projections, matchup grades,
                trend momentum, floor/ceiling, and start/sit recommendation.
              </div>
            )}

            {compareResult && (
              <div className="space-y-5">
                <div className="grid grid-cols-1 xl:grid-cols-[1fr_1fr_1.1fr] gap-4">
                  {[{ side: compareResult.player_a, projection: projectionA, confidence: confidenceA, tradeValue: tradeValueA }, { side: compareResult.player_b, projection: projectionB, confidence: confidenceB, tradeValue: tradeValueB }].map(
                    ({ side, projection, confidence, tradeValue }) => (
                      <div key={side.player_id} className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[11px] font-black uppercase tracking-[0.16em] text-foreground">
                            {side.player_name}
                          </p>
                          <span className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                            {side.position}
                          </span>
                        </div>
                        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground/70">{side.school}</p>
                        <div className="grid grid-cols-2 gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground/80">
                          <span>Proj: {safeNum(projection?.fantasy_points).toFixed(1)}</span>
                          <span>PPG: {side.fantasy_ppg.toFixed(1)}</span>
                          <span>Floor: {safeNum(projection?.floor).toFixed(1)}</span>
                          <span>Ceiling: {safeNum(projection?.ceiling).toFixed(1)}</span>
                          <span className={difficultyClass(side.projected_matchup_difficulty)}>Matchup: {side.projected_matchup_difficulty}</span>
                          <span>Trade: {tradeValue}</span>
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/70">
                            <span>Projection Confidence</span>
                            <span>{confidence}%</span>
                          </div>
                          <Progress value={confidence} className="h-2 bg-white/10" />
                        </div>
                      </div>
                    )
                  )}

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Gauge className="w-4 h-4 text-primary" />
                      <p className="text-[10px] font-black tracking-[0.22em] uppercase text-primary">
                        Start/Sit Recommendation
                      </p>
                    </div>
                    {startRecommendation ? (
                      <>
                        <p className="text-2xl font-black italic uppercase tracking-tight text-foreground">
                          Start{" "}
                          {startRecommendation.recommended === "A"
                            ? compareResult.player_a.player_name
                            : compareResult.player_b.player_name}
                        </p>
                        <p className="text-[11px] font-bold text-muted-foreground/80">
                          Confidence:{" "}
                          <span className="text-primary font-black">{startRecommendation.confidence}%</span>
                        </p>
                        <ul className="space-y-1">
                          {(startRecommendation.recommended === "A"
                            ? startRecommendation.reasonA
                            : startRecommendation.reasonB
                          ).slice(0, 3).map((reason, idx) => (
                            <li key={idx} className="text-[10px] font-semibold text-muted-foreground/80">
                              • {reason}
                            </li>
                          ))}
                        </ul>
                      </>
                    ) : (
                      <p className="text-[10px] font-semibold text-muted-foreground/70">
                        Compare two active players to generate recommendation.
                      </p>
                    )}
                  </div>
                </div>

                <Tabs value={comparisonTab} onValueChange={(value) => setComparisonTab(value as PlayerComparisonTab)}>
                  <TabsList className="bg-white/5 border border-white/10 rounded-xl p-1 h-auto flex flex-wrap gap-1">
                    {[
                      { key: "overview", label: "Overview", icon: Scale },
                      { key: "advanced", label: "Advanced Stats", icon: BarChart2 },
                      { key: "matchup", label: "Matchup", icon: Target },
                      { key: "trends", label: "Trends", icon: TrendingUp },
                      { key: "projections", label: "Projections", icon: Waves },
                    ].map((tab) => (
                      <TabsTrigger
                        key={tab.key}
                        value={tab.key}
                        className="rounded-lg text-[10px] font-black uppercase tracking-[0.18em] px-3 py-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
                      >
                        <tab.icon className="w-3.5 h-3.5 mr-1.5" />
                        {tab.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  <TabsContent value="overview" className="space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-3">
                        This Week Projection (Side-by-Side)
                      </p>
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[700px]">
                          <thead className="border-b border-white/10">
                            <tr>
                              <th className="px-3 py-2 text-left text-[10px] font-black uppercase tracking-[0.15em] text-muted-foreground/60">Metric</th>
                              <th className="px-3 py-2 text-left text-[10px] font-black uppercase tracking-[0.15em] text-muted-foreground/60">{compareResult.player_a.player_name}</th>
                              <th className="px-3 py-2 text-left text-[10px] font-black uppercase tracking-[0.15em] text-muted-foreground/60">{compareResult.player_b.player_name}</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/10">
                            {[
                              ["Projected Points", safeNum(projectionA?.fantasy_points).toFixed(1), safeNum(projectionB?.fantasy_points).toFixed(1)],
                              ["Floor", safeNum(projectionA?.floor).toFixed(1), safeNum(projectionB?.floor).toFixed(1)],
                              ["Ceiling", safeNum(projectionA?.ceiling).toFixed(1), safeNum(projectionB?.ceiling).toFixed(1)],
                              ["Boom %", `${Math.round(safeNum(projectionA?.boom_prob) * 100)}%`, `${Math.round(safeNum(projectionB?.boom_prob) * 100)}%`],
                              ["Bust %", `${Math.round(safeNum(projectionA?.bust_prob) * 100)}%`, `${Math.round(safeNum(projectionB?.bust_prob) * 100)}%`],
                              ["Consistency", `${consistencyA}%`, `${consistencyB}%`],
                            ].map(([label, aValue, bValue]) => (
                              <tr key={label}>
                                <td className="px-3 py-2 text-[11px] font-black uppercase tracking-[0.12em] text-foreground">{label}</td>
                                <td className="px-3 py-2 text-[11px] font-bold text-muted-foreground/85">{aValue}</td>
                                <td className="px-3 py-2 text-[11px] font-bold text-muted-foreground/85">{bValue}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="advanced" className="space-y-4">
                    <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-4">
                      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-3">
                          Attribute Radar
                        </p>
                        <div className="h-[300px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <RadarChart data={radarData}>
                              <PolarGrid />
                              <PolarAngleAxis dataKey="metric" tick={{ fill: "rgba(210,220,236,0.7)", fontSize: 10, fontWeight: 700 }} />
                              <Radar
                                name={compareResult.player_a.player_name}
                                dataKey="a"
                                stroke="#60A5FA"
                                fill="#60A5FA"
                                fillOpacity={0.35}
                              />
                              <Radar
                                name={compareResult.player_b.player_name}
                                dataKey="b"
                                stroke="#34D399"
                                fill="#34D399"
                                fillOpacity={0.25}
                              />
                              <Legend />
                              <RechartsTooltip />
                            </RadarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      <div className="space-y-4">
                        {[{
                          label: compareResult.player_a.player_name,
                          side: compareResult.player_a,
                          projection: projectionA,
                          similar: similarPlayersA,
                        }, {
                          label: compareResult.player_b.player_name,
                          side: compareResult.player_b,
                          projection: projectionB,
                          similar: similarPlayersB,
                        }].map((block) => (
                          <div key={block.label} className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-2">
                            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">{block.label}</p>
                            <div className="grid grid-cols-2 gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground/80">
                              <span>Usage: {block.side.usage_rate.toFixed(1)}</span>
                              <span>Red Zone: {block.side.red_zone_touches.toFixed(1)}</span>
                              <span>Targets: {safeNum(block.projection?.targets).toFixed(1)}</span>
                              <span>Rush Att: {safeNum(block.projection?.rush_attempts).toFixed(1)}</span>
                              <span>Expected Plays: {safeNum(block.projection?.expected_plays).toFixed(1)}</span>
                              <span>QBR: {block.projection?.qb_rating ? block.projection.qb_rating.toFixed(1) : "-"}</span>
                            </div>
                            <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/60">
                              Similar Players
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {block.similar.length === 0 ? (
                                <span className="text-[10px] text-muted-foreground/70">No comps found.</span>
                              ) : (
                                block.similar.map((player) => (
                                  <span
                                    key={player.id}
                                    className="inline-flex items-center rounded-full px-2.5 py-1 text-[9px] font-black uppercase tracking-[0.14em] border border-white/15 bg-white/5 text-muted-foreground/80"
                                  >
                                    {player.name}
                                  </span>
                                ))
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="matchup" className="space-y-4">
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                      {[{
                        side: compareResult.player_a,
                        matchup: matchupA,
                        schedule: scheduleA,
                        script: gameScriptA,
                      }, {
                        side: compareResult.player_b,
                        matchup: matchupB,
                        schedule: scheduleB,
                        script: gameScriptB,
                      }].map((block) => (
                        <div key={block.side.player_id} className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                              {block.side.player_name}
                            </p>
                            <span className={cn("rounded-full border px-2 py-1 text-[9px] font-black uppercase tracking-[0.15em]", difficultyChipClass(block.side.projected_matchup_difficulty))}>
                              Matchup {block.side.projected_matchup_difficulty}
                            </span>
                          </div>
                          {block.matchup ? (
                            <div className="grid grid-cols-2 gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground/80">
                              <span>Opponent Rank: #{block.matchup.rank}</span>
                              <span>Yds/Target: {block.matchup.yards_per_target.toFixed(2)}</span>
                              <span>Yds/Rush: {block.matchup.yards_per_rush.toFixed(2)}</span>
                              <span>Pressure: {(block.matchup.pressure_rate * 100).toFixed(1)}%</span>
                              <span>Pass TD Rate: {(block.matchup.pass_td_rate * 100).toFixed(1)}%</span>
                              <span>Rush TD Rate: {(block.matchup.rush_td_rate * 100).toFixed(1)}%</span>
                            </div>
                          ) : (
                            <p className="text-[10px] font-semibold text-muted-foreground/70">No detailed matchup row yet for this week.</p>
                          )}
                          <div className="space-y-1">
                            <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/60">
                              Strength of Schedule (Next 5)
                            </p>
                            {block.schedule.length === 0 ? (
                              <p className="text-[10px] font-semibold text-muted-foreground/70">No upcoming games found.</p>
                            ) : (
                              <ul className="space-y-1">
                                {block.schedule.map((game) => (
                                  <li key={`${block.side.player_id}-${game.week}`} className="text-[10px] font-semibold text-muted-foreground/85">
                                    {matchupDot(game.grade)} Week {game.week} {game.home_away === "home" ? "vs" : "@"} {game.opponent} ({game.grade})
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                          <p className="text-[10px] font-semibold text-muted-foreground/75">Game Script: {block.script}</p>
                        </div>
                      ))}
                    </div>
                  </TabsContent>

                  <TabsContent value="trends" className="space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-3">
                        Fantasy Points Trend (Last Available Weeks)
                      </p>
                      <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={trendData}>
                            <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                            <XAxis dataKey="week" tick={{ fill: "rgba(210,220,236,0.7)", fontSize: 10 }} />
                            <YAxis tick={{ fill: "rgba(210,220,236,0.7)", fontSize: 10 }} />
                            <RechartsTooltip />
                            <Legend />
                            <Line type="monotone" dataKey="playerA" name={compareResult.player_a.player_name} stroke="#60A5FA" strokeWidth={2.5} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="playerB" name={compareResult.player_b.player_name} stroke="#34D399" strokeWidth={2.5} dot={{ r: 3 }} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-2">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">{compareResult.player_a.player_name}</p>
                        <p className="text-[11px] font-bold text-muted-foreground/80">Consistency: {consistencyA}%</p>
                        <p className="text-[11px] font-bold text-muted-foreground/80">Ceiling: {safeNum(projectionA?.ceiling).toFixed(1)} · Floor: {safeNum(projectionA?.floor).toFixed(1)}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-2">
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">{compareResult.player_b.player_name}</p>
                        <p className="text-[11px] font-bold text-muted-foreground/80">Consistency: {consistencyB}%</p>
                        <p className="text-[11px] font-bold text-muted-foreground/80">Ceiling: {safeNum(projectionB?.ceiling).toFixed(1)} · Floor: {safeNum(projectionB?.floor).toFixed(1)}</p>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="projections" className="space-y-4">
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                      {[{
                        side: compareResult.player_a,
                        projection: projectionA,
                        reasons: explanationsA,
                        confidence: confidenceA,
                      }, {
                        side: compareResult.player_b,
                        projection: projectionB,
                        reasons: explanationsB,
                        confidence: confidenceB,
                      }].map((block) => (
                        <div key={block.side.player_id} className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-3">
                          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">{block.side.player_name}</p>
                          <div className="grid grid-cols-2 gap-2 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground/80">
                            <span>Pass Yds: {safeNum(block.projection?.pass_yards).toFixed(1)}</span>
                            <span>Rush Yds: {safeNum(block.projection?.rush_yards).toFixed(1)}</span>
                            <span>Rec Yds: {safeNum(block.projection?.rec_yards).toFixed(1)}</span>
                            <span>Receptions: {safeNum(block.projection?.receptions).toFixed(1)}</span>
                            <span>Pass TD: {safeNum(block.projection?.pass_tds).toFixed(1)}</span>
                            <span>Rush TD: {safeNum(block.projection?.rush_tds).toFixed(1)}</span>
                            <span>Rec TD: {safeNum(block.projection?.rec_tds).toFixed(1)}</span>
                            <span>INT: {safeNum(block.projection?.interceptions).toFixed(1)}</span>
                          </div>
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/70">
                              <span>Projection Confidence</span>
                              <span>{block.confidence}%</span>
                            </div>
                            <Progress value={block.confidence} className="h-2 bg-white/10" />
                          </div>
                          <div className="space-y-1">
                            <p className="text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/60">
                              Projection Drivers
                            </p>
                            {(block.reasons.length ? block.reasons : ["No explanation rows yet."])
                              .slice(0, 3)
                              .map((reason, idx) => (
                                <p key={idx} className="text-[10px] font-semibold text-muted-foreground/80">
                                  • {reason}
                                </p>
                              ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
