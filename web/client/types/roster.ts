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

export interface Transaction {
  id: number;
  league_id: number;
  team_id: number;
  transaction_type: string;
  player_id: number | null;
  related_player_id: number | null;
  created_by_user_id: number | null;
  reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface AddDropResponse {
  roster: RosterEntry[];
  transaction: Transaction;
}
