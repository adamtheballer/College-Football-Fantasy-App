export interface Team {
  id: number;
  league_id: number;
  name: string;
  owner_name: string | null;
  owner_user_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface TeamListResponse {
  data: Team[];
  total: number;
  limit: number;
  offset: number;
}
