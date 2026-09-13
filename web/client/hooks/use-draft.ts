import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api";
import type { DraftRoom } from "@/types/draft";
import { reconcileDraftRoom, stampDraftRoom } from "@/lib/draftReconciliation";

const roomKey = (leagueId?: number) => ["league", leagueId, "draft-room"] as const;

export function useDraftRoom(leagueId?: number, enabled = true) {
  const queryClient = useQueryClient();
  return useQuery<DraftRoom>({
    queryKey: roomKey(leagueId),
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 1_000,
    refetchInterval: (query) => {
      const room = query.state.data as DraftRoom | undefined;
      const status = room?.status?.toLowerCase();
      if (status === "pre_draft" || status === "on_clock" || status === "transition") return 1_000;
      if (status === "scheduled") return 15_000;
      return false;
    },
    refetchIntervalInBackground: true,
    queryFn: async ({ signal }) => {
      const draftId = queryClient.getQueryData<DraftRoom>(roomKey(leagueId))?.draft_id;
      const incoming = stampDraftRoom(await apiGet<DraftRoom>(`/leagues/${leagueId}/draft-room`, undefined, signal));
      return reconcileDraftRoom(queryClient.getQueryData<DraftRoom>(roomKey(leagueId)), incoming, draftId);
    },
    // Applies at cache commit as well as fetch completion (GET vs POST race).
    structuralSharing: (current, incoming) => reconcileDraftRoom(current as DraftRoom | undefined, incoming as DraftRoom),
  });
}

export function useDraftPick(leagueId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    retry: false,
    onMutate: async () => {
      const draftId = queryClient.getQueryData<DraftRoom>(roomKey(leagueId))?.draft_id;
      await queryClient.cancelQueries({ queryKey: roomKey(leagueId) });
      return { draftId };
    },
    mutationFn: async ({
      playerId,
      pickNumber,
      draftVersion,
    }: {
      playerId: number;
      pickNumber: number;
      draftVersion: number;
    }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft room is missing a valid league id.");
      }
      const before = queryClient.getQueryData<DraftRoom>(roomKey(leagueId));
      try {
        return stampDraftRoom(await apiPost<DraftRoom>(`/leagues/${leagueId}/draft-picks`, {
          player_id: playerId,
          pick_number: pickNumber,
          draft_version: draftVersion,
        }));
      } catch (error) {
        // A lost POST response is not proof of failure. Read authority once;
        // never resubmit a stale/versioned pick envelope automatically.
        try {
          const observed = stampDraftRoom(await apiGet<DraftRoom>(`/leagues/${leagueId}/draft-room`));
          const latest = reconcileDraftRoom(queryClient.getQueryData<DraftRoom>(roomKey(leagueId)), observed, before?.draft_id);
          queryClient.setQueryData(roomKey(leagueId), latest);
          if (latest.draft_id === before?.draft_id && latest.picks.some((pick) =>
            pick.overall_pick === pickNumber && pick.player_id === playerId && pick.team_id === before.user_team_id
          )) return latest;
        } catch { /* The normal reconnect state handles a failed reconciliation. */ }
        throw error;
      }
    },
    onSuccess: (payload, _variables, context) => {
      queryClient.setQueryData<DraftRoom>(roomKey(leagueId), (current) => reconcileDraftRoom(current, payload, context?.draftId));
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
      queryClient.invalidateQueries({ queryKey: ["draft-player-pool"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
      if (payload.user_team_id) {
        queryClient.invalidateQueries({ queryKey: ["team", payload.user_team_id, "roster"] });
      }
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
      queryClient.invalidateQueries({ queryKey: ["draft-player-pool"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });
}

export function useStartDraft(leagueId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    retry: false,
    onMutate: async () => {
      const draftId = queryClient.getQueryData<DraftRoom>(roomKey(leagueId))?.draft_id;
      await queryClient.cancelQueries({ queryKey: roomKey(leagueId) });
      return { draftId };
    },
    mutationFn: async () => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft room is missing a valid league id.");
      }
      return stampDraftRoom(await apiPost<DraftRoom>(`/leagues/${leagueId}/draft/start`, {}));
    },
    onSuccess: (payload, _variables, context) => {
      queryClient.setQueryData<DraftRoom>(roomKey(leagueId), (current) => reconcileDraftRoom(current, payload, context?.draftId));
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "teams"] });
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
    },
  });
}
