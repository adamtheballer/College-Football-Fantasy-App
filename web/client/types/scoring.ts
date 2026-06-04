import type { Lineup } from "@/types/lineup";

export interface MatchupScore {
  matchup_id: number;
  week: number;
  status: string;
  home_team_id: number;
  home_team_name?: string | null;
  home_score: number;
  away_team_id: number;
  away_team_name?: string | null;
  away_score: number;
}

export interface ScheduleResponse {
  league_id: number;
  season: number;
  created?: number;
  matchups: MatchupScore[];
}

export interface TeamWeeklyScore {
  team_id: number;
  team_name?: string | null;
  season: number;
  week: number;
  starter_points: number;
  bench_points: number;
  total_points: number;
  breakdown_json: Record<string, unknown>;
}

export interface WeekScoreResponse {
  league_id: number;
  season: number;
  week: number;
  player_scores_count: number;
  team_scores: TeamWeeklyScore[];
  matchups: MatchupScore[];
}

export interface WeekFinalizeStanding {
  team_id: number;
  team_name?: string | null;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
  points_against: number;
}

export interface WeekFinalizeResponse {
  league_id: number;
  season: number;
  week: number;
  finalized_matchups: number;
  standings: WeekFinalizeStanding[];
}

export interface FantasyPlayerScore {
  player_id: number;
  player_name?: string | null;
  season: number;
  week: number;
  points: number;
  breakdown_json: Record<string, unknown>;
}

export interface MatchupDetailResponse {
  matchup: MatchupScore;
  home_lineup: Lineup | null;
  away_lineup: Lineup | null;
  home_team_score: TeamWeeklyScore | null;
  away_team_score: TeamWeeklyScore | null;
  player_scores: FantasyPlayerScore[];
}
