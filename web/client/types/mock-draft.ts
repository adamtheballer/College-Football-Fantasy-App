import type { DraftEventEnvelope, DraftPositionEligibility, DraftQueueItem, DraftRoomPick, DraftRoomTeam, DraftRosterTeam } from "./draft";

export type StandaloneMockDraftMode = "public_multiplayer" | "single_player";

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

export interface MockDraftEmailSummaryResponse {
  sent: boolean;
  emails: string[];
}

export interface StandaloneMockDraftParticipant {
  id: number;
  mock_draft_id: number;
  user_id: number | null;
  display_name: string;
  team_name: string;
  participant_type: "human" | "bot";
  seat_number: number;
  draft_position: number | null;
  is_host: boolean;
  is_ready: boolean;
  joined_at: string;
  left_at: string | null;
  last_seen_at: string | null;
  connection_status: string;
  auto_pick_count: number;
}

export interface StandaloneMockDraftSession {
  id: number;
  name: string;
  mode: StandaloneMockDraftMode;
  invite_code: string | null;
  status: "scheduled" | "lobby" | "intermission" | "live" | "paused" | "completed" | "cancelled" | "expired" | "pending_deletion";
  team_count: number;
  round_count: number;
  draft_type: string;
  pick_timer_seconds: number;
  scheduled_start_at: string;
  intermission_started_at: string | null;
  intermission_ends_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  player_pool: string;
  scoring_type: string;
  bot_difficulty: string;
  draft_order_locked: boolean;
  should_preserve_history: boolean;
}

export interface StandaloneMockDraftCreateRequest {
  name: string;
  mode: StandaloneMockDraftMode;
  team_count: 4 | 6 | 8 | 10 | 12;
  round_count: number;
  pick_timer_seconds: 30 | 60 | 90 | 120;
  scheduled_start_at: string;
  player_pool: string;
  scoring_type: string;
  bot_difficulty: string;
}

export interface StandaloneMockDraftCreateResponse {
  mock_draft_id: number;
  id: number;
  mode: StandaloneMockDraftMode;
  invite_code: string | null;
  invite_link: string | null;
  join_url: string | null;
  lobby_url: string;
  status: string;
  scheduled_start_at: string;
}

export interface StandaloneMockDraftLobby {
  session: StandaloneMockDraftSession;
  participants: StandaloneMockDraftParticipant[];
  invite_code: string | null;
  invite_link: string | null;
  join_url: string | null;
  server_time: string;
  seconds_until_start: number;
  is_current_user_host: boolean;
  settings_locked: boolean;
  can_join: boolean;
  can_leave: boolean;
  can_edit_settings: boolean;
  can_start_now: boolean;
  message: string;
  id: number;
  name: string;
  status: string;
  team_count: number;
  manager_count: number;
  joined_count: number;
  can_enter_room: boolean;
  scheduled_start_at: string;
}

export interface StandaloneMockDraftPick {
  id: number;
  mock_draft_id: number;
  participant_id: number;
  participant_name: string;
  team_name: string;
  player_id: number;
  player_name: string;
  player_position: string;
  player_school: string;
  overall_pick: number;
  round_number: number;
  round_pick: number;
  pick_source: "human" | "bot" | "auto_timer" | "host_override" | "system";
  auto_pick_reason: string | null;
  made_by_user_id: number | null;
  created_at: string;
}

export interface StandaloneMockDraftRoster {
  participant_id: number;
  participant_name: string;
  team_name: string;
  picks: StandaloneMockDraftPick[];
}

export interface StandaloneMockDraftRoom {
  session: StandaloneMockDraftSession;
  server_time: string;
  participants: StandaloneMockDraftParticipant[];
  picks: StandaloneMockDraftPick[];
  rosters: StandaloneMockDraftRoster[];
  draft_order: number[];
  current_overall_pick: number;
  current_round: number;
  current_round_pick: number;
  current_participant_id: number | null;
  current_participant_name: string | null;
  current_participant_type: string | null;
  current_team_name: string | null;
  current_pick_started_at: string | null;
  current_pick_expires_at: string | null;
  seconds_remaining: number | null;
  total_picks: number;
  is_user_on_clock: boolean;
  is_complete: boolean;
  can_exit: boolean;
  email_history_available: boolean;
  should_show_email_prompt: boolean;
  available_player_count: number;
  mock_draft_id: number;
  status: string;
  pick_timer_seconds: number;
  total_rounds: number;
  current_pick: number;
  current_team_id: number | null;
  user_team_id: number | null;
  can_make_pick: boolean;
  phase_type: string | null;
}

export interface StandaloneMockDraftHistory {
  mock_draft_id: number;
  draft_name: string;
  completed_at: string | null;
  participants: StandaloneMockDraftParticipant[];
  draft_order: StandaloneMockDraftParticipant[];
  picks: StandaloneMockDraftPick[];
  picks_by_round: Array<{ round: number; picks: StandaloneMockDraftPick[] }>;
  rosters: StandaloneMockDraftRoster[];
  plain_text: string;
  html: string;
  pick_count: number;
}

export interface StandaloneMockDraftEmailResponse {
  sent: boolean;
  emails: string[];
  message: string;
  history: StandaloneMockDraftHistory | null;
}
