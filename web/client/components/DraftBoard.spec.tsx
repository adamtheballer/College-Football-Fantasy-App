// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DraftBoard } from "./DraftBoard";

describe("DraftBoard", () => {
  const slots = [
    { overallPick: 1, round: 1, roundPick: 1, teamId: 1, teamName: "Alpha", playerName: "Jamie Rivers", playerPosition: "QB", isCurrent: false, isUser: true },
    { overallPick: 2, round: 1, roundPick: 2, teamId: 2, teamName: "Beta", playerName: null, playerPosition: null, isCurrent: true, isUser: false },
    { overallPick: 3, round: 2, roundPick: 1, teamId: 2, teamName: "Beta", playerName: null, playerPosition: null, isCurrent: false, isUser: false },
    { overallPick: 4, round: 2, roundPick: 2, teamId: 1, teamName: "Alpha", playerName: null, playerPosition: null, isCurrent: false, isUser: true },
  ];

  it("keeps a compact grid of all picks and opens the existing roster view", async () => {
    const user = userEvent.setup();
    const onOpenRosters = vi.fn();
    render(<DraftBoard slots={slots} totalRounds={2} onOpenRosters={onOpenRosters} />);
    expect(screen.getByTestId("draft-board")).toBeTruthy();
    expect(screen.getByText("Jamie Rivers")).toBeTruthy();
    expect(screen.getByText("On the clock")).toBeTruthy();
    expect(screen.getByText("Your team")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /rosters/i }));
    expect(onOpenRosters).toHaveBeenCalledOnce();
  });
});
