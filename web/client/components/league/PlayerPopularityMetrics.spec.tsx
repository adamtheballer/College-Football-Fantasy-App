/** @vitest-environment jsdom */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerPopularityMetrics } from "./PlayerPopularityMetrics";

describe("PlayerPopularityMetrics", () => {
  it("distinguishes unavailable values from a truthful zero", () => {
    render(<PlayerPopularityMetrics popularity={{ rostered_percent: 0, start_percent: null }} />);

    expect(screen.getByText("Rostered 0.0%")).toBeTruthy();
    expect(screen.getByText("Start —")).toBeTruthy();
  });
});
