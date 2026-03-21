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

export interface LeagueListItem {
  id: number;
  name: string;
  platform: string;
  scoring_type: string;
  created_at: string;
  updated_at: string;
}

export interface LeagueListResponse {
  data: LeagueListItem[];
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
  player_id: number;
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
