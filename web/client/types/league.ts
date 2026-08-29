export interface LeagueSettings {
  id: number;
  league_id: number;
  scoring_json: Record<string, number | string | boolean>;
  scoring_snapshot_json?: Record<string, number | string | boolean> | null;
  scoring_locked_at?: string | null;
  roster_slots_json: Record<string, number>;
  playoff_teams: number;
  waiver_type: string;
  waiver_period_hours: number;
  waiver_processing_weekday?: number;
  waiver_processing_hour?: number;
  waiver_timezone?: string;
  waiver_process_day?: number;
  waiver_process_hour?: number;
  next_waiver_run_at?: string | null;
  faab_starting_budget?: number;
  allow_zero_faab_bids?: boolean;
  reveal_all_waiver_bids?: boolean;
  faab_budget?: number;
  allow_zero_dollar_bids?: boolean;
  waiver_tiebreaker?: string;
  initial_waiver_priority_method?: string;
  post_drop_waiver_hours?: number;
  waivers_enabled?: boolean;
  free_agent_mode?: string;
  trade_review_type: string;
  trade_deadline_week?: number | null;
  trade_deadline_at?: string | null;
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
  draft_order_mode: "random" | "custom";
  pick_timer_seconds: number;
  status: string;
}

export interface DraftOrderEntry {
  team_id: number;
  team_name: string;
  owner_user_id: number | null;
  owner_name: string | null;
  owner_avatar_url?: string | null;
  draft_position: number | null;
}

export interface DraftOrder {
  draft_order_mode: "random" | "custom";
  max_teams: number;
  is_complete: boolean;
  entries: DraftOrderEntry[];
}

export interface LeagueMember {
  id: number;
  user_id: number;
  role: string;
  joined_at: string;
  manager_name?: string | null;
  manager_avatar_url?: string | null;
}

export interface LeagueListCurrentUserSummary {
  team_name?: string | null;
  wins?: number | null;
  losses?: number | null;
  ties?: number | null;
  opponent_team_name?: string | null;
  matchup_week?: number | null;
  projected_points_for?: number | null;
  projected_points_against?: number | null;
  win_probability_for?: number | null;
  win_probability_against?: number | null;
  is_rivalry_matchup?: boolean;
}

export interface LeagueDetail {
  id: number;
  name: string;
  commissioner_user_id: number | null;
  commissioner_name?: string | null;
  commissioner_avatar_url?: string | null;
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
  draft_order: DraftOrder | null;
  members: LeagueMember[];
  current_user_summary?: LeagueListCurrentUserSummary | null;
}

export interface LeaguePreview {
  id: number;
  name: string;
  commissioner_name: string | null;
  commissioner_avatar_url?: string | null;
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
  win_probability_for?: number | null;
  win_probability_against?: number | null;
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
  home_owner_avatar_url?: string | null;
  home_score: number;
  away_team_id: number;
  away_team_name: string;
  away_owner_avatar_url?: string | null;
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
  id: number | null;
  league_id?: number | null;
  team_id?: number | null;
  fantasy_team_id: number | null;
  fantasy_team_name: string | null;
  player_id: number | null;
  player_name: string | null;
  player_school?: string | null;
  player_position?: string | null;
  school?: string | null;
  position?: string | null;
  slot?: string | null;
  slot_id?: string;
  slot_index?: number;
  display_label?: string;
  roster_slot?: string | null;
  injury_status?: "QUESTIONABLE" | "OUT" | "IR" | string | null;
  status?: string;
  acquisition_type?: string;
  draft_pick_id?: number | null;
  is_starter?: boolean;
  is_ir?: boolean;
  opponent: string | null;
  game_location?: "home" | "away" | "neutral" | "bye" | null;
  projected_points?: number | null;
  floor?: number | null;
  ceiling?: number | null;
  boom_prob?: number | null;
  bust_prob?: number | null;
  weekly_projected_fantasy_points: number | null;
  projection_status?: string | null;
  live_points?: number | null;
  live_scoring_status?: string | null;
  live_scoring_updated_at?: string | null;
  current_fantasy_points?: number | null;
  pregame_projected_points?: number | null;
  live_projected_final_points?: number | null;
  live_projection_status?: "PRE" | "LIVE" | "FINAL" | "STALE" | "OUT" | string | null;
  live_projection_model_version?: string | null;
  projection_updated_at?: string | null;
  provider_snapshot_at?: string | null;
  game_period?: number | null;
  game_clock?: string | null;
  game_score?: string | null;
  game_down_distance?: string | null;
  game_is_halftime?: boolean;
  game_progress?: number | null;
  live_projection_fallback_reason?: string | null;
  live_game_state?: "scheduled" | "live" | "final" | "unavailable" | string | null;
  team_has_possession?: boolean;
  team_in_red_zone?: boolean;
  game_start_at?: string | null;
  is_locked?: boolean;
  is_placeholder?: boolean;
}

