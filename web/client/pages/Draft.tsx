import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bot, ClipboardList, History, LocateFixed, Loader2, Lock, Search, ShieldAlert, Trophy, User, Users } from "lucide-react";

import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDraftPick, useDraftRoom, useStartDraft } from "@/hooks/use-draft";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useLeagueDetail } from "@/hooks/use-leagues";
import { useDraftPlayerPool, usePlayerCard } from "@/hooks/use-players";
import { ApiError } from "@/lib/api";
import { buildDraftBoard, type DraftConfig, type DraftPlayer } from "@/lib/draftRankings";
import { enrichCfb27DraftPlayers } from "@/lib/mockDraftMasterBoard";
import { filterDraftablePlayers, getLegalPositionsForRoster } from "@/lib/rosterLegality";
import { cn } from "@/lib/utils";
import type { DraftRoomPick, DraftRoomTeam } from "@/types/draft";

const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"];
const DRAFT_PLAYER_PAGE_SIZE = 200;
const DRAFT_SLOT_KEYS = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH"] as const;
type DraftTab = "draft" | "queue" | "roster" | "history";

const DRAFT_TABS: Array<{ value: DraftTab; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "queue", label: "Queue" },
  { value: "roster", label: "Roster" },
  { value: "history", label: "History" },
];

const POSITION_STYLES: Record<string, string> = {
  QB: "border-blue-300/40 bg-blue-500/15 text-blue-100 shadow-[0_0_16px_rgba(96,165,250,0.18)]",
  RB: "border-emerald-300/40 bg-emerald-500/15 text-emerald-100 shadow-[0_0_16px_rgba(74,222,128,0.18)]",
  WR: "border-violet-300/40 bg-violet-500/15 text-violet-100 shadow-[0_0_16px_rgba(196,181,253,0.18)]",
  TE: "border-amber-300/40 bg-amber-500/15 text-amber-100 shadow-[0_0_16px_rgba(251,191,36,0.18)]",
  K: "border-slate-300/40 bg-slate-400/15 text-slate-100 shadow-[0_0_16px_rgba(203,213,225,0.14)]",
};

const POSITION_ROW_HOVER_STYLES: Record<string, string> = {
  QB: "hover:bg-blue-400/[0.06] hover:shadow-[inset_3px_0_0_rgba(96,165,250,0.65),0_0_28px_rgba(96,165,250,0.10)] focus:bg-blue-400/[0.08]",
  RB: "hover:bg-emerald-400/[0.06] hover:shadow-[inset_3px_0_0_rgba(52,211,153,0.65),0_0_28px_rgba(52,211,153,0.10)] focus:bg-emerald-400/[0.08]",
  WR: "hover:bg-violet-400/[0.06] hover:shadow-[inset_3px_0_0_rgba(167,139,250,0.65),0_0_28px_rgba(167,139,250,0.10)] focus:bg-violet-400/[0.08]",
  TE: "hover:bg-amber-400/[0.06] hover:shadow-[inset_3px_0_0_rgba(251,191,36,0.65),0_0_28px_rgba(251,191,36,0.10)] focus:bg-amber-400/[0.08]",
  K: "hover:bg-slate-200/[0.06] hover:shadow-[inset_3px_0_0_rgba(226,232,240,0.65),0_0_28px_rgba(226,232,240,0.10)] focus:bg-slate-200/[0.08]",
};

