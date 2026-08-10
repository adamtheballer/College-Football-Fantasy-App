// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DraftLobby from "./DraftLobby";

const state = vi.hoisted(() => ({
  league: null as any,
  userId: 1,
  mutateAsync: vi.fn(),
  orderMutateAsync: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ leagueId: "77" }),
  };
});

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: state.userId } }),
}));

vi.mock("@/hooks/use-leagues", () => ({
  useLeagueDetail: () => ({ data: state.league, error: null, isLoading: false, refetch: vi.fn() }),
  useRescheduleDraft: () => ({ mutateAsync: state.mutateAsync, isPending: false }),
  useUpdateDraftOrder: () => ({ mutateAsync: state.orderMutateAsync, isPending: false }),
  useRotateLeagueInvite: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRevokeLeagueInvite: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/hooks/use-players", () => ({
  useDraftPlayerPool: () => ({ data: { total: 10_000 }, isLoading: false }),
}));

const makeLeague = (overrides: Record<string, unknown> = {}) => ({
  id: 77,
  name: "Countdown League",
  commissioner_user_id: 1,
  max_teams: 2,
  status: "pre_draft",
  invite_code: "COUNTDOWN",
  members: [
    { id: 1, user_id: 1, role: "commissioner" },
    { id: 2, user_id: 2, role: "member" },
  ],
  draft: {
    id: 5,
    league_id: 77,
    draft_datetime_utc: "2026-08-20T23:30:00Z",
    timezone: "America/New_York",
    draft_type: "snake",
    draft_order_mode: "random",
    pick_timer_seconds: 90,
    status: "scheduled",
  },
  draft_order: {
    draft_order_mode: "random",
    max_teams: 2,
    is_complete: false,
    entries: [
      { team_id: 11, team_name: "Coach1's Team", owner_user_id: 1, owner_name: "Coach1", draft_position: null },
      { team_id: 12, team_name: "Coach2's Team", owner_user_id: 2, owner_name: "Coach2", draft_position: null },
    ],
  },
  ...overrides,
});

const renderLobby = () => render(<MemoryRouter><DraftLobby /></MemoryRouter>);

beforeEach(() => {
  state.league = makeLeague();
  state.userId = 1;
  state.mutateAsync.mockReset();
  state.orderMutateAsync.mockReset();
  state.mutateAsync.mockResolvedValue({ ...state.league.draft });
  state.orderMutateAsync.mockResolvedValue({ ...state.league.draft_order });
});

afterEach(() => cleanup());

describe("DraftLobby rescheduling", () => {
  it("keeps countdown values and unit labels inside four compact mobile timer cards", () => {
    renderLobby();

    const countdownUnits = screen.getByTestId("draft-countdown-units");
    expect(countdownUnits.className).toContain("grid-cols-4");
    expect(screen.getByLabelText("Days").className).toContain("whitespace-nowrap");
    expect(screen.getByLabelText("Minutes").className).toContain("whitespace-nowrap");
  });

  it("shows the commissioner a visible league-timezone modal with the current schedule prefilled", () => {
    renderLobby();

    fireEvent.click(screen.getByRole("button", { name: "Reschedule Draft" }));

    expect(screen.getByRole("heading", { name: "Update Draft Time" })).toBeTruthy();
    expect((screen.getByLabelText("New date") as HTMLInputElement).value).toBe("2026-08-20");
    expect((screen.getByLabelText("New time") as HTMLInputElement).value).toBe("19:30");
    expect(screen.getAllByText(/America\/New_York/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Save New Draft Time" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeTruthy();
  });

  it("submits the league-local picker value as authoritative UTC and confirms success", async () => {
    renderLobby();
    fireEvent.click(screen.getByRole("button", { name: "Reschedule Draft" }));
    fireEvent.change(screen.getByLabelText("New date"), { target: { value: "2026-08-21" } });
    fireEvent.change(screen.getByLabelText("New time"), { target: { value: "20:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save New Draft Time" }));

    await waitFor(() => {
      expect(state.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
        draft_datetime_utc: "2026-08-22T00:00:00.000Z",
        timezone: "America/New_York",
      }));
    });
    expect(screen.getByRole("status").textContent).toContain("Draft time updated");
  });

  it("keeps the modal open and shows a controlled API error", async () => {
    state.mutateAsync.mockRejectedValueOnce(new Error("Draft has already started."));
    renderLobby();
    fireEvent.click(screen.getByRole("button", { name: "Reschedule Draft" }));
    fireEvent.click(screen.getByRole("button", { name: "Save New Draft Time" }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Draft has already started.");
    });
    expect(screen.getByRole("heading", { name: "Update Draft Time" })).toBeTruthy();
  });

  it("keeps editing controls away from ordinary members and started drafts", () => {
    state.userId = 2;
    const { rerender } = renderLobby();
    expect(screen.queryByRole("button", { name: "Reschedule Draft" })).toBeNull();

    state.userId = 1;
    state.league = makeLeague({ draft: { ...makeLeague().draft, status: "pre_draft" } });
    rerender(<MemoryRouter><DraftLobby /></MemoryRouter>);
    expect(screen.queryByRole("button", { name: "Reschedule Draft" })).toBeNull();
  });

  it("lets the commissioner select a custom order before every manager has joined", async () => {
    state.league = makeLeague({
      members: [{ id: 1, user_id: 1, role: "commissioner" }],
      draft_order: {
        draft_order_mode: "custom",
        max_teams: 2,
        is_complete: false,
        entries: [
          { team_id: 11, team_name: "Coach1's Team", owner_user_id: 1, owner_name: "Coach1", draft_position: 1 },
        ],
      },
    });
    renderLobby();

    expect(screen.getByText(/Empty slots are allowed now/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save Draft Order" }));

    await waitFor(() => {
      expect(state.orderMutateAsync).toHaveBeenCalledWith({
        draft_order_mode: "custom",
        entries: [{ team_id: 11, draft_position: 1 }],
      });
    });
  });
});
