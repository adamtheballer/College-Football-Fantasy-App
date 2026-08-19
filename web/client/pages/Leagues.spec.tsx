// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LeagueCard, orderLeaguesByRecent } from "./Leagues";

const props = {
  id: 1,
  name: "Saturday League",
  status: "pre_draft",
  teams: 12,
  memberCount: 1,
  draftLabel: "August 20",
  draftDateTime: "2026-08-20T19:00:00Z",
  isPrivate: true,
  draftStatus: "scheduled",
  currentUserSummary: {
    wins: 2,
    losses: 1,
    ties: 0,
    opponent_team_name: "Sunday Stars",
    matchup_week: 1,
    projected_points_for: 133.1,
    projected_points_against: 127.6,
    win_probability_for: 52.4,
  },
  onOpen: vi.fn(),
  onOpenDraft: vi.fn(),
};

afterEach(() => {
  cleanup();
  props.onOpen.mockReset();
  props.onOpenDraft.mockReset();
});

describe("LeagueCard", () => {
  it("renders the saved league image inside the trophy tile", () => {
    render(<LeagueCard {...props} iconUrl="https://images.example.com/saturday-league.png" />);

    expect(screen.getByRole("img", { name: "Saturday League league logo" }).getAttribute("src")).toBe(
      "https://images.example.com/saturday-league.png"
    );
    expect(screen.queryByLabelText("Default league trophy")).toBeNull();
  });

  it("keeps the trophy when the image is empty or fails to load", () => {
    const { rerender } = render(<LeagueCard {...props} iconUrl={null} />);
    expect(screen.getByLabelText("Default league trophy")).toBeTruthy();

    rerender(<LeagueCard {...props} iconUrl="https://images.example.com/missing.png" />);
    fireEvent.error(screen.getByRole("img", { name: "Saturday League league logo" }));
    expect(screen.getByLabelText("Default league trophy")).toBeTruthy();
  });

  it("opens the post-draft hub and never offers a completed league's draft room", () => {
    render(
      <LeagueCard
        {...props}
        status="post_draft"
        draftStatus="completed"
        iconUrl={null}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /Saturday League/i }));
    expect(props.onOpen).toHaveBeenCalledWith(1);
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("shows the signed-in manager's compact record and projection metadata", () => {
    render(<LeagueCard {...props} iconUrl={null} />);

    expect(screen.getByText("Record 2-1")).toBeTruthy();
    expect(screen.getByText("Proj 133.1")).toBeTruthy();
    expect(screen.getByText("Week 1 · 52% win")).toBeTruthy();
    expect(screen.queryByText("Sunday Stars")).toBeNull();
  });
});

describe("orderLeaguesByRecent", () => {
  it("places recently opened leagues first and preserves the remaining server order", () => {
    expect(orderLeaguesByRecent([
      { id: 1, name: "First" },
      { id: 2, name: "Second" },
      { id: 3, name: "Third" },
    ], [3, 1])).toEqual([
      { id: 3, name: "Third" },
      { id: 1, name: "First" },
      { id: 2, name: "Second" },
    ]);
  });
});
