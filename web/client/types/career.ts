export type CareerRecord = {
  wins: number;
  losses: number;
  ties: number;
  win_pct: number;
};

export type CareerProfile = {
  user_id: number;
  display_name: string;
  username?: string | null;
  member_since: string;
  record: CareerRecord;
  leagues: Record<string, number>;
  drafts: Record<string, number>;
  trades: Record<string, number>;
  waivers: Record<string, number>;
  postseason: Record<string, number>;
  matchups: Record<string, number>;
  scoring: Record<string, number | null>;
  streaks: Record<string, number>;
  rivalry: Record<string, number>;
};

export type CareerEvent = {
  id: number;
  event_type: string;
  title: string;
  season?: number | null;
  week?: number | null;
  league_id?: number | null;
  occurred_at: string;
  metadata: Record<string, unknown>;
};

export type CareerEventsResponse = { data: CareerEvent[]; total: number };

export type CareerLeague = {
  league_id: number;
  name: string;
  season: number;
  status: string;
  record: CareerRecord;
  points_for: number;
  final_place?: number | null;
  postseason_result?: string | null;
  rival_team_name?: string | null;
  rival_record?: CareerRecord | null;
};

export type CareerTrophy = {
  key: string;
  title: string;
  season?: number | null;
  league_id?: number | null;
  subtitle?: string | null;
};

export type RivalCandidate = { team_id: number; team_name: string; manager_name: string };

export type LeagueRivalry = {
  league_id: number;
  season: number;
  team_id: number;
  rival_team_id?: number | null;
  rival_team_name?: string | null;
  rival_manager_name?: string | null;
  selected_at?: string | null;
  changed_at?: string | null;
  can_change: boolean;
  candidates: RivalCandidate[];
};

export type RivalryMatchup = {
  matchup_id: number;
  is_rivalry_matchup: boolean;
  is_championship: boolean;
  user_team_name: string;
  rival_team_name?: string | null;
  series: CareerRecord;
  last_meeting?: { week: number; own_score: number; rival_score: number; result: string } | null;
};
