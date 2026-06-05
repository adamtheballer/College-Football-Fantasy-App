import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { normalizePlayer } from "@/hooks/use-players";
import type { Player } from "@/types/player";
import type {
  StandaloneMockDraftCreateRequest,
  StandaloneMockDraftCreateResponse,
  StandaloneMockDraftEmailResponse,
  StandaloneMockDraftHistory,
  StandaloneMockDraftLobby,
  StandaloneMockDraftRoom,
} from "@/types/mock-draft";

type BackendPlayerRead = {
  id: number;
  name: string;
  position: string;
  school: string;
  image_url?: string | null;
  player_class?: string | null;
  sheet_adp?: number | null;
  sheet_projected_season_points?: number | null;
  sheet_projection_stats?: Record<string, number | null> | null;
  sheet_source_sheet_id?: string | null;
  sheet_synced_at?: string | null;
  board_rank?: number | null;
};

type BackendPlayerListResponse = {
  data: BackendPlayerRead[];
  total: number;
  limit: number;
  offset: number;
};

type MockAvailablePlayerListResponse = Omit<BackendPlayerListResponse, "data"> & {
  data: Player[];
};

export function useCreateMockDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StandaloneMockDraftCreateRequest) =>
      apiPost<StandaloneMockDraftCreateResponse>("/mock-drafts", payload),
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["mock-drafts", "recent"] });
      queryClient.invalidateQueries({ queryKey: ["mock-draft", payload.mock_draft_id] });
    },
  });
}

export function useJoinMockDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { invite_code: string; team_name?: string | null; display_name?: string | null }) =>
      apiPost<StandaloneMockDraftLobby>("/mock-drafts/join", payload),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", payload.id, "lobby"], payload);
      queryClient.invalidateQueries({ queryKey: ["mock-drafts", "recent"] });
    },
  });
}

export function useMockDraftLobby(mockDraftId?: number, enabled = true) {
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "lobby"],
    enabled: enabled && typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    refetchInterval: 3_000,
    queryFn: () => apiGet<StandaloneMockDraftLobby>(`/mock-drafts/${mockDraftId}/lobby`),
  });
}

export function useUpdateMockDraftSettings(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<StandaloneMockDraftCreateRequest>) =>
      apiPatch<StandaloneMockDraftLobby>(`/mock-drafts/${mockDraftId}/settings`, payload),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "lobby"], payload);
    },
  });
}

export function useMockDraftReady(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ready: boolean) => apiPost<StandaloneMockDraftLobby>(`/mock-drafts/${mockDraftId}/ready`, { ready }),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "lobby"], payload);
    },
  });
}

export function useMockDraftRoom(mockDraftId?: number, enabled = true) {
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "room"],
    enabled: enabled && typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    refetchInterval: (query) => {
      const room = query.state.data as StandaloneMockDraftRoom | undefined;
      if (!room) return 3_000;
      if (room.is_complete) return false;
      if (room.status === "intermission" || room.status === "live") return 1_000;
      return 3_000;
    },
    queryFn: () => apiGet<StandaloneMockDraftRoom>(`/mock-drafts/${mockDraftId}/room`),
  });
}

export function useMockDraftPick(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (playerId: number) => {
      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `mock-pick-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      return apiPost<StandaloneMockDraftRoom>(
        `/mock-drafts/${mockDraftId}/picks`,
        { player_id: playerId },
        undefined,
        { "Idempotency-Key": idempotencyKey }
      );
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "room"], payload);
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "available-players"] });
    },
  });
}

export function useMockDraftAutoPick(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { force?: boolean; expectedOverallPick?: number } = {}) =>
      apiPost<StandaloneMockDraftRoom>(`/mock-drafts/${mockDraftId}/auto-pick`, {
        force: Boolean(payload.force),
        expected_overall_pick: payload.expectedOverallPick,
      }),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "room"], payload);
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "available-players"] });
    },
  });
}

export function useMockDraftAvailablePlayers(
  mockDraftId?: number,
  params: { search?: string; position?: string; limit?: number; offset?: number } = {}
) {
  const { search, position, limit = 100, offset = 0 } = params;
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "available-players", { search: search || "", position: position || "", limit, offset }],
    enabled: typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    staleTime: 5_000,
    placeholderData: (previousData) => previousData,
    queryFn: async (): Promise<MockAvailablePlayerListResponse> => {
      const payload = await apiGet<BackendPlayerListResponse>(`/mock-drafts/${mockDraftId}/available-players`, {
        search: search || undefined,
        position: position || undefined,
        limit,
        offset,
      });
      return {
        ...payload,
        data: payload.data.map((player, index) =>
          normalizePlayer(player, {
            rank: player.board_rank ?? offset + index + 1,
            adp: player.sheet_adp ?? 0,
            posRank: null,
          })
        ),
      };
    },
  });
}

export function useMockDraftHistory(mockDraftId?: number, enabled = true) {
  return useQuery({
    queryKey: ["mock-draft", mockDraftId, "history"],
    enabled: enabled && typeof mockDraftId === "number" && !Number.isNaN(mockDraftId),
    queryFn: () => apiGet<StandaloneMockDraftHistory>(`/mock-drafts/${mockDraftId}/history`),
  });
}

export function useEmailMockDraftHistory(mockDraftId?: number) {
  return useMutation({
    mutationFn: () => apiPost<StandaloneMockDraftEmailResponse>(`/mock-drafts/${mockDraftId}/history/email`, { send_to_account_email: true }),
  });
}

export function useExitMockDraft(mockDraftId?: number) {
  return useMutation({
    mutationFn: () => apiPost<{ ok: boolean; navigate_to: string }>(`/mock-drafts/${mockDraftId}/exit`, {}),
  });
}

export function useResetSinglePlayerMockDraft(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<StandaloneMockDraftRoom>(`/mock-drafts/${mockDraftId}/reset`, {}),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "room"], payload);
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "available-players"] });
      queryClient.invalidateQueries({ queryKey: ["mock-draft", mockDraftId, "history"] });
    },
  });
}

export function useRecentMockDrafts(enabled = true) {
  return useQuery({
    queryKey: ["mock-drafts", "recent"],
    enabled,
    staleTime: 10_000,
    queryFn: () => apiGet<{ data: StandaloneMockDraftLobby[] }>("/mock-drafts/recent"),
  });
}
