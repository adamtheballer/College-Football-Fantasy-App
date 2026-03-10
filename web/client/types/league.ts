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