const ROSTER_POSITION_STYLES: Record<string, { border: string; bg: string; text: string; dot: string; hover: string }> = {
  QB: { border: "border-blue-300/30", bg: "bg-[#0b1830]", text: "text-blue-100/85", dot: "bg-blue-400/60", hover: "hover:border-blue-300/55 hover:shadow-[0_0_34px_rgba(96,165,250,0.14)]" },
  RB: { border: "border-emerald-300/30", bg: "bg-[#0a1f24]", text: "text-emerald-100/85", dot: "bg-emerald-400/60", hover: "hover:border-emerald-300/55 hover:shadow-[0_0_34px_rgba(52,211,153,0.14)]" },
  WR: { border: "border-violet-300/30", bg: "bg-[#151530]", text: "text-violet-100/85", dot: "bg-violet-400/60", hover: "hover:border-violet-300/55 hover:shadow-[0_0_34px_rgba(167,139,250,0.14)]" },
  TE: { border: "border-amber-300/30", bg: "bg-[#211b16]", text: "text-amber-100/85", dot: "bg-amber-400/60", hover: "hover:border-amber-300/55 hover:shadow-[0_0_34px_rgba(251,191,36,0.14)]" },
  K: { border: "border-slate-300/25", bg: "bg-[#182235]", text: "text-slate-100/85", dot: "bg-slate-400/55", hover: "hover:border-slate-200/55 hover:shadow-[0_0_34px_rgba(226,232,240,0.12)]" },
  EMPTY: { border: "border-white/10", bg: "bg-[#071224]", text: "text-muted-foreground", dot: "bg-white/18", hover: "hover:border-cyan-200/18 hover:shadow-[0_0_24px_rgba(34,211,238,0.08)]" },
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
  totalRosterSpots: getTotalDraftSlots(rosterSlots),
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
      is_cpu: false,
      isPlaceholder: true,
    };
  });
};

type RealRosterSlot = {
  label: string;
  allowedPositions: string[];
  player: DraftRoomPick | null;
};

const addRosterSlots = (
  slots: RealRosterSlot[],
  label: string,
  count: number,
  allowedPositions: string[]
) => {
  Array.from({ length: Math.max(0, count) }, (_, index) => {
    slots.push({
      label: count > 1 ? `${label} ${index + 1}` : label,
      allowedPositions,
      player: null,
    });
  });
};

const createRealRosterSlots = (rosterSlots: Record<string, number> | undefined): RealRosterSlot[] => {
  const slots: RealRosterSlot[] = [];
  addRosterSlots(slots, "QB", getSlotCount(rosterSlots, "QB"), ["QB"]);
  addRosterSlots(slots, "RB", getSlotCount(rosterSlots, "RB"), ["RB"]);
  addRosterSlots(slots, "WR", getSlotCount(rosterSlots, "WR"), ["WR"]);
  addRosterSlots(slots, "TE", getSlotCount(rosterSlots, "TE"), ["TE"]);
  addRosterSlots(slots, "FLEX", getSlotCount(rosterSlots, "FLEX"), ["RB", "WR", "TE"]);
  addRosterSlots(slots, "SUPERFLEX", getSlotCount(rosterSlots, "SUPERFLEX"), ["QB", "RB", "WR", "TE"]);
  addRosterSlots(slots, "K", getSlotCount(rosterSlots, "K"), ["K"]);
  addRosterSlots(slots, "BENCH", getSlotCount(rosterSlots, "BENCH"), ["QB", "RB", "WR", "TE", "K"]);
  return slots;
};

const buildRealRoster = (
  picks: DraftRoomPick[],
  teamId: number | null | undefined,
  rosterSlots: Record<string, number> | undefined
) => {
  const slots = createRealRosterSlots(rosterSlots);
  if (!teamId) return slots;

  const teamPicks = picks
    .filter((pick) => pick.team_id === teamId)
    .sort((left, right) => left.overall_pick - right.overall_pick);

  for (const pick of teamPicks) {
    const position = (pick.player_position || "").toUpperCase();
    const slot =
      slots.find((candidate) => !candidate.player && candidate.allowedPositions.length === 1 && candidate.allowedPositions[0] === position) ??
      slots.find((candidate) => !candidate.player && !candidate.label.startsWith("BENCH") && candidate.allowedPositions.includes(position)) ??
      slots.find((candidate) => !candidate.player && candidate.label.startsWith("BENCH"));
    if (slot) slot.player = pick;
  }
  return slots;
};

const groupRealPicksByRound = (picks: DraftRoomPick[]) => {
  const rounds = new Map<number, DraftRoomPick[]>();
  for (const pick of picks) {
    rounds.set(pick.round_number, [...(rounds.get(pick.round_number) ?? []), pick]);
  }
  return [...rounds.entries()].sort(([left], [right]) => left - right);
};

const formatTimer = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
};

