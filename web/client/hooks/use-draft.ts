import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost, getStoredAccessToken } from "@/lib/api";
import type {
  DraftEventEnvelope,
  DraftHistory,
  DraftHistoryEmailResponse,
  DraftQueue,
  DraftRoom,
  DraftRoomSnapshot,
} from "@/types/draft";

type DraftPracticeSetupRequest = {
  team_count?: number;
  reset_existing?: boolean;
  start_now?: boolean;
  mock_team_prefix?: string;
};

type DraftRoomStatusUpdateRequest = {
  status: "active" | "paused" | "filling" | "lobby_open" | "countdown" | "abandoned";
};

type DraftPlayerImportRow = {
  external_id?: string | null;
  name: string;
  position: string;
  school: string;
  image_url?: string | null;
  player_class?: string | null;
  adp?: number | null;
  projected_fantasy_points?: number | null;
};

type DraftPlayerImportResponse = {
  received: number;
  created: number;
  updated: number;
  removed: number;
};

type DraftSheetSyncResponse = {
  received: number;
  valid_rows: number;
  imported: DraftPlayerImportResponse;
  watchlist_id: number;
  watchlist_name: string;
  watchlist_player_count: number;
  matched_players: number;
  unmatched_players: number;
  unmatched_player_names: string[];
  sample_imported_rows: Array<{
    player: string;
    fantasy_proj: number;
  }>;
  invalid_rows: Array<{
    row_number: number;
    reason: string;
    raw?: Record<string, string> | null;
  }>;
  sheet_id: string;
};

const LIVE_DRAFT_REFETCH_MS = 3_000;
const IDLE_DRAFT_REFETCH_MS = 15_000;

const invalidateDraftPickDependencies = (
  queryClient: ReturnType<typeof useQueryClient>,
  leagueId?: number,
  teamId?: number | null
) => {
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
  queryClient.invalidateQueries({ queryKey: ["players"] });
  if (teamId) {
    queryClient.invalidateQueries({ queryKey: ["team", teamId, "roster"] });
  }
};

export function useDraftRoom(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "draft-room"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 500,
    refetchOnWindowFocus: true,
    refetchIntervalInBackground: true,
    refetchInterval: (query) => {
      const room = query.state.data as DraftRoom | undefined;
      if (!room) return LIVE_DRAFT_REFETCH_MS;
      const active = room.status === "live" || room.status === "countdown" || Boolean(room.current_team_id);
      return active ? LIVE_DRAFT_REFETCH_MS : IDLE_DRAFT_REFETCH_MS;
    },
    queryFn: () => apiGet<DraftRoom>(`/leagues/${leagueId}/draft-room`),
  });
}

export function useDraftRoomRealtime(leagueId?: number, enabled = true) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || typeof leagueId !== "number" || Number.isNaN(leagueId)) return;
    const token = getStoredAccessToken();
    if (!token) return;

    const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const wsUrl = new URL(`/leagues/${leagueId}/draft-room/ws`, apiBase);
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

    const applySnapshot = (snapshot: DraftRoomSnapshot) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], snapshot.draft_room);
      latestSeq = Math.max(latestSeq, snapshot.latest_seq || 0);
    };

    const fetchSnapshot = async (sinceSeq = 0) => {
      try {
        const snapshot = await apiGet<DraftRoomSnapshot>(`/leagues/${leagueId}/draft-room/snapshot`, {
          since_seq: sinceSeq,
          limit: 250,
        });
        if (!isActive) return;
        applySnapshot(snapshot);
      } catch {
        // Fallback to normal query polling when snapshot fetch fails.
      }
    };

    const scheduleReconnect = () => {
      if (!isActive) return;
      if (reconnectScheduled) return;
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

    const handleDraftEvent = (message: Partial<DraftEventEnvelope> & { payload?: { draft_room?: DraftRoom } }) => {
      const eventName = String(message.event || "").toLowerCase();
      const eventType = String(message.event_type || "").toLowerCase();
      const seq = typeof message.seq === "number" ? message.seq : null;

      if (seq !== null) {
        if (seq <= latestSeq) return;
        if (latestSeq > 0 && seq > latestSeq + 1) {
          // Missed one or more events; recover with delta snapshot replay.
          void fetchSnapshot(latestSeq);
        }
        latestSeq = seq;
      }

      if ((eventType === "draft.room.snapshot" || eventName === "draft_room_ready") && message.payload?.draft_room) {
        queryClient.setQueryData(["league", leagueId, "draft-room"], message.payload.draft_room);
        return;
      }
      if (eventType.startsWith("draft.") || eventName.startsWith("draft_")) {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
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
          const message = JSON.parse(event.data) as Partial<DraftEventEnvelope> & {
            payload?: { draft_room?: DraftRoom };
          };
          handleDraftEvent(message);
        } catch {
          // Ignore malformed events.
        }
      };

      socket.onerror = () => {
        scheduleReconnect();
      };

      socket.onclose = () => {
        scheduleReconnect();
      };
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
  }, [enabled, leagueId, queryClient]);
}

