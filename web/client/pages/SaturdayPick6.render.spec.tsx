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
    expect(screen.queryByText(/CFBFAN/i)).toBeNull();
  });

  it("keeps an empty published response in the coming-soon state", () => {
    contestQuery.data = { status: "OPEN", players: [] };
    render(<MemoryRouter><SaturdayPick6 embedded /></MemoryRouter>);

    expect(screen.getByText(SATURDAY_PICK_6_COMING_SOON_MESSAGE)).toBeTruthy();
  });
});
