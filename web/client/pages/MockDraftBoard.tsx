import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  CircleAlert,
  ClipboardList,
  Loader2,
  Lock,
  Plus,
  Search,
  ShieldAlert,
  Star,
  Trash2,
  Trophy,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useMockDraftPick,
  useMockDraftQueue,
  useMockDraftQueueAdd,
  useMockDraftQueueClear,
  useMockDraftEmailSummary,
  useMockDraftQueueRemove,
  useMockDraftQueueReorder,
  useMockDraftRealtime,
  useMockDraftRoom,
} from "@/hooks/use-mock-draft";
import { useAuth } from "@/hooks/use-auth";
import { usePlayerSeasonSummary, usePlayers, type PlayerSeasonSummary } from "@/hooks/use-players";
import { ApiError, getStoredAccessToken } from "@/lib/api";
import type { DraftRoomPick, DraftRoomTeam } from "@/types/draft";
import type { MockDraftRoom as MockDraftRoomType } from "@/types/mock-draft";
import type { Player } from "@/types/player";

const POSITION_FULL_PICK_ERROR = "You cannot draft this position because your roster has no available slot for it.";
const DEFAULT_PICK_TIMER_SECONDS = 90;
const DRAFTABLE_ROSTER_SLOT_KEYS = new Set(["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "DEF", "BENCH"]);
const ROSTER_SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR"];

type PositionFilter = "ALL" | "QB" | "RB" | "WR" | "TE" | "K";
type SortMode = "adp" | "projection";
type DraftTab = "draft" | "queue" | "roster" | "history";
type CompletionStep = "ask" | "email" | "sent";

type TimelineEntry = {
  overallPick: number;
  round: number;
  roundPick: number;
  teamId: number;
  team: DraftRoomTeam;
  pick: DraftRoomPick | null;
};

const MOBILE_BREAKPOINT = 768;

function formatClock(totalSeconds: number) {
  const safe = Math.max(0, totalSeconds);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function normalizePosition(position: string | null | undefined) {
  return String(position || "").toUpperCase();
}

function normalizePlayerIdentityText(value: string | null | undefined) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function normalizePlayerPoolPosition(position: string | null | undefined) {
  const normalized = String(position || "").trim().toUpperCase().replace(/[^A-Z0-9]+/g, "").replace(/\d+$/g, "");
  const aliases: Record<string, string> = { PK: "K", HB: "RB", FB: "RB", FL: "WR", SE: "WR" };
  return aliases[normalized] ?? normalized;
}

function getStableRankNumber(value: unknown) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) return null;
  return Math.max(1, Math.round(numericValue));
}

function getRosterSlotBase(slot: string) {
  const normalized = normalizePosition(slot);
  if (normalized.startsWith("SUPERFLEX")) return "SUPERFLEX";
  if (normalized.startsWith("FLEX")) return "FLEX";
  if (normalized.startsWith("BENCH")) return "BENCH";
  if (normalized.startsWith("IR")) return "IR";
  return normalized;
}

function getRosterSlotLabel(slot: string, index: number, count: number) {
  const base = getRosterSlotBase(slot);
  if (base === "BENCH") return `BENCH ${index + 1}`;
  if (base === "IR") return "IR";
  return count > 1 ? `${base} ${index + 1}` : base;
}

function buildDraftTimeline(room: MockDraftRoomType) {
  const teamById = new Map(room.teams.map((team) => [team.id, team]));
  const baseOrder = room.draft_order.length ? room.draft_order : room.teams.map((team) => team.id);
  const picksByOverall = new Map(room.picks.map((pick) => [pick.overall_pick, pick]));
  const timeline: TimelineEntry[] = [];
  let overallPick = 1;

  for (let round = 1; round <= room.total_rounds; round += 1) {
    const roundOrder = round % 2 === 1 ? baseOrder : [...baseOrder].reverse();
    roundOrder.forEach((teamId, index) => {
      const team = teamById.get(teamId);
      if (!team) return;
      timeline.push({
        overallPick,
        round,
        roundPick: index + 1,
        teamId,
        team,
        pick: picksByOverall.get(overallPick) ?? null,
      });
      overallPick += 1;
    });
  }

  return timeline;
}

function getTeamInitials(team: DraftRoomTeam) {
  const source = team.owner_name || team.name || "MO";
  return getInitials(source);
}

function getCompactSeatLabel(team: DraftRoomTeam, seatNumber: number | null) {
  if (team.owner_user_id === null) {
    return `C${seatNumber ?? team.id}`;
  }
  return getTeamInitials(team);
}

function getInitials(source: string) {
  return source
    .split(/\s+/)
    .map((part) => part[0] || "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function getPositionAura(position: string | null | undefined) {
  const normalized = normalizePosition(position);
  if (normalized === "QB") {
    return {
      ring: "border-sky-400/45",
      glow: "shadow-[0_0_0_1px_rgba(56,189,248,0.18),0_10px_28px_rgba(14,165,233,0.12)]",
      label: "text-sky-200",
      pill: "bg-sky-500/20 text-sky-50 border-sky-300/40 shadow-[0_0_18px_rgba(56,189,248,0.16)]",
      icon: "from-sky-500/24 via-slate-900 to-slate-950 text-sky-50 border-sky-300/38",
      surface: "from-sky-500/14 via-slate-950 to-slate-950",
      accent: "bg-sky-300",
      nameAura: "cfb-name-aura-sky",
      row: "border-l-sky-300/90 bg-sky-400/[0.07] hover:bg-sky-400/[0.13]",
      draftButton: "from-sky-300 via-cyan-400 to-blue-500",
    };
  }
  if (normalized === "RB") {
    return {
      ring: "border-emerald-400/45",
      glow: "shadow-[0_0_0_1px_rgba(52,211,153,0.18),0_10px_28px_rgba(16,185,129,0.12)]",
      label: "text-emerald-200",
      pill: "bg-emerald-500/20 text-emerald-50 border-emerald-300/40 shadow-[0_0_18px_rgba(52,211,153,0.14)]",
      icon: "from-emerald-500/24 via-slate-900 to-slate-950 text-emerald-50 border-emerald-300/38",
      surface: "from-emerald-500/14 via-slate-950 to-slate-950",
      accent: "bg-emerald-300",
      nameAura: "cfb-name-aura-emerald",
      row: "border-l-emerald-300/90 bg-emerald-400/[0.07] hover:bg-emerald-400/[0.13]",
      draftButton: "from-emerald-300 via-lime-300 to-green-500",
    };
  }
  if (normalized === "WR") {
    return {
      ring: "border-violet-400/45",
      glow: "shadow-[0_0_0_1px_rgba(167,139,250,0.18),0_10px_28px_rgba(124,58,237,0.12)]",
      label: "text-violet-200",
      pill: "bg-violet-500/20 text-violet-50 border-violet-300/40 shadow-[0_0_18px_rgba(167,139,250,0.15)]",
      icon: "from-violet-500/24 via-slate-900 to-slate-950 text-violet-50 border-violet-300/38",
      surface: "from-violet-500/14 via-slate-950 to-slate-950",
      accent: "bg-violet-300",
      nameAura: "cfb-name-aura-violet",
      row: "border-l-violet-300/90 bg-violet-400/[0.07] hover:bg-violet-400/[0.13]",
      draftButton: "from-violet-300 via-fuchsia-400 to-purple-500",
    };
  }
  if (normalized === "TE") {
    return {
      ring: "border-amber-400/45",
      glow: "shadow-[0_0_0_1px_rgba(251,191,36,0.16),0_10px_28px_rgba(217,119,6,0.1)]",
      label: "text-amber-200",
      pill: "bg-amber-500/20 text-amber-50 border-amber-300/40 shadow-[0_0_18px_rgba(251,191,36,0.13)]",
      icon: "from-amber-500/24 via-slate-900 to-slate-950 text-amber-50 border-amber-300/38",
      surface: "from-amber-500/13 via-slate-950 to-slate-950",
      accent: "bg-amber-300",
      nameAura: "cfb-name-aura-amber",
      row: "border-l-amber-300/90 bg-amber-400/[0.065] hover:bg-amber-400/[0.12]",
      draftButton: "from-amber-300 via-yellow-300 to-orange-500",
    };
  }
  if (normalized === "K" || normalized === "DEF" || normalized === "D/ST") {
    return {
      ring: "border-rose-400/45",
      glow: "shadow-[0_0_0_1px_rgba(251,113,133,0.16),0_10px_28px_rgba(190,18,60,0.1)]",
      label: "text-rose-200",
      pill: "bg-rose-500/20 text-rose-50 border-rose-300/40 shadow-[0_0_18px_rgba(251,113,133,0.13)]",
      icon: "from-rose-500/24 via-slate-900 to-slate-950 text-rose-50 border-rose-300/38",
      surface: "from-rose-500/13 via-slate-950 to-slate-950",
      accent: "bg-rose-300",
      nameAura: "cfb-name-aura-rose",
      row: "border-l-rose-300/90 bg-rose-400/[0.06] hover:bg-rose-400/[0.115]",
      draftButton: "from-rose-300 via-pink-400 to-slate-300",
    };
  }
  return {
    ring: "border-cyan-400/40",
    glow: "shadow-[0_0_0_1px_rgba(34,211,238,0.14),0_10px_28px_rgba(8,145,178,0.1)]",
    label: "text-cyan-200",
    pill: "bg-cyan-500/18 text-cyan-50 border-cyan-300/38 shadow-[0_0_18px_rgba(34,211,238,0.13)]",
    icon: "from-cyan-500/22 via-slate-900 to-slate-950 text-cyan-50 border-cyan-300/35",
    surface: "from-cyan-500/12 via-slate-950 to-slate-950",
    accent: "bg-cyan-300",
    nameAura: "cfb-name-aura-cyan",
    row: "border-l-cyan-300/85 bg-cyan-400/[0.06] hover:bg-cyan-400/[0.11]",
    draftButton: "from-cyan-300 via-sky-400 to-blue-500",
  };
}

function getAdpSortValue(player: Player) {
  return Number.isFinite(player.sheetAdp as number) && Number(player.sheetAdp) > 0 ? Number(player.sheetAdp) : 9999;
}

function getProjectionSortValue(player: Player) {
  return Number(player.sheetProjectedSeasonPoints || 0);
}

function getPlayerPoolKey(player: Player) {
  return `${normalizePlayerIdentityText(player.name)}|${normalizePlayerPoolPosition(player.pos)}|${normalizePlayerIdentityText(player.school)}`;
}

function getDraftedPlayerPoolKey(pick: DraftRoomPick) {
  return `${normalizePlayerIdentityText(pick.player_name)}|${normalizePlayerPoolPosition(pick.player_position)}|${normalizePlayerIdentityText(pick.player_school)}`;
}

function hasSheetBoardData(player: Player) {
  return getStableRankNumber(player.sheetAdp) !== null || Number(player.sheetProjectedSeasonPoints || 0) > 0;
}

function preferDraftBoardPlayer(current: Player, candidate: Player) {
  const currentHasSheetData = hasSheetBoardData(current);
  const candidateHasSheetData = hasSheetBoardData(candidate);
  if (candidateHasSheetData !== currentHasSheetData) return candidateHasSheetData ? candidate : current;
  const adpGap = getAdpSortValue(candidate) - getAdpSortValue(current);
  if (adpGap !== 0) return adpGap < 0 ? candidate : current;
  const projectionGap = getProjectionSortValue(candidate) - getProjectionSortValue(current);
  if (projectionGap !== 0) return projectionGap > 0 ? candidate : current;
  return candidate.id < current.id ? candidate : current;
}

function comparePlayersByBoardRank(left: Player, right: Player) {
  const adpGap = getAdpSortValue(left) - getAdpSortValue(right);
  if (adpGap !== 0) return adpGap;
  const projectionGap = getProjectionSortValue(right) - getProjectionSortValue(left);
  if (projectionGap !== 0) return projectionGap;
  return left.id - right.id;
}

function comparePlayersBySortMode(left: Player, right: Player, sortMode: SortMode) {
  if (sortMode === "projection") {
    const projectionGap = getProjectionSortValue(right) - getProjectionSortValue(left);
    if (projectionGap !== 0) return projectionGap;
  }
  return comparePlayersByBoardRank(left, right);
}

function hasNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatStatValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function getPositionCoreStats(position: string | null | undefined, summary: PlayerSeasonSummary | undefined) {
  const totals = summary?.totals;
  if (!totals) return [];
  const normalized = normalizePosition(position);
  const stats =
    normalized === "QB"
      ? [
          { label: "Pass Yards", value: totals.passing_yards },
          { label: "Pass TD", value: totals.passing_tds },
          { label: "INT", value: totals.interceptions },
        ]
      : normalized === "RB"
        ? [
            { label: "Rush TD", value: totals.rushing_tds },
            { label: "Rush Yards", value: totals.rushing_yards },
            { label: "Carries", value: totals.rushing_attempts },
          ]
        : normalized === "WR" || normalized === "TE"
          ? [
              { label: "Receptions", value: totals.receptions },
              { label: "Rec Yards", value: totals.receiving_yards },
              { label: "Rec TD", value: totals.receiving_tds },
            ]
          : normalized === "K"
            ? [
                { label: "FG Made", value: totals.field_goals_made },
                { label: "XP Made", value: totals.extra_points_made },
              ]
            : [];

  if (!stats.length) return [];
  const hasRealLine = stats.some((stat) => hasNumber(stat.value) && stat.value > 0);
  if (!hasRealLine) return [];
  return stats.filter((stat) => hasNumber(stat.value));
}

export default function MockDraftBoard() {
  const { mockDraftId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: room, isLoading, error, refetch: refetchRoom } = useMockDraftRoom(parsedMockDraftId, Boolean(parsedMockDraftId));
  useMockDraftRealtime(parsedMockDraftId, Boolean(parsedMockDraftId));
  const pickMutation = useMockDraftPick(parsedMockDraftId);
  const queueSeatId = room?.user_team_id ?? null;
  const { data: queue } = useMockDraftQueue(parsedMockDraftId, queueSeatId, Boolean(parsedMockDraftId));
  const queueAdd = useMockDraftQueueAdd(parsedMockDraftId, queueSeatId);
  const queueRemove = useMockDraftQueueRemove(parsedMockDraftId, queueSeatId);
  const queueClear = useMockDraftQueueClear(parsedMockDraftId, queueSeatId);
  const queueReorder = useMockDraftQueueReorder(parsedMockDraftId, queueSeatId);
  const emailSummary = useMockDraftEmailSummary(parsedMockDraftId);
  const [search, setSearch] = useState("");
  const [positionFilter, setPositionFilter] = useState<PositionFilter>("ALL");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [sortMode, setSortMode] = useState<SortMode>("adp");
  const [activeTab, setActiveTab] = useState<DraftTab>("draft");
  const [pickError, setPickError] = useState<string | null>(null);
  const [displaySecondsRemaining, setDisplaySecondsRemaining] = useState<number>(60);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number | null>(null);
  const [isMobileSheet, setIsMobileSheet] = useState(false);
  const [completionDismissed, setCompletionDismissed] = useState(false);
  const [completionStep, setCompletionStep] = useState<CompletionStep>("ask");
  const [sendToAccountEmail, setSendToAccountEmail] = useState(true);
  const [additionalSummaryEmail, setAdditionalSummaryEmail] = useState("");
  const [summaryEmailError, setSummaryEmailError] = useState<string | null>(null);
  const pickRailRef = useRef<HTMLDivElement | null>(null);
  const isAutoScrollingPickRailRef = useRef(false);
  const autoScrollReleaseRef = useRef<number | null>(null);
  const manuallyScrolledPickRef = useRef<number | null>(null);
  const lastTimeoutRefreshPickRef = useRef<number | null>(null);
  const completedModalSessionRef = useRef<number | null>(null);

  const playerSearch = search.trim();
  const { data: playersPayload, error: playersError, isLoading: playersLoading } = usePlayers({
    search: playerSearch || undefined,
    position: positionFilter === "ALL" ? undefined : positionFilter,
    sort: sortMode === "projection" ? "projection" : "draft_rank",
    limit: 2000,
    season: new Date().getFullYear(),
    week: 1,
  });
  const { data: playerSeasonSummary, isLoading: playerSeasonSummaryLoading } = usePlayerSeasonSummary(
    selectedPlayerId,
    2025,
    selectedPlayerId !== null
  );

  useEffect(() => {
    if (!room) return;
    const fallbackPickTimer = Number(room.pick_timer_seconds || room.current_pick_timer_seconds || DEFAULT_PICK_TIMER_SECONDS);
    const next =
      room.phase_type === "pick_transition"
        ? fallbackPickTimer
        : Number(room.phase_seconds_remaining ?? room.seconds_remaining ?? fallbackPickTimer);
    setDisplaySecondsRemaining(Number.isFinite(next) ? Math.max(0, next) : fallbackPickTimer);
  }, [room]);

  useEffect(() => {
    if (!room || !["countdown", "live"].includes(room.status) || displaySecondsRemaining <= 0) return;
    if (room.phase_type === "pick_transition" || room.phase_type === "auto_picking") return;
    const timer = window.setInterval(() => setDisplaySecondsRemaining((current) => Math.max(0, current - 1)), 1_000);
    return () => window.clearInterval(timer);
  }, [displaySecondsRemaining, room]);

  useEffect(() => {
    if (!room || room.status !== "live" || room.phase_type !== "pick_clock" || displaySecondsRemaining > 0) return;
    if (lastTimeoutRefreshPickRef.current === room.current_pick) return;
    lastTimeoutRefreshPickRef.current = room.current_pick;
    void refetchRoom();
  }, [displaySecondsRemaining, refetchRoom, room]);

  useEffect(() => {
    if (!parsedMockDraftId || !room) return;
    if (room.status === "countdown" && location.pathname !== `/mock-drafts/${parsedMockDraftId}/room`) {
      navigate(`/mock-drafts/${parsedMockDraftId}/room`, { replace: true });
    }
  }, [location.pathname, navigate, parsedMockDraftId, room]);

  useEffect(() => {
    const handleResize = () => {
      setIsMobileSheet(window.innerWidth < MOBILE_BREAKPOINT);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!room?.rosters_by_team.length) return;
    const ids = new Set(room.rosters_by_team.map((entry) => entry.team_id));
    setSelectedRosterTeamId((current) => {
      if (current && ids.has(current)) return current;
      if (room.user_team_id && ids.has(room.user_team_id)) return room.user_team_id;
      return room.rosters_by_team[0]?.team_id ?? null;
    });
  }, [room?.rosters_by_team, room?.user_team_id]);

  useEffect(() => {
    if (!room || room.status !== "completed") return;
    if (completedModalSessionRef.current === room.mock_draft_id) return;
    completedModalSessionRef.current = room.mock_draft_id;
    setActiveTab("draft");
    setCompletionDismissed(false);
    setCompletionStep("ask");
    setSummaryEmailError(null);
  }, [room]);

  const draftedIds = useMemo(() => new Set(room?.picks.map((pick) => pick.player_id) ?? []), [room?.picks]);
  const draftedPlayerKeys = useMemo(() => new Set(room?.picks.map((pick) => getDraftedPlayerPoolKey(pick)) ?? []), [room?.picks]);
  const draftEligiblePlayers = useMemo(() => {
    const rows = playersPayload?.data ?? [];
    const deduped = new Map<string, Player>();
    rows.forEach((player) => {
      if (!["QB", "RB", "WR", "TE", "K"].includes(String(player.pos || "").toUpperCase())) return;
      const key = getPlayerPoolKey(player);
      const current = deduped.get(key);
      deduped.set(key, current ? preferDraftBoardPlayer(current, player) : player);
    });
    return Array.from(deduped.values());
  }, [playersPayload?.data]);

  const allAvailablePlayers = useMemo(() => {
    return [...draftEligiblePlayers]
      .filter((player) => !draftedIds.has(player.id) && !draftedPlayerKeys.has(getPlayerPoolKey(player)))
      .sort((left, right) => comparePlayersBySortMode(left, right, sortMode));
  }, [draftEligiblePlayers, draftedIds, draftedPlayerKeys, sortMode]);

  const baseAvailablePlayers = useMemo(
    () =>
      allAvailablePlayers
        .filter((player) => (positionFilter === "ALL" ? true : String(player.pos || "").toUpperCase() === positionFilter))
        .filter((player) => (teamFilter === "ALL" ? true : player.school === teamFilter)),
    [allAvailablePlayers, positionFilter, teamFilter]
  );

  const availablePlayers = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return baseAvailablePlayers;
    return baseAvailablePlayers.filter((player) => `${player.name} ${player.school}`.toLowerCase().includes(term));
  }, [baseAvailablePlayers, search]);

  const userRoster = useMemo(
    () => room?.rosters_by_team.find((roster) => roster.team_id === room.user_team_id) ?? null,
    [room?.rosters_by_team, room?.user_team_id]
  );
  const phaseLabel = useMemo(() => {
    if (!room) return "Draft Timer";
    if (room.phase_type === "lobby_countdown") return "Seat Fill Timer";
    if (room.phase_type === "prestart_countdown") return "Draft Starts In";
    if (room.phase_type === "pick_transition") return "Pick Confirmed";
    if (room.phase_type === "pick_clock") return "Pick Clock";
    return "Draft Timer";
  }, [room]);
  const currentPhaseClock = formatClock(displaySecondsRemaining);
  const teamOptions = useMemo(
    () => Array.from(new Set((playersPayload?.data ?? []).map((player) => player.school))).sort((left, right) => left.localeCompare(right)),
    [playersPayload?.data]
  );
  const timeline = useMemo(() => (room ? buildDraftTimeline(room) : []), [room]);
  const activeTimelineIndex = useMemo(() => {
    if (!room?.current_pick) return -1;
    return timeline.findIndex((entry) => entry.overallPick === room.current_pick);
  }, [room?.current_pick, timeline]);

  useEffect(() => {
    const rail = pickRailRef.current;
    if (!rail || activeTimelineIndex < 0) return;
    const currentPickForCenter = room?.current_pick ?? null;
    if (manuallyScrolledPickRef.current === currentPickForCenter) return;
    const activeCard = rail.querySelector<HTMLElement>("[data-active-pick='true']");
    if (!activeCard) return;
    const nextLeft = activeCard.offsetLeft - rail.clientWidth / 2 + activeCard.offsetWidth / 2;
    const maxLeft = Math.max(0, rail.scrollWidth - rail.clientWidth);
    isAutoScrollingPickRailRef.current = true;
    if (autoScrollReleaseRef.current !== null) {
      window.clearTimeout(autoScrollReleaseRef.current);
    }
    rail.scrollTo({ left: Math.min(maxLeft, Math.max(0, nextLeft)), behavior: "smooth" });
    manuallyScrolledPickRef.current = null;
    autoScrollReleaseRef.current = window.setTimeout(() => {
      isAutoScrollingPickRailRef.current = false;
      autoScrollReleaseRef.current = null;
    }, 650);
  }, [activeTimelineIndex, room?.current_pick, timeline.length]);

  useEffect(() => {
    return () => {
      if (autoScrollReleaseRef.current !== null) {
        window.clearTimeout(autoScrollReleaseRef.current);
      }
    };
  }, []);

  const recentPicks = useMemo(() => [...(room?.picks ?? [])].sort((left, right) => right.overall_pick - left.overall_pick), [room?.picks]);
  const lastPick = recentPicks[0] ?? null;
  const seatNumberByTeamId = useMemo(() => {
    if (!room) return new Map<number, number>();
    const baseOrder = room.draft_order.length ? room.draft_order : room.teams.map((team) => team.id);
    return new Map(baseOrder.map((teamId, index) => [teamId, index + 1]));
  }, [room]);
  const selectedRoster = useMemo(
    () => room?.rosters_by_team.find((entry) => entry.team_id === selectedRosterTeamId) ?? userRoster ?? null,
    [room?.rosters_by_team, selectedRosterTeamId, userRoster]
  );
  const rosterFilledCount = useMemo(
    () =>
      selectedRoster
        ? Object.entries(selectedRoster.slots).reduce(
            (total, [slot, players]) => total + (DRAFTABLE_ROSTER_SLOT_KEYS.has(getRosterSlotBase(slot)) ? players.length : 0),
            0
          )
        : 0,
    [selectedRoster]
  );
  const rosterCapacity = useMemo(
    () =>
      room
        ? Object.entries(room.roster_slots).reduce(
            (total, [slot, value]) => total + (DRAFTABLE_ROSTER_SLOT_KEYS.has(getRosterSlotBase(slot)) ? Number(value || 0) : 0),
            0
          )
        : 0,
    [room]
  );
  const rosterSlotEntries = useMemo(() => {
    if (!room || !selectedRoster) return [];
    return Object.entries(room.roster_slots)
      .sort(([leftSlot], [rightSlot]) => {
        const leftIndex = ROSTER_SLOT_ORDER.indexOf(getRosterSlotBase(leftSlot));
        const rightIndex = ROSTER_SLOT_ORDER.indexOf(getRosterSlotBase(rightSlot));
        return (leftIndex === -1 ? 999 : leftIndex) - (rightIndex === -1 ? 999 : rightIndex);
      })
      .flatMap(([slot, count]) => {
        const slotCount = Math.max(0, Number(count || 0));
        const players = getRosterSlotBase(slot) === "IR" ? [] : selectedRoster.slots[slot] ?? [];
        return Array.from({ length: slotCount }).map((_, index) => ({
          slot,
          label: getRosterSlotLabel(slot, index, slotCount),
          player: players[index] ?? null,
        }));
      });
  }, [room, selectedRoster]);
  const selectedPlayer =
    useMemo(() => (selectedPlayerId === null ? null : (playersPayload?.data ?? []).find((player) => player.id === selectedPlayerId) ?? null), [
      playersPayload?.data,
      selectedPlayerId,
    ]);
  const selectedPlayerAura = getPositionAura(selectedPlayer?.pos);
  const selectedPlayerCoreStats = useMemo(
    () => getPositionCoreStats(selectedPlayer?.pos, playerSeasonSummary),
    [playerSeasonSummary, selectedPlayer?.pos]
  );
  const isTimerUrgent = room?.phase_type === "pick_clock" && displaySecondsRemaining <= 10 && displaySecondsRemaining >= 0;
  const canDraftNow = Boolean(room?.can_make_pick && displaySecondsRemaining > 0 && room.status !== "completed");
  const draftDisabledReason = useMemo(() => {
    if (!room) return "Draft room is loading.";
    if (room.status === "completed") return "Draft complete.";
    if (!room.can_make_pick) {
      if (room.status === "countdown") return "Draft has not started yet.";
      if (room.phase_type === "pick_transition") return "Previous pick is being finalized.";
      if (room.phase_type === "prestart_countdown") return "Draft is starting shortly.";
      return "You can draft when your team is on the clock.";
    }
    if (displaySecondsRemaining <= 0) return "Pick clock expired. Auto-pick is advancing this turn.";
    return null;
  }, [displaySecondsRemaining, room]);
  const showCompletionModal = Boolean(room?.status === "completed" && !completionDismissed);

  const handlePick = async (playerId: number) => {
    setPickError(null);
    if (!getStoredAccessToken()) {
      setPickError("Your sign-in expired. Sign in again before making a pick.");
      return;
    }
    if (!canDraftNow) {
      setPickError(draftDisabledReason || "Pick is not available right now.");
      void refetchRoom();
      return;
    }
    try {
      await pickMutation.mutateAsync(playerId);
    } catch (err) {
      if (err instanceof ApiError && err.message === POSITION_FULL_PICK_ERROR) {
        setPickError(POSITION_FULL_PICK_ERROR);
        return;
      }
      setPickError(err instanceof Error ? err.message : "Unable to make draft pick.");
    }
  };
  const sendDraftSummary = async () => {
    setSummaryEmailError(null);
    try {
      await emailSummary.mutateAsync({
        send_to_account_email: sendToAccountEmail,
        additional_email: additionalSummaryEmail.trim() || null,
      });
      setCompletionStep("sent");
    } catch (err) {
      setSummaryEmailError(err instanceof Error ? err.message : "Unable to send draft history.");
    }
  };
  const exitMockDraft = () => {
    setCompletionDismissed(true);
    navigate("/mock-drafts");
  };
  const moveQueueItem = async (playerId: number, direction: -1 | 1) => {
    if (!queue?.data.length) return;
    const currentIndex = queue.data.findIndex((item) => item.player_id === playerId);
    if (currentIndex < 0) return;
    const targetIndex = currentIndex + direction;
    if (targetIndex < 0 || targetIndex >= queue.data.length) return;
    const next = [...queue.data];
    const [row] = next.splice(currentIndex, 1);
    next.splice(targetIndex, 0, row);
    await queueReorder.mutateAsync(next.map((item) => item.player_id));
  };

  if (!parsedMockDraftId) {
    return <div className="py-16 text-center text-sm font-semibold uppercase tracking-[0.2em] text-red-300">Invalid mock draft id.</div>;
  }

  if (isLoading) {
    return (
      <div className="py-16 flex items-center justify-center gap-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        Loading mock draft board...
      </div>
    );
  }

  if (!room) {
    return <div className="py-16 text-center text-sm font-semibold uppercase tracking-[0.2em] text-red-300">{error instanceof Error ? error.message : "Mock draft board unavailable."}</div>;
  }

  return (
    <div className="relative mx-auto max-w-[1480px] pb-32 pt-4">
      <div className="pointer-events-none absolute -left-12 top-6 h-40 w-40 rounded-full bg-primary/7 blur-[90px]" />
      <div className="pointer-events-none absolute right-10 top-14 h-32 w-32 rounded-full bg-violet-300/7 blur-[70px]" />
      <Card className="cfb-panel-strong overflow-hidden rounded-[1.4rem] border-primary/10 bg-card/60">
        <CardHeader className="space-y-0 border-b border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.12),transparent_24%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.08),transparent_22%),linear-gradient(180deg,rgba(16,25,44,0.98),rgba(10,16,31,0.96))] p-0">
          <div className="grid items-center gap-4 px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:px-6">
            <div className="flex min-w-0 items-center gap-4">
              <Button
                variant="ghost"
                className="h-11 w-11 shrink-0 rounded-xl border border-cyan-200/16 bg-cyan-300/9 p-0 text-cyan-200 hover:bg-cyan-300/15"
                onClick={() => navigate(`/mock-drafts/${parsedMockDraftId}/room`)}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="min-w-0">
                <CardTitle className="truncate text-2xl font-semibold uppercase tracking-normal text-white md:text-3xl">
                  Mock Draft Board
                </CardTitle>
                <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.2em] text-primary/75">
                  Power 4 • {room.mode === "single_player" ? "Single Player" : "Public Multiplayer"}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-center">
              <div
                className={[
                  "rounded-[1.05rem] border px-6 py-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] transition-all duration-300",
                  isTimerUrgent
                    ? "cfb-draft-timer-urgent border-red-300/35 bg-red-500/12"
                    : "border-cyan-200/14 bg-white/[0.06]",
                ].join(" ")}
              >
                <p className={["text-[9px] font-semibold uppercase tracking-[0.18em]", isTimerUrgent ? "text-red-100/85" : "text-cyan-100/70"].join(" ")}>
                  {room.status === "live" ? room.current_team_name || phaseLabel : phaseLabel}
                </p>
                <p className={["mt-1 text-3xl font-semibold leading-none tabular-nums md:text-4xl", isTimerUrgent ? "text-red-100" : "text-white"].join(" ")}>
                  {currentPhaseClock}
                </p>
              </div>
            </div>

            <div className="hidden min-w-0 text-right md:block">
              <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">On the Clock</p>
              <p className="mt-1 truncate text-sm font-semibold text-cyan-100">{room.current_team_name || "Awaiting Pick"}</p>
            </div>
          </div>

          <div className="border-t border-white/10 bg-[linear-gradient(180deg,rgba(8,17,31,0.65),rgba(8,17,31,0.35))] px-4 py-4 md:px-6">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.12em] text-white">Draft Order</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-primary/75">
                  {room.teams.length} Managers • {room.total_rounds} Rounds
                </p>
              </div>
              <div className="text-right">
                <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">Current Pick</p>
                <p className="mt-1 text-base font-semibold text-cyan-200">Round {room.current_round} • Pick {room.current_round_pick}</p>
              </div>
            </div>
            <div
              ref={pickRailRef}
              className="overflow-x-auto overscroll-x-contain scroll-smooth pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              onScroll={() => {
                if (isAutoScrollingPickRailRef.current) return;
                manuallyScrolledPickRef.current = room.current_pick ?? null;
              }}
            >
              <div className="flex min-w-max gap-3 pr-8">
                {timeline.map((entry, index) => {
                  const isActive = index === activeTimelineIndex;
                  const isCompleted = Boolean(entry.pick);
                  const aura = getPositionAura(entry.pick?.player_position);
                  const compactLabel = getCompactSeatLabel(entry.team, seatNumberByTeamId.get(entry.teamId) ?? null);
                  const pickRevealText = entry.pick?.player_name ?? "";
                  return (
                    <div
                      key={`${entry.overallPick}-${entry.teamId}`}
                      data-active-pick={isActive ? "true" : undefined}
                      className="w-[126px] shrink-0 sm:w-[136px]"
                    >
                      <div
                        className={[
                          "relative flex h-full min-h-[118px] flex-col overflow-hidden rounded-xl border px-3 py-3 transition-all duration-300",
                          isActive
                            ? "scale-[1.025] border-cyan-200/25 bg-[linear-gradient(180deg,rgba(56,189,248,0.11),rgba(15,23,42,0.88))] shadow-[0_12px_28px_rgba(34,211,238,0.12)]"
                            : isCompleted
                              ? `${aura.ring} bg-white/[0.045] ${aura.glow}`
                              : "border-white/7 bg-[#0d1121]/88",
                        ].join(" ")}
                      >
                        {!pickRevealText ? (
                          <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-3 pb-7">
                            <span
                              className={[
                                "block max-w-full truncate text-center text-2xl font-semibold uppercase tracking-normal leading-none sm:text-3xl",
                                isActive ? "text-cyan-100/62 drop-shadow-[0_0_10px_rgba(34,211,238,0.14)]" : "text-slate-400/48",
                              ].join(" ")}
                            >
                              {compactLabel}
                            </span>
                          </div>
                        ) : null}
                        {pickRevealText ? (
                          <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-3 pb-3">
                            <span className="block max-w-full truncate text-center text-3xl font-semibold uppercase leading-none text-slate-300/34 drop-shadow-[0_0_12px_rgba(125,211,252,0.1)] sm:text-4xl">
                              {compactLabel}
                            </span>
                          </div>
                        ) : null}
                        <div className="relative z-10 min-h-[46px]">
                          {pickRevealText ? (
                            <p className={`truncate text-[10px] font-semibold uppercase tracking-[0.12em] ${aura.label}`}>
                              {pickRevealText}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex-1" />
                        <div className="relative z-10 mt-4 flex items-center justify-center">
                          <span className={["h-2.5 w-2.5 rounded-full", isActive ? "bg-cyan-100/75 shadow-[0_0_10px_rgba(34,211,238,0.34)]" : isCompleted ? aura.label.replace("text-", "bg-") : "bg-transparent"].join(" ")} />
                        </div>
                        <p className="relative z-10 mt-3 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                          {entry.round}.{entry.roundPick}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            {lastPick ? (
              <div className="mx-auto mt-3 flex max-w-xl items-center justify-center gap-2 rounded-full border border-cyan-200/10 bg-cyan-300/[0.055] px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-300">
                <Zap className="h-3.5 w-3.5 text-cyan-200/80" />
                <span className="text-slate-500">Last Pick</span>
                <span className="truncate text-cyan-100">{lastPick.player_name}</span>
                <span className="text-slate-500">to {lastPick.team_name}</span>
              </div>
            ) : null}
          </div>
        </CardHeader>

        <CardContent className="bg-transparent p-0">
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as DraftTab)} className="space-y-5">
            <div className="px-4 pt-4 md:px-6">
              {pickError ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-red-400/25 bg-red-500/10 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-red-200">
                  <CircleAlert className="h-3.5 w-3.5" />
                  {pickError}
                </div>
              ) : null}
            </div>

            <TabsContent value="draft" className="space-y-6 px-4 pb-32 pt-5 md:px-6">
              <div className="grid items-center gap-4">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-100/55" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search players, schools, positions..."
                    className="cfb-draft-search-input h-12 rounded-xl pl-12 text-sm font-medium"
                  />
                </div>
              </div>

              <div className="cfb-panel overflow-hidden rounded-[1.25rem] border-white/10 bg-card/45">
                <div className="grid grid-cols-[56px_minmax(0,1.9fr)_84px_92px_92px_84px_172px] gap-3 border-b border-white/7 px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <span>Pick</span>
                  <span>Player</span>
                  <span>Pos</span>
                  <span>ADP</span>
                  <span>Proj</span>
                  <span>ROS</span>
                  <span className="text-right">Action</span>
                </div>
                {playersLoading ? (
                  <div className="flex items-center justify-center gap-3 py-10 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    Loading board...
                  </div>
                ) : playersError ? (
                  <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                    <CircleAlert className="h-7 w-7 text-red-200" />
                    <div>
                      <p className="text-sm font-semibold text-slate-100">Unable to load player pool.</p>
                      <p className="mt-2 max-w-xl text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Make sure the FastAPI backend is running on port 8000 and the player import has completed.
                      </p>
                    </div>
                  </div>
                ) : availablePlayers.length === 0 ? (
                  <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                    <Search className="h-7 w-7 text-cyan-100/60" />
                    <div>
                      <p className="text-sm font-semibold text-slate-100">
                        {(playersPayload?.total ?? 0) === 0 ? "No players have been imported yet." : "No available players match this search."}
                      </p>
                      <p className="mt-2 max-w-2xl text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        {(playersPayload?.total ?? 0) === 0
                          ? "Run the Google Sheet import script to seed the draft player pool, then refresh this draft room."
                          : "Clear the search or position filter to bring players back into the board."}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="max-h-[780px] overflow-y-auto pb-24">
                    {availablePlayers.map((player, index) => {
                      const position = normalizePosition(player.pos);
                      const aura = getPositionAura(position);
                      const eligibility = room.position_eligibility[position];
                      const disabledReason = eligibility && !eligibility.can_draft ? eligibility.reason || "Roster full for this position" : null;
                      const queued = Boolean(queue?.data.some((row) => row.player_id === player.id));
                      const projectedPickNumber = room.current_pick + index;
                      return (
                        <div
                          key={player.id}
                          role="button"
                          tabIndex={0}
                          className={[
                            "relative grid w-full grid-cols-[56px_minmax(0,1.9fr)_84px_92px_92px_84px_172px] items-center gap-3 overflow-hidden border-t px-4 py-3.5 pl-5 text-left transition-colors",
                            "border-white/6 bg-gradient-to-r",
                            aura.surface,
                            "hover:bg-white/[0.07]",
                          ].join(" ")}
                          onClick={() => setSelectedPlayerId(player.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedPlayerId(player.id);
                            }
                          }}
                        >
                          <span className={`absolute left-0 top-0 h-full w-1 ${aura.accent} opacity-75 shadow-[0_0_18px_currentColor]`} />
                          <div className="text-lg font-semibold tabular-nums text-slate-100/90">{projectedPickNumber}</div>
                          <div className="min-w-0">
                            <div className="flex min-w-0 items-center gap-2">
                              <span className={`h-2 w-2 shrink-0 rounded-full ${aura.accent} shadow-[0_0_12px_currentColor]`} />
                              <p className={["truncate text-base font-semibold text-slate-50 cfb-position-name-aura", aura.nameAura].join(" ")}>
                                {player.name}
                              </p>
                            </div>
                            <p className="mt-0.5 truncate text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                              {player.school}
                            </p>
                            {disabledReason ? (
                              <p className="mt-1 inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-amber-200">
                                <Lock className="h-3 w-3" />
                                {disabledReason}
                              </p>
                            ) : null}
                          </div>
                          <div className="text-sm font-semibold">
                            <span className={`inline-flex min-w-[54px] items-center justify-center rounded-full border px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] ${aura.pill}`}>
                              {position}
                            </span>
                          </div>
                          <div>
                            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">ADP</p>
                            <p className="mt-0.5 text-sm font-semibold text-white">
                              {Number.isFinite(player.sheetAdp as number) ? Number(player.sheetAdp).toFixed(1) : "--"}
                            </p>
                          </div>
                          <div>
                            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">PROJ</p>
                            <p className="mt-0.5 text-sm font-semibold text-white">{Math.round(Number(player.sheetProjectedSeasonPoints || 0))}</p>
                          </div>
                          <div>
                            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">ROS</p>
                            <p className="mt-0.5 text-sm font-semibold text-white">100%</p>
                          </div>
                          <div className="flex items-center justify-end gap-2" onClick={(event) => event.stopPropagation()}>
                            <Button
                              variant="outline"
                              className="h-9 rounded-full border-white/10 bg-transparent px-4 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400 hover:bg-white/[0.06] hover:text-white"
                              disabled={queueAdd.isPending || queued}
                              onClick={() => queueAdd.mutate(player.id)}
                            >
                              {queued ? "Queued" : "Queue"}
                            </Button>
                            <Button
                              className="h-9 rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 px-5 text-[9px] font-bold uppercase tracking-[0.14em] text-slate-950 shadow-[0_12px_26px_rgba(14,165,233,0.18)] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45"
                              disabled={pickMutation.isPending || Boolean(disabledReason) || !canDraftNow}
                              title={disabledReason || draftDisabledReason || undefined}
                              onClick={() => void handlePick(player.id)}
                            >
                              Draft
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="queue" className="space-y-4 px-4 pb-32 md:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-foreground">My Queue</p>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Reorder your next auto-pick priorities
                  </p>
                </div>
                <Button
                  variant="outline"
                  className="h-10 rounded-xl text-[10px] font-semibold uppercase tracking-[0.16em]"
                  onClick={() => queueClear.mutate()}
                  disabled={queueClear.isPending || !queue?.data.length}
                >
                  Clear Queue
                </Button>
              </div>

              <div className="space-y-3">
                {queue?.data.length ? queue.data.map((item, index) => (
                  <div key={item.id} className="flex items-center justify-between gap-4 rounded-[1.35rem] border border-white/10 bg-white/[0.03] px-4 py-4">
                    <div className="flex items-center gap-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-cyan-100">
                        {item.priority}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground">{item.player_name}</p>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                          {item.player_position} • {item.player_school}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        className="h-10 rounded-xl px-3"
                        onClick={() => void moveQueueItem(item.player_id, -1)}
                        disabled={queueReorder.isPending || index === 0}
                      >
                        <ArrowUp className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        className="h-10 rounded-xl px-3"
                        onClick={() => void moveQueueItem(item.player_id, 1)}
                        disabled={queueReorder.isPending || index === queue.data.length - 1}
                      >
                        <ArrowDown className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        className="h-10 rounded-xl text-red-200"
                        onClick={() => queueRemove.mutate(item.player_id)}
                        disabled={queueRemove.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )) : (
                  <div className="rounded-[1.5rem] border border-dashed border-white/10 bg-slate-950/40 px-4 py-10 text-center">
                    <p className="text-sm font-semibold text-foreground">Queue is empty.</p>
                    <p className="mt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Add players from the Players tab before the clock reaches auto-pick.
                    </p>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="roster" className="space-y-4 px-4 pb-32 md:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-foreground">Team Rosters</p>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Position slots and current fills
                  </p>
                </div>
                <Select
                  value={selectedRosterTeamId ? String(selectedRosterTeamId) : undefined}
                  onValueChange={(value) => setSelectedRosterTeamId(Number(value))}
                >
                  <SelectTrigger className="cfb-control h-11 w-[240px] rounded-2xl text-[10px] font-semibold uppercase tracking-[0.16em]">
                    <SelectValue placeholder="Select roster" />
                  </SelectTrigger>
                  <SelectContent>
                    {(room.rosters_by_team ?? []).map((roster) => (
                      <SelectItem key={roster.team_id} value={String(roster.team_id)}>
                        {roster.team_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="cfb-panel rounded-[2rem] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">Roster Progress</p>
                    <p className="mt-1 text-sm font-semibold text-foreground">{selectedRoster?.team_name || "Roster"}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-semibold text-white">{rosterFilledCount}/{rosterCapacity || 0}</p>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Slots Filled</p>
                  </div>
                </div>
              </div>

              {selectedRoster ? (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {rosterSlotEntries.map(({ slot, label, player }) => {
                    const slotAura = getPositionAura(slot);
                    const isIrSlot = getRosterSlotBase(slot) === "IR";
                    return (
                      <button
                        key={label}
                        type="button"
                        className={[
                          "relative flex min-h-[68px] w-full items-center gap-3 rounded-[1.05rem] border px-4 py-3 text-left transition-all",
                          player
                            ? `${slotAura.ring} bg-gradient-to-r ${slotAura.surface} ${slotAura.glow} hover:brightness-110`
                            : isIrSlot
                              ? "border-slate-500/20 bg-slate-950/22 opacity-60"
                              : `${slotAura.ring} bg-slate-950/30 opacity-78 hover:opacity-95`,
                        ].join(" ")}
                        onClick={() => player && setSelectedPlayerId(player.player_id)}
                        disabled={!player}
                      >
                        <span className={`absolute left-3 top-2 rounded-md border px-2 py-0.5 text-[8px] font-semibold uppercase tracking-[0.12em] ${slotAura.pill}`}>
                          {label}
                        </span>
                        <span className="min-w-0 flex-1 pt-4">
                          <span className={player ? "block truncate text-sm font-semibold text-foreground" : "block truncate text-sm font-semibold text-slate-500"}>
                            {player ? player.player_name : isIrSlot ? "IR unavailable in draft" : "Empty"}
                          </span>
                          <span className="mt-1 block truncate text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                            {player ? `${player.position} • ${player.school}` : isIrSlot ? "Not counted toward rounds" : "Ready to fill"}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-[1.5rem] border border-dashed border-white/10 bg-slate-950/40 px-4 py-10 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  No roster entries yet.
                </div>
              )}
            </TabsContent>

            <TabsContent value="history" className="space-y-4 px-4 pb-32 md:px-6">
              <div>
                <p className="text-lg font-semibold text-foreground">Draft History</p>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Completed picks in reverse order
                </p>
              </div>
              <div className="cfb-panel overflow-hidden rounded-[2rem] border-white/10 bg-card/55">
                <div className="grid grid-cols-[90px_minmax(0,1.3fr)_110px_1fr] gap-3 border-b border-white/10 bg-white/[0.05] px-5 py-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-300">
                  <span>Pick</span>
                  <span>Player</span>
                  <span>Pos</span>
                  <span>Team</span>
                </div>
                <div className="max-h-[62vh] overflow-y-auto">
                  {recentPicks.length ? recentPicks.map((pick) => {
                    const aura = getPositionAura(pick.player_position);
                    return (
                      <div key={pick.id} className="grid grid-cols-[90px_minmax(0,1.3fr)_110px_1fr] gap-3 border-b border-white/5 bg-white/[0.02] px-5 py-4 even:bg-white/[0.04]">
                        <div className="text-sm font-semibold text-slate-200">R{pick.round_number}.{pick.round_pick}</div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">{pick.player_name}</p>
                          <p className="truncate text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                            {pick.player_school}
                          </p>
                        </div>
                        <div className="text-sm font-semibold">
                          <span className={`inline-flex rounded-full border px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.12em] ${aura.pill}`}>
                            {pick.player_position}
                          </span>
                        </div>
                        <div className="truncate text-sm font-semibold text-slate-300">{pick.team_name}</div>
                      </div>
                    );
                  }) : (
                    <div className="px-5 py-10 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      No picks yet.
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            <div className="fixed bottom-4 left-1/2 z-[300] w-[min(calc(100%-1.5rem),980px)] -translate-x-1/2 rounded-2xl border border-cyan-200/10 bg-[linear-gradient(180deg,rgba(8,17,31,0.94),rgba(8,17,31,0.985))] p-1.5 shadow-[0_18px_50px_rgba(0,0,0,0.48),0_0_30px_rgba(34,211,238,0.08)] backdrop-blur-xl">
              <TabsList className="grid h-auto w-full grid-cols-4 rounded-xl border-0 bg-transparent p-0 shadow-none">
                <TabsTrigger value="draft" className="rounded-xl border border-transparent py-2.5 text-[9px] font-semibold uppercase tracking-[0.12em] data-[state=active]:border-cyan-300/30 data-[state=active]:bg-cyan-300/[0.08] data-[state=active]:text-cyan-100">
                  <div className="flex flex-col items-center gap-1">
                    <Star className="h-4 w-4" />
                    <span>Draft</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger value="queue" className="rounded-xl border border-transparent py-2.5 text-[9px] font-semibold uppercase tracking-[0.12em] data-[state=active]:border-cyan-300/30 data-[state=active]:bg-cyan-300/[0.08] data-[state=active]:text-cyan-100">
                  <div className="flex flex-col items-center gap-1">
                    <ClipboardList className="h-4 w-4" />
                    <span>Queue</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger
                  value="roster"
                  className="rounded-xl border border-transparent py-2.5 text-[9px] font-semibold uppercase tracking-[0.12em] data-[state=active]:border-cyan-300/30 data-[state=active]:bg-cyan-300/[0.08] data-[state=active]:text-cyan-100"
                >
                  <div className="flex flex-col items-center gap-1">
                    <ClipboardList className="h-4 w-4" />
                    <span>Roster</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger
                  value="history"
                  className="rounded-xl border border-transparent py-2.5 text-[9px] font-semibold uppercase tracking-[0.12em] data-[state=active]:border-cyan-300/30 data-[state=active]:bg-cyan-300/[0.08] data-[state=active]:text-cyan-100"
                >
                  <div className="flex flex-col items-center gap-1">
                    <Trophy className="h-4 w-4" />
                    <span>History</span>
                  </div>
                </TabsTrigger>
              </TabsList>
            </div>
          </Tabs>
        </CardContent>
      </Card>

      {showCompletionModal ? (
        <div className="fixed inset-0 z-[180] flex items-center justify-center bg-slate-950/72 px-4 backdrop-blur-xl">
          <div className="w-full max-w-[520px] overflow-hidden rounded-[1.6rem] border border-cyan-200/16 bg-[linear-gradient(180deg,rgba(15,23,42,0.98),rgba(8,17,31,0.98))] p-6 text-center shadow-[0_24px_80px_rgba(0,0,0,0.48),0_0_40px_rgba(34,211,238,0.12)]">
            <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-300/[0.08] text-cyan-100">
              <Trophy className="h-5 w-5" />
            </div>
            {completionStep === "ask" ? (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200/80">Mock Draft Complete</p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Want to send this draft to your email?</h2>
                <p className="mt-3 text-sm font-medium leading-6 text-slate-400">
                  Draft history is ready. Send the completed pick log before exiting.
                </p>
                <div className="mt-6 grid grid-cols-2 gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 rounded-xl text-[10px] font-semibold uppercase tracking-[0.16em]"
                    onClick={exitMockDraft}
                  >
                    No
                  </Button>
                  <Button
                    type="button"
                    className="h-11 rounded-xl bg-cyan-300 text-slate-950 text-[10px] font-bold uppercase tracking-[0.16em] hover:bg-cyan-200"
                    onClick={() => setCompletionStep("email")}
                  >
                    Yes
                  </Button>
                </div>
              </>
            ) : completionStep === "email" ? (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200/80">Email Draft History</p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Choose where to send it</h2>
                <div className="mt-5 space-y-3 text-left">
                  <button
                    type="button"
                    className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-sm font-semibold transition-all ${
                      sendToAccountEmail
                        ? "border-cyan-300/35 bg-cyan-300/[0.08] text-cyan-50"
                        : "border-white/10 bg-white/[0.035] text-slate-400"
                    }`}
                    onClick={() => setSendToAccountEmail((value) => !value)}
                  >
                    <span>Account email</span>
                    <span className="truncate pl-4 text-xs text-slate-400">{user?.email || "No account email"}</span>
                  </button>
                  <Input
                    type="email"
                    value={additionalSummaryEmail}
                    onChange={(event) => setAdditionalSummaryEmail(event.target.value)}
                    placeholder="Another email address"
                    className="cfb-draft-search-input h-11 rounded-xl text-sm"
                  />
                </div>
                {summaryEmailError ? (
                  <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-red-200">{summaryEmailError}</p>
                ) : null}
                <div className="mt-6 grid grid-cols-2 gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 rounded-xl text-[10px] font-semibold uppercase tracking-[0.16em]"
                    onClick={() => setCompletionStep("ask")}
                  >
                    Back
                  </Button>
                  <Button
                    type="button"
                    className="h-11 rounded-xl bg-cyan-300 text-slate-950 text-[10px] font-bold uppercase tracking-[0.16em] hover:bg-cyan-200"
                    disabled={emailSummary.isPending}
                    onClick={() => void sendDraftSummary()}
                  >
                    {emailSummary.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200/80">Draft History Sent</p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">Your mock draft is saved</h2>
                <p className="mt-3 text-sm font-medium leading-6 text-slate-400">
                  The completed pick log was sent to the selected email destination.
                </p>
                <Button
                  type="button"
                  className="mt-6 h-11 w-full rounded-xl bg-cyan-300 text-slate-950 text-[10px] font-bold uppercase tracking-[0.16em] hover:bg-cyan-200"
                  onClick={exitMockDraft}
                >
                  Exit Draft
                </Button>
              </>
            )}
          </div>
        </div>
      ) : null}

      <Sheet open={selectedPlayerId !== null} onOpenChange={(open) => !open && setSelectedPlayerId(null)}>
        <SheetContent
          side={isMobileSheet ? "bottom" : "right"}
          className="z-[220] h-screen overflow-y-auto border-white/10 bg-[#08111f] p-0 text-foreground sm:max-w-[560px]"
        >
          {selectedPlayer ? (
            <div className="space-y-6">
              <div className={`border-b bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_30%),radial-gradient(circle_at_top_right,rgba(167,139,250,0.13),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(8,17,31,0.98))] px-6 pb-8 pt-14 ${selectedPlayerAura.ring}`}>
                <SheetHeader className="space-y-3 text-left">
                  <div className="flex items-start gap-4 pr-10">
                    <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border bg-gradient-to-br text-base font-semibold uppercase ${selectedPlayerAura.icon} ${selectedPlayerAura.glow}`}>
                      {normalizePosition(selectedPlayer.pos).slice(0, 2)}
                    </div>
                    <SheetTitle className={`cfb-player-card-name min-w-0 break-words text-2xl font-bold leading-tight text-slate-100/95 ${selectedPlayerAura.nameAura}`}>
                      {selectedPlayer.name}
                    </SheetTitle>
                  </div>
                  <SheetDescription className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                    {selectedPlayer.school} • {normalizePosition(selectedPlayer.pos)}
                    {selectedPlayer.playerClass ? ` • ${selectedPlayer.playerClass}` : ""}
                  </SheetDescription>
                </SheetHeader>

                <div className="mt-6 grid grid-cols-3 gap-3">
                  <div className="rounded-xl border border-cyan-200/10 bg-white/[0.055] p-4 text-center">
                    <p className="text-2xl font-semibold text-white">
                      {Number.isFinite(selectedPlayer.sheetAdp as number) ? Number(selectedPlayer.sheetAdp).toFixed(1) : "--"}
                    </p>
                    <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">ADP</p>
                  </div>
                  <div className="rounded-xl border border-cyan-200/10 bg-white/[0.055] p-4 text-center">
                    <p className="text-2xl font-semibold text-white">{Number(selectedPlayer.sheetProjectedSeasonPoints || 0).toFixed(1)}</p>
                    <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">Projection</p>
                  </div>
                  <div className="rounded-xl border border-cyan-200/10 bg-white/[0.055] p-4 text-center">
                    <p className="text-2xl font-semibold text-white">{selectedPlayer.projection.floor?.toFixed(1) ?? "--"}</p>
                    <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">Floor</p>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    className="rounded-lg border-white/15 bg-white/[0.055] text-[10px] font-semibold uppercase tracking-[0.14em] hover:bg-white/[0.09]"
                    disabled={queueAdd.isPending || Boolean(queue?.data.some((row) => row.player_id === selectedPlayer.id))}
                    onClick={() => queueAdd.mutate(selectedPlayer.id)}
                  >
                    <Plus className="mr-1 h-3.5 w-3.5" />
                    Add to Queue
                  </Button>
                  <Button
                    className="rounded-lg bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-950 shadow-[0_12px_28px_rgba(14,165,233,0.18)] hover:brightness-110"
                    disabled={
                      pickMutation.isPending ||
                      !room.can_make_pick ||
                      Boolean(
                        room.position_eligibility[normalizePosition(selectedPlayer.pos)] &&
                          !room.position_eligibility[normalizePosition(selectedPlayer.pos)].can_draft
                      )
                    }
                    onClick={() => void handlePick(selectedPlayer.id)}
                  >
                    Draft Player
                  </Button>
                </div>
              </div>

              <div className="space-y-5 px-6 pb-8">
                <div className="rounded-[1.05rem] border border-white/10 bg-white/[0.045] p-5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">Outlook</p>
                  <p className="mt-3 text-sm leading-7 text-slate-200">
                    {playerSeasonSummary?.latest_news ||
                      selectedPlayer.analysis ||
                      `${selectedPlayer.name} profiles as a high-priority ${normalizePosition(selectedPlayer.pos)} for ${selectedPlayer.school}.`}
                  </p>
                </div>

                {playerSeasonSummaryLoading || selectedPlayerCoreStats.length ? (
                  <div className={`rounded-[1.05rem] border bg-gradient-to-br ${selectedPlayerAura.surface} p-5 ${selectedPlayerAura.ring}`}>
                    <div className="mb-4 flex items-center gap-2">
                      <Trophy className={`h-4 w-4 ${selectedPlayerAura.label}`} />
                      <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${selectedPlayerAura.label}`}>Core Stats</p>
                    </div>
                    {playerSeasonSummaryLoading ? (
                      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading player detail...
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-3">
                        {selectedPlayerCoreStats.map((stat) => (
                          <div key={stat.label} className={`rounded-lg border bg-black/35 p-3 ${selectedPlayerAura.ring}`}>
                            <p className="text-xl font-semibold text-white">{formatStatValue(stat.value)}</p>
                            <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">{stat.label}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="rounded-[1.05rem] border border-white/10 bg-white/[0.045] p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-slate-300" />
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">Roster Fit</p>
                  </div>
                  {room.position_eligibility[normalizePosition(selectedPlayer.pos)]?.can_draft ? (
                    <p className="text-sm text-emerald-200">
                      Draftable now • destination {room.position_eligibility[normalizePosition(selectedPlayer.pos)]?.destination_slot || "available"}
                    </p>
                  ) : (
                    <p className="text-sm text-amber-200">
                      {room.position_eligibility[normalizePosition(selectedPlayer.pos)]?.reason || "Roster full for this position"}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
