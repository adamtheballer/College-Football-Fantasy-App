import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertCircle, ArrowLeft, Clock3, HeartPulse, Loader2, Newspaper, ShieldAlert, X } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useDraftQueue,
  useDraftQueueAdd,
  useDraftQueueClear,
  useDraftQueueRemove,
  useDraftPick,
  useDraftPracticeSetup,
  useDraftRoom,
  useDraftRoomRealtime,
  useDraftSheetSync,
} from "@/hooks/use-draft";
import { useActiveLeagueId } from "@/hooks/use-active-league";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { usePlayerSeasonSummary, usePlayers } from "@/hooks/use-players";
import { ApiError } from "@/lib/api";
import type { Player } from "@/types/player";

const DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1NMP3EJSMbdRd7HDA0t7TwxzJ9DM_bUynLoRCgE6Ml74/edit?gid=0#gid=0";
const DEFAULT_SHEET_ID = "1NMP3EJSMbdRd7HDA0t7TwxzJ9DM_bUynLoRCgE6Ml74";
const DEFAULT_SHEET_TABS = ["BIG10", "ACC", "SEC", "BIG12"];
const MIN_EXPECTED_SHEET_PLAYERS = 700;
const ROSTER_SLOT_LAYOUT = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "K", "BENCH1", "BENCH2", "BENCH3", "BENCH4", "BENCH5", "IR"] as const;
const REQUIRED_PROJECTION_STAT_KEYS = [
  "comp",
  "attempts",
  "pass_yds",
  "pass_tds",
  "ints",
  "rush_yds",
  "rush_tds",
  "receptions",
  "rec_yds",
  "rec_tds",
  "fg",
  "xp",
] as const;

const formatApiError = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Sign in again to enter the draft room.";
    if (error.status === 403) return "You do not have access to this draft room.";
    if (error.status === 404) return "This draft room does not exist yet.";
    return error.message || fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

type DraftBoardPlayer = Player & {
  draftRank: number;
  adpRank: number;
  projectedStandardPoints: number;
};

type DraftSortMode = "projection_desc" | "adp_asc" | "position_asc";
type DraftStatRow = { key: string; label: string; value: number };

const positionPillClass: Record<string, string> = {
  QB: "border-blue-300/40 bg-blue-500/15 text-blue-100",
  RB: "border-emerald-300/40 bg-emerald-500/15 text-emerald-100",
  WR: "border-violet-300/40 bg-violet-500/15 text-violet-100",
  TE: "border-amber-300/40 bg-amber-500/15 text-amber-100",
  K: "border-slate-300/40 bg-slate-400/15 text-slate-100",
};

const positionDotClass: Record<string, string> = {
  QB: "bg-blue-300",
  RB: "bg-emerald-300",
  WR: "bg-violet-300",
  TE: "bg-amber-300",
  K: "bg-slate-300",
};

const pickAuraClassByPosition: Record<string, string> = {
  QB: "border-blue-300/45 bg-blue-500/16 shadow-[0_0_16px_rgba(96,165,250,0.35)]",
  RB: "border-emerald-300/45 bg-emerald-500/14 shadow-[0_0_16px_rgba(74,222,128,0.32)]",
  WR: "border-violet-300/45 bg-violet-500/14 shadow-[0_0_16px_rgba(196,181,253,0.34)]",
  TE: "border-amber-300/45 bg-amber-500/14 shadow-[0_0_16px_rgba(251,191,36,0.3)]",
  K: "border-slate-300/45 bg-slate-500/14 shadow-[0_0_14px_rgba(203,213,225,0.24)]",
};

const formatProjection = (value: number) => {
  if (!Number.isFinite(value)) return "0.0";
  return value.toFixed(1);
};

const formatProjectionCardNumber = (value: number) => {
  if (!Number.isFinite(value)) return "0";
  const rounded = Math.round(value * 10) / 10;
  if (Number.isInteger(rounded)) return String(Math.trunc(rounded));
  return rounded.toFixed(1);
};

const asFiniteNumber = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const clampTimerSeconds = (value: unknown, fallback = 90): number => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.round(parsed));
};

type SchoolPalette = {
  primary: string;
  secondary: string;
};

const SCHOOL_COLOR_PALETTES: Record<string, SchoolPalette> = {
  ALABAMA: { primary: "#9E1B32", secondary: "#FFFFFF" },
  ARIZONA: { primary: "#CC0033", secondary: "#003366" },
  "ARIZONA STATE": { primary: "#8C1D40", secondary: "#FFC627" },
  ARKANSAS: { primary: "#9D2235", secondary: "#FFFFFF" },
  AUBURN: { primary: "#0C2340", secondary: "#E87722" },
  BAYLOR: { primary: "#154734", secondary: "#FFB81C" },
  "BOSTON COLLEGE": { primary: "#98002E", secondary: "#BC9B6A" },
  BYU: { primary: "#002E5D", secondary: "#A5ACAF" },
  CAL: { primary: "#003262", secondary: "#FDB515" },
  CALIFORNIA: { primary: "#003262", secondary: "#FDB515" },
  CINCINNATI: { primary: "#E00122", secondary: "#000000" },
  CLEMSON: { primary: "#F56600", secondary: "#522D80" },
  COLORADO: { primary: "#CFB87C", secondary: "#000000" },
  DUKE: { primary: "#003087", secondary: "#FFFFFF" },
  FLORIDA: { primary: "#0021A5", secondary: "#FA4616" },
  "FLORIDA STATE": { primary: "#782F40", secondary: "#CEB888" },
  "GEORGIA TECH": { primary: "#B3A369", secondary: "#003057" },
  GEORGIA: { primary: "#BA0C2F", secondary: "#000000" },
  HOUSTON: { primary: "#C8102E", secondary: "#FFFFFF" },
  ILLINOIS: { primary: "#E84A27", secondary: "#13294B" },
  INDIANA: { primary: "#990000", secondary: "#EEEDEB" },
  IOWA: { primary: "#FFCD00", secondary: "#000000" },
  "IOWA STATE": { primary: "#C8102E", secondary: "#F1BE48" },
  KANSAS: { primary: "#0051BA", secondary: "#E8000D" },
  "KANSAS STATE": { primary: "#512888", secondary: "#D1D1D1" },
  KENTUCKY: { primary: "#0033A0", secondary: "#FFFFFF" },
  LOUISVILLE: { primary: "#AD0000", secondary: "#000000" },
  LSU: { primary: "#461D7C", secondary: "#FDD023" },
  MARYLAND: { primary: "#E03A3E", secondary: "#FFD520" },
  MIAMI: { primary: "#005030", secondary: "#F47321" },
  MICHIGAN: { primary: "#00274C", secondary: "#FFCB05" },
  "MICHIGAN STATE": { primary: "#18453B", secondary: "#FFFFFF" },
  MINNESOTA: { primary: "#7A0019", secondary: "#FFCC33" },
  MISSOURI: { primary: "#000000", secondary: "#F1B82D" },
  "MISSISSIPPI STATE": { primary: "#660000", secondary: "#FFFFFF" },
  NEBRASKA: { primary: "#E41C38", secondary: "#FFFFFF" },
  "NC STATE": { primary: "#CC0000", secondary: "#000000" },
  "NORTH CAROLINA": { primary: "#7BAFD4", secondary: "#13294B" },
  NORTHWESTERN: { primary: "#4E2A84", secondary: "#FFFFFF" },
  "OHIO STATE": { primary: "#BB0000", secondary: "#666666" },
  OKLAHOMA: { primary: "#841617", secondary: "#FDF9D8" },
  "OKLAHOMA STATE": { primary: "#FF7300", secondary: "#000000" },
  "OLE MISS": { primary: "#CE1126", secondary: "#13294B" },
  OREGON: { primary: "#154733", secondary: "#FEE123" },
  "PENN STATE": { primary: "#041E42", secondary: "#FFFFFF" },
  PITTSBURGH: { primary: "#003594", secondary: "#FFB81C" },
  PURDUE: { primary: "#CFB991", secondary: "#000000" },
  RUTGERS: { primary: "#CC0033", secondary: "#5F6A72" },
  SMU: { primary: "#D51309", secondary: "#1E3C9B" },
  "SOUTH CAROLINA": { primary: "#73000A", secondary: "#000000" },
  STANFORD: { primary: "#8C1515", secondary: "#FFFFFF" },
  SYRACUSE: { primary: "#D44500", secondary: "#0C2340" },
  TCU: { primary: "#4D1979", secondary: "#A3A9AC" },
  TENNESSEE: { primary: "#FF8200", secondary: "#FFFFFF" },
  TEXAS: { primary: "#BF5700", secondary: "#FFFFFF" },
  "TEXAS A&M": { primary: "#500000", secondary: "#FFFFFF" },
  "TEXAS TECH": { primary: "#CC0000", secondary: "#000000" },
  UCF: { primary: "#000000", secondary: "#BA9B37" },
  UCLA: { primary: "#2774AE", secondary: "#FFD100" },
  USC: { primary: "#990000", secondary: "#FFCC00" },
  UTAH: { primary: "#CC0000", secondary: "#000000" },
  VANDERBILT: { primary: "#866D4B", secondary: "#000000" },
  VIRGINIA: { primary: "#232D4B", secondary: "#F84C1E" },
  "VIRGINIA TECH": { primary: "#630031", secondary: "#CF4420" },
  WASHINGTON: { primary: "#4B2E83", secondary: "#B7A57A" },
  "WAKE FOREST": { primary: "#9E7E38", secondary: "#000000" },
  "WEST VIRGINIA": { primary: "#002855", secondary: "#EAAA00" },
  WISCONSIN: { primary: "#C5050C", secondary: "#FFFFFF" },
};