export interface LeagueRosterTeam {
  team: {
    id: number;
    name: string;
    owner_user_id: number | null;
    owner_name?: string | null;
    owner_avatar_url?: string | null;
    record: string | null;
  };
  roster: LeagueRosterPlayer[];
}

export interface LeagueRosterTabResponse {
  league_id: number;
  season?: number;
  fantasy_team_id: number | null;
  fantasy_team_name: string | null;
  owned_team?: LeagueWorkspaceTeam | null;
  week: number;
  roster?: LeagueRosterPlayer[];
  slots?: LeagueRosterPlayer[];
  roster_slot_limits?: Record<string, number>;
  ir_slots?: number;
  message?: string | null;
  data: LeagueRosterPlayer[];
  team_rosters?: LeagueRosterTeam[];
}

export interface LeagueMatchupTeam {
  id?: number;
  name?: string;
  fantasy_team_id: number;
  fantasy_team_name: string;
  manager_name?: string | null;
  owner_avatar_url?: string | null;
  record: string;
  projected_points?: number | null;
  projected_total?: number | null;
  current_points?: number | null;
  pregame_projected_total?: number | null;
  live_projected_total?: number | null;
  win_probability?: number | null;
  roster: LeagueRosterPlayer[];
}

export interface LiveScoringFreshness {
  provider?: string | null;
  state: "fresh" | "delayed" | "stale" | "unavailable" | string;
  provider_as_of?: string | null;
  last_successful_update_at?: string | null;
  data_age_seconds?: number | null;
  relevant_game_count: number;
}

export interface LeagueMatchupTabResponse {
  league_id: number;
  season?: number;
  matchup_id: number | null;
  week: number;
  week_started?: boolean;
  status: string | null;
  my_team?: LeagueMatchupTeam | null;
  user_team: LeagueMatchupTeam | null;
  opponent_team: LeagueMatchupTeam | null;
  my_roster?: LeagueRosterPlayer[];
  opponent_roster?: LeagueRosterPlayer[];
  projection_source?: string;
  live_scoring_freshness?: LiveScoringFreshness | null;
  projection_updated_at?: string | null;
  provider_snapshot_at?: string | null;
  next_refresh_at?: string | null;
  message?: string | null;
  rivalry?: RivalryMatchup | null;
  postseason?: {
    bracket_id: number;
    matchup_type: string;
    bracket_path?: string | null;
    status: string;
  } | null;
}

export interface PostseasonTeam {
  team_id: number;
  team_name: string;
  manager_name?: string | null;
  manager_avatar_url?: string | null;
}

export interface PostseasonSeed extends PostseasonTeam {
  seed: number;
  regular_season_rank: number;
  wins: number;
  losses: number;
  ties: number;
  points_for: number;
  tiebreaker_explanation?: string | null;
}

export interface PostseasonMatchup {
  id: number;
  round_number: number;
  week: number;
  matchup_type: string;
  bracket_path?: string | null;
  status: string;
  fantasy_matchup_id?: number | null;
  team_a?: PostseasonTeam | null;
  team_b?: PostseasonTeam | null;
  team_a_seed?: number | null;
  team_b_seed?: number | null;
  team_a_score?: number | null;
  team_b_score?: number | null;
  winner_team_id?: number | null;
  loser_team_id?: number | null;
  tiebreaker_used?: string | null;
}

export interface PostseasonRound {
  round_number: number;
  week: number;
  status: string;
  matchups: PostseasonMatchup[];
}

export interface PostseasonFinalStanding extends PostseasonTeam {
  final_place: number;
  regular_season_rank: number;
  playoff_seed?: number | null;
  postseason_result: string;
}

export interface LeaguePostseasonResponse {
  league_id: number;
  season: number;
  status: string;
  is_preview: boolean;
  playoff_teams: number;
  regular_season_end_week: number;
  playoff_start_week: number;
  championship_week: number;
  max_rounds: number;
  calendar_policy_version: string;
  calendar_source_identity: string;
  calendar_source_revision: string;
  calendar_source_sha256: string;
  calendar_source_format_version: string;
  format_version: string;
  tiebreaker_policy: string;
  format_summary: string;
  seeds_locked_at?: string | null;
  champion?: PostseasonTeam | null;
  review_reason?: string | null;
  seeds: PostseasonSeed[];
  playoff_cut_line?: number | null;
  rounds?: PostseasonRound[];
  final_standings?: PostseasonFinalStanding[];
}

