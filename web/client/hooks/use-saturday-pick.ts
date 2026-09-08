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
  first_game_player?: {
    id: number;
    player_id: number;
    player_name: string;
    opponent: string;
    game_time: string;
  };
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

export function useSaturdayPickContest(enabled = true) {
  return useQuery({
    queryKey: ["saturday-pick-6", "current"],
    enabled,
    staleTime: 5_000,
    // A finalized contest still needs to discover the next weekly publication.
    refetchInterval: 30_000,
    queryFn: () => apiGet<SaturdayPickContest>("/saturday-pick-6/current"),
  });
}

export function useSaturdayPickRewards() {
  return useQuery({
    queryKey: ["saturday-pick-6", "rewards"],
    staleTime: 5_000,
    refetchInterval: 30_000,
    queryFn: () => apiGet<SaturdayPickContest[]>("/saturday-pick-6/rewards"),
  });
}

export function useSaveSaturdayPick() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ contestId, selectedPickPlayerId }: { contestId: number; selectedPickPlayerId: number }) =>
      apiPut<NonNullable<SaturdayPickContest["entry"]>>(`/saturday-pick-6/${contestId}/entry`, { selected_pick_player_id: selectedPickPlayerId }),
    onSuccess: (entry) => {
      queryClient.setQueriesData<SaturdayPickContest>(
        { queryKey: ["saturday-pick-6", "current"] },
        (contest) => contest ? { ...contest, entry } : contest
      );
      void queryClient.invalidateQueries({ queryKey: ["saturday-pick-6"] });
    },
  });
}
