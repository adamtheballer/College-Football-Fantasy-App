// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage, ChatThread } from "@/types/chat";

const state = vi.hoisted(() => ({
  activeLeagueId: 1 as number | null,
  selectedLeagueId: 1,
  sendMutate: vi.fn(),
  directMutate: vi.fn(),
  readMutate: vi.fn(),
  setActiveLeagueId: vi.fn(),
  failedMessage: false,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: 1, firstName: "Avery", email: "avery@example.com", isAdmin: false } }),
}));

vi.mock("@/hooks/use-active-league", () => ({
  useActiveLeagueId: () => ({ activeLeagueId: state.activeLeagueId, setActiveLeagueId: state.setActiveLeagueId }),
}));

vi.mock("@/hooks/use-leagues", () => ({
  useLeagues: () => ({
    data: [
      { id: 1, name: "League One" },
      { id: 2, name: "League Two" },
    ],
    isLoading: false,
  }),
}));

vi.mock("@/components/ui/select", async () => {
  const React = await import("react");
  const SelectContext = React.createContext<{ onValueChange?: (value: string) => void } | null>(null);
  return {
    Select: ({ onValueChange, children }: { onValueChange?: (value: string) => void; children: React.ReactNode }) => (
      <SelectContext.Provider value={{ onValueChange }}>{children}</SelectContext.Provider>
    ),
    SelectTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectValue: ({ placeholder }: { placeholder?: string }) => <span>{placeholder}</span>,
    SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => {
      const context = React.useContext(SelectContext);
      return <button type="button" onClick={() => context?.onValueChange?.(value)}>{children}</button>;
    },
  };
});

const leagueThread = (leagueId: number): ChatThread => ({
  id: leagueId * 100,
  league_id: leagueId,
  thread_type: "league",
  title: "General",
  created_by_user_id: null,
  direct_user_low_id: null,
  direct_user_high_id: null,
  is_archived: false,
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  participants: [
    { user_id: 1, joined_at: "2026-08-01T12:00:00Z", display_name: "Avery", fantasy_team_name: "Avery Aces" },
    { user_id: 2, joined_at: "2026-08-01T12:00:00Z", display_name: "Blake", fantasy_team_name: "Blake Bears" },
  ],
  other_participant: null,
  last_message_preview: "Welcome",
  last_message_at: "2026-08-01T12:00:00Z",
  unread_count: 0,
});

const directThread = (leagueId: number): ChatThread => ({
  ...leagueThread(leagueId),
  id: leagueId * 100 + 1,
  thread_type: "direct",
  created_by_user_id: 1,
  direct_user_low_id: 1,
  direct_user_high_id: 2,
  participants: leagueThread(leagueId).participants,
  other_participant: leagueThread(leagueId).participants[1],
  last_message_preview: "Private note",
  unread_count: 2,
});

const chatMessage = (threadId: number, body: string, options: Partial<ChatMessage> = {}): ChatMessage => ({
  id: threadId * 10 + 1,
  thread_id: threadId,
  league_id: Math.floor(threadId / 100),
  sender_user_id: 2,
  message_type: "user",
  body,
  metadata: {},
  client_message_id: null,
  reply_to_message_id: null,
  edited_at: null,
  deleted_at: null,
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
  sender_display_name: "Blake",
  sender_fantasy_team_name: "Blake Bears",
  reply_to_message: null,
  ...options,
});

