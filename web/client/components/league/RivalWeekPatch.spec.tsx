// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import { RivalWeekPatch } from "./RivalWeekPatch";

afterEach(cleanup);

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: () => ({ matches: true }),
  });
});

describe("RivalWeekPatch", () => {
  it("uses an original bowl-game patch for a rivalry matchup", () => {
    render(
      <RivalWeekPatch
        leagueId={17}
        matchupId={42}
        rivalry={{ is_rivalry_matchup: true, series: { wins: 2, losses: 1, ties: 0 } }}
      />,
    );

    expect(screen.getByTestId("rival-week-patch")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Rivalry Bowl patch" })).toBe(screen.getByTestId("rival-bowl-emblem"));
    expect(screen.getByText("Rivalry Bowl")).toBeTruthy();
    expect(screen.getByText(/Rival week · Series: 2-1-0/)).toBeTruthy();
    expect(screen.queryByText("Rose Bowl")).toBeNull();
  });

  it("does not render outside of a rivalry matchup", () => {
    const { container } = render(<RivalWeekPatch leagueId={17} matchupId={42} rivalry={{ is_rivalry_matchup: false }} />);

    expect(container.innerHTML).toBe("");
  });
});
