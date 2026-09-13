// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "@/lib/api";
import { useDraftPick, useDraftRoom } from "./use-draft";
import type { DraftRoom } from "@/types/draft";

vi.mock("@/lib/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
const room = (version = 1) => ({
  draft_id: 5, league_id: 77, draft_version: version, status: "on_clock", user_team_id: 1,
  picks: [], server_time: `2026-09-13T00:00:0${version}Z`,
} as unknown as DraftRoom);
const key = ["league", 77, "draft-room"];
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: 3 } } });
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { client, wrapper };
}
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe("draft transport races", () => {
  it("does not let an old in-flight GET overwrite a newer cache commit", async () => {
    const { client, wrapper } = setup();
    let resolve!: (room: DraftRoom) => void;
    vi.mocked(apiGet).mockImplementation(() => new Promise((done) => { resolve = done as typeof resolve; }));
    const { result } = renderHook(() => useDraftRoom(77), { wrapper });
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1));
    act(() => { client.setQueryData(key, room(3)); });
    await act(async () => { resolve(room(1)); });
    await waitFor(() => expect(result.current.isFetching).toBe(false));
    expect(result.current.data?.draft_version).toBe(3);
    client.clear();
  });
  it("does not let a delayed successful POST rewind a newer poll", async () => {
    const { client, wrapper } = setup();
    client.setQueryData(key, room());
    let resolve!: (room: DraftRoom) => void;
    vi.mocked(apiPost).mockImplementation(() => new Promise((done) => { resolve = done as typeof resolve; }));
    const { result } = renderHook(() => useDraftPick(77), { wrapper });
    let pending!: Promise<DraftRoom>;
    act(() => { pending = result.current.mutateAsync({ playerId: 7, pickNumber: 1, draftVersion: 1 }); });
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    act(() => { client.setQueryData(key, room(3)); });
    await act(async () => { resolve(room(2)); await pending; });
    expect(client.getQueryData<DraftRoom>(key)?.draft_version).toBe(3);
    client.clear();
  });
  it("never retries a rejected pick envelope", async () => {
    const { client, wrapper } = setup();
    client.setQueryData(key, room());
    vi.mocked(apiPost).mockRejectedValue(new Error("Pick expired"));
    vi.mocked(apiGet).mockResolvedValue(room(2));
    const { result } = renderHook(() => useDraftPick(77), { wrapper });
    await act(async () => { await expect(result.current.mutateAsync({ playerId: 7, pickNumber: 1, draftVersion: 1 })).rejects.toThrow("expired"); });
    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(client.getQueryData<DraftRoom>(key)?.draft_version).toBe(2);
    client.clear();
  });
  it("reconciles a lost POST response only when the exact own pick is committed", async () => {
    const { client, wrapper } = setup();
    client.setQueryData(key, room());
    vi.mocked(apiPost).mockRejectedValue(new Error("Network error"));
    const confirmed = { ...room(2), picks: [{ overall_pick: 1, player_id: 7, team_id: 1 }] } as DraftRoom;
    vi.mocked(apiGet).mockResolvedValue(confirmed);
    const { result } = renderHook(() => useDraftPick(77), { wrapper });
    await act(async () => { await expect(result.current.mutateAsync({ playerId: 7, pickNumber: 1, draftVersion: 1 })).resolves.toEqual(confirmed); });
    expect(apiPost).toHaveBeenCalledTimes(1);
    client.clear();
  });
});
