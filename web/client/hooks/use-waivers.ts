import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiPatch, apiPost, ApiError } from "@/lib/api";
import type { LeagueWaiverClaim } from "@/types/league";

type WaiverClaimPayload = {
  team_id: number;
  add_player_id: number;
  drop_roster_entry_id?: number;
  faab_bid: number;
  preference_order?: number;
  reason?: string;
};

type FreeAgentAddPayload = {
  team_id: number;
  drop_roster_entry_id?: number;
};

const invalidateWaiverQueries = (queryClient: ReturnType<typeof useQueryClient>, leagueId: number) => {
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "waivers"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "roster"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "matchup"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "transactions"] });
  queryClient.invalidateQueries({ queryKey: ["players"] });
};

export function useSubmitWaiverClaim(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: WaiverClaimPayload) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPost<LeagueWaiverClaim>(`/leagues/${leagueId}/waivers/claims`, payload);
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateWaiverQueries(queryClient, leagueId);
    },
  });
}

export function useAddFreeAgent(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ playerId, payload }: { playerId: number; payload: FreeAgentAddPayload }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPost(`/leagues/${leagueId}/waivers/free-agents/${playerId}/add`, payload);
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateWaiverQueries(queryClient, leagueId);
    },
  });
}

export function useCancelWaiverClaim(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ claimId, reason }: { claimId: number; reason?: string }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPost<LeagueWaiverClaim>(`/leagues/${leagueId}/waivers/claims/${claimId}/cancel`, { reason });
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateWaiverQueries(queryClient, leagueId);
    },
  });
}

export function useEditWaiverClaim(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ claimId, payload }: { claimId: number; payload: WaiverClaimPayload }) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPatch<LeagueWaiverClaim>(`/leagues/${leagueId}/waivers/claims/${claimId}`, payload);
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateWaiverQueries(queryClient, leagueId);
    },
  });
}

export function useReorderWaiverClaims(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (claimIds: number[]) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPost<LeagueWaiverClaim[]>(`/leagues/${leagueId}/waivers/claims/reorder`, { claim_ids: claimIds });
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateWaiverQueries(queryClient, leagueId);
    },
  });
}
