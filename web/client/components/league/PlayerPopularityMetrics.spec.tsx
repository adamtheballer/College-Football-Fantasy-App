/** @vitest-environment jsdom */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerPopularityMetrics } from "./PlayerPopularityMetrics";

describe("PlayerPopularityMetrics", () => {
  it("shows the start rate without rendering a rostered percentage", () => {
    render(<PlayerPopularityMetrics popularity={{ start_percent: 0 }} />);

    expect(screen.getByText("Start 0.0%")).toBeTruthy();
    expect(screen.queryByText(/Rostered/)).toBeNull();
  });
});
