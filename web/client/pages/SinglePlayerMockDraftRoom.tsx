import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ClipboardList, LocateFixed, Loader2, RefreshCcw, Search, Trophy } from "lucide-react";

import { DraftBoard } from "@/components/DraftBoard";
import { DraftOrderPickCard } from "@/components/DraftOrderPickCard";
import { PlayerCardModal } from "@/components/player/PlayerCardModal";
import { DraftRoomVisuals, draftMatteControlClass, draftMattePanelClass } from "@/components/DraftRoomVisuals";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useDraftPlayerPool, usePlayerCard, usePlayerDetail } from "@/hooks/use-players";
import { buildDraftBoard, type DraftPlayer } from "@/lib/draftRankings";
import { formatDraftProjection } from "@/lib/draft-projections";
import { mergeMockDraftMasterBoardPlayers } from "@/lib/mockDraftMasterBoard";
import {
  advanceSinglePlayerMockDraft,
  buildMockRoster,
  createRandomSinglePlayerMockDraft,
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
  reconcileSinglePlayerMockDraftState,
  resolveInitialSinglePlayerMockDraftState,
  toggleQueuedMockPlayer,
  type MockDraftPick,
  type SinglePlayerMockDraftState,
} from "@/lib/singlePlayerMockDraft";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "cfb_single_player_mock_draft";
const POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"];

type MockDraftTab = "draft" | "queue" | "board" | "roster" | "history";

const MOCK_TABS: Array<{ value: MockDraftTab; label: string }> = [
  { value: "draft", label: "Players" },
  { value: "queue", label: "Queue" },
  { value: "board", label: "Board" },
  { value: "roster", label: "Roster" },
  { value: "history", label: "History" },
];

const formatPlayerPoolError = (error: unknown) => {
  if (error instanceof Error && error.message) return error.message;
  return "Unable to load players. Start the backend API and try again.";
};

const POSITION_STYLES: Record<string, string> = {
  QB: "border-blue-300/30 bg-blue-400/[0.08] text-blue-100",
  RB: "border-emerald-300/30 bg-emerald-400/[0.08] text-emerald-100",
  WR: "border-violet-300/30 bg-violet-400/[0.08] text-violet-100",
  TE: "border-amber-300/30 bg-amber-400/[0.08] text-amber-100",
  K: "border-slate-300/30 bg-slate-200/[0.08] text-slate-100",
};

