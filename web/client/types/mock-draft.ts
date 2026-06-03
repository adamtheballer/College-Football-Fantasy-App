import type { DraftEventEnvelope, DraftPositionEligibility, DraftQueueItem, DraftRoomPick, DraftRoomTeam, DraftRosterTeam } from "./draft";

export interface MockDraftSeat {
  id: number;
  seat_number: number;
  name: string;
  owner_name: string | null;
  owner_user_id: number | null;
  is_cpu: boolean;
  lobby_joined: boolean;
  lobby_connected: boolean;
  lobby_ready: boolean;
}

export interface MockDraftSession {
  id: number;
  name: string;
  invite_code: string;
  mode: "public_multiplayer" | "single_player";
  status: string;
  manager_count: number;
  pick_timer_seconds: number;
  draft_type: string;
  commissioner_user_id: number;
  roster_slots: Record<string, number>;
  scoring_json: Record<string, unknown>;
  seats: MockDraftSeat[];
  joined_count: number;
  connected_count: number;
  ready_count: number;
  user_seat_id: number | null;
  seconds_remaining: number | null;
  can_enter_room: boolean;
  created_at: string;
  updated_at: string;
}

export interface MockDraftPreview {
  id: number;
  name: string;
  invite_code: string;
  mode: "public_multiplayer" | "single_player";
  status: string;
  manager_count: number;
  joined_count: number;
  pick_timer_seconds: number;
}

export interface MockDraftRoom {
  draft_room_id: number;
  mock_draft_id: number;
  mode: "public_multiplayer" | "single_player";
  status: string;
  draft_status: "waiting" | "active" | "paused" | "complete";
  pick_timer_seconds: number;
  total_rounds: number;
  total_picks: number;
  roster_slots: Record<string, number>;
  position_eligibility: Record<string, DraftPositionEligibility>;
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

export interface MockDraftRoomSnapshot {
  draft_room: MockDraftRoom;
  events: DraftEventEnvelope[];
  latest_seq: number;
}

export interface MockDraftQueue {
  session_id: number;
  seat_id: number;
  count: number;
  data: DraftQueueItem[];
}
