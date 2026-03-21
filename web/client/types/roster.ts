export interface RosterPlayer {
  id: number;
  name: string;
  position: string;
  school: string;
}

export interface RosterEntry {
  id: number;
  team_id: number;
  player_id: number;
  slot: string;
  status: string;
  created_at: string;
  updated_at: string;
  player: RosterPlayer;
}

export interface RosterEntryListResponse {
  data: RosterEntry[];
  total: number;
  limit: number;
  offset: number;
}
