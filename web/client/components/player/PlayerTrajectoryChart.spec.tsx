// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlayerTrajectoryChart } from "./PlayerTrajectoryChart";

const renderChart = (points: Array<{ week: number; value: number | null; source: "preseason" | "current" | "published" | "bye" }>) =>
  render(
    <PlayerTrajectoryChart
      ariaLabel="Projection trajectory"
      points={points}
      yLabel="Points"
      yMax={30}
      valueFormatter={(value) => `${value.toFixed(1)} pts`}
    />,
  );

describe("PlayerTrajectoryChart", () => {
  afterEach(cleanup);

  it("renders a canonical weekly point without inventing a preseason week", () => {
    renderChart([{ week: 1, value: 18.4, source: "published" }]);

    expect(screen.getByText("Week 0–13 trajectory")).toBeTruthy();
    expect(screen.getByText("Preseason")).toBeTruthy();
    expect(screen.getByText("W13")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#5ee7ff']")).toHaveLength(0);
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle")).toHaveLength(1);
  });

  it("connects only consecutive published weekly records", () => {
    renderChart([
      { week: 1, value: 20.1, source: "published" },
      { week: 2, value: 18.4, source: "published" },
    ]);

    expect(screen.getByText("Week 0–13 trajectory")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("path[stroke='#5ee7ff']")).toHaveLength(1);
  });

  it("renders a bye without fabricating a zero-valued projection", () => {
    renderChart([{ week: 2, value: null, source: "bye" }]);

    expect(screen.getByText("BYE")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Projection trajectory" }).querySelectorAll("circle")).toHaveLength(0);
  });
});
