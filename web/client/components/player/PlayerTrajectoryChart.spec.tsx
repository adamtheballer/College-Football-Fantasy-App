// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
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
    expect(screen.getByText("Preweek baseline")).toBeTruthy();
    expect(screen.getByText("Actual fantasy points")).toBeTruthy();
    expect(screen.getByText("W13")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#5ee7ff']")).toHaveLength(0);
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
  });

  it("connects only consecutive published weekly records", () => {
    renderChart([
      { week: 1, value: 20.1, source: "published" },
      { week: 2, value: 18.4, source: "published" },
    ]);

    expect(screen.getByText("Preweek baseline — actual fantasy points publish after each game")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#5ee7ff']")).toHaveLength(1);
  });

  it("uses blue only for actual fantasy-point totals", () => {
    renderChart([{ week: 1, value: 22.6, source: "actual" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#2f80ff']")).toHaveLength(1);
    expect(chart.querySelector("title")?.textContent).toContain("actual fantasy points");
  });

  it("keeps the published pregame point and the final total visible for the same week", () => {
    renderChart([{ week: 1, value: 18.4, actualValue: 25.2, source: "published" }]);

    const chart = screen.getByRole("img", { name: "Projection trajectory" });
    expect(chart.querySelectorAll("circle[fill='#ffffff']")).toHaveLength(1);
    expect(chart.querySelectorAll("circle[fill='#2f80ff']")).toHaveLength(1);
    expect(chart.querySelectorAll("title")[1]?.textContent).toContain("actual fantasy points");
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
