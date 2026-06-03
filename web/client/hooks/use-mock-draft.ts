import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost, getStoredAccessToken } from "@/lib/api";
import type { DraftEventEnvelope } from "@/types/draft";
import type { MockDraftPreview, MockDraftQueue, MockDraftRoom, MockDraftRoomSnapshot, MockDraftSession } from "@/types/mock-draft";

export function useMockDraftLobby(mockDraftId?: number, enabled = true) {
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "lobby"],
    enabled: enabled && typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    staleTime: 1_000,
    refetchOnWindowFocus: true,
    refetchInterval: 3_000,
    queryFn: () => apiGet<MockDraftSession>(`/mock-drafts/${mockDraftId}/lobby`),
  });
}

export function useMockDraftRoom(mockDraftId?: number, enabled = true) {
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "room"],
    enabled: enabled && typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    staleTime: 1_000,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const room = query.state.data as MockDraftRoom | undefined;
      if (!room) return 3_000;
      if (room.status === "countdown" || room.status === "live") return 1_000;
      if (room.status === "paused") return 5_000;
      return 10_000;
    },
    queryFn: () => apiGet<MockDraftRoom>(`/mock-drafts/${mockDraftId}/room`),
  });
}

export function useMockDraftRealtime(mockDraftId?: number, enabled = true) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!enabled || typeof mockDraftId !== "number" || Number.isNaN(mockDraftId)) return;
    const token = getStoredAccessToken();
    if (!token) return;
    const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const wsUrl = new URL(`/mock-drafts/${mockDraftId}/ws`, apiBase);
    wsUrl.protocol = wsUrl.protocol === "https:" ? "wss:" : "ws:";
    wsUrl.searchParams.set("token", token);
    let isActive = true;
    let latestSeq = 0;
    let pingInterval: number | null = null;
    let reconnectTimeout: number | null = null;
    let reconnectAttempt = 0;
    let socket: WebSocket | null = null;
    let reconnectScheduled = false;

    const clearTimers = () => {
      if (pingInterval !== null) {
        window.clearInterval(pingInterval);
        pingInterval = null;
      }
      if (reconnectTimeout !== null) {
        window.clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
    };

    const fetchSnapshot = async (sinceSeq = 0) => {
      try {
        const snapshot = await apiGet<MockDraftRoomSnapshot>(`/mock-drafts/${mockDraftId}/snapshot`, { since_seq: sinceSeq, limit: 250 });
        if (!isActive) return;
        queryClient.setQueryData(["mock-draft", mockDraftId, "room"], snapshot.draft_room);
        latestSeq = Math.max(latestSeq, snapshot.latest_seq || 0);
      } catch {
        // noop
      }
    };

    const scheduleReconnect = () => {
      if (!isActive || reconnectScheduled) return;
      reconnectScheduled = true;
      clearTimers();
      reconnectAttempt += 1;
      const delayMs = Math.min(30_000, Math.max(1_000, 1_000 * 2 ** (reconnectAttempt - 1)));
      reconnectTimeout = window.setTimeout(() => {
        if (!isActive) return;
        reconnectScheduled = false;
        connectSocket();
      }, delayMs);
    };

    const handleEvent = (message: Partial<DraftEventEnvelope> & { payload?: { draft_room?: MockDraftRoom } }) => {
      const eventName = String(message.event || "").toLowerCase();
      const eventType = String(message.event_type || "").toLowerCase();
      const seq = typeof message.seq === "number" ? message.seq : null;
      if (seq !== null) {
        if (seq <= latestSeq) return;
        if (latestSeq > 0 && seq > latestSeq + 1) {
          void fetchSnapshot(latestSeq);
        }
        latestSeq = seq;
      }
      if ((eventType === "draft.room.snapshot" || eventName === "draft_room_ready") && message.payload?.draft_room) {
        queryClient.setQueryData(["mock-draft", mockDraftId, "room"], message.payload.draft_room);
        return;
      }
      if (eventType.startsWith("draft.") || eventName.startsWith("draft_")) {
        queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "room"] });
        queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "lobby"] });
        queryClient.invalidateQueries({ queryKey: ["players"] });
      }
    };

    const connectSocket = () => {
      reconnectScheduled = false;
      clearTimers();
      socket = new WebSocket(wsUrl.toString());
      socket.onopen = () => {
        reconnectAttempt = 0;
        pingInterval = window.setInterval(() => {
          if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 20_000);
        void fetchSnapshot(latestSeq);
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as Partial<DraftEventEnvelope> & { payload?: { draft_room?: MockDraftRoom } };
          handleEvent(message);
        } catch {
          // noop
        }
      };
      socket.onerror = () => scheduleReconnect();
      socket.onclose = () => scheduleReconnect();
    };

    void fetchSnapshot(0);
    connectSocket();

    return () => {
      isActive = false;
      clearTimers();
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close();
      }
    };
  }, [enabled, mockDraftId, queryClient]);
}

