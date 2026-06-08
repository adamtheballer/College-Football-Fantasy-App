import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, RadioTower } from "lucide-react";

import { DraftRoomBoard, getDraftablePositionsForRosterPicks } from "@/components/draft/DraftRoomBoard";
import { SinglePlayerDraftOrderReveal } from "@/components/draft/SinglePlayerDraftOrderReveal";
import { PlayerDetailModal } from "@/components/PlayerDetailModal";
import { useDraftTimer } from "@/hooks/use-draft-timer";
import {
  useEmailMockDraftHistory,
  useExitMockDraft,
  useMockDraftAvailablePlayers,
  useMockDraftAutoPick,
  useMockDraftHistory,
  useMockDraftPick,
  useMockDraftRoom,
  useResetSinglePlayerMockDraft,
} from "@/hooks/use-mock-drafts";
import { ApiError } from "@/lib/api";
import { adaptMockToDraftBoardState, mapPlayersToDraftBoardPlayers } from "@/lib/draft-board-adapters";
import type { DraftBoardPick } from "@/types/draft-board";
import type { Player } from "@/types/player";
import type { StandaloneMockDraftPick } from "@/types/mock-draft";
import {
  MOCK_DRAFT_EXIT_PATH,
  getMockTurnKey,
  getMockAutoPickDelayMs,
  shouldShowMockCompletionModal,
  shouldShowSinglePlayerDraftOrderReveal,
  shouldScheduleBotAutoPick,
  shouldTriggerTimerExpiredAutoPick,
} from "./mock-draft-flow";

const singlePlayerContinueStorageKey = (mockDraftId: number) => `single-player-mock-draft-continued:${mockDraftId}`;
const MOCK_AUTO_PICK_RETRY_MS = 1_000;
const SEARCH_DEBOUNCE_MS = 180;
const MOCK_DRAFT_BOARD_LIMIT = 500;

const mapMockPickToDraftBoardPick = (pick: StandaloneMockDraftPick): DraftBoardPick => ({
  id: pick.id,
  overallPick: pick.overall_pick,
  roundNumber: pick.round_number,
  roundPick: pick.round_pick,
  participantId: pick.participant_id,
  participantName: pick.participant_name,
  teamName: pick.team_name,
  playerId: pick.player_id,
  playerName: pick.player_name,
  playerPosition: pick.player_position,
  playerSchool: pick.player_school,
  pickSource: pick.pick_source,
  createdAt: pick.created_at,
});

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebouncedValue(value), delayMs);
    return () => window.clearTimeout(timeoutId);
  }, [delayMs, value]);

  return debouncedValue;
}

