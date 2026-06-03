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

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
  useMockDraftQueueRemove,
  useMockDraftQueueReorder,
  useMockDraftRealtime,
  useMockDraftRoom,
} from "@/hooks/use-mock-draft";
import { usePlayerSeasonSummary, usePlayers, type PlayerSeasonSummary } from "@/hooks/use-players";
import { ApiError } from "@/lib/api";
import type { DraftRoomPick, DraftRoomTeam } from "@/types/draft";
import type { MockDraftRoom as MockDraftRoomType } from "@/types/mock-draft";

const POSITION_FULL_PICK_ERROR = "You cannot draft this position because your roster has no available slot for it.";

type PositionFilter = "ALL" | "QB" | "RB" | "WR" | "TE" | "K";
type SortMode = "adp" | "projection";
type DraftTab = "draft" | "queue" | "roster";

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
      pill: "bg-sky-500/14 text-sky-100 border-sky-300/28",
      icon: "from-sky-500/18 via-slate-900 to-slate-950 text-sky-100 border-sky-300/28",
      surface: "from-sky-500/9 via-slate-950 to-slate-950",
      row: "border-l-sky-300/90 bg-sky-400/[0.07] hover:bg-sky-400/[0.13]",
      draftButton: "from-sky-300 via-cyan-400 to-blue-500",
    };
  }
  if (normalized === "RB") {
    return {
      ring: "border-emerald-400/45",
      glow: "shadow-[0_0_0_1px_rgba(52,211,153,0.18),0_10px_28px_rgba(16,185,129,0.12)]",
      label: "text-emerald-200",
      pill: "bg-emerald-500/14 text-emerald-100 border-emerald-300/28",
      icon: "from-emerald-500/18 via-slate-900 to-slate-950 text-emerald-100 border-emerald-300/28",
      surface: "from-emerald-500/9 via-slate-950 to-slate-950",
      row: "border-l-emerald-300/90 bg-emerald-400/[0.07] hover:bg-emerald-400/[0.13]",
      draftButton: "from-emerald-300 via-lime-300 to-green-500",
    };
  }
  if (normalized === "WR") {
    return {
      ring: "border-violet-400/45",
      glow: "shadow-[0_0_0_1px_rgba(167,139,250,0.18),0_10px_28px_rgba(124,58,237,0.12)]",
      label: "text-violet-200",
      pill: "bg-violet-500/14 text-violet-100 border-violet-300/28",
      icon: "from-violet-500/18 via-slate-900 to-slate-950 text-violet-100 border-violet-300/28",
      surface: "from-violet-500/9 via-slate-950 to-slate-950",
      row: "border-l-violet-300/90 bg-violet-400/[0.07] hover:bg-violet-400/[0.13]",
      draftButton: "from-violet-300 via-fuchsia-400 to-purple-500",
    };
  }
  if (normalized === "TE") {
    return {
      ring: "border-amber-400/45",
      glow: "shadow-[0_0_0_1px_rgba(251,191,36,0.16),0_10px_28px_rgba(217,119,6,0.1)]",
      label: "text-amber-200",
      pill: "bg-amber-500/14 text-amber-100 border-amber-300/28",
      icon: "from-amber-500/18 via-slate-900 to-slate-950 text-amber-100 border-amber-300/28",
      surface: "from-amber-500/8 via-slate-950 to-slate-950",
      row: "border-l-amber-300/90 bg-amber-400/[0.065] hover:bg-amber-400/[0.12]",
      draftButton: "from-amber-300 via-yellow-300 to-orange-500",
    };
  }
  if (normalized === "K" || normalized === "DEF" || normalized === "D/ST") {
    return {
      ring: "border-rose-400/45",
      glow: "shadow-[0_0_0_1px_rgba(251,113,133,0.16),0_10px_28px_rgba(190,18,60,0.1)]",
      label: "text-rose-200",
      pill: "bg-rose-500/14 text-rose-100 border-rose-300/28",
      icon: "from-rose-500/18 via-slate-900 to-slate-950 text-rose-100 border-rose-300/28",
      surface: "from-rose-500/8 via-slate-950 to-slate-950",
      row: "border-l-rose-300/90 bg-rose-400/[0.06] hover:bg-rose-400/[0.115]",
      draftButton: "from-rose-300 via-pink-400 to-slate-300",
    };
  }
  return {
    ring: "border-cyan-400/40",
    glow: "shadow-[0_0_0_1px_rgba(34,211,238,0.14),0_10px_28px_rgba(8,145,178,0.1)]",
    label: "text-cyan-200",
    pill: "bg-cyan-500/12 text-cyan-100 border-cyan-300/25",
    icon: "from-cyan-500/16 via-slate-900 to-slate-950 text-cyan-100 border-cyan-300/25",
    surface: "from-cyan-500/8 via-slate-950 to-slate-950",
    row: "border-l-cyan-300/85 bg-cyan-400/[0.06] hover:bg-cyan-400/[0.11]",
    draftButton: "from-cyan-300 via-sky-400 to-blue-500",
  };
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
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: room, isLoading, error } = useMockDraftRoom(parsedMockDraftId, Boolean(parsedMockDraftId));
  useMockDraftRealtime(parsedMockDraftId, Boolean(parsedMockDraftId));
  const pickMutation = useMockDraftPick(parsedMockDraftId);
  const queueSeatId = room?.user_team_id ?? null;
  const { data: queue } = useMockDraftQueue(parsedMockDraftId, queueSeatId, Boolean(parsedMockDraftId));
  const queueAdd = useMockDraftQueueAdd(parsedMockDraftId, queueSeatId);
  const queueRemove = useMockDraftQueueRemove(parsedMockDraftId, queueSeatId);
  const queueClear = useMockDraftQueueClear(parsedMockDraftId, queueSeatId);
  const queueReorder = useMockDraftQueueReorder(parsedMockDraftId, queueSeatId);
  const [search, setSearch] = useState("");
  const [positionFilter, setPositionFilter] = useState<PositionFilter>("ALL");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [sortMode, setSortMode] = useState<SortMode>("adp");
  const [activeTab, setActiveTab] = useState<DraftTab>("draft");
  const [pickError, setPickError] = useState<string | null>(null);
  const [displaySecondsRemaining, setDisplaySecondsRemaining] = useState<number>(120);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number | null>(null);
  const [isMobileSheet, setIsMobileSheet] = useState(false);
  const pickRailRef = useRef<HTMLDivElement | null>(null);

  const { data: playersPayload, isLoading: playersLoading } = usePlayers({
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
    const next = Number(room.phase_seconds_remaining ?? room.seconds_remaining ?? room.pick_timer_seconds);
    setDisplaySecondsRemaining(Number.isFinite(next) ? Math.max(0, next) : 120);
  }, [room]);

  useEffect(() => {
    if (!room || !["countdown", "live"].includes(room.status) || displaySecondsRemaining <= 0) return;
    const timer = window.setInterval(() => setDisplaySecondsRemaining((current) => Math.max(0, current - 1)), 1_000);
    return () => window.clearInterval(timer);
  }, [displaySecondsRemaining, room]);

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

  const draftedIds = useMemo(() => new Set(room?.picks.map((pick) => pick.player_id) ?? []), [room?.picks]);
  const allAvailablePlayers = useMemo(() => {
    const rows = playersPayload?.data ?? [];
    return rows
      .filter((player) => ["QB", "RB", "WR", "TE", "K"].includes(String(player.pos || "").toUpperCase()))
      .filter((player) => !draftedIds.has(player.id))
      .sort((a, b) => {
        if (sortMode === "projection") {
          const projGap = (Number(b.sheetProjectedSeasonPoints) || 0) - (Number(a.sheetProjectedSeasonPoints) || 0);
          if (projGap !== 0) return projGap;
        }
        const adpA = Number.isFinite(a.sheetAdp as number) ? Number(a.sheetAdp) : 9999;
        const adpB = Number.isFinite(b.sheetAdp as number) ? Number(b.sheetAdp) : 9999;
        if (adpA !== adpB) return adpA - adpB;
        return (Number(b.sheetProjectedSeasonPoints) || 0) - (Number(a.sheetProjectedSeasonPoints) || 0);
      });
  }, [draftedIds, playersPayload?.data, sortMode]);

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

  const availablePlayerRanks = useMemo(
    () => new Map(allAvailablePlayers.map((player, index) => [player.id, index + 1])),
    [allAvailablePlayers]
  );

  const userRoster = useMemo(
    () => room?.rosters_by_team.find((roster) => roster.team_id === room.user_team_id) ?? null,
    [room?.rosters_by_team, room?.user_team_id]
  );
  const phaseLabel = useMemo(() => {
    if (!room) return "Draft Timer";
    if (room.phase_type === "lobby_countdown") return "Seat Fill Timer";
    if (room.phase_type === "prestart_countdown") return "Draft Starts In";
    if (room.phase_type === "pick_transition") return "Next Pick In";
    if (room.phase_type === "pick_clock") return "Pick Clock";
    return "Draft Timer";
  }, [room]);
  const phaseDescription = useMemo(() => {
    if (!room) return "";
    if (room.status === "countdown") return "You have 120 seconds to review everything and the players before the draft opens.";
    if (room.status === "live") return room.can_make_pick ? "You are on the clock." : "Waiting for the active manager.";
    if (room.status === "paused") return "Draft clock is paused.";
    if (room.status === "completed") return "Draft complete.";
    return "";
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
        ? Object.values(selectedRoster.slots).reduce((total, players) => total + players.length, 0)
        : 0,
    [selectedRoster]
  );
  const rosterCapacity = useMemo(
    () =>
      room ? Object.values(room.roster_slots).reduce((total, value) => total + Number(value || 0), 0) : 0,
    [room]
  );
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

  const handlePick = async (playerId: number) => {
    setPickError(null);
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
    return <div className="py-16 text-center text-sm font-black uppercase tracking-[0.2em] text-red-300">Invalid mock draft id.</div>;
  }

  if (isLoading) {
    return (
      <div className="py-16 flex items-center justify-center gap-3 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        Loading mock draft board...
      </div>
    );
  }

  if (!room) {
    return <div className="py-16 text-center text-sm font-black uppercase tracking-[0.2em] text-red-300">{error instanceof Error ? error.message : "Mock draft board unavailable."}</div>;
  }

  return (
    <div className="relative mx-auto max-w-[1480px] pb-24 pt-4">
      <div className="pointer-events-none absolute -left-12 top-6 h-40 w-40 rounded-full bg-primary/10 blur-[90px]" />
      <div className="pointer-events-none absolute right-10 top-14 h-32 w-32 rounded-full bg-cyan-300/8 blur-[70px]" />
      <Card className="cfb-panel-strong overflow-hidden rounded-[2.15rem] border-primary/12 bg-card/65">
        <CardHeader className="space-y-0 border-b border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.12),transparent_24%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.08),transparent_22%),linear-gradient(180deg,rgba(16,25,44,0.98),rgba(10,16,31,0.96))] p-0">
          <div className="grid items-center gap-4 px-4 py-5 md:grid-cols-[minmax(0,1.2fr)_auto] md:px-6">
            <div className="flex min-w-0 items-center gap-4">
              <Button
                variant="ghost"
                className="h-14 w-14 shrink-0 rounded-[1.2rem] border border-cyan-200/18 bg-cyan-300/10 p-0 text-cyan-200 hover:bg-cyan-300/16"
                onClick={() => navigate(`/mock-drafts/${parsedMockDraftId}/room`)}
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div className="min-w-0">
                <CardTitle className="truncate text-3xl font-black uppercase italic tracking-tight text-white md:text-4xl">
                  Mock Draft Board
                </CardTitle>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.26em] text-primary/85">
                  Power 4 • {room.mode === "single_player" ? "Single Player" : "Public Multiplayer"}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-slate-300 md:flex">
                <Zap className="h-4 w-4 text-cyan-200/75" />
                <span className="text-sm font-black">{room.picks.length}/{timeline.length}</span>
              </div>
              <div className="rounded-[1.35rem] border border-cyan-200/14 bg-white/[0.06] px-5 py-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                <p className="text-[9px] font-black uppercase tracking-[0.22em] text-cyan-100/70">
                  {room.status === "live" ? room.current_team_name || phaseLabel : phaseLabel}
                </p>
                <p className="mt-1 text-4xl font-black leading-none tabular-nums text-white md:text-5xl">{currentPhaseClock}</p>
              </div>
            </div>
          </div>

          <div className="border-t border-white/10 bg-[linear-gradient(180deg,rgba(8,17,31,0.65),rgba(8,17,31,0.35))] px-4 py-5 md:px-6">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-[18px] font-black uppercase tracking-[0.12em] text-white">Draft Order</p>
                <p className="mt-1 text-[11px] font-black uppercase tracking-[0.2em] text-primary">
                  {room.teams.length} Managers • {room.total_rounds} Rounds
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">On the Clock</p>
                <p className="mt-1 text-2xl font-black text-cyan-200">{room.current_team_name || "Awaiting Pick"}</p>
              </div>
            </div>
            <div
              ref={pickRailRef}
              className="overflow-x-auto overscroll-x-contain pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              onWheel={(event) => {
                const rail = pickRailRef.current;
                if (!rail) return;
                const horizontalDelta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
                if (horizontalDelta === 0) return;
                event.preventDefault();
                rail.scrollLeft += horizontalDelta * 1.35;
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
                      className="w-[152px] shrink-0 sm:w-[164px]"
                    >
                      <div
                        className={[
                          "relative flex h-full min-h-[150px] flex-col overflow-hidden rounded-[1.15rem] border px-4 py-4 transition-all",
                          isActive
                            ? "border-cyan-200/18 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] shadow-[0_18px_34px_rgba(34,211,238,0.14)]"
                            : isCompleted
                              ? `${aura.ring} bg-white/[0.055] ${aura.glow}`
                              : "border-white/8 bg-[#0d1121]",
                        ].join(" ")}
                      >
                        {!pickRevealText ? (
                          <div className="pointer-events-none absolute inset-x-3 bottom-10 top-4 flex items-center justify-center">
                            <span
                              className={[
                                "max-w-full truncate text-center text-5xl font-black uppercase tracking-[0.06em] sm:text-6xl",
                                isActive ? "text-cyan-100/90 drop-shadow-[0_0_18px_rgba(103,232,249,0.22)]" : "text-slate-200/72",
                              ].join(" ")}
                            >
                              {compactLabel}
                            </span>
                          </div>
                        ) : null}
                        <div className="relative z-10 min-h-[46px]">
                          {pickRevealText ? (
                            <p className={`truncate text-[11px] font-black uppercase tracking-[0.16em] ${aura.label}`}>
                              {pickRevealText}
                            </p>
                          ) : null}
                        </div>
                        {pickRevealText ? (
                          <div className="relative z-10 mt-1">
                            <p className="truncate text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">
                              {compactLabel}
                            </p>
                          </div>
                        ) : null}
                        <div className="flex-1" />
                        <div className="relative z-10 mt-4 flex items-center justify-center">
                          <span className={["h-3 w-3 rounded-full", isActive ? "bg-white shadow-[0_0_14px_rgba(255,255,255,0.5)]" : isCompleted ? aura.label.replace("text-", "bg-") : "bg-transparent"].join(" ")} />
                        </div>
                        <p className="relative z-10 mt-4 text-center text-[12px] font-black uppercase tracking-[0.16em] text-slate-500">
                          {entry.round}.{entry.roundPick}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </CardHeader>

        <CardContent className="bg-transparent p-0">
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as DraftTab)} className="space-y-5">
            <div className="px-4 pt-4 md:px-6">
              {pickError ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-red-400/25 bg-red-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-red-200">
                  <CircleAlert className="h-3.5 w-3.5" />
                  {pickError}
                </div>
              ) : null}
            </div>

            <TabsContent value="draft" className="space-y-7 px-4 pb-6 pt-6 md:px-6">
              <div className="grid items-center gap-4 xl:grid-cols-[minmax(0,1fr)_240px]">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search players, schools, positions..."
                    className="h-16 rounded-[1.5rem] border-0 bg-white pl-14 text-lg font-semibold text-slate-700 placeholder:text-slate-400 focus-visible:ring-0"
                  />
                </div>
                <div className="flex items-center justify-between gap-6 xl:justify-end">
                  <div className="text-right">
                    <p className="text-[12px] font-black uppercase tracking-[0.22em] text-slate-400">Available</p>
                    <p className="mt-1 text-4xl font-black text-white">{room.available_player_count}</p>
                  </div>
                </div>
              </div>

              <div className="cfb-panel overflow-hidden rounded-[2rem] border-white/10 bg-card/45">
                <div className="grid grid-cols-[70px_minmax(0,1.9fr)_110px_110px_110px_110px_190px] gap-3 px-5 py-4 text-[10px] font-black uppercase tracking-[0.24em] text-slate-500">
                  <span>RK</span>
                  <span>Player</span>
                  <span>Pos</span>
                  <span>ADP</span>
                  <span>Proj</span>
                  <span>ROS</span>
                  <span className="text-right">Action</span>
                </div>
                {playersLoading ? (
                  <div className="flex items-center justify-center gap-3 py-10 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    Loading board...
                  </div>
                ) : (
                  <div className="max-h-[780px] overflow-y-auto">
                    {availablePlayers.slice(0, 150).map((player) => {
                      const position = normalizePosition(player.pos);
                      const aura = getPositionAura(position);
                      const eligibility = room.position_eligibility[position];
                      const disabledReason = eligibility && !eligibility.can_draft ? eligibility.reason || "Roster full for this position" : null;
                      const queued = Boolean(queue?.data.some((row) => row.player_id === player.id));
                      const boardRank = availablePlayerRanks.get(player.id) ?? "--";
                      return (
                        <div
                          key={player.id}
                          role="button"
                          tabIndex={0}
                          className="grid w-full grid-cols-[70px_minmax(0,1.9fr)_110px_110px_110px_110px_190px] items-center gap-3 border-t border-white/8 bg-white/[0.03] px-5 py-5 text-left transition-colors hover:bg-white/[0.06]"
                          onClick={() => setSelectedPlayerId(player.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedPlayerId(player.id);
                            }
                          }}
                        >
                          <div className="text-3xl font-black text-white">{boardRank}</div>
                          <div className="min-w-0">
                            <p className={["truncate text-xl font-black", position === "QB" ? "text-blue-300" : position === "RB" ? "text-emerald-300" : position === "WR" ? "text-violet-300" : position === "TE" ? "text-amber-300" : "text-slate-100"].join(" ")}>{player.name}</p>
                            <p className="mt-1 truncate text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                              {player.school} • CFB
                            </p>
                            {disabledReason ? (
                              <p className="mt-1 inline-flex items-center gap-1 text-[10px] font-black uppercase tracking-[0.16em] text-amber-200">
                                <Lock className="h-3 w-3" />
                                {disabledReason}
                              </p>
                            ) : null}
                          </div>
                          <div className="text-sm font-black">
                            <span className={`inline-flex min-w-[64px] items-center justify-center rounded-full border px-3 py-2 text-[13px] font-black uppercase tracking-[0.08em] ${aura.pill} ${aura.glow}`}>
                              {position}
                            </span>
                          </div>
                          <div>
                            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">ADP</p>
                            <p className="mt-1 text-xl font-black text-white">
                              {Number.isFinite(player.sheetAdp as number) ? Number(player.sheetAdp).toFixed(1) : "--"}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">PROJ</p>
                            <p className="mt-1 text-xl font-black text-white">{Math.round(Number(player.sheetProjectedSeasonPoints || 0))}</p>
                          </div>
                          <div>
                            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">ROS</p>
                            <p className="mt-1 text-xl font-black text-white">100%</p>
                          </div>
                          <div className="flex items-center justify-end gap-2" onClick={(event) => event.stopPropagation()}>
                            <Button
                              variant="outline"
                              className="h-12 rounded-full border-white/10 bg-transparent px-6 text-[11px] font-black uppercase tracking-[0.18em] text-slate-400 hover:bg-white/[0.06] hover:text-white"
                              disabled={queueAdd.isPending || queued}
                              onClick={() => queueAdd.mutate(player.id)}
                            >
                              {queued ? "Queued" : "Queue"}
                            </Button>
                            {room.can_make_pick ? (
                              <Button
                                className="h-12 rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 px-6 text-[11px] font-black uppercase tracking-[0.18em] text-slate-950 shadow-[0_14px_34px_rgba(14,165,233,0.2)] hover:brightness-110"
                                disabled={pickMutation.isPending || Boolean(disabledReason)}
                                onClick={() => void handlePick(player.id)}
                              >
                                Draft
                              </Button>
                            ) : null}
                            <Button
                              variant="outline"
                              className="h-12 w-12 rounded-full border-white/10 bg-white/[0.04] p-0 text-slate-400 hover:bg-white/[0.08] hover:text-white"
                              onClick={() => setSelectedPlayerId(player.id)}
                            >
                              <Star className="h-5 w-5" />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <p className="text-lg font-black text-foreground">Draft History</p>
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                    Scroll further for completed picks
                  </p>
                </div>
                <div className="cfb-panel overflow-hidden rounded-[2rem] border-white/10 bg-card/55">
                  <div className="grid grid-cols-[90px_minmax(0,1.3fr)_110px_1fr] gap-3 border-b border-white/10 bg-white/[0.05] px-5 py-3 text-[10px] font-black uppercase tracking-[0.2em] text-slate-300">
                    <span>Pick</span>
                    <span>Player</span>
                    <span>Pos</span>
                    <span>Team</span>
                  </div>
                  <div className="max-h-[420px] overflow-y-auto">
                    {recentPicks.length ? recentPicks.map((pick) => {
                      const aura = getPositionAura(pick.player_position);
                      return (
                        <div key={pick.id} className="grid grid-cols-[90px_minmax(0,1.3fr)_110px_1fr] gap-3 border-b border-white/5 bg-white/[0.02] px-5 py-4 even:bg-white/[0.04]">
                          <div className="text-sm font-black text-slate-200">R{pick.round_number}.{pick.round_pick}</div>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-black text-foreground">{pick.player_name}</p>
                            <p className="truncate text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                              {pick.player_school}
                            </p>
                          </div>
                          <div className="text-sm font-black">
                            <span className={`inline-flex rounded-full border px-2 py-1 text-[9px] font-black uppercase tracking-[0.12em] ${aura.pill}`}>
                              {pick.player_position}
                            </span>
                          </div>
                          <div className="truncate text-sm font-black text-slate-300">{pick.team_name}</div>
                        </div>
                      );
                    }) : (
                      <div className="px-5 py-10 text-center text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                        No picks yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="queue" className="space-y-4 px-4 pb-6 md:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-black text-foreground">My Queue</p>
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                    Reorder your next auto-pick priorities
                  </p>
                </div>
                <Button
                  variant="outline"
                  className="h-10 rounded-xl text-[10px] font-black uppercase tracking-[0.16em]"
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
                      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-900 text-sm font-black text-cyan-100">
                        {item.priority}
                      </div>
                      <div>
                        <p className="text-sm font-black text-foreground">{item.player_name}</p>
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
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
                    <p className="text-sm font-black text-foreground">Queue is empty.</p>
                    <p className="mt-2 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                      Add players from the Players tab before the clock reaches auto-pick.
                    </p>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="roster" className="space-y-4 px-4 pb-6 md:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-black text-foreground">Team Rosters</p>
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                    Position slots and current fills
                  </p>
                </div>
                <Select
                  value={selectedRosterTeamId ? String(selectedRosterTeamId) : undefined}
                  onValueChange={(value) => setSelectedRosterTeamId(Number(value))}
                >
                  <SelectTrigger className="cfb-control h-11 w-[240px] rounded-2xl text-[10px] font-black uppercase tracking-[0.16em]">
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
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-300">Roster Progress</p>
                    <p className="mt-1 text-sm font-black text-foreground">{selectedRoster?.team_name || "Roster"}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-black text-white">{rosterFilledCount}/{rosterCapacity || 0}</p>
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Slots Filled</p>
                  </div>
                </div>
              </div>

              {selectedRoster ? (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(selectedRoster.slots).map(([slot, players]) => (
                    <div key={slot} className="cfb-panel rounded-[1.75rem] p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-300">{slot}</p>
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                          {players.length}/{room.roster_slots[slot] ?? players.length}
                        </p>
                      </div>
                      <div className="space-y-3">
                        {Array.from({ length: room.roster_slots[slot] ?? Math.max(1, players.length) }).map((_, index) => {
                          const player = players[index];
                          const aura = getPositionAura(player?.position || slot);
                          const label = player?.position || slot;
                          return (
                            <button
                              key={`${slot}-${index}`}
                              type="button"
                              className={[
                                "flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition-colors",
                                player
                                  ? `${aura.ring} ${aura.glow} bg-gradient-to-br ${aura.surface} hover:brightness-110`
                                  : `${aura.ring} bg-gradient-to-br ${aura.surface} opacity-55 hover:opacity-75`,
                              ].join(" ")}
                              onClick={() => player && setSelectedPlayerId(player.player_id)}
                              disabled={!player}
                            >
                              <span
                                className={[
                                  "flex h-14 w-14 shrink-0 items-center justify-center rounded-[0.85rem] border text-[11px] font-black uppercase tracking-[0.08em]",
                                  player ? `bg-gradient-to-br ${aura.icon}` : `${aura.pill} opacity-65`,
                                ].join(" ")}
                              >
                                {player ? getInitials(player.player_name) : label.slice(0, 2)}
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className={player ? "block truncate text-sm font-black text-foreground" : "block truncate text-sm font-black text-slate-500"}>
                                  {player ? player.player_name : `Empty ${slot}`}
                                </span>
                                <span className="mt-1 flex flex-wrap items-center gap-2">
                                  <span className={`inline-flex rounded-xl border px-2 py-0.5 text-[9px] font-black uppercase tracking-[0.14em] ${player ? aura.pill : `${aura.pill} opacity-70`}`}>
                                    {label}
                                  </span>
                                  <span className="truncate text-[10px] font-black uppercase tracking-[0.14em] text-muted-foreground">
                                    {player ? player.school : "Available Slot"}
                                  </span>
                                </span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-[1.5rem] border border-dashed border-white/10 bg-slate-950/40 px-4 py-10 text-center text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                  No roster entries yet.
                </div>
              )}
            </TabsContent>

            <div className="sticky bottom-0 z-20 border-t border-white/10 bg-[linear-gradient(180deg,rgba(8,17,31,0.85),rgba(8,17,31,0.96))] backdrop-blur-xl">
              <TabsList className="mx-auto grid h-auto w-full max-w-[720px] grid-cols-3 rounded-none border-0 bg-transparent p-0 shadow-none">
                <TabsTrigger value="draft" className="rounded-none border-t-2 border-transparent py-4 text-[10px] font-black uppercase tracking-[0.12em] data-[state=active]:border-cyan-300 data-[state=active]:bg-transparent data-[state=active]:text-cyan-200">
                  <div className="flex flex-col items-center gap-1">
                    <Star className="h-4 w-4" />
                    <span>Draft</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger value="queue" className="rounded-none border-t-2 border-transparent py-4 text-[10px] font-black uppercase tracking-[0.12em] data-[state=active]:border-cyan-300 data-[state=active]:bg-transparent data-[state=active]:text-cyan-200">
                  <div className="flex flex-col items-center gap-1">
                    <ClipboardList className="h-4 w-4" />
                    <span>Queue</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger
                  value="roster"
                  className="rounded-none border-t-2 border-transparent py-4 text-[10px] font-black uppercase tracking-[0.12em] data-[state=active]:border-cyan-300 data-[state=active]:bg-transparent data-[state=active]:text-cyan-200"
                >
                  <div className="flex flex-col items-center gap-1">
                    <ClipboardList className="h-4 w-4" />
                    <span>Roster</span>
                  </div>
                </TabsTrigger>
              </TabsList>
            </div>
          </Tabs>
        </CardContent>
      </Card>

      <Sheet open={selectedPlayerId !== null} onOpenChange={(open) => !open && setSelectedPlayerId(null)}>
        <SheetContent
          side={isMobileSheet ? "bottom" : "right"}
          className="z-[220] h-screen overflow-y-auto border-white/10 bg-[#111214] p-0 text-foreground sm:max-w-[560px]"
        >
          {selectedPlayer ? (
            <div className="space-y-6">
              <div className="border-b border-white/10 bg-[linear-gradient(180deg,rgba(28,29,33,0.98),rgba(12,13,15,0.98))] px-6 pb-8 pt-14">
                <SheetHeader className="space-y-3 text-left">
                  <div className="flex items-start gap-4 pr-10">
                    <div className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-[0.95rem] border bg-gradient-to-br text-lg font-black uppercase ${selectedPlayerAura.icon}`}>
                      {normalizePosition(selectedPlayer.pos).slice(0, 2)}
                    </div>
                    <SheetTitle className="min-w-0 text-3xl font-black leading-tight text-white break-words">
                      {selectedPlayer.name}
                    </SheetTitle>
                  </div>
                  <SheetDescription className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-300">
                    {selectedPlayer.school} • {normalizePosition(selectedPlayer.pos)} • {selectedPlayer.playerClass || "CFB"}
                  </SheetDescription>
                </SheetHeader>

                <div className="mt-6 grid grid-cols-3 gap-3">
                  <div className="rounded-xl border border-white/10 bg-[#1c1d20] p-4 text-center">
                    <p className="text-3xl font-black text-white">
                      {Number.isFinite(selectedPlayer.sheetAdp as number) ? Number(selectedPlayer.sheetAdp).toFixed(1) : "--"}
                    </p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">ADP</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-[#1c1d20] p-4 text-center">
                    <p className="text-3xl font-black text-white">{Number(selectedPlayer.sheetProjectedSeasonPoints || 0).toFixed(1)}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Projection</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-[#1c1d20] p-4 text-center">
                    <p className="text-3xl font-black text-white">{selectedPlayer.projection.floor?.toFixed(1) ?? "--"}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Floor</p>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    className="rounded-lg border-white/15 bg-[#202226] text-[10px] font-black uppercase tracking-[0.16em] hover:bg-[#2a2c31]"
                    disabled={queueAdd.isPending || Boolean(queue?.data.some((row) => row.player_id === selectedPlayer.id))}
                    onClick={() => queueAdd.mutate(selectedPlayer.id)}
                  >
                    <Plus className="mr-1 h-3.5 w-3.5" />
                    Add to Queue
                  </Button>
                  <Button
                    className="rounded-lg bg-white text-[10px] font-black uppercase tracking-[0.16em] text-black hover:bg-slate-100"
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
                <div className="rounded-[1.05rem] border border-white/10 bg-[#1a1b1f] p-5">
                  <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-300">Outlook</p>
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
                      <p className={`text-[11px] font-black uppercase tracking-[0.24em] ${selectedPlayerAura.label}`}>Core Stats</p>
                    </div>
                    {playerSeasonSummaryLoading ? (
                      <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading player detail...
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-3">
                        {selectedPlayerCoreStats.map((stat) => (
                          <div key={stat.label} className={`rounded-lg border bg-black/35 p-3 ${selectedPlayerAura.ring}`}>
                            <p className="text-2xl font-black text-white">{formatStatValue(stat.value)}</p>
                            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">{stat.label}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="rounded-[1.05rem] border border-white/10 bg-[#1a1b1f] p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-slate-300" />
                    <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-300">Roster Fit</p>
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
