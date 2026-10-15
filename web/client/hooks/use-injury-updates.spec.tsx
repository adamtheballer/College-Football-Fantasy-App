// @vitest-environment jsdom
import { cleanup, renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "@/lib/api";
import { useDraftPlayerPool } from "./use-players";
import { useInjuryUpdates } from "./use-injury-updates";
vi.mock("@/lib/api", () => ({ apiGet: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("shared current injury feed", () => {
  it("updates draft badges from the live feed without downloading the board again", async () => {
    let status = "PROBABLE";
    vi.mocked(apiGet).mockImplementation(async (path) => {
      if (path === "/injuries") return { data: [{ player_id: 7, status }], season: 2026, week: 6, total: 1 } as never;
      if (path === "/players") return { data: [{ id: 7, name: "Runner", school: "Texas", position: "RB", master_draft_rank: 1, draft_ranking_version: "injury-test" }], total: 1, limit: 100, offset: 0, ranking_version: "injury-test", ranking_season: 2026, ranking_week: 7 } as never;
      return { data: [] } as never;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const hook = renderHook(() => ({ board: useDraftPlayerPool(), feed: useInjuryUpdates() }), { wrapper });
    await waitFor(() => expect(hook.result.current.board.data?.data[0].status).toBe("PROBABLE"));
    const injuryCalls = vi.mocked(apiGet).mock.calls.filter(([path]) => path === "/injuries");
    expect(injuryCalls).toHaveLength(1);
    expect(injuryCalls[0][1]).toEqual({ season: undefined, week: undefined });
    const boardCalls = vi.mocked(apiGet).mock.calls.filter(([path]) => path === "/players").length;
    status = "OUT";
    await act(async () => { await hook.result.current.feed.refetch(); });
    await waitFor(() => expect(hook.result.current.board.data?.data[0].status).toBe("OUT"));
    expect(vi.mocked(apiGet).mock.calls.filter(([path]) => path === "/players")).toHaveLength(boardCalls);
    client.clear();
  });

  it("preserves loaded reports when a refresh fails", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce({ data: [{ player_id: 7, status: "OUT" }], season: 2026, week: 6, total: 1 });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const hook = renderHook(() => useInjuryUpdates(), { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
    await waitFor(() => expect(hook.result.current.isSuccess).toBe(true));
    vi.mocked(apiGet).mockRejectedValueOnce(new Error("network unavailable"));
    await act(async () => { await hook.result.current.refetch(); });
    await waitFor(() => expect(hook.result.current.isError).toBe(true));
    expect(hook.result.current.data?.data[0].status).toBe("OUT");
    client.clear();
  });
});
