export interface DraftRoomTeam {
  id: number;
  name: string;
  owner_user_id: number | null;
  owner_name: string | null;
}

export interface DraftRoomPick {
  id: number;
  overall_pick: number;
  round_number: number;
  round_pick: number;
  team_id: number;
  team_name: string;
  player_id: number;
  player_name: string;
  player_position: string;
  player_school: string;
  made_by_user_id: number | null;
  created_at: string;
}

export interface DraftRoom {
  league_id: number;
  draft_id: number;
  status: string;
  pick_timer_seconds: number;
  roster_slots: Record<string, number>;
  teams: DraftRoomTeam[];
  picks: DraftRoomPick[];
  current_pick: number;
  current_round: number;
  current_round_pick: number;
  current_team_id: number | null;
  current_team_name: string | null;
  user_team_id: number | null;
  can_make_pick: boolean;
}
