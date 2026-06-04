import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type {
  StandaloneMockDraftCreateRequest,
  StandaloneMockDraftCreateResponse,
  StandaloneMockDraftEmailResponse,
  StandaloneMockDraftHistory,
  StandaloneMockDraftLobby,
  StandaloneMockDraftRoom,
} from "@/types/mock-draft";

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
    },
  });
}

export function useMockDraftAutoPick(mockDraftId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { force?: boolean } = {}) =>
      apiPost<StandaloneMockDraftRoom>(`/mock-drafts/${mockDraftId}/auto-pick`, { force: Boolean(payload.force) }),
    onSuccess: (payload) => {
      queryClient.setQueryData(["mock-draft", mockDraftId, "room"], payload);
      queryClient.invalidateQueries({ queryKey: ["players"] });
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

export function useRecentMockDrafts(enabled = true) {
  return useQuery({
    queryKey: ["mock-drafts", "recent"],
    enabled,
    staleTime: 10_000,
    queryFn: () => apiGet<{ data: StandaloneMockDraftLobby[] }>("/mock-drafts/recent"),
  });
}
