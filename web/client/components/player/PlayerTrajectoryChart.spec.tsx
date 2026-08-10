// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

const renderProjectionChart = (points: Array<{ week: number; value: number | null; actualValue?: number | null; source: "preweek" | "bye" }>) =>
  render(
    <PlayerTrajectoryChart
      ariaLabel="Projection trajectory"
      points={points}
      yLabel="Points"
      yMax={30}
      valueFormatter={(value) => `${value.toFixed(1)} pts`}
      series="projection"
    />,
  );

describe("PlayerTrajectoryChart", () => {
  afterEach(cleanup);

  it("renders a white pre-week point without inventing a preseason chart point", () => {
    renderProjectionChart([{ week: 1, value: 18.4, source: "preweek" }]);

    expect(screen.getByText("Pre-week projections and final actuals")).toBeTruthy();
    expect(screen.queryByText("Preseason")).toBeNull();
    expect(screen.getByText("W1")).toBeTruthy();
    expect(screen.getByText("W13")).toBeTruthy();
    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("path[stroke='#ffffff']")).toHaveLength(0);
    expect(chart.querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
    expect(chart.querySelectorAll("circle[fill='#3b82f6']")).toHaveLength(0);
  });

  it("connects only consecutive pre-week projection records", () => {
    renderProjectionChart([
      { week: 1, value: 20.1, source: "preweek" },
      { week: 2, value: 18.4, source: "preweek" },
    ]);

    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#ffffff']")).toHaveLength(1);
  });

  it("renders final actuals in blue only when final data is provided", () => {
    renderProjectionChart([{ week: 1, value: 20.1, actualValue: 15.3, source: "preweek" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
    expect(chart.querySelectorAll("circle[fill='#3b82f6']")).toHaveLength(1);
    expect(screen.getByText("Final actual")).toBeTruthy();
  });

  it("renders a bye without fabricating a zero-valued projection", () => {
    renderProjectionChart([{ week: 2, value: null, source: "bye" }]);

    expect(screen.getByText("BYE")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle")).toHaveLength(0);
  });

  it("keeps the separate value chart preseason baseline semantics", () => {
    render(
      <PlayerTrajectoryChart
        ariaLabel="Value trajectory"
        points={[{ week: 0, value: 91, source: "preseason" }]}
        yLabel="Value"
        yMax={100}
        valueFormatter={(value) => value.toFixed(0)}
        series="value"
      />,
    );

    expect(screen.getByText("Preseason")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Value trajectory" }).querySelectorAll("circle[fill='#5ee7ff']")).toHaveLength(1);
  });
});
