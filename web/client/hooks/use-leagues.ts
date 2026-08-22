import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPatch, apiPost, ApiError } from "@/lib/api";
import type {
  DraftInfo,
  DraftOrder,
  LeagueDetail,
  LeagueCreateResponse,
  LeagueListResponse,
  LeagueMatchupTabResponse,
  LeaguePostseasonResponse,
  LeagueNewsResponse,
  LeaguePowerRankingResponse,
  LeagueRosterTabResponse,
  LeagueScoreboardResponse,
  LeagueSettingsTabResponse,
  LeagueWaiverTabResponse,
  LeagueWorkspace,
  LeagueRivalryView,
} from "@/types/league";

export type DraftUpdatePayload = {
  draft_datetime_utc: string;
  timezone: string;
  draft_type: string;
  pick_timer_seconds: number;
  status?: string;
};

export type DraftOrderUpdatePayload = {
  draft_order_mode: "random" | "custom";
  entries: Array<{ team_id: number; draft_position: number }>;
};

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
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["league", leagueId] }),
        queryClient.invalidateQueries({ queryKey: ["leagues"] }),
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] }),
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "settings-view"] }),
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] }),
        queryClient.invalidateQueries({ queryKey: ["draft-room", leagueId] }),
      ]);
    },
  });
}

export function useUpdateDraftOrder(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DraftOrderUpdatePayload) => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPatch<DraftOrder>(`/leagues/${leagueId}/draft-order`, payload);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["league", leagueId] }),
        queryClient.invalidateQueries({ queryKey: ["leagues"] }),
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] }),
      ]);
    },
  });
}

const invalidateLeagueQueries = (queryClient: ReturnType<typeof useQueryClient>, leagueId: number) => {
  queryClient.invalidateQueries({ queryKey: ["league", leagueId] });
  queryClient.invalidateQueries({ queryKey: ["leagues"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "settings-view"] });
  queryClient.invalidateQueries({ queryKey: ["league", leagueId, "draft-room"] });
};

export function useRotateLeagueInvite(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPost<LeagueCreateResponse>(`/leagues/${leagueId}/invite/rotate`, {});
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateLeagueQueries(queryClient, leagueId);
    },
  });
}

export function useRevokeLeagueInvite(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (typeof leagueId !== "number" || Number.isNaN(leagueId)) {
        throw new ApiError(400, "Invalid league ID.");
      }
      return apiPost<LeagueDetail>(`/leagues/${leagueId}/invite/revoke`, {});
    },
    onSuccess: () => {
      if (typeof leagueId === "number") invalidateLeagueQueries(queryClient, leagueId);
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
    refetchInterval: (query) => {
      const teamRosters = query.state.data?.team_rosters;
      const roster =
        (teamRosters?.length ? teamRosters.flatMap((team) => team.roster) : undefined) ??
        query.state.data?.slots ??
        query.state.data?.roster ??
        query.state.data?.data ??
        [];
      if (roster.some((player) =>
        ["live", "stale"].includes((player.live_scoring_status ?? "").toLowerCase()) ||
        (player.live_game_state ?? "").toLowerCase() === "live"
      )) {
        return 10_000;
      }
      return 30_000;
    },
    refetchIntervalInBackground: true,
  });
}

export function useLeagueMatchupTab(
  leagueId?: number,
  week?: number,
  matchupId?: number,
  enabled = true
) {
  const LIVE_REFRESH_MS = 180_000;
  return useQuery({
    queryKey: ["league", leagueId, "matchup", week ?? "auto", matchupId ?? "mine"],
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
        matchup_id: typeof matchupId === "number" ? matchupId : undefined,
      }),
    refetchInterval: (query) => {
      const status = query.state.data?.status?.toLowerCase();
      if (status === "live") {
        const nextRefreshAt = query.state.data?.next_refresh_at;
        if (nextRefreshAt) {
          const remaining = new Date(nextRefreshAt).getTime() - Date.now();
          if (Number.isFinite(remaining) && remaining > 0) return Math.max(15_000, remaining);
        }
        return LIVE_REFRESH_MS;
      }
      if (status === "final" || status === "stat_corrected") return false;
      return 30_000;
    },
    refetchIntervalInBackground: true,
  });
}

export function useLeaguePostseason(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "postseason"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 60_000,
    retry: (failureCount, error) => !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && failureCount < 2,
    queryFn: () => apiGet<LeaguePostseasonResponse>(`/leagues/${leagueId}/postseason`),
  });
}

export function useLeaguePostseasonBracket(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "postseason", "bracket"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 60_000,
    retry: (failureCount, error) => !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && failureCount < 2,
    queryFn: () => apiGet<LeaguePostseasonResponse>(`/leagues/${leagueId}/postseason/bracket`),
  });
}

export function useLeagueRivalry(leagueId?: number, enabled = true) {
  return useQuery({ queryKey: ["league", leagueId, "rivalry"], enabled: enabled && typeof leagueId === "number", queryFn: () => apiGet<LeagueRivalryView>(`/leagues/${leagueId}/rivalry`) });
}

export function useRivalryActions(leagueId?: number) {
  const queryClient = useQueryClient();
  const invalidate = () => { queryClient.invalidateQueries({ queryKey: ["league", leagueId, "rivalry"] }); queryClient.invalidateQueries({ queryKey: ["league", leagueId, "matchup"] }); };
  return {
    invite: useMutation({ mutationFn: (recipientTeamId: number) => apiPost(`/leagues/${leagueId}/rivalry/invites`, { recipient_team_id: recipientTeamId }), onSuccess: invalidate }),
    accept: useMutation({ mutationFn: (id: number) => apiPost(`/leagues/${leagueId}/rivalry/invites/${id}/accept`, {}), onSuccess: invalidate }),
    decline: useMutation({ mutationFn: (id: number) => apiPost(`/leagues/${leagueId}/rivalry/invites/${id}/decline`, {}), onSuccess: invalidate }),
    cancel: useMutation({ mutationFn: (id: number) => apiDelete(`/leagues/${leagueId}/rivalry/invites/${id}`), onSuccess: invalidate }),
  };
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
  limit = 1000,
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
    refetchInterval: (query) => {
      const statuses = query.state.data?.data.map((matchup) => matchup.status.toLowerCase()) ?? [];
      if (statuses.some((status) => status === "live" || status === "delayed")) return 10_000;
      if (statuses.length > 0 && statuses.every((status) => status === "final" || status === "stat_corrected")) return false;
      return 30_000;
    },
    refetchIntervalInBackground: true,
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
