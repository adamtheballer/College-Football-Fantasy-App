import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, RadioTower } from "lucide-react";

import { DraftRoomBoard } from "@/components/draft/DraftRoomBoard";
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
import type { Player } from "@/types/player";
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
  const [autoPickRetryMessage, setAutoPickRetryMessage] = useState<string | null>(null);
  const previousStatusRef = useRef<string | null>(null);
  const autoPickTimeoutRef = useRef<number | null>(null);
  const timerFallbackTimeoutRef = useRef<number | null>(null);
  const currentAutoPickTurnKeyRef = useRef<string | null>(null);
  const lastBotAutoPickAttemptKeyRef = useRef<string | null>(null);
  const lastTimerFallbackAttemptKeyRef = useRef<string | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);
  const { data: playersPayload } = useMockDraftAvailablePlayers(parsedMockDraftId, { search: debouncedSearch || undefined, limit: 100 });

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
  const showCompletionModal = shouldShowMockCompletionModal(Boolean(room?.is_complete), completionChoiceMade);
  const showOrderReveal = shouldShowSinglePlayerDraftOrderReveal(room, hasContinuedToDraft);

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
          setAutoPickRetryMessage(null);
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
          setAutoPickRetryMessage("Auto-pick failed. Retrying...");
          if (import.meta.env.DEV) {
            console.error("[SingleMockDraft] auto-pick failed", err);
          }
          timerFallbackTimeoutRef.current = window.setTimeout(() => {
            if (currentAutoPickTurnKeyRef.current === turnKey) {
              void autoPickMutation
                .mutateAsync({ force: true, expectedOverallPick: room.current_overall_pick })
                .then((payload) => {
                  setAutoPickRetryMessage(null);
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
                  if (import.meta.env.DEV) {
                    console.error("[SingleMockDraft] auto-pick retry failed", retryErr);
                  }
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
      .mutateAsync({ force: true, expectedOverallPick: room.current_overall_pick })
      .then((payload) => {
        setAutoPickRetryMessage(null);
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
        setAutoPickRetryMessage("Auto-pick failed. Retrying...");
        if (import.meta.env.DEV) {
          console.error("[SingleMockDraft] auto-pick failed", err);
        }
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
    previousStatusRef.current = null;
    await resetMutation.mutateAsync();
    setHasContinuedToDraft(false);
  };

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
        onSelectPlayer={(player) => setSelectedPlayer(player.sourcePlayer ?? null)}
        draftPending={pickMutation.isPending}
        autoPickPending={autoPickMutation.isPending}
        error={autoPickRetryMessage ?? (pickMutation.error instanceof Error ? pickMutation.error.message : autoPickMutation.error instanceof Error ? autoPickMutation.error.message : resetMutation.error instanceof Error ? resetMutation.error.message : null)}
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
