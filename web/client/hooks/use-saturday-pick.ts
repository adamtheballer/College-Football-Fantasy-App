import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPut } from "@/lib/api";

export type SaturdayPickPlayer = {
  id: number;
  player_id: number;
  canonical_position: "QB" | "RB" | "WR" | "TE";
  player_name: string;
  school: string;
  opponent: string;
  game_time: string;
  image_url: string | null;
  projected_points: number | null;
  live_points: number | null;
  final_points: number | null;
  scoring_status: string;
  sort_order: number;
};

export type SaturdayPickContest = {
  id: number;
  season: number;
  week_number: number;
  title: string;
  contest_position: "QB" | "RB" | "WR" | "TE";
  status: string;
  lock_at: string;
  winning_player_ids: number[];
  players: SaturdayPickPlayer[];
  entry: {
    id: number;
    selected_pick_player_id: number;
    submitted_at: string;
    is_winner: boolean;
    reward_unlocked_at: string | null;
  } | null;
  sponsor: {
    name: string;
    logo_url: string | null;
    offer_text: string | null;
    terms: string | null;
    reward_unlocked: boolean;
    code: string | null;
    url: string | null;
  } | null;
};

export const SATURDAY_PICK_6_SEASON = 2026;
export const SATURDAY_PICK_6_WEEK = 1;

export function useSaturdayPickContest(enabled = true) {
  return useQuery({
    queryKey: ["saturday-pick-6", SATURDAY_PICK_6_SEASON, SATURDAY_PICK_6_WEEK],
    enabled,
    staleTime: 15_000,
    queryFn: () => apiGet<SaturdayPickContest>("/saturday-pick-6/current", {
      season: SATURDAY_PICK_6_SEASON,
      week: SATURDAY_PICK_6_WEEK,
    }),
  });
}

export function useSaveSaturdayPick() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ contestId, selectedPickPlayerId }: { contestId: number; selectedPickPlayerId: number }) =>
      apiPut(`/saturday-pick-6/${contestId}/entry`, { selected_pick_player_id: selectedPickPlayerId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saturday-pick-6"] }),
  });
}
