import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Bot, ClipboardList, LocateFixed, Loader2, RefreshCcw, Search, Trophy, User } from "lucide-react";

import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useDraftPlayerPool, usePlayerCard, usePlayerDetail } from "@/hooks/use-players";
import { buildDraftBoard, type DraftPlayer } from "@/lib/draftRankings";
import { mergeMockDraftMasterBoardPlayers } from "@/lib/mockDraftMasterBoard";
import {
  advanceSinglePlayerMockDraft,
  buildMockRoster,
  createSinglePlayerMockDraft,
  getCenteredDraftCarouselScrollLeft,
  getCurrentTeam,
  getDraftablePlayersForTeam,
  getLegalMockPositionsForTeam,
  getMockDraftSettings,
  getMockTeamCount,
  getMockTotalPicks,
  getRoundNumber,
  getRoundPick,
  getSecondsRemaining,
  getTeamIdForPick,
  isPickTimerDanger,
  isUserOnClock,
  makeUserMockPick,
  resolveInitialSinglePlayerMockDraftState,
  toggleQueuedMockPlayer,
  type MockDraftPick,
  type SinglePlayerMockDraftState,
} from "@/lib/singlePlayerMockDraft";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "cfb_single_player_mock_draft";
const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"];

type MockDraftTab = "draft" | "queue" | "roster" | "history";

const MOCK_TABS: Array<{ value: MockDraftTab; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "queue", label: "Queue" },
  { value: "roster", label: "Roster" },
  { value: "history", label: "History" },
];

const formatPlayerPoolError = (error: unknown) => {
  if (error instanceof Error && error.message) return error.message;
  return "Unable to load players. Start the backend API and try again.";
};

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

const readStoredDraft = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SinglePlayerMockDraftState;
  } catch {
    return null;
  }
};

const formatTimer = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
};

const groupPicksByRound = (picks: MockDraftPick[]) => {
  const rounds = new Map<number, MockDraftPick[]>();
  for (const pick of picks) {
    rounds.set(pick.round, [...(rounds.get(pick.round) ?? []), pick]);
  }
  return [...rounds.entries()].sort(([left], [right]) => left - right);
};