export default function MockDraftRoom() {
  const { mockDraftId } = useParams();
  const navigate = useNavigate();
  const parsedMockDraftId = mockDraftId && !Number.isNaN(Number(mockDraftId)) ? Number(mockDraftId) : undefined;
  const { data: room, isLoading, error } = useMockDraftRoom(parsedMockDraftId, Boolean(parsedMockDraftId));
  const pickMutation = useMockDraftPick(parsedMockDraftId);
  const autoPickMutation = useMockDraftAutoPick(parsedMockDraftId);
  const emailMutation = useEmailMockDraftHistory(parsedMockDraftId);
  const exitMutation = useExitMockDraft(parsedMockDraftId);
  const resetMutation = useResetSinglePlayerMockDraft(parsedMockDraftId);
  const { data: history } = useMockDraftHistory(parsedMockDraftId, Boolean(room?.is_complete));
  const [search, setSearch] = useState("");
  const [completionChoiceMade, setCompletionChoiceMade] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [hasContinuedToDraft, setHasContinuedToDraft] = useState(false);
  const [showDraftUnderway, setShowDraftUnderway] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [queuedPlayerIds, setQueuedPlayerIds] = useState<number[]>([]);
  const previousStatusRef = useRef<string | null>(null);
  const autoPickTimeoutRef = useRef<number | null>(null);
  const timerFallbackTimeoutRef = useRef<number | null>(null);
  const currentAutoPickTurnKeyRef = useRef<string | null>(null);
  const lastBotAutoPickAttemptKeyRef = useRef<string | null>(null);
  const lastTimerFallbackAttemptKeyRef = useRef<string | null>(null);
  const autoPickRetryCountByTurnKeyRef = useRef<Map<string, number>>(new Map());
  const latestAutoPickContextRef = useRef<{
    room: typeof room;
    availablePlayers: typeof availablePlayers;
    draftedPlayerIds: Set<number>;
    autoPickPending: boolean;
  }>({ room: null, availablePlayers: [], draftedPlayerIds: new Set(), autoPickPending: false });
  const debouncedSearch = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);
  const userDraftablePositions = useMemo(() => {
    if (!room?.user_team_id) return undefined;
    const userRoster = room.rosters.find((roster) => roster.participant_id === room.user_team_id);
    if (!userRoster) return undefined;
    const positions = [...getDraftablePositionsForRosterPicks(userRoster.picks.map(mapMockPickToDraftBoardPick))].sort();
    return positions.length ? positions : undefined;
  }, [room?.rosters, room?.user_team_id]);
  const { data: playersPayload } = useMockDraftAvailablePlayers(parsedMockDraftId, {
    search: debouncedSearch || undefined,
    positions: userDraftablePositions,
    limit: MOCK_DRAFT_BOARD_LIMIT,
  });

  useEffect(() => {
    if (!parsedMockDraftId) return;
    setHasContinuedToDraft(window.sessionStorage.getItem(singlePlayerContinueStorageKey(parsedMockDraftId)) === "1");
  }, [parsedMockDraftId]);

  const timerTargetExpiresAt = room?.current_pick_expires_at ?? (room?.status === "intermission" ? room.session.intermission_ends_at : null);
  const timer = useDraftTimer({
    serverTime: room?.server_time,
    currentPickExpiresAt: timerTargetExpiresAt,
    currentPick: room?.current_overall_pick,
  });

  const draftedPlayerIds = useMemo(() => new Set((room?.picks ?? []).map((pick) => pick.player_id)), [room?.picks]);
  const availablePlayers = useMemo(
    () => mapPlayersToDraftBoardPlayers(playersPayload?.data ?? [], draftedPlayerIds),
    [draftedPlayerIds, playersPayload?.data]
  );
  const boardState = useMemo(
    () => (room ? adaptMockToDraftBoardState(room, availablePlayers, timer.formattedTime, timer.secondsRemaining) : null),
    [availablePlayers, room, timer.formattedTime, timer.secondsRemaining]
  );
  const queuedAutoPickPlayerIds = useMemo(
    () => (room?.current_participant_type === "human" ? queuedPlayerIds : []),
    [queuedPlayerIds, room?.current_participant_type]
  );
  const showCompletionModal = shouldShowMockCompletionModal(Boolean(room?.is_complete), completionChoiceMade);
  const showOrderReveal = shouldShowSinglePlayerDraftOrderReveal(room, hasContinuedToDraft);

  useEffect(() => {
    latestAutoPickContextRef.current = {
      room,
      availablePlayers,
      draftedPlayerIds,
      autoPickPending: autoPickMutation.isPending,
    };
  }, [autoPickMutation.isPending, availablePlayers, draftedPlayerIds, room]);

  const logAutoPickFailure = (err: unknown, context: { reason: string; turnKey: string; retryCount: number }) => {
    if (!import.meta.env.DEV) return;
    const latest = latestAutoPickContextRef.current;
    const latestRoom = latest.room;
    const currentParticipant = latestRoom?.participants.find((participant) => participant.id === latestRoom.current_participant_id);
    console.error("[SingleMockDraft] auto-pick failed", {
      error: err,
      errorName: err instanceof Error ? err.name : undefined,
      errorMessage: err instanceof Error ? err.message : String(err),
      errorStack: err instanceof Error ? err.stack : undefined,
      apiStatus: err instanceof ApiError ? err.status : undefined,
      apiMessage: err instanceof ApiError ? err.message : undefined,
      apiDetail: err instanceof ApiError ? err.detail : undefined,
      reason: context.reason,
      turnKey: context.turnKey,
      retryCount: context.retryCount,
      mockDraftId: latestRoom?.mock_draft_id,
      currentOverallPick: latestRoom?.current_overall_pick,
      currentRound: latestRoom?.current_round,
      currentRoundPick: latestRoom?.current_round_pick,
      currentParticipant,
      currentParticipantType: latestRoom?.current_participant_type,
      status: latestRoom?.status,
      picksCount: latestRoom?.picks.length ?? 0,
      availablePlayersCount: latest.availablePlayers.length,
      firstAvailablePlayer: latest.availablePlayers[0],
      draftedPlayerIds: Array.from(latest.draftedPlayerIds),
      autoPickPending: latest.autoPickPending,
    });
  };

  useEffect(() => {
    currentAutoPickTurnKeyRef.current = getMockTurnKey(room);
  }, [room?.mock_draft_id, room?.current_overall_pick, room?.current_participant_id, room?.current_participant_type, room?.status]);

  useEffect(() => {
    if (!room) return;
    const turnKey = getMockTurnKey(room);
    if (!turnKey) return;
    if (!shouldScheduleBotAutoPick(room, { autoPickPending: autoPickMutation.isPending })) return;
    if (lastBotAutoPickAttemptKeyRef.current === turnKey) return;

    lastBotAutoPickAttemptKeyRef.current = turnKey;
    const delayMs = getMockAutoPickDelayMs(room);
    if (import.meta.env.DEV) {
      console.debug("[SingleMockDraft] bot auto-pick scheduled", {
        mockDraftId: room.mock_draft_id,
        overallPick: room.current_overall_pick,
        participantId: room.current_participant_id,
        participantType: room.current_participant_type,
        delayMs,
      });
    }
    autoPickTimeoutRef.current = window.setTimeout(() => {
      autoPickTimeoutRef.current = null;
      if (currentAutoPickTurnKeyRef.current !== turnKey) return;
      if (import.meta.env.DEV) {
        console.debug("[SingleMockDraft] bot auto-pick firing", {
          mockDraftId: room.mock_draft_id,
          overallPick: room.current_overall_pick,
          participantType: room.current_participant_type,
        });
      }
      void autoPickMutation
        .mutateAsync({ force: true, expectedOverallPick: room.current_overall_pick })
        .then((payload) => {
          autoPickRetryCountByTurnKeyRef.current.delete(turnKey);
          lastTimerFallbackAttemptKeyRef.current = null;
          if (import.meta.env.DEV) {
            console.debug("[SingleMockDraft] auto-pick success", {
              mockDraftId: payload.mock_draft_id,
              status: payload.status,
              currentOverallPick: payload.current_overall_pick,
              picks: payload.picks.length,
            });
          }
        })
        .catch((err) => {
          lastBotAutoPickAttemptKeyRef.current = null;
          const retryCount = (autoPickRetryCountByTurnKeyRef.current.get(turnKey) ?? 0) + 1;
          autoPickRetryCountByTurnKeyRef.current.set(turnKey, retryCount);
          logAutoPickFailure(err, { reason: "bot_turn", turnKey, retryCount });
          if (retryCount > 2) {
            return;
          }
          timerFallbackTimeoutRef.current = window.setTimeout(() => {
            if (currentAutoPickTurnKeyRef.current === turnKey) {
              void autoPickMutation
                .mutateAsync({ force: true, expectedOverallPick: room.current_overall_pick })
                .then((payload) => {
                  autoPickRetryCountByTurnKeyRef.current.delete(turnKey);
                  lastTimerFallbackAttemptKeyRef.current = null;
                  if (import.meta.env.DEV) {
                    console.debug("[SingleMockDraft] auto-pick retry success", {
                      mockDraftId: payload.mock_draft_id,
                      status: payload.status,
                      currentOverallPick: payload.current_overall_pick,
                      picks: payload.picks.length,
                    });
                  }
                })
                .catch((retryErr) => {
                  lastTimerFallbackAttemptKeyRef.current = null;
                  const nextRetryCount = (autoPickRetryCountByTurnKeyRef.current.get(turnKey) ?? retryCount) + 1;
                  autoPickRetryCountByTurnKeyRef.current.set(turnKey, nextRetryCount);
                  logAutoPickFailure(retryErr, { reason: "bot_turn_retry", turnKey, retryCount: nextRetryCount });
                });
            }
          }, MOCK_AUTO_PICK_RETRY_MS);
        });
    }, delayMs);
    return () => {
      if (autoPickTimeoutRef.current !== null) {
        window.clearTimeout(autoPickTimeoutRef.current);
        autoPickTimeoutRef.current = null;
        if (currentAutoPickTurnKeyRef.current === turnKey) {
          lastBotAutoPickAttemptKeyRef.current = null;
        }
      }
    };
  }, [
    autoPickMutation.isPending,
    autoPickMutation.mutateAsync,
    room?.mock_draft_id,
    room?.current_overall_pick,
    room?.current_participant_id,
    room?.current_participant_type,
    room?.is_complete,
    room?.status,
  ]);

  useEffect(() => {
    if (!room) return;
    const turnKey = getMockTurnKey(room);
    if (!turnKey) return;
    if (!shouldTriggerTimerExpiredAutoPick(room, { isExpired: timer.isExpired, autoPickPending: autoPickMutation.isPending })) return;
    if (lastTimerFallbackAttemptKeyRef.current === turnKey) return;

    lastTimerFallbackAttemptKeyRef.current = turnKey;
    if (import.meta.env.DEV) {
      console.debug("[SingleMockDraft] timer expired fallback", {
        mockDraftId: room.mock_draft_id,
        overallPick: room.current_overall_pick,
        participantId: room.current_participant_id,
        participantType: room.current_participant_type,
      });
    }
    void autoPickMutation
      .mutateAsync({
        force: true,
        expectedOverallPick: room.current_overall_pick,
        preferredPlayerIds: queuedAutoPickPlayerIds,
      })
      .then((payload) => {
        autoPickRetryCountByTurnKeyRef.current.delete(turnKey);
        lastBotAutoPickAttemptKeyRef.current = null;
        if (import.meta.env.DEV) {
          console.debug("[SingleMockDraft] auto-pick success", {
            mockDraftId: payload.mock_draft_id,
            status: payload.status,
            currentOverallPick: payload.current_overall_pick,
            picks: payload.picks.length,
          });
        }
      })
      .catch((err) => {
        lastTimerFallbackAttemptKeyRef.current = null;
        const retryCount = (autoPickRetryCountByTurnKeyRef.current.get(turnKey) ?? 0) + 1;
        autoPickRetryCountByTurnKeyRef.current.set(turnKey, retryCount);
        logAutoPickFailure(err, {
          reason: room.current_participant_type === "bot" ? "bot_timer_fallback" : "timer_expired",
          turnKey,
          retryCount,
        });
      });
  }, [
    autoPickMutation.isPending,
    autoPickMutation.mutateAsync,
    room?.mock_draft_id,
    room?.current_overall_pick,
    room?.current_participant_id,
    room?.current_participant_type,
    room?.is_complete,
    room?.status,
    queuedAutoPickPlayerIds,
    timer.isExpired,
  ]);

  useEffect(() => {
    return () => {
      if (autoPickTimeoutRef.current !== null) {
        window.clearTimeout(autoPickTimeoutRef.current);
      }
      if (timerFallbackTimeoutRef.current !== null) {
        window.clearTimeout(timerFallbackTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!room) return;
    const previousStatus = previousStatusRef.current;
    if (room.session.mode === "single_player" && previousStatus === "intermission" && room.status === "live") {
      setShowDraftUnderway(true);
      if (import.meta.env.DEV) {
        console.debug("[SingleMockDraft] intermission ended -> live", {
          mockDraftId: room.mock_draft_id,
          currentOverallPick: room.current_overall_pick,
          currentParticipantId: room.current_participant_id,
          currentParticipantType: room.current_participant_type,
        });
      }
    }
    if (previousStatus !== room.status && import.meta.env.DEV) {
      console.debug("[SingleMockDraft] status changed", {
        mockDraftId: room.mock_draft_id,
        from: previousStatus,
        to: room.status,
      });
    }
    previousStatusRef.current = room.status;
  }, [room, room?.status, room?.session.mode]);

  useEffect(() => {
    if (!showDraftUnderway) return;
    const timeout = window.setTimeout(() => setShowDraftUnderway(false), 1_500);
    return () => window.clearTimeout(timeout);
  }, [showDraftUnderway]);

  if (!parsedMockDraftId) return <div className="py-16 text-center text-red-300">Invalid mock draft id.</div>;
  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading mock draft board...
      </div>
    );
  }
  if (!room || !boardState) {
    return <div className="py-16 text-center text-red-300">{error instanceof Error ? error.message : "Mock room unavailable."}</div>;
  }

  const sendEmail = async () => {
    setEmailError(null);
    try {
      await emailMutation.mutateAsync();
      setCompletionChoiceMade(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setEmailError("Email is not configured. Copy the history and exit when ready.");
        setCompletionChoiceMade(true);
        return;
      }
      setEmailError(err instanceof Error ? err.message : "Unable to send history email.");
    }
  };

  const exitDraft = async () => {
    const response = await exitMutation.mutateAsync();
    navigate(response.navigate_to || MOCK_DRAFT_EXIT_PATH);
  };

  const continueToDraft = () => {
    if (parsedMockDraftId) {
      window.sessionStorage.setItem(singlePlayerContinueStorageKey(parsedMockDraftId), "1");
    }
    setHasContinuedToDraft(true);
  };

  const resetDraft = async () => {
    if (!parsedMockDraftId) return;
    window.sessionStorage.removeItem(singlePlayerContinueStorageKey(parsedMockDraftId));
    setCompletionChoiceMade(false);
    setEmailError(null);
    setShowDraftUnderway(false);
    setQueuedPlayerIds([]);
    previousStatusRef.current = null;
    await resetMutation.mutateAsync();
    setHasContinuedToDraft(false);
  };

  const visibleDraftError =
    room.is_complete || room.status === "completed"
      ? null
      : pickMutation.error instanceof Error
        ? pickMutation.error.message
        : resetMutation.error instanceof Error
          ? resetMutation.error.message
          : null;

  if (showOrderReveal) {
    return (
      <SinglePlayerDraftOrderReveal
        participants={boardState.participants}
        formattedTime={timer.formattedTime}
        onContinue={continueToDraft}
        onExit={() => void exitDraft()}
      />
    );
  }

  return (
    <>
      {showDraftUnderway ? (
        <div className="pointer-events-none fixed inset-0 z-[1300] flex items-center justify-center bg-slate-950/30 backdrop-blur-sm">
          <div className="rounded-[2rem] border border-cyan-300/25 bg-slate-950/90 px-10 py-8 text-center shadow-[0_0_80px_rgba(34,211,238,0.18)]">
            <RadioTower className="mx-auto h-8 w-8 text-cyan-200" />
            <p className="mt-4 text-3xl font-black italic uppercase tracking-tight text-white">Draft Is Underway</p>
            <p className="mt-2 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-100/80">The pick clock is live</p>
          </div>
        </div>
      ) : null}
      <DraftRoomBoard
        state={boardState}
        searchQuery={search}
        onSearchChange={setSearch}
        onDraftPlayer={(playerId) => pickMutation.mutate(playerId)}
        queuedPlayerIds={queuedPlayerIds}
        onQueuedPlayerIdsChange={setQueuedPlayerIds}
        onSelectPlayer={(player) => setSelectedPlayer(player.sourcePlayer ?? null)}
        draftPending={pickMutation.isPending}
        autoPickPending={autoPickMutation.isPending}
        error={visibleDraftError}
        onExit={() => void exitDraft()}
        onEmailHistory={() => void sendEmail()}
        onSkipEmail={() => setCompletionChoiceMade(true)}
        onCopyHistory={() => history?.plain_text && navigator.clipboard?.writeText(history.plain_text)}
        onReset={room.session.mode === "single_player" ? () => void resetDraft() : undefined}
        showCompletionModal={showCompletionModal}
        completionChoiceMade={Boolean(room.is_complete && completionChoiceMade)}
        emailPending={emailMutation.isPending}
        exitPending={exitMutation.isPending}
        emailError={emailError}
        historyTextAvailable={Boolean(history?.plain_text)}
      />
      <PlayerDetailModal
        player={selectedPlayer}
        isOpen={Boolean(selectedPlayer)}
        onClose={() => setSelectedPlayer(null)}
      />
    </>
  );
}
