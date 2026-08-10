import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Bot, ClipboardList, LocateFixed, Loader2, RefreshCcw, Search, Trophy, User } from "lucide-react";

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

      <div className="hidden grid-cols-[64px_minmax(0,1fr)_70px_110px_180px] border-b border-white/10 px-5 py-3 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground sm:grid">
        <span>RK</span>
        <span>Player</span>
        <span>Pos</span>
        <span>Proj</span>
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
                  "grid min-h-[68px] cursor-pointer grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-x-2 border-b border-white/10 px-3 py-2 outline-none transition-[background-color,box-shadow,color] duration-200 sm:min-h-0 sm:grid-cols-[64px_minmax(0,1fr)_70px_110px_180px] sm:items-center sm:gap-3 sm:px-5 sm:py-4",
                  positionHoverClass,
                  isSelected && "bg-amber-300/[0.075] shadow-[inset_3px_0_0_rgba(251,191,36,0.72)]"
                )}
              >
                <p className="row-span-2 self-center text-base font-bold tabular-nums text-muted-foreground sm:row-auto sm:text-xl sm:font-black">{visibleRank}</p>
                <div className="min-w-0 self-center sm:col-auto sm:row-auto">
                  <p className="line-clamp-2 text-sm font-black leading-4 text-foreground transition-colors hover:text-amber-100 sm:text-base sm:leading-normal">{player.name}</p>
                  <p className="mt-0.5 truncate text-[9px] font-black uppercase tracking-[0.08em] text-muted-foreground sm:mt-1 sm:text-[10px] sm:tracking-[0.18em]">{player.school}</p>
                </div>
                <div className="row-span-2 flex items-center justify-end gap-1.5 sm:contents">
                  <div className="flex flex-col items-end gap-0.5 sm:contents">
                    <span className={cn("shrink-0 rounded-lg border px-2 py-1 text-[9px] font-black sm:col-auto sm:row-auto sm:w-fit sm:rounded-full sm:px-4 sm:py-2 sm:text-xs", positionClass)}>{player.pos}</span>
                    <p className="text-[10px] font-black tabular-nums text-foreground sm:col-auto sm:block sm:text-sm">
                      <span className="sm:hidden">{formatDraftProjection({ seasonProjection: player.sheetProjectedSeasonPoints, fallbackSeasonProjection: player.sheetProjectionStats?.fpts })}</span>
                      <span className="hidden sm:inline">{formatDraftProjection({ seasonProjection: player.sheetProjectedSeasonPoints, fallbackSeasonProjection: player.sheetProjectionStats?.fpts })}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-1 sm:col-auto sm:justify-end sm:gap-2">
                  <Button
                    variant="outline"
                    className="h-10 min-h-[44px] w-10 rounded-lg px-0 text-[10px] font-black uppercase tracking-[0.08em] sm:h-10 sm:min-h-0 sm:w-auto sm:rounded-xl sm:px-4 sm:tracking-[0.14em]"
                    onClick={(event) => {
                      event.stopPropagation();
                      toggleQueue(player.id);
                    }}
                  >
                    <ClipboardList className="h-3.5 w-3.5 sm:hidden" aria-hidden="true" />
                    <span className="sr-only sm:hidden">{isQueued ? "Queued" : "Queue"}</span>
                    <span className="hidden sm:inline">{isQueued ? "Queued" : "Queue"}</span>
                  </Button>
                  <Button
                    className="h-10 min-h-[44px] rounded-lg border border-cyan-100/35 bg-[#1b3349] px-3 text-[9px] font-black uppercase tracking-[0.06em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_5px_12px_rgba(2,6,23,0.24)] transition hover:border-cyan-100/60 hover:bg-[#294d69] sm:h-10 sm:min-h-0 sm:rounded-xl sm:px-5 sm:text-[10px] sm:tracking-[0.14em]"
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
          {slot.player ? (
            <button
              type="button"
              onClick={() => setSelectedPlayerId(slot.player?.playerId ?? null)}
              className="mt-2 block max-w-full truncate text-left text-base font-black text-foreground transition-colors hover:text-cyan-100 focus:outline-none focus-visible:text-cyan-100 focus-visible:underline"
              aria-label={`Open ${slot.player.playerName} player card`}
            >
              {slot.player.playerName}
            </button>
          ) : (
            <p className="mt-2 truncate text-base font-black text-foreground">Open Slot</p>
          )}
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
            {slot.player ? (
              <button
                type="button"
                onClick={() => setSelectedPlayerId(slot.player?.playerId ?? null)}
                className="block max-w-full truncate text-left text-base font-black text-foreground transition-colors hover:text-cyan-100 focus:outline-none focus-visible:text-cyan-100 focus-visible:underline"
                aria-label={`Open ${slot.player.playerName} player card`}
              >
                {slot.player.playerName}
              </button>
            ) : (
              <p className="truncate text-base font-black text-foreground">Open Slot</p>
            )}
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
              className="h-12 w-12 rounded-2xl border-sky-100/20 bg-[#102f4e] text-slate-100 shadow-[0_8px_20px_rgba(7,27,49,0.24)] hover:border-amber-100/55 hover:bg-amber-200/14 hover:text-white"
              aria-label="Exit mock draft room"
              title="Exit mock draft room"
              onClick={() => navigate("/draft")}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-2xl border-sky-100/20 bg-[#102f4e] px-5 text-[10px] font-black uppercase tracking-[0.18em] text-slate-100 hover:border-amber-100/55 hover:bg-amber-200/14 hover:text-white">
              <Link to="/draft">Exit</Link>
            </Button>
          </div>

          <div className="pointer-events-none order-3 flex w-full justify-center sm:fixed sm:left-1/2 sm:top-3 sm:z-[1250] sm:w-auto sm:-translate-x-1/2">
            <div
              className={cn(
                  "rounded-3xl border border-sky-100/24 bg-[#102f4e]/95 px-6 py-3 text-center shadow-[0_10px_24px_rgba(7,27,49,0.30)] backdrop-blur-sm transition sm:px-8",
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
                "rounded-3xl border border-sky-100/24 bg-[#102f4e]/95 px-6 py-4 text-right shadow-[0_10px_24px_rgba(7,27,49,0.30)] backdrop-blur-sm",
                userOnClock && "border-amber-200/45 bg-amber-300/10 shadow-[0_0_28px_rgba(251,191,36,0.14)]"
              )}
            >
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-muted-foreground">On Clock</p>
              <p className="text-xl font-black uppercase text-cyan-100">{draftState.status === "complete" ? "Complete" : currentTeam?.name ?? "Loading"}</p>
            </div>
            <Button variant="outline" className="h-12 rounded-2xl border-sky-100/20 bg-[#102f4e]/90 px-5 text-[10px] font-black uppercase tracking-[0.18em] text-white hover:bg-sky-100/10" onClick={resetDraft}>
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
                return (
                  <div key={slot.overallPick} aria-current={isCurrent ? "step" : undefined} className={cn("flex w-[4.15rem] shrink-0 snap-start flex-col items-center rounded-lg border px-1 py-1.5 text-center", isCurrent ? "border-amber-200/70 bg-amber-300/12 text-amber-100" : isUser ? "border-emerald-200/45 bg-emerald-300/10 text-emerald-100" : "border-white/10 bg-white/[0.025] text-muted-foreground")}>
                    <span className="flex h-6 w-6 items-center justify-center rounded-full border border-white/12 bg-black/20">{isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}</span>
                    <span className="mt-1 whitespace-nowrap text-[9px] font-black tabular-nums">{slot.round}.{slot.roundPick}</span>
                    <span className="max-w-full truncate text-[8px] font-black uppercase tracking-[0.04em]">{isUser ? "You" : slot.team?.name?.replace("Bot Team", "B") ?? "Bot"}</span>
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
                    "relative min-w-[178px] rounded-3xl border border-white/10 bg-[#131c27] p-4 shadow-[0_8px_18px_rgba(2,6,23,0.22)] transition",
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
                  <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">Pick {slot.overallPick}</p>
                  <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{slot.round}.{slot.roundPick}</p>
                  <div className="mt-3 flex h-8 w-8 items-center justify-center rounded-xl border border-white/14 bg-black/20 text-amber-100">
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
          <div className="shrink-0 rounded-xl border border-amber-300/20 bg-amber-300/10 p-2 text-center text-[9px] font-black uppercase tracking-[0.1em] text-amber-100 sm:rounded-[2rem] sm:p-5 sm:text-[10px] sm:tracking-[0.2em]">
            Draft is about to begin. Bot pick #1 starts after the pre-draft reveal.
          </div>
        ) : null}

        <div className="flex min-h-0 flex-1 flex-col sm:block">
          {activeTab === "draft" ? renderAvailablePlayers() : null}
          {activeTab === "queue" ? <div>{renderQueue()}</div> : null}
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

      <div data-testid="draft-room-tabs" className="fixed inset-x-0 bottom-0 z-[1200] border-t border-sky-100/20 bg-[#102f4e]/96 px-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shadow-[0_-8px_24px_rgba(7,27,49,0.26)] backdrop-blur-xl sm:pointer-events-none sm:bottom-4 sm:flex sm:border-0 sm:bg-transparent sm:px-4 sm:pb-0 sm:pt-0 sm:shadow-none">
        <div className={cn("grid w-full grid-cols-4 overflow-hidden rounded-xl sm:pointer-events-auto sm:mx-auto sm:max-w-xl", draftMatteControlClass)}>
          {MOCK_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                "relative min-w-0 whitespace-nowrap px-1.5 py-3 text-[9px] font-bold uppercase leading-none tracking-[0.06em] transition after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-transparent sm:px-4 sm:text-[10px] sm:tracking-[0.16em]",
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
