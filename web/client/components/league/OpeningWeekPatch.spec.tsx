// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { OpeningWeekPatch } from "./OpeningWeekPatch";

afterEach(cleanup);

describe("OpeningWeekPatch", () => {
  it("appears for the opening week without requiring a rivalry", () => {
    render(createElement(OpeningWeekPatch, { week: 1 }));

    expect(screen.getByTestId("opening-week-patch")).toBeTruthy();
    expect(screen.getByText("Opening Week")).toBeTruthy();
  });

  it("does not occupy space after the opening week", () => {
    render(createElement(OpeningWeekPatch, { week: 2 }));

    expect(screen.queryByTestId("opening-week-patch")).toBeNull();
  });
});
