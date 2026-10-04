// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  DraftPlayerPickHorizon,
  getDraftPlayerPickHorizon,
} from "./DraftPlayerPickHorizon";

const slots = Array.from({ length: 24 }, (_, index) => ({
  overallPick: index + 1,
  isUser: index === 11 || index === 12 || index === 23,
}));

afterEach(() => cleanup());

describe("draft player pick horizon", () => {
  it("puts pick 12 between the 11th and 12th available players", () => {
    expect(getDraftPlayerPickHorizon(slots, 1)).toEqual({
      overallPick: 12,
      rowIndex: 11,
    });
  });

  it("moves up as other managers pick and reaches the first row on the user's turn", () => {
    expect(getDraftPlayerPickHorizon(slots, 8)).toEqual({
      overallPick: 12,
      rowIndex: 4,
    });
    expect(getDraftPlayerPickHorizon(slots, 12)).toEqual({
      overallPick: 12,
      rowIndex: 0,
    });
    expect(getDraftPlayerPickHorizon(slots, 13)).toEqual({
      overallPick: 13,
      rowIndex: 0,
    });
    expect(getDraftPlayerPickHorizon(slots, 14)).toEqual({
      overallPick: 24,
      rowIndex: 10,
    });
  });

  it("does not show a stale marker after the user's final pick", () => {
    expect(getDraftPlayerPickHorizon(slots, 25)).toBeNull();
    expect(getDraftPlayerPickHorizon(slots, 0)).toBeNull();
  });

  it("renders an accessible line and next-pick label", () => {
    render(<DraftPlayerPickHorizon overallPick={12} />);
    expect(
      screen.getByRole("status", { name: "Your next draft pick is pick 12" }),
    ).toBeTruthy();
    expect(screen.getByText("Your pick #12")).toBeTruthy();
  });
});
