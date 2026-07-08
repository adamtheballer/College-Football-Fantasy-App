import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Activity, AlertTriangle, ArrowLeft, Bot, ClipboardList, Info, Loader2, Lock, Search, ShieldAlert, Trophy, User, Users, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDraftPick, useDraftRoom } from "@/hooks/use-draft";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { useDraftPlayerPool, usePlayerCard } from "@/hooks/use-players";
import { ApiError } from "@/lib/api";
import { buildDraftBoard, type DraftConfig, type DraftPlayer } from "@/lib/draftRankings";
import { buildProjectedStats, formatStat, statRowsForPosition, statValue } from "@/lib/playerProjectionStats";
import { filterDraftablePlayers, getLegalPositionsForRoster } from "@/lib/rosterLegality";
import { cn } from "@/lib/utils";
import type { DraftRoomTeam } from "@/types/draft";

const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"];
const DRAFT_PLAYER_PAGE_SIZE = 80;
const DRAFT_SLOT_KEYS = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH"] as const;
const PLAYER_CARD_TABS = ["about", "injuries", "stats", "projections"] as const;

type PlayerCardTab = (typeof PLAYER_CARD_TABS)[number];

const POSITION_STYLES: Record<string, string> = {
  QB: "border-blue-300/40 bg-blue-500/15 text-blue-100 shadow-[0_0_16px_rgba(96,165,250,0.18)]",
  RB: "border-emerald-300/40 bg-emerald-500/15 text-emerald-100 shadow-[0_0_16px_rgba(74,222,128,0.18)]",
  WR: "border-violet-300/40 bg-violet-500/15 text-violet-100 shadow-[0_0_16px_rgba(196,181,253,0.18)]",
  TE: "border-amber-300/40 bg-amber-500/15 text-amber-100 shadow-[0_0_16px_rgba(251,191,36,0.18)]",
  K: "border-slate-300/40 bg-slate-400/15 text-slate-100 shadow-[0_0_16px_rgba(203,213,225,0.14)]",
};

type PreviewTeam = DraftRoomTeam & {
  isPlaceholder?: boolean;
};

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

const formatStatus = (value: string) => value.replace(/_/g, " ");

