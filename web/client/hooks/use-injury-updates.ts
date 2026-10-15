import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

export type InjuryUpdate = {
  player_id: number; player_name: string; team: string; conference: string | null;
  position: string; season: number; week: number; status: string;
  injury: string | null; return_timeline: string | null; practice_level: string | null;
  notes: string | null; last_updated: string; projection_delta: number | null;
  source_url?: string | null;
};
export type InjuryUpdates = { data: InjuryUpdate[]; total: number; season: number; week: number };

/** One live injury feed shared by the center and player/draft lists.
 * Omit week to let the server follow its fantasy-week rollover. */
export function useInjuryUpdates({ season, week, enabled = true }: { season?: number; week?: number; enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["injury-updates", season ?? "current", week ?? "current"],
    enabled,
    staleTime: 15_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: "always",
    queryFn: ({ signal }) => apiGet<InjuryUpdates>("/injuries", { season, week }, signal),
  });
}
