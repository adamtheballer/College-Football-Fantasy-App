// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LeagueCard } from "./Leagues";

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
    render(
      <LeagueCard
        {...props}
        iconUrl="https://images.example.com/saturday-league.png"
      />,
    );

    expect(
      screen
        .getByRole("img", { name: "Saturday League league logo" })
        .getAttribute("src"),
    ).toBe("https://images.example.com/saturday-league.png");
    expect(screen.queryByLabelText("Default league trophy")).toBeNull();
  });

  it("keeps the trophy when the image is empty or fails to load", () => {
    const { rerender } = render(<LeagueCard {...props} iconUrl={null} />);
    expect(screen.getByLabelText("Default league trophy")).toBeTruthy();

    rerender(
      <LeagueCard
        {...props}
        iconUrl="https://images.example.com/missing.png"
      />,
    );
    fireEvent.error(
      screen.getByRole("img", { name: "Saturday League league logo" }),
    );
    expect(screen.getByLabelText("Default league trophy")).toBeTruthy();
  });

  it("opens the post-draft hub and never offers a completed league's draft room", () => {
    render(
      <LeagueCard
        {...props}
        status="post_draft"
        draftStatus="completed"
        iconUrl={null}
      />,
    );

    const openHubButton = screen
      .getAllByRole("button", { name: /Open League Hub/i })
      .find((element) => element.tagName === "BUTTON");
    expect(openHubButton).toBeTruthy();
    fireEvent.click(openHubButton!);
    expect(props.onOpen).toHaveBeenCalledWith(1);
    expect(
      screen.queryByRole("button", { name: /Join Draft Room/i }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Draft Room Locked/i }),
    ).toBeNull();
  });

  it("shows the signed-in manager's record, opponent, and canonical win chance", () => {
    render(<LeagueCard {...props} iconUrl={null} />);

    expect(screen.getByText("2-1")).toBeTruthy();
    expect(screen.getByText("Sunday Stars")).toBeTruthy();
    expect(screen.getByText("Win chance 52%")).toBeTruthy();
  });
});
