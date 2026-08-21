// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { formatDisplayedProbabilityPair, WinChanceBar, WinChanceMeter } from "./WinChanceMeter";

afterEach(cleanup);

describe("WinChanceMeter", () => {
  it("formats the screenshot case as complementary one-decimal percentages", () => {
    expect(formatDisplayedProbabilityPair(48.05, 51.95)).toEqual({ left: 48.1, right: 51.9 });

    render(
      <WinChanceMeter
        myPercent={48.05}
        opponentPercent={51.95}
        myProjectedTotal={133.1}
        opponentProjectedTotal={137.0}
      />,
    );

    expect(screen.getByText("48.1% / 51.9%")).toBeTruthy();
    expect(screen.getByTestId("win-chance-left-bar").getAttribute("style")).toContain("48.05%");
    expect(screen.getByTestId("win-chance-right-bar").getAttribute("style")).toContain("51.95%");
    expect(screen.getByTestId("win-chance-left-bar").className).toContain("bg-cfb-brand");
    expect(screen.getByTestId("win-chance-right-bar").className).toContain("bg-cfb-pink");
  });

  it("uses a controlled unavailable state instead of a fabricated percentage", () => {
    render(<WinChanceMeter myPercent={null} opponentPercent={null} myProjectedTotal={null} opponentProjectedTotal={137} />);

    expect(screen.getByText("Win chance unavailable")).toBeTruthy();
    expect(screen.queryByTestId("win-chance-left-bar")).toBeNull();
  });

  it("allows matchup pages to use their crimson opponent identity without changing the default meter", () => {
    render(<WinChanceBar myPercent={45} opponentPercent={55} opponentColorClassName="bg-[#B42335]" testIdPrefix="crimson" />);

    expect(screen.getByTestId("crimson-right-bar").className).toContain("bg-[#B42335]");
  });
});
