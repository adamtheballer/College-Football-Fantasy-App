// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  apiPost: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ isLoggedIn: true }),
}));

vi.mock("@/lib/api", () => ({
  apiPost: state.apiPost,
  getStoredAccessToken: () => "test-access-token",
}));

import CreateLeague, { leagueSizes } from "./CreateLeague";

const renderPage = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CreateLeague />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("CreateLeague standard rules", () => {
  beforeEach(() => {
    state.apiPost.mockReset();
    state.apiPost.mockResolvedValue({
      league: { id: 42 },
      invite_code: "LEAGUE42",
      invite_link: "https://example.test/join/LEAGUE42",
    });
  });

  afterEach(cleanup);

  it("offers 14 teams as the alpha maximum", () => {
    expect(leagueSizes).toEqual([4, 6, 8, 10, 12, 14]);
    expect(leagueSizes).not.toContain(16);
  });

  it("shows only playoffs, waiver system, and trade review on the settings step", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Continue to Settings" }));

    expect(screen.getByText("Playoff teams")).toBeTruthy();
    expect(screen.getByText("Waiver system")).toBeTruthy();
    expect(screen.getByText("Trade review")).toBeTruthy();
    expect(screen.queryByText("Roster format")).toBeNull();
    expect(screen.queryByText("Scoring settings")).toBeNull();
    expect(screen.queryByText("Processing time (local hour)")).toBeNull();
  });

  it("shows the alpha standard-rules acknowledgment without beta copy", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Continue to Settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue to Draft" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue to Review" }));

    const standardRulesNotice = screen.getByText(/Standard league rules:/);
    expect(standardRulesNotice).toBeTruthy();
    expect(standardRulesNotice.parentElement?.querySelector("svg")).toBeTruthy();
    expect(screen.getByText(/cannot be changed after league creation/i)).toBeTruthy();
    expect(screen.queryByText(/beta/i)).toBeNull();
  });

  it("submits the standard roster and managed processing schedule", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Continue to Settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue to Draft" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue to Review" }));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Create League" }));

    await waitFor(() => {
      expect(state.apiPost).toHaveBeenCalledWith(
        "/leagues",
        expect.objectContaining({
          settings: expect.objectContaining({
            roster_slots_json: {
              QB: 1,
              RB: 2,
              WR: 2,
              TE: 1,
              FLEX: 1,
              SUPERFLEX: 0,
              K: 1,
              BENCH: 5,
              IR: 1,
            },
            waiver_processing_weekday: 6,
            waiver_processing_hour: 8,
            waiver_timezone: "America/New_York",
          }),
        }),
      );
    });
  });
});
