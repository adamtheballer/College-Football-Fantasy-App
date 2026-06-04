import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPatch, apiPost } from "@/lib/api";
import type { Lineup, LineupUpdateRequest, LineupUpdateResponse } from "@/types/lineup";
import type {
  MatchupDetailResponse,
  ScheduleResponse,
  WeekFinalizeResponse,
  WeekScoreResponse,
} from "@/types/scoring";

const invalidateLeagueLoop = (queryClient: ReturnType<typeof useQueryClient>, leagueId: number) => {
  queryClient.invalidateQueries({ queryKey: ["league", leagueId] });
};

export function useLeagueSchedule(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "schedule"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    queryFn: () => apiGet<ScheduleResponse>(`/leagues/${leagueId}/schedule`),
  });
}

export function useGenerateSchedule(leagueId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<ScheduleResponse>(`/leagues/${leagueId}/schedule/generate`, { weeks: 12 }),
    onSuccess: () => invalidateLeagueLoop(queryClient, leagueId),
  });
}

export function useTeamLineup(
  leagueId?: number,
  teamId?: number,
  season?: number,
  week?: number,
  enabled = true
) {
  return useQuery({
    queryKey: ["league", leagueId, "team", teamId, "lineup", season, week],
    enabled:
      enabled &&
      typeof leagueId === "number" &&
      typeof teamId === "number" &&
      typeof season === "number" &&
      typeof week === "number",
    staleTime: 10_000,
    queryFn: () =>
      apiGet<Lineup>(`/leagues/${leagueId}/teams/${teamId}/lineup`, {
        season,
        week,
      }),
  });
}

export function useUpdateLineup(leagueId: number, teamId: number, season: number, week: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LineupUpdateRequest) =>
      apiPatch<LineupUpdateResponse>(`/leagues/${leagueId}/teams/${teamId}/lineup`, payload, {
        season,
        week,
      }),
    onSuccess: () => invalidateLeagueLoop(queryClient, leagueId),
  });
}

export function useLockLineup(leagueId: number, teamId: number, season: number, week: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<Lineup>(`/leagues/${leagueId}/teams/${teamId}/lineup/lock`, {}, { season, week }),
    onSuccess: () => invalidateLeagueLoop(queryClient, leagueId),
  });
}

export function useScoreLeagueWeek(leagueId: number, week: number, season?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<WeekScoreResponse>(
        `/leagues/${leagueId}/weeks/${week}/score`,
        {},
        { season }
      ),
    onSuccess: () => invalidateLeagueLoop(queryClient, leagueId),
  });
}

export function useFinalizeLeagueWeek(leagueId: number, week: number, season?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<WeekFinalizeResponse>(
        `/leagues/${leagueId}/weeks/${week}/finalize`,
        {},
        { season }
      ),
    onSuccess: () => invalidateLeagueLoop(queryClient, leagueId),
  });
}

export function useWeekScores(leagueId?: number, week?: number, season?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "week-scores", season, week],
    enabled: enabled && typeof leagueId === "number" && typeof week === "number",
    staleTime: 10_000,
    queryFn: () =>
      apiGet<WeekScoreResponse>(`/leagues/${leagueId}/weeks/${week}/scores`, {
        season,
      }),
  });
}

export function useMatchupDetail(leagueId?: number, matchupId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "matchup", matchupId],
    enabled: enabled && typeof leagueId === "number" && typeof matchupId === "number",
    staleTime: 10_000,
    queryFn: () => apiGet<MatchupDetailResponse>(`/leagues/${leagueId}/matchups/${matchupId}`),
  });
}
