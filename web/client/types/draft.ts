export interface DraftRoomTeam {
  id: number;
  name: string;
  owner_user_id: number | null;
  owner_name: string | null;
  lobby_joined: boolean;
  lobby_connected: boolean;
  lobby_ready: boolean;
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

export interface DraftRosterPlayer {
  player_id: number;
  player_name: string;
  position: string;
  school: string;
  slot: string;
  projected_fantasy_points: number | null;
}

export interface DraftRosterTeam {
  team_id: number;
  team_name: string;
  total_projected_points: number;
  position_counts: Record<string, number>;
  slots: Record<string, DraftRosterPlayer[]>;
}

export interface DraftRoom {
  draft_room_id: number;
  league_id: number;
  draft_id: number;
  status: string;
  draft_status: "waiting" | "active" | "paused" | "complete";
  pick_timer_seconds: number;
  roster_slots: Record<string, number>;
  draft_order: number[];
  drafted_player_ids: number[];
  available_player_count: number;
  rosters_by_team: DraftRosterTeam[];
  lobby_ready_count: number;
  lobby_joined_count: number;
  lobby_connected_count: number;
  teams: DraftRoomTeam[];
  picks: DraftRoomPick[];
  current_pick: number;
  current_round: number;
  current_round_pick: number;
  current_team_id: number | null;
  current_team_name: string | null;
  current_pick_expires_at: string | null;
  seconds_remaining: number | null;
  phase_seconds_remaining: number | null;
  phase_type: "lobby_countdown" | "prestart_countdown" | "pick_clock" | "pick_transition" | "auto_picking" | null;
  pick_state: "WAITING_FOR_PICK" | "AUTO_PICKING" | "PICK_SUBMITTED";
  auto_pick_seconds_remaining: number | null;
  current_pick_timer_seconds: number;
  timer_started_at: string | null;
  timer_paused_at: string | null;
  timer_paused_total_seconds: number;
  server_state_seq: number;
  user_team_id: number | null;
  can_make_pick: boolean;
  created_at: string;
  updated_at: string;
}

export interface DraftEventEnvelope {
  event_id: string;
  event: string;
  event_type: string;
  league_id: number;
  entity_type: string;
  entity_id: number | null;
  seq: number;
  schema_version: number;
  at: string;
  payload: Record<string, unknown>;
}

export interface DraftRoomSnapshot {
  draft_room: DraftRoom;
  events: DraftEventEnvelope[];
  latest_seq: number;
}

export interface DraftQueueItem {
  id: number;
  priority: number;
  player_id: number;
  player_name: string;
  player_position: string;
  player_school: string;
  player_class: string | null;
  projected_fantasy_points: number | null;
  adp: number | null;
}

export interface DraftQueue {
  draft_id: number;
  league_id: number;
  team_id: number;
  count: number;
  data: DraftQueueItem[];
}