const normalizeSchoolKey = (value: string) =>
  value
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9\s]/g, " ")
    .replace(/\s+/g, " ");

const hexToRgba = (hex: string, alpha: number) => {
  const sanitized = hex.replace("#", "");
  const expanded =
    sanitized.length === 3
      ? sanitized
          .split("")
          .map((char) => char + char)
          .join("")
      : sanitized;
  const intValue = Number.parseInt(expanded, 16);
  if (!Number.isFinite(intValue)) return `rgba(59, 130, 246, ${alpha})`;
  const r = (intValue >> 16) & 255;
  const g = (intValue >> 8) & 255;
  const b = intValue & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const fallbackPalette = (school: string): SchoolPalette => {
  let hash = 0;
  for (const char of school) hash = (hash << 5) - hash + char.charCodeAt(0);
  const palette = [
    { primary: "#2563EB", secondary: "#1E40AF" },
    { primary: "#0F766E", secondary: "#0E7490" },
    { primary: "#7C3AED", secondary: "#4338CA" },
    { primary: "#B45309", secondary: "#92400E" },
  ];
  return palette[Math.abs(hash) % palette.length];
};

const getSchoolPalette = (school: string): SchoolPalette => {
  const key = normalizeSchoolKey(school);
  const direct = SCHOOL_COLOR_PALETTES[key];
  if (direct) return direct;
  for (const [candidate, palette] of Object.entries(SCHOOL_COLOR_PALETTES)) {
    if (normalizeSchoolKey(candidate) === key) return palette;
  }
  return fallbackPalette(school);
};

const normalizePlayerPosition = (value: unknown): string => String(value ?? "").trim().toUpperCase();

export default function Draft() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { setActiveLeagueId } = useActiveLeagueId();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"draft" | "queue" | "roster">("draft");
  const [sortMode, setSortMode] = useState<DraftSortMode>("adp_asc");
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [displaySecondsRemaining, setDisplaySecondsRemaining] = useState<number>(90);
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number | null>(null);
  const [pickSlotTransition, setPickSlotTransition] = useState<{ fromPick: number | null; toPick: number | null } | null>(null);
  const [recentPickFx, setRecentPickFx] = useState<{
    pickId: number;
    teamId: number;
    playerName: string;
  } | null>(null);
  const [draftStartFxVisible, setDraftStartFxVisible] = useState(false);
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);
  const timelineCardRefs = useRef(new Map<number, HTMLDivElement>());
  const boardScrollRef = useRef<HTMLDivElement | null>(null);
  const draftHistoryRef = useRef<HTMLDivElement | null>(null);
  const pendingBoardScrollTopRef = useRef<number | null>(null);
  const previousCurrentPickRef = useRef<number | null>(null);
  const previousCenteredPickRef = useRef<number | null>(null);
  const previousLatestPickIdRef = useRef<number | null>(null);
  const draftStartFxShownRef = useRef(false);
  const draftStartFxTimeoutRef = useRef<number | null>(null);

  const parsedLeagueId = leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;

  const { data: league } = useLeagueDetail(parsedLeagueId);
  const {
    data: draftRoom,
    isLoading: draftRoomLoading,
    error: draftRoomError,
  } = useDraftRoom(parsedLeagueId);
  useDraftRoomRealtime(parsedLeagueId, true);
  const draftPracticeSetup = useDraftPracticeSetup(parsedLeagueId);
  const pickMutation = useDraftPick(parsedLeagueId);
  const sheetSyncMutation = useDraftSheetSync(parsedLeagueId);
  const userTeamId = draftRoom?.user_team_id ?? null;
  const { data: queuePayload } = useDraftQueue(parsedLeagueId, userTeamId, Boolean(parsedLeagueId));
  const queueAddMutation = useDraftQueueAdd(parsedLeagueId, userTeamId);
  const queueRemoveMutation = useDraftQueueRemove(parsedLeagueId, userTeamId);
  const queueClearMutation = useDraftQueueClear(parsedLeagueId, userTeamId);
  const [autoOpenedDraft, setAutoOpenedDraft] = useState(false);
  const [autoSheetSyncTriggered, setAutoSheetSyncTriggered] = useState(false);
  const [accessRecoveryAttempted, setAccessRecoveryAttempted] = useState(false);

  const projectionSeason = league?.season_year ?? new Date().getFullYear();

  const jumpToDraftHistory = useCallback(() => {
    setActiveTab("draft");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        draftHistoryRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }, []);

  const { data: playersPayload, isLoading: playersLoading } = usePlayers({
    limit: 2000,
    season: projectionSeason,
    week: 1,
  });
  const {
    data: playerSeasonSummary,
    isLoading: playerSeasonSummaryLoading,
  } = usePlayerSeasonSummary(selectedPlayerId, 2025, selectedPlayerId !== null);

  useEffect(() => {
    setAutoOpenedDraft(false);
    draftStartFxShownRef.current = false;
    if (draftStartFxTimeoutRef.current !== null) {
      window.clearTimeout(draftStartFxTimeoutRef.current);
      draftStartFxTimeoutRef.current = null;
    }
    setDraftStartFxVisible(false);
    previousCenteredPickRef.current = null;
    setAccessRecoveryAttempted(false);
  }, [parsedLeagueId]);

  useEffect(() => {
    if (accessRecoveryAttempted) return;
    if (!(draftRoomError instanceof ApiError) || draftRoomError.status !== 403) return;
    setAccessRecoveryAttempted(true);
    setActiveLeagueId(null);
    navigate("/draft", { replace: true });
  }, [accessRecoveryAttempted, draftRoomError, navigate, setActiveLeagueId]);

  useEffect(() => {
    if (!parsedLeagueId || autoOpenedDraft || draftPracticeSetup.isPending) return;

    const draftMissing = draftRoomError instanceof ApiError && draftRoomError.status === 404;
    if (!draftMissing) return;

    setAutoOpenedDraft(true);
    draftPracticeSetup.mutate({
      team_count: 12,
      reset_existing: true,
      start_now: false,
      mock_team_prefix: "Auto Manager",
    });
  }, [
    autoOpenedDraft,
    draftPracticeSetup,
    draftRoom,
    draftRoomError,
    parsedLeagueId,
  ]);

  const draftTeams = useMemo(() => (Array.isArray(draftRoom?.teams) ? draftRoom.teams : []), [draftRoom?.teams]);
  const draftPicks = useMemo(() => (Array.isArray(draftRoom?.picks) ? draftRoom.picks : []), [draftRoom?.picks]);
  const draftRosters = useMemo(
    () => (Array.isArray(draftRoom?.rosters_by_team) ? draftRoom.rosters_by_team : []),
    [draftRoom?.rosters_by_team]
  );
  const draftTeamById = useMemo(() => new Map(draftTeams.map((team) => [team.id, team])), [draftTeams]);
  const draftPicksByOverall = useMemo(() => new Map(draftPicks.map((pick) => [pick.overall_pick, pick])), [draftPicks]);
  const totalDraftRounds = useMemo(() => {
    const rosterSlots = draftRoom?.roster_slots && typeof draftRoom.roster_slots === "object" ? draftRoom.roster_slots : {};
    const rawRounds = Object.values(rosterSlots).reduce((sum, value) => {
      const n = Number(value);
      return sum + (Number.isFinite(n) ? Math.max(0, Math.round(n)) : 0);
    }, 0);
    return Math.max(1, rawRounds);
  }, [draftRoom?.roster_slots]);
  const draftPickTimeline = useMemo(() => {
    if (draftTeams.length === 0) return [] as Array<{ overallPick: number; round: number; roundPick: number; teamId: number }>;
    const fallbackOrder = draftTeams.map((team) => team.id);
    const serverOrder =
      Array.isArray(draftRoom?.draft_order) && draftRoom.draft_order.length === draftTeams.length
        ? draftRoom.draft_order
        : fallbackOrder;
    let overallPick = 1;
    const timeline: Array<{ overallPick: number; round: number; roundPick: number; teamId: number }> = [];
    for (let round = 1; round <= totalDraftRounds; round += 1) {
      const roundOrder = round % 2 === 1 ? serverOrder : [...serverOrder].reverse();
      roundOrder.forEach((teamId, index) => {
        timeline.push({
          overallPick,
          round,
          roundPick: index + 1,
          teamId: Number(teamId),
        });
        overallPick += 1;
      });
    }
    return timeline;
  }, [draftRoom?.draft_order, draftTeams, totalDraftRounds]);

  const managerLabelByTeamId = useMemo(() => {
    const map = new Map<number, string>();
    if (draftTeams.length === 0) return map;

    const fallbackOrder = draftTeams.map((team) => team.id);
    const order =
      Array.isArray(draftRoom?.draft_order) && draftRoom.draft_order.length === draftTeams.length
        ? draftRoom.draft_order.map((teamId) => Number(teamId))
        : fallbackOrder;

    const orderedUniqueTeamIds = order.filter(
      (teamId, index) => draftTeamById.has(teamId) && order.indexOf(teamId) === index
    );
    const managerOneTeamId =
      (draftRoom?.user_team_id && draftTeamById.has(draftRoom.user_team_id) ? draftRoom.user_team_id : null) ??
      orderedUniqueTeamIds[0] ??
      draftTeams[0].id;

    map.set(managerOneTeamId, "Manager 1");
    let autoManagerNumber = 2;

    orderedUniqueTeamIds.forEach((teamId) => {
      if (teamId === managerOneTeamId) return;
      map.set(teamId, `Auto Manager ${autoManagerNumber}`);
      autoManagerNumber += 1;
    });

    draftTeams.forEach((team) => {
      if (map.has(team.id)) return;
      map.set(team.id, `Auto Manager ${autoManagerNumber}`);
      autoManagerNumber += 1;
    });

    return map;
  }, [draftRoom?.draft_order, draftRoom?.user_team_id, draftTeamById, draftTeams]);

  const centerTimelinePick = useCallback((overallPick: number | null | undefined, behavior: ScrollBehavior = "smooth") => {
    if (!overallPick) return;
    const scroller = timelineScrollRef.current;
    const card = timelineCardRefs.current.get(overallPick);
    if (!scroller || !card) return;

    const rawTarget = card.offsetLeft + card.offsetWidth / 2 - scroller.clientWidth / 2;
    const maxLeft = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
    const targetLeft = Math.min(maxLeft, Math.max(0, rawTarget));
    scroller.scrollTo({ left: targetLeft, behavior });
  }, []);

  const draftedIds = useMemo(() => new Set(draftPicks.map((pick) => pick.player_id)), [draftPicks]);

  useEffect(() => {
    const pick = draftRoom?.current_pick ?? null;
    if (!pick || draftPickTimeline.length === 0) return;
    const behavior: ScrollBehavior = previousCenteredPickRef.current === null ? "auto" : "smooth";
    previousCenteredPickRef.current = pick;
    const frame = window.requestAnimationFrame(() => centerTimelinePick(pick, behavior));
    return () => window.cancelAnimationFrame(frame);
  }, [centerTimelinePick, draftRoom?.current_pick, draftPickTimeline.length]);

  useEffect(() => {
    const handleResize = () => {
      centerTimelinePick(draftRoom?.current_pick ?? null, "auto");
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [centerTimelinePick, draftRoom?.current_pick]);

  useEffect(() => {
    if (draftRosters.length === 0) {
      setSelectedRosterTeamId(null);
      return;
    }
    const rosterIds = new Set(draftRosters.map((roster) => roster.team_id));
    setSelectedRosterTeamId((current) => {
      if (current && rosterIds.has(current)) return current;
      if (draftRoom?.user_team_id && rosterIds.has(draftRoom.user_team_id)) return draftRoom.user_team_id;
      return draftRosters[0].team_id;
    });
  }, [draftRosters, draftRoom?.user_team_id]);

  useEffect(() => {
    const currentPick = draftRoom?.current_pick ?? null;
    const previousPick = previousCurrentPickRef.current;
    if (previousPick !== null && currentPick !== null && previousPick !== currentPick) {
      setPickSlotTransition({ fromPick: previousPick, toPick: currentPick });
      const timeoutId = window.setTimeout(() => setPickSlotTransition(null), 1400);
      previousCurrentPickRef.current = currentPick;
      return () => window.clearTimeout(timeoutId);
    }
    previousCurrentPickRef.current = currentPick;
  }, [draftRoom?.current_pick]);

  useEffect(() => {
    const latestPick = draftPicks[draftPicks.length - 1];
    if (!latestPick) {
      previousLatestPickIdRef.current = null;
      return;
    }
    if (previousLatestPickIdRef.current === latestPick.id) return;
    previousLatestPickIdRef.current = latestPick.id;
    setRecentPickFx({
      pickId: latestPick.id,
      teamId: latestPick.team_id,
      playerName: latestPick.player_name,
    });
    const timeoutId = window.setTimeout(() => {
      setRecentPickFx((current) => (current?.pickId === latestPick.id ? null : current));
    }, 5000);
    return () => window.clearTimeout(timeoutId);
  }, [draftPicks]);

  useEffect(() => {
    if (!draftRoom) return;
    const fallback = clampTimerSeconds(draftRoom.current_pick_timer_seconds ?? draftRoom.pick_timer_seconds, 90);
    const next = clampTimerSeconds(draftRoom.phase_seconds_remaining ?? draftRoom.seconds_remaining, fallback);
    setDisplaySecondsRemaining(next);
  }, [
    draftRoom?.current_pick,
    draftRoom?.seconds_remaining,
    draftRoom?.phase_seconds_remaining,
    draftRoom?.pick_timer_seconds,
    draftRoom?.current_pick_timer_seconds,
    draftRoom?.status,
    draftRoom?.server_state_seq,
  ]);

  useEffect(() => {
    if (!draftRoom || !["live", "countdown"].includes(draftRoom.status)) return;
    if (draftRoom.status === "live" && !draftRoom.current_team_id) return;
    if (displaySecondsRemaining <= 0) return;

    const interval = window.setInterval(() => {
      setDisplaySecondsRemaining((current) => Math.max(0, current - 1));
    }, 1_000);

    return () => {
      window.clearInterval(interval);
    };
  }, [draftRoom?.status, draftRoom?.current_team_id, draftRoom?.current_pick, displaySecondsRemaining]);

  const sheetBackedPlayerCount = useMemo(() => {
    const rows = playersPayload?.data ?? [];
    return rows.filter((player) => {
      const hasProjection = Number.isFinite(player.sheetProjectedSeasonPoints as number);
      const hasAdp = Number.isFinite(player.sheetAdp as number) && Number(player.sheetAdp) > 0;
      if (player.sheetSourceSheetId && player.sheetSourceSheetId === DEFAULT_SHEET_ID && hasProjection && hasAdp) return true;
      if (hasProjection && hasAdp) return true;
      return false;
    }).length;
  }, [playersPayload?.data]);
  const incompleteSheetStatCount = useMemo(() => {
    const rows = playersPayload?.data ?? [];
    return rows.filter((player) => {
      const hasProjection = Number.isFinite(player.sheetProjectedSeasonPoints as number);
      const hasAdp = Number.isFinite(player.sheetAdp as number) && Number(player.sheetAdp) > 0;
      const isSheetBacked =
        (player.sheetSourceSheetId && player.sheetSourceSheetId === DEFAULT_SHEET_ID) || (hasProjection && hasAdp);
      if (!isSheetBacked) return false;
      const stats = player.sheetProjectionStats;
      if (!stats || typeof stats !== "object") return true;
      return REQUIRED_PROJECTION_STAT_KEYS.some((key) => !Number.isFinite(Number(stats[key])));
    }).length;
  }, [playersPayload?.data]);

  useEffect(() => {
    if (autoSheetSyncTriggered || !parsedLeagueId || playersLoading || sheetSyncMutation.isPending) return;
    const hasSheetData = sheetBackedPlayerCount >= MIN_EXPECTED_SHEET_PLAYERS;
    const hasCompleteStatPayload = incompleteSheetStatCount === 0;
    if (hasSheetData && hasCompleteStatPayload) {
      setAutoSheetSyncTriggered(true);
      return;
    }
    setAutoSheetSyncTriggered(true);
    sheetSyncMutation.mutate({
      sheet_url: DEFAULT_SHEET_URL,
      worksheet_names: DEFAULT_SHEET_TABS,
      replace_mode: "replace_offense_pool",
      watchlist_name: "CFB Master Board",
    });
  }, [
    autoSheetSyncTriggered,
    parsedLeagueId,
    playersLoading,
    sheetBackedPlayerCount,
    incompleteSheetStatCount,
    sheetSyncMutation,
  ]);

  useEffect(() => {
    const result = sheetSyncMutation.data;
    if (!result) return;
    // Explicit debug output requested to verify column mapping and name matching.
    console.info("[DraftSheetSync] rows_imported=", result.received);
    console.info("[DraftSheetSync] players_matched=", result.matched_players);
    console.info("[DraftSheetSync] players_unmatched=", result.unmatched_players);
    console.info("[DraftSheetSync] sample_imported_rows=", result.sample_imported_rows);
    if (result.unmatched_player_names.length > 0) {
      console.warn("[DraftSheetSync] unmatched_player_names=", result.unmatched_player_names);
    }
  }, [sheetSyncMutation.data]);

  const sheetBackedPlayers = useMemo(() => {
    const allPlayers = playersPayload?.data ?? [];
    const offensePlayers = allPlayers.filter((player) =>
      ["QB", "RB", "WR", "TE", "K"].includes(normalizePlayerPosition(player.pos))
    );
    return offensePlayers.filter((player) => {
      if (player.sheetSourceSheetId && player.sheetSourceSheetId === DEFAULT_SHEET_ID) return true;
      if (Number.isFinite(player.sheetAdp as number) && Number.isFinite(player.sheetProjectedSeasonPoints as number)) return true;
      return false;
    });
  }, [playersPayload?.data]);

  const playersMissingDraftValues = useMemo(
    () =>
      sheetBackedPlayers.filter((player) => {
        const hasProjection = Number.isFinite(player.sheetProjectedSeasonPoints as number);
        const hasAdp = Number.isFinite(player.sheetAdp as number) && Number(player.sheetAdp) > 0;
        return !hasProjection || !hasAdp;
      }),
    [sheetBackedPlayers]
  );

  useEffect(() => {
    if (playersMissingDraftValues.length === 0) return;
    console.warn("[DraftBoard] players_missing_projection_or_adp count=", playersMissingDraftValues.length);
    playersMissingDraftValues.forEach((player) => {
      const reason = [
        Number.isFinite(player.sheetProjectedSeasonPoints as number) ? null : "missing projection",
        Number.isFinite(player.sheetAdp as number) && Number(player.sheetAdp) > 0 ? null : "missing ADP",
      ]
        .filter(Boolean)
        .join(", ");
      console.warn("[DraftBoard] missing_values player=", player.name, "school=", player.school, "reason=", reason);
    });
  }, [playersMissingDraftValues]);

  const boardPlayers = useMemo<DraftBoardPlayer[]>(() => {
    const useSheetValuesOnly = sheetBackedPlayers.length > 0;
    const allPlayers = playersPayload?.data ?? [];
    const offensePlayers = allPlayers.filter((player) =>
      ["QB", "RB", "WR", "TE", "K"].includes(normalizePlayerPosition(player.pos))
    );
    const sourcePlayers = useSheetValuesOnly ? sheetBackedPlayers : offensePlayers;

    return [...sourcePlayers]
      .filter((player) => ["QB", "RB", "WR", "TE", "K"].includes(normalizePlayerPosition(player.pos)))
      .filter((player) => Number.isFinite(player.sheetProjectedSeasonPoints as number))
      .filter((player) => Number.isFinite(player.sheetAdp as number) && Number(player.sheetAdp) > 0)
      .map((player) => {
        const projectedStandardPoints = Number(player.sheetProjectedSeasonPoints);
        const adpFromSheet = Number(player.sheetAdp);
        return {
          ...player,
          projectedStandardPoints,
          adpRank: adpFromSheet,
          draftRank: 0,
        };
      });
  }, [playersPayload?.data, sheetBackedPlayers]);

  const prospectById = useMemo(
    () => new Map(boardPlayers.map((player) => [player.id, player])),
    [boardPlayers]
  );

  const sortedBoardPlayers = useMemo(() => {
    const sorted = [...boardPlayers].sort((left, right) => {
      if (sortMode === "adp_asc") {
        if (left.adpRank !== right.adpRank) return left.adpRank - right.adpRank;
        if (right.projectedStandardPoints !== left.projectedStandardPoints) {
          return right.projectedStandardPoints - left.projectedStandardPoints;
        }
        return left.name.localeCompare(right.name);
      }
      if (sortMode === "position_asc") {
        const positionOrder = ["QB", "RB", "WR", "TE", "K"];
        const leftPos = positionOrder.indexOf(normalizePlayerPosition(left.pos));
        const rightPos = positionOrder.indexOf(normalizePlayerPosition(right.pos));
        if (leftPos !== rightPos) return leftPos - rightPos;
        if (right.projectedStandardPoints !== left.projectedStandardPoints) {
          return right.projectedStandardPoints - left.projectedStandardPoints;
        }
        return left.name.localeCompare(right.name);
      }
      if (right.projectedStandardPoints !== left.projectedStandardPoints) {
        return right.projectedStandardPoints - left.projectedStandardPoints;
      }
      if (left.adpRank !== right.adpRank) return left.adpRank - right.adpRank;
      return left.name.localeCompare(right.name);
    });

    return sorted.map((player, index) => ({
      ...player,
      draftRank: index + 1,
    }));
  }, [boardPlayers, sortMode]);

  const rankedPlayers = useMemo(() => {
    const normalizedSearch = searchQuery.trim().toLowerCase();
    if (!normalizedSearch) return sortedBoardPlayers;
    return sortedBoardPlayers.filter((player) => {
      const playerName = String(player.name ?? "").toLowerCase();
      const schoolName = String(player.school ?? "").toLowerCase();
      const position = normalizePlayerPosition(player.pos).toLowerCase();
      return (
        playerName.includes(normalizedSearch) ||
        schoolName.includes(normalizedSearch) ||
        position.includes(normalizedSearch)
      );
    });
  }, [searchQuery, sortedBoardPlayers]);

  const availablePlayers = useMemo(
    () => rankedPlayers.filter((player) => !draftedIds.has(player.id)),
    [draftedIds, rankedPlayers]
  );
  const selectedPlayer = useMemo(
    () => rankedPlayers.find((player) => player.id === selectedPlayerId) ?? null,
    [rankedPlayers, selectedPlayerId]
  );

  useEffect(() => {
    const pending = pendingBoardScrollTopRef.current;
    if (pending === null) return;
    const rafId = window.requestAnimationFrame(() => {
      if (boardScrollRef.current) {
        boardScrollRef.current.scrollTop = pending;
      }
      pendingBoardScrollTopRef.current = null;
    });
    return () => window.cancelAnimationFrame(rafId);
  }, [availablePlayers.length, draftRoom?.server_state_seq, sortMode, searchQuery]);

  const queuePlayerIds = useMemo(
    () => (queuePayload?.data ?? []).map((row) => row.player_id),
    [queuePayload?.data]
  );

  const queuedPlayers = useMemo(
    () =>
      queuePlayerIds
        .map((playerId) => prospectById.get(playerId))
        .filter((player): player is DraftBoardPlayer => Boolean(player) && !draftedIds.has(player.id)),
    [draftedIds, prospectById, queuePlayerIds]
  );

  useEffect(() => {
    if (selectedPlayerId === null) return;
    if (!selectedPlayer) {
      setSelectedPlayerId(null);
    }
  }, [selectedPlayer, selectedPlayerId]);

  const makePick = async (playerId: number) => {
    try {
      pendingBoardScrollTopRef.current = boardScrollRef.current?.scrollTop ?? null;
      await pickMutation.mutateAsync(playerId);
    } catch {
      // Error rendered inline.
    }
  };

  const addToQueue = async (playerId: number) => {
    try {
      await queueAddMutation.mutateAsync(playerId);
    } catch {
      // Rendered inline.
    }
  };

  const removeFromQueue = async (playerId: number) => {
    try {
      await queueRemoveMutation.mutateAsync(playerId);
    } catch {
      // Rendered inline.
    }
  };

  const draftNextQueued = async () => {
    const next = queuedPlayers[0];
    if (!next) return;
    await makePick(next.id);
  };

  const selectedProjectionStats =
    selectedPlayer?.sheetProjectionStats && typeof selectedPlayer.sheetProjectionStats === "object"
      ? selectedPlayer.sheetProjectionStats
      : {};
  const selectedProjectionStatsMap = selectedProjectionStats as Record<string, unknown>;
  const selectedPlayerDrafted = selectedPlayer ? draftedIds.has(selectedPlayer.id) : false;
  const selectedPlayerPosition = normalizePlayerPosition(selectedPlayer?.pos);
  const selectedPlayerHealthStatus =
    typeof selectedProjectionStatsMap["health_status"] === "string" && String(selectedProjectionStatsMap["health_status"]).trim()
      ? String(selectedProjectionStatsMap["health_status"]).trim().toUpperCase()
      : "HEALTHY";
  const selectedPlayerNews =
    playerSeasonSummary?.latest_news ||
    (typeof selectedProjectionStatsMap["latest_news"] === "string" && String(selectedProjectionStatsMap["latest_news"]).trim()
      ? String(selectedProjectionStatsMap["latest_news"]).trim()
      : selectedPlayer
        ? `${selectedPlayer.name} projects as a core ${selectedPlayerPosition || "CFB"} option in ${selectedPlayer.school}'s 2026/27 offense.`
        : "");
  const selectedPlayerNewsSourceType = playerSeasonSummary?.latest_news_source_type ?? "fallback_context";
  const selectedPlayerNewsSourceLabel =
    selectedPlayerNewsSourceType === "verified_override"
      ? "Verified"
      : selectedPlayerNewsSourceType === "sheet"
        ? "Sheet"
        : selectedPlayerNewsSourceType === "generated_stats"
          ? "Generated"
          : "Fallback";
  const selectedPlayerRank = selectedPlayer ? Math.max(1, Math.round(selectedPlayer.adpRank || selectedPlayer.draftRank || 1)) : 1;
  const selectedPlayerStatsRows = useMemo(() => {
    if (!selectedPlayer) return [] as DraftStatRow[];
    const pos = selectedPlayerPosition;
    if (pos === "QB") {
      return [
        { key: "comp", label: "Completions", value: asFiniteNumber(selectedProjectionStats.comp) },
        { key: "attempts", label: "Attempts", value: asFiniteNumber(selectedProjectionStats.attempts) },
        { key: "pass_yds", label: "Pass Yards", value: asFiniteNumber(selectedProjectionStats.pass_yds) },
        { key: "pass_tds", label: "Pass TD", value: asFiniteNumber(selectedProjectionStats.pass_tds) },
        { key: "ints", label: "Interceptions", value: asFiniteNumber(selectedProjectionStats.ints) },
        { key: "rush_yds", label: "Rush Yards", value: asFiniteNumber(selectedProjectionStats.rush_yds) },
        { key: "rush_tds", label: "Rush TD", value: asFiniteNumber(selectedProjectionStats.rush_tds) },
      ];
    }
    if (pos === "RB") {
      return [
        { key: "rush_yds", label: "Rush Yards", value: asFiniteNumber(selectedProjectionStats.rush_yds) },
        { key: "rush_tds", label: "Rush TD", value: asFiniteNumber(selectedProjectionStats.rush_tds) },
        { key: "receptions", label: "Receptions", value: asFiniteNumber(selectedProjectionStats.receptions) },
        { key: "rec_yds", label: "Receiving Yards", value: asFiniteNumber(selectedProjectionStats.rec_yds) },
        { key: "rec_tds", label: "Receiving TD", value: asFiniteNumber(selectedProjectionStats.rec_tds) },
      ];
    }
    if (pos === "WR" || pos === "TE") {
      return [
        { key: "receptions", label: "Receptions", value: asFiniteNumber(selectedProjectionStats.receptions) },
        { key: "rec_yds", label: "Receiving Yards", value: asFiniteNumber(selectedProjectionStats.rec_yds) },
        { key: "rec_tds", label: "Receiving TD", value: asFiniteNumber(selectedProjectionStats.rec_tds) },
      ];
    }
    if (pos === "K") {
      return [
        { key: "fg", label: "FG Made", value: asFiniteNumber(selectedProjectionStats.fg) },
        { key: "xp", label: "XP Made", value: asFiniteNumber(selectedProjectionStats.xp) },
      ];
    }
    return [
      { key: "rush_yds", label: "Rush Yards", value: asFiniteNumber(selectedProjectionStats.rush_yds) },
      { key: "rush_tds", label: "Rush TD", value: asFiniteNumber(selectedProjectionStats.rush_tds) },
      { key: "receptions", label: "Receptions", value: asFiniteNumber(selectedProjectionStats.receptions) },
      { key: "rec_yds", label: "Receiving Yards", value: asFiniteNumber(selectedProjectionStats.rec_yds) },
      { key: "rec_tds", label: "Receiving TD", value: asFiniteNumber(selectedProjectionStats.rec_tds) },
    ];
  }, [selectedPlayer, selectedPlayerPosition, selectedProjectionStats]);
  const selectedPlayerSeasonRows = useMemo(() => {
    if (!playerSeasonSummary) return [] as DraftStatRow[];
    const totals = playerSeasonSummary.totals;
    if (selectedPlayerPosition === "QB") {
      return [
        { key: "games", label: "Games", value: asFiniteNumber(totals.games) },
        { key: "passing_completions", label: "Completions", value: asFiniteNumber(totals.passing_completions) },
        { key: "passing_attempts", label: "Attempts", value: asFiniteNumber(totals.passing_attempts) },
        { key: "passing_yards", label: "Pass Yards", value: asFiniteNumber(totals.passing_yards) },
        { key: "passing_tds", label: "Pass TD", value: asFiniteNumber(totals.passing_tds) },
        { key: "interceptions", label: "INT", value: asFiniteNumber(totals.interceptions) },
        { key: "rushing_yards", label: "Rush Yards", value: asFiniteNumber(totals.rushing_yards) },
        { key: "rushing_tds", label: "Rush TD", value: asFiniteNumber(totals.rushing_tds) },
      ];
    }
    if (selectedPlayerPosition === "RB") {
      return [
        { key: "games", label: "Games", value: asFiniteNumber(totals.games) },
        { key: "rushing_attempts", label: "Rush Attempts", value: asFiniteNumber(totals.rushing_attempts) },
        { key: "rushing_yards", label: "Rush Yards", value: asFiniteNumber(totals.rushing_yards) },
        { key: "rushing_tds", label: "Rush TD", value: asFiniteNumber(totals.rushing_tds) },
        { key: "receptions", label: "Receptions", value: asFiniteNumber(totals.receptions) },
        { key: "receiving_yards", label: "Rec Yards", value: asFiniteNumber(totals.receiving_yards) },
        { key: "receiving_tds", label: "Rec TD", value: asFiniteNumber(totals.receiving_tds) },
      ];
    }
    if (selectedPlayerPosition === "WR" || selectedPlayerPosition === "TE") {
      return [
        { key: "games", label: "Games", value: asFiniteNumber(totals.games) },
        { key: "receptions", label: "Receptions", value: asFiniteNumber(totals.receptions) },
        { key: "receiving_yards", label: "Rec Yards", value: asFiniteNumber(totals.receiving_yards) },
        { key: "receiving_tds", label: "Rec TD", value: asFiniteNumber(totals.receiving_tds) },
      ];
    }
    if (selectedPlayerPosition === "K") {
      return [
        { key: "games", label: "Games", value: asFiniteNumber(totals.games) },
        { key: "field_goals_made", label: "FG Made", value: asFiniteNumber(totals.field_goals_made) },
        { key: "extra_points_made", label: "XP Made", value: asFiniteNumber(totals.extra_points_made) },
      ];
    }
    return [
      { key: "games", label: "Games", value: asFiniteNumber(totals.games) },
      { key: "rushing_yards", label: "Rush Yards", value: asFiniteNumber(totals.rushing_yards) },
      { key: "rushing_tds", label: "Rush TD", value: asFiniteNumber(totals.rushing_tds) },
      { key: "receptions", label: "Receptions", value: asFiniteNumber(totals.receptions) },
      { key: "receiving_yards", label: "Rec Yards", value: asFiniteNumber(totals.receiving_yards) },
      { key: "receiving_tds", label: "Rec TD", value: asFiniteNumber(totals.receiving_tds) },
    ];
  }, [playerSeasonSummary, selectedPlayerPosition]);
  const selectedSchoolPalette = useMemo(
    () => (selectedPlayer ? getSchoolPalette(selectedPlayer.school) : { primary: "#2563EB", secondary: "#1E3A8A" }),
    [selectedPlayer]
  );
  const liveTimerSeconds = Math.max(0, displaySecondsRemaining);
  const phaseType = draftRoom?.phase_type ?? null;
  const pickPrepSeconds = phaseType === "pick_transition" ? liveTimerSeconds : 0;
  const isPrepWindow = draftRoom?.status === "live" && phaseType === "pick_transition" && pickPrepSeconds > 0;
  const isUrgencyTimer =
    draftRoom?.status === "live" &&
    phaseType === "pick_clock" &&
    liveTimerSeconds > 0 &&
    liveTimerSeconds <= 10;
  const urgencyScaleClass = isUrgencyTimer ? (liveTimerSeconds % 2 === 0 ? "scale-110" : "scale-95") : "scale-100";
  const timerLabel =
    draftRoom?.status === "countdown"
      ? "Draft Starts In"
      : isPrepWindow
        ? "Pick Transition"
        : "Draft Timer";
  const selectedRosterTeam = useMemo(
    () => draftRosters.find((teamRoster) => teamRoster.team_id === selectedRosterTeamId) ?? null,
    [draftRosters, selectedRosterTeamId]
  );
  const selectedRosterSlots = useMemo(() => {
    if (!selectedRosterTeam) return [] as Array<{ label: string; key: string; player: null | { player_name: string; position: string; school: string; projected_fantasy_points: number | null } }>;
    const slots = selectedRosterTeam?.slots && typeof selectedRosterTeam.slots === "object" ? selectedRosterTeam.slots : {};
    const normalized = new Map<string, Array<{ player_name: string; position: string; school: string; projected_fantasy_points: number | null }>>();
    Object.entries(slots).forEach(([slotName, players]) => {
      if (!Array.isArray(players)) return;
      const normalizedSlotName = slotName.toUpperCase() === "SUPERFLEX" ? "FLEX" : slotName.toUpperCase();
      normalized.set(normalizedSlotName, [...players] as Array<{ player_name: string; position: string; school: string; projected_fantasy_points: number | null }>);
    });

    const pullPlayer = (slotKey: string) => {
      const rows = normalized.get(slotKey);
      if (!rows || rows.length === 0) return null;
      const player = rows.shift() || null;
      normalized.set(slotKey, rows);
      return player;
    };

    return ROSTER_SLOT_LAYOUT.map((label) => {
      const key = label.replace(/[0-9]+$/, "");
      const player = pullPlayer(key);
      return { label, key, player };
    });
  }, [selectedRosterTeam]);

  useEffect(() => {
    if (!draftRoom) return;
    const isDraftStartTransition =
      draftRoom.status === "live" &&
      draftRoom.current_pick === 1 &&
      draftRoom.picks.length === 0 &&
      pickPrepSeconds > 0;
    if (!isDraftStartTransition || draftStartFxShownRef.current) return;
    draftStartFxShownRef.current = true;
    setDraftStartFxVisible(true);
    draftStartFxTimeoutRef.current = window.setTimeout(() => {
      setDraftStartFxVisible(false);
      draftStartFxTimeoutRef.current = null;
    }, 2100);
  }, [draftRoom, pickPrepSeconds]);

  useEffect(
    () => () => {
      if (draftStartFxTimeoutRef.current !== null) {
        window.clearTimeout(draftStartFxTimeoutRef.current);
        draftStartFxTimeoutRef.current = null;
      }
    },
    []
  );

  if (!parsedLeagueId) {
    return (
      <div className="max-w-4xl mx-auto py-16">
        <Card className="bg-card/40 border-border/60 rounded-[2.5rem]">
          <CardContent className="p-12 text-center">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">Invalid league ID.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (draftRoomLoading || draftPracticeSetup.isPending) {
    return (
      <div className="max-w-5xl mx-auto py-16">
        <Card className="bg-card/40 border-white/10 rounded-[2.5rem]">
          <CardContent className="p-12 flex items-center justify-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/70">
              {draftRoomLoading
                ? "Loading live draft room..."
                : draftPracticeSetup.isPending
                  ? "Opening pre-draft lobby..."
                  : "Building ADP board..."}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!draftRoom || draftRoomError) {
    return (
      <div className="max-w-5xl mx-auto py-16">
        <Card className="bg-card/40 border border-red-400/20 rounded-[2.5rem]">
          <CardContent className="p-12 text-center space-y-4">
            <ShieldAlert className="mx-auto h-8 w-8 text-red-300" />
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
              {formatApiError(draftRoomError, "Unable to load draft room.")}
            </p>
            <Button
              variant="outline"
              className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
              onClick={() => navigate(`/league/${parsedLeagueId}`)}
            >
              Back to League Hub
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto py-10 space-y-6">
      {draftStartFxVisible && (
        <div className="pointer-events-none fixed inset-0 z-[180] flex items-center justify-center bg-[#030a18]/75">
          <div className="rounded-2xl border border-primary/40 bg-primary/15 px-8 py-5 text-center shadow-[0_0_32px_rgba(59,130,246,0.5)] animate-[pulse_900ms_ease-in-out_2]">
            <p className="text-[11px] font-black uppercase tracking-[0.28em] text-primary/90">Draft Start</p>
            <p className="mt-1 text-3xl font-black italic text-foreground">Make Your Picks</p>
          </div>
        </div>
      )}
      <Card className="bg-card/40 border-white/10 rounded-[2.5rem] shadow-[0_0_60px_rgba(59,130,246,0.18)]">
        <CardHeader className="border-b border-white/10">
          <div className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-8 px-2 -ml-2 justify-start text-[9px] font-black uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground"
                  onClick={() => navigate(`/league/${parsedLeagueId}`)}
                >
                  <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                  Exit Draft
                </Button>
                <CardTitle className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
                  Managers In Draft
                </CardTitle>
                <p className="text-[9px] font-black uppercase tracking-[0.18em] text-emerald-100/90">
                  Draft Status: {draftRoom.status} • Live synced in real time
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-2">
                <Button asChild variant="outline" className="h-10 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]">
                  <Link to={`/league/${parsedLeagueId}`}>League Hub</Link>
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 rounded-xl text-[9px] font-black uppercase tracking-[0.16em]"
                  onClick={jumpToDraftHistory}
                >
                  Draft History
                </Button>
              </div>
            </div>

            <div className="flex justify-center">
              <div
                className={`min-w-[180px] rounded-2xl border px-5 py-3 text-center transition-all duration-300 ${
                  isUrgencyTimer
                    ? "border-red-400/70 bg-red-500/10 shadow-[0_0_24px_rgba(248,113,113,0.45)]"
                    : "border-white/10 bg-white/5"
                }`}
              >
                <p className="text-[9px] font-black uppercase tracking-[0.2em] text-muted-foreground/70">{timerLabel}</p>
                <p
                  className={`mt-1 text-3xl font-black italic transition-all duration-300 ${
                    isUrgencyTimer ? `animate-pulse text-red-300 ${urgencyScaleClass}` : "text-foreground"
                  }`}
                >
                  {isPrepWindow ? `Prep ${pickPrepSeconds}s` : `${liveTimerSeconds}s`}
                </p>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-5 space-y-5">
          <div ref={timelineScrollRef} className="overflow-x-auto no-scrollbar" style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}>
            <div className="flex min-w-max gap-3">
              {draftPickTimeline.map((slot) => {
                const team = draftTeamById.get(slot.teamId);
                const isOnClock = slot.overallPick === draftRoom.current_pick && draftRoom.status !== "completed";
                const isUserTeam = slot.teamId === draftRoom.user_team_id;
                const isIncomingClock = pickSlotTransition?.toPick === slot.overallPick;
                const isOutgoingClock = pickSlotTransition?.fromPick === slot.overallPick && !isOnClock;
                const madePick = draftPicksByOverall.get(slot.overallPick);
                const isComplete = Boolean(madePick);
                const pickedPosition = normalizePlayerPosition(madePick?.player_position);
                const pickAuraClass =
                  pickAuraClassByPosition[pickedPosition] ??
                  "border-white/12 bg-black/25 shadow-[0_0_10px_rgba(148,163,184,0.2)]";
                const managerDisplayName =
                  managerLabelByTeamId.get(slot.teamId) ||
                  (team?.owner_user_id === null ? (team?.name || team?.owner_name || "Team") : (team?.owner_name || team?.name || "Team"));
                const badge = managerDisplayName.trim().slice(0, 2).toUpperCase();
                const slotLabel = `${slot.round}.${slot.roundPick}`;
                return (
                  <div
                    key={slot.overallPick}
                    ref={(node) => {
                      if (node) {
                        timelineCardRefs.current.set(slot.overallPick, node);
                      } else {
                        timelineCardRefs.current.delete(slot.overallPick);
                      }
                    }}
                    className={`relative min-w-[150px] max-w-[150px] overflow-hidden rounded-2xl border px-3 py-3 transition-all duration-300 ${
                      isOnClock
                        ? "border-primary/80 bg-primary/20 shadow-[0_0_20px_rgba(59,130,246,0.42)] scale-[1.02]"
                        : isUserTeam
                          ? "border-primary/45 bg-primary/10 shadow-[0_0_10px_rgba(59,130,246,0.2)]"
                          : "border-white/10 bg-white/5"
                    } ${isIncomingClock ? "animate-[pulse_900ms_ease-in-out_2]" : ""} ${isOutgoingClock ? "animate-[ping_800ms_ease-out_1]" : ""}`}
                    title={managerDisplayName}
                  >
                    {isOnClock && <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-primary shadow-[0_0_14px_rgba(96,165,250,0.95)] animate-pulse" />}
                    <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full border border-white/20 bg-black/25 text-[10px] font-black uppercase text-foreground">
                      {badge}
                    </div>
                    <div
                      className={`mb-2 rounded-md border px-2 py-1 transition-all duration-300 ${
                        isComplete ? pickAuraClass : "border-white/12 bg-black/25"
                      }`}
                    >
                      <p className="truncate text-center text-[8px] font-black uppercase tracking-[0.08em] text-muted-foreground/75">
                          {madePick?.player_name ||
                            (isOnClock ? "On Clock" : "Waiting for pick")}
                        </p>
                      </div>
                    <p className="truncate text-center text-[9px] font-black uppercase tracking-[0.12em] text-foreground/85">
                      {managerDisplayName}
                    </p>
                    <p className="mt-1 text-center text-[8px] font-black uppercase tracking-[0.16em] text-primary/80">
                      {isOnClock ? `${slotLabel} • On Clock` : slotLabel}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {recentPickFx && (
            <div className="rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 shadow-[0_0_22px_rgba(59,130,246,0.35)] animate-[pulse_1200ms_ease-in-out_2]">
              <p className="text-[9px] font-black uppercase tracking-[0.2em] text-primary">
                Pick Confirmed
              </p>
              <p className="mt-1 text-[11px] font-black uppercase tracking-[0.1em] text-foreground">
                {(managerLabelByTeamId.get(recentPickFx.teamId) || "Auto Manager")} drafted {recentPickFx.playerName}
              </p>
            </div>
          )}

        </CardContent>
      </Card>

      {sheetSyncMutation.error && (
        <div className="rounded-2xl border border-red-400/20 bg-red-500/5 px-4 py-3 text-[10px] font-black uppercase tracking-[0.16em] text-red-300">
          {formatApiError(sheetSyncMutation.error, "Unable to sync sheet.")}
        </div>
      )}

      {sheetSyncMutation.data && (
        <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-[10px] font-black uppercase tracking-[0.15em] text-emerald-100">
          Synced {sheetSyncMutation.data.valid_rows}/{sheetSyncMutation.data.received} rows • Watchlist {sheetSyncMutation.data.watchlist_name} now has{" "}
          {sheetSyncMutation.data.watchlist_player_count} players • Matched {sheetSyncMutation.data.matched_players} • Unmatched{" "}
          {sheetSyncMutation.data.unmatched_players}.
          {(sheetSyncMutation.data.invalid_rows?.length ?? 0) > 0
            ? ` ${sheetSyncMutation.data.invalid_rows?.length ?? 0} rows were skipped due to validation issues.`
            : ""}
        </div>
      )}

      {!sheetSyncMutation.isPending && sheetBackedPlayerCount === 0 && (
        <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-[10px] font-black uppercase tracking-[0.16em] text-amber-100">
          No synced sheet rankings detected yet. The board is waiting for Google Sheet data.
        </div>
      )}

      <Card className="bg-card/40 border-white/10 rounded-[2.5rem] shadow-[0_0_70px_rgba(59,130,246,0.14)]">
        <CardHeader className="border-b border-white/10 items-center">
          <CardTitle className="text-center text-[11px] font-black uppercase tracking-[0.28em] text-primary">Draft Board</CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "draft" | "queue" | "roster")}>
            <TabsContent value="draft" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_280px] gap-3">
                <Input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search players, schools, or positions..."
                  className="h-12 rounded-2xl bg-white/5 border-white/10"
                />
                <Select value={sortMode} onValueChange={(value) => setSortMode(value as DraftSortMode)}>
                  <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-white/5 text-[10px] font-black uppercase tracking-[0.16em]">
                    <SelectValue placeholder="Sort board" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="adp_asc">Draft Value / ADP</SelectItem>
                    <SelectItem value="projection_desc">Projection</SelectItem>
                    <SelectItem value="position_asc">Position</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {pickMutation.error && (
                <div className="rounded-2xl border border-red-400/20 bg-red-500/5 p-4 text-[10px] font-black uppercase tracking-[0.18em] text-red-300">
                  {formatApiError(pickMutation.error, "Unable to save draft pick.")}
                </div>
              )}

              <div className="overflow-hidden rounded-[2rem] border border-primary/20 bg-gradient-to-b from-white/[0.06] to-white/[0.03] shadow-[inset_0_0_28px_rgba(59,130,246,0.12)]">
                <div className="grid grid-cols-[68px_minmax(0,1fr)_90px_170px_110px_90px_170px_210px] gap-4 border-b border-white/10 px-5 py-3 text-[9px] font-black uppercase tracking-[0.28em] text-muted-foreground/70 sticky top-0 bg-[#071327]/95 backdrop-blur">
                  <span>#</span>
                  <span>Player</span>
                  <span className={sortMode === "position_asc" ? "text-primary" : ""}>Pos</span>
                  <span>School</span>
                  <span>Class</span>
                  <span className={sortMode === "adp_asc" ? "text-primary" : ""}>ADP</span>
                  <span className={sortMode === "projection_desc" ? "text-primary" : ""}>Proj Pts</span>
                  <span className="text-right">Action</span>
                </div>

                <div ref={boardScrollRef} className="max-h-[75vh] overflow-y-auto">
                  {playersLoading ? (
                    <div className="px-6 py-10 text-center text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                      Loading players...
                    </div>
                  ) : availablePlayers.length === 0 ? (
                    <div className="px-6 py-10 text-center text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground/60">
                      No players match this search.
                    </div>
                  ) : (
                    availablePlayers.map((player) => {
                      const playerPos = normalizePlayerPosition(player.pos) || "N/A";
                      const playerSchool = String(player.school ?? "-");
                      const playerClass = String(player.playerClass ?? "-").toUpperCase();
                      const boardRankDisplay = player.draftRank;
                      return (
                      <div
                        key={player.id}
                        className="grid grid-cols-[68px_minmax(0,1fr)_90px_170px_110px_90px_170px_210px] items-center gap-4 border-b border-white/5 px-5 py-3 last:border-b-0 hover:bg-primary/[0.08] transition-colors"
                      >
                        <span className="inline-flex h-8 min-w-[46px] items-center justify-center rounded-full border border-primary/35 bg-primary/15 px-3 text-[11px] font-black uppercase tracking-[0.16em] text-primary shadow-[0_0_14px_rgba(59,130,246,0.35)]">
                          #{boardRankDisplay}
                        </span>
                        <div className="min-w-0">
                          <button
                            type="button"
                            className="truncate text-left text-sm font-black uppercase tracking-tight text-foreground hover:text-primary"
                            onClick={() => setSelectedPlayerId(player.id)}
                          >
                            {player.name}
                          </button>
                        </div>
                        <span
                          className={`inline-flex h-8 min-w-[58px] items-center justify-center gap-1 rounded-full border px-2 text-[10px] font-black uppercase tracking-[0.14em] ${
                            positionPillClass[playerPos] ?? "border-white/20 bg-white/10 text-foreground"
                          }`}
                        >
                          <span
                            className={`h-2 w-2 rounded-full ${positionDotClass[playerPos] ?? "bg-white/60"}`}
                          />
                          {playerPos}
                        </span>
                        <span className="truncate text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">{playerSchool}</span>
                        <span className="truncate text-[10px] font-black uppercase tracking-[0.2em] text-foreground/80">{playerClass}</span>
                        <span className="inline-flex h-8 min-w-[62px] items-center justify-center rounded-full border border-white/20 bg-white/5 px-2 text-[10px] font-black uppercase tracking-[0.14em] text-foreground tabular-nums">
                          {formatProjection(player.adpRank)}
                        </span>
                        <span className="inline-flex h-8 min-w-[84px] items-center justify-center rounded-full border border-primary/30 bg-primary/10 px-2 text-[10px] font-black uppercase tracking-[0.14em] text-primary tabular-nums shadow-[0_0_16px_rgba(59,130,246,0.28)]">
                          {formatProjection(player.projectedStandardPoints)}
                        </span>
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.18em]"
                            onClick={(event) => {
                              event.stopPropagation();
                              void addToQueue(player.id);
                            }}
                            disabled={
                              queuePlayerIds.includes(player.id) ||
                              draftedIds.has(player.id) ||
                              queueAddMutation.isPending
                            }
                          >
                            Queue
                          </Button>
                          <Button
                            type="button"
                            className="h-9 rounded-xl text-[9px] font-black uppercase tracking-[0.18em]"
                            disabled={!draftRoom.can_make_pick || pickMutation.isPending || draftedIds.has(player.id)}
                            onClick={(event) => {
                              event.stopPropagation();
                              void makePick(player.id);
                            }}
                          >
                            {pickMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : draftedIds.has(player.id) ? "Drafted" : "Draft"}
                          </Button>
                        </div>
                      </div>
                    )})
                  )}
                </div>
              </div>

              <div ref={draftHistoryRef} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Draft History</p>
                <div className="mt-3 max-h-44 space-y-2 overflow-y-auto pr-1">
                  {[...draftPicks]
                    .sort((a, b) => b.overall_pick - a.overall_pick)
                    .slice(0, 20)
                    .map((pick) => {
                      const player = prospectById.get(pick.player_id);
                      return (
                        <div key={pick.id} className="rounded-xl border border-primary/20 bg-[#0c1730] px-3 py-2.5">
                          <p className="text-[10px] font-bold tracking-[0.015em] text-slate-100">
                            <span className="font-black text-cyan-300">
                              {pick.round_number}.{pick.round_pick}
                            </span>{" "}
                            {pick.team_name} drafted{" "}
                            <span className="font-black text-foreground/95">{pick.player_name}</span>{" "}
                            <span className="text-slate-300/90">
                              ({pick.player_position}, {pick.player_school})
                            </span>{" "}
                            <span className="font-black text-primary/95">
                              {formatProjection(player?.projectedStandardPoints ?? 0)} pts
                            </span>
                          </p>
                        </div>
                      );
                    })}
                  {draftPicks.length === 0 && (
                    <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground/60">No picks yet.</p>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="queue" className="space-y-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">Manage your queue before you draft.</p>
                <div className="flex gap-2">
                  <Button
                    className="h-10 rounded-xl text-[9px] font-black uppercase tracking-[0.18em]"
                    disabled={!draftRoom.can_make_pick || queuedPlayers.length === 0 || pickMutation.isPending}
                    onClick={() => void draftNextQueued()}
                  >
                    Draft Next
                  </Button>
                  <Button
                    variant="outline"
                    className="h-10 rounded-xl text-[9px] font-black uppercase tracking-[0.18em]"
                    onClick={() => void queueClearMutation.mutateAsync()}
                    disabled={queuedPlayers.length === 0 || queueClearMutation.isPending}
                  >
                    Clear
                  </Button>
                </div>
              </div>

              {queuedPlayers.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-5 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">Queue is empty</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[52vh] overflow-y-auto pr-1">
                  {queuedPlayers.map((player, index) => (
                    <div key={player.id} className="rounded-2xl border border-white/10 bg-white/5 p-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-black uppercase tracking-tight text-foreground">#{index + 1} • {player.name}</p>
                        <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                          {normalizePlayerPosition(player.pos) || "N/A"} • {player.school} • {(player.playerClass || "-").toUpperCase()} • ADP {formatProjection(player.adpRank)} • {formatProjection(player.projectedStandardPoints)} proj
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        className="h-9 rounded-lg text-[9px] font-black uppercase tracking-[0.15em]"
                        onClick={() => void removeFromQueue(player.id)}
                        disabled={queueRemoveMutation.isPending}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="roster" className="space-y-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground/70">
                  Review every roster in clean slot order while draft is live.
                </p>
                <Select
                  value={selectedRosterTeamId ? String(selectedRosterTeamId) : ""}
                  onValueChange={(value) => setSelectedRosterTeamId(Number(value))}
                >
                  <SelectTrigger className="h-10 min-w-[220px] rounded-xl border-white/20 bg-white/5 text-[10px] font-black uppercase tracking-[0.16em]">
                    <SelectValue placeholder="Select team" />
                  </SelectTrigger>
                  <SelectContent>
                    {draftRosters.map((teamRoster) => (
                      <SelectItem key={teamRoster.team_id} value={String(teamRoster.team_id)}>
                        {teamRoster.team_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {!selectedRosterTeam ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-6 text-center">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground/60">
                    Select a team to view roster slots.
                  </p>
                </div>
              ) : (
                <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.06] to-white/[0.03] p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <p className="text-sm font-black uppercase tracking-tight text-foreground">{selectedRosterTeam.team_name}</p>
                      <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground/70">
                        Total Proj {formatProjection(selectedRosterTeam.total_projected_points)} • QB {selectedRosterTeam.position_counts?.QB || 0} • RB {selectedRosterTeam.position_counts?.RB || 0} • WR {selectedRosterTeam.position_counts?.WR || 0} • TE {selectedRosterTeam.position_counts?.TE || 0} • K {selectedRosterTeam.position_counts?.K || 0}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    {selectedRosterSlots.map((slotRow) => {
                      const positionAccent =
                        slotRow.key === "QB"
                          ? "border-blue-400/25 bg-blue-500/[0.08]"
                          : slotRow.key === "RB"
                            ? "border-emerald-400/25 bg-emerald-500/[0.08]"
                            : slotRow.key === "WR"
                              ? "border-violet-400/25 bg-violet-500/[0.08]"
                              : slotRow.key === "TE"
                                ? "border-amber-400/25 bg-amber-500/[0.08]"
                                : slotRow.key === "FLEX"
                                  ? "border-cyan-400/25 bg-cyan-500/[0.08]"
                                  : slotRow.key === "K"
                                    ? "border-slate-400/25 bg-slate-500/[0.08]"
                                    : slotRow.key === "IR"
                                      ? "border-rose-400/25 bg-rose-500/[0.08]"
                                      : "border-white/12 bg-white/[0.03]";
                      return (
                        <div key={slotRow.label} className={`rounded-xl border px-3 py-3 ${positionAccent}`}>
                          <p className="text-[9px] font-black uppercase tracking-[0.2em] text-muted-foreground/80">{slotRow.label}</p>
                          {slotRow.player ? (
                            <>
                              <p className="mt-2 text-[12px] font-black uppercase tracking-[0.08em] text-foreground truncate">
                                {slotRow.player.player_name}
                              </p>
                              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/70 truncate">
                                {slotRow.player.position} • {slotRow.player.school} • {formatProjection(slotRow.player.projected_fantasy_points ?? 0)} proj
                              </p>
                            </>
                          ) : (
                            <p className="mt-2 text-[9px] font-black uppercase tracking-[0.14em] text-muted-foreground/45">
                              Empty
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </TabsContent>

            <div className="mt-5 border-t border-white/10 pt-4">
              <TabsList className="w-full grid grid-cols-3">
                <TabsTrigger value="draft">Draft</TabsTrigger>
                <TabsTrigger value="queue">Queue</TabsTrigger>
                <TabsTrigger value="roster">Roster</TabsTrigger>
              </TabsList>
            </div>
          </Tabs>
        </CardContent>
      </Card>

      {!draftRoom.can_make_pick && (
        <div className="rounded-[2rem] border border-amber-500/20 bg-amber-500/10 p-5 flex gap-3">
          <Clock3 className="h-5 w-5 text-amber-300 shrink-0" />
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-100/85">
            {draftRoom.status === "countdown"
              ? "Draft has not started yet. Picks unlock when the countdown reaches 0."
              : isPrepWindow
                ? "Previous pick is being finalized. Next manager will be on the clock shortly."
                : "You can draft when your team is on the clock. Queue players now so your next pick is instant."}
          </p>
        </div>
      )}

      {selectedPlayer && (
        <div className="fixed inset-0 z-[220] flex items-center justify-center bg-black/70 p-4" onClick={() => setSelectedPlayerId(null)}>
          <div
            className="relative w-full max-w-5xl max-h-[94vh] overflow-hidden rounded-[1.5rem] border border-white/15 bg-[#081326] shadow-[0_24px_64px_rgba(0,0,0,0.55)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="relative border-b border-white/10 bg-white/[0.02] px-6 py-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p
                    className="text-[1.8rem] font-black uppercase tracking-tight text-foreground"
                    style={{
                      textShadow: `0 0 10px ${hexToRgba(selectedSchoolPalette.primary, 0.24)}, 0 0 14px ${hexToRgba(
                        selectedSchoolPalette.secondary,
                        0.16
                      )}`,
                    }}
                  >
                    {selectedPlayer.name}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="inline-flex h-8 items-center rounded-full border border-white/15 bg-white/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-foreground/90">
                      {selectedPlayer.school}
                    </span>
                    <span className="inline-flex h-8 items-center rounded-full border border-white/15 bg-white/5 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                      {(selectedPlayer.playerClass || "CFB").toUpperCase()}
                    </span>
                    <span
                      className="inline-flex h-8 items-center rounded-full border px-3 text-[10px] font-black uppercase tracking-[0.14em]"
                      style={{ borderColor: "rgba(96,165,250,0.4)", backgroundColor: "rgba(59,130,246,0.16)", color: "#EAF2FF" }}
                    >
                      {selectedPlayerPosition || "N/A"}
                    </span>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-9 w-9 rounded-full border border-white/15 bg-white/5 p-0 hover:bg-white/10"
                  onClick={() => setSelectedPlayerId(null)}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            <div className="relative border-b border-white/10 px-6 py-4">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-primary">
                About {selectedPlayer.name}
              </p>
            </div>

            <div className="relative max-h-[58vh] overflow-y-auto px-6 py-5 space-y-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                <div className="rounded-xl border border-white/14 bg-[#0E1A31] px-4 py-3">
                  <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">ADP</p>
                  <p className="mt-1 text-3xl font-black text-slate-100">{formatProjectionCardNumber(selectedPlayer.adpRank)}</p>
                </div>
                <div className="rounded-xl border border-white/14 bg-[#0E1A31] px-4 py-3">
                  <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">PROJ</p>
                  <p className="mt-1 text-3xl font-black text-slate-100">{formatProjectionCardNumber(selectedPlayer.projectedStandardPoints)}</p>
                </div>
                <div className="rounded-xl border border-white/14 bg-[#0E1A31] px-4 py-3">
                  <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">ROS</p>
                  <p className="mt-1 text-3xl font-black text-slate-100">100%</p>
                </div>
                <div className="rounded-xl border border-white/14 bg-[#0E1A31] px-4 py-3">
                  <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">RANK</p>
                  <p className="mt-1 text-3xl font-black text-slate-100">#{selectedPlayerRank}</p>
                </div>
              </div>

              <div className="rounded-xl border border-white/14 bg-[#0E1A31] px-5 py-4">
                <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                  <HeartPulse className="h-3.5 w-3.5" />
                  Health Status
                </p>
                <p className="mt-2 text-2xl font-black uppercase text-slate-100">{selectedPlayerHealthStatus}</p>
              </div>

              <div className="rounded-xl border border-amber-400/20 bg-amber-500/[0.05] px-5 py-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-amber-300">
                    <Newspaper className="h-3.5 w-3.5" />
                    Latest News
                  </p>
                  <span className="inline-flex h-6 items-center rounded-full border border-amber-300/40 bg-amber-400/10 px-2.5 text-[9px] font-black uppercase tracking-[0.12em] text-amber-200">
                    {selectedPlayerNewsSourceLabel}
                  </span>
                </div>
                <p className="mt-2 text-sm font-semibold leading-relaxed text-amber-100/85">{selectedPlayerNews}</p>
                {playerSeasonSummary?.latest_news_sources?.length ? (
                  <p className="mt-2 text-[10px] font-bold text-amber-200/70">
                    Sources: {playerSeasonSummary.latest_news_sources.join(" • ")}
                  </p>
                ) : null}
              </div>

              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">2026/27 Projected Stats</p>
                <div className="mt-3 space-y-2.5">
                  {selectedPlayerStatsRows.map((row) => (
                    <div key={row.key} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3">
                      <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">{row.label}</p>
                      <p className="text-2xl font-black text-foreground tabular-nums">{formatProjectionCardNumber(row.value)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">2025 Season Stats</p>
                {playerSeasonSummaryLoading ? (
                  <div className="mt-3 rounded-xl border border-white/10 bg-white/5 px-4 py-5">
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">Loading 2025 stats...</p>
                  </div>
                ) : playerSeasonSummary ? (
                  <div className="mt-3 space-y-2.5">
                    {selectedPlayerSeasonRows.map((row) => (
                      <div key={row.key} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.12em] text-muted-foreground">{row.label}</p>
                        <p className="text-2xl font-black text-foreground tabular-nums">{formatProjectionCardNumber(row.value)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-xl border border-white/10 bg-white/5 px-4 py-5">
                    <p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                      <AlertCircle className="h-3.5 w-3.5" />
                      2025 historical stat feed has not been imported for this player yet.
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-white/10 bg-[#0B1A35] px-6 py-4">
              <Button
                type="button"
                variant="outline"
                className="h-10 rounded-lg text-[10px] font-black uppercase tracking-[0.14em]"
                disabled={!draftRoom.can_make_pick || pickMutation.isPending || selectedPlayerDrafted}
                onClick={async () => {
                  if (!selectedPlayer) return;
                  await makePick(selectedPlayer.id);
                  setSelectedPlayerId(null);
                }}
              >
                {selectedPlayerDrafted ? "Drafted" : "Draft Player"}
              </Button>
              <Button
                type="button"
                className="h-10 min-w-[180px] rounded-lg text-[10px] font-black uppercase tracking-[0.16em]"
                onClick={() => setSelectedPlayerId(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
