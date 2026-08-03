import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPut } from "@/lib/api";
import type { SaturdayPickSponsor } from "@/lib/saturday-pick-sponsor";

export type SaturdayPickPlayer = {
  id: number;
  player_id: number;
  canonical_position: "QB" | "RB" | "WR" | "TE";
  player_name: string;
  school: string;
  opponent: string;
  game_id: number | null;
  game_time: string;
  image_url: null;
  projected_points: number | null;
  live_points: number | null;
  final_points: number | null;
  scoring_status: string;
  sort_order: number;
};

export type SaturdayPickEntry = {
  id: number;
  selected_pick_player_id: number;
  submitted_at: string;
  is_winner: boolean;
  reward_unlocked_at: string | null;
};

export type SaturdayPickContest = {
  id: number;
  season: number;
  week_number: number;
  title: string;
  contest_position: "QB" | "RB" | "WR" | "TE";
  status: string;
  lock_at: string;
  players: SaturdayPickPlayer[];
  entry: SaturdayPickEntry | null;
  sponsor: SaturdayPickSponsor | null;
};

export const saturdayPickQueryKey = (season: number, week: number) =>
  ["saturday-pick-6", season, week] as const;

export const useSaturdayPickContest = (season = 2026, week = 1, enabled = true) =>
  useQuery({
    queryKey: saturdayPickQueryKey(season, week),
    queryFn: () => apiGet<SaturdayPickContest>("/saturday-pick-6/current", { season, week }),
    enabled,
    staleTime: 15_000,
    retry: false,
  });

export const useSaveSaturdayPick = (season = 2026, week = 1) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ contestId, selectedPickPlayerId }: { contestId: number; selectedPickPlayerId: number }) =>
      apiPut(`/saturday-pick-6/${contestId}/entry`, {
        selected_pick_player_id: selectedPickPlayerId,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: saturdayPickQueryKey(season, week) }),
  });
};

export const useClearSaturdayPick = (season = 2026, week = 1) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ contestId }: { contestId: number }) => apiDelete(`/saturday-pick-6/${contestId}/entry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: saturdayPickQueryKey(season, week) }),
  });
};
