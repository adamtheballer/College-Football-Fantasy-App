// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const state = vi.hoisted(() => ({ apiPost: vi.fn() }));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: 7, firstName: "Alex", email: "alex@example.com", isAdmin: false } }),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiPost: state.apiPost,
}));

import { chatMessagesQueryKey, chatThreadsQueryKey, useCreateDirectChatThread, useSendChatMessage } from "./use-chat";

const wrapperFor = (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;

describe("useSendChatMessage", () => {
  it("reconciles an optimistic message by client_message_id without a duplicate", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const key = chatMessagesQueryKey(3, 14);
    queryClient.setQueryData(key, { data: [], next_before_message_id: null, next_after_message_id: null });
    state.apiPost.mockResolvedValueOnce({
      id: 88,
      thread_id: 14,
      league_id: 3,
      sender_user_id: 7,
      message_type: "user",
      body: "Good luck",
      metadata: {},
      client_message_id: "browser-123",
      reply_to_message_id: null,
      edited_at: null,
      deleted_at: null,
      created_at: "2026-08-01T12:00:00Z",
      updated_at: "2026-08-01T12:00:00Z",
      sender_display_name: "Alex",
      sender_fantasy_team_name: null,
      reply_to_message: null,
    });
    const { result } = renderHook(() => useSendChatMessage(3, 14), { wrapper: wrapperFor(queryClient) });

    await act(async () => {
      await result.current.mutateAsync({ body: "Good luck", client_message_id: "browser-123" });
    });

    await waitFor(() => {
      const page = queryClient.getQueryData<{ data: Array<{ id: number; client_message_id: string; delivery_status?: string }> }>(key);
      expect(page?.data).toEqual([expect.objectContaining({ id: 88, client_message_id: "browser-123" })]);
    });
    expect(state.apiPost).toHaveBeenCalledWith(
      "/leagues/3/chats/14/messages",
      { body: "Good luck", client_message_id: "browser-123" },
    );
  });

  it("leaves a failed optimistic message available for retry", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const key = chatMessagesQueryKey(3, 14);
    queryClient.setQueryData(key, { data: [], next_before_message_id: null, next_after_message_id: null });
    state.apiPost.mockRejectedValueOnce(new Error("network unavailable"));
    const { result } = renderHook(() => useSendChatMessage(3, 14), { wrapper: wrapperFor(queryClient) });

    await act(async () => {
      await expect(result.current.mutateAsync({ body: "Retry me", client_message_id: "browser-124" })).rejects.toThrow("network unavailable");
    });

    const page = queryClient.getQueryData<{ data: Array<{ body: string; delivery_status?: string }> }>(key);
    expect(page?.data).toEqual([expect.objectContaining({ body: "Retry me", delivery_status: "failed" })]);
  });
});

describe("useCreateDirectChatThread", () => {
  it("adds the server-created direct thread to the cache before refetching", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const key = chatThreadsQueryKey(3);
    queryClient.setQueryData(key, { data: [{ id: 9, thread_type: "league" }], total: 1 });
    state.apiPost.mockResolvedValueOnce({ id: 14, thread_type: "direct", league_id: 3 });
    const { result } = renderHook(() => useCreateDirectChatThread(3), { wrapper: wrapperFor(queryClient) });

    await act(async () => {
      await result.current.mutateAsync(12);
    });

    expect(queryClient.getQueryData<{ data: Array<{ id: number }>; total: number }>(key)).toEqual({
      data: [{ id: 9, thread_type: "league" }, { id: 14, thread_type: "direct", league_id: 3 }],
      total: 2,
    });
  });
});