const formatCountdown = (target: Date | null, now: number) => {
  if (!target || Number.isNaN(target.getTime())) return "Draft time pending";
  const diff = Math.max(0, target.getTime() - now);
  const days = Math.floor(diff / 86_400_000);
  const hours = Math.floor((diff % 86_400_000) / 3_600_000);
  const minutes = Math.floor((diff % 3_600_000) / 60_000);
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

const getSlotCount = (slots: Record<string, number> | undefined, key: string) => Number(slots?.[key] ?? 0);

const getTotalDraftSlots = (slots: Record<string, number> | undefined) =>
  DRAFT_SLOT_KEYS.reduce((total, key) => total + getSlotCount(slots, key), 0);

const getDraftConfig = (
  leagueSize: number,
  rosterSlots: Record<string, number> | undefined
): DraftConfig => ({
  leagueSize,
  rosterSlots: {
    QB: getSlotCount(rosterSlots, "QB"),
    RB: getSlotCount(rosterSlots, "RB"),
    WR: getSlotCount(rosterSlots, "WR"),
    TE: getSlotCount(rosterSlots, "TE"),
    K: getSlotCount(rosterSlots, "K"),
    BE:
      getSlotCount(rosterSlots, "BENCH") +
      getSlotCount(rosterSlots, "FLEX") +
      getSlotCount(rosterSlots, "SUPERFLEX"),
    IR: 0,
  },
});

const projectionStatsForPlayer = (player: DraftPlayer | null) => {
  if (!player) return null;
  return buildProjectedStats(player.projection, player.projectedPoints, player.sheetProjectionStats);
};

const formatCardValue = (value: unknown, fallback = "—") => {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : fallback;
  return String(value);
};

const statDisplayKeys = [
  ["Passing Yards", ["pass_yards", "PassingYards", "passingYards"]],
  ["Passing TD", ["pass_tds", "PassingTouchdowns", "passingTouchdowns"]],
  ["Interceptions", ["interceptions", "Interceptions"]],
  ["Rush Yards", ["rush_yards", "RushingYards", "rushingYards"]],
  ["Rush TD", ["rush_tds", "RushingTouchdowns", "rushingTouchdowns"]],
  ["Receptions", ["receptions", "Receptions"]],
  ["Rec Yards", ["rec_yards", "ReceivingYards", "receivingYards"]],
  ["Rec TD", ["rec_tds", "ReceivingTouchdowns", "receivingTouchdowns"]],
  ["Fumbles Lost", ["fumbles_lost", "FumblesLost", "fumblesLost"]],
] as const;

const getStatValue = (stats: Record<string, unknown>, keys: readonly string[]) => {
  for (const key of keys) {
    const value = stats[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return null;
};

const getRoundNumber = (overallPick: number, teamCount: number) =>
  Math.floor((overallPick - 1) / Math.max(1, teamCount)) + 1;

const getRoundPick = (overallPick: number, teamCount: number) =>
  ((overallPick - 1) % Math.max(1, teamCount)) + 1;

const getCenteredScrollLeft = ({
  overallPick,
  cardOffsetLeft,
  cardWidth,
  containerWidth,
}: {
  overallPick: number;
  cardOffsetLeft: number;
  cardWidth: number;
  containerWidth: number;
}) => {
  if (overallPick <= 3) return 0;
  return Math.max(0, cardOffsetLeft - containerWidth / 2 + cardWidth / 2);
};

const buildPreviewTeams = (teams: DraftRoomTeam[], maxTeams: number): PreviewTeam[] => {
  const targetCount = Math.max(teams.length, maxTeams, 1);
  return Array.from({ length: targetCount }, (_, index) => {
    const team = teams[index];
    if (team) return team;
    return {
      id: -(index + 1),
      name: `Open Team ${index + 1}`,
      owner_user_id: null,
      owner_name: "Waiting for manager",
      isPlaceholder: true,
    };
  });
};

export default function Draft() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [activePlayerCardTab, setActivePlayerCardTab] = useState<PlayerCardTab>("about");
  const [localError, setLocalError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const carouselRef = useRef<HTMLDivElement | null>(null);
  const pickRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());

  const parsedLeagueId =
    leagueId && !Number.isNaN(Number(leagueId)) ? Number(leagueId) : undefined;

  const { data: league } = useLeagueDetail(parsedLeagueId);
  const {
    data: draftRoom,
    isLoading: draftRoomLoading,
    error: draftRoomError,
  } = useDraftRoom(parsedLeagueId);
  const pickMutation = useDraftPick(parsedLeagueId);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  const draftStartsAt = useMemo(
    () => (league?.draft?.draft_datetime_utc ? new Date(league.draft.draft_datetime_utc) : null),
    [league?.draft?.draft_datetime_utc]
  );
  const memberCount = league?.members.length ?? draftRoom?.teams.length ?? 0;
  const maxTeams = league?.max_teams ?? draftRoom?.teams.length ?? 0;
  const isLeagueFull = Boolean(maxTeams > 0 && memberCount >= maxTeams);
  const hasDraftTimePassed = Boolean(draftStartsAt && draftStartsAt.getTime() <= now);
  const isScheduledPreview = Boolean(
    draftRoom?.status === "scheduled" && (!hasDraftTimePassed || !isLeagueFull)
  );
  const isDraftActive = Boolean(
    isLeagueFull && (draftRoom?.status === "live" || (draftRoom?.status === "scheduled" && hasDraftTimePassed))
  );
  const leagueSize = Math.max(league?.max_teams ?? draftRoom?.teams.length ?? 12, draftRoom?.teams.length ?? 0, 1);

  const draftConfig = useMemo(
    () => getDraftConfig(leagueSize, draftRoom?.roster_slots),
    [draftRoom?.roster_slots, leagueSize]
  );

  const draftedIds = useMemo(
    () => new Set(draftRoom?.picks.map((pick) => pick.player_id) ?? []),
    [draftRoom?.picks]
  );

  const viewerDraftBoardTeamId = draftRoom?.user_team_id ?? draftRoom?.current_team_id ?? null;
  const viewerDraftBoardTeamName =
    draftRoom?.teams.find((team) => team.id === viewerDraftBoardTeamId)?.name ??
    (viewerDraftBoardTeamId ? "Your Team" : "Draft complete");

  const viewerTeamRoster = useMemo(() => {
    if (!viewerDraftBoardTeamId || !draftRoom?.picks) return [];
    return draftRoom.picks
      .filter((pick) => pick.team_id === viewerDraftBoardTeamId)
      .map((pick) => ({
        id: pick.player_id,
        position: pick.player_position,
      }));
  }, [draftRoom?.picks, viewerDraftBoardTeamId]);

  const superflexEnabled = getSlotCount(draftRoom?.roster_slots, "SUPERFLEX") > 0;

  const legalPositions = useMemo(
    () =>
      draftRoom
        ? getLegalPositionsForRoster(viewerTeamRoster, draftRoom.roster_slots, {
            superflexEnabled,
          })
        : [],
    [viewerTeamRoster, draftRoom, superflexEnabled]
  );

  const showMasterBoardPreview = isScheduledPreview && !isDraftActive;
  const serverPositionFilter =
    position === "ALL"
      ? showMasterBoardPreview
        ? undefined
        : legalPositions.length > 0
          ? legalPositions.join(",")
          : undefined
      : position;
  const draftSearch = search.trim();
  const { data: playersPayload, isLoading: playersLoading, isError: playersError } = useDraftPlayerPool({
    search: draftSearch || undefined,
    position: serverPositionFilter,
    league_id: parsedLeagueId,
    available_only: Boolean(parsedLeagueId) && !showMasterBoardPreview,
    limit: DRAFT_PLAYER_PAGE_SIZE,
    offset: 0,
    pages: showMasterBoardPreview ? 10 : 5,
    sort: "draft_rank",
  });

  const draftBoard = useMemo(() => {
    const board = buildDraftBoard(playersPayload?.data ?? [], draftConfig);
    return board
      .map((player) => {
        const stableRank =
          player.sourceBoardRank ?? player.boardRank ?? player.sheetAdp ?? player.masterDraftRank ?? player.draftRank;
        return {
          ...player,
          draftRank: stableRank,
          masterDraftRank: stableRank,
        };
      })
      .sort((left, right) => {
        const leftRank = left.masterDraftRank ?? Number.POSITIVE_INFINITY;
        const rightRank = right.masterDraftRank ?? Number.POSITIVE_INFINITY;
        if (leftRank !== rightRank) return leftRank - rightRank;
        if (left.projectedPoints !== right.projectedPoints) return right.projectedPoints - left.projectedPoints;
        return left.name.localeCompare(right.name);
      });
  }, [draftConfig, playersPayload?.data]);

  const draftablePlayers = useMemo(
    () =>
      draftRoom
        ? filterDraftablePlayers(
            draftBoard,
            viewerTeamRoster,
            draftRoom.roster_slots,
            draftedIds,
            { superflexEnabled }
          )
        : [],
    [viewerTeamRoster, draftedIds, draftBoard, draftRoom, superflexEnabled]
  );

  const visiblePlayers = useMemo(
    () => (showMasterBoardPreview ? draftBoard : draftablePlayers),
    [draftBoard, draftablePlayers, showMasterBoardPreview]
  );

  const selectedPlayer = useMemo(
    () => draftBoard.find((player) => player.id === selectedPlayerId) ?? null,
    [draftBoard, selectedPlayerId]
  );
  const { data: playerCard, isLoading: playerCardLoading } = usePlayerCard(
    selectedPlayer?.id,
    Boolean(selectedPlayer)
  );

  useEffect(() => {
    setActivePlayerCardTab("about");
  }, [selectedPlayerId]);

  const previewTeams = useMemo(
    () => buildPreviewTeams(draftRoom?.teams ?? [], leagueSize),
    [draftRoom?.teams, leagueSize]
  );

  const totalDraftSlots = getTotalDraftSlots(draftRoom?.roster_slots);
  const totalPicks = Math.max(0, totalDraftSlots * previewTeams.length);

  const draftOrderPicks = useMemo(
    () =>
      Array.from({ length: totalPicks }, (_, index) => {
        const overallPick = index + 1;
        const round = getRoundNumber(overallPick, previewTeams.length);
        const roundPick = getRoundPick(overallPick, previewTeams.length);
        const orderedTeams = round % 2 === 1 ? previewTeams : [...previewTeams].reverse();
        const team = orderedTeams[roundPick - 1];
        const pick = draftRoom?.picks.find((row) => row.overall_pick === overallPick);
        return {
          overallPick,
          round,
          roundPick,
          team,
          pick,
        };
      }),
    [draftRoom?.picks, previewTeams, totalPicks]
  );

  useEffect(() => {
    const container = carouselRef.current;
    const activeCard = pickRefs.current.get(draftRoom?.current_pick ?? 1);
    if (!container || !activeCard) return;
    container.scrollTo({
      left: getCenteredScrollLeft({
        overallPick: draftRoom?.current_pick ?? 1,
        cardOffsetLeft: activeCard.offsetLeft,
        cardWidth: activeCard.offsetWidth,
        containerWidth: container.clientWidth,
      }),
      behavior: "smooth",
    });
  }, [draftRoom?.current_pick, draftRoom?.status, totalPicks]);

  const makePick = async (player: DraftPlayer) => {
    if (!isLeagueFull) {
      setLocalError("Draft cannot start until the league is full.");
      return;
    }
    if (!isDraftActive) {
      setLocalError("Draft is locked until the scheduled start time.");
      return;
    }
    if (!draftRoom?.can_make_pick) {
      setLocalError("You can only draft when your team is on the clock.");
      return;
    }
    setLocalError(null);
    try {
      await pickMutation.mutateAsync(player.id);
    } catch {
      // Rendered below from mutation state.
    }
  };

  if (!parsedLeagueId) {
    return (
      <div className="mx-auto max-w-4xl py-16">
        <div className="rounded-[2rem] border border-red-400/20 bg-red-500/10 p-10 text-center">
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">Invalid league ID.</p>
        </div>
      </div>
    );
  }

  if (draftRoomLoading) {
    return (
      <div className="mx-auto max-w-5xl py-16">
        <div className="flex items-center justify-center gap-3 rounded-[2rem] border border-cyan-200/15 bg-card/45 p-12">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">
            Loading draft room...
          </p>
        </div>
      </div>
    );
  }

  if (!draftRoom || draftRoomError) {
    return (
      <div className="mx-auto max-w-5xl py-16">
        <div className="space-y-4 rounded-[2rem] border border-red-400/20 bg-red-500/10 p-12 text-center">
          <ShieldAlert className="mx-auto h-8 w-8 text-red-300" />
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">
            {formatApiError(draftRoomError, "Unable to load draft room.")}
          </p>
          <Button
            variant="outline"
            className="rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]"
            onClick={() => navigate(`/league/${parsedLeagueId}/lobby`)}
          >
            Back to Draft Lobby
          </Button>
        </div>
      </div>
    );
  }

  const leagueName = league?.name || `League ${draftRoom.league_id}`;
  const currentTeamLabel = draftRoom.current_team_name || "Draft complete";
  const latestPick = draftRoom.picks[draftRoom.picks.length - 1];
  const currentPick = draftRoom.current_pick;
  const canPick = isDraftActive && draftRoom.can_make_pick && !pickMutation.isPending;
  const actionLabel = isScheduledPreview ? "Locked" : draftRoom.can_make_pick ? "Draft" : "Wait";
  const completed = draftRoom.current_team_id === null || draftRoom.status === "complete";

  return (
    <div className="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#020713_0%,#06172a_42%,#0a102c_68%,#120a29_100%)] text-foreground">
      <div className="pointer-events-none absolute inset-0 opacity-[0.32] [background-image:radial-gradient(circle_at_18%_16%,rgba(56,189,248,0.2),transparent_30%),radial-gradient(circle_at_78%_12%,rgba(96,165,250,0.16),transparent_28%),radial-gradient(circle_at_86%_72%,rgba(251,191,36,0.08),transparent_26%),radial-gradient(circle_at_42%_92%,rgba(217,70,239,0.09),transparent_32%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.075] [background-image:linear-gradient(rgba(255,255,255,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:56px_56px]" />

      <div className="relative mx-auto max-w-[1800px] space-y-6 px-4 pb-28 pt-4 md:px-6">
        <div className="relative z-20 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-12 w-12 rounded-2xl border-cyan-200/20 bg-slate-950/70 text-cyan-100 shadow-[0_0_28px_rgba(34,211,238,0.16)] backdrop-blur-xl hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white"
              aria-label="Exit real draft room"
              title="Exit real draft room"
              onClick={() => navigate(`/league/${parsedLeagueId}/lobby`)}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-2xl border-cyan-200/20 bg-slate-950/70 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100 hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white">
              <Link to={`/league/${parsedLeagueId}/lobby`}>Exit</Link>
            </Button>
          </div>

          {!isScheduledPreview && !completed ? (
            <div className="pointer-events-none fixed left-1/2 top-3 z-[1250] -translate-x-1/2">
              <div className="rounded-3xl border border-cyan-200/20 bg-slate-950/82 px-8 py-3 text-center shadow-[0_0_48px_rgba(34,211,238,0.18)] backdrop-blur-2xl">
                <p className="text-[9px] font-black uppercase tracking-[0.26em] text-muted-foreground">Pick Timer</p>
                <p className="mt-1 text-4xl font-black tabular-nums leading-none tracking-tight text-cyan-100">
                  {draftRoom.pick_timer_seconds}s
                </p>
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <div
              className={cn(
                "rounded-3xl border border-cyan-200/20 bg-slate-950/72 px-6 py-4 text-right shadow-[0_0_42px_rgba(34,211,238,0.17)] backdrop-blur-xl",
                canPick && "border-cyan-200/50 bg-cyan-300/12 shadow-[0_0_58px_rgba(103,232,249,0.28)]"
              )}
            >
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">
                {isScheduledPreview ? "Preview Mode" : "On Clock"}
              </p>
              <p className="text-xl font-black uppercase text-cyan-100">
                {isScheduledPreview ? (isLeagueFull ? "Locked" : "Need Managers") : completed ? "Complete" : currentTeamLabel}
              </p>
            </div>
            <Button asChild variant="outline" className="h-12 rounded-2xl border-white/15 bg-slate-950/65 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-white hover:bg-white/10">
              <Link to={`/league/${parsedLeagueId}`}>League Hub</Link>
            </Button>
          </div>
        </div>

        <header className="rounded-[2rem] border border-cyan-200/15 bg-card/45 p-6 shadow-[0_0_70px_rgba(14,165,233,0.10)] md:p-8">
          <p className="text-[10px] font-black uppercase tracking-[0.26em] text-cyan-200">Real League Draft Room</p>
          <h1 className="mt-3 text-4xl font-black italic uppercase tracking-tight text-white md:text-6xl">
            {leagueName}
          </h1>
          <div className="mt-5 flex flex-wrap gap-3">
            <span className="rounded-full border border-cyan-200/15 bg-cyan-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100">
              {formatStatus(draftRoom.status)}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
              {league?.members.length ?? draftRoom.teams.length}/{league?.max_teams ?? draftRoom.teams.length} Managers
            </span>
            {isScheduledPreview ? (
              <span className="rounded-full border border-amber-300/25 bg-amber-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-amber-100">
                {isLeagueFull
                  ? `Opens in ${formatCountdown(draftStartsAt, now)}`
                  : `${memberCount}/${maxTeams} Managers Joined`}
              </span>
            ) : null}
          </div>
          {isScheduledPreview ? (
            <p className="mt-5 max-w-3xl text-[11px] font-black uppercase leading-6 tracking-[0.18em] text-muted-foreground">
              {isLeagueFull
                ? "Preview mode uses the real player board and real draft order shell. Picks are locked until the scheduled draft time."
                : "Preview mode uses the real player board and real draft order shell. Picks are locked until every league slot is filled."}
            </p>
          ) : null}
        </header>

        {(localError || pickMutation.error) && (
          <div className="rounded-2xl border border-red-300/20 bg-red-400/10 p-4 text-sm font-bold text-red-100">
            {localError || formatApiError(pickMutation.error, "Unable to save draft pick.")}
          </div>
        )}

        {latestPick ? (
          <div className="mx-auto flex w-fit items-center rounded-full border border-cyan-300/15 bg-cyan-400/10 px-5 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100">
            Last pick&nbsp;<span className="text-white">{latestPick.player_name}</span>&nbsp;to {latestPick.team_name}
          </div>
        ) : null}

        <section className="overflow-hidden rounded-[2rem] border border-cyan-200/15 bg-card/50 shadow-[0_0_70px_rgba(14,165,233,0.13),inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="flex items-center justify-between gap-4 border-b border-cyan-100/10 px-5 py-4">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.26em] text-cyan-200 drop-shadow-[0_0_14px_rgba(103,232,249,0.32)]">Draft Order</p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                Real league draft board preview
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">{totalPicks} Picks</p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                {Math.max(0, totalPicks - draftRoom.picks.length)} Unlocked
              </p>
            </div>
          </div>
          <div ref={carouselRef} className="flex gap-4 overflow-x-auto px-5 py-5 scroll-smooth">
            {draftOrderPicks.map((slot) => {
              const isCurrent = !completed && slot.overallPick === currentPick;
              const isUser = slot.team?.id === draftRoom.user_team_id;
              const isLocked = Boolean(slot.pick);
              return (
                <div
                  key={slot.overallPick}
                  ref={(node) => {
                    if (node) {
                      pickRefs.current.set(slot.overallPick, node);
                    } else {
                      pickRefs.current.delete(slot.overallPick);
                    }
                  }}
                  className={cn(
                    "min-w-[178px] rounded-3xl border p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition",
                    isCurrent && !isScheduledPreview
                      ? "border-cyan-200/80 bg-cyan-300/14 shadow-[0_0_52px_rgba(103,232,249,0.36),inset_0_1px_0_rgba(255,255,255,0.07)]"
                      : isCurrent
                        ? "border-amber-200/45 bg-amber-300/10 shadow-[0_0_42px_rgba(251,191,36,0.16)]"
                      : isUser
                        ? "border-cyan-300/40 bg-cyan-400/10 shadow-[0_0_30px_rgba(34,211,238,0.18),inset_0_1px_0_rgba(255,255,255,0.05)]"
                      : "border-white/10 bg-white/[0.045] hover:border-cyan-200/20 hover:shadow-[0_0_22px_rgba(34,211,238,0.10)]",
                    isLocked && "opacity-80"
                  )}
                >
                  <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">Pick {slot.overallPick}</p>
                  <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{slot.round}.{slot.roundPick}</p>
                  <div className="mt-3 flex h-8 w-8 items-center justify-center rounded-xl border border-cyan-200/30 bg-slate-950/55 text-cyan-100 shadow-[0_0_22px_rgba(103,232,249,0.24),inset_0_0_12px_rgba(103,232,249,0.08)]">
                    {isUser ? <User className="h-3.5 w-3.5 drop-shadow-[0_0_8px_rgba(103,232,249,0.65)]" /> : <Bot className="h-3.5 w-3.5 drop-shadow-[0_0_8px_rgba(103,232,249,0.65)]" />}
                  </div>
                  <p className="mt-3 truncate text-base font-black text-foreground">
                    {slot.pick?.player_name ?? slot.team?.name ?? `Team ${slot.roundPick}`}
                  </p>
                  <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                    {slot.pick
                      ? `${slot.pick.player_position} • ${slot.pick.player_school}`
                      : slot.team?.isPlaceholder
                        ? "Waiting for manager"
                        : slot.team?.owner_name || "Manager"}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {completed ? (
          <section className="rounded-[2rem] border border-primary/30 bg-primary/10 p-6 text-center">
            <Trophy className="mx-auto mb-3 h-8 w-8 text-primary" />
            <p className="text-xl font-black uppercase tracking-tight text-foreground">Draft Complete</p>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Real league rosters are finalized.</p>
          </section>
        ) : null}

        <section data-testid="available-players-table" className="overflow-hidden rounded-[2rem] border border-cyan-200/15 bg-card/50 shadow-[0_0_56px_rgba(34,211,238,0.12),inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="border-b border-cyan-100/10 p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-cyan-200 drop-shadow-[0_0_14px_rgba(103,232,249,0.28)]">Available Players</p>
                <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                  {showMasterBoardPreview
                    ? "Master draft board preview. Picks are locked."
                    : `Showing your roster needs: ${viewerDraftBoardTeamName}`}
                </p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/80">
                  {showMasterBoardPreview
                    ? "All positions are visible until the draft unlocks."
                    : `Your legal positions: ${legalPositions.length ? legalPositions.join(", ") : "None"}`}
                </p>
              </div>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                <div className="relative w-full lg:w-[480px]">
                  <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    className="h-12 rounded-2xl border-cyan-200/15 bg-slate-950/35 pl-11 text-sm font-bold"
                    placeholder="Search players, schools..."
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {POSITIONS.map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setPosition(value)}
                      className={cn(
                        "h-10 rounded-2xl border px-4 text-[10px] font-black uppercase tracking-[0.14em] transition",
                        position === value
                          ? "border-cyan-200/50 bg-cyan-300 text-slate-950 shadow-[0_0_22px_rgba(103,232,249,0.24)]"
                          : "border-white/10 bg-white/5 text-muted-foreground hover:border-cyan-200/30 hover:text-cyan-100"
                      )}
                    >
                      {value}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-[72px_minmax(0,1fr)_96px_110px_180px] border-b border-cyan-100/10 px-5 py-3 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
            <span>RK</span>
            <span>Player</span>
            <span>Pos</span>
            <span>Proj</span>
            <span className="text-right">Action</span>
          </div>

          <div className="max-h-[690px] overflow-y-auto">
            {playersLoading ? (
              <div className="flex min-h-40 items-center justify-center gap-3 px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" /> Loading real player board...
              </div>
            ) : playersError ? (
              <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-red-300">
                Unable to load players. Start the backend API and try again.
              </div>
            ) : visiblePlayers.length === 0 ? (
              <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                {showMasterBoardPreview
                  ? "No players found on the master draft board."
                  : legalPositions.length === 0
                  ? "Roster is full. No legal picks remain."
                  : position !== "ALL" && !legalPositions.includes(position as (typeof legalPositions)[number])
                    ? `No ${position} players fit your remaining roster slots.`
                    : `No legal players available for your remaining roster slots. Remaining legal positions: ${legalPositions.join(", ")}.`}
              </div>
            ) : (
              visiblePlayers.map((player) => {
                const positionClass = POSITION_STYLES[player.pos] ?? "border-white/20 bg-white/10 text-foreground";
                const isSelected = selectedPlayerId === player.id;
                const visibleRank = player.masterDraftRank ?? player.draftRank;
                return (
                  <div
                    key={player.id}
                    data-testid="draft-player-row"
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedPlayerId(player.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedPlayerId(player.id);
                      }
                    }}
                    className={cn(
                      "grid cursor-pointer grid-cols-[72px_minmax(0,1fr)_96px_110px_180px] items-center gap-3 border-b border-cyan-100/10 px-5 py-4 outline-none transition-colors hover:bg-cyan-300/[0.045] focus:bg-cyan-300/[0.06]",
                      isSelected && "bg-cyan-300/[0.075] shadow-[inset_3px_0_0_rgba(103,232,249,0.75)]"
                    )}
                  >
                    <p className="text-xl font-black tabular-nums text-muted-foreground">{visibleRank}</p>
                    <div className="min-w-0">
                      <p className="truncate text-base font-black text-foreground transition-colors hover:text-cyan-100">{player.name}</p>
                      <p className="mt-1 truncate text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">{player.school}</p>
                    </div>
                    <span className={cn("w-fit rounded-full border px-4 py-2 text-xs font-black", positionClass)}>{player.pos}</span>
                    <p className="text-sm font-black tabular-nums text-foreground">{player.projectedPoints.toFixed(1)}</p>
                    <div className="flex justify-end">
                      <Button
                        className={cn(
                          "h-10 rounded-2xl px-5 text-[10px] font-black uppercase tracking-[0.14em]",
                          canPick
                            ? "bg-gradient-to-r from-cyan-300 to-blue-500 text-slate-950"
                            : "border border-white/10 bg-white/[0.04] text-muted-foreground"
                        )}
                        disabled={!canPick}
                        onClick={(event) => {
                          event.stopPropagation();
                          makePick(player);
                        }}
                        title={
                          isScheduledPreview
                            ? isLeagueFull
                              ? "Draft picks unlock at the scheduled start time."
                              : "Draft picks unlock after the league is full."
                            : undefined
                        }
                      >
                        {pickMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : !canPick && isScheduledPreview ? (
                          <><Lock className="mr-2 h-3.5 w-3.5" />{actionLabel}</>
                        ) : (
                          actionLabel
                        )}
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>

      {selectedPlayer ? (
        <aside className="fixed bottom-0 right-0 top-0 z-[1300] flex w-full max-w-[380px] flex-col border-l border-cyan-200/15 bg-[#071225]/96 shadow-[-24px_0_80px_rgba(8,145,178,0.22)] backdrop-blur-2xl">
          <div className="border-b border-cyan-100/10 p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-200">Player Card</p>
                <h2 className="mt-3 truncate text-2xl font-black tracking-tight text-white">{selectedPlayer.name}</h2>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                  {selectedPlayer.school} • Master Rank #{selectedPlayer.masterDraftRank ?? selectedPlayer.draftRank}
                </p>
              </div>
              <button
                type="button"
                aria-label="Close player card"
                onClick={() => setSelectedPlayerId(null)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-muted-foreground transition hover:border-cyan-200/30 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <span className={cn("rounded-full border px-4 py-2 text-xs font-black", POSITION_STYLES[selectedPlayer.pos])}>{selectedPlayer.pos}</span>
              <span className="rounded-full border border-cyan-200/15 bg-cyan-300/10 px-4 py-2 text-xs font-black tabular-nums text-cyan-100">
                {selectedPlayer.projectedPoints.toFixed(1)} PROJ
              </span>
            </div>
          </div>
          <div className="border-b border-cyan-100/10 px-5 py-3">
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: "about", label: "About", icon: Info },
                { id: "injuries", label: "Alerts", icon: AlertTriangle },
                { id: "stats", label: "Stats", icon: ClipboardList },
                { id: "projections", label: "Proj", icon: Activity },
              ].map((tab) => {
                const Icon = tab.icon;
                const isActive = activePlayerCardTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActivePlayerCardTab(tab.id as PlayerCardTab)}
                    className={cn(
                      "flex items-center justify-center gap-2 rounded-2xl border px-3 py-2 text-[9px] font-black uppercase tracking-[0.16em] transition",
                      isActive
                        ? "border-cyan-200/50 bg-cyan-300 text-slate-950"
                        : "border-white/10 bg-white/[0.04] text-muted-foreground hover:border-cyan-200/30 hover:text-cyan-100"
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {playerCardLoading ? (
              <div className="flex min-h-40 items-center justify-center gap-3 rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4 text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading player card...
              </div>
            ) : activePlayerCardTab === "about" ? (
              <section className="rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">About Player</p>
                {playerCard?.about.headshot_url ? (
                  <img
                    src={playerCard.about.headshot_url}
                    alt={selectedPlayer.name}
                    className="mt-4 h-28 w-28 rounded-3xl border border-cyan-200/15 object-cover"
                  />
                ) : null}
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {[
                    ["Height", playerCard?.about.height],
                    ["Weight", playerCard?.about.weight],
                    ["Class", playerCard?.about.player_class ?? selectedPlayer.playerClass],
                    ["Birthplace", playerCard?.about.birthplace],
                    ["Status", playerCard?.about.status ?? selectedPlayer.status],
                    ["Jersey", playerCard?.about.jersey],
                    ["Position", playerCard?.about.position ?? selectedPlayer.pos],
                    ["Team", playerCard?.about.team ?? selectedPlayer.school],
                  ].map(([label, value]) => (
                    <div key={`about-${label}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                      <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
                      <p className="mt-2 text-sm font-black text-white">{formatCardValue(value)}</p>
                    </div>
                  ))}
                </div>
                {playerCard?.about.message ? (
                  <p className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-400/10 p-3 text-xs font-bold leading-5 text-amber-100">
                    {playerCard.about.message}
                  </p>
                ) : null}
              </section>
            ) : activePlayerCardTab === "injuries" ? (
              <section className="rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">Injury Report / Alerts</p>
                {playerCard?.injuries.length ? (
                  <div className="mt-4 space-y-3">
                    {playerCard.injuries.map((injury) => (
                      <div key={injury.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-black text-white">{injury.status}</p>
                          <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                            {injury.season} W{injury.week}
                          </p>
                        </div>
                        <p className="mt-2 text-xs font-bold leading-5 text-slate-200">
                          {[injury.body_part, injury.injury, injury.practice_level, injury.return_timeline].filter(Boolean).join(" • ") || "No injury detail provided."}
                        </p>
                        <p className="mt-2 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                          Source: {injury.source ?? "unknown"} • Last seen:{" "}
                          {injury.last_seen_at ? new Date(injury.last_seen_at).toLocaleString() : "Not reported"}
                        </p>
                        {injury.notes ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{injury.notes}</p> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm font-bold leading-6 text-muted-foreground">
                    No injury alerts are recorded for this player yet.
                  </p>
                )}
              </section>
            ) : activePlayerCardTab === "stats" ? (
              <section className="rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">Past Season Stats</p>
                {playerCard?.season_stats.length ? (
                  <div className="mt-4 space-y-3">
                    {playerCard.season_stats.map((row) => (
                      <div key={`${row.source}-${row.season}-${row.week}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-black text-white">{row.season}{row.week > 0 ? ` • Week ${row.week}` : " Season"}</p>
                          <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">{row.source}</p>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          {statDisplayKeys
                            .map(([label, keys]) => [label, getStatValue(row.stats, keys)] as const)
                            .filter(([, value]) => value !== null)
                            .slice(0, 8)
                            .map(([label, value]) => (
                              <div key={`${row.source}-${row.season}-${row.week}-${label}`} className="rounded-xl bg-white/[0.04] p-2">
                                <p className="text-[8px] font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
                                <p className="mt-1 text-sm font-black tabular-nums text-white">{formatCardValue(value)}</p>
                              </div>
                            ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm font-bold leading-6 text-muted-foreground">
                    No past season stats are available yet. This can be blank for first-year players.
                  </p>
                )}
              </section>
            ) : (
              <>
                <section className="rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">Projected 2026</p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    {statRowsForPosition(selectedPlayer.pos).map((row) => (
                      <div key={`projection-${row.label}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                        <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">{row.label}</p>
                        <p className="mt-2 text-lg font-black tabular-nums text-white">
                          {formatStat(statValue(projectionStatsForPlayer(selectedPlayer), row.projectionKeys))}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>
                <section className="mt-4 rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">Draft Note</p>
                  <p className="mt-3 text-sm font-medium leading-6 text-slate-200">
                    This real draft room uses the same master board ranking model as the single-player mock draft. Picks stay locked until the scheduled start time.
                  </p>
                </section>
              </>
            )}
          </div>
        </aside>
      ) : null}
    </div>
  );
}
