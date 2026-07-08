import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import type { AddDropResponse, RosterEntry, Transaction } from "@/types/roster";

type TransactionListResponse = {
  data: Transaction[];
  total: number;
  limit: number;
  offset: number;
};

export function useLeagueTransactions(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["league", leagueId, "transactions"],
    enabled: enabled && typeof leagueId === "number" && !Number.isNaN(leagueId),
    staleTime: 15_000,
    queryFn: () => apiGet<TransactionListResponse>(`/leagues/${leagueId}/transactions`),
  });
}

export function useAddDrop(teamId?: number, leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      add_player_id: number;
      drop_roster_entry_id: number;
      reason?: string;
    }) => {
      if (typeof teamId !== "number") {
        throw new Error("Missing team id for add/drop.");
      }
      return apiPost<AddDropResponse>(`/teams/${teamId}/add-drop`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      if (typeof teamId === "number") {
        queryClient.invalidateQueries({ queryKey: ["team", teamId, "roster"] });
      }
      if (typeof leagueId === "number") {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "transactions"] });
      }
    },
  });
}

export function useAddRosterEntry(teamId?: number, leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { player_id: number; slot?: string; status?: string }) => {
      if (typeof teamId !== "number") {
        throw new Error("Missing team id for roster add.");
      }
      return apiPost<RosterEntry>(`/teams/${teamId}/roster`, {
        player_id: payload.player_id,
        slot: payload.slot ?? "BENCH",
        status: payload.status ?? "active",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      if (typeof teamId === "number") {
        queryClient.invalidateQueries({ queryKey: ["team", teamId, "roster"] });
      }
      if (typeof leagueId === "number") {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "roster"] });
      }
    },
  });
}

export function useDropRosterEntry(teamId?: number, leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rosterEntryId: number) => {
      if (typeof teamId !== "number") {
        throw new Error("Missing team id for roster drop.");
      }
      return apiDelete<void>(`/teams/${teamId}/roster/${rosterEntryId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      if (typeof teamId === "number") {
        queryClient.invalidateQueries({ queryKey: ["team", teamId, "roster"] });
      }
      if (typeof leagueId === "number") {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "roster"] });
      }
    },
  });
}

export function useUpdateLineup(teamId?: number, leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignments: Array<{ roster_entry_id: number; slot: string }>) => {
      if (typeof teamId !== "number") {
        throw new Error("Missing team id for lineup update.");
      }
      return apiPatch(`/teams/${teamId}/lineup`, { assignments });
    },
    onSuccess: () => {
      if (typeof teamId === "number") {
        queryClient.invalidateQueries({ queryKey: ["team", teamId, "roster"] });
      }
      if (typeof leagueId === "number") {
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "workspace"] });
        queryClient.invalidateQueries({ queryKey: ["league", leagueId, "transactions"] });
      }
    },
  });
}