export function useDraftPick(leagueId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (playerId: number) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft room is missing a valid league id.");
      }
      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `pick-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
      return apiPost<DraftRoom>(
        `/leagues/${leagueId}/draft-picks`,
        { player_id: playerId },
        undefined,
        { "Idempotency-Key": idempotencyKey }
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
      invalidateDraftPickDependencies(queryClient, leagueId, payload.user_team_id);
    },
    onError: () => {
      const cachedRoom = queryClient.getQueryData<DraftRoom>(["league", leagueId, "draft-room"]);
      invalidateDraftPickDependencies(queryClient, leagueId, cachedRoom?.user_team_id);
    },
  });
}

export function useDraftAutoPick(leagueId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { force?: boolean } = {}) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft room is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-picks/auto`, { force: Boolean(payload.force) });
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
      invalidateDraftPickDependencies(queryClient, leagueId, payload.user_team_id);
    },
    onError: () => {
      const cachedRoom = queryClient.getQueryData<DraftRoom>(["league", leagueId, "draft-room"]);
      invalidateDraftPickDependencies(queryClient, leagueId, cachedRoom?.user_team_id);
    },
  });
}

export function useDraftHistory(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "draft-history"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    queryFn: () => apiGet<DraftHistory>(`/leagues/${leagueId}/draft-history`),
  });
}

export function useDraftHistoryEmail(leagueId?: number) {
  return useMutation({
    mutationFn: async (payload: { send_to_account_email: boolean; additional_email?: string | null }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft history email is missing a valid league id.");
      }
      return apiPost<DraftHistoryEmailResponse>(`/leagues/${leagueId}/draft-history/email`, payload);
    },
  });
}

export function useDraftPracticeSetup(leagueId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: DraftPracticeSetupRequest) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft setup is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-room/practice-setup`, payload);
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
    },
  });
}

export function useDraftRoomStatus(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DraftRoomStatusUpdateRequest) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft room status update is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-room/status`, payload);
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
    },
  });
}

export function useDraftSlotMove(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { from_slot: number; to_slot: number }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft slot move is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-room/slots/move`, payload);
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
    },
  });
}

export function useDraftLobbyJoin(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft lobby join is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-room/lobby/join`, {});
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
    },
  });
}

export function useDraftLobbyReady(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ready: boolean) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft lobby ready is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-room/lobby/ready`, { ready });
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
    },
  });
}

export function useDraftLobbyHeartbeat(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft lobby heartbeat is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-room/lobby/heartbeat`, {});
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
    },
  });
}

export function useDraftPlayerPoolImport(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      replace_mode: "upsert" | "replace_offense_pool";
      rows: DraftPlayerImportRow[];
    }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Player pool import is missing a valid league id.");
      }
      return apiPost<DraftPlayerImportResponse>(
        `/leagues/${leagueId}/draft-room/player-pool/import`,
        payload
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
    },
  });
}

export function useDraftSheetSync(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      sheet_url: string;
      worksheet_gid?: string;
      worksheet_names?: string[];
      replace_mode?: "upsert" | "replace_offense_pool";
      watchlist_name?: string;
    }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Sheet sync is missing a valid league id.");
      }
      return apiPost<DraftSheetSyncResponse>(`/leagues/${leagueId}/draft-room/sheet-sync`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
    },
  });
}

export function useDraftQueue(leagueId?: number, teamId?: number | null, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "draft-queue", teamId ?? "self"],
    enabled:
      enabled &&
      typeof leagueId === "number" &&
      !Number.isNaN(leagueId),
    staleTime: 5_000,
    queryFn: () =>
      apiGet<DraftQueue>(`/leagues/${leagueId}/draft-room/queue`, teamId ? { team_id: teamId } : undefined),
  });
}

export function useDraftQueueAdd(leagueId?: number, teamId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (playerId: number) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft queue add is missing a valid league id.");
      }
      return apiPost<DraftQueue>(
        `/leagues/${leagueId}/draft-room/queue${teamId ? `?team_id=${teamId}` : ""}`,
        { player_id: playerId }
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-queue", teamId ?? "self"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
    },
  });
}

export function useDraftQueueRemove(leagueId?: number, teamId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (playerId: number) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft queue remove is missing a valid league id.");
      }
      return apiDelete<DraftQueue>(
        `/leagues/${leagueId}/draft-room/queue/${playerId}`,
        teamId ? { team_id: teamId } : undefined
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-queue", teamId ?? "self"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
    },
  });
}

export function useDraftQueueClear(leagueId?: number, teamId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft queue clear is missing a valid league id.");
      }
      return apiPost<DraftQueue>(
        `/leagues/${leagueId}/draft-room/queue/clear${teamId ? `?team_id=${teamId}` : ""}`,
        {}
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-queue", teamId ?? "self"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
    },
  });
}

export function useDraftQueueReorder(leagueId?: number, teamId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (playerIds: number[]) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft queue reorder is missing a valid league id.");
      }
      return apiPost<DraftQueue>(
        `/leagues/${leagueId}/draft-room/queue/reorder${teamId ? `?team_id=${teamId}` : ""}`,
        { player_ids: playerIds }
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-queue", teamId ?? "self"], payload);
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
    },
  });
}