export default function SinglePlayerMockDraftRoom() {
  const navigate = useNavigate();
  const location = useLocation();
  const [initialDraftResolution] = useState(() =>
    resolveInitialSinglePlayerMockDraftState({
      search: location.search,
      storedState: readStoredDraft(),
    })
  );
  const [draftState, setDraftState] = useState<SinglePlayerMockDraftState>(
    initialDraftResolution.state
  );
  const [now, setNow] = useState(Date.now());
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 150);
  const [position, setPosition] = useState("ALL");
  const [activeTab, setActiveTab] = useState<MockDraftTab>("draft");
  const [error, setError] = useState<string | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [selectedRosterTeamId, setSelectedRosterTeamId] = useState<number | null>(null);
  const [showCompleteDialog, setShowCompleteDialog] = useState(false);
  const carouselRef = useRef<HTMLDivElement | null>(null);
  const pickRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());
  const { data: playersPayload, isLoading, isError, error: playerPoolError } = useDraftPlayerPool({
    limit: 200,
    fetchAll: true,
    sort: "draft_rank",
  });
  const mockSettings = getMockDraftSettings(draftState);
  const teamCount = getMockTeamCount(draftState);
  const totalPicks = getMockTotalPicks(draftState);
  const mockPlayerPool = useMemo(
    () => mergeMockDraftMasterBoardPlayers(playersPayload?.data ?? []),
    [playersPayload?.data]
  );

  const draftBoard = useMemo(
    () =>
      buildDraftBoard(mockPlayerPool, {
        leagueSize: mockSettings.leagueSize,
        totalRosterSpots: mockSettings.rounds,
        rosterSlots: {
          QB: 1,
          RB: 2,
          WR: 2,
          TE: 1,
          K: 1,
          BE: 5,
          IR: 0,
        },
      }),
    [mockSettings.leagueSize, mockPlayerPool]
  );

  const selectedBoardPlayer = useMemo(
    () => draftBoard.find((player) => player.id === selectedPlayerId) ?? null,
    [draftBoard, selectedPlayerId]
  );
  const selectedPlayerHasBackendRecord =
    typeof selectedPlayerId === "number" && selectedPlayerId > 0;
  const { data: selectedPlayerDetail } = usePlayerDetail(
    selectedPlayerId,
    selectedPlayerHasBackendRecord
  );
  const selectedPlayer = useMemo(() => {
    if (!selectedPlayerDetail && !selectedBoardPlayer) return null;
    return {
      ...(selectedPlayerDetail ?? {}),
      ...(selectedBoardPlayer ?? {}),
      masterDraftRank: selectedBoardPlayer?.masterDraftRank ?? selectedBoardPlayer?.draftRank ?? selectedPlayerDetail?.rank ?? 0,
      draftRank: selectedBoardPlayer?.masterDraftRank ?? selectedBoardPlayer?.draftRank ?? selectedPlayerDetail?.rank ?? 0,
      projectedPoints: selectedBoardPlayer?.projectedPoints ?? selectedPlayerDetail?.projection.fpts ?? 0,
      tier: selectedBoardPlayer?.tier ?? 1,
      tprScore: selectedBoardPlayer?.tprScore ?? 0,
      marScore: selectedBoardPlayer?.marScore ?? 0,
      adpRank: selectedBoardPlayer?.adpRank ?? selectedPlayerDetail?.adp ?? 0,
      adpEstimate: selectedBoardPlayer?.adpEstimate ?? selectedPlayerDetail?.adp ?? 0,
      sourceBoardRank: selectedBoardPlayer?.sourceBoardRank ?? selectedPlayerDetail?.boardRank ?? null,
    } as DraftPlayer;
  }, [selectedBoardPlayer, selectedPlayerDetail]);
  const { data: selectedPlayerCard, isLoading: selectedPlayerCardLoading } = usePlayerCard(
    selectedPlayer?.id,
    Boolean(selectedPlayer && selectedPlayer.id > 0)
  );

  useEffect(() => {
    if (initialDraftResolution.shouldClearStoredDraft) {
      localStorage.removeItem(STORAGE_KEY);
    }
    if (initialDraftResolution.shouldReplaceUrl) {
      navigate("/draft/mock/single-player", { replace: true });
    }
  }, [initialDraftResolution.shouldClearStoredDraft, initialDraftResolution.shouldReplaceUrl, navigate]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draftState));
  }, [draftState]);

  useEffect(() => {
    if (draftState.status === "complete") {
      setShowCompleteDialog(true);
    }
  }, [draftState.status]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      const tickNow = Date.now();
      setNow(tickNow);
      setDraftState((current) =>
        draftBoard.length ? advanceSinglePlayerMockDraft(current, draftBoard, tickNow) : current
      );
    }, 500);
    return () => window.clearInterval(interval);
  }, [draftBoard]);

  const centerDraftCarouselOnPick = useCallback(
    (overallPick: number, behavior: ScrollBehavior = "smooth") => {
      const container = carouselRef.current;
      const activeCard = pickRefs.current.get(overallPick);
      if (!container || !activeCard) return;

      container.scrollTo({
        left: getCenteredDraftCarouselScrollLeft({
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
    centerDraftCarouselOnPick(draftState.currentPick);
  };

  const currentTeam = getCurrentTeam(draftState);
  const userDraftBoardTeam = useMemo(
    () => draftState.teams.find((team) => team.id === draftState.userTeamId) ?? null,
    [draftState.teams, draftState.userTeamId]
  );
  const userLegalPositions = useMemo(
    () => getLegalMockPositionsForTeam(draftState, draftState.userTeamId),
    [draftState]
  );
  const draftablePlayersForUserTeam = useMemo(
    () => getDraftablePlayersForTeam(draftBoard, draftState, draftState.userTeamId),
    [draftBoard, draftState]
  );
  const draftablePlayerIds = useMemo(
    () => new Set(draftablePlayersForUserTeam.map((player) => player.id)),
    [draftablePlayersForUserTeam]
  );

  const availablePlayers = useMemo(() => {
    const normalizedSearch = debouncedSearch.trim().toLowerCase();
    const filteredPlayers = draftablePlayersForUserTeam.filter((player) => {
      const matchesPosition = position === "ALL" || player.pos === position;
      const matchesSearch =
        !normalizedSearch ||
        player.name.toLowerCase().includes(normalizedSearch) ||
        player.school.toLowerCase().includes(normalizedSearch);
      return matchesPosition && matchesSearch;
    });

    if (position === "ALL") {
      return filteredPlayers;
    }

    return [...filteredPlayers].sort((left, right) => {
      if (left.projectedPoints !== right.projectedPoints) {
        return right.projectedPoints - left.projectedPoints;
      }
      const leftRank = left.masterDraftRank ?? left.draftRank;
      const rightRank = right.masterDraftRank ?? right.draftRank;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return left.name.localeCompare(right.name);
    });
  }, [draftablePlayersForUserTeam, position, debouncedSearch]);

  const queuedPlayers = useMemo(() => {
    const byId = new Map(draftBoard.map((player) => [player.id, player]));
    return draftState.queuedPlayerIds
      .map((playerId) => byId.get(playerId))
      .filter((player): player is DraftPlayer => Boolean(player));
  }, [draftBoard, draftState.queuedPlayerIds]);

  useEffect(() => {
    if (
      selectedRosterTeamId !== null &&
      !draftState.teams.some((team) => team.id === selectedRosterTeamId)
    ) {
      setSelectedRosterTeamId(null);
    }
  }, [draftState.teams, selectedRosterTeamId]);

  const selectedRosterTeam = useMemo(() => {
    const fallbackTeam =
      draftState.teams.find((team) => team.id === draftState.userTeamId) ?? draftState.teams[0];
    return (
      draftState.teams.find((team) => team.id === selectedRosterTeamId) ??
      fallbackTeam
    );
  }, [draftState.teams, draftState.userTeamId, selectedRosterTeamId]);

  const selectedRoster = useMemo(
    () => buildMockRoster(draftState, selectedRosterTeam?.id ?? draftState.userTeamId),
    [draftState, selectedRosterTeam?.id]
  );
  const secondsRemaining = getSecondsRemaining(draftState, now);
  const timerDanger = isPickTimerDanger(draftState, secondsRemaining);
  const userOnClock = isUserOnClock(draftState);
  const draftedCount = draftState.picks.length;
  const latestPick = draftState.picks[draftState.picks.length - 1];
  const historyRounds = useMemo(() => groupPicksByRound(draftState.picks), [draftState.picks]);

  const draftOrderPicks = useMemo(
    () =>
      Array.from({ length: totalPicks }, (_, index) => {
        const overallPick = index + 1;
        const teamId = getTeamIdForPick(overallPick, teamCount);
        const team = draftState.teams.find((row) => row.id === teamId);
        const pick = draftState.picks.find((row) => row.overallPick === overallPick);
        return {
          overallPick,
          round: getRoundNumber(overallPick, teamCount),
          roundPick: getRoundPick(overallPick, teamCount),
          teamId,
          team,
          pick,
        };
      }),
    [draftState.picks, draftState.teams, teamCount, totalPicks]
  );

  const resetDraft = () => {
    const freshDraft = createSinglePlayerMockDraft(Date.now(), mockSettings);
    setDraftState(freshDraft);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(freshDraft));
    setActiveTab("draft");
    setSelectedRosterTeamId(null);
    setShowCompleteDialog(false);
    setError(null);
  };

  const viewDraftedRoster = () => {
    setSelectedRosterTeamId(draftState.userTeamId);
    setActiveTab("roster");
    setShowCompleteDialog(false);
  };

  const draftPlayer = (playerId: number) => {
    setError(null);
    try {
      setDraftState((current) => makeUserMockPick(current, draftBoard, playerId));
      setActiveTab("draft");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to make pick.");
    }
  };

  const toggleQueue = (playerId: number) => {
    setDraftState((current) => toggleQueuedMockPlayer(current, playerId));
  };

  const renderAvailablePlayers = () => (
    <section data-testid="available-players-table" className="overflow-hidden rounded-[2rem] border border-cyan-200/15 bg-card/50 shadow-[0_0_56px_rgba(34,211,238,0.12),inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="border-b border-cyan-100/10 p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-cyan-200 drop-shadow-[0_0_14px_rgba(103,232,249,0.28)]">Available Players</p>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">
              Showing your roster needs: {userDraftBoardTeam?.name ?? "Your Team"}
            </p>
            <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/80">
              Your legal positions: {userLegalPositions.length ? userLegalPositions.join(", ") : "None"}
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
        {isLoading ? (
          <div className="flex min-h-40 items-center justify-center gap-3 px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading draft board...
          </div>
        ) : isError ? (
          <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-red-300">
            {formatPlayerPoolError(playerPoolError)}
          </div>
        ) : availablePlayers.length === 0 ? (
          <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
            {userLegalPositions.length === 0
              ? "Roster is full. No legal picks remain."
              : position !== "ALL" &&
                  !userLegalPositions.includes(position as (typeof userLegalPositions)[number])
                ? `No ${position} players fit your remaining roster slots.`
                : `No legal players available for your remaining roster slots. Remaining legal positions: ${userLegalPositions.join(", ")}.`}
          </div>
        ) : (
          availablePlayers.slice(0, 160).map((player) => {
            const positionClass = POSITION_STYLES[player.pos] ?? "border-white/20 bg-white/10 text-foreground";
            const positionHoverClass = POSITION_ROW_HOVER_STYLES[player.pos] ?? "hover:bg-cyan-300/[0.045] focus:bg-cyan-300/[0.06]";
            const isQueued = draftState.queuedPlayerIds.includes(player.id);
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
                <p className="text-sm font-black tabular-nums text-foreground">
                  {player.hasWeeklyProjection ? player.projectedPoints.toFixed(1) : "—"}
                </p>
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
                    className="h-10 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 px-5 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950"
                    disabled={!userOnClock || draftState.status !== "live"}
                    onClick={(event) => {
                      event.stopPropagation();
                      draftPlayer(player.id);
                    }}
                  >
                    Draft
                  </Button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );

  const renderScoutingPanel = () => {
    if (!selectedPlayer) return null;

    return (
      <PlayerCardModal
        card={selectedPlayerCard}
        loading={selectedPlayerCardLoading}
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
        title="Scouting Card"
        note="Mock draft cards use the same linked ESPN profile and cached stat endpoint as the real draft room when data is available."
      />
    );
  };

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
            return (
            <div key={player.id} className="rounded-3xl border border-white/10 bg-white/[0.035] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Queue {index + 1}</p>
                  <p className="mt-2 text-base font-black text-foreground">{player.name}</p>
                  <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">RK {player.draftRank} • {player.school}</p>
                  {!isLegalForCurrentPick ? (
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
                <Button className="h-10 flex-1 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 text-[10px] font-black uppercase tracking-[0.14em] text-slate-950" disabled={!userOnClock || draftState.status !== "live" || !isLegalForCurrentPick} onClick={() => draftPlayer(player.id)}>
                  {isLegalForCurrentPick ? "Draft" : "No Slot"}
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
    const slotByLabel = new Map(selectedRoster.map((slot) => [slot.label, slot]));
    const starterRows = [
      { label: "Quarterback", accent: "QB", slots: ["QB"] },
      { label: "Running Backs", accent: "RB", slots: ["RB 1", "RB 2"] },
      { label: "Wide Receivers", accent: "WR", slots: ["WR 1", "WR 2"] },
      { label: "Tight End", accent: "TE", slots: ["TE"] },
      { label: "Flex + Kicker", accent: "K", slots: ["FLEX", "K"] },
    ];
    const benchSlots = selectedRoster.filter((slot) => slot.label.startsWith("BENCH"));

    const renderSlotCard = (slotLabel: string) => {
      const slot = slotByLabel.get(slotLabel);
      if (!slot) return null;
      const fallbackPosition =
        slot.allowedPositions.length === 1 ? slot.allowedPositions[0] : "EMPTY";
      const position = slot.player?.position ?? fallbackPosition;
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
          <p className="mt-2 truncate text-base font-black text-foreground">{slot.player?.playerName ?? "Open Slot"}</p>
          <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.16em] opacity-80">
            {slot.player
              ? `${slot.player.school} • ${slot.player.projectedPoints.toFixed(1)}`
              : "Waiting for pick"}
          </p>
          {slot.player ? (
            <span className="mt-2 inline-flex rounded-full bg-black/20 px-2.5 py-0.5 text-[8px] font-black uppercase tracking-[0.14em]">
              {slot.player.position}
            </span>
          ) : null}
        </div>
      );
    };

    const renderBenchSlotCard = (slot: (typeof selectedRoster)[number]) => {
      const position = slot.player?.position ?? "EMPTY";
      const style = ROSTER_POSITION_STYLES[position] ?? ROSTER_POSITION_STYLES.EMPTY;
      return (
        <div
          key={slot.label}
          className={cn(
            "grid min-h-[64px] grid-cols-[90px_minmax(0,1fr)_auto] items-center gap-3 rounded-2xl border px-4 py-3 transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5",
            "bg-slate-950/35 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
            style.border,
            style.text,
            style.hover
          )}
        >
          <p className="text-[9px] font-black uppercase tracking-[0.2em]">{slot.label}</p>
          <div className="min-w-0">
            <p className="truncate text-base font-black text-foreground">{slot.player?.playerName ?? "Open Slot"}</p>
            <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.16em] opacity-75">
              {slot.player ? `${slot.player.position} • ${slot.player.school} • ${slot.player.projectedPoints.toFixed(1)}` : "Bench reserve"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {slot.player ? (
              <span className={cn("rounded-full border px-3 py-1 text-[9px] font-black uppercase tracking-[0.14em]", POSITION_STYLES[slot.player.position])}>
                {slot.player.position}
              </span>
            ) : null}
            <div className={cn("h-2.5 w-2.5 rounded-full shadow-[0_0_18px_currentColor]", style.dot)} />
          </div>
        </div>
      );
    };

    return (
      <section className="rounded-[1.75rem] border border-cyan-200/15 bg-card/45 p-5 shadow-[0_0_44px_rgba(34,211,238,0.08),inset_0_1px_0_rgba(255,255,255,0.035)]">
        <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Roster Viewer</p>
            <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              Inspect every manager's roster by position group
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="mock-roster-team-select">
              Select roster team
            </label>
            <select
              id="mock-roster-team-select"
              value={selectedRosterTeam?.id ?? draftState.userTeamId}
              onChange={(event) => setSelectedRosterTeamId(Number(event.target.value))}
              className="h-12 min-w-[220px] rounded-2xl border border-cyan-200/25 bg-slate-950/70 px-4 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-50 shadow-[0_0_24px_rgba(34,211,238,0.12)] outline-none transition focus:border-cyan-200/60 focus:ring-2 focus:ring-cyan-300/20"
            >
              {draftState.teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.id === draftState.userTeamId ? `${team.name} (You)` : team.name}
                </option>
              ))}
            </select>
            <p className="rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              {selectedRoster.filter((slot) => slot.player).length}/{selectedRoster.length} filled
            </p>
          </div>
        </div>

        <div className="space-y-2.5">
          {starterRows.map((row) => {
            const accent = ROSTER_POSITION_STYLES[row.accent] ?? ROSTER_POSITION_STYLES.EMPTY;
            return (
              <div
                key={row.label}
                className="grid gap-2.5 rounded-3xl border border-white/10 bg-slate-950/22 p-2.5 lg:grid-cols-[132px_minmax(0,1fr)]"
              >
                <div className={cn("flex items-center rounded-2xl border px-4 py-3", accent.border, accent.bg, accent.text)}>
                  <div>
                    <p className="text-[8px] font-black uppercase tracking-[0.18em] opacity-75">Starters</p>
                    <p className="mt-1 text-xs font-black uppercase tracking-[0.13em] text-foreground">{row.label}</p>
                  </div>
                </div>
                <div className={cn("grid gap-2.5", row.slots.length > 1 && "md:grid-cols-2")}>
                  {row.slots.map(renderSlotCard)}
                </div>
              </div>
            );
          })}
        </div>

        <div className="my-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-cyan-300/45 to-cyan-300/12 shadow-[0_0_14px_rgba(103,232,249,0.34)]" />
          <div className="rounded-full border border-cyan-200/20 bg-cyan-300/10 px-4 py-1.5 text-[9px] font-black uppercase tracking-[0.2em] text-cyan-100 shadow-[0_0_20px_rgba(34,211,238,0.14)]">
            Bench / Reserve
          </div>
          <div className="h-px flex-1 bg-gradient-to-l from-transparent via-cyan-300/45 to-cyan-300/12 shadow-[0_0_14px_rgba(103,232,249,0.34)]" />
        </div>

        <div className="grid gap-2.5 xl:grid-cols-2">
          {benchSlots.map(renderBenchSlotCard)}
        </div>
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
                  <div key={pick.overallPick} className="rounded-3xl border border-white/10 bg-white/[0.035] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Pick {pick.overallPick}</p>
                      <span className={cn("rounded-full border px-3 py-1 text-[10px] font-black", POSITION_STYLES[pick.position])}>{pick.position}</span>
                    </div>
                    <p className="mt-2 text-base font-black text-foreground">{pick.playerName}</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{pick.teamName} • RK {pick.draftRank}</p>
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
              aria-label="Exit mock draft room"
              title="Exit mock draft room"
              onClick={() => navigate("/draft")}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-2xl border-cyan-200/20 bg-slate-950/70 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100 hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white">
              <Link to="/draft">Exit</Link>
            </Button>
          </div>

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
                {draftState.status === "intermission" ? "Draft Starts In" : draftState.status === "complete" ? "Draft Complete" : "Pick Timer"}
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

          <div className="flex flex-wrap items-center justify-end gap-3">
            <div
              className={cn(
                "rounded-3xl border border-cyan-200/20 bg-slate-950/72 px-6 py-4 text-right shadow-[0_0_42px_rgba(34,211,238,0.17)] backdrop-blur-xl",
                userOnClock && "border-cyan-200/50 bg-cyan-300/12 shadow-[0_0_58px_rgba(103,232,249,0.28)]"
              )}
            >
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">On Clock</p>
              <p className="text-xl font-black uppercase text-cyan-100">{draftState.status === "complete" ? "Complete" : currentTeam?.name ?? "Loading"}</p>
            </div>
            <Button variant="outline" className="h-12 rounded-2xl border-white/15 bg-slate-950/65 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-white hover:bg-white/10" onClick={resetDraft}>
              <RefreshCcw className="mr-2 h-4 w-4" /> Reset
            </Button>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-300/20 bg-red-400/10 p-4 text-sm font-bold text-red-100">{error}</div>
        ) : null}

        {latestPick ? (
          <div className="mx-auto flex w-fit items-center rounded-full border border-cyan-300/15 bg-cyan-400/10 px-5 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100">
            Last pick&nbsp;<span className="text-white">{latestPick.playerName}</span>&nbsp;to {latestPick.teamName}
          </div>
        ) : null}

        <section className="overflow-hidden rounded-[2rem] border border-cyan-200/15 bg-card/50 shadow-[0_0_70px_rgba(14,165,233,0.13),inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="flex items-center justify-between gap-4 border-b border-cyan-100/10 px-5 py-4">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.26em] text-cyan-200 drop-shadow-[0_0_14px_rgba(103,232,249,0.32)]">Draft Order</p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">Scroll every pick left to right</p>
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
                <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">{totalPicks - draftedCount} Unlocked</p>
              </div>
            </div>
          </div>
          <div ref={carouselRef} className="flex gap-4 overflow-x-auto px-5 py-5 scroll-smooth">
            {draftOrderPicks.map((slot) => {
              const isCurrent = draftState.status !== "complete" && slot.overallPick === draftState.currentPick;
              const isUser = slot.teamId === draftState.userTeamId;
              const isLocked = Boolean(slot.pick);
              return (
                <div
                  key={slot.overallPick}
                  aria-current={isCurrent ? "step" : undefined}
                  ref={(node) => {
                    if (node) {
                      pickRefs.current.set(slot.overallPick, node);
                    } else {
                      pickRefs.current.delete(slot.overallPick);
                    }
                  }}
                  className={cn(
                    "relative min-w-[178px] rounded-3xl border p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition",
                    isCurrent
                      ? "border-cyan-200/80 bg-cyan-300/14 shadow-[0_0_52px_rgba(103,232,249,0.36),inset_0_1px_0_rgba(255,255,255,0.07)]"
                      : isUser
                        ? "border-cyan-300/40 bg-cyan-400/10 shadow-[0_0_30px_rgba(34,211,238,0.18),inset_0_1px_0_rgba(255,255,255,0.05)]"
                      : "border-white/10 bg-white/[0.045] hover:border-cyan-200/20 hover:shadow-[0_0_22px_rgba(34,211,238,0.10)]",
                    isLocked && "opacity-80"
                  )}
                >
                  {isCurrent ? (
                    <div
                      aria-label="Current pick"
                      className="absolute -top-3 left-1/2 z-10 flex h-7 w-7 -translate-x-1/2 items-center justify-center rounded-full border border-cyan-100/70 bg-slate-950 text-cyan-100 shadow-[0_0_24px_rgba(103,232,249,0.55)]"
                    >
                      <LocateFixed className="h-3.5 w-3.5" />
                    </div>
                  ) : null}
                  <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">Pick {slot.overallPick}</p>
                  <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{slot.round}.{slot.roundPick}</p>
                  <div className="mt-3 flex h-8 w-8 items-center justify-center rounded-xl border border-cyan-200/30 bg-slate-950/55 text-cyan-100 shadow-[0_0_22px_rgba(103,232,249,0.24),inset_0_0_12px_rgba(103,232,249,0.08)]">
                    {isUser ? <User className="h-3.5 w-3.5 drop-shadow-[0_0_8px_rgba(103,232,249,0.65)]" /> : <Bot className="h-3.5 w-3.5 drop-shadow-[0_0_8px_rgba(103,232,249,0.65)]" />}
                  </div>
                  <p className="mt-3 truncate text-base font-black text-foreground">{slot.pick?.playerName ?? slot.team?.name ?? `Team ${slot.teamId}`}</p>
                  <p className="mt-1 truncate text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                    {slot.pick ? `${slot.pick.position} • ${slot.pick.school}` : isUser ? "Adam • You" : slot.team?.name?.replace("Team", "") ?? "Bot"}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {draftState.status === "intermission" ? (
          <div className="rounded-[2rem] border border-cyan-300/20 bg-cyan-400/10 p-5 text-center text-[10px] font-black uppercase tracking-[0.2em] text-cyan-100">
            Draft is about to begin. Bot pick #1 starts after the pre-draft reveal.
          </div>
        ) : null}

        {activeTab === "draft" ? renderAvailablePlayers() : null}
        {activeTab === "queue" ? renderQueue() : null}
        {activeTab === "roster" ? renderRoster() : null}
        {activeTab === "history" ? renderHistory() : null}
      </div>

      {renderScoutingPanel()}

      {draftState.status === "complete" && showCompleteDialog ? (
        <div className="fixed inset-0 z-[1450] flex items-center justify-center bg-slate-950/58 px-4 backdrop-blur-[7px]">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="mock-draft-complete-title"
            className="w-full max-w-[720px] overflow-hidden rounded-[2rem] border border-cyan-200/25 bg-[#071225]/92 text-center shadow-[0_0_90px_rgba(34,211,238,0.22),inset_0_1px_0_rgba(255,255,255,0.08)]"
          >
            <div className="border-b border-cyan-100/10 bg-gradient-to-br from-cyan-400/12 via-blue-500/8 to-violet-500/10 px-8 py-10">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-cyan-200/35 bg-cyan-300/12 text-cyan-100 shadow-[0_0_48px_rgba(103,232,249,0.34)]">
                <Trophy className="h-10 w-10" />
              </div>
              <p className="mt-6 text-[10px] font-black uppercase tracking-[0.28em] text-cyan-200">
                Mock Draft Complete
              </p>
              <h2
                id="mock-draft-complete-title"
                className="mt-3 text-4xl font-black uppercase tracking-tight text-white md:text-5xl"
              >
                Draft Complete
              </h2>
              <p className="mx-auto mt-4 max-w-md text-sm font-bold leading-6 text-muted-foreground">
                {totalPicks} picks completed. This single-player mock draft did not mutate real leagues,
                rosters, standings, or transactions.
              </p>
            </div>
            <div className="grid gap-3 px-8 py-6 sm:grid-cols-3">
              <Button
                type="button"
                className="h-12 rounded-2xl bg-gradient-to-r from-cyan-300 to-blue-500 px-6 text-[10px] font-black uppercase tracking-[0.16em] text-slate-950 shadow-[0_0_28px_rgba(103,232,249,0.24)]"
                onClick={viewDraftedRoster}
              >
                <ClipboardList className="mr-2 h-4 w-4" />
                View Your Roster
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-12 rounded-2xl border-cyan-200/20 bg-white/[0.04] px-6 text-[10px] font-black uppercase tracking-[0.16em] text-cyan-100 hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white"
                onClick={() => navigate("/draft")}
              >
                Exit to Draft Center
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-12 rounded-2xl border-cyan-200/20 bg-white/[0.04] px-6 text-[10px] font-black uppercase tracking-[0.16em] text-cyan-100 hover:border-cyan-200/40 hover:bg-cyan-400/12 hover:text-white"
                onClick={resetDraft}
              >
                <RefreshCcw className="mr-2 h-4 w-4" />
                Start New Mock
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[1200] flex justify-center px-4">
        <div className="pointer-events-auto grid w-full max-w-xl grid-cols-4 rounded-2xl border border-cyan-200/15 bg-slate-950/88 p-1 shadow-[0_0_40px_rgba(34,211,238,0.16)] backdrop-blur-xl">
          {MOCK_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                "rounded-xl px-4 py-3 text-[10px] font-black uppercase tracking-[0.2em] transition",
                activeTab === tab.value
                  ? "bg-gradient-to-r from-cyan-300 to-blue-400 text-slate-950 shadow-[0_0_24px_rgba(103,232,249,0.22)]"
                  : "text-muted-foreground hover:bg-white/[0.06] hover:text-cyan-100"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