export function useCreateMockDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { manager_count: 4 | 6 | 8 | 10 | 12; pick_timer_seconds: number; name: string; mode: "public_multiplayer" | "single_player" }) =>
      apiPost<MockDraftSession>("/mock-drafts", payload),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", payload.id, "lobby"], payload);
    },
  });
}

export function usePreviewMockDraft() {
  return useMutation({
    mutationFn: (inviteCode: string) => apiPost<MockDraftPreview>("/mock-drafts/join-by-code", { invite_code: inviteCode }),
  });
}

export function useJoinMockDraftByCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteCode: string) => apiPost<MockDraftSession>("/mock-drafts/join-with-code", { invite_code: inviteCode }),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", payload.id, "lobby"], payload);
    },
  });
}

export function useMockDraftLobbyJoin(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<MockDraftSession>(`/mock-drafts/${mockDraftId}/lobby/join`, {}),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "lobby"], payload);
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "room"] });
    },
  });
}

export function useMockDraftLobbyReady(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ready: boolean) => apiPost<MockDraftSession>(`/mock-drafts/${mockDraftId}/lobby/ready`, { ready }),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "lobby"], payload);
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "room"] });
    },
  });
}

export function useMockDraftLobbyHeartbeat(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<MockDraftSession>(`/mock-drafts/${mockDraftId}/lobby/heartbeat`, {}),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "lobby"], payload);
    },
  });
}

export function useMockDraftStatus(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { status: "lobby_open" | "countdown" | "active" | "paused" | "abandoned" }) =>
      apiPost<MockDraftRoom>(`/mock-drafts/${mockDraftId}/status`, payload),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "room"], payload);
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "lobby"] });
    },
  });
}

export function useMockDraftPick(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (playerId: number) => {
      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `mock-pick-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
      return apiPost<MockDraftRoom>(
        `/mock-drafts/${mockDraftId}/pick`,
        { player_id: playerId },
        undefined,
        { "Idempotency-Key": idempotencyKey }
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "room"], payload);
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "lobby"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });
}

export function useMockDraftQueue(mockDraftId?: number, seatId?: number | null, enabled = true) {
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "queue", seatId ?? "self"],
    enabled: enabled && typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    staleTime: 5_000,
    queryFn: () =>
      apiGet<MockDraftQueue>(`/mock-drafts/${mockDraftId}/queue`, seatId ? { seat_id: seatId } : undefined),
  });
}

export function useMockDraftQueueAdd(mockDraftId?: number, seatId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (playerId: number) =>
      apiPost<MockDraftQueue>(
        `/mock-drafts/${mockDraftId}/queue`,
        { player_id: playerId },
        seatId ? { seat_id: seatId } : undefined
      ),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "queue", seatId ?? "self"], payload);
    },
  });
}

export function useMockDraftQueueRemove(mockDraftId?: number, seatId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (playerId: number) =>
      apiDelete<MockDraftQueue>(`/mock-drafts/${mockDraftId}/queue/${playerId}`, seatId ? { seat_id: seatId } : undefined),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "queue", seatId ?? "self"], payload);
    },
  });
}

export function useMockDraftQueueClear(mockDraftId?: number, seatId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<MockDraftQueue>(`/mock-drafts/${mockDraftId}/queue/clear`, {}, seatId ? { seat_id: seatId } : undefined),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "queue", seatId ?? "self"], payload);
    },
  });
}

export function useMockDraftQueueReorder(mockDraftId?: number, seatId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (playerIds: number[]) =>
      apiPost<MockDraftQueue>(
        `/mock-drafts/${mockDraftId}/queue/reorder`,
        { player_ids: playerIds },
        seatId ? { seat_id: seatId } : undefined
      ),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "queue", seatId ?? "self"], payload);
    },
  });
}

export function useDeleteMockDraft(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiDelete<void>(`/mock-drafts/${mockDraftId}`),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["mock-draft", mockDraftId] });
    },
  });
}