const POSITION_ROW_HOVER_STYLES: Record<string, string> = {
  QB: "hover:bg-blue-400/[0.07] hover:shadow-[inset_2px_0_0_rgba(96,165,250,0.65)] focus:bg-blue-400/[0.10]",
  RB: "hover:bg-emerald-400/[0.07] hover:shadow-[inset_2px_0_0_rgba(52,211,153,0.65)] focus:bg-emerald-400/[0.10]",
  WR: "hover:bg-violet-400/[0.07] hover:shadow-[inset_2px_0_0_rgba(167,139,250,0.65)] focus:bg-violet-400/[0.10]",
  TE: "hover:bg-amber-400/[0.07] hover:shadow-[inset_2px_0_0_rgba(251,191,36,0.65)] focus:bg-amber-400/[0.10]",
  K: "hover:bg-slate-200/[0.07] hover:shadow-[inset_2px_0_0_rgba(226,232,240,0.65)] focus:bg-slate-200/[0.10]",
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
  const selectedPlayerCardQuery = usePlayerCard(
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
    if (!draftBoard.length) return;
    setDraftState((current) => {
      const reconciliation = reconcileSinglePlayerMockDraftState(current, draftBoard);
      return reconciliation.state;
    });
  }, [draftBoard]);

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
      const center = (
        container: HTMLDivElement | null,
        cards: Map<number, HTMLDivElement | null>,
      ) => {
        const activeCard = cards.get(overallPick);
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
      };

      center(carouselRef.current, pickRefs.current);
    },
    []
  );

  const recenterDraftCarousel = () => {
    centerDraftCarouselOnPick(draftState.currentPick);
  };

  useEffect(() => {
    if (draftState.status === "complete") return;
    const frame = window.requestAnimationFrame(() => {
      centerDraftCarouselOnPick(draftState.currentPick, draftState.currentPick >= 4 ? "smooth" : "auto");
    });
    return () => window.cancelAnimationFrame(frame);
  }, [centerDraftCarouselOnPick, draftState.currentPick, draftState.status]);

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
    const freshDraft = createRandomSinglePlayerMockDraft(Date.now(), mockSettings);
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
    <section data-testid="available-players-table" className={cn("flex min-h-0 flex-1 flex-col overflow-hidden", draftMattePanelClass)}>
      <div className="shrink-0 border-b border-white/10 p-3 sm:p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-200 sm:text-[11px] sm:tracking-[0.24em]">Available Players</p>
            <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[9px] font-black uppercase tracking-[0.08em] text-muted-foreground sm:mt-2 sm:block sm:text-[10px] sm:tracking-[0.18em]">
              <span className="sm:block">Needs: {userDraftBoardTeam?.name ?? "Your Team"}</span>
              <span className="text-emerald-100/80 sm:mt-1 sm:block">Legal: {userLegalPositions.length ? userLegalPositions.join(" · ") : "None"}</span>
            </div>
          </div>
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-3">
            <div className="relative w-full lg:w-[480px]">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="h-11 rounded-xl border-white/14 bg-black/20 pl-10 text-sm font-bold sm:h-12 sm:rounded-2xl sm:pl-11"
                placeholder="Search players, schools..."
              />
            </div>
            <div data-testid="draft-player-filters" className="flex min-w-0 gap-1 overflow-x-auto pb-0.5 sm:flex-wrap sm:gap-2 sm:overflow-visible">
              {POSITIONS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPosition(value)}
                  className={cn(
                    "h-9 shrink-0 whitespace-nowrap rounded-full border px-3 text-[10px] font-bold uppercase tracking-[0.03em] transition sm:h-10 sm:px-4 sm:text-[10px] sm:font-black sm:tracking-[0.14em]",
                    position === value
                      ? "border-amber-200/55 bg-amber-200 text-slate-950 shadow-[0_8px_18px_rgba(251,191,36,0.20)]"
                      : "border-white/10 bg-white/5 text-muted-foreground hover:border-amber-200/35 hover:text-amber-100"
                  )}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[28px_minmax(0,1fr)_54px_78px] items-center gap-x-2 border-b border-white/10 px-3 py-2 text-[8px] font-black uppercase tracking-[0.14em] text-muted-foreground sm:grid-cols-[56px_minmax(0,1fr)_72px_88px_120px] sm:gap-3 sm:px-5 sm:py-3 sm:text-[9px] sm:tracking-[0.22em]">
        <span>RK</span>
        <span>Player</span>
        <span className="hidden text-right sm:block">ADP</span>
        <span className="text-right">Proj</span>
        <span className="text-right">Action</span>
      </div>

      <div data-testid="draft-player-list">
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
            const positionHoverClass = POSITION_ROW_HOVER_STYLES[player.pos] ?? "hover:bg-amber-300/[0.045] focus:bg-amber-300/[0.06]";
            const isQueued = draftState.queuedPlayerIds.includes(player.id);
            const isSelected = selectedPlayerId === player.id;
            const visibleRank = player.masterDraftRank ?? player.draftRank;
            const isLegalForCurrentPick = draftablePlayerIds.has(player.id);
            const actionIsDraft = userOnClock && draftState.status === "live";
            const actionIsDisabled = actionIsDraft && !isLegalForCurrentPick;
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
                  "grid min-h-[66px] cursor-pointer grid-cols-[28px_minmax(0,1fr)_54px_78px] items-center gap-x-2 border-b border-white/10 px-3 py-2 outline-none transition-[background-color,box-shadow,color] duration-200 sm:min-h-0 sm:grid-cols-[56px_minmax(0,1fr)_72px_88px_120px] sm:items-center sm:gap-3 sm:px-5 sm:py-3",
                  positionHoverClass,
                  isSelected && "bg-amber-300/[0.075] shadow-[inset_3px_0_0_rgba(251,191,36,0.72)]"
                )}
              >
                <p className="self-center text-base font-bold tabular-nums text-muted-foreground sm:text-xl sm:font-black">{visibleRank}</p>
                <div className="min-w-0 self-center">
                  <p className="truncate text-sm font-black leading-4 text-foreground transition-colors hover:text-amber-100 sm:text-base sm:leading-normal">{player.name}</p>
                  <div className="mt-0.5 flex min-w-0 items-center gap-1.5 sm:mt-1 sm:gap-2">
                    <p className="truncate text-[9px] font-black uppercase tracking-[0.08em] text-muted-foreground sm:text-[10px] sm:tracking-[0.18em]">{player.school}</p>
                    <span className={cn("shrink-0 rounded-md border px-1.5 py-0.5 text-[8px] font-black sm:rounded-full sm:px-2 sm:text-[9px]", positionClass)}>{player.pos}</span>
                  </div>
                </div>
                <p className="hidden text-right text-xs font-black tabular-nums text-muted-foreground sm:block">{player.adpEstimate ?? player.adpRank ?? "—"}</p>
                <p className="text-right text-[10px] font-black tabular-nums text-foreground sm:text-sm">{formatDraftProjection({ seasonProjection: player.sheetProjectedSeasonPoints, fallbackSeasonProjection: player.sheetProjectionStats?.fpts })}</p>
                  <Button
                    className={cn(
                      "h-10 min-h-[44px] w-[78px] rounded-lg px-1 text-[8px] font-black uppercase tracking-[0.04em] sm:h-10 sm:min-h-0 sm:w-[140px] sm:rounded-xl sm:px-3 sm:text-[10px] sm:tracking-[0.14em]",
                      actionIsDraft
                        ? "border border-cyan-100/35 bg-[#1b3349] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_5px_12px_rgba(2,6,23,0.24)] transition hover:border-cyan-100/60 hover:bg-[#294d69]"
                        : "border border-white/15 bg-white/[0.06] text-cyan-50 transition hover:border-cyan-100/45 hover:bg-white/[0.12]"
                    )}
                    disabled={actionIsDisabled}
                    onClick={(event) => {
                      event.stopPropagation();
                      if (actionIsDraft) {
                        draftPlayer(player.id);
                      } else {
                        toggleQueue(player.id);
                      }
                    }}
                    title={actionIsDraft ? (isLegalForCurrentPick ? `Draft ${player.name}.` : "No legal roster slot is available for this player.") : isQueued ? `Remove ${player.name} from your queue.` : `Queue ${player.name}.`}
                    aria-label={actionIsDraft ? `Draft ${player.name}` : isQueued ? `Remove ${player.name} from queue` : `Queue ${player.name}`}
                  >
                    {actionIsDraft ? (isLegalForCurrentPick ? "Draft" : "No Slot") : isQueued ? "Queued" : "Queue"}
                  </Button>
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
        card={selectedPlayerCardQuery.data}
        error={selectedPlayerCardQuery.isError}
        loading={selectedPlayerCardQuery.isLoading}
        onClose={() => setSelectedPlayerId(null)}
        onRetry={() => void selectedPlayerCardQuery.refetch()}
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
                <Button className="h-10 flex-1 rounded-2xl border border-cyan-100/35 bg-[#1b3349] text-[10px] font-black uppercase tracking-[0.14em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.28),0_8px_18px_rgba(2,6,23,0.34)] transition hover:border-cyan-100/60 hover:bg-[#294d69] hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.35),0_10px_22px_rgba(2,6,23,0.4)]" disabled={!userOnClock || draftState.status !== "live" || !isLegalForCurrentPick} onClick={() => draftPlayer(player.id)}>
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
    const filledSlots = selectedRoster.filter((slot) => slot.player).length;
    const rosterSlotLimits = selectedRoster.reduce<Record<string, number>>((limits, slot) => {
      const limitName = slot.label.startsWith("BENCH") ? "BE" : slot.label.replace(/\s+\d+$/, "");
      limits[limitName] = (limits[limitName] ?? 0) + 1;
      return limits;
    }, {});

    const renderSlotRow = (slot: (typeof selectedRoster)[number], index: number) => {
      const displayLabel = slot.label.startsWith("BENCH") ? "BE" : slot.label.replace(/\s+\d+$/, "");

      return (
        <div
          key={slot.label}
          className={cn(
            "grid min-h-14 grid-cols-[3.35rem_minmax(0,1fr)_2.4rem] items-center gap-2 border-b border-white/[0.07] px-3 py-2.5 last:border-b-0 sm:grid-cols-[4.5rem_minmax(0,1fr)_3.25rem] sm:px-5",
            index % 2 === 0 ? "bg-[#202224]" : "bg-[#1b1d1f]",
            slot.player ? "transition-colors hover:bg-[#292c2f]" : "text-slate-500"
          )}
        >
          <p className="text-center text-xs font-medium uppercase tracking-[0.04em] text-slate-400 sm:text-sm">{displayLabel}</p>
          {slot.player ? (
            <button
              type="button"
              onClick={() => setSelectedPlayerId(slot.player?.playerId ?? null)}
              className="min-w-0 text-left focus:outline-none focus-visible:underline"
              aria-label={`Open ${slot.player.playerName} player card`}
            >
              <span className="block truncate text-sm font-bold text-foreground transition-colors hover:text-white sm:text-base">{slot.player.playerName}</span>
              <span className="block truncate text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-400 sm:text-[10px]">
                {slot.player.position} · {slot.player.school} · {slot.player.projectedPoints.toFixed(1)} proj
              </span>
            </button>
          ) : (
            <p className="truncate text-sm font-medium text-slate-500 sm:text-base">Open slot</p>
          )}
          <span className="border-l border-white/10 pl-2 text-right text-xs font-medium tabular-nums text-slate-400 sm:pl-3 sm:text-sm">—</span>
        </div>
      );
    };

    return (
      <section className="overflow-hidden rounded-xl border border-white/12 bg-[#17191b] shadow-[0_8px_20px_rgba(2,6,23,0.18)]">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-white/10 bg-[#151719] px-3 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <p className="text-sm font-bold text-slate-100">{selectedRosterTeam?.id === draftState.userTeamId ? "My Team" : "Team"}</p>
            <label className="sr-only" htmlFor="mock-roster-team-select">
              Select roster team
            </label>
            <select
              id="mock-roster-team-select"
              value={selectedRosterTeam?.id ?? draftState.userTeamId}
              onChange={(event) => setSelectedRosterTeamId(Number(event.target.value))}
              className="h-8 min-w-0 max-w-[13rem] rounded-md border border-white/15 bg-[#202328] px-2.5 text-[10px] font-semibold text-slate-100 outline-none transition focus:border-slate-300/60 focus:ring-2 focus:ring-white/10 sm:min-w-[13rem]"
            >
              {draftState.teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.id === draftState.userTeamId ? `${team.name} (You)` : team.name}
                </option>
              ))}
            </select>
          </div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">{filledSlots}/{selectedRoster.length} filled</p>
          <details className="relative ml-auto">
            <summary className="cursor-pointer list-none rounded-full border border-primary/70 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-primary transition-colors hover:bg-primary/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/70">
              Position limits
            </summary>
            <div className="absolute right-0 top-[calc(100%+0.5rem)] z-30 flex min-w-44 flex-wrap gap-1.5 rounded-lg border border-white/15 bg-[#151719] p-3 shadow-xl">
              {Object.entries(rosterSlotLimits).map(([slot, count]) => (
                <span key={slot} className="rounded border border-white/10 bg-[#202328] px-2 py-1 text-[9px] font-bold uppercase tracking-[0.06em] text-slate-300">
                  {slot} {count}
                </span>
              ))}
            </div>
          </details>
        </div>

        <div className="grid grid-cols-[3.35rem_minmax(0,1fr)_2.4rem] items-center border-b border-white/10 bg-[#1a1c1e] px-3 py-2 sm:grid-cols-[4.5rem_minmax(0,1fr)_3.25rem] sm:px-5">
          <p className="text-center text-[9px] font-bold uppercase tracking-[0.08em] text-slate-100">Slot</p>
          <p className="text-[9px] font-bold uppercase tracking-[0.08em] text-slate-100">Player</p>
          <p className="border-l border-white/10 pl-2 text-right text-[9px] font-bold uppercase tracking-[0.08em] text-slate-100 sm:pl-3">Bye</p>
        </div>

        <div>{selectedRoster.map(renderSlotRow)}</div>
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

  const renderBoard = () => (
    <DraftBoard
      slots={draftOrderPicks.map((slot) => ({
        overallPick: slot.overallPick,
        round: slot.round,
        roundPick: slot.roundPick,
        teamId: slot.teamId,
        teamName: slot.team?.name ?? `Team ${slot.teamId}`,
        playerName: slot.pick?.playerName,
        playerPosition: slot.pick?.position,
        isCurrent: draftState.status !== "complete" && slot.overallPick === draftState.currentPick,
        isUser: slot.teamId === draftState.userTeamId,
      }))}
      totalRounds={mockSettings.rounds}
      followCurrentPick
      onOpenRosters={() => setActiveTab("roster")}
    />
  );

  return (
    <div data-draft-room="mock" className="relative min-h-[100dvh] overflow-x-clip text-foreground">
      <DraftRoomVisuals />

      <div className="relative mx-auto flex min-h-0 w-full max-w-[1800px] flex-1 flex-col space-y-2 px-3 pb-[calc(env(safe-area-inset-bottom)+5.5rem)] pt-[max(0.5rem,env(safe-area-inset-top))] sm:block sm:space-y-6 sm:px-4 sm:pb-[calc(env(safe-area-inset-bottom)+7.5rem)] sm:pt-4 md:px-6 md:pb-28">
        <div className="relative z-20 flex h-12 shrink-0 items-center gap-2 rounded-xl border border-white/12 bg-[#0b121a]/92 px-2 shadow-[0_8px_20px_rgba(2,6,23,0.28)] sm:hidden">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-9 w-9 shrink-0 rounded-lg border-white/15 bg-[#0b121a] text-slate-200"
            aria-label="Exit mock draft room"
            onClick={() => navigate("/draft")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[9px] font-black uppercase tracking-[0.12em] text-muted-foreground">On the clock · Pick {getRoundNumber(draftState.currentPick, teamCount)}.{getRoundPick(draftState.currentPick, teamCount)}</p>
            <p className="truncate text-sm font-black text-cyan-100">{draftState.status === "complete" ? "Draft complete" : currentTeam?.name ?? "Loading"}</p>
          </div>
          <div className={cn("shrink-0 text-right", timerDanger ? "text-red-300" : "text-cyan-100")}>
            <p className="text-[9px] font-black uppercase tracking-[0.08em] text-muted-foreground">Timer</p>
            <p className="text-2xl font-black leading-none tabular-nums">{formatTimer(secondsRemaining)}</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-9 w-9 shrink-0 rounded-lg border-white/15 bg-[#0b121a] text-slate-200"
            aria-label="Reset mock draft"
            onClick={resetDraft}
          >
            <RefreshCcw className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="relative z-20 hidden flex-wrap items-center justify-between gap-3 sm:flex">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-12 w-12 rounded-2xl border-cfb-border-subtle bg-cfb-surface-raised text-cfb-text-primary shadow-[0_8px_20px_rgba(0,0,0,0.24)] hover:border-cfb-gold/55 hover:bg-cfb-gold/10 hover:text-white"
              aria-label="Exit mock draft room"
              title="Exit mock draft room"
              onClick={() => navigate("/draft")}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-2xl border-cfb-border-subtle bg-cfb-surface-raised px-5 text-[10px] font-black uppercase tracking-[0.18em] text-cfb-text-primary hover:border-cfb-gold/55 hover:bg-cfb-gold/10 hover:text-white">
              <Link to="/draft">Exit</Link>
            </Button>
          </div>

          <div className="pointer-events-none order-3 flex w-full justify-center sm:fixed sm:left-1/2 sm:top-3 sm:z-[1250] sm:w-auto sm:-translate-x-1/2">
            <div
              className={cn(
                  "rounded-3xl border border-cfb-border-subtle bg-cfb-surface-raised/95 px-6 py-3 text-center shadow-[0_10px_24px_rgba(0,0,0,0.30)] backdrop-blur-sm transition sm:px-8",
                timerDanger
                  ? "animate-pulse border-red-300/50 shadow-[0_0_58px_rgba(248,113,113,0.34)]"
                    : "border-white/14"
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
            <div className="rounded-3xl border border-cyan-200/35 bg-cyan-400/10 px-6 py-4 text-right shadow-[0_0_42px_rgba(34,211,238,0.17)] backdrop-blur-xl">
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100">
                Your Draft Position: <span className="text-xl tabular-nums">{draftState.userTeamId}</span>
              </p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">
                {userDraftBoardTeam?.name ?? "Your Team"}
              </p>
            </div>
            <div
              className={cn(
                "rounded-3xl border border-cfb-border-subtle bg-cfb-surface-raised/95 px-6 py-4 text-right shadow-[0_10px_24px_rgba(0,0,0,0.30)] backdrop-blur-sm",
                userOnClock && "border-amber-200/45 bg-amber-300/10 shadow-[0_0_28px_rgba(251,191,36,0.14)]"
              )}
            >
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">On Clock</p>
              <p className="text-xl font-black uppercase text-cyan-100">{draftState.status === "complete" ? "Complete" : currentTeam?.name ?? "Loading"}</p>
            </div>
            <Button variant="outline" className="h-12 rounded-2xl border-cfb-border-subtle bg-cfb-surface-raised/90 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-white hover:bg-cfb-surface-hover" onClick={resetDraft}>
              <RefreshCcw className="mr-2 h-4 w-4" /> Reset
            </Button>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-300/20 bg-red-400/10 p-4 text-sm font-bold text-red-100">{error}</div>
        ) : null}

        {latestPick ? (
          <div className="flex min-w-0 shrink-0 items-center rounded-xl border border-cyan-300/15 bg-cyan-400/10 px-3 py-2 text-[9px] font-black uppercase tracking-[0.08em] text-cyan-100 sm:mx-auto sm:w-fit sm:rounded-full sm:px-5 sm:text-[10px] sm:tracking-[0.18em]">
            <span className="shrink-0">Last pick&nbsp;</span><span className="truncate text-white">{latestPick.playerName}</span><span className="shrink-0">&nbsp;to&nbsp;{latestPick.teamName}</span>
          </div>
        ) : null}

        <section data-testid="mobile-draft-order" className={cn("shrink-0 overflow-hidden sm:hidden", draftMattePanelClass)}>
          <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
            <div>
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-amber-200">Draft order</p>
              <p className="mt-0.5 text-[8px] font-bold uppercase tracking-[0.08em] text-muted-foreground">Swipe for future rounds</p>
            </div>
            <p className="text-[9px] font-black uppercase tracking-[0.08em] text-muted-foreground">{draftState.currentPick} / {totalPicks}</p>
          </div>
          <div
            data-testid="mobile-draft-order-scroll"
            aria-label="Draft order; swipe horizontally to view every pick and future rounds"
            className="overflow-x-auto overscroll-x-contain scroll-smooth snap-x px-2 py-2 touch-pan-x"
          >
            <div className="flex min-w-max gap-1.5">
              {draftOrderPicks.map((slot) => {
                const isCurrent = draftState.status !== "complete" && slot.overallPick === draftState.currentPick;
                const isUser = slot.teamId === draftState.userTeamId;
                const managerName = isUser ? "You" : slot.team?.name ?? "Bot";
                return (
                  <div key={slot.overallPick} data-testid={`mobile-draft-order-card-${slot.overallPick}`} aria-current={isCurrent ? "step" : undefined} className={cn("flex w-[4.15rem] shrink-0 snap-start flex-col items-center rounded-lg border px-1 py-1.5 text-center", isCurrent ? "border-amber-200/70 bg-amber-300/12 text-amber-100" : isUser ? "border-emerald-200/45 bg-emerald-300/10 text-emerald-100" : "border-white/10 bg-white/[0.025] text-muted-foreground")}>
                    <DraftOrderPickCard
                      compact
                      managerName={managerName}
                      isCpu={!isUser}
                      round={slot.round}
                      roundPick={slot.roundPick}
                      playerName={slot.pick?.playerName}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className={cn("hidden overflow-hidden sm:block", draftMattePanelClass)}>
          <div className="relative flex min-h-[76px] items-center justify-between gap-4 border-b border-white/10 px-5 py-4">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.26em] text-amber-200">Draft Order</p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">Scroll every pick left to right</p>
            </div>
            <button
              type="button"
              onClick={recenterDraftCarousel}
              className="absolute left-1/2 top-1/2 inline-flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[1.15rem] border border-white/16 bg-[#0b121a] text-amber-100 shadow-[0_8px_20px_rgba(2,6,23,0.32)] transition hover:border-amber-200/45 hover:bg-amber-300/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-200/60"
              aria-label="Center draft order on the current pick"
              title="Center current pick"
            >
              <LocateFixed className="h-5 w-5" />
            </button>
            <div className="ml-auto text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">{totalPicks} Picks</p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">{totalPicks - draftedCount} Unlocked</p>
            </div>
          </div>
          <div ref={carouselRef} className="flex gap-2 overflow-x-auto px-4 py-3 scroll-smooth snap-x">
            {draftOrderPicks.map((slot) => {
              const isCurrent = draftState.status !== "complete" && slot.overallPick === draftState.currentPick;
              const isUser = slot.teamId === draftState.userTeamId;
              const isLocked = Boolean(slot.pick);
              const managerName = isUser ? "You" : slot.team?.name ?? "Bot";
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
                    "relative min-w-[142px] snap-start rounded-2xl border border-white/10 bg-[#131c27] p-3 shadow-[0_8px_18px_rgba(2,6,23,0.22)] transition",
                    isCurrent
                      ? "border-amber-200/70 bg-amber-300/12 shadow-[0_0_28px_rgba(251,191,36,0.16)]"
                      : isUser
                        ? "border-emerald-200/40 bg-emerald-300/10 shadow-[0_0_22px_rgba(52,211,153,0.14)]"
                      : "hover:border-white/25 hover:bg-white/[0.055]",
                    isLocked && "opacity-80"
                  )}
                >
                  {isCurrent ? (
                    <div
                      aria-label="Current pick"
                      className="absolute -top-3 left-1/2 z-10 flex h-7 w-7 -translate-x-1/2 items-center justify-center rounded-full border border-amber-100/70 bg-[#0b121a] text-amber-100 shadow-[0_0_18px_rgba(251,191,36,0.30)]"
                    >
                      <LocateFixed className="h-3.5 w-3.5" />
                    </div>
                  ) : null}
                  <DraftOrderPickCard
                    managerName={managerName}
                    isCpu={!isUser}
                    round={slot.round}
                    roundPick={slot.roundPick}
                    playerName={slot.pick?.playerName}
                  />
                </div>
              );
            })}
          </div>
        </section>

        {draftState.status === "intermission" ? (
          <div className="shrink-0 rounded-xl border border-amber-300/20 bg-amber-300/10 p-2 text-center text-[9px] font-black uppercase tracking-[0.1em] text-amber-100 sm:rounded-[2rem] sm:p-5 sm:text-[10px] sm:tracking-[0.2em]">
            Draft is about to begin. Bot pick #1 starts after the pre-draft reveal.
          </div>
        ) : null}

        <div className="flex min-h-0 flex-1 flex-col sm:block">
          {activeTab === "draft" ? renderAvailablePlayers() : null}
          {activeTab === "queue" ? <div>{renderQueue()}</div> : null}
          {activeTab === "board" ? <div>{renderBoard()}</div> : null}
          {activeTab === "roster" ? <div>{renderRoster()}</div> : null}
          {activeTab === "history" ? <div>{renderHistory()}</div> : null}
        </div>
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
                className="h-12 rounded-2xl border border-cyan-100/35 bg-[#1b3349] px-6 text-[10px] font-black uppercase tracking-[0.16em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.28),0_8px_18px_rgba(2,6,23,0.34)] transition hover:border-cyan-100/60 hover:bg-[#294d69] hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.35),0_10px_22px_rgba(2,6,23,0.4)]"
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

      <div data-testid="draft-room-tabs" className="fixed inset-x-0 bottom-0 z-[1200] border-t border-cfb-border-subtle bg-cfb-surface-raised/96 px-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-8px_24px_rgba(0,0,0,0.26)] backdrop-blur-xl sm:pointer-events-none sm:inset-x-auto sm:bottom-3 sm:left-1/2 sm:flex sm:w-[min(100vw-3rem,60rem)] sm:-translate-x-1/2 sm:border-0 sm:bg-transparent sm:px-0 sm:pb-0 sm:pt-0 sm:shadow-none sm:backdrop-blur-none">
        <div className={cn("grid w-full grid-cols-5 overflow-hidden rounded-xl sm:pointer-events-auto sm:mx-auto sm:rounded-2xl", draftMatteControlClass)}>
          {MOCK_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              aria-current={activeTab === tab.value ? "page" : undefined}
              className={cn(
                "relative inline-flex min-h-[4.75rem] min-w-0 touch-manipulation items-center justify-center whitespace-nowrap px-2 py-3 text-xs font-black uppercase leading-none tracking-[0.02em] transition after:absolute after:inset-x-2 after:bottom-0 after:h-1 after:bg-transparent focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cfb-brand focus-visible:ring-inset sm:min-h-[3.75rem] sm:px-5 sm:py-4 sm:text-[11px] sm:tracking-[0.14em]",
                activeTab === tab.value
                  ? "bg-white/[0.04] text-white after:bg-cfb-brand"
                  : "text-muted-foreground hover:bg-white/[0.035] hover:text-white"
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
