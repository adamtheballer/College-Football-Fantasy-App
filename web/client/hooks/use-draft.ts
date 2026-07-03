import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api";
import type { DraftRoom } from "@/types/draft";

export function useDraftRoom(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "draft-room"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 1_000,
    refetchInterval: (query) => {
      const room = query.state.data as DraftRoom | undefined;
      const status = room?.status?.toLowerCase();
      if (status === "live" || status === "active") return 2_500;
      if (status === "scheduled") return 15_000;
      return false;
    },
    refetchIntervalInBackground: true,
    queryFn: () => apiGet<DraftRoom>(`/leagues/${leagueId}/draft-room`),
  });
}

export function useDraftPick(leagueId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (playerId: number) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new Error("Draft room is missing a valid league id.");
      }
      return apiPost<DraftRoom>(`/leagues/${leagueId}/draft-picks`, { player_id: playerId });
    },
    onSuccess: (payload) => {
      queryClient.setQueryData(["league", leagueId, "draft-room"], payload);
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
