import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import type { Watchlist, WatchlistListResponse } from "@/types/watchlist";

export function useWatchlists(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: ["watchlists", leagueId ?? "all"],
    enabled,
    staleTime: 30_000,
    queryFn: () =>
      apiGet<WatchlistListResponse>("/watchlists", {
        league_id: leagueId,
      }),
  });
}

export function useCreateWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; league_id?: number | null }) =>
      apiPost<Watchlist>("/watchlists", payload),
    onSuccess: (watchlist) => {
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      if (watchlist.league_id) {
        queryClient.invalidateQueries({ queryKey: ["watchlists", watchlist.league_id] });
      }
    },
  });
}

export function useRenameWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ watchlistId, name }: { watchlistId: number; name: string }) =>
      apiPatch<Watchlist>(`/watchlists/${watchlistId}`, { name }),
    onSuccess: (watchlist) => {
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      if (watchlist.league_id) {
        queryClient.invalidateQueries({ queryKey: ["watchlists", watchlist.league_id] });
      }
    },
  });
}

export function useToggleWatchlistPlayer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      watchlistId,
      playerId,
      isSaved,
      notes,
      priority,
      tags,
    }: {
      watchlistId: number;
      playerId: number;
      isSaved: boolean;
      notes?: string | null;
      priority?: number;
      tags?: string[];
    }) => {
      if (isSaved) {
        return apiDelete<Watchlist>(`/watchlists/${watchlistId}/players/${playerId}`);
      }
      return apiPost<Watchlist>(`/watchlists/${watchlistId}/players`, {
        player_id: playerId,
        notes,
        priority,
        tags,
      });
    },
    onSuccess: (watchlist) => {
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      if (watchlist.league_id) {
        queryClient.invalidateQueries({ queryKey: ["watchlists", watchlist.league_id] });
      }
    },
  });
}

export function useUpdateWatchlistPlayer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      watchlistId,
      playerId,
      payload,
    }: {
      watchlistId: number;
      playerId: number;
      payload: {
        notes?: string | null;
        priority?: number | null;
        tags?: string[] | null;
        alert_available?: boolean | null;
        alert_injury?: boolean | null;
        alert_projection?: boolean | null;
        alert_ownership?: boolean | null;
        alert_matchup?: boolean | null;
      };
    }) => apiPatch<Watchlist>(`/watchlists/${watchlistId}/players/${playerId}`, payload),
    onSuccess: (watchlist) => {
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
      if (watchlist.league_id) {
        queryClient.invalidateQueries({ queryKey: ["watchlists", watchlist.league_id] });
      }
    },
  });
}
