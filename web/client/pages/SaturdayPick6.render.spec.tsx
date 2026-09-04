// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const contestQuery = vi.hoisted(() => ({
  data: undefined as unknown,
  isLoading: false,
  isError: true,
  refetch: vi.fn(),
}));

vi.mock("@/hooks/use-saturday-pick", () => ({
  useSaturdayPickContest: () => contestQuery,
  useSaveSaturdayPick: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import SaturdayPick6, { SATURDAY_PICK_6_COMING_SOON_MESSAGE } from "./SaturdayPick6";

describe("SaturdayPick6 unavailable states", () => {
  afterEach(cleanup);

  beforeEach(() => {
    contestQuery.data = undefined;
    contestQuery.isLoading = false;
    contestQuery.isError = true;
  });

  it("keeps the direct route polished when the contest API is disabled or returns 404", () => {
    render(<MemoryRouter initialEntries={["/saturday-pick-6"]}><SaturdayPick6 /></MemoryRouter>);

    expect(screen.getByRole("heading", { name: "Saturday Pick 6" })).toBeTruthy();
    expect(screen.getByText(SATURDAY_PICK_6_COMING_SOON_MESSAGE)).toBeTruthy();
    expect(screen.getByText("West Georgia Cornhole")).toBeTruthy();
    expect(screen.getByText("#1 in All Things Cornhole & Outdoor Games")).toBeTruthy();
  });

  it("keeps an empty published response in the coming-soon state", () => {
    contestQuery.data = { status: "OPEN", players: [] };
    render(<MemoryRouter><SaturdayPick6 embedded /></MemoryRouter>);

    expect(screen.getByText(SATURDAY_PICK_6_COMING_SOON_MESSAGE)).toBeTruthy();
    expect(screen.getByRole("link", { name: "View Saturday Pick 6" }).getAttribute("href")).toBe("/saturday-pick-6");
  });

  it("makes the homepage sponsor tile open the full event where featured players are shown", () => {
    contestQuery.data = {
      id: 8,
      status: "SCORING",
      week_number: 1,
      contest_position: "QB",
      lock_at: "2026-09-05T16:00:00Z",
      players: [{
        id: 81,
        player_id: 18,
        canonical_position: "QB",
        player_name: "Featured Player",
        school: "West Georgia",
        opponent: "Opponent",
        game_time: "2026-09-05T16:00:00Z",
        image_url: null,
        projected_points: 21.4,
        live_points: 10.2,
        final_points: null,
        scoring_status: "LIVE",
        sort_order: 1,
      }],
      winning_player_ids: [],
      entry: null,
      sponsor: {
        name: "West Georgia Cornhole",
        logo_url: null,
        offer_text: "Partner offer",
        terms: null,
        reward_unlocked: false,
        code: null,
        url: null,
      },
    };
    render(<MemoryRouter><SaturdayPick6 embedded /></MemoryRouter>);

    expect(screen.getByRole("link", { name: "Open Saturday Pick 6 event" }).getAttribute("href")).toBe("/saturday-pick-6");
    expect(screen.getByRole("link", { name: "View Event" }).getAttribute("href")).toBe("/saturday-pick-6");
  });
});
