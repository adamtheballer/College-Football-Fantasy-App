import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Bot, Loader2, RefreshCcw, Search, Trophy, User, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePlayerDetail, usePlayers, usePlayerSeasonStats } from "@/hooks/use-players";
import { buildDraftBoard, type DraftPlayer } from "@/lib/draftRankings";
import {
  advanceSinglePlayerMockDraft,
  buildMockRoster,
  createSinglePlayerMockDraft,
  getCenteredDraftCarouselScrollLeft,
  getCurrentTeam,
  getDraftablePlayersForTeam,
  getLegalMockPositionsForTeam,
  getRoundNumber,
  getRoundPick,
  getSecondsRemaining,
  getTeamIdForPick,
  isPickTimerDanger,
  isUserOnClock,
  makeUserMockPick,
  MOCK_TEAM_COUNT,
  MOCK_TOTAL_PICKS,
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

const POSITION_STYLES: Record<string, string> = {
  QB: "border-blue-300/40 bg-blue-500/15 text-blue-100 shadow-[0_0_16px_rgba(96,165,250,0.18)]",
  RB: "border-emerald-300/40 bg-emerald-500/15 text-emerald-100 shadow-[0_0_16px_rgba(74,222,128,0.18)]",
  WR: "border-violet-300/40 bg-violet-500/15 text-violet-100 shadow-[0_0_16px_rgba(196,181,253,0.18)]",
  TE: "border-amber-300/40 bg-amber-500/15 text-amber-100 shadow-[0_0_16px_rgba(251,191,36,0.18)]",
  K: "border-slate-300/40 bg-slate-400/15 text-slate-100 shadow-[0_0_16px_rgba(203,213,225,0.14)]",
};

const ROSTER_POSITION_STYLES: Record<string, { border: string; bg: string; text: string; dot: string }> = {
  QB: { border: "border-blue-300/30", bg: "bg-[#0b1830]", text: "text-blue-100/85", dot: "bg-blue-400/60" },
  RB: { border: "border-emerald-300/30", bg: "bg-[#0a1f24]", text: "text-emerald-100/85", dot: "bg-emerald-400/60" },
  WR: { border: "border-violet-300/30", bg: "bg-[#151530]", text: "text-violet-100/85", dot: "bg-violet-400/60" },
  TE: { border: "border-amber-300/30", bg: "bg-[#211b16]", text: "text-amber-100/85", dot: "bg-amber-400/60" },
  K: { border: "border-slate-300/25", bg: "bg-[#182235]", text: "text-slate-100/85", dot: "bg-slate-400/55" },
  EMPTY: { border: "border-white/10", bg: "bg-[#071224]", text: "text-muted-foreground", dot: "bg-white/18" },
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

const statValue = (
  stats: Record<string, unknown> | null | undefined,
  candidates: string[]
) => {
  if (!stats) return null;
  for (const key of candidates) {
    const value = stats[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
      return Number(value);
    }
  }
  return null;
};

const formatStat = (value: number | null | undefined) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString();
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
};

const statRowsForPosition = (position: string) => {
  if (position === "QB") {
    return [
      { label: "Pass Yds", projectionKeys: ["pass_yds", "passingYards"], previousKeys: ["PassingYards", "Passing Yards", "pass_yards", "pass_yds"] },
      { label: "Pass TD", projectionKeys: ["pass_tds", "passingTds"], previousKeys: ["PassingTouchdowns", "Passing TD", "pass_tds"] },
      { label: "INT", projectionKeys: ["ints", "interceptions"], previousKeys: ["Interceptions", "ints", "interceptions"] },
      { label: "Rush Yds", projectionKeys: ["rush_yds", "rushingYards"], previousKeys: ["RushingYards", "Rushing Yards", "rush_yards", "rush_yds"] },
      { label: "Rush TD", projectionKeys: ["rush_tds", "rushingTds"], previousKeys: ["RushingTouchdowns", "Rushing TD", "rush_tds"] },
    ];
  }

  if (position === "K") {
    return [
      { label: "FG", projectionKeys: ["fg", "field_goals"], previousKeys: ["FieldGoalsMade", "FieldGoals", "fg"] },
      { label: "XP", projectionKeys: ["xp", "extra_points"], previousKeys: ["ExtraPointsMade", "ExtraPoints", "xp"] },
      { label: "Fantasy", projectionKeys: ["fpts"], previousKeys: ["FantasyPoints", "fantasy_points", "fpts"] },
    ];
  }

  return [
    { label: "Rush Yds", projectionKeys: ["rush_yds", "rushingYards"], previousKeys: ["RushingYards", "Rushing Yards", "rush_yards", "rush_yds"] },
    { label: "Rush TD", projectionKeys: ["rush_tds", "rushingTds"], previousKeys: ["RushingTouchdowns", "Rushing TD", "rush_tds"] },
    { label: "Rec", projectionKeys: ["receptions"], previousKeys: ["Receptions", "receptions"] },
    { label: "Rec Yds", projectionKeys: ["rec_yds", "receivingYards"], previousKeys: ["ReceivingYards", "Receiving Yards", "rec_yards", "rec_yds"] },
    { label: "Rec TD", projectionKeys: ["rec_tds", "receivingTds"], previousKeys: ["ReceivingTouchdowns", "Receiving TD", "rec_tds"] },
  ];
};

const projectionStatsForPlayer = (player: DraftPlayer | null) => {
  if (!player) return null;
  return {
    ...(player.sheetProjectionStats ?? {}),
    passingYards: player.projection.passingYards,
    passingTds: player.projection.passingTds,
    ints: player.projection.ints,
    rushingYards: player.projection.rushingYards,
    rushingTds: player.projection.rushingTds,
    receptions: player.projection.receptions,
    receivingYards: player.projection.receivingYards,
    receivingTds: player.projection.receivingTds,
    fpts: player.projectedPoints,
  };
};

const buildPlayerSummary = (
  player: DraftPlayer,
  previousStats: Record<string, unknown> | null | undefined
) => {
  const rank = player.masterDraftRank ?? player.draftRank;
  const hasPreviousStats = Boolean(previousStats && Object.keys(previousStats).length);
  const role =
    player.pos === "QB"
      ? "passing and rushing profile"
      : player.pos === "K"
        ? "kicking volume profile"
        : "touch and yardage profile";

  return `${player.name} enters the 2026 projection board as ${player.school}'s ${player.pos} with a master mock rank of #${rank}. The sheet projects ${player.projectedPoints.toFixed(1)} fantasy points, so this card treats him as a ${role} rather than inventing outside context. ${
    hasPreviousStats
      ? "The 2025 section uses the cached SportsData feed where available."
      : "No cached 2025 stat line is available yet, so missing fields are shown as dashes."
  }`;
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
  const [position, setPosition] = useState("ALL");
  const [activeTab, setActiveTab] = useState<MockDraftTab>("draft");
  const [error, setError] = useState<string | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const carouselRef = useRef<HTMLDivElement | null>(null);
  const pickRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());
  const { data: playersPayload, isLoading, isError } = usePlayers({
    limit: 1000,
    sort: "draft_rank",
  });

  const draftBoard = useMemo(
    () =>
      buildDraftBoard(playersPayload?.data ?? [], {
        leagueSize: 12,
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
    [playersPayload?.data]
  );

  const selectedBoardPlayer = useMemo(
    () => draftBoard.find((player) => player.id === selectedPlayerId) ?? null,
    [draftBoard, selectedPlayerId]
  );
  const { data: selectedPlayerDetail } = usePlayerDetail(selectedPlayerId, selectedPlayerId !== null);
  const { data: selectedPlayerSeasonStats } = usePlayerSeasonStats(
    selectedPlayerId,
    2025,
    selectedPlayerId !== null
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
    const interval = window.setInterval(() => {
      const tickNow = Date.now();
      setNow(tickNow);
      setDraftState((current) =>
        draftBoard.length ? advanceSinglePlayerMockDraft(current, draftBoard, tickNow) : current
      );
    }, 500);
    return () => window.clearInterval(interval);
  }, [draftBoard]);

  useEffect(() => {
    const container = carouselRef.current;
    const activeCard = pickRefs.current.get(draftState.currentPick);
    if (!container || !activeCard) return;

    container.scrollTo({
      left: getCenteredDraftCarouselScrollLeft({
        overallPick: draftState.currentPick,
        cardOffsetLeft: activeCard.offsetLeft,
        cardWidth: activeCard.offsetWidth,
        containerWidth: container.clientWidth,
      }),
      behavior: "smooth",
    });
  }, [draftState.currentPick, draftState.status]);

  const currentTeam = getCurrentTeam(draftState);
  const legalPositions = useMemo(
    () => (currentTeam ? getLegalMockPositionsForTeam(draftState, currentTeam.id) : []),
    [currentTeam, draftState]
  );
  const draftablePlayersForCurrentTeam = useMemo(
    () => (currentTeam ? getDraftablePlayersForTeam(draftBoard, draftState, currentTeam.id) : []),
    [currentTeam, draftBoard, draftState]
  );
  const draftablePlayerIds = useMemo(
    () => new Set(draftablePlayersForCurrentTeam.map((player) => player.id)),
    [draftablePlayersForCurrentTeam]
  );

  const availablePlayers = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return draftablePlayersForCurrentTeam.filter((player) => {
      const matchesPosition = position === "ALL" || player.pos === position;
      const matchesSearch =
        !normalizedSearch ||
        player.name.toLowerCase().includes(normalizedSearch) ||
        player.school.toLowerCase().includes(normalizedSearch);
      return matchesPosition && matchesSearch;
    });
  }, [draftablePlayersForCurrentTeam, position, search]);

  const queuedPlayers = useMemo(() => {
    const byId = new Map(draftBoard.map((player) => [player.id, player]));
    return draftState.queuedPlayerIds
      .map((playerId) => byId.get(playerId))
      .filter((player): player is DraftPlayer => Boolean(player));
  }, [draftBoard, draftState.queuedPlayerIds]);

  const userRoster = useMemo(() => buildMockRoster(draftState), [draftState]);
  const secondsRemaining = getSecondsRemaining(draftState, now);
  const timerDanger = isPickTimerDanger(draftState, secondsRemaining);
  const userOnClock = isUserOnClock(draftState);
  const draftedCount = draftState.picks.length;
  const latestPick = draftState.picks[draftState.picks.length - 1];
  const historyRounds = useMemo(() => groupPicksByRound(draftState.picks), [draftState.picks]);

  const draftOrderPicks = useMemo(
    () =>
      Array.from({ length: MOCK_TOTAL_PICKS }, (_, index) => {
        const overallPick = index + 1;
        const teamId = getTeamIdForPick(overallPick);
        const team = draftState.teams.find((row) => row.id === teamId);
        const pick = draftState.picks.find((row) => row.overallPick === overallPick);
        return {
          overallPick,
          round: getRoundNumber(overallPick),
          roundPick: getRoundPick(overallPick),
          teamId,
          team,
          pick,
        };
      }),
    [draftState.picks, draftState.teams]
  );

  const resetDraft = () => {
    const freshDraft = createSinglePlayerMockDraft();
    setDraftState(freshDraft);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(freshDraft));
    setActiveTab("draft");
    setError(null);
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
              Showing legal players for: {currentTeam?.name ?? "Draft complete"}
            </p>
            <p className="mt-1 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-100/80">
              Legal positions: {legalPositions.length ? legalPositions.join(", ") : "None"}
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
            Unable to load players. Start the backend API and try again.
          </div>
        ) : availablePlayers.length === 0 ? (
          <div className="flex min-h-40 items-center justify-center px-6 text-center text-[10px] font-black uppercase tracking-[0.22em] text-muted-foreground">
            {legalPositions.length === 0
              ? "Roster is full. No legal picks remain."
              : position !== "ALL" &&
                  !legalPositions.includes(position as (typeof legalPositions)[number])
                ? `No ${position} players fit your remaining roster slots.`
                : `No legal players available for your remaining roster slots. Remaining legal positions: ${legalPositions.join(", ")}.`}
          </div>
        ) : (
          availablePlayers.slice(0, 160).map((player) => {
            const positionClass = POSITION_STYLES[player.pos] ?? "border-white/20 bg-white/10 text-foreground";
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

    const projectionStats = projectionStatsForPlayer(selectedPlayer);
    const previousStats = selectedPlayerSeasonStats?.stats ?? null;
    const statRows = statRowsForPosition(selectedPlayer.pos);
    const positionClass = POSITION_STYLES[selectedPlayer.pos] ?? "border-white/20 bg-white/10 text-foreground";
    const visibleRank = selectedPlayer.masterDraftRank ?? selectedPlayer.draftRank;

    return (
      <aside className="fixed bottom-0 right-0 top-0 z-[1300] flex w-full max-w-[420px] flex-col border-l border-cyan-200/15 bg-[#071225]/96 shadow-[-24px_0_80px_rgba(8,145,178,0.22)] backdrop-blur-2xl">
        <div className="border-b border-cyan-100/10 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-200">Scouting Card</p>
              <h2 className="mt-3 truncate text-2xl font-black tracking-tight text-white">{selectedPlayer.name}</h2>
              <p className="mt-1 text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">
                {selectedPlayer.school} • Master Rank #{visibleRank}
              </p>
            </div>
            <button
              type="button"
              aria-label="Close scouting card"
              onClick={() => setSelectedPlayerId(null)}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-muted-foreground transition hover:border-cyan-200/30 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <span className={cn("rounded-full border px-4 py-2 text-xs font-black", positionClass)}>{selectedPlayer.pos}</span>
            <span className="rounded-full border border-cyan-200/15 bg-cyan-300/10 px-4 py-2 text-xs font-black tabular-nums text-cyan-100">
              {selectedPlayer.projectedPoints.toFixed(1)} PROJ
            </span>
            {selectedPlayer.sourceBoardRank ? (
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs font-black tabular-nums text-muted-foreground">
                Source #{selectedPlayer.sourceBoardRank}
              </span>
            ) : null}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <section className="rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">Projected 2026</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {statRows.map((row) => (
                <div key={`projection-${row.label}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">{row.label}</p>
                  <p className="mt-2 text-lg font-black tabular-nums text-white">
                    {formatStat(statValue(projectionStats, row.projectionKeys))}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-4 rounded-3xl border border-cyan-200/12 bg-white/[0.035] p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">2025 Stats</p>
                <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
                  {selectedPlayerSeasonStats?.source ?? "sportsdata"} {selectedPlayerSeasonStats?.cached ? "• cached" : ""}
                </p>
              </div>
              {selectedPlayerSeasonStats?.message ? (
                <span className="rounded-full border border-amber-200/20 bg-amber-300/10 px-3 py-1 text-[9px] font-black uppercase tracking-[0.12em] text-amber-100">
                  Limited
                </span>
              ) : null}
            </div>
            {selectedPlayerSeasonStats?.message ? (
              <p className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs font-bold leading-relaxed text-muted-foreground">
                {selectedPlayerSeasonStats.message}
              </p>
            ) : null}
            <div className="mt-4 grid grid-cols-2 gap-3">
              {statRows.map((row) => (
                <div key={`previous-${row.label}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-[9px] font-black uppercase tracking-[0.18em] text-muted-foreground">{row.label}</p>
                  <p className="mt-2 text-lg font-black tabular-nums text-white">
                    {formatStat(statValue(previousStats, row.previousKeys))}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-4 rounded-3xl border border-cyan-200/12 bg-cyan-400/[0.055] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-200">About the Player</p>
            <p className="mt-3 text-sm font-semibold leading-6 text-slate-200">
              {buildPlayerSummary(selectedPlayer, previousStats)}
            </p>
          </section>
        </div>
      </aside>
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
    const slotByLabel = new Map(userRoster.map((slot) => [slot.label, slot]));
    const starterRows = [
      { label: "Quarterback", accent: "QB", slots: ["QB"] },
      { label: "Running Backs", accent: "RB", slots: ["RB 1", "RB 2"] },
      { label: "Wide Receivers", accent: "WR", slots: ["WR 1", "WR 2"] },
      { label: "Tight End", accent: "TE", slots: ["TE"] },
      { label: "Flex + Kicker", accent: "K", slots: ["FLEX", "K"] },
    ];
    const benchSlots = userRoster.filter((slot) => slot.label.startsWith("BENCH"));

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
            "relative min-h-[82px] overflow-hidden rounded-2xl border px-4 py-3",
            "shadow-[inset_0_1px_0_rgba(255,255,255,0.045)]",
            style.border,
            style.bg,
            style.text
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

    const renderBenchSlotCard = (slot: (typeof userRoster)[number]) => {
      const position = slot.player?.position ?? "EMPTY";
      const style = ROSTER_POSITION_STYLES[position] ?? ROSTER_POSITION_STYLES.EMPTY;
      return (
        <div
          key={slot.label}
          className={cn(
            "grid min-h-[64px] grid-cols-[90px_minmax(0,1fr)_auto] items-center gap-3 rounded-2xl border px-4 py-3",
            "bg-slate-950/35 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
            style.border,
            style.text
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
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Your Roster</p>
            <p className="mt-1 text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
              Starters by position group
            </p>
          </div>
          <p className="text-[9px] font-black uppercase tracking-[0.16em] text-muted-foreground">
            {userRoster.filter((slot) => slot.player).length}/{userRoster.length} filled
          </p>
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
            <div className="text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">{MOCK_TOTAL_PICKS} Picks</p>
              <p className="mt-1 text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">{MOCK_TOTAL_PICKS - draftedCount} Unlocked</p>
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
                  ref={(node) => {
                    if (node) {
                      pickRefs.current.set(slot.overallPick, node);
                    } else {
                      pickRefs.current.delete(slot.overallPick);
                    }
                  }}
                  className={cn(
                    "min-w-[178px] rounded-3xl border p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition",
                    isCurrent
                      ? "border-cyan-200/80 bg-cyan-300/14 shadow-[0_0_52px_rgba(103,232,249,0.36),inset_0_1px_0_rgba(255,255,255,0.07)]"
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

        {draftState.status === "complete" ? (
          <section className="rounded-[2rem] border border-primary/30 bg-primary/10 p-6 text-center">
            <Trophy className="mx-auto mb-3 h-8 w-8 text-primary" />
            <p className="text-xl font-black uppercase tracking-tight text-foreground">Draft Complete</p>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">156 picks completed without real league mutations.</p>
          </section>
        ) : null}

        {activeTab === "draft" ? renderAvailablePlayers() : null}
        {activeTab === "queue" ? renderQueue() : null}
        {activeTab === "roster" ? renderRoster() : null}
        {activeTab === "history" ? renderHistory() : null}
      </div>

      {renderScoutingPanel()}

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
