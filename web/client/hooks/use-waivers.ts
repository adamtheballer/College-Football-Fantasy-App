import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiPost, ApiError } from "@/lib/api";
import type { LeagueWaiverClaim } from "@/types/league";

type WaiverClaimPayload = {
  team_id: number;
  add_player_id: number;
  drop_roster_entry_id?: number;
  faab_bid: number;
  reason?: string;
};

const invalidateWaiverQueries = (queryClient: ReturnType<typeof useQueryClient>, leagueId: number) => {
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "waivers"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "roster"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
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
