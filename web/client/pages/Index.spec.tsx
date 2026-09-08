import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { SaturdayPick6HomeFeature } from "./Index";

describe("SaturdayPick6HomeFeature", () => {
  it("links to Pick 6 without mounting the contest results on Home", () => {
    render(<MemoryRouter><SaturdayPick6HomeFeature /></MemoryRouter>);

    expect(screen.getByRole("link", { name: "Open Pick 6" }).getAttribute("href")).toBe("/saturday-pick-6");
    expect(screen.queryByText("Live Results")).toBeNull();
  });
});
// @vitest-environment jsdom
