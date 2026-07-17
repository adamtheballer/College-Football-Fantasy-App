import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import type {
  ChatMessage,
  ChatMessagePageResponse,
  ChatReadReceipt,
  ChatThread,
  ChatThreadListResponse,
  ChatUnreadSummaryResponse,
} from "@/types/chat";

const isValidLeagueId = (leagueId?: number) =>
  typeof leagueId === "number" && Number.isInteger(leagueId) && leagueId > 0;

export const chatMessagesQueryKey = (leagueId?: number, threadId?: number) =>
  ["chat", "league", leagueId, "thread", threadId, "messages", "latest", "none"] as const;

export const chatThreadsQueryKey = (leagueId?: number) =>
  ["chat", "league", leagueId, "threads"] as const;

const isDocumentVisible = () =>
  typeof document === "undefined" || document.visibilityState === "visible";

const shouldRetryChatQuery = (failureCount: number, error: unknown) => {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return false;
  return failureCount < 3;
};

export function useLeagueChatThreads(leagueId?: number, enabled = true) {
  return useQuery({
    queryKey: chatThreadsQueryKey(leagueId),
    enabled: enabled && isValidLeagueId(leagueId),
    staleTime: 5_000,
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
    queryFn: () => apiGet<ChatThreadListResponse>(`/leagues/${leagueId}/chats`),
  });
}

export function useChatMessages(
  leagueId?: number,
  threadId?: number,
  beforeMessageId?: number,
  afterMessageId?: number,
  enabled = true,
) {
  return useQuery({
    queryKey: ["chat", "league", leagueId, "thread", threadId, "messages", beforeMessageId ?? "latest", afterMessageId ?? "none"],
    enabled: enabled && isValidLeagueId(leagueId) && typeof threadId === "number" && threadId > 0,
    staleTime: 3_000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
    queryFn: () =>
      apiGet<ChatMessagePageResponse>(`/leagues/${leagueId}/chats/${threadId}/messages`, {
        before_message_id: beforeMessageId,
        after_message_id: afterMessageId,
        limit: 50,
      }),
  });
}

export function useChatMessageUpdates(
  leagueId?: number,
  threadId?: number,
  afterMessageId = 0,
  enabled = true,
) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["chat", "league", leagueId, "thread", threadId, "message-updates", afterMessageId],
    enabled: enabled && isValidLeagueId(leagueId) && typeof threadId === "number" && threadId > 0,
    staleTime: 0,
    refetchInterval: () => isDocumentVisible() ? 5_000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: shouldRetryChatQuery,
    queryFn: () =>
      apiGet<ChatMessagePageResponse>(`/leagues/${leagueId}/chats/${threadId}/messages`, {
        after_message_id: afterMessageId,
        limit: 100,
      }),
  });

  useEffect(() => {
    if (!query.data?.data.length) return;
    const messagesKey = chatMessagesQueryKey(leagueId, threadId);
    queryClient.setQueryData<ChatMessagePageResponse>(messagesKey, (current) => {
      const page = current ?? { data: [], next_before_message_id: null, next_after_message_id: null };
      const byMessageId = new Map(page.data.map((message) => [message.id, message]));
      query.data.data.forEach((message) => byMessageId.set(message.id, message));
      return {
        ...page,
        data: [...byMessageId.values()].sort((left, right) => left.id - right.id),
      };
    });
    queryClient.invalidateQueries({ queryKey: ["chat", "league", leagueId, "threads"] });
    queryClient.invalidateQueries({ queryKey: ["chat", "unread-summary"] });
  }, [leagueId, query.data, queryClient, threadId]);

  return query;
}

export function useSendChatMessage(leagueId?: number, threadId?: number) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  return useMutation({
    mutationFn: (payload: { body: string; client_message_id: string; reply_to_message_id?: number }) =>
      apiPost<ChatMessage>(`/leagues/${leagueId}/chats/${threadId}/messages`, payload),
    onMutate: async (payload) => {
      const messagesKey = chatMessagesQueryKey(leagueId, threadId);
      await queryClient.cancelQueries({ queryKey: messagesKey });
      const previousMessages = queryClient.getQueryData<ChatMessagePageResponse>(messagesKey);
      const optimisticMessage: ChatMessage = {
        id: -Date.now(),
        thread_id: threadId ?? 0,
        league_id: leagueId ?? 0,
        sender_user_id: user?.id ?? null,
        message_type: "user",
        body: payload.body,
        metadata: {},
        client_message_id: payload.client_message_id,
        reply_to_message_id: payload.reply_to_message_id ?? null,
        edited_at: null,
        deleted_at: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        sender_display_name: user?.firstName ?? null,
        sender_fantasy_team_name: null,
        reply_to_message: null,
        delivery_status: "sending",
      };
      queryClient.setQueryData<ChatMessagePageResponse>(messagesKey, (current) => {
        const page = current ?? { data: [], next_before_message_id: null, next_after_message_id: null };
        const alreadyPresent = page.data.some((message) => message.client_message_id === payload.client_message_id);
        return {
          ...page,
          data: alreadyPresent
            ? page.data.map((message) => message.client_message_id === payload.client_message_id ? optimisticMessage : message)
            : [...page.data, optimisticMessage],
        };
      });
      return { previousMessages };
    },
    onError: (_error, payload) => {
      const messagesKey = chatMessagesQueryKey(leagueId, threadId);
      queryClient.setQueryData<ChatMessagePageResponse>(messagesKey, (current) => current ? {
        ...current,
        data: current.data.map((message) => message.client_message_id === payload.client_message_id
          ? { ...message, delivery_status: "failed" }
          : message),
      } : current);
    },
    onSuccess: (message) => {
      const messagesKey = chatMessagesQueryKey(leagueId, threadId);
      queryClient.setQueryData<ChatMessagePageResponse>(messagesKey, (current) => current ? {
        ...current,
        data: current.data.some((item) => item.client_message_id === message.client_message_id)
          ? current.data.map((item) => item.client_message_id === message.client_message_id ? message : item)
          : [...current.data, message],
      } : current);
      queryClient.invalidateQueries({ queryKey: ["chat", "league", leagueId, "threads"] });
      queryClient.invalidateQueries({ queryKey: ["chat", "unread-summary"] });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["chat", "league", leagueId, "thread", threadId, "messages"] });
    },
  });
}

