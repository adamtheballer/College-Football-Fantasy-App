import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { RosterEntryListResponse } from "@/types/roster";
import type { TeamListResponse } from "@/types/team";

export function useLeagueTeams(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "teams"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 30_000,
    queryFn: () => apiGet<TeamListResponse>(`/leagues/${leagueId}/teams`),
  });
}

export function useTeamRoster(teamId?: number, enabled = true) {
  return useQuery({
    queryKey: ["team", teamId, "roster"],
    enabled: enabled && typeof teamId === "number" && !Number.isNaN(teamId),
    staleTime: 30_000,
    queryFn: () => apiGet<RosterEntryListResponse>(`/teams/${teamId}/roster`),
  });
}
