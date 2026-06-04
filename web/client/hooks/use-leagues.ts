import { useQuery } from "@tanstack/react-query";

import { apiGet, ApiError } from "@/lib/api";
import type {
  LeagueDetail,
  LeagueListResponse,
  LeagueNewsResponse,
  LeaguePowerRankingResponse,
  LeagueScoreboardResponse,
  LeagueWorkspace,
} from "@/types/league";

export function useLeagues(limit = 20, enabled = true) {
  return useQuery({
    queryKey: ["leagues", limit],
    enabled,
    staleTime: 30_000,
    queryFn: async () => {
      const payload = await apiGet<LeagueListResponse>("/leagues", { limit });
      return payload.data.sort(
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

export function useLeagueScoreboard(
  leagueId?: number,
  week?: number,
  enabled = true
) {
  return useQuery({
    queryKey: ["league", leagueId, "scoreboard", week ?? "default"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [404, 405, 501].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () =>
      apiGet<LeagueScoreboardResponse>(`/leagues/${leagueId}/matchups`, {
        week: typeof week === "number" ? week : undefined,
      }),
  });
}

export function useLeaguePowerRankings(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "power-rankings"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [404, 405, 501].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () => apiGet<LeaguePowerRankingResponse>(`/leagues/${leagueId}/power-rankings`),
  });
}

export function useLeagueNews(
  leagueId?: number,
  limit = 25,
  enabled = true
) {
  return useQuery({
    queryKey: ["league", leagueId, "news", limit],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [404, 405, 501].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () =>
      apiGet<LeagueNewsResponse>(`/leagues/${leagueId}/news`, {
        limit,
      }),
  });
}
