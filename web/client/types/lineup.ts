export interface LineupEntry {
  id: number;
  lineup_id: number;
  roster_entry_id: number | null;
  player_id: number;
  player_name?: string | null;
  player_position?: string | null;
  player_school?: string | null;
  slot: string;
  is_starter: boolean;
}

export interface Lineup {
  id: number;
  league_id: number;
  team_id: number;
  season: number;
  week: number;
  status: string;
  locked_at?: string | null;
  entries: LineupEntry[];
}

export interface LineupAssignment {
  roster_entry_id?: number | null;
  player_id: number;
  slot: string;
  is_starter: boolean;
}

export interface LineupUpdateRequest {
  assignments: LineupAssignment[];
}

export interface LineupUpdateResponse {
  data: Lineup;
}