vi.mock("@/hooks/use-chat", () => ({
  useLeagueChatThreads: (leagueId?: number) => ({
    data: {
      data: leagueId === 2
        ? [leagueThread(2)]
        : [leagueThread(1), directThread(1)],
    },
    isLoading: false,
    isFetching: false,
    isError: false,
  }),
  useChatMessages: (leagueId?: number, threadId?: number) => ({
    data: {
      data: leagueId === 2
        ? [chatMessage(threadId ?? 200, "League two only")]
        : state.failedMessage
          ? [chatMessage(threadId ?? 100, "Failed message", { delivery_status: "failed", client_message_id: "failed-1", sender_user_id: 1 })]
          : threadId === 101
            ? [chatMessage(101, "Private note")]
          : [chatMessage(100, "League one only")],
      next_before_message_id: null,
      next_after_message_id: null,
    },
    isLoading: false,
    isError: false,
  }),
  useChatMessageUpdates: () => ({ isFetching: false }),
  useSendChatMessage: () => ({ mutate: state.sendMutate, isPending: false, isError: false }),
  useMarkChatThreadRead: () => ({ mutate: state.readMutate, isPending: false }),
  useCreateDirectChatThread: () => ({ mutate: state.directMutate, isPending: false, isError: false }),
}));

import Chats, { TradeFinalizedCard } from "./Chats";

afterEach(() => {
  cleanup();
  state.activeLeagueId = 1;
  state.failedMessage = false;
  state.sendMutate.mockReset();
  state.directMutate.mockReset();
  state.readMutate.mockReset();
  state.setActiveLeagueId.mockReset();
});

describe("Chats", () => {
  it("shows the master chat, isolates messages after league switching, and marks the viewed thread read", () => {
    render(<Chats />);

    expect(screen.getAllByText("# General").length).toBeGreaterThan(0);
    expect(screen.getByText("League one only")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(state.readMutate).toHaveBeenCalledWith(1001, expect.any(Object));

    fireEvent.click(screen.getByRole("button", { name: "League Two" }));

    expect(screen.getByText("League two only")).toBeTruthy();
    expect(screen.queryByText("League one only")).toBeNull();
  });

  it("creates a direct thread for the selected manager and sends a client-idempotent message", () => {
    render(<Chats />);

    fireEvent.click(screen.getByRole("button", { name: /new message/i }));
    fireEvent.click(screen.getByRole("button", { name: /Blake.*Blake Bears/i }));
    expect(state.directMutate).toHaveBeenCalledWith(2, expect.any(Object));

    fireEvent.change(screen.getByPlaceholderText("Message your league…"), { target: { value: "Good luck" } });
    fireEvent.click(screen.getByRole("button", { name: /^send$/i }));
    expect(state.sendMutate).toHaveBeenCalledWith(expect.objectContaining({
      body: "Good luck",
      client_message_id: expect.any(String),
    }));
  });

  it("shows retry for a failed optimistic message", () => {
    state.failedMessage = true;
    render(<Chats />);

    expect(screen.getByText("Failed to send")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(state.sendMutate).toHaveBeenCalledWith(expect.objectContaining({
      body: "Failed message",
      client_message_id: "failed-1",
    }));
    state.failedMessage = false;
  });
});

describe("TradeFinalizedCard", () => {
  it("renders pending and completed trade transfer states", () => {
    const message = {
      league_id: 4,
      body: "Trade finalized",
      metadata: {
        trade_id: 18,
        proposing_team: { name: "Saturday Stars" },
        receiving_team: { name: "Campus Kings" },
        proposing_team_sends: [{ player_id: 9, name: "Jeremiah Smith", position: "WR", school: "Ohio State" }],
        receiving_team_sends: [{ player_id: 10, name: "Ahmad Hardy", position: "RB", school: "Missouri" }],
        processing_status: "pending_transfer",
        players_process_at: "2026-09-07T04:00:00Z",
      },
    };
    const { rerender } = render(<TradeFinalizedCard message={message} />);

    expect(screen.getByText("Trade Finalized")).toBeTruthy();
    expect(screen.getByText(/Jeremiah Smith/)).toBeTruthy();
    expect(screen.getByText(/Ahmad Hardy/)).toBeTruthy();
    expect(screen.getByText(/Roster transfer pending/)).toBeTruthy();

    rerender(<TradeFinalizedCard message={{ ...message, metadata: { ...message.metadata, processing_status: "processed" } }} />);
    expect(screen.getByText("Roster transfer complete")).toBeTruthy();
  });
});
