import type { Player } from "./player";

export interface Watchlist {
  id: number;
  user_id: number;
  league_id: number | null;
  name: string;
  players: Player[];
  created_at: string;
  updated_at: string;
}

export interface WatchlistListResponse {
  data: Watchlist[];
  total: number;
}