export function useMarkChatThreadRead(leagueId?: number, threadId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lastReadMessageId?: number) =>
      apiPost<ChatReadReceipt>(`/leagues/${leagueId}/chats/${threadId}/read`, {
        last_read_message_id: lastReadMessageId,
      }),
    onMutate: async () => {
      const threadQueryKey = ["chat", "league", leagueId, "threads"] as const;
      const summaryQueryKey = ["chat", "unread-summary"] as const;
      await Promise.all([
        queryClient.cancelQueries({ queryKey: threadQueryKey }),
        queryClient.cancelQueries({ queryKey: summaryQueryKey }),
      ]);
      const previousThreads = queryClient.getQueryData<ChatThreadListResponse>(threadQueryKey);
      const previousSummary = queryClient.getQueryData<ChatUnreadSummaryResponse>(summaryQueryKey);
      const threadUnread = previousThreads?.data.find((thread) => thread.id === threadId)?.unread_count ?? 0;

      if (previousThreads && typeof threadId === "number") {
        queryClient.setQueryData<ChatThreadListResponse>(threadQueryKey, {
          ...previousThreads,
          data: previousThreads.data.map((thread) =>
            thread.id === threadId ? { ...thread, unread_count: 0 } : thread,
          ),
        });
      }
      if (previousSummary && typeof leagueId === "number" && threadUnread > 0) {
        const nextLeagueUnread = Math.max(
          0,
          (previousSummary.leagues.find((league) => league.league_id === leagueId)?.unread ?? 0) - threadUnread,
        );
        queryClient.setQueryData<ChatUnreadSummaryResponse>(summaryQueryKey, {
          total_unread: Math.max(0, previousSummary.total_unread - threadUnread),
          leagues: previousSummary.leagues
            .map((league) => league.league_id === leagueId ? { ...league, unread: nextLeagueUnread } : league)
            .filter((league) => league.unread > 0),
        });
      }
      return { previousThreads, previousSummary };
    },
    onError: (_error, _lastReadMessageId, context) => {
      const threadQueryKey = ["chat", "league", leagueId, "threads"] as const;
      const summaryQueryKey = ["chat", "unread-summary"] as const;
      if (context?.previousThreads) queryClient.setQueryData(threadQueryKey, context.previousThreads);
      if (context?.previousSummary) queryClient.setQueryData(summaryQueryKey, context.previousSummary);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["chat", "league", leagueId, "threads"] });
      queryClient.invalidateQueries({ queryKey: ["chat", "unread-summary"] });
    },
  });
}

export function useCreateDirectChatThread(leagueId?: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (recipientUserId: number) => apiPost<ChatThread>(`/leagues/${leagueId}/chats/direct`, { recipient_user_id: recipientUserId }),
    onSuccess: (thread) => {
      const threadsKey = chatThreadsQueryKey(leagueId);
      queryClient.setQueryData<ChatThreadListResponse>(threadsKey, (current) => {
        if (!current || current.data.some((existing) => existing.id === thread.id)) return current;
        return { ...current, data: [...current.data, thread], total: current.total + 1 };
      });
      queryClient.invalidateQueries({ queryKey: threadsKey });
    },
  });
}

export function useChatUnreadSummary(enabled = true, chatsPageOpen = false) {
  return useQuery({
    queryKey: ["chat", "unread-summary"],
    enabled,
    staleTime: 5_000,
    refetchInterval: () => isDocumentVisible() ? (chatsPageOpen ? 5_000 : 10_000) : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    placeholderData: (previousData) => previousData,
    retry: shouldRetryChatQuery,
    queryFn: () => apiGet<ChatUnreadSummaryResponse>("/chats/unread-summary"),
  });
}