export interface RivalrySeries { wins: number; losses: number; ties: number; last_meeting?: string | null; }
export interface RivalryMatchup { is_rivalry_matchup: boolean; rivalry_id?: number | null; opponent_team_id?: number | null; opponent_team_name?: string | null; series?: RivalrySeries | null; }
export interface RivalryCandidate { team_id: number; team_name: string; manager_user_id: number; manager_name: string; manager_avatar_url?: string | null; }
export interface RivalryInvite { id: number; league_id: number; sender_team_id: number; sender_team_name: string; sender_manager_name: string; sender_manager_avatar_url?: string | null; recipient_team_id: number; recipient_team_name: string; recipient_manager_name: string; recipient_manager_avatar_url?: string | null; status: string; expires_at: string; created_at: string; }
export interface LeagueRivalryView { eligible: boolean; rivalry?: { id: number; opponent_team_id: number; opponent_team_name: string; opponent_manager_name: string; opponent_manager_avatar_url?: string | null; accepted_at: string; status: string } | null; outgoing_invite?: RivalryInvite | null; incoming_invites: RivalryInvite[]; candidates: RivalryCandidate[]; }

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
  weekly_projected_fantasy_points: number | null;
  projection_status: string;
  availability_state: string;
  available_at: string | null;
}

export interface LeagueWaiverClaim {
  id: number;
  league_id: number;
  team_id: number;
  fantasy_team_id: number;
  add_player_id: number;
  add_player_name: string;
  drop_roster_entry_id: number | null;
  drop_player_id: number | null;
  drop_player_name: string | null;
  priority: number | null;
  faab_bid: number;
  status: string;
  failure_reason: string | null;
  failure_code: string | null;
  season: number;
  processing_week: number;
  processing_window_id: string;
  waiver_period_id: number | null;
  processing_run_id: number | null;
  preference_order: number;
  winning_bid: number | null;
  prior_priority: number | null;
  resulting_priority: number | null;
  process_after: string | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
}

export interface LeagueWaiverPeriod {
  id: number;
  season: number;
  week: number;
  window_key: string;
  opens_at: string;
  closes_at: string;
  processes_at: string;
  status: string;
}

export interface LeagueWaiverDropCandidate {
  roster_entry_id: number;
  player_id: number;
  player_name: string;
  position: string | null;
  school: string | null;
  slot: string;
}

export interface LeagueWaiverTabResponse {
  league_id: number;
  fantasy_team_id: number | null;
  waiver_priority: number | null;
  faab_remaining: number | null;
  available_players: LeagueWaiverPlayer[];
  claims: LeagueWaiverClaim[];
  current_period: LeagueWaiverPeriod | null;
  results_period: LeagueWaiverPeriod | null;
  results: LeagueWaiverClaim[];
  roster: LeagueWaiverDropCandidate[];
  waiver_rules: Record<string, string | number | boolean>;
  total_available: number;
  message: string | null;
}

export interface LeagueSettingsTabResponse {
  league_id: number;
  league_name: string;
  league_info: Record<string, string | number | boolean | null>;
  postseason_calendar?: {
    regular_season_start_week: number;
    regular_season_end_week: number;
    playoff_start_week: number;
    championship_week: number;
    playoff_teams: number;
    max_rounds: number;
    calendar_policy_version: string;
    source_identity: string;
    source_revision: string;
    source_sha256: string;
    source_format_version: string;
  } | null;
  invite?: {
    code: string;
    link: string;
    draft_status?: string | null;
    visible_until_draft_complete: boolean;
  } | null;
  members: LeagueMemberSettings[];
  teams?: Array<{
    id: number;
    league_id: number;
    name: string;
    owner_user_id: number | null;
  }>;
  scoring_settings: Record<string, number | string | boolean>;
  roster_settings: Record<string, number>;
  waiver_rules: Record<string, string | number | boolean>;
  standings: Array<Record<string, string | number>>;
  schedule: LeagueScheduleRow[];
  rosters: LeagueRosterPlayer[];
  trade_history: Array<{
    id: number;
    status: string;
    proposing_party: {
      team_id: number;
      team_name: string;
      manager_name: string | null;
      manager_avatar_url?: string | null;
    };
    receiving_party: {
      team_id: number;
      team_name: string;
      manager_name: string | null;
      manager_avatar_url?: string | null;
    };
    proposing_team_sends: Array<{
      player_id: number | null;
      name: string;
      position: string | null;
      school: string | null;
    }>;
    receiving_team_sends: Array<{
      player_id: number | null;
      name: string;
      position: string | null;
      school: string | null;
    }>;
    created_at: string;
    accepted_at: string | null;
    processed_at: string | null;
  }>;
  draft_results: Array<Record<string, string | number | null>>;
  commissioner_controls: string[];
}
