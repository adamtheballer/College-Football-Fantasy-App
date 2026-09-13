// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

const renderChart = (points: Array<{ week: number; value: number | null; actualValue?: number | null; source: "preseason" | "current" | "published" | "actual" | "bye" }>) =>
  render(
    <PlayerTrajectoryChart
      ariaLabel="Projection trajectory"
      points={points}
      yLabel="Points"
      yMax={30}
      valueFormatter={(value) => `${value.toFixed(1)} pts`}
      seriesKind="projection"
    />,
  );

describe("PlayerTrajectoryChart", () => {
  afterEach(cleanup);

  it("renders a canonical weekly preweek baseline without inventing a preseason point", () => {
    renderChart([{ week: 1, value: 18.4, source: "published" }]);

    expect(screen.getByText("Preweek baseline — actual fantasy points publish after each game")).toBeTruthy();
    expect(screen.getByText("Preweek")).toBeTruthy();
    expect(screen.getByText("Weekly projection")).toBeTruthy();
    expect(screen.getByText("Final fantasy points")).toBeTruthy();
    expect(screen.getByText("W13")).toBeTruthy();
    expect(screen.queryByTestId("trajectory-projection-line")).toBeNull();
    expect(screen.queryByTestId("trajectory-actual-line")).toBeNull();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
  });

  it("connects only consecutive published weekly records", () => {
    renderChart([
      { week: 1, value: 20.1, source: "published" },
      { week: 2, value: 18.4, source: "published" },
    ]);

    expect(screen.getByText("Preweek baseline — actual fantasy points publish after each game")).toBeTruthy();
    const projectionLine = screen.getByTestId("trajectory-projection-line");
    expect(projectionLine.getAttribute("stroke")).toBe("#ffffff");
    expect(projectionLine.getAttribute("stroke-dasharray")).toBe("7 7");
    expect(screen.getByTestId("trajectory-point-baseline-1-0").getAttribute("fill")).toBe("#ffffff");
  });

  it("uses blue only for actual fantasy-point totals", () => {
    renderChart([{ week: 1, value: 22.6, source: "actual" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#2f80ff']")).toHaveLength(1);
    expect(chart.querySelector("title")?.textContent).toContain("actual fantasy points");
  });

  it("connects consecutive actual fantasy totals with a solid blue line", () => {
    renderChart([
      { week: 1, value: 17.1, source: "actual" },
      { week: 2, value: 24.2, source: "actual" },
    ]);

    const actualLine = screen.getByTestId("trajectory-actual-line");
    expect(actualLine.getAttribute("stroke")).toBe("#2f80ff");
    expect(actualLine.getAttribute("stroke-dasharray")).toBeNull();
    expect(screen.queryByTestId("trajectory-projection-line")).toBeNull();
  });

  it("replaces a completed week's pregame estimate with its one final total", () => {
    renderChart([{ week: 1, value: 18.4, actualValue: 25.2, source: "published" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#5ee7ff']")).toHaveLength(0);
    expect(chart.querySelectorAll("circle[fill='#2f80ff']")).toHaveLength(1);
    expect(chart.querySelector("title")?.textContent).toBe("Week 1 actual fantasy points: 25.2 pts");
  });

  it("keeps each final total under the week that produced it", () => {
    renderChart([
      { week: 1, value: 20.0, actualValue: 17.1, source: "published" },
      { week: 2, value: 19.0, actualValue: 4.2, source: "published" },
    ]);

    const weekOne = screen.getByTestId("trajectory-point-actual-1-0");
    const weekTwo = screen.getByTestId("trajectory-point-actual-2-1");
    expect(weekOne.getAttribute("cx")).not.toBe(weekTwo.getAttribute("cx"));
    expect(weekOne.getAttribute("aria-label")).toContain("Week 1 actual fantasy points: 17.1 pts");
    expect(weekTwo.getAttribute("aria-label")).toContain("Week 2 actual fantasy points: 4.2 pts");
  });

  it("shows a precise value on hover and lets touch users toggle that value", () => {
    renderChart([{ week: 1, value: 18.4, source: "published" }]);

    const point = screen.getByTestId("trajectory-point-baseline-1-0");
    fireEvent.pointerEnter(point);
    expect(screen.getByTestId("trajectory-point-value").textContent).toContain("18.4 pts");

    fireEvent.pointerLeave(point);
    expect(screen.queryByTestId("trajectory-point-value")).toBeNull();

    fireEvent.click(point);
    expect(screen.getByTestId("trajectory-point-value").textContent).toContain("18.4 pts");
    fireEvent.click(point);
    expect(screen.queryByTestId("trajectory-point-value")).toBeNull();
  });

  it("keeps the value-history legend separate from the weekly points semantics", () => {
    render(
      <PlayerTrajectoryChart
        ariaLabel="Value trajectory"
        points={[{ week: 0, value: 91, source: "preseason" }]}
        yLabel="Value"
        yMax={100}
        valueFormatter={(value) => value.toFixed(0)}
        seriesKind="value"
      />,
    );

    expect(screen.getByText("Preseason baseline — weekly snapshots begin at Week 1")).toBeTruthy();
    expect(screen.getByText("Published weekly snapshot")).toBeTruthy();
    expect(screen.queryByText("Actual fantasy points")).toBeNull();
  });

  it("renders a bye without fabricating a zero-valued projection", () => {
    renderChart([{ week: 2, value: null, source: "bye" }]);

    expect(screen.getByText("BYE")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle")).toHaveLength(0);
  });
});
