export type ChatThreadType = "league" | "direct";

export interface ChatParticipant {
  user_id: number;
  joined_at: string;
  display_name: string;
  fantasy_team_name: string | null;
}

export interface ChatThread {
  id: number;
  league_id: number;
  thread_type: ChatThreadType;
  title: string | null;
  created_by_user_id: number | null;
  direct_user_low_id: number | null;
  direct_user_high_id: number | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  participants: ChatParticipant[];
  other_participant: ChatParticipant | null;
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count: number;
}

export interface ChatThreadListResponse {
  data: ChatThread[];
  total: number;
}

export interface ChatMessage {
  id: number;
  thread_id: number;
  league_id: number;
  sender_user_id: number | null;
  message_type: "user" | "system" | "trade_finalized" | "trade_processed" | "waiver" | "draft" | "commissioner";
  body: string | null;
  metadata: Record<string, unknown>;
  client_message_id: string | null;
  reply_to_message_id: number | null;
  edited_at: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  sender_display_name: string | null;
  sender_fantasy_team_name: string | null;
  reply_to_message: {
    id: number;
    sender_display_name: string | null;
    body: string | null;
    message_type: string;
    created_at: string;
  } | null;
  delivery_status?: "sending" | "failed";
}

export interface ChatMessagePageResponse {
  data: ChatMessage[];
  next_before_message_id: number | null;
  next_after_message_id: number | null;
}

export interface ChatReadReceipt {
  thread_id: number;
  league_id: number;
  unread_count: number;
  total_unread: number;
}

export interface ChatUnreadSummaryResponse {
  total_unread: number;
  leagues: Array<{
    league_id: number;
    unread: number;
  }>;
}
