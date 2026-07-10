import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPatch, apiPost, ApiError } from "@/lib/api";
import type {
  DraftInfo,
  LeagueDetail,
  LeagueListResponse,
  LeagueWaiverClaim,
  LeagueMatchupTabResponse,
  LeagueNewsResponse,
  LeaguePowerRankingResponse,
  LeagueRosterTabResponse,
  LeagueScoreboardResponse,
  LeagueSettingsTabResponse,
  LeagueWaiverTabResponse,
  LeagueWorkspace,
} from "@/types/league";

export type DraftUpdatePayload = {
  draft_datetime_utc: string;
  timezone: string;
  draft_type: string;
  pick_timer_seconds: number;
  status?: string;
};

export const mergeDraftIntoLeagueDetail = (
  current: LeagueDetail | undefined,
  updatedDraft: DraftInfo
) => (current ? { ...current, draft: updatedDraft } : current);

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

export function useRescheduleDraft(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DraftUpdatePayload) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPatch<DraftInfo>(`/leagues/${leagueId}/draft`, payload);
    },
    onSuccess: (updatedDraft) => {
      queryClient.setQueryData<LeagueDetail | undefined>(["league", leagueId], (current) =>
        mergeDraftIntoLeagueDetail(current, updatedDraft)
      );
      queryClient.invalidateQueries({ queryKey: ["league", leagueId] });
      queryClient.invalidateQueries({ queryKey: ["leagues"] });
      queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
    },
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

export function useLeagueRosterTab(
  leagueId?: number,
  week?: number,
  enabled = true
) {
  return useQuery({
    queryKey: ["league", leagueId, "roster", week ?? "auto"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () =>
      apiGet<LeagueRosterTabResponse>(`/leagues/${leagueId}/roster`, {
        week: typeof week === "number" ? week : undefined,
      }),
  });
}

export function useLeagueMatchupTab(
  leagueId?: number,
  week?: number,
  enabled = true
) {
  return useQuery({
    queryKey: ["league", leagueId, "matchup", week ?? "auto"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () =>
      apiGet<LeagueMatchupTabResponse>(`/leagues/${leagueId}/matchup`, {
        week: typeof week === "number" ? week : undefined,
      }),
    refetchInterval: (query) => {
      const status = query.state.data?.status?.toLowerCase();
      if (status === "live") return 10_000;
      if (status === "final" || status === "stat_corrected") return false;
      return 30_000;
    },
    refetchIntervalInBackground: true,
  });
}

export function useLeagueSettingsTab(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "settings-view"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () => apiGet<LeagueSettingsTabResponse>(`/leagues/${leagueId}/settings-view`),
  });
}

export function useLeagueWaiverTab(
  leagueId?: number,
  limit = 50,
  offset = 0,
  enabled = true
) {
  return useQuery({
    queryKey: ["league", leagueId, "waivers", limit, offset],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
        return false;
      }
      return failureCount < 2;
    },
    queryFn: () =>
      apiGet<LeagueWaiverTabResponse>(`/leagues/${leagueId}/waivers`, {
        limit,
        offset,
      }),
  });
}

export type WaiverClaimPayload = {
  team_id: number;
  add_player_id: number;
  drop_player_id?: number | null;
  bid_amount?: number | null;
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
      if (typeof leagueId === "number") {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "waivers"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "roster"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "transactions"] });
        queryClient.invalidateQueries({ queryKey: ["players"] });
      }
    },
  });
}

export function useCancelWaiverClaim(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (claimId: number) => apiDelete<LeagueWaiverClaim>(`/waivers/claims/${claimId}`),
    onSuccess: () => {
      if (typeof leagueId === "number") {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "waivers"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "transactions"] });
      }
    },
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
