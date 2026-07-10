export interface LeagueSettings {
  id: number;
  league_id: number;
  scoring_json: Record<string, number | string | boolean>;
  roster_slots_json: Record<string, number>;
  playoff_teams: number;
  waiver_type: string;
  trade_review_type: string;
  superflex_enabled: boolean;
  kicker_enabled: boolean;
  defense_enabled: boolean;
}

export interface LeagueListResponse {
  data: LeagueDetail[];
  total: number;
  limit: number;
  offset: number;
}

export interface DraftInfo {
  id: number;
  league_id: number;
  draft_datetime_utc: string;
  timezone: string;
  draft_type: string;
  pick_timer_seconds: number;
  status: string;
}

export interface LeagueMember {
  id: number;
  user_id: number;
  role: string;
  joined_at: string;
}

export interface LeagueDetail {
  id: number;
  name: string;
  commissioner_user_id: number | null;
  season_year: number;
  max_teams: number;
  is_private: boolean;
  invite_code: string | null;
  description?: string | null;
  icon_url?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  settings: LeagueSettings;
  draft: DraftInfo | null;
  members: LeagueMember[];
}

export interface LeaguePreview {
  id: number;
  name: string;
  commissioner_name: string | null;
  max_teams: number;
  member_count: number;
  is_private: boolean;
  draft_datetime_utc: string | null;
  timezone: string | null;
  scoring_preset: string;
}

export interface LeagueCreateResponse {
  league: LeagueDetail;
  invite_code: string;
  invite_link: string;
}

export interface LeagueWorkspaceTeam {
  id: number;
  league_id: number;
  name: string;
  owner_user_id: number | null;
}

export interface LeagueWorkspaceRosterEntry {
  id: number;
  team_id: number;
  player_id: number | null;
  slot: string | null;
  status?: string | null;
  player_name?: string | null;
  player_school?: string | null;
  player_position?: string | null;
}

export interface LeagueWorkspaceMatchupSummary {
  week?: number | null;
  team_id?: number | null;
  opponent_team_id?: number | null;
  opponent_team_name?: string | null;
  status?: string | null;
  projected_points_for?: number | null;
  projected_points_against?: number | null;
}

export interface LeagueWorkspaceStandingSummary {
  team_id: number;
  team_name: string;
  wins?: number;
  losses?: number;
  ties?: number;
  points_for?: number;
  rank?: number;
}

export interface LeagueWorkspace {
  league: LeagueDetail;
  membership: LeagueMember | null;
  owned_team: LeagueWorkspaceTeam | null;
  roster: LeagueWorkspaceRosterEntry[];
  matchup_summary: LeagueWorkspaceMatchupSummary | null;
  standings_summary: LeagueWorkspaceStandingSummary[];
  allowed_actions: string[] | Record<string, boolean> | null;
}

export interface LeagueScoreboardRow {
  matchup_id: number;
  week: number;
  status: string;
  home_team_id: number;
  home_team_name: string;
  home_score: number;
  away_team_id: number;
  away_team_name: string;
  away_score: number;
}

export interface LeagueScoreboardResponse {
  data: LeagueScoreboardRow[];
  total: number;
}

export interface LeaguePowerRankingRow {
  team_id: number;
  team_name: string;
  rank: number;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
}

export interface LeaguePowerRankingResponse {
  data: LeaguePowerRankingRow[];
  total: number;
}

export interface LeagueNewsItem {
  id: number;
  team_id: number;
  team_name: string | null;
  transaction_type: string;
  headline: string;
  detail: string | null;
  created_at: string;
}

export interface LeagueNewsResponse {
  data: LeagueNewsItem[];
  total: number;
  limit: number;
}

export interface LeagueRosterPlayer {
  id: number;
  league_id?: number | null;
  team_id?: number;
  fantasy_team_id: number;
  fantasy_team_name: string;
  player_id: number | null;
  player_name: string;
  player_school?: string | null;
  player_position?: string | null;
  school?: string | null;
  position?: string | null;
  slot?: string;
  roster_slot?: string | null;
  status?: string;
  acquisition_type?: string;
  draft_pick_id?: number | null;
  is_starter?: boolean;
  is_ir?: boolean;
  opponent: string | null;
  projected_points?: number | null;
  floor?: number | null;
  ceiling?: number | null;
  boom_prob?: number;
  bust_prob?: number;
  weekly_projected_fantasy_points?: number | null;
}

export interface LeagueRosterTabResponse {
  league_id: number;
  season?: number;
  fantasy_team_id: number | null;
  fantasy_team_name: string | null;
  owned_team?: LeagueWorkspaceTeam | null;
  week: number;
  roster?: LeagueRosterPlayer[];
  roster_slot_limits?: Record<string, number>;
  ir_slots?: number;
  message?: string | null;
  data: LeagueRosterPlayer[];
}

export interface LeagueMatchupTeam {
  id?: number;
  name?: string;
  fantasy_team_id: number;
  fantasy_team_name: string;
  record: string;
  projected_points?: number;
  projected_total: number;
  win_probability: number;
  roster: LeagueRosterPlayer[];
}

export interface LeagueMatchupTabResponse {
  league_id: number;
  season?: number;
  matchup_id: number | null;
  week: number;
  status: string | null;
  my_team?: LeagueMatchupTeam | null;
  user_team: LeagueMatchupTeam | null;
  opponent_team: LeagueMatchupTeam | null;
  my_roster?: LeagueRosterPlayer[];
  opponent_roster?: LeagueRosterPlayer[];
  projection_source?: string;
  message?: string | null;
}

export interface LeagueScheduleRow {
  matchup_id: number;
  week: number;
  home_team_id: number;
  home_team_name: string;
  away_team_id: number;
  away_team_name: string;
  home_projected_total: number;
  away_projected_total: number;
  home_win_probability: number;
  away_win_probability: number;
}

export interface LeagueMemberSettings {
  id: number;
  user_id: number;
  role: string;
  joined_at: string;
}

export interface LeagueWaiverPlayer {
  id: number;
  name: string;
  school: string | null;
  position: string | null;
  weekly_projected_fantasy_points: number;
}

export interface LeagueWaiverClaim {
  id: number;
  league_id: number;
  fantasy_team_id: number;
  add_player_id: number;
  add_player_name: string;
  drop_player_id: number | null;
  drop_player_name: string | null;
  priority: number | null;
  status: string;
  created_at: string;
}

export interface LeagueWaiverTabResponse {
  league_id: number;
  fantasy_team_id: number | null;
  available_players: LeagueWaiverPlayer[];
  claims: LeagueWaiverClaim[];
  total_available: number;
}

export interface LeagueSettingsTabResponse {
  league_id: number;
  league_name: string;
  league_status?: string | null;
  draft_status?: string | null;
  league_info: Record<string, string | number | boolean | null>;
  members: LeagueMemberSettings[];
  scoring_settings: Record<string, number | string | boolean>;
  roster_settings: Record<string, number>;
  waiver_rules: Record<string, string | number | boolean>;
  standings: Array<Record<string, string | number>>;
  schedule: LeagueScheduleRow[];
  rosters: LeagueRosterPlayer[];
  draft_results: Array<Record<string, string | number | null>>;
  commissioner_controls: string[];
}
