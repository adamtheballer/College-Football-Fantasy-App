import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export const RANKING_POSITIONS = ["QB", "RB", "WR", "TE", "K"] as const;
export type RankedPlayer = {
  id: number;
  name: string;
  school: string;
  position: string;
  image_url: string | null;
  fantasy_points: number | null;
  position_rank: number | null;
  games: number;
  missing_games: number;
  status: "final" | "pending" | "bye" | "ineligible";
  stats: Record<string, number>;
  updated_at: string | null;
  on_my_roster: boolean;
};
export type RankingContext = {
  season: number;
  period: "week" | "season";
  week: number | null;
  through_week: number;
  available_weeks: number[];
  league_id: number | null;
  scoring_label: string;
  verified_players: number;
  pending_players: number;
  updated_at: string | null;
};
export type RankingFilters = {
  season?: number;
  period?: "week" | "season";
  week?: number;
  position?: string;
  league_id?: number;
  mine?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
};
export type PlayerRankingList = RankingContext & {
  data: RankedPlayer[];
  total: number;
  limit: number;
  offset: number;
};
export type PlayerLeaders = RankingContext & {
  data: { position: string; player: RankedPlayer | null }[];
};

function checkedRankingResponse<T extends RankingContext & {data: unknown[]}>(value: T): T {
  if (!value || !Array.isArray(value.data) || !["week","season"].includes(value.period)
      || !Array.isArray(value.available_weeks) || typeof value.scoring_label !== "string"
      || !Number.isFinite(value.through_week) || !Number.isFinite(value.pending_players)) {
    throw new Error("Verified player rankings returned an invalid response.");
  }
  return value;
}

export function usePlayerRankings(filters: RankingFilters, enabled = true) {
  const { user, isBootstrapping } = useAuth();
  return useQuery({
    queryKey: ["player-rankings", user?.id, filters],
    enabled: enabled && !!user && !isBootstrapping,
    queryFn: ({ signal }) =>
      apiGet<PlayerRankingList>("/player-rankings", filters, signal).then(checkedRankingResponse),
    staleTime: 30_000,
    refetchInterval: 180_000,
    refetchIntervalInBackground: false,
  });
}
export function usePositionLeaders(period: "week" | "season", enabled = true) {
  const { user, isBootstrapping } = useAuth();
  return useQuery({
    queryKey: ["position-leaders", period, user?.id],
    enabled: enabled && !!user && !isBootstrapping,
    queryFn: ({ signal }) =>
      apiGet<PlayerLeaders>("/player-rankings/leaders", { period }, signal).then(checkedRankingResponse),
    staleTime: 30_000,
    refetchInterval: 180_000,
    refetchIntervalInBackground: false,
  });
}
export const rankingPeriodLabel = (data: RankingContext) =>
  data.period === "week"
    ? `Week ${data.week ?? "—"}`
    : `Season · through Week ${data.through_week}`;
export const rankingPoints = (points: number | null) =>
  points !== null && Number.isFinite(points) ? points.toFixed(1) : "—";
