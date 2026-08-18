// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DraftBoard } from "./DraftBoard";

describe("DraftBoard", () => {
  const slots = [
    { overallPick: 1, round: 1, roundPick: 1, teamId: 1, teamName: "Alpha", playerName: "Jamie Rivers", playerPosition: "QB", isCurrent: false, isUser: true },
    { overallPick: 2, round: 1, roundPick: 2, teamId: 2, teamName: "Beta", playerName: null, playerPosition: null, isCurrent: true, isUser: false },
    { overallPick: 3, round: 2, roundPick: 1, teamId: 2, teamName: "Beta", playerName: null, playerPosition: null, isCurrent: false, isUser: false },
    { overallPick: 4, round: 2, roundPick: 2, teamId: 1, teamName: "Alpha", playerName: null, playerPosition: null, isCurrent: false, isUser: true },
  ];

  afterEach(() => cleanup());

  it("keeps a compact grid of all picks and opens the existing roster view", async () => {
    const user = userEvent.setup();
    const onOpenRosters = vi.fn();
    render(<DraftBoard slots={slots} totalRounds={2} onOpenRosters={onOpenRosters} />);
    expect(screen.getByTestId("draft-board")).toBeTruthy();
    expect(screen.getByText("Jamie Rivers")).toBeTruthy();
    expect(screen.getByText("On the clock")).toBeTruthy();
    expect(screen.getByText("Your team")).toBeTruthy();
    expect(screen.getByTestId("draft-board-pick-1").className).toContain("bg-blue-400/[0.10]");
    expect(screen.getByTestId("draft-board-pick-2").className).not.toContain("bg-blue-400/[0.10]");
    await user.click(screen.getByRole("button", { name: /rosters/i }));
    expect(onOpenRosters).toHaveBeenCalledOnce();
  });

  it("provides a current-pick control when the board has an active pick", async () => {
    const user = userEvent.setup();
    render(<DraftBoard slots={slots} totalRounds={2} onOpenRosters={vi.fn()} followCurrentPick />);

    const currentPick = screen.getByRole("button", { name: /center board on the current draft pick/i });
    expect(currentPick).toBeTruthy();
    await user.click(currentPick);
    expect(screen.getByText("On the clock")).toBeTruthy();
  });
});