export default function Draft() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 150);
  const [position, setPosition] = useState("ALL");
  const [activeTab, setActiveTab] = useState<DraftTab>("draft");
  const [queuedPlayerIds, setQueuedPlayerIds] = useState<number[]>([]);
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
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
    dataUpdatedAt: draftRoomUpdatedAt,
  } = useDraftRoom(parsedLeagueId);
  const pickMutation = useDraftPick(parsedLeagueId);
  const startDraftMutation = useStartDraft(parsedLeagueId);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(interval);
  }, []);

  const draftStartsAt = useMemo(
    () => {
      const value = draftRoom?.draft_starts_at ?? league?.draft?.draft_datetime_utc;
      return value ? new Date(value) : null;
    },
    [draftRoom?.draft_starts_at, league?.draft?.draft_datetime_utc]
  );
  const memberCount = draftRoom?.teams.length ?? league?.members.length ?? 0;
  const maxTeams = league?.max_teams ?? draftRoom?.teams.length ?? 0;
  const isLeagueFull = Boolean(maxTeams > 0 && memberCount >= maxTeams);
  const isScheduledPreview = draftRoom?.status === "scheduled";
  const isPreDraft = draftRoom?.status === "pre_draft";
  const isTransition = draftRoom?.status === "transition";
  const isDraftActive = draftRoom?.status === "on_clock";
  const serverNowAtFetchMs = draftRoom?.server_time ? Date.parse(draftRoom.server_time) : Number.NaN;
  const countdownDeadline = isPreDraft
    ? draftRoom?.draft_starts_at
    : isDraftActive
      ? draftRoom?.current_pick_deadline
      : isTransition
        ? draftRoom?.transition_ends_at
        : null;
  const countdownDeadlineMs = countdownDeadline ? Date.parse(countdownDeadline) : Number.NaN;
  const adjustedNowMs =
    Number.isFinite(serverNowAtFetchMs) && draftRoomUpdatedAt
      ? serverNowAtFetchMs + Math.max(0, now - draftRoomUpdatedAt)
      : now;
  const secondsRemaining =
    Number.isFinite(countdownDeadlineMs)
      ? Math.max(0, Math.ceil((countdownDeadlineMs - adjustedNowMs) / 1000))
      : draftRoom?.seconds_remaining ?? 0;
  const timerDanger = isDraftActive && secondsRemaining > 0 && secondsRemaining <= 10;
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

  const {
    data: playersPayload,
    isLoading: playersLoading,
    isError: playersError,
    error: playersErrorObject,
  } = useDraftPlayerPool({
    league_id: parsedLeagueId,
    available_only: Boolean(parsedLeagueId),
    limit: DRAFT_PLAYER_PAGE_SIZE,
    offset: 0,
    fetchAll: true,
    sort: "draft_rank",
  });

  const realDraftPlayerPool = useMemo(
    () => enrichCfb27DraftPlayers(playersPayload?.data ?? []),
    [playersPayload?.data]
  );

  const draftBoard = useMemo(() => {
    return [...buildDraftBoard(realDraftPlayerPool, draftConfig)].sort((left, right) => {
      if (left.masterDraftRank !== right.masterDraftRank) {
        return left.masterDraftRank - right.masterDraftRank;
      }
      if (left.projectedPoints !== right.projectedPoints) {
        return right.projectedPoints - left.projectedPoints;
      }
      return left.name.localeCompare(right.name);
    });
  }, [draftConfig, realDraftPlayerPool]);

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

  const visiblePlayers = useMemo(() => {
    const normalizedSearch = debouncedSearch.trim().toLowerCase();
    const filteredPlayers = draftablePlayers.filter((player) => {
      const matchesPosition = position === "ALL" || player.pos === position;
      const matchesSearch =
        !normalizedSearch ||
        player.name.toLowerCase().includes(normalizedSearch) ||
        player.school.toLowerCase().includes(normalizedSearch);
      return matchesPosition && matchesSearch;
    });

    if (position === "ALL") return filteredPlayers;

    return [...filteredPlayers].sort((left, right) => {
      if (left.projectedPoints !== right.projectedPoints) {
        return right.projectedPoints - left.projectedPoints;
      }
      const leftRank = left.masterDraftRank ?? left.draftRank;
      const rightRank = right.masterDraftRank ?? right.draftRank;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return left.name.localeCompare(right.name);
    });
  }, [draftablePlayers, position, debouncedSearch]);

  const queuedPlayers = useMemo(() => {
    const byId = new Map(draftBoard.map((player) => [player.id, player]));
    return queuedPlayerIds
      .map((playerId) => byId.get(playerId))
      .filter((player): player is DraftPlayer => Boolean(player));
  }, [draftBoard, queuedPlayerIds]);

  useEffect(() => {
    if (
      selectedRosterTeamId !== null &&
      draftRoom &&
      !draftRoom.teams.some((team) => team.id === selectedRosterTeamId)
    ) {
      setSelectedRosterTeamId(null);
    }
  }, [draftRoom, selectedRosterTeamId]);

  const selectedPlayer = useMemo(
    () => draftBoard.find((player) => player.id === selectedPlayerId) ?? null,
    [draftBoard, selectedPlayerId]
  );
  const { data: playerCard, isLoading: playerCardLoading } = usePlayerCard(
    selectedPlayer?.id,
    Boolean(selectedPlayer && selectedPlayer.id > 0)
  );

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

  const selectedRosterTeam = useMemo(() => {
    const fallbackTeam =
      draftRoom?.teams.find((team) => team.id === draftRoom.user_team_id) ?? draftRoom?.teams[0] ?? null;
    return (
      draftRoom?.teams.find((team) => team.id === selectedRosterTeamId) ??
      fallbackTeam
    );
  }, [draftRoom?.teams, draftRoom?.user_team_id, selectedRosterTeamId]);

  const selectedRoster = useMemo(
    () => buildRealRoster(draftRoom?.picks ?? [], selectedRosterTeam?.id, draftRoom?.roster_slots),
    [draftRoom?.picks, draftRoom?.roster_slots, selectedRosterTeam?.id]
  );

  const historyRounds = useMemo(
    () => groupRealPicksByRound(draftRoom?.picks ?? []),
    [draftRoom?.picks]
  );

  const draftablePlayerIds = useMemo(
    () => new Set(draftablePlayers.map((player) => player.id)),
    [draftablePlayers]
  );

  const centerDraftCarouselOnPick = useCallback(
    (overallPick: number, behavior: ScrollBehavior = "smooth") => {
      const container = carouselRef.current;
      const activeCard = pickRefs.current.get(overallPick);
      if (!container || !activeCard) return;

      container.scrollTo({
        left: getCenteredScrollLeft({
          overallPick,
          cardOffsetLeft: activeCard.offsetLeft,
          cardWidth: activeCard.offsetWidth,
          containerWidth: container.clientWidth,
        }),
        behavior,
      });
    },
    []
  );

  const recenterDraftCarousel = () => {
    centerDraftCarouselOnPick(draftRoom?.current_pick ?? 1);
  };

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
      await pickMutation.mutateAsync({
        playerId: player.id,
        pickNumber: draftRoom.current_pick,
        draftVersion: draftRoom.draft_version,
      });
    } catch {
      // Rendered below from mutation state.
    }
  };

  const toggleQueue = (playerId: number) => {
    setQueuedPlayerIds((current) =>
      current.includes(playerId)
        ? current.filter((queuedId) => queuedId !== playerId)
        : [...current, playerId]
    );
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
  const actionLabel = isScheduledPreview || isPreDraft || isTransition ? "Locked" : draftRoom.can_make_pick ? "Draft" : "Wait";
  const completed = draftRoom.current_team_id === null || ["complete", "completed"].includes(draftRoom.status);
  const exitPath = completed ? `/league/${parsedLeagueId}/roster` : `/league/${parsedLeagueId}/lobby`;
  const backendPlayerCount = playersPayload?.total ?? 0;
  const masterBoardCount = draftBoard.length;

  const renderQueue = () => (
    <section className="rounded-[2rem] border border-white/10 bg-card/45 p-6">
      <div className="mb-5 flex items-center justify-between gap-4">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Draft Queue</p>
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">{queuedPlayers.length} queued</p>
      </div>
      {queuedPlayers.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.03] p-8 text-center text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
          Queue players from the draft tab.
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {queuedPlayers.map((player, index) => {
            const isLegalForCurrentPick = draftablePlayerIds.has(player.id);
            const isBackendPlayer = player.id > 0;
            return (
              <div key={player.id} className="rounded-3xl border border-white/10 bg-white/[0.035] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Queue {index + 1}</p>
                    <p className="mt-2 text-base font-black text-foreground">{player.name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">RK {player.masterDraftRank ?? player.draftRank} • {player.school}</p>
                    {!isBackendPlayer ? (
                      <p className="mt-2 text-[9px] font-black uppercase tracking-[0.16em] text-amber-200">
                        Needs backend sync before real draft pick
                      </p>
                    ) : !isLegalForCurrentPick ? (
                      <p className="mt-2 text-[9px] font-black uppercase tracking-[0.16em] text-amber-200">
                        No open roster slot for this pick
                      </p>
                    ) : null}
                  </div>
                  <span className={cn("rounded-full border px-3 py-1 text-xs font-black", POSITION_STYLES[player.pos])}>{player.pos}</span>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button variant="outline" className="h-10 flex-1 rounded-2xl text-[10px] font-black uppercase tracking-[0.14em]" onClick={() => toggleQueue(player.id)}>
                    Remove
                  </Button>
                  <Button
                    className="h-10 flex-1 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950"
                    disabled={!canPick || !isLegalForCurrentPick || !isBackendPlayer}
                    onClick={() => makePick(player)}
                  >
                    {!isBackendPlayer ? "Sync Req" : isLegalForCurrentPick ? "Draft" : "No Slot"}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );

  const renderRoster = () => {
    const starterSlots = selectedRoster.filter((slot) => !slot.label.startsWith("BENCH"));
    const benchSlots = selectedRoster.filter((slot) => slot.label.startsWith("BENCH"));

    const renderSlotCard = (slot: RealRosterSlot) => {
      const position = slot.player?.player_position ?? (slot.allowedPositions.length === 1 ? slot.allowedPositions[0] : "EMPTY");
      const style = ROSTER_POSITION_STYLES[position] ?? ROSTER_POSITION_STYLES.EMPTY;
      return (
        <div
          key={slot.label}
          className={cn(
            "relative min-h-[82px] overflow-hidden rounded-2xl border px-4 py-3 transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5",
            "shadow-[inset_0_1px_0_rgba(255,255,255,0.045)]",
            style.border,
            style.bg,
            style.text,
            style.hover
          )}
        >
          <div className={cn("absolute right-4 top-4 h-2.5 w-2.5 rounded-full shadow-[0_0_18px_currentColor]", style.dot)} />
          <p className="text-[9px] font-black uppercase tracking-[0.2em]">{slot.label}</p>
          <p className="mt-2 truncate text-base font-black text-foreground">{slot.player?.player_name ?? "Open Slot"}</p>
          <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.16em] opacity-80">
            {slot.player
              ? `${slot.player.player_school} • Pick ${slot.player.overall_pick}`
              : slot.allowedPositions.join("/")}
          </p>
          {slot.player ? (
            <span className="mt-2 inline-flex rounded-full bg-black/20 px-2.5 py-0.5 text-[8px] font-black uppercase tracking-[0.14em]">
              {slot.player.player_position}
            </span>
          ) : null}
        </div>
      );
    };

    return (
      <section className="rounded-[1.75rem] border border-cyan-200/15 bg-card/45 p-5 shadow-[0_0_44px_rgba(34,211,238,0.08),inset_0_1px_0_rgba(255,255,255,0.035)]">
        <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Roster Viewer</p>
            <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              Inspect every manager's drafted roster
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="real-roster-team-select">
              Select roster team
            </label>
            <select
              id="real-roster-team-select"
              value={selectedRosterTeam?.id ?? draftRoom.user_team_id ?? ""}
              onChange={(event) => setSelectedRosterTeamId(Number(event.target.value))}
              className="h-12 min-w-[220px] rounded-2xl border border-cyan-200/25 bg-slate-950/70 px-4 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-50 shadow-[0_0_24px_rgba(34,211,238,0.12)] outline-none transition focus:border-cyan-200/60 focus:ring-2 focus:ring-cyan-300/20"
            >
              {draftRoom.teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.id === draftRoom.user_team_id ? `${team.name} (You)` : team.name}
                </option>
              ))}
            </select>
            <p className="rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              {selectedRoster.filter((slot) => slot.player).length}/{selectedRoster.length} filled
            </p>
          </div>
        </div>

        <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
          {starterSlots.map(renderSlotCard)}
        </div>

        {benchSlots.length ? (
          <>
            <div className="my-5 flex items-center gap-3">
              <div className="h-px flex-1 bg-gradient-to-r from-transparent via-cyan-300/45 to-cyan-300/12 shadow-[0_0_14px_rgba(103,232,249,0.34)]" />
              <div className="rounded-full border border-cyan-200/20 bg-cyan-300/10 px-4 py-1.5 text-[9px] font-black uppercase tracking-[0.2em] text-cyan-100 shadow-[0_0_20px_rgba(34,211,238,0.14)]">
                Bench / Reserve
              </div>
              <div className="h-px flex-1 bg-gradient-to-l from-transparent via-cyan-300/45 to-cyan-300/12 shadow-[0_0_14px_rgba(103,232,249,0.34)]" />
            </div>
            <div className="grid gap-2.5 xl:grid-cols-2">{benchSlots.map(renderSlotCard)}</div>
          </>
        ) : null}
      </section>
    );
  };

  const renderHistory = () => (
    <section className="rounded-[2rem] border border-white/10 bg-card/45 p-6">
      <p className="mb-5 text-[11px] font-black uppercase tracking-[0.24em] text-primary">Draft History</p>
      {historyRounds.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.03] p-8 text-center text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
          Picks will appear here once the draft starts.
        </div>
      ) : (
        <div className="space-y-5">
          {historyRounds.map(([round, picks]) => (
            <div key={round}>
              <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100">Round {round}</p>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {picks.map((pick) => (
                  <div key={pick.id} className="rounded-3xl border border-white/10 bg-white/[0.035] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Pick {pick.overall_pick}</p>
                      <span className={cn("rounded-full border px-3 py-1 text-[10px] font-black", POSITION_STYLES[pick.player_position])}>{pick.player_position}</span>
                    </div>
                    <p className="mt-2 text-base font-black text-foreground">{pick.player_name}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{pick.team_name} • {pick.player_school}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );

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
              onClick={() => navigate(exitPath)}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-2xl border-cyan-200/20 bg-slate-950/70 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100 hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white">
              <Link to={exitPath}>Exit</Link>
            </Button>
          </div>

          {(isPreDraft || isDraftActive || isTransition) && !completed ? (
            <div className="pointer-events-none fixed left-1/2 top-3 z-[1250] -translate-x-1/2">
              <div
                className={cn(
                  "rounded-3xl border bg-slate-950/82 px-8 py-3 text-center shadow-[0_0_48px_rgba(34,211,238,0.18)] backdrop-blur-2xl transition",
                  timerDanger
                    ? "animate-pulse border-red-300/50 shadow-[0_0_58px_rgba(248,113,113,0.34)]"
                    : "border-cyan-200/20"
                )}
              >
                  <p className="text-[9px] font-black uppercase tracking-[0.26em] text-muted-foreground">
                    {isPreDraft ? "Draft Starts In" : isTransition ? "Next Pick In" : "Pick Timer"}
                  </p>
                <p
                  className={cn(
                    "mt-1 text-4xl font-black tabular-nums leading-none tracking-tight",
                    timerDanger ? "text-red-300" : "text-cyan-100"
                  )}
                >
                  {formatTimer(secondsRemaining)}
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
                {isScheduledPreview ? "Draft Lobby" : isPreDraft ? "Pre-Draft" : isTransition ? "Pick Recorded" : "On Clock"}
              </p>
              <p className="text-xl font-black uppercase text-cyan-100">
                {isScheduledPreview
                  ? isLeagueFull
                    ? draftRoom.can_start_draft
                      ? "Ready To Start"
                      : "Scheduled"
                    : "Need Managers"
                  : isPreDraft
                    ? "Starting Soon"
                    : isTransition
                      ? "Updating Board"
                      : completed
                        ? "Complete"
                        : currentTeamLabel}
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
              {draftRoom.teams.length}/{league?.max_teams ?? draftRoom.teams.length} Teams
            </span>
            {isScheduledPreview ? (
              <span className="rounded-full border border-amber-300/25 bg-amber-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-amber-100">
                {isLeagueFull
                  ? draftRoom.can_start_draft
                    ? "Commissioner can start"
                    : `Opens in ${formatCountdown(draftStartsAt, now)}`
                  : `${memberCount}/${maxTeams} Managers Joined`}
              </span>
            ) : null}
          </div>
          {isScheduledPreview ? (
            <p className="mt-5 max-w-3xl text-[11px] font-black uppercase leading-6 tracking-[0.18em] text-muted-foreground">
              {isLeagueFull
                ? "The commissioner starts the one-minute pre-draft countdown when the scheduled time arrives. Picks unlock only after the countdown ends."
                : "Draft order remains locked until every league slot is filled. Invite more managers or reschedule the draft."}
            </p>
          ) : null}
          {draftRoom.can_start_draft ? (
            <Button
              className="mt-6 h-12 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 px-6 text-[10px] font-black uppercase tracking-[0.18em] text-slate-950"
              disabled={startDraftMutation.isPending}
              onClick={() => {
                setLocalError(null);
                startDraftMutation.mutate();
              }}
            >
              {startDraftMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Start Draft"}
            </Button>
          ) : null}
        </header>

        {(localError || pickMutation.error || startDraftMutation.error) && (
          <div className="rounded-2xl border border-red-300/20 bg-red-400/10 p-4 text-sm font-bold text-red-100">
            {localError || formatApiError(pickMutation.error ?? startDraftMutation.error, "Unable to update the draft.")}
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
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={recenterDraftCarousel}
                className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-cyan-200/20 bg-slate-950/60 text-cyan-100 shadow-[0_0_28px_rgba(34,211,238,0.14)] transition hover:border-cyan-200/50 hover:bg-cyan-300/12 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200/70"
                aria-label="Center draft order on the current pick"
                title="Center current pick"
              >
                <LocateFixed className="h-4 w-4" />
              </button>
              <div className="text-right">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">{totalPicks} Picks</p>
                <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                  {Math.max(0, totalPicks - draftRoom.picks.length)} Unlocked
                </p>
              </div>
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
                    isCurrent && isDraftActive
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
                    {slot.team?.is_cpu ? <Bot className="h-3.5 w-3.5 drop-shadow-[0_0_8px_rgba(103,232,249,0.65)]" /> : <User className="h-3.5 w-3.5 drop-shadow-[0_0_8px_rgba(103,232,249,0.65)]" />}
                  </div>
                  <p className="mt-3 truncate text-base font-black text-foreground">
                    {slot.pick?.player_name ?? slot.team?.name ?? `Team ${slot.roundPick}`}
                  </p>
                  <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                    {slot.pick
                      ? `${slot.pick.player_position} • ${slot.pick.player_school}`
                      : slot.team?.isPlaceholder
                        ? "Waiting for manager"
                        : slot.team?.is_cpu
                          ? "CPU manager"
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

        {activeTab === "draft" ? (
        <section data-testid="available-players-table" className="overflow-hidden rounded-[2rem] border border-cyan-200/15 bg-card/50 shadow-[0_0_56px_rgba(34,211,238,0.12),inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="border-b border-cyan-100/10 p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-cyan-200 drop-shadow-[0_0_14px_rgba(103,232,249,0.28)]">Available Players</p>
                <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                  Showing your roster needs: {viewerDraftBoardTeamName}
                </p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/80">
                  Your legal positions: {legalPositions.length ? legalPositions.join(", ") : "None"}
                </p>
                <p className="mt-1 text-[9px] font-black uppercase tracking-[0.18em] text-amber-100/80">
                  Master board loaded: {masterBoardCount} players • Backend synced: {backendPlayerCount}
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
                {formatApiError(playersErrorObject, "Unable to load players. Start the backend API and try again.")}
              </div>
            ) : visiblePlayers.length === 0 ? (
              <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                {legalPositions.length === 0
                  ? "Roster is full. No legal picks remain."
                  : position !== "ALL" && !legalPositions.includes(position as (typeof legalPositions)[number])
                    ? `No ${position} players fit your remaining roster slots.`
                    : `No legal players available for your remaining roster slots. Remaining legal positions: ${legalPositions.join(", ")}.`}
              </div>
            ) : (
              visiblePlayers.slice(0, 180).map((player) => {
                const positionClass = POSITION_STYLES[player.pos] ?? "border-white/20 bg-white/10 text-foreground";
                const positionHoverClass = POSITION_ROW_HOVER_STYLES[player.pos] ?? "hover:bg-cyan-300/[0.045] focus:bg-cyan-300/[0.06]";
                const isSelected = selectedPlayerId === player.id;
                const isQueued = queuedPlayerIds.includes(player.id);
                const isBackendPlayer = player.id > 0;
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
                      "grid cursor-pointer grid-cols-[72px_minmax(0,1fr)_96px_110px_180px] items-center gap-3 border-b border-cyan-100/10 px-5 py-4 outline-none transition-[background-color,box-shadow,color] duration-200",
                      positionHoverClass,
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
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        className="h-10 rounded-2xl px-4 text-[10px] font-black uppercase tracking-[0.14em]"
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleQueue(player.id);
                        }}
                      >
                        {isQueued ? "Queued" : "Queue"}
                      </Button>
                      <Button
                        className={cn(
                          "h-10 rounded-2xl px-5 text-[10px] font-black uppercase tracking-[0.14em]",
                          canPick && isBackendPlayer
                            ? "bg-gradient-to-r from-cyan-300 to-blue-500 text-slate-950"
                            : "border border-white/10 bg-white/[0.04] text-muted-foreground"
                        )}
                        disabled={!canPick || !isBackendPlayer}
                        onClick={(event) => {
                          event.stopPropagation();
                          makePick(player);
                        }}
                        title={
                          isScheduledPreview || isPreDraft || isTransition
                            ? isLeagueFull
                              ? "Draft picks unlock after the commissioner starts the draft and the countdown ends."
                              : "Draft picks unlock after the league is full."
                            : !isBackendPlayer
                              ? "This master-board player needs backend CFB27 sync before a real pick can be saved."
                            : undefined
                        }
                      >
                        {pickMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : !isBackendPlayer ? (
                          "Sync Req"
                        ) : !canPick && (isScheduledPreview || isPreDraft || isTransition) ? (
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
        ) : null}
        {activeTab === "queue" ? renderQueue() : null}
        {activeTab === "roster" ? renderRoster() : null}
        {activeTab === "history" ? renderHistory() : null}
      </div>

      {selectedPlayer ? (
        <PlayerCardModal
          card={playerCard}
          loading={playerCardLoading}
          onClose={() => setSelectedPlayerId(null)}
          player={{
            id: selectedPlayer.id,
            name: selectedPlayer.name,
            school: selectedPlayer.school,
            position: selectedPlayer.pos,
            rankLabel: `Master Rank #${selectedPlayer.masterDraftRank ?? selectedPlayer.draftRank}`,
            projectedPoints: selectedPlayer.projectedPoints,
            playerClass: selectedPlayer.playerClass,
            status: selectedPlayer.status,
            projection: selectedPlayer.projection,
            sheetProjectionStats: selectedPlayer.sheetProjectionStats,
          }}
          title="Player Card"
          note="Player profiles use the linked ESPN profile when an ESPN player ID exists, plus cached stat rows already stored for this player."
        />
      ) : null}

      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[1200] flex justify-center px-4">
        <div className="pointer-events-auto grid w-full max-w-xl grid-cols-4 rounded-2xl border border-cyan-200/15 bg-slate-950/88 p-1 shadow-[0_0_40px_rgba(34,211,238,0.16)] backdrop-blur-xl">
          {DRAFT_TABS.map((tab) => {
            const Icon = tab.value === "draft" ? Trophy : tab.value === "queue" ? ClipboardList : tab.value === "roster" ? Users : History;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setActiveTab(tab.value)}
                className={cn(
                  "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-[0.2em] transition",
                  activeTab === tab.value
                    ? "bg-gradient-to-r from-cyan-300 to-blue-400 text-slate-950 shadow-[0_0_24px_rgba(103,232,249,0.22)]"
                    : "text-muted-foreground hover:bg-white/[0.06] hover:text-cyan-100"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
