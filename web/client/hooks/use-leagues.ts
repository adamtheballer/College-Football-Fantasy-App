import { useQuery } from "@tanstack/react-query";

import { apiGet, ApiError } from "@/lib/api";
import type { LeagueDetail, LeagueListResponse, LeagueWorkspace } from "@/types/league";

export function useLeagues(limit = 20, enabled = true) {
  return useQuery({
    queryKey: ["leagues", "detail", limit],
    enabled,
    staleTime: 30_000,
    queryFn: async () => {
      const payload = await apiGet<LeagueListResponse>("/leagues", { limit });
      const details = await Promise.all(
        payload.data.map((row) => apiGet<LeagueDetail>(`/leagues/${row.id}`))
      );
      return details.sort(
        (left, right) =>
          new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
      );
    },
  });
}

export function useLeagueDetail(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    queryFn: () => apiGet<LeagueDetail>(`/leagues/${leagueId}`),
  });
}

export function useLeagueWorkspace(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "workspace"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [404, 405, 501].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () => apiGet<LeagueWorkspace>(`/leagues/${leagueId}/workspace`),
  });
}
